#!/usr/bin/env python3
"""
SNOWMAN PC Prototype v1.5 – lokal teneste
GNSS/NTRIP-bru, førargrensesnitt og lagring av arbeidsøkter.

Flow:
  GNSS/Leica serial <-> SNOWMAN NTRIP <-> NTRIP caster
  Browser UI         <-> localhost HTTP/WebSocket-like polling API

No third-party packages required for the core service.
Windows COM ports are supported through a tiny PowerShell serial bridge if pyserial
is not installed; installing pyserial is recommended for reliable binary RTCM.
"""
import argparse, base64, json, os, re, socket, threading, time, http.server, urllib.parse, urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
DATA=HERE/"data"; SESS=DATA/"sessions"
CFG_FILE=HERE/"snowman-config.local.json"   # lokal, aldri i git (sjå .gitignore)
VENDOR={"leaflet.js":"application/javascript","leaflet.css":"text/css"}

STATE = {
    "version":"1.5","running":True,"serial_connected":False,"ntrip_connected":False,
    "port":"","baud":115200,"caster":"","mountpoint":"","bytes_rtcm":0,
    "last_gga":"","fix":"NO DATA","satellites":0,"hdop":None,"altitude":None,
    "lat":None,"lon":None,"last_error":"","last_update":0
}
CFG = {"serial_port":"","baud":115200,"caster":"","caster_port":2101,"mountpoint":"",
       "username":"","password":"","gga_interval":5}
def load_cfg():
    try: CFG.update({k:v for k,v in json.loads(CFG_FILE.read_text("utf-8")).items() if k in CFG})
    except FileNotFoundError: pass
    except Exception as e: print("Kunne ikkje lese config:",e)
def save_cfg():
    try: CFG_FILE.write_text(json.dumps(CFG,indent=1),"utf-8")
    except Exception as e: print("Kunne ikkje lagre config:",e)
LOCK=threading.Lock()
STOP=threading.Event()
serial_obj=None
ntrip_sock=None

def update(**kw):
    with LOCK:
        STATE.update(kw); STATE["last_update"]=time.time()

def nmea_coord(v, hemi, is_lat):
    if not v: return None
    n=2 if is_lat else 3
    deg=float(v[:n]); mins=float(v[n:])
    x=deg+mins/60.0
    return -x if hemi in ("S","W") else x

def parse_gga(line):
    try:
        p=line.strip().split(",")
        if len(p)<10 or not p[0].endswith("GGA"): return
        q=int(p[6] or 0)
        names={0:"NO FIX",1:"GPS",2:"DGPS",4:"RTK FIX",5:"RTK FLOAT",6:"DR"}
        update(last_gga=line.strip(), fix=names.get(q,f"FIX {q}"),
               satellites=int(p[7] or 0), hdop=float(p[8]) if p[8] else None,
               altitude=float(p[9]) if p[9] else None,
               lat=nmea_coord(p[2],p[3],True), lon=nmea_coord(p[4],p[5],False))
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
                update(last_error="pyserial manglar. Køyr INSTALL.bat først.")
                time.sleep(3); continue
            serial_obj=serial.Serial(CFG["serial_port"], int(CFG["baud"]), timeout=.2)
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
        if u.path=="/ntrip":
            p=Path(__file__).with_name("ntrip.html")
            self.headers_ok(200,"text/html; charset=utf-8"); self.wfile.write(p.read_bytes()); return
        if u.path.startswith("/vendor/") and u.path[8:] in VENDOR:
            self.headers_ok(200,VENDOR[u.path[8:]]); self.wfile.write((HERE/"vendor"/u.path[8:]).read_bytes()); return
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
        n=int(self.headers.get("Content-Length","0")); body=self.rfile.read(n)
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
        if self.path=="/api/sessions/clear":
            for f in SESS.glob("*.json"): f.unlink()
            self.headers_ok(); self.wfile.write(b'{"ok":true}'); return
        self.headers_ok(404); self.wfile.write(b'{"error":"not found"}')

def safe_id(x): return re.sub(r"[^A-Za-z0-9_-]","",str(x))[:64]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--http-port",type=int,default=8765)
    ap.add_argument("--serial",help="Seriellport for GNSS, t.d. COM3 eller /dev/ttyUSB0")
    a=ap.parse_args()
    load_cfg()
    if a.serial: CFG["serial_port"]=a.serial; save_cfg()
    threading.Thread(target=serial_loop,daemon=True).start()
    threading.Thread(target=ntrip_loop,daemon=True).start()
    print(f"SNOWMAN PC Prototype v1.5 køyrer: http://127.0.0.1:{a.http_port}")
    try: http.server.ThreadingHTTPServer(("127.0.0.1",a.http_port),API).serve_forever()
    except KeyboardInterrupt: pass
    finally: STOP.set()

if __name__=="__main__": main()
