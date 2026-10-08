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
VERSION="1.6.56"   # versjonen som er i bruk (same som APP_VERSION i driver.html)
import sys
import argparse, base64, json, math, os, re, socket, threading, time, http.server, urllib.parse, urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
DATA=HERE/"data"; SESS=DATA/"sessions"
CFG_FILE=HERE/"snowman-config.local.json"   # lokal, aldri i git (sjå .gitignore)
VENDOR={"leaflet.js":"application/javascript","leaflet.css":"text/css","qrcode.js":"application/javascript","three.snowman.min.js":"application/javascript","snowman-icon.png":"image/png"}
import terrain as T
TERR=T.TerrainLibrary(DATA/"terrain")
import kontroll as K
import helling as HL
HEL=HL.Helling()   # hellingskorreksjon: antenna står ikkje rett over beltet når maskina står på skrå
import feltlogg as F
LOG=F.FeltLogg(DATA/"logg")   # feltlogg: alt frå mottakaren + det SNOWMAN rekna ut (Innst. › System)

import traceback, platform
def where(e):
    """Kvar i koden ein feil oppstod (fil:linje i funksjon) – til feltloggen."""
    tb=traceback.extract_tb(e.__traceback__) if e is not None and e.__traceback__ else []
    return f" [{Path(tb[-1].filename).name}:{tb[-1].lineno} i {tb[-1].name}]" if tb else ""
def _thread_err(a):
    LOG.event(f"Programfeil i tråd {a.thread.name if a.thread else '?'}: {a.exc_type.__name__}: {a.exc_value}{where(a.exc_value)}",err=True)
threading.excepthook=_thread_err
_old_hook=sys.excepthook
def _main_err(t,v,tb):
    try: LOG.event(f"Programfeil: {t.__name__}: {v}{where(v)}",err=True)
    except Exception: pass
    _old_hook(t,v,tb)
sys.excepthook=_main_err

def log_changes(what,before,after,keys):
    """Endra innstillingar til feltloggen (passord og brukarnamn blir aldri skrivne – berre at dei er endra)."""
    ch=[]
    for k in keys:
        a,b=before.get(k),after.get(k)
        if a!=b: ch.append(f"{k}: endra" if k in ("password","username") else f"{k}: {a} → {b}")
    if ch: LOG.event(f"Innstilling endra ({what}): "+"; ".join(ch))

def start_log(note):
    """Start feltloggen og skriv ei oppstartsblokk med alt som trengst for å forstå loggen (aldri passord)."""
    if LOG.active(): return LOG.name
    name=LOG.start(note)
    try:
        LOG.event(f"Oppstart: SNOWMAN v{VERSION} · {platform.platform()} · Python {platform.python_version()}")
        LOG.event(f"Kalibrering: antennehøgd {CFG['antZ']} m, høgdekorreksjon {CFG['zOff']} m, høgdeval {CFG['heightMode']}"
                  f"{', fast geoidehøgd '+str(CFG['geoidN']) if CFG.get('heightMode')=='ellipsoid' else ''}, lagra {bool(CFG.get('calibrated'))}")
        LOG.event(f"Helling: {CFG.get('tiltMode')}, snu fram/bak {bool(CFG.get('tiltFlipPitch'))}, snu side {bool(CFG.get('tiltFlipRoll'))}")
        LOG.event(f"Mottakar: port {CFG['serial_port'] or '-'} @ {CFG['baud']}, oppstartskommandoar {'ja' if (CFG.get('initCmds') or '').strip() else 'nei'}")
        LOG.event(f"NTRIP: {CFG['caster'] or '-'}:{CFG['caster_port']}/{CFG['mountpoint'] or '-'}, versjon {CFG.get('ntrip_version')}, "
                  f"vakthund {CFG.get('ntrip_timeout')} s, GGA kvart {CFG['gga_interval']} s, brukar sett {'ja' if CFG['username'] else 'nei'}")
        if T.AVAILABLE:
            ls=[f"{m.get('name')} ({m.get('type')}, {m.get('res')} m, {'aktiv' if m.get('active') else 'av'})" for m in TERR.listing()]
            LOG.event("Terrenglag: "+("; ".join(ls) if ls else "ingen"))
        try:
            u=json.loads(UI_CFG.read_text("utf-8")); c=u.get("cfg",u) if isinstance(u,dict) else {}
            LOG.event("Maskin: "+", ".join(f"{k} {c.get(k)}" for k in ("mname","machine","blade","bladeN","tiller","tillerN","target","tol","detail3d") if k in c))
        except Exception: pass
        if STATE.get("client_info"): LOG.event("Skjerm/3D: "+STATE["client_info"])
    except Exception as e: LOG.event(f"Kunne ikkje skrive oppstartsblokka: {e}{where(e)}",err=True)
    return name
KON=K.Kontroll(DATA/"kontroll.json",TERR if T.AVAILABLE else None,T.utm_inverse)
try:
    import trasear as TR   # trasear (yttergrenser), forbodne område og prosent preparert – krev numpy som Terrain Engine
    TRA=TR.Trasear(DATA/"trasear.json",SESS)
    OBJ=TR.Objekt(DATA/"objekt.json")   # hindringar (punkt) med varsel på skjerm og HUD
    import drivstoff as DS   # drivstoff (manuelt) og rapport per prepareringsdøgn
    FUEL=DS.Drivstoff(DATA/"drivstoff.json",TRA)
except ImportError as e:
    TR=TRA=FUEL=OBJ=None; TRA_ERR=str(e)
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
       "ntrip_version":"auto","ntrip_timeout":20,   # NTRIP 1/2/auto, og vakthund: sekund utan korreksjonar før ny oppkopling
       "antZ":2.8,"zOff":0.0,"heightMode":"nn2000","geoidN":None,"calibrated":False,
       "tiltMode":"auto","tiltFlipPitch":False,"tiltFlipRoll":False,
       "initCmds":"",   # oppstartskommandoar til mottakaren (éin per linje), sende når seriellporten blir opna
       "hudLan":False}
def load_cfg():
    try: CFG.update({k:v for k,v in json.loads(CFG_FILE.read_text("utf-8")).items() if k in CFG})
    except FileNotFoundError: pass
    except Exception as e: print("Kunne ikkje lese config:",e)
REAL_PORT=[None]   # seriellporten til ekte mottakar; simulatorporten blir aldri lagra i innstillingane
def save_cfg():
    d=dict(CFG)
    if REAL_PORT[0] is not None: d["serial_port"]=REAL_PORT[0]
    try:
        tmp=CFG_FILE.with_name(CFG_FILE.name+".tmp"); tmp.write_text(json.dumps(d,indent=1),"utf-8"); os.replace(tmp,CFG_FILE)
    except Exception as e: print("Kunne ikkje lagre config:",e)
HUD={"t":0}   # siste tilstand frå førarskjermen (prep, tid, demo, mål), til HUD-visinga
DEPTH_TXT={"OUTSIDE":"UTANFOR TERRENGMODELL","NO_CAL":"KALIBRERING MANGLAR","NO_FIX":"IKKJE MÅLT – KREV RTK FIX",
    "NEGATIVE":"FEIL – SJEKK HØGDESYSTEM/KALIBRERING","NO_ENGINE":"TERRENGMOTOR MANGLAR","NO_HEIGHT":"INGA GNSS-HØGD","NO_GEOID":"GEOIDEHØGD MANGLAR"}

def hud_state():
    """HUD-data sett saman i tenesta: GNSS og snødjupne direkte frå mottakaren (alltid ferske),
    prepareringsstatus frå førarskjermen. Då stoppar ikkje HUD sjølv om førarskjermen ligg i bakgrunnen."""
    now=time.time(); drv=dict(HUD); drv_age=now-drv.get("t",0); fresh_drv=drv_age<15
    # Alderen på GNSS-data er tida sidan siste tolka GGA – ikkje siste oppdatering av noko i STATE (NTRIP o.l.)
    gnss_age=now-STATE.get("gga_time",0); gnss_ok=STATE.get("serial_connected") and STATE.get("lat") is not None and gnss_age<5
    if fresh_drv and drv.get("demo"):
        out=drv; age=drv_age
    elif gnss_ok:
        out={k:drv.get(k) for k in ("preparing","elapsed","distance","area","target","tol","bounds","trase","warn","warnLevel","ahead")} if fresh_drv else {"target":0.8,"tol":0.1}
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
    out["reason"]="" if age<5 else ("Mottakaren har slutta å sende posisjon" if STATE.get("serial_connected") and STATE.get("gga_time")
                                      else "Ingen GNSS-data og førarskjermen er ikkje open")
    return out
LOCK=threading.Lock()
STOP=threading.Event()
serial_obj=None
ntrip_sock=None

UI_CFG=DATA/"ui-config.json"   # innstillingane i førarskjermen – same i kiosk og vanleg vindauge
def write_atomic(path,text):
    """Skriv trygt: først til mellombels fil, så bytt ut. Straumbrot midt i gir aldri ei halvskriven fil."""
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+".tmp")
    with open(tmp,"w",encoding="utf-8") as f:
        f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)
import oppstart as O
from rtcm import RtcmMonitor
import ntripklient as NK
RTCM=RtcmMonitor()   # kontroll av korreksjonane (gyldige rammer, meldingstypar, basestasjon)
def system_cfg():
    d=O.system_cfg(); d["autostart"]=O.autostart_status(); return d
RESTART=[False]   # «Start SNOWMAN på nytt» etter oppdatering: tenesta avsluttar med kode 3
SERVER=[None]   # hovudtenesta, så «Avslutt SNOWMAN» kan stoppe ho
HUD_TICK=threading.Condition()   # varslar HUD-straumane kvar gong ny GNSS-posisjon kjem
def update(**kw):
    with LOCK:
        STATE.update(kw); STATE["last_update"]=time.time()
        if "last_gga" in kw: STATE["gga_time"]=STATE["last_update"]   # berre ein tolka posisjon gjer GNSS-data «ferske»
    if "last_gga" in kw:
        with HUD_TICK: HUD_TICK.notify_all()

def nmea_check(line):
    """NMEA-sjekksum: XOR av teikna mellom «$» og «*» skal vere lik dei to hex-sifra etter «*».
    Returnerer True (rett), False (feil) eller None (linja har ingen sjekksum)."""
    if "*" not in line: return None
    body,_,ck=line[1:].partition("*")
    try: want=int(ck.strip()[:2],16)
    except ValueError: return False
    x=0
    for ch in body: x^=ord(ch)
    return x==want

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
    if lat is None or lon is None:   # ingen posisjon (tunnel, NO FIX): ikkje lagre tomt punkt – då ville neste utrekning feile
        pr["v"]=0.0; return pr["v"],pr["h"]
    if pr["p"] is None or pr["p"][0] is None: pr.update(p=(lat,lon),t=now); return pr["v"],pr["h"]
    la0,lo0=pr["p"]; dy=(lat-la0)*111320; dx=(lon-lo0)*111320*math.cos(math.radians(lat)); d=math.hypot(dx,dy); dt=now-pr["t"]
    if d>=0.3 and dt>0:
        pr["v"]=0.6*(d/dt)+0.4*pr["v"]; pr["h"]=(math.degrees(math.atan2(dx,dy))+360)%360; pr.update(p=(lat,lon),t=now)
    elif dt>3: pr["v"]=0.0; pr.update(t=now)
    return pr["v"],pr["h"]

LOGRATE={}   # siste tid ei hending av same slag vart skriven i feltloggen (unngår tusenvis av like linjer)
def parse_gga(line):
    try:
        p=line.strip().split(",")
        if len(p)<10 or not p[0].endswith("GGA"): return
        q=int(p[6] or 0)
        # GGA-kvalitet: 9 = SBAS/EGNOS (NovAtel-baserte mottakarar, t.d. GeoMax Zenith) – betre enn GPS, men ikkje RTK
        names={0:"NO FIX",1:"GPS",2:"DGPS",3:"PPS",4:"RTK FIX",5:"RTK FLOAT",6:"DR",7:"MANUELL",8:"SIMULERT",9:"SBAS"}
        fix=names.get(q,f"FIX {q}")
        prev=STATE.get("fix")
        if prev!=fix and prev not in (None,"NO DATA"):   # endring i fix-type til feltloggen (RTK FIX → FLOAT er ein feil)
            LOG.event(f"Fix: {prev} → {fix} ({p[7] or '?'} satellittar)",err=(prev=="RTK FIX"))
        alt=float(p[9]) if p[9] else None
        sep=float(p[11]) if len(p)>11 and p[11] else None
        # Alder på korreksjonane (s) og ID til basestasjonen som mottakaren brukar (GGA-felt 13 og 14): viser om
        # mottakaren faktisk brukar korreksjonane. Tomt = mottakaren brukar ingen.
        try: corr_age=float(p[13]) if len(p)>13 and p[13] else None
        except ValueError: corr_age=None
        base_id=(p[14].split("*")[0].strip() or None) if len(p)>14 else None
        lat,lon=nmea_coord(p[2],p[3],True), nmea_coord(p[4],p[5],False)
        v,h=_motion(lat,lon); HEL.add_position(lat,lon,alt)
        # Hellingskorreksjon: finn punktet der maskina står (under midten) og høgda ned til snøflata
        cal=CFG; mlat,mlon=lat,lon; tilt={"src":"av"}
        gN=T.GEOID.n(lat,lon) if T.AVAILABLE else None   # Kartverket-geoiden der antenna er
        if CFG.get("heightMode")=="geoide": cal=dict(CFG,_N=gN)
        if T.AVAILABLE and lat is not None and lon is not None:
            g,tilt=HEL.gradient(lat,lon,alt,h,v,TERR,CFG)
            tilt["ant"]=sorted(HEL.sentences)   # kva hellingsmeldingar antenna har sendt
            if g is not None:
                mlat,mlon,ant_v,shift=HL.correct(lat,lon,g,float(CFG.get("antZ",0)))
                cal=dict(cal,antZ=ant_v); tilt.update(shift=round(shift,2),dz=round(float(CFG.get("antZ",0))-ant_v,3))
        # Terrain Engine: terrenghøgd under maskina og snødjupne
        ter=TERR.height(mlat,mlon) if (mlat is not None and mlon is not None) else None
        depth,dstat,det=T.snow_depth(alt,sep,fix,ter,cal) if T.AVAILABLE else (None,"NO_ENGINE",{})
        pst=STATE.get("depth_status")
        if pst is not None and pst!=dstat:   # kvifor forsvann (eller kom) snødjupna – med tala i augneblinken
            LOG.event(f"Snødjupne-status: {pst} → {dstat} ({DEPTH_TXT.get(dstat,'OK') if dstat!='OK' else 'snødjupne blir vist'}); "
                      f"høgd {det.get('H')}, overflate {det.get('surface')}, terreng {det.get('terrain')}, rå {det.get('raw')}, "
                      f"lag {(ter or {}).get('name','-')}",err=dstat in ("NEGATIVE","NO_GEOID","NO_HEIGHT","NO_ENGINE"))
        update(last_gga=line.strip(), fix=fix,
               satellites=int(p[7] or 0), hdop=float(p[8]) if p[8] else None,
               altitude=alt, geoid_sep=sep, lat=lat, lon=lon, tilt=tilt, geoid_model=None if gN is None else round(gN,3),
               h_nn2000=None if T.nn2000_height(alt,sep,lat,lon,CFG) is None else round(T.nn2000_height(alt,sep,lat,lon,CFG),3),
               h_ell=None if alt is None else round(alt+(sep or 0),3), corr_age=corr_age, base_id=base_id,
               terrain=ter, depth=None if depth is None else round(depth,3), depth_status=dstat, depth_detail=det)
        update(speed=round(v,2), course=None if h is None else round(h))
        LOG.row(STATE,CFG)
    except Exception as e:
        update(last_error=f"GGA parse: {e}")
        if time.time()-LOGRATE.get("gga",0)>60: LOGRATE["gga"]=time.time(); LOG.event(f"Kunne ikkje tolke GGA: {e}{where(e)}",err=True)

def serial_loop():
    global serial_obj
    while not STOP.is_set():
        try:
            if not CFG["serial_port"]:
                if STATE.get("serial_connected"): update(serial_connected=False)
                time.sleep(1); continue
            try:
                import serial
            except ImportError:
                update(last_error="pyserial manglar. Køyr INSTALLER-WINDOWS.bat (Windows) eller start-snowman.sh (Linux).")
                time.sleep(3); continue
            # serial_for_url: vanleg port (COM3, /dev/ttyUSB0) eller simulator over TCP (socket://127.0.0.1:7777)
            # write_timeout: skriving til ein Bluetooth-port som har mista sambandet skal ikkje kunne henge for alltid
            serial_obj=serial.serial_for_url(CFG["serial_port"], baudrate=int(CFG["baud"]), timeout=.2, write_timeout=1)
            update(serial_connected=True, port=CFG["serial_port"], baud=int(CFG["baud"]), last_error="")
            LOG.event(f"Mottakar tilkopla: {CFG['serial_port']} @ {CFG['baud']}")
            # Oppstartskommandoar til mottakaren (valfritt, avhengig av merke – GeoMax Zenith35 Pro treng ingen)
            for cmd in str(CFG.get("initCmds") or "").splitlines():
                if cmd.strip():
                    serial_obj.write((cmd.strip()+"\r\n").encode("ascii","ignore")); LOG.event("Sendt til mottakar: "+cmd.strip()); time.sleep(0.3)
            buf=b""; opened=(CFG["serial_port"],int(CFG["baud"]),CFG.get("initCmds")); bad_n=0; gnss_lost=False
            while not STOP.is_set() and serial_obj.is_open:
                if (CFG["serial_port"],int(CFG["baud"]),CFG.get("initCmds"))!=opened:   # endra i oppsettet: opne på nytt
                    LOG.event("Mottakaroppsett endra – opnar porten på nytt"); serial_obj.close()
                    update(serial_connected=False); serial_obj=None; break
                b=serial_obj.read(4096)
                ga=time.time()-(STATE.get("gga_time") or time.time())
                if ga>5 and not gnss_lost:
                    gnss_lost=True; LOG.event(f"Mottakaren har slutta å sende posisjon (ingen GGA på {ga:.0f} s)",err=True)
                elif gnss_lost and ga<1:
                    gnss_lost=False; LOG.event("Posisjon frå mottakaren er tilbake")
                if b:
                    buf+=b
                    while b"\n" in buf:
                        raw,buf=buf.split(b"\n",1)
                        line=raw.decode("ascii","ignore").strip()
                        if line: LOG.raw(line)
                        if line.startswith("$"):
                            ok=nmea_check(line)
                            # Feil sjekksum = bitfeil i overføringa: linja blir forkasta (ingen feil høgd inn i snødjupna,
                            # ingen øydelagd GGA til casteren). Linjer utan sjekksum (nokre eldre mottakarar) blir godtekne og talde.
                            if ok is False:
                                update(nmea_bad=STATE.get("nmea_bad",0)+1); bad_n+=1
                                if time.time()-LOGRATE.get("cs",0)>60:
                                    LOGRATE["cs"]=time.time(); LOG.event(f"NMEA med feil sjekksum forkasta: {bad_n} sidan sist",err=True); bad_n=0
                                continue
                            if ok is None: update(nmea_nock=STATE.get("nmea_nock",0)+1)
                        if line.startswith("$") and "GGA" in line: parse_gga(line)
                        elif line.startswith("$"): HEL.feed(line)   # hellingsmålar i antenna, om ho har
                        elif line and line.isprintable(): update(rx_text=line[:120])   # svar på kommandoar o.l. (t.d. «<OK»)
                else: time.sleep(.02)
            update(serial_connected=False)   # løkka slutta (port lukka/endra) – aldri «TILKOPLA» utan open port
        except Exception as e:
            update(serial_connected=False,last_error=f"Serial: {e}")
            LOG.event(f"Mottakar-feil: {e}{'' if isinstance(e,OSError) else where(e)}",err=True)
            try:
                if serial_obj: serial_obj.close()
            except: pass
            serial_obj=None; time.sleep(2)

def ntrip_loop():
    """Hentar korreksjonar frå casteren og sender dei uendra vidare til mottakaren.
    Vakthund (v1.6.41): kjem det ingen data på CFG["ntrip_timeout"] sekund, blir sambandet kopla opp på nytt
    (mobilnettet kan «henge» utan at sambandet blir lukka – då ville SNOWMAN elles vente i det uendelege)."""
    global ntrip_sock
    last_rtcm_log=0; last_wfail=0
    while not STOP.is_set():
        stream=None
        try:
            if not (CFG["caster"] and CFG["mountpoint"]):
                time.sleep(1); continue
            gga=STATE.get("last_gga") or None
            stream=NK.open_stream(CFG["caster"],CFG["caster_port"],CFG["mountpoint"],CFG["username"],CFG["password"],
                                  str(CFG.get("ntrip_version") or "auto"),VERSION,gga)
            ntrip_sock=stream; RTCM.reset()
            update(ntrip_connected=True,ntrip_proto=stream.proto,ntrip_wait=0,caster=CFG["caster"],mountpoint=CFG["mountpoint"],last_error="")
            LOG.event(f"NTRIP tilkopla ({stream.proto}): {CFG['caster']} / {CFG['mountpoint']}")
            nkey=lambda:(CFG["caster"],CFG["caster_port"],CFG["mountpoint"],CFG["username"],CFG["password"],CFG.get("ntrip_version")); opened=nkey()
            last_data=time.time(); last_gga_sent=0
            while not STOP.is_set():
                if nkey()!=opened: raise ConnectionError("NTRIP-oppsettet er endra – koplar til på nytt")
                now=time.time()
                gga=STATE.get("last_gga","")
                if gga and now-last_gga_sent>=float(CFG["gga_interval"]):
                    stream.send_gga(gga); last_gga_sent=now
                data=stream.read(4096)
                if not data:
                    wait=now-last_data; tmo=max(5.0,float(CFG.get("ntrip_timeout") or 20))
                    update(ntrip_wait=round(wait),rtcm=RTCM.status(STATE.get("lat"),STATE.get("lon"),STATE["bytes_rtcm"]))
                    if wait>tmo: raise ConnectionError(f"Ingen korreksjonar på {wait:.0f} s – koplar til på nytt")
                    continue
                last_data=now
                so=serial_obj   # lokal referanse: serial_loop kan setje serial_obj til None når som helst
                if so is not None and getattr(so,"is_open",False):
                    # Feil ved skriving til mottakaren er ein MOTTAKARFEIL: NTRIP-sambandet skal halde fram.
                    # (write_timeout=1 hindrar at eit dødt Bluetooth-samband held tråden fast.)
                    try: so.write(data)
                    except Exception as e:
                        if now-last_wfail>=10:
                            last_wfail=now; update(last_error=f"Serial: klarte ikkje å sende korreksjonar til mottakaren ({e})")
                            LOG.event(f"Mottakar-feil ved sending av RTCM: {e}",err=True)
                RTCM.feed(data)   # berre kontroll – dataa blir sende uendra til mottakaren
                if now-last_rtcm_log>=60 and RTCM.frames:
                    st=RTCM.status(STATE.get("lat"),STATE.get("lon"),STATE["bytes_rtcm"]); last_rtcm_log=now
                    LOG.event(f"RTCM: {st['frames']} rammer, {st['crcErr']} CRC-feil, typar {','.join(st['types'])}, base {st['station']} {st.get('baseKm','?')} km – {st['verdict']}")
                update(bytes_rtcm=STATE["bytes_rtcm"]+len(data),ntrip_wait=0,rtcm=RTCM.status(STATE.get("lat"),STATE.get("lon"),STATE["bytes_rtcm"]+len(data)))
        except Exception as e:
            update(ntrip_connected=False,last_error=f"NTRIP: {e}")
            LOG.event(f"NTRIP-feil: {e}{'' if isinstance(e,(OSError,NK.NtripError)) else where(e)}",err=True)
            if stream: stream.close()
            ntrip_sock=None
            time.sleep(10 if isinstance(e,NK.NtripError) and e.code in ("auth","mount") else 3)

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
    def origin_ok(self):
        """Endringar (POST) blir berre godtekne frå SNOWMAN sine eigne sider på denne PC-en.
        Utan dette kunne ei anna nettside i nettlesaren på PC-en endre t.d. caster medan passordet står lagra,
        slik at innlogginga vart send til ein annan server. Førespurnader utan Origin (ikkje frå nettlesar) er OK."""
        o=self.headers.get("Origin")
        if not o: return True
        try:
            u=urllib.parse.urlparse(o); port=self.server.server_address[1]
            return u.scheme=="http" and u.hostname in ("127.0.0.1","localhost","::1") and (u.port or 80)==port
        except Exception: return False
    def do_GET(self):
        u=urllib.parse.urlparse(self.path)
        if u.path=="/api/status":
            st=dict(STATE); gt=st.get("gga_time"); st["gga_age"]=None if not gt else round(time.time()-gt,1)
            self.headers_ok(); self.wfile.write(json.dumps(st).encode()); return
        if u.path=="/":
            p=Path(__file__).with_name("driver.html")
            self.headers_ok(200,"text/html; charset=utf-8"); self.wfile.write(p.read_bytes()); return
        if u.path=="/api/terrain":
            self.headers_ok(); self.wfile.write(json.dumps({"available":T.AVAILABLE,"error":T.IMPORT_ERROR,
                "types":T.TYPES,"layers":TERR.listing() if T.AVAILABLE else [],
                "calibration":{k:CFG[k] for k in ("antZ","zOff","heightMode","geoidN","calibrated","tiltMode","tiltFlipPitch","tiltFlipRoll")},
                "tiltSentences":sorted(HEL.sentences)}).encode()); return
        if u.path=="/api/log":
            r=LOG.status(); r.update(ok=True,logs=LOG.listing(),always=bool(O.system_cfg().get("logAlways")))
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/log/events":   # hendingar og feil i ein logg (Innst. › System › Feltlogg › Hendingar)
            try: r={"ok":True,"events":LOG.events_of(urllib.parse.parse_qs(u.query)["name"][0])}
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/log/download-day":   # alle loggane frå éin dag i éi zip
            try:
                day=urllib.parse.parse_qs(u.query)["day"][0]; data=LOG.zip_day(day)
                self.send_response(200); self.send_header("Content-Type","application/zip")
                self.send_header("Content-Disposition",f'attachment; filename="snowman-loggar-{day}.zip"'); self.end_headers(); self.wfile.write(data)
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if u.path=="/api/log/download":   # zip med begge filene i ein logg
            try:
                name=urllib.parse.parse_qs(u.query)["name"][0]; data=LOG.zip(name)
                self.send_response(200); self.send_header("Content-Type","application/zip")
                self.send_header("Content-Disposition",f'attachment; filename="{name}.zip"'); self.end_headers(); self.wfile.write(data)
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if u.path=="/api/window":   # kiosk/vanleg: styrt av oppstartsprogrammet om det køyrer
            try: st=json.loads((DATA/"launcher.json").read_text())
            except Exception: st={}
            self.headers_ok(); self.wfile.write(json.dumps({"launcher":bool(st.get("browser")),"mode":st.get("mode","window"),"system":system_cfg()}).encode()); return
        if u.path=="/api/config":   # NTRIP/GNSS-oppsettet: noverande verdiar til skjemaet (passordet blir aldri sendt)
            c={k:CFG[k] for k in ("serial_port","baud","caster","caster_port","mountpoint","username","initCmds","ntrip_version","ntrip_timeout")}
            c["password"]="***" if CFG.get("password") else ""
            self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"config":c,"simulert":REAL_PORT[0] is not None}).encode()); return
        if u.path=="/api/ntrip/sourcetable":   # lista over mountpoints på casteren (HENT MOUNTPOINTS på NTRIP-sida)
            q=urllib.parse.parse_qs(u.query)
            caster=(q.get("caster",[""])[0] or CFG["caster"]).strip(); port=q.get("port",[""])[0] or CFG["caster_port"]
            same=caster==CFG["caster"]   # brukarnamn/passord blir berre sende til casteren dei er lagra for
            try:
                if not caster: raise ValueError("Skriv inn caster først")
                r=NK.fetch_sourcetable(caster,int(port),CFG["username"] if same else "",CFG["password"] if same else "",VERSION,STATE.get("lat"),STATE.get("lon"))
                r["ok"]=True
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/ports":   # seriellportar på PC-en (USB, Bluetooth …) med skildring
            try:
                from serial.tools import list_ports
                r=[{"port":p.device,"desc":p.description or "","hwid":p.hwid or ""} for p in sorted(list_ports.comports(),key=lambda p:p.device)]
            except Exception: r=[]
            self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"ports":r}).encode()); return
        if u.path=="/api/ui-config":
            try: d=json.loads(UI_CFG.read_text("utf-8"))
            except Exception: d={}
            self.headers_ok(); self.wfile.write(json.dumps(d).encode()); return
        if u.path=="/api/control":
            r=KON.listing(CFG,STATE); r.update(ok=True,simTruth=sim_truth(),fix=STATE.get("fix"),depth=STATE.get("depth"),
                raw=(STATE.get("depth_detail") or {}).get("raw"),depth_status=STATE.get("depth_status"),zOff=CFG["zOff"],calibrated=CFG["calibrated"])
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path in ("/api/fuel","/api/report","/api/report/days"):
            try:
                if FUEL is None: raise RuntimeError("Drivstoff og rapport krev numpy: "+TRA_ERR)
                q=urllib.parse.parse_qs(u.query); date=q.get("date",[None])[0]
                if u.path=="/api/fuel": r={"ok":True,"fuel":FUEL.computed(),"summary":FUEL.summary()}
                elif u.path=="/api/report/days": r={"ok":True,"days":FUEL.days()}
                else: r=FUEL.report(date); r["ok"]=True
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/report/export":
            r={"ok":True,**report_cfg(),**EXPORT}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/report/csv":   # rapporten som CSV (Excel)
            try:
                date=urllib.parse.parse_qs(u.query).get("date",[None])[0]
                data=FUEL.report_csv(date).encode("utf-8"); name="snowman-rapport-"+(date or time.strftime("%Y-%m-%d"))+".csv"
                self.send_response(200); self.send_header("Content-Type","text/csv; charset=utf-8")
                self.send_header("Content-Disposition",f'attachment; filename="{name}"'); self.end_headers(); self.wfile.write(data)
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if u.path=="/api/objekt":
            r={"ok":True,"objekt":OBJ.listing(),"types":{k:{"name":v[0],"radius":v[1],"sym":v[2]} for k,v in TR.OBJ_TYPES.items()}} if OBJ else {"ok":False,"error":TRA_ERR}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/history/coverage":   # trakka område i ein periode eller for éi økt (Historikk › TRAKKA OMRÅDE)
            q=urllib.parse.parse_qs(u.query); per=q.get("period",["day"])[0]; now=time.time()
            try:
                if TRA is None: raise RuntimeError("Trakka område krev numpy: "+TRA_ERR)
                ids=None; since=0
                if per=="session": ids={q.get("id",[""])[0]}
                elif per=="day": since=TR.prep_day_start()
                elif per=="all": since=0
                else: since=now-{"24h":1,"3d":3,"7d":7,"30d":30}.get(per,1)*86400
                r=TRA.coverage(since,None,ids,q.get("test",["0"])[0]=="1"); r["ok"]=True
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path in ("/api/trasear","/api/trasear/status"):
            try:
                if TRA is None: raise RuntimeError("Trasear krev numpy: "+TRA_ERR)
                if u.path=="/api/trasear": r={"ok":True,"trasear":TRA.listing(),"levels":TR.LEVELS,"kinds":TR.KINDS,"dayStartHour":TR.DAY_START_HOUR}
                else:
                    q=urllib.parse.parse_qs(u.query)
                    since=TR.prep_day_start(date=q["date"][0]) if q.get("date") else (float(q["since"][0])/1000 if q.get("since") else None)
                    until=since+86400 if q.get("date") else None
                    r=TRA.status(since,until,with_map=q.get("map",["0"])[0]=="1"); r["ok"]=True
            except Exception as e: r={"ok":False,"error":str(e)}
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
            try: self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)   # send kvar melding med éin gong (ingen Nagle-venting)
            except OSError: pass
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
        if not self.origin_ok():
            LOG.event(f"Avvist endring frå framand nettside: {self.headers.get('Origin')} {self.path}",err=True)
            self.headers_ok(403); self.wfile.write(json.dumps({"ok":False,"error":"Endringar er berre tillatne frå SNOWMAN sjølv"}).encode()); return
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
                d=json.loads(body or b"{}"); before=dict(CFG)
                for k in CFG:
                    if k in d and not (k=="password" and d[k] in ("***",)): CFG[k]=d[k]
                log_changes("NTRIP/mottakar",before,CFG,("serial_port","baud","caster","caster_port","mountpoint","username","password",
                            "ntrip_version","ntrip_timeout","gga_interval","initCmds"))
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
                if d.get("final"): threading.Thread(target=export_now,daemon=True).start()   # prep stoppa: lagre rapporten no
                self.headers_ok(); self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/report/export":   # innstillingar for automatisk lagring, og «lagre no»
            try:
                d=json.loads(body or b"{}")
                if "on" in d: O.save_system(reportExport=bool(d["on"]))
                if d.get("dir") is not None:
                    p=str(d["dir"]).strip()
                    if p:
                        Path(p).expanduser().mkdir(parents=True,exist_ok=True)
                        p=str(Path(p).expanduser())
                    O.save_system(reportDir=p)
                if d.get("now") or "dir" in d or d.get("on"): export_now()
                r={"ok":True,**report_cfg(),**EXPORT}
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":"Kunne ikkje bruke mappa: "+str(e)}).encode())
            return
        if self.path in ("/api/objekt/save","/api/objekt/delete"):
            try:
                if OBJ is None: raise RuntimeError("Hindringar krev numpy: "+TRA_ERR)
                d=json.loads(body or b"{}")
                r={"ok":True,"objekt":OBJ.save(d)} if self.path.endswith("save") else (OBJ.delete(d["id"]) or {"ok":True})
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path in ("/api/fuel/add","/api/fuel/delete"):
            try:
                if FUEL is None: raise RuntimeError("Drivstoff krev numpy: "+TRA_ERR)
                d=json.loads(body or b"{}")
                if self.path=="/api/fuel/add":
                    r={"ok":True,"fill":FUEL.add(d)}; LOG.event(f"Førar: drivstoff registrert – {d.get('litres')} l, timeteljar {d.get('hours') or '-'}")
                else: FUEL.delete(d["id"]); r={"ok":True}
                r.update(fuel=FUEL.computed(),summary=FUEL.summary())
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path.startswith("/api/trasear/"):
            try:
                if TRA is None: raise RuntimeError("Trasear krev numpy: "+TRA_ERR)
                d=json.loads(body or b"{}"); a=self.path[13:]
                if a=="save": r={"ok":True,"trase":TRA.save(d)}
                elif a=="delete": TRA.delete(d["id"]); r={"ok":True}
                elif a=="from-terrain":   # yttergrensa til eit terrenglag – blir ikkje lagra før føraren har sett på ho
                    if not T.AVAILABLE: raise RuntimeError(T.IMPORT_ERROR)
                    m=TERR.layers.get(d.get("layer"))
                    if not m: raise ValueError("Fann ikkje terrenglaget.")
                    poly=TR.outline_from_layer(TERR._grid(m["id"]),m,T.utm_inverse,float(d.get("tol",2.0)))
                    r={"ok":True,"poly":poly,"area":round(TR.poly_area_m2(poly)),"name":m["name"]}
                else: raise ValueError("Ukjend trasé-handling")
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path.startswith("/api/control/"):
            try:
                d=json.loads(body or b"{}"); a=self.path[13:]
                if a=="check":
                    c=KON.add_check(STATE,CFG,d.get("known"),d.get("note",""),sim_truth()); r={"ok":True,"check":c}
                    LOG.event(f"Førar: kontrollmåling – kjend {c.get('known')} m, SNOWMAN rå {c.get('raw')} m, avvik "
                              f"{None if c.get('raw') is None else round(c['raw']-float(c['known']),3)} m ({c.get('layerName') or '-'})")
                elif a=="check/delete": KON.delete_check(d["id"]); r={"ok":True}
                elif a=="point": r={"ok":True,"point":KON.add_point(d.get("name"),d.get("E"),d.get("N"),d.get("zone",32),d.get("h"))}
                elif a=="point/delete": KON.delete_point(d["id"]); r={"ok":True}
                elif a=="apply-offset":
                    z,m=KON.apply_offset(CFG); save_cfg(); r={"ok":True,"zOff":z,"change":m}
                    LOG.event(f"Førar: høgdekorreksjon justert til {z} m (endring {m} m) frå kontrollmålingar")
                else: raise ValueError("Ukjend kontroll-handling")
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/terrain/crop":   # utsnitt av ei stor fil (Kartverket DTM1 o.l.)
            try:
                if not T.AVAILABLE: raise RuntimeError(T.IMPORT_ERROR)
                d=json.loads(body or b"{}")
                r=TERR.crop(d.get("bigToken"),d["lat"],d["lon"],d.get("half",2000))
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"errors":[str(e)],"warnings":[],"info":{}}).encode())
            return
        if self.path in ("/api/terrain/import","/api/terrain/update","/api/terrain/delete","/api/calibration"):
            try:
                d=json.loads(body or b"{}")
                if self.path=="/api/calibration":
                    before=dict(CFG); ks=("antZ","zOff","heightMode","geoidN","calibrated","tiltMode","tiltFlipPitch","tiltFlipRoll")
                    for k in ks:
                        if k in d: CFG[k]=d[k]
                    log_changes("kalibrering",before,CFG,ks)
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
        if self.path=="/api/log/client":   # frå førarskjermen: JavaScript-feil, handlingar og skjerm/3D-info
            try:
                d=json.loads(body or b"{}"); kind=d.get("kind"); txt=str(d.get("text",""))[:600]
                if kind=="error":
                    n=LOGRATE.get("js_n",0) if time.time()-LOGRATE.get("js_t",0)<60 else 0
                    if n==0: LOGRATE["js_t"]=time.time()
                    LOGRATE["js_n"]=n+1
                    if n<20: LOG.event("Førarskjerm-feil: "+txt,err=True)   # maks 20 per minutt
                elif kind=="action": LOG.event("Førar: "+txt)
                elif kind=="info":
                    if txt!=STATE.get("client_info"):
                        update(client_info=txt)
                        if LOG.active(): LOG.event("Skjerm/3D: "+txt)
                self.headers_ok(); self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/log":
            try:
                d=json.loads(body or b"{}"); a=d.get("action")
                if a=="start": start_log(f"SNOWMAN v{VERSION}, port {CFG['serial_port'] or '-'}, antZ {CFG['antZ']}, zOff {CFG['zOff']}, høgd {CFG['heightMode']}")
                elif a=="stop": LOG.stop()
                elif a=="delete": LOG.delete_all()
                if "always" in d: O.save_system(logAlways=bool(d["always"]))
                r=LOG.status(); r.update(ok=True,logs=LOG.listing(),always=bool(O.system_cfg().get("logAlways")))
                self.headers_ok(); self.wfile.write(json.dumps(r).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/window":   # «Vanleg skjerm» / «Kioskmodus»: oppstartsprogrammet byter vindauge
            try:
                m=json.loads(body or b"{}").get("mode")
                if m not in ("kiosk","window"): raise ValueError("Ukjend modus")
                if not (DATA/"launcher.json").exists(): raise ValueError("SNOWMAN er ikkje starta med oppstartsprogrammet")
                (DATA/"window-request.txt").write_text(m)
                self.headers_ok(); self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/system":   # Innst. › System: kiosk ved oppstart (autostart kjem i steg 3)
            try:
                d=json.loads(body or b"{}"); msg=""
                if "kiosk" in d: O.save_system(kiosk=bool(d["kiosk"]))
                if "autostart" in d:
                    ok,msg=O.autostart_set(bool(d["autostart"]))
                    if not ok: raise ValueError(msg)
                self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"system":system_cfg(),"message":msg}).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/ui-config":
            try:
                d=json.loads(body or b"{}")
                if not isinstance(d,dict) or len(body)>300000: raise ValueError("Ugyldige innstillingar")
                try:
                    old=json.loads(UI_CFG.read_text("utf-8")); oc=old.get("cfg",old); nc=d.get("cfg",d)
                    log_changes("førarskjerm",oc,nc,("mname","machine","blade","bladeN","tiller","tillerN","target","tol","bounds","northUp",
                                "detail3d","estOn","bgOn","viewMode","demoD","antX","antY","antN","ant2X","ant2Y"))
                except Exception: pass
                write_atomic(UI_CFG,json.dumps(d,ensure_ascii=False,indent=1))
                self.headers_ok(); self.wfile.write(b'{"ok":true}')
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/update":   # Innst. › System › Hent siste versjon (same som menyval 5)
            import io, contextlib, start_snowman as SS
            buf=io.StringIO(); old=VERSION
            with contextlib.redirect_stdout(buf): SS.oppdater()
            new=SS.version()
            self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"output":buf.getvalue().strip(),"changed":new!=old,"version":new}).encode()); return
        if self.path=="/api/restart":
            RESTART[0]=True; save_cfg()
            self.headers_ok(); self.wfile.write(b'{"ok":true}')
            threading.Thread(target=lambda:(time.sleep(0.5),SERVER[0] and SERVER[0].shutdown()),daemon=True).start(); return
        if self.path=="/api/shutdown":   # «Avslutt SNOWMAN» frå førarskjermen (berre frå denne PC-en)
            save_cfg()
            self.headers_ok(); self.wfile.write(json.dumps({"ok":True}).encode())
            def stop():
                time.sleep(0.5)
                if SERVER[0]: SERVER[0].shutdown()
            threading.Thread(target=stop,daemon=True).start()
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
                with HUD_TICK: HUD_TICK.notify_all()   # demo/preparering frå førarskjermen: send til HUD med éin gong
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
        if u.path in ("/","/hud","/api/hud","/api/hud/stream","/vendor/snowman-icon.png"):
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

# --- Automatisk lagring av rapportar (Innst. › Rapport). Synkroniseringsprogram lastar opp når PC-en har nett. ---
EXPORT={"last":None,"error":"","files":[],"written":0}
def report_cfg():
    s=O.system_cfg()
    return {"on":s.get("reportExport",True),"dir":s.get("reportDir") or str(DS.default_report_dir())} if FUEL else {"on":False,"dir":""}
def ui_machine():
    try: return json.loads(UI_CFG.read_text("utf-8")).get("mname","")
    except Exception: return ""
def export_now():
    c=report_cfg()
    if not (FUEL and c["on"]): return
    try:
        n,files=DS.export_reports(FUEL,c["dir"],ui_machine())
        EXPORT.update(last=time.strftime("%Y-%m-%d %H:%M"),error="",files=files,written=EXPORT["written"]+n)
    except Exception as e:
        EXPORT.update(last=time.strftime("%Y-%m-%d %H:%M"),error=str(e))
def export_loop():
    time.sleep(20)
    while not STOP.is_set():
        export_now()
        STOP.wait(300)   # kvart 5. minutt (og når prep blir stoppa)

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
    threading.Thread(target=export_loop,daemon=True).start()
    threading.Thread(target=ntrip_loop,daemon=True).start()
    print(f"SNOWMAN PC v{VERSION} køyrer: http://127.0.0.1:{a.http_port}")
    if a.lan or CFG.get("hudLan"): set_hud_lan(True)
    # Hovudtenesta (styring, innstillingar) er berre tilgjengeleg på denne PC-en.
    if O.system_cfg().get("logAlways"): start_log(f"Starta automatisk. SNOWMAN v{VERSION}")
    SERVER[0]=http.server.ThreadingHTTPServer(("127.0.0.1",a.http_port),API)
    try: SERVER[0].serve_forever()
    except KeyboardInterrupt: pass
    finally:
        STOP.set(); save_cfg(); LOG.stop()
        try:
            if serial_obj: serial_obj.close()   # frigjer COM-porten til Leica
        except Exception: pass
        print("SNOWMAN-tenesta er avslutta.")
    if RESTART[0]: sys.exit(3)   # oppstartsprogrammet startar tenesta og vindauget på nytt

if __name__=="__main__": main()
