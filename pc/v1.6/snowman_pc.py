#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""
SNOWMAN PC Prototype v1.6 – lokal teneste
GNSS/NTRIP-bru, Terrain Engine (snødjupne), førargrensesnitt og lagring av arbeidsøkter.

Flow:
  GNSS/Leica serial <-> SNOWMAN NTRIP <-> NTRIP caster
  Browser UI         <-> localhost HTTP/WebSocket-like polling API

No third-party packages required for the core service.
Windows COM ports are supported through a tiny PowerShell serial bridge if pyserial
is not installed; installing pyserial is recommended for reliable binary RTCM.
"""
VERSION="1.6.13"   # versjonen som er i bruk (same som APP_VERSION i driver.html)
import argparse, base64, json, math, os, re, socket, threading, time, http.server, urllib.parse, urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
DATA=HERE/"data"; SESS=DATA/"sessions"
CFG_FILE=HERE/"snowman-config.local.json"   # lokal, aldri i git (sjå .gitignore)
VENDOR={"leaflet.js":"application/javascript","leaflet.css":"text/css","qrcode.js":"application/javascript","three.snowman.min.js":"application/javascript"}
import terrain as T
TERR=T.TerrainLibrary(DATA/"terrain")
import kontroll as K
KON=K.Kontroll(DATA/"kontroll.json",TERR if T.AVAILABLE else None,T.utm_inverse)
SIM_FASIT=DATA/"sim-fasit.json"   # skriven av simuler-leica.py: simulert snødjupne der maskina står (berre test)
def sim_truth():
    """Fasit frå simulatoren, berre når mottakaren er simulert og fila er fersk."""
    if not STATE.get("simulated"): return None
    try:
        if time.time()-SIM_FASIT.stat().st_mtime>3: return None
        return json.loads(SIM_FASIT.read_text()).get("snow")
    except Exception: return None

STATE = {
    "version":VERSION,"running":True,"serial_connected":False,"ntrip_connected":False,
    "port":"","baud":115200,"caster":"","mountpoint":"","bytes_rtcm":0,
    "last_gga":"","fix":"NO DATA","satellites":0,"hdop":None,"altitude":None,
    "lat":None,"lon":None,"last_error":"","last_update":0
}
CFG = {"serial_port":"","baud":115200,"caster":"","caster_port":2101,"mountpoint":"",
       "username":"","password":"","gga_interval":5,
       "antZ":2.8,"zOff":0.0,"heightMode":"nn2000","geoidN":None,"calibrated":False,"hudLan":False}
def load_cfg():
    try: CFG.update({k:v for k,v in json.loads(CFG_FILE.read_text("utf-8")).items() if k in CFG})
    except FileNotFoundError: pass
    except Exception as e: print("Kunne ikkje lese config:",e)
REAL_PORT=[None]   # seriellporten til ekte mottakar; simulatorporten blir aldri lagra i innstillingane
def save_cfg():
    d=dict(CFG)
    if REAL_PORT[0] is not None: d["serial_port"]=REAL_PORT[0]
    try: CFG_FILE.write_text(json.dumps(d,indent=1),"utf-8")
    except Exception as e: print("Kunne ikkje lagre config:",e)
HUD={"t":0}   # siste tilstand frå førarskjermen (prep, tid, demo, mål), til HUD-visinga
DEPTH_TXT={"OUTSIDE":"UTANFOR TERRENGMODELL","NO_CAL":"KALIBRERING MANGLAR","NO_FIX":"IKKJE MÅLT – KREV RTK FIX",
    "NEGATIVE":"FEIL – SJEKK HØGDESYSTEM/KALIBRERING","NO_ENGINE":"TERRENGMOTOR MANGLAR","NO_HEIGHT":"INGA GNSS-HØGD","NO_GEOID":"GEOIDEHØGD MANGLAR"}

def hud_state():
    """HUD-data sett saman i tenesta: GNSS og snødjupne direkte frå mottakaren (alltid ferske),
    prepareringsstatus frå førarskjermen. Då stoppar ikkje HUD sjølv om førarskjermen ligg i bakgrunnen."""
    now=time.time(); drv=dict(HUD); drv_age=now-drv.get("t",0); fresh_drv=drv_age<15
    gnss_age=now-STATE.get("last_update",0); gnss_ok=STATE.get("serial_connected") and STATE.get("lat") is not None and gnss_age<5
    if fresh_drv and drv.get("demo"):
        out=drv; age=drv_age
    elif gnss_ok:
        out={k:drv.get(k) for k in ("preparing","elapsed","distance","area","target","tol","bounds")} if fresh_drv else {"target":0.8,"tol":0.1}
        d=STATE.get("depth"); ter=STATE.get("terrain") or {}
        out.update(src="gnss",demo=bool(STATE.get("simulated")),fix=STATE.get("fix"),sats=STATE.get("satellites"),
                   speed=round((STATE.get("speed") or 0)*3.6,1),heading=STATE.get("course"),
                   depth=d,depthNote=ter.get("name","") if d is not None else DEPTH_TXT.get(STATE.get("depth_status"),"IKKJE MÅLT"))
        age=gnss_age
    elif fresh_drv:
        out=drv; age=drv_age
    else:
        out={"fix":"AV"}; age=min(drv_age,gnss_age)
    out["age"]=age; out["t"]=now-age
    out["reason"]="" if age<5 else ("Ingen GNSS-data og førarskjermen er ikkje open" if not gnss_ok else "")
    return out
LOCK=threading.Lock()
STOP=threading.Event()
serial_obj=None
ntrip_sock=None

HUD_TICK=threading.Condition()   # varslar HUD-straumane kvar gong ny GNSS-posisjon kjem
def update(**kw):
    with LOCK:
        STATE.update(kw); STATE["last_update"]=time.time()
    if "last_gga" in kw:
        with HUD_TICK: HUD_TICK.notify_all()

def nmea_coord(v, hemi, is_lat):
    if not v: return None
    n=2 if is_lat else 3
    deg=float(v[:n]); mins=float(v[n:])
    x=deg+mins/60.0
    return -x if hemi in ("S","W") else x

_prev={"p":None,"t":0,"v":0.0,"h":None}
def _motion(lat,lon):
    """Fart (m/s) og kurs (grader) frå to GGA-posisjonar – så tenesta kan forsyne HUD utan førarskjermen."""
    now=time.time(); pr=_prev
    if pr["p"] is None or lat is None: pr.update(p=(lat,lon),t=now); return pr["v"],pr["h"]
    la0,lo0=pr["p"]; dy=(lat-la0)*111320; dx=(lon-lo0)*111320*math.cos(math.radians(lat)); d=math.hypot(dx,dy); dt=now-pr["t"]
    if d>=0.3 and dt>0:
        pr["v"]=0.6*(d/dt)+0.4*pr["v"]; pr["h"]=(math.degrees(math.atan2(dx,dy))+360)%360; pr.update(p=(lat,lon),t=now)
    elif dt>3: pr["v"]=0.0; pr.update(t=now)
    return pr["v"],pr["h"]

def parse_gga(line):
    try:
        p=line.strip().split(",")
        if len(p)<10 or not p[0].endswith("GGA"): return
        q=int(p[6] or 0)
        names={0:"NO FIX",1:"GPS",2:"DGPS",4:"RTK FIX",5:"RTK FLOAT",6:"DR"}
        fix=names.get(q,f"FIX {q}")
        alt=float(p[9]) if p[9] else None
        sep=float(p[11]) if len(p)>11 and p[11] else None
        lat,lon=nmea_coord(p[2],p[3],True), nmea_coord(p[4],p[5],False)
        # Terrain Engine: terrenghøgd under maskina og snødjupne
        ter=TERR.height(lat,lon) if (lat is not None and lon is not None) else None
        depth,dstat,det=T.snow_depth(alt,sep,fix,ter,CFG) if T.AVAILABLE else (None,"NO_ENGINE",{})
        update(last_gga=line.strip(), fix=fix,
               satellites=int(p[7] or 0), hdop=float(p[8]) if p[8] else None,
               altitude=alt, geoid_sep=sep, lat=lat, lon=lon,
               terrain=ter, depth=None if depth is None else round(depth,3), depth_status=dstat, depth_detail=det)
        v,h=_motion(lat,lon); update(speed=round(v,2), course=None if h is None else round(h))
    except Exception as e: update(last_error=f"GGA parse: {e}")

def serial_loop():
    global serial_obj
    while not STOP.is_set():
        try:
            if not CFG["serial_port"]:
                time.sleep(1); continue
            try:
                import serial
            except ImportError:
                update(last_error="pyserial manglar. Køyr INSTALLER-WINDOWS.bat (Windows) eller start-snowman.sh (Linux).")
                time.sleep(3); continue
            # serial_for_url: vanleg port (COM3, /dev/ttyUSB0) eller simulator over TCP (socket://127.0.0.1:7777)
            serial_obj=serial.serial_for_url(CFG["serial_port"], baudrate=int(CFG["baud"]), timeout=.2)
            update(serial_connected=True, port=CFG["serial_port"], baud=int(CFG["baud"]), last_error="")
            buf=b""
            while not STOP.is_set() and serial_obj.is_open:
                b=serial_obj.read(4096)
                if b:
                    buf+=b
                    while b"\n" in buf:
                        raw,buf=buf.split(b"\n",1)
                        line=raw.decode("ascii","ignore").strip()
                        if line.startswith("$") and "GGA" in line: parse_gga(line)
                else: time.sleep(.02)
        except Exception as e:
            update(serial_connected=False,last_error=f"Serial: {e}")
            try:
                if serial_obj: serial_obj.close()
            except: pass
            serial_obj=None; time.sleep(2)

def connect_ntrip():
    host=CFG["caster"].replace("http://","").replace("https://","").split("/")[0]
    port=int(CFG["caster_port"])
    mp=CFG["mountpoint"].lstrip("/")
    s=socket.create_connection((host,port),timeout=10)
    auth=base64.b64encode(f'{CFG["username"]}:{CFG["password"]}'.encode()).decode()
    req=(f"GET /{mp} HTTP/1.0\r\nUser-Agent: SNOWMAN-NTRIP/1.1\r\n"
         f"Authorization: Basic {auth}\r\nAccept: */*\r\nConnection: close\r\n\r\n")
    s.sendall(req.encode())
    head=b""
    while b"\r\n\r\n" not in head and len(head)<16384:
        head+=s.recv(1)
    first=head.split(b"\r\n",1)[0].decode("latin1","ignore")
    if not ("200" in first or "ICY 200" in first):
        raise RuntimeError("NTRIP svar: "+first)
    s.settimeout(1)
    return s

def ntrip_loop():
    global ntrip_sock
    last_gga_sent=0
    while not STOP.is_set():
        try:
            if not (CFG["caster"] and CFG["mountpoint"]):
                time.sleep(1); continue
            ntrip_sock=connect_ntrip()
            update(ntrip_connected=True,caster=CFG["caster"],mountpoint=CFG["mountpoint"],last_error="")
            while not STOP.is_set():
                now=time.time()
                gga=STATE.get("last_gga","")
                if gga and now-last_gga_sent>=float(CFG["gga_interval"]):
                    ntrip_sock.sendall((gga+"\r\n").encode("ascii","ignore")); last_gga_sent=now
                try: data=ntrip_sock.recv(4096)
                except socket.timeout: continue
                if not data: raise ConnectionError("Caster lukka sambandet")
                if serial_obj and getattr(serial_obj,"is_open",False):
                    serial_obj.write(data)
                update(bytes_rtcm=STATE["bytes_rtcm"]+len(data))
        except Exception as e:
            update(ntrip_connected=False,last_error=f"NTRIP: {e}")
            try:
                if ntrip_sock: ntrip_sock.close()
            except: pass
            ntrip_sock=None; time.sleep(3)

class API(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def headers_ok(self, code=200, typ="application/json"):
        self.send_response(code); self.send_header("Content-Type",typ)
        if typ.startswith("text/html") or typ=="application/json":
            self.send_header("Cache-Control","no-cache")   # ny versjon blir alltid vist etter oppdatering
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS"); self.end_headers()
    def do_OPTIONS(self): self.headers_ok(204)
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=="/api/status":
            self.headers_ok(); self.wfile.write(json.dumps(STATE).encode()); return
        if u.path=="/":
            p=Path(__file__).with_name("driver.html")
            self.headers_ok(200,"text/html; charset=utf-8"); self.wfile.write(p.read_bytes()); return
        if u.path=="/api/terrain":
            self.headers_ok(); self.wfile.write(json.dumps({"available":T.AVAILABLE,"error":T.IMPORT_ERROR,
                "types":T.TYPES,"layers":TERR.listing() if T.AVAILABLE else [],
                "calibration":{k:CFG[k] for k in ("antZ","zOff","heightMode","geoidN","calibrated")}}).encode()); return
        if u.path=="/api/control":
            r=KON.listing(CFG,STATE); r.update(ok=True,simTruth=sim_truth(),fix=STATE.get("fix"),depth=STATE.get("depth"),
                raw=(STATE.get("depth_detail") or {}).get("raw"),depth_status=STATE.get("depth_status"),zOff=CFG["zOff"],calibrated=CFG["calibrated"])
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/terrain/patch":   # terrengutsnitt rundt maskina til 3D-visinga
            q=urllib.parse.parse_qs(u.query)
            try:
                half=min(400.0,max(20.0,float(q.get("half",["150"])[0]))); step=min(5.0,max(0.5,float(q.get("step",["1"])[0])))
                P=TERR.patch(float(q["lat"][0]),float(q["lon"][0]),half,step) if T.AVAILABLE else None
                r={"ok":False} if P is None else {"ok":True,"lat0":P["lat0"],"lon0":P["lon0"],"half":P["half"],"step":P["step"],"n":P["n"],
                   "layers":P["layers"],"h":base64.b64encode(P["h"].astype("<f4").tobytes()).decode()}
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/terrain/height":
            q=urllib.parse.parse_qs(u.query)
            try: r=TERR.height(float(q["lat"][0]),float(q["lon"][0]))
            except Exception as e: r={"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/hud/stream":   # HUD-straum (Server-Sent Events): ny melding med éin gong ny posisjon kjem
            self.send_response(200); self.send_header("Content-Type","text/event-stream")
            self.send_header("Cache-Control","no-cache"); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
            try:
                while not STOP.is_set():
                    self.wfile.write(b"data: "+json.dumps(hud_state()).encode()+b"\n\n"); self.wfile.flush()
                    with HUD_TICK: HUD_TICK.wait(1.0)   # ny GNSS-posisjon (5 Hz), elles kvart sekund
            except (BrokenPipeError,ConnectionResetError,OSError): pass
            return
        if u.path=="/api/hud":
            self.headers_ok(); self.wfile.write(json.dumps(hud_state()).encode()); return
        if u.path=="/api/info":
            self.headers_ok(); self.wfile.write(json.dumps({"lan_ip":lan_ip(),"hud_lan":HUDLAN["srv"] is not None,
                "hud_port":HUD_PORT,"hud_url":f"http://{lan_ip()}:{HUD_PORT}/hud"}).encode()); return
        if u.path=="/hud":
            p=Path(__file__).with_name("hud.html")
            self.headers_ok(200,"text/html; charset=utf-8"); self.wfile.write(p.read_bytes()); return
        if u.path=="/ntrip":
            p=Path(__file__).with_name("ntrip.html")
            self.headers_ok(200,"text/html; charset=utf-8"); self.wfile.write(p.read_bytes()); return
        if u.path.startswith("/vendor/") and u.path[8:] in VENDOR:
            self.headers_ok(200,VENDOR[u.path[8:]]); self.wfile.write((HERE/"vendor"/u.path[8:]).read_bytes()); return
        m=re.fullmatch(r"/tiles/(\d{1,2})/(\d{1,8})/(\d{1,8})",u.path)
        if m:  # lokale kartfliser for offline drift: data/tiles/{z}/{x}/{y}.png|.jpg
            for ext,typ in ((".png","image/png"),(".jpg","image/jpeg"),(".jpeg","image/jpeg"),(".webp","image/webp")):
                f=DATA/"tiles"/m[1]/m[2]/(m[3]+ext)
                if f.exists():
                    self.send_response(200); self.send_header("Content-Type",typ)
                    self.send_header("Cache-Control","max-age=86400"); self.end_headers()
                    self.wfile.write(f.read_bytes()); return
            self.send_response(404); self.end_headers(); return
        if u.path=="/api/sessions":
            out=[]
            for f in sorted(SESS.glob("*.json")):
                try:
                    d=json.loads(f.read_text("utf-8")); pts=d.get("points",[])
                    out.append({k:d.get(k) for k in ("id","date","start","end","durationMs","demo","distance","machine","width")}|{"n":len(pts)})
                except Exception: pass
            self.headers_ok(); self.wfile.write(json.dumps(out).encode()); return
        if u.path=="/api/session":
            sid=urllib.parse.parse_qs(u.query).get("id",[""])[0]
            f=SESS/f"{safe_id(sid)}.json"
            if sid and f.exists(): self.headers_ok(); self.wfile.write(f.read_bytes()); return
        self.headers_ok(404); self.wfile.write(b'{"error":"not found"}')
    def do_POST(self):
        global CFG
        n=int(self.headers.get("Content-Length","0"))
        u=urllib.parse.urlparse(self.path)
        if u.path=="/api/terrain/analyse":  # filopplasting blir straumd til disk
            name=urllib.parse.parse_qs(u.query).get("file",["opplasting"])[0]
            tmp=DATA/"upload"; tmp.mkdir(parents=True,exist_ok=True)
            f=tmp/(uuid4hex()+Path(name).suffix.lower())
            try:
                left=n
                with open(f,"wb") as out:
                    while left>0:
                        b=self.rfile.read(min(1<<20,left))
                        if not b: break
                        out.write(b); left-=len(b)
                if not T.AVAILABLE: raise RuntimeError(T.IMPORT_ERROR)
                r=TERR.analyse(f,name)
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"errors":[str(e)],"warnings":[],"info":{}}).encode())
            finally:
                try: f.unlink()
                except Exception: pass
            return
        body=self.rfile.read(n)
        if self.path=="/api/config":
            try:
                d=json.loads(body or b"{}")
                for k in CFG:
                    if k in d and not (k=="password" and d[k] in ("***",)): CFG[k]=d[k]
                save_cfg(); update(last_error="")
                self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"config":{**CFG,"password":"***" if CFG["password"] else ""}}).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/session":
            try:
                d=json.loads(body or b"{}"); sid=safe_id(d.get("id",""))
                if not sid: raise ValueError("manglar id")
                SESS.mkdir(parents=True,exist_ok=True)
                tmp=SESS/f"{sid}.tmp"; tmp.write_text(json.dumps(d),"utf-8"); tmp.replace(SESS/f"{sid}.json")
                self.headers_ok(); self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path.startswith("/api/control/"):
            try:
                d=json.loads(body or b"{}"); a=self.path[13:]
                if a=="check": r={"ok":True,"check":KON.add_check(STATE,CFG,d.get("known"),d.get("note",""),sim_truth())}
                elif a=="check/delete": KON.delete_check(d["id"]); r={"ok":True}
                elif a=="point": r={"ok":True,"point":KON.add_point(d.get("name"),d.get("E"),d.get("N"),d.get("zone",32),d.get("h"))}
                elif a=="point/delete": KON.delete_point(d["id"]); r={"ok":True}
                elif a=="apply-offset":
                    z,m=KON.apply_offset(CFG); save_cfg(); r={"ok":True,"zOff":z,"change":m}
                else: raise ValueError("Ukjend kontroll-handling")
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path in ("/api/terrain/import","/api/terrain/update","/api/terrain/delete","/api/calibration"):
            try:
                d=json.loads(body or b"{}")
                if self.path=="/api/calibration":
                    for k in ("antZ","zOff","heightMode","geoidN","calibrated"):
                        if k in d: CFG[k]=d[k]
                    save_cfg(); r={"ok":True}
                elif not T.AVAILABLE: raise RuntimeError(T.IMPORT_ERROR)
                elif self.path=="/api/terrain/import":
                    r={"ok":True,"layer":TERR.import_pending(d.get("token"),d.get("name","").strip(),d.get("type","barmark"),
                        d.get("priority"),d.get("replace") or None,d.get("source",""),bool(d.get("vdatumConfirmed")))}
                elif self.path=="/api/terrain/update":
                    r={"ok":True,"layer":TERR.update(d["id"],name=d.get("name"),active=d.get("active"),priority=d.get("priority"))}
                else:
                    TERR.delete(d["id"]); r={"ok":True}
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/hudlan":
            try:
                on=bool(json.loads(body or b"{}").get("enable")); err=set_hud_lan(on); CFG["hudLan"]=on and not err; save_cfg()
                self.headers_ok(); self.wfile.write(json.dumps({"ok":not err,"error":err,"hud_lan":HUDLAN["srv"] is not None,
                    "hud_url":f"http://{lan_ip()}:{HUD_PORT}/hud"}).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/hud":
            try:
                d=json.loads(body or b"{}"); d["t"]=time.time(); HUD.clear(); HUD.update(d)
                self.headers_ok(); self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/sessions/clear":
            for f in SESS.glob("*.json"): f.unlink()
            self.headers_ok(); self.wfile.write(b'{"ok":true}'); return
        self.headers_ok(404); self.wfile.write(b'{"error":"not found"}')

def uuid4hex():
    import uuid; return uuid.uuid4().hex

def safe_id(x): return re.sub(r"[^A-Za-z0-9_-]","",str(x))[:64]

# --- HUD på mobil/eiga eining: eigen, avgrensa port på lokalnettet. Berre HUD-sida og HUD-data – ingen styring. ---
HUD_PORT=8766
HUDLAN={"srv":None}
def lan_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.connect(("10.255.255.255",1)); ip=s.getsockname()[0]; s.close(); return ip
    except Exception: return "127.0.0.1"

class HUDOnly(API):
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path in ("/","/hud","/api/hud","/api/hud/stream"):
            if u.path=="/": self.path="/hud"
            return API.do_GET(self)
        self.send_response(403); self.end_headers()
    def do_POST(self):
        self.send_response(403); self.end_headers()

def set_hud_lan(on):
    """Start/stopp HUD-porten. Returnerer feiltekst eller ''."""
    if on and HUDLAN["srv"] is None:
        try:
            srv=http.server.ThreadingHTTPServer(("0.0.0.0",HUD_PORT),HUDOnly)
        except OSError as e:
            return f"Kunne ikkje opne port {HUD_PORT}: {e}"
        HUDLAN["srv"]=srv; threading.Thread(target=srv.serve_forever,daemon=True).start()
        print(f"HUD på mobil (same nett): http://{lan_ip()}:{HUD_PORT}/hud")
    elif not on and HUDLAN["srv"] is not None:
        srv=HUDLAN["srv"]; HUDLAN["srv"]=None; threading.Thread(target=srv.shutdown,daemon=True).start()
    return ""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--http-port",type=int,default=8765)
    ap.add_argument("--lan",action="store_true",help="Slå på HUD for mobil/eiga eining i same nett (port 8766, berre HUD)")
    ap.add_argument("--serial",help="Seriellport for GNSS, t.d. COM3 eller /dev/ttyUSB0")
    ap.add_argument("--simulert",action="store_true",help="Mottakaren er simulatoren: alt blir merka som TEST/simulert")
    a=ap.parse_args()
    load_cfg()
    STATE["simulated"]=a.simulert
    if a.serial:
        if a.simulert: REAL_PORT[0]=CFG["serial_port"]; CFG["serial_port"]=a.serial   # berre for denne økta
        else: CFG["serial_port"]=a.serial; save_cfg()
    threading.Thread(target=serial_loop,daemon=True).start()
    threading.Thread(target=ntrip_loop,daemon=True).start()
    print(f"SNOWMAN PC v{VERSION} køyrer: http://127.0.0.1:{a.http_port}")
    if a.lan or CFG.get("hudLan"): set_hud_lan(True)
    # Hovudtenesta (styring, innstillingar) er berre tilgjengeleg på denne PC-en.
    try: http.server.ThreadingHTTPServer(("127.0.0.1",a.http_port),API).serve_forever()
    except KeyboardInterrupt: pass
    finally: STOP.set()

if __name__=="__main__": main()
