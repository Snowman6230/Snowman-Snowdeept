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
VERSION="1.6.91"   # versjonen som er i bruk (same som APP_VERSION i driver.html)
import sys
import argparse, base64, json, math, os, re, socket, threading, time, http.server, urllib.parse, urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
DATA=HERE/"data"; SESS=DATA/"sessions"
CFG_FILE=HERE/"snowman-config.local.json"   # lokal, aldri i git (sjå .gitignore)
VENDOR={"leaflet.js":"application/javascript","leaflet.css":"text/css","qrcode.js":"application/javascript","three.snowman.min.js":"application/javascript","snowman-icon.png":"image/png"}
import terrain as T
TERR=T.TerrainLibrary(DATA/"terrain")
import snoflate as SF
SURF=SF.SnowSurface(DATA/"snoflate.json")   # snøflateminne: målt snøoverflate, til estimat framfor maskina
import ver as VER
WX=VER.Weather(DATA/"ver-cache.json",VERSION)   # vêr og snøproduksjon (MET Locationforecast), lagra for bruk utan nett
import frost as FR
try: import snokart as SK; SNOWMAP=SK.SnowMap()
except Exception: SK=SNOWMAP=None   # snøkartet krev numpy (same som terrengmotoren)
SNOWMAP_CACHE={}   # snøkart (estimat) i Vêr – byggjer på den gjeldande terrengmodellen
FROST=FR.Frost(DATA/"frost-cache.json",VERSION)  # målingar frå næraste vêrstasjonar (MET Frost) – «MÅLT NO» i Vêr
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
       "rtk_mode":"snowman",   # kvar RTK blir rekna: "snowman" (RTK-motoren i SNOWMAN – eigaren si avgjerd) eller "mottakar"
       "rtcm_drop":"",  # RTCM-typar som ikkje blir sende til mottakaren, t.d. «1008,1033» (antennenamn mottakaren ikkje godtek)
       "initCmds":"",   # oppstartskommandoar til mottakaren (éin per linje), sende når seriellporten blir opna
       "hudLan":False,
       "frost_client_id":"",   # tomt = SNOWMAN sin innebygde Frost-ID (berre opne data); eit anlegg kan setje sin eigen
       "frost_stations":""}    # tomt = næraste stasjonar etter GPS; elles t.d. "SN60190,SN60225"
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
                   depth=d,depthNote=ter.get("name","") if d is not None else DEPTH_TXT.get(STATE.get("depth_status"),"IKKJE MÅLT"),
                   change=STATE.get("surf_change") if d is not None else None,
                   last=STATE.get("surf_last") if d is None else None)
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

SURFX={"chg":[],"last_t":0}
def surf_upd(dstat,det,lat,lon,ter):
    """Snøflateminnet: lagre overflata ved gyldig snødjupne, og rekn ut til HUD-en
    – endring i overflata sidan førre preparering (median av dei siste målingane), og
    – «sist målt her» frå minnet når den direkte målinga manglar (høgst 1 gong i sekundet)."""
    test=bool(STATE.get("simulated")); now=time.time()
    if dstat=="OK" and det.get("surface") is not None:
        c=SURF.add(lat,lon,det["surface"],TERR.height,test=test); SURF.save()
        L=SURFX["chg"]; L.append((now,c)); del L[:-15]
        v=[x[1] for x in L if x[1] is not None and now-x[0]<5]
        if len(v)>=5:
            dz=sorted(a for a,_ in v)[len(v)//2]; ag=sorted(b for _,b in v)[len(v)//2]
            STATE["surf_change"]={"dz":round(dz,2),"ageH":round(ag/3600,1)}
        else: STATE["surf_change"]=None
        STATE["surf_last"]=None
    else:
        STATE["surf_change"]=None
        if ter is not None and now-SURFX["last_t"]>1:
            SURFX["last_t"]=now
            try: STATE["surf_last"]=SURF.at(lat,lon,TERR.height,test=test)
            except Exception: STATE["surf_last"]=None
        elif ter is None: STATE["surf_last"]=None

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
        surf_upd(dstat,det,mlat,mlon,ter)
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

def serial_explain(e,port):
    """Kort forklaring på norsk av kvifor mottakarporten ikkje opnar (vist under «Feil» og i Innst. › GNSS)."""
    low=str(e).lower(); port=port or "porten"
    bt=False
    try:
        from serial.tools import list_ports
        bt=any(p.device.upper()==str(port).upper() and "bluetooth" in (p.description or "").lower() for p in list_ports.comports())
    except Exception: pass
    if "socket://" in low or str(port).startswith("socket://"):
        return "Får ikkje kontakt med mottakaren over nettverket. Sjekk adresse og port."
    if "permission" in low or "access is denied" in low or "tilgang" in low or "errno 13" in low:
        return (f"{port} er oppteken av eit anna program – t.d. eit anna GNSS-program, ein nettlesarfane med "
                "seriell-/Bluetooth-tilkopling eller ein SNOWMAN som alt køyrer. Lukk det, så koplar SNOWMAN til av seg sjølv.")
    if "121" in low or "semaphore" in low or "semafor" in low or "timeout" in low or "tidsavbrot" in low:
        return "Tidsavbrot: mottakaren svarar ikkje på Bluetooth (av, for langt unna eller kopla til ei anna eining)."
    if "filenotfound" in low or "errno 2" in low or "finner ikke" in low or "cannot find" in low or "no such file" in low:
        if bt or str(port).upper().startswith("COM"):
            return (f"Windows får ikkje opna {port}. Med Bluetooth tyder det nesten alltid at PC-en ikkje får samband med mottakaren: "
                    "1) Sjå at mottakaren er på og nær PC-en. 2) Kople frå alt anna som brukar mottakaren over Bluetooth "
                    "(telefon, kontrollar, andre program) – han tek berre éi tilkopling om gongen. 3) Hjelper ikkje det: "
                    "fjern mottakaren i Windows › Bluetooth, par han på nytt og bruk den nye UTGÅANDE porten. "
                    "Med kabel: sjekk at USB-kabelen sit i og at portnamnet er rett. SNOWMAN prøver igjen av seg sjølv.")
        return f"Porten {port} finst ikkje. Sjekk kabel og portnamn."
    return ""

# ---------- RTK i SNOWMAN (v1.6.91): RTKLIB-motor, rådata frå mottakaren + basen frå NTRIP ----------
import rtkmotor as RM
MOTOR=[None]   # RtkMotor når rtk_mode = "snowman" og motoren er klar
def rtk_snowman(): return str(CFG.get("rtk_mode") or "snowman")=="snowman"
def motor_solution(gga,info):
    """Løysing frå RTK-motoren → same veg som GGA frå mottakaren (snødjupne, kart, logg)."""
    update(rtk_src="snowman",rtk_ratio=round(info.get("ratio",0),1))
    parse_gga(gga)
def motor_start():
    """Start RTK-motoren i bakgrunnen (installerer pyrtklib første gong). Kallast ved oppstart og når valet blir slått på."""
    if MOTOR[0] is not None or not rtk_snowman(): return
    def run():
        m=RM.RtkMotor(on_solution=motor_solution,log=LOG.event)
        update(rtk_motor="startar")
        # Avspeling av opptak / test: SNOWMAN_RTK_REFTIME="2005-04-02" (veke for RTCM-tid), SNOWMAN_RTK_NAVFILE=banefil (RINEX)
        rt=os.environ.get("SNOWMAN_RTK_REFTIME"); ref=tuple(int(x) for x in rt.split("-")) if rt else None
        if m.start(install=True,ref_time=ref):
            nf=os.environ.get("SNOWMAN_RTK_NAVFILE")
            if nf: update(rtk_nav=f"fil {Path(nf).name}: {m.load_nav(nf)} baner")
            MOTOR[0]=m; update(rtk_motor="klar"); LOG.event("RTK-motor i SNOWMAN klar (RTKLIB)")
            threading.Thread(target=motor_nav_loop,daemon=True).start()
        else:
            update(rtk_motor="feil: "+RM.LIB_ERR[:200]); LOG.event("RTK-motor: "+RM.LIB_ERR,err=True)
    threading.Thread(target=run,daemon=True).start()
def motor_nav_loop():
    """Satellittbaner når verken mottakar eller base sender dei: prøv BRDC-fila frå BKG (IGS) kvar time."""
    while not STOP.is_set() and MOTOR[0] is not None:
        m=MOTOR[0]
        if m.stats.get("eph",0)<4:
            try:
                path=RM.fetch_brdc(DATA/"brdc",ua=WX.ua)
                if path:
                    n=m.load_nav(str(path)); update(rtk_nav=f"BRDC-fil {path.name}: {n} baner")
            except Exception as e: update(rtk_nav=f"BRDC-fil: {e}")
        STOP.wait(3600)

SERIAL_REOPEN=threading.Event()   # «LAGRE / KOPLE TIL» eller døyande samband: lukk porten og opne han på nytt
SERIAL_IDLE=15.0                   # s utan data frå mottakaren før porten blir opna på nytt (mottakarar sender minst 1 Hz)

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
            SERIAL_REOPEN.clear(); last_rx=time.time()
            while not STOP.is_set() and serial_obj.is_open:
                if (CFG["serial_port"],int(CFG["baud"]),CFG.get("initCmds"))!=opened:   # endra i oppsettet: opne på nytt
                    LOG.event("Mottakaroppsett endra – opnar porten på nytt"); serial_obj.close()
                    update(serial_connected=False); serial_obj=None; break
                if SERIAL_REOPEN.is_set():   # LAGRE / KOPLE TIL, eller NTRIP får ikkje skrive til porten
                    SERIAL_REOPEN.clear(); LOG.event("Opnar mottakarporten på nytt (kople til på nytt)")
                    serial_obj.close(); update(serial_connected=False); serial_obj=None; break
                # Vakthund (v1.6.86): når mottakaren startar på nytt eller går utanfor rekkjevidd, døyr Bluetooth-sambandet
                # utan at Windows lukkar porten – då kjem det aldri meir data. Opne porten på nytt etter SERIAL_IDLE s stille.
                if time.time()-last_rx>SERIAL_IDLE:
                    LOG.event(f"Ingen data frå mottakaren på {SERIAL_IDLE:.0f} s – opnar porten på nytt",err=True)
                    update(serial_reopens=STATE.get("serial_reopens",0)+1,serial_reopen_time=time.time())
                    update(serial_connected=False,last_error=f"Serial: ingen data frå mottakaren på {SERIAL_IDLE:.0f} s – koplar til på nytt "
                           "(mottakaren av, starta på nytt eller utanfor rekkjevidd?)")
                    try: serial_obj.close()
                    except Exception: pass
                    serial_obj=None; time.sleep(1); break
                b=serial_obj.read(4096)
                if b: last_rx=time.time()
                ga=time.time()-(STATE.get("gga_time") or time.time())
                if ga>5 and not gnss_lost:
                    gnss_lost=True; LOG.event(f"Mottakaren har slutta å sende posisjon (ingen GGA på {ga:.0f} s)",err=True)
                elif gnss_lost and ga<1:
                    gnss_lost=False; LOG.event("Posisjon frå mottakaren er tilbake")
                if b and rtk_snowman() and MOTOR[0] is not None:
                    b=MOTOR[0].rover_bytes(b)   # RTCM-rådata til RTK-motoren; teksten (NMEA) går vidare som før
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
                        if line.startswith("$") and "GGA" in line:
                            STATE["rx_gga"]=line   # GGA frå mottakaren, uredigert – blir send slik til casteren (NTRIP)
                            m=MOTOR[0] if rtk_snowman() else None
                            if m is not None:
                                try: m.hdop=float(line.split(",")[8] or 0) or None
                                except Exception: pass
                            # I SNOWMAN-modus er posisjonen frå RTK-motoren; GGA frå mottakaren blir berre brukt når motoren
                            # ikkje har hatt løysing på 3 s (kart og status held fram, men utan RTK frå mottakaren).
                            if m is None or not m.stats.get("last_sol") or time.time()-m.stats["last_sol"]>3:
                                update(rtk_src="mottakar"); parse_gga(line)
                        elif line.startswith("$"): HEL.feed(line)   # hellingsmålar i antenna, om ho har
                        elif line and line.isprintable(): update(rx_text=line[:120],rx_time=time.time())   # svar på kommandoar o.l. (t.d. «<OK»)
                else: time.sleep(.02)
            update(serial_connected=False)   # løkka slutta (port lukka/endra) – aldri «TILKOPLA» utan open port
        except Exception as e:
            why=serial_explain(e,CFG.get("serial_port"))
            update(serial_connected=False,last_error=f"Serial: {e}"+(f" – {why}" if why else ""))
            # same feil kvart 2. sekund skal ikkje fylle feltloggen: skriv han når han endrar seg, elles kvart 5. min
            msg=str(e)
            if msg!=LOGRATE.get("serr_msg") or time.time()-LOGRATE.get("serr",0)>300:
                LOGRATE["serr_msg"]=msg; LOGRATE["serr"]=time.time()
                LOG.event(f"Mottakar-feil: {e}{'' if isinstance(e,OSError) else where(e)}"+(f" – {why}" if why else ""),err=True)
            try:
                if serial_obj: serial_obj.close()
            except: pass
            serial_obj=None; time.sleep(2)

def rtk_hint(st):
    """Kvifor manglar RTK FIX? Kort vurdering på norsk frå heile kjeda: caster → SNOWMAN → mottakar → løysing.
    Byggjer på GGA-kvaliteten og korreksjonsfelta i GGA (alder, base-ID) og byte sende til mottakaren."""
    fix=st.get("fix") or ""
    if fix=="RTK FIX" or fix=="SIMULERT": return ""
    if rtk_snowman():   # RTK blir rekna i SNOWMAN – sjå 🔍 FEILSØK RTK for alle stega
        m=st.get("motor") or {}
        if not m: return "RTK i SNOWMAN: motoren startar ("+str(st.get("rtk_motor") or "…")+")."
        if not m.get("rover_obs"): return ("RTK i SNOWMAN: mottakaren sender ikkje rådata (RTCM 3 MSM eller 1004/1012) – berre GGA. "
                                           "Slå på rådata-utgang på mottakaren, på same port som SNOWMAN les.")
        if not m.get("base_obs"): return "RTK i SNOWMAN: ingen basedata frå NTRIP endå."
        if m.get("eph",0)<4 and not m.get("eph_file"): return ("RTK i SNOWMAN: manglar satellittbaner. Slå på baner (RTCM 1019/1020/1042/1046) "
                                                               "i rådata frå mottakaren, eller bruk eit mountpoint som sender dei.")
        return f"RTK i SNOWMAN: motoren reknar ({m.get('last_name')}, ratio {m.get('last_ratio')}). Vent med fri sikt."
    if not st.get("serial_connected"): return "Mottakaren er ikkje tilkopla – sjå «Feil»."
    if not st.get("ntrip_connected"): return "Ingen korreksjonar: NTRIP er ikkje tilkopla (Innst. › Kart, GNSS). Utan korreksjonar blir det aldri RTK FIX."
    r=st.get("rtcm") or {}
    if not str(r.get("verdict","")).startswith("OK"): return "Korreksjonane frå casteren er ikkje i orden: "+str(r.get("verdict") or "ventar")
    out=st.get("bytes_rtcm_out",0); ot=st.get("rtcm_out_time")
    if not out or (ot and time.time()-ot>10):
        return "Korreksjonane kjem frå casteren, men blir ikkje sende vidare til mottakaren – sjekk at mottakarporten er open."
    km=r.get("baseKm"); kmt=f" Basen er {km} km unna." if km is not None else ""
    rx=str(st.get("rx_text") or ""); rxt=st.get("rx_time") or 0
    if re.search(r"^@\w+,.*,ERROR",rx) and time.time()-rxt<60:
        return ("Mottakaren svarar «"+rx[:60]+"»: han tolkar korreksjonane som kommandoar, så porten SNOWMAN brukar er "
                "kommandoporten hans, ikkje korreksjonsinngangen. La mottakaren hente korreksjonane sjølv (RTK Data Source = "
                "GSM/GPRS med SIM og NTRIP i mottakaren) eller bruk kabel (External). Sjå 🔍 FEILSØK RTK.")
    if fix=="MANUELL":
        # GGA-kvalitet 7: mottakaren melder ein fast/innlagd posisjon – ikkje ei måling. Typisk Working Mode = Base/Static,
        # eller eit augneblinksbilete medan mottakaren startar opp eller byter modus.
        return ("Mottakaren melder MANUELL posisjon (GGA-kvalitet 7) – ein fast eller innlagd posisjon, ikkje ei måling. "
                "Sjekk på nettsida til mottakaren (Zenith: 192.168.10.1 › Settings) at Working Mode = RTK Rover "
                "(ikkje RTK Base eller Static), og at RTK Data Source er den vegen korreksjonane kjem: Bluetooth når SNOWMAN "
                "sender dei, eller GSM/GPRS når mottakaren hentar dei sjølv med eige SIM-kort og NTRIP-oppsett. "
                "Har mottakaren nett starta på nytt, vent eitt minutt.")
    try: bid=int(str(st.get("base_id") or "").strip())
    except ValueError: bid=None
    if fix!="RTK FLOAT" and bid is not None and 120<=bid<=158:
        # Base-ID 120–158 = SBAS-satellitt (EGNOS o.l.): mottakaren les ikkje korreksjonane i det heile. Hadde han lese
        # dei, ville han brukt basen (DGPS/FLOAT) sjølv med dårleg sikt – så dette er innstillingar, ikkje sikt.
        return (f"Mottakaren les ikkje korreksjonane frå SNOWMAN ({out//1024} kB sendt): han brukar SBAS-satellitt {bid} "
                f"i staden for basen.{kmt} Feilen ligg i korreksjonsinngangen på mottakaren, ikkje i sikta eller i SNOWMAN. "
                "Sjekk på nettsida til mottakaren (Zenith: 192.168.10.1 › Status Info) om «Datalink Status» er Disconnected. "
                "GeoMax Zenith35 Pro tok i felttest ikkje imot korreksjonar frå PC over Bluetooth: bruk RTK Data Source = "
                "GSM/GPRS (SIM og NTRIP i mottakaren) eller External (kabel). SNOWMAN les då berre posisjonen.")
    if fix=="RTK FLOAT":
        return ("Mottakaren brukar korreksjonane (RTK FLOAT) og reknar seg fram mot FIX – vent 1–3 min med fri sikt."+kmt+
                " Står han lenge i FLOAT: antenna treng fri sikt mot himmelen (ikkje inne i bil/under tak, unngå bygningar og tre).")
    return (f"Mottakaren får korreksjonar frå SNOWMAN ({out//1024} kB sendt), men brukar dei ikkje – han står i {fix or 'ukjend'}."+kmt+
            " Sjekk: 1) Antenna ute med fri sikt mot himmelen – inne i bil eller under tak blir det sjeldan RTK. "
            "2) På nettsida til mottakaren (Zenith: 192.168.10.1 › Settings): Working Mode = RTK Rover og RTK Data Source = "
            "same veg som SNOWMAN er kopla (Bluetooth), trykk Save Settings og start mottakaren på nytt. "
            "3) Status Info på same nettside viser om mottakaren sjølv ser korreksjonane (korreksjonsalder).")

def ntrip_loop():
    """Hentar korreksjonar frå casteren og sender dei uendra vidare til mottakaren.
    Vakthund (v1.6.41): kjem det ingen data på CFG["ntrip_timeout"] sekund, blir sambandet kopla opp på nytt
    (mobilnettet kan «henge» utan at sambandet blir lukka – då ville SNOWMAN elles vente i det uendelege)."""
    global ntrip_sock
    last_rtcm_log=0; last_wfail=0; wfails=0
    while not STOP.is_set():
        stream=None
        try:
            if not (CFG["caster"] and CFG["mountpoint"]):
                time.sleep(1); continue
            gga=STATE.get("rx_gga") or STATE.get("last_gga") or None   # uredigert GGA frå mottakaren
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
                gga=STATE.get("rx_gga") or STATE.get("last_gga","")   # uredigert GGA frå mottakaren til casteren
                if gga and now-last_gga_sent>=float(CFG["gga_interval"]):
                    stream.send_gga(gga); last_gga_sent=now
                data=stream.read(4096)
                if not data:
                    wait=now-last_data; tmo=max(5.0,float(CFG.get("ntrip_timeout") or 20))
                    update(ntrip_wait=round(wait),rtcm=RTCM.status(STATE.get("lat"),STATE.get("lon"),STATE["bytes_rtcm"]))
                    if wait>tmo: raise ConnectionError(f"Ingen korreksjonar på {wait:.0f} s – koplar til på nytt")
                    continue
                last_data=now
                drop={int(x) for x in re.findall(r"\d{4}",str(CFG.get("rtcm_drop") or ""))}
                clean=RTCM.feed(data,drop)   # berre heile RTCM-rammer med rett CRC går vidare – aldri tekst frå casteren
                so=serial_obj   # lokal referanse: serial_loop kan setje serial_obj til None når som helst
                if clean and rtk_snowman():   # RTK i SNOWMAN: basen går til motoren – ingenting blir sendt til mottakaren
                    if MOTOR[0] is not None: MOTOR[0].base_feed(clean)
                elif clean and so is not None and getattr(so,"is_open",False):
                    # Feil ved skriving til mottakaren er ein MOTTAKARFEIL: NTRIP-sambandet skal halde fram.
                    # (write_timeout=1 hindrar at eit dødt Bluetooth-samband held tråden fast.)
                    try:
                        so.write(clean); update(bytes_rtcm_out=STATE.get("bytes_rtcm_out",0)+len(clean),rtcm_out_time=now); wfails=0
                    except Exception as e:
                        wfails+=1
                        if wfails>=3: SERIAL_REOPEN.set(); wfails=0   # porten tek ikkje imot: sambandet er dødt – opne på nytt
                        if now-last_wfail>=10:
                            last_wfail=now; update(last_error=f"Serial: klarte ikkje å sende korreksjonar til mottakaren ({e})")
                            LOG.event(f"Mottakar-feil ved sending av RTCM: {e}",err=True)
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
            st["rtk_mode"]=CFG.get("rtk_mode") or "snowman"
            if MOTOR[0] is not None: st["motor"]=MOTOR[0].status()
            try: st["rtk_hint"]=rtk_hint(st)
            except Exception: st["rtk_hint"]=""
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
            c={k:CFG.get(k,"") for k in ("serial_port","baud","caster","caster_port","mountpoint","username","initCmds","rtcm_drop","rtk_mode","ntrip_version","ntrip_timeout")}
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
                else: r=FUEL.report(date,maps=q.get("maps",["0"])[0]=="1"); r["ok"]=True
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/report/export":
            r={"ok":True,**report_cfg(),**EXPORT}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/report/pdf":   # rapporten som PDF: samandrag, kart, trasear, økter og drivstoff
            try:
                import pdfrapport as PR
                date=urllib.parse.parse_qs(u.query).get("date",[None])[0]
                try: uc=(lambda d:d.get("cfg",d))(json.loads(UI_CFG.read_text("utf-8")))
                except Exception: uc={}
                rep=FUEL.report(date,maps=True); data=PR.build(rep,uc.get("mname",""),uc.get("bounds")); name="snowman-rapport-"+rep["date"]+".pdf"
                self.send_response(200); self.send_header("Content-Type","application/pdf")
                self.send_header("Content-Disposition",f'attachment; filename="{name}"'); self.end_headers(); self.wfile.write(data)
            except Exception as e:
                self.headers_ok(500); self.wfile.write(json.dumps({"ok":False,"error":f"PDF: {e}{where(e)}"}).encode())
            return
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
        if u.path in ("/api/surface/ahead","/api/surface/status"):   # estimat framfor maskina frå tidlegare snøoverflate
            q=urllib.parse.parse_qs(u.query); test=bool(STATE.get("simulated"))
            try:
                if u.path.endswith("status"): r=dict(SURF.stats(test),ok=True,test=test)
                else:
                    f=lambda k,d=None: float(q[k][0]) if k in q and q[k][0] not in ("","null") else d
                    r=SURF.ahead(f("lat"),f("lon"),f("hdg"),f("w",5.0),TERR.height,test=test,max_age_h=f("maxh",72.0))
                    r.update(ok=True,test=test)
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/weather":   # vêr og snøproduksjon (Vêr-knappen) – varsel frå MET, eller DEMO
            q=urllib.parse.parse_qs(u.query)
            f=lambda k,d=None: float(q[k][0]) if k in q and q[k][0] not in ("","null","undefined") else d
            try:
                demo=q.get("demo",["0"])[0]=="1"; lat,lon,psrc,palt,pname=wx_where(f("lat"),f("lon"),demo)
                if demo and lat is None: lat,lon,psrc=62.3905,6.5810,"demo"
                if lat is None or lon is None: r={"ok":False,"error":"Ingen posisjon: GNSS er av, og det finst korkje sist kjende posisjon eller terrengmodell. Vel ein stad (📍 Stad), kopla til GNSS eller legg inn ein terrengmodell."}
                else:
                    alt,src=wx_alt(lat,lon,palt if pname else f("alt"),chosen=bool(pname))
                    r=WX.forecast(lat,lon,alt,{"good":f("good"),"marg":f("marg"),"wind":f("wind")},demo=demo); r["altSrc"]=src; r["posSrc"]=psrc
                r["place"]=pname; r["placeLat"]=lat; r["placeLon"]=lon
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/weather/obs":   # «MÅLT NO» i Vêr: siste målingar frå næraste vêrstasjonar (MET Frost), eller DEMO
            q=urllib.parse.parse_qs(u.query)
            f=lambda k,d=None: float(q[k][0]) if k in q and q[k][0] not in ("","null","undefined") else d
            try:
                FROST.cid=(CFG.get("frost_client_id") or "").strip() or FR.CLIENT_ID
                demo=q.get("demo",["0"])[0]=="1"; lat,lon,psrc,palt,pname=wx_where(f("lat"),f("lon"),demo)
                if demo and lat is None: lat,lon=62.3905,6.5810
                if lat is None or lon is None: r={"ok":False,"error":"Ingen posisjon (GNSS av, ingen terrengmodell, ingen vald stad).","stations":[]}
                else:
                    alt,_src=wx_alt(lat,lon,palt if pname else f("alt"),chosen=bool(pname))
                    fixed=re.sub(r"[^A-Za-z0-9,]","",CFG.get("frost_stations") or "") or None
                    r=FROST.observations(lat,lon,alt,fixed,demo=demo); r["alt"]=None if alt is None else round(alt)
                    for st in r.get("stations",[]):   # våttemperatur der stasjonen måler luftfukt
                        if st.get("temp") is not None and st.get("rh") is not None: st["tw"]=round(VER.wetbulb(st["temp"],st["rh"]),1)
            except Exception as e: r={"ok":False,"error":str(e),"stations":[]}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/snowmap":   # Vêr › Snøkart: ESTIMAT av snøendring i den gjeldande terrengmodellen
            q=urllib.parse.parse_qs(u.query)
            try: r=snowmap_response(q)
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/nettest":   # Vêr › Test samband: MET og Frost, med forklaring på norsk
            try:
                import nett
                r=dict(nett.test(WX.ua,(CFG.get("frost_client_id") or "").strip() or FR.CLIENT_ID),ok=True)
                lat,lon,psrc,_a,pname=wx_where(); r["pos"]={"lat":lat,"lon":lon,"src":pname or psrc}
                LOG.event("Samband-test: "+", ".join(f"{t['name']} {'OK' if t['ok'] else 'FEIL'}" for t in r["tests"]))
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/terrain/centre":   # midten av den gjeldande terrengmodellen (når GNSS manglar)
            c=terrain_centre() if T.AVAILABLE else None
            ms=sorted((m for m in TERR.listing() if m.get("active") and m.get("type")=="barmark"),key=lambda m:-m["priority"]) if T.AVAILABLE else []
            r={"ok":True,"lat":c[0],"lon":c[1],"name":ms[0]["name"]} if c else {"ok":False}
            self.headers_ok(); self.wfile.write(json.dumps(r).encode()); return
        if u.path=="/api/ver/stad":   # Vêr › Stad: vald stad, lagra stader, terrengmodellar og staden til maskina
            w=wx_places(); a,b,c=stad()
            self.headers_ok(); self.wfile.write(json.dumps({"ok":True,**w,"terreng":wx_terrain_places(),"auto":{"lat":a,"lon":b,"src":c}},ensure_ascii=False).encode()); return
        if u.path=="/api/ver/stadsok":   # Vêr › Stad: søk i stadnamn (Kartverket) – krev nett
            q=urllib.parse.parse_qs(u.query)
            try: r=wx_search(q.get("q",[""])[0])
            except Exception as e: r={"ok":False,"error":str(e)}
            self.headers_ok(); self.wfile.write(json.dumps(r,ensure_ascii=False).encode()); return
        if u.path=="/api/opningstid":   # AI › Opningstider
            self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"cfg":OPEN.cfg,"upcoming":OPEN.upcoming(days=21)}).encode()); return
        if u.path=="/api/ai/eksport":   # opplæringspakke til ein framtidig sentral SNOWMAN-AI (berre lokal nedlasting)
            try:
                import zipfile, io, hashlib
                test=bool(STATE.get("simulated")); J=ai_journal(test)
                site=AIPROF.d["sites"]; sid=hashlib.sha256(json.dumps(sorted(site)).encode()).hexdigest()[:12] if site else "ukjend"
                buf=io.BytesIO()
                with zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as z:
                    z.writestr("LES-MEG.txt","SNOWMAN – opplæringspakke for lokal AI (anonymisert).\nInneheld læringsloggen (hendingar per prepareringsdøgn, utan posisjonar, trasénamn og talt tekst), "
                               "områdeprofilen utan namn og koordinatar, og statistikk. Ingen førarnamn, ingen lyd, ingen rå GNSS-spor.\n"
                               "Pakka blir IKKJE sendt automatisk. Ho er laga for ein framtidig sentral SNOWMAN-AI, og skal berre delast etter avtale med anlegget.\n")
                    anon=lambda e: {k:(v.split("|")[0] if k=="day" and isinstance(v,str) else v) for k,v in e.items() if k not in ("text","cells","trase")}|({"textLen":len(e.get("text",""))} if "text" in e else {})|({"cellCount":len(e["cells"])} if "cells" in e else {})
                    z.writestr("laering.jsonl","\n".join(json.dumps(anon(e),ensure_ascii=False) for e in J.ev))
                    z.writestr("profil.json",json.dumps({"site":sid,"test":test,"version":VERSION,
                        "profiles":[{k:v for k,v in p_.items() if k not in ("name","lat","lon","stations")} for p_ in site.values()]},ensure_ascii=False,indent=1))
                    names=[t["name"] for t in (TRA.listing() if TRA else [])]
                    def scrub(x):
                        for nm in names: x=x.replace(nm,"[trasé]")
                        return re.sub(r"«[^»]*»","«…»",x)
                    fd=[{k:(scrub(v) if isinstance(v,str) else v) for k,v in f_.items()} for f_ in AI.findings(J.ev)]
                    z.writestr("statistikk.json",json.dumps({"journal":J.stats(),"findings":fd},ensure_ascii=False,indent=1))
                data=buf.getvalue()
                self.send_response(200); self.send_header("Content-Type","application/zip")
                self.send_header("Content-Disposition",f'attachment; filename="snowman-ai-opplaering-{time.strftime("%Y%m%d")}{"-TEST" if test else ""}.zip"')
                self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
            except Exception as e:
                self.headers_ok(500); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if u.path=="/api/ai":   # AI-knappen: lokale preparéringsråd
            q=urllib.parse.parse_qs(u.query)
            try: r=ai_response(q)
            except Exception as e:
                import traceback; traceback.print_exc(); r={"ok":False,"error":str(e)}
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
        if u.path=="/tastatur.js":   # tastatur på skjermen (alle sider)
            self.headers_ok(200,"application/javascript"); self.wfile.write((HERE/"tastatur.js").read_bytes()); return
        if u.path=="/feilsok":   # RTK-feilsøkar (Innst. › GNSS › FEILSØK RTK)
            self.headers_ok(200,"text/html; charset=utf-8"); self.wfile.write(Path(__file__).with_name("feilsok.html").read_bytes()); return
        if u.path=="/api/rtksjekk":   # alle stega frå port til RTK FIX – utan passord/brukarnamn
            try:
                import rtksjekk as RS
                try:
                    from serial.tools import list_ports
                    ports=[{"port":p.device,"desc":p.description or ""} for p in list_ports.comports()]
                except Exception: ports=[]
                st=dict(STATE); st["rtk_mode"]=CFG.get("rtk_mode") or "snowman"
                if MOTOR[0] is not None: st["motor"]=MOTOR[0].status()
                net=None if st.get("ntrip_connected") else RS.net_check(str(CFG.get("caster") or ""),CFG.get("caster_port") or 2101)
                cfg={k:CFG.get(k) for k in ("serial_port","baud","caster","caster_port","mountpoint","rtcm_drop")}
                r=RS.check(st,cfg,ports,net); r["report"]=RS.report(r,"v"+VERSION); r["ok_api"]=True
            except Exception as e: r={"ok_api":False,"error":f"{e}{where(e)}"}
            self.headers_ok(); self.wfile.write(json.dumps(r,ensure_ascii=False).encode()); return
        if u.path=="/ntrip":
            p=Path(__file__).with_name("ntrip.html")
            self.headers_ok(200,"text/html; charset=utf-8"); self.wfile.write(p.read_bytes()); return
        m=re.fullmatch(r"/vendor/vaersymbol/([a-z_]{3,40})\.svg",u.path)
        if m and (HERE/"vendor"/"vaersymbol"/(m.group(1)+".svg")).is_file():   # vêrsymbol frå MET (MIT), til vêr-overlayet
            self.headers_ok(200,"image/svg+xml"); self.wfile.write((HERE/"vendor"/"vaersymbol"/(m.group(1)+".svg")).read_bytes()); return
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
                    if k in d and not (k=="password" and re.fullmatch(r"\*{3,}|•{3,}",str(d[k]))): CFG[k]=d[k]
                log_changes("NTRIP/mottakar",before,CFG,("serial_port","baud","caster","caster_port","mountpoint","username","password",
                            "ntrip_version","ntrip_timeout","gga_interval","initCmds","rtcm_drop","rtk_mode"))
                save_cfg(); update(last_error="")
                if "serial_port" in d: SERIAL_REOPEN.set()   # LAGRE / KOPLE TIL: kople alltid til mottakaren på nytt
                if rtk_snowman(): motor_start()
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
        if self.path=="/api/ver/stad":   # Vêr › Stad: vel, lagre, slett eller tilbake til automatisk (maskina)
            try:
                w=wx_place_set(json.loads(body or b"{}"))
                self.headers_ok(); self.wfile.write(json.dumps({"ok":True,**w},ensure_ascii=False).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path=="/api/opningstid":   # lagre opningstider (AI › Opningstider)
            try:
                before=json.dumps(OPEN.cfg,ensure_ascii=False); c=OPEN.save(json.loads(body or b"{}"))
                if json.dumps(c,ensure_ascii=False)!=before: LOG.event("Opningstider endra (AI)")
                self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"cfg":c,"upcoming":OPEN.upcoming(days=21)}).encode())
            except Exception as e:
                self.headers_ok(400); self.wfile.write(json.dumps({"ok":False,"error":str(e)}).encode())
            return
        if self.path in ("/api/ai/feedback","/api/ai/voice"):   # føraren: nyttig/ikkje nyttig, og talekommandoar (lokalt)
            try:
                d=json.loads(body or b"{}"); test=bool(STATE.get("simulated")) or bool(d.get("demo"))
                if AI is None: raise ValueError("Lokal AI er ikkje tilgjengeleg")
                if self.path.endswith("feedback"):
                    ai_journal(test).add("feedback",{"sec":str(d.get("sec"))[:8],"val":1 if d.get("val",0)>0 else -1})
                else:
                    ai_journal(test).add("voice",{"text":str(d.get("text",""))[:120],"intent":str(d.get("intent"))[:20],"ok":bool(d.get("ok"))})
                self.headers_ok(); self.wfile.write(b'{"ok":true}')
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
                                "detail3d","estOn","bgOn","viewMode","demoD","antX","antY","antN","ant2X","ant2Y","surfMem","surfH","kbMode","teleOn","wxGood","wxMarg","wxWind","aiOpen","aiGunRate","voiceOn","voiceProactive"))
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
        if self.path=="/api/surface/clear":   # gløym tidlegare snøoverflate (t.d. etter mykje nysnø)
            test=bool(STATE.get("simulated")); n=SURF.stats(test).get("cells",0); SURF.clear(test=test)
            LOG.event(f"Snøflateminne sletta ({n} ruter{' – test' if test else ''})")
            self.headers_ok(); self.wfile.write(json.dumps({"ok":True,"cleared":n}).encode()); return
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
LASTPOS=DATA/"sist-posisjon.json"
WXPLACE=DATA/"ver-stad.json"   # Vêr › Stad: vald stad og lagra stader (høyrer til anlegget, ikkje i git)
def wx_places():
    try: d=json.loads(WXPLACE.read_text("utf-8"))
    except Exception: d={}
    return {"valt":d.get("valt"),"lagra":d.get("lagra") or []}
def wx_place_ok(p):
    """Rydd ein stad frå klienten: namn, lat, lon (innanfor rimelege grenser), valfri høgd og kjelde."""
    try:
        lat,lon=float(p["lat"]),float(p["lon"])
        if not (-90<=lat<=90 and -180<=lon<=180): return None
        alt=p.get("alt"); alt=None if alt in (None,"") else float(alt)
        if alt is not None and not (-500<=alt<=9000): alt=None
        name=re.sub(r"\s+"," ",str(p.get("name") or "")).strip()[:60] or f"{lat:.4f}, {lon:.4f}"
        return {"name":name,"lat":round(lat,5),"lon":round(lon,5),"alt":alt,"src":str(p.get("src") or "")[:40]}
    except Exception: return None
def wx_place_set(d):
    """Vel/lagre/slett stad for Vêr. d: {action: vel|auto|lagre|slett, place|name}."""
    w=wx_places(); a=d.get("action")
    if a=="auto": w["valt"]=None
    elif a=="slett":
        w["lagra"]=[x for x in w["lagra"] if x.get("name")!=d.get("name")]
        if w["valt"] and w["valt"].get("name")==d.get("name"): w["valt"]=None
    elif a in ("vel","lagre"):
        p=wx_place_ok(d.get("place") or {})
        if not p: raise ValueError("Ugyldig stad (treng namn, breidd og lengd).")
        w["lagra"]=[p]+[x for x in w["lagra"] if x.get("name")!=p["name"]][:19]   # nyaste først, høgst 20
        if a=="vel": w["valt"]=p
    else: raise ValueError("Ukjend handling")
    write_atomic(WXPLACE,json.dumps(w,ensure_ascii=False,indent=1))
    LOG.event("Vêr: stad "+(("valt «"+w["valt"]["name"]+"»") if w["valt"] else "automatisk (maskina)")+f" ({a})")
    return w
def wx_where(lat=None,lon=None,demo=False):
    """Staden for Vêr-overlayet: vald stad (Vêr › Stad) går føre maskina. Returnerer (lat, lon, kjelde, høgd|None, namn|None)."""
    v=None if demo else wx_places()["valt"]
    if v: return v["lat"],v["lon"],"vald stad",v.get("alt"),v["name"]
    a,b,c=stad(lat,lon)
    return a,b,c,None,None
def wx_alt(lat,lon,alt=None,chosen=False):
    """Høgd for Vêr: oppgitt → terrengmodellen → (berre for maskina) GNSS. Ein vald stad utanfor terrengmodellen
    får høgda frå MET sin eigen høgdemodell (None) – aldri GNSS-høgda til maskina som står ein annan stad."""
    if alt is not None: return alt,"oppgitt for staden"
    if chosen:
        try:
            h=TERR.height(lat,lon) if T.AVAILABLE else None
            if h: return h["h"],"terrengmodell «"+h["name"]+"»"
        except Exception: pass
        return None,"høgdemodellen til MET"
    return terrain_alt(lat,lon)
def wx_terrain_places():
    """Midten av kvart aktive barmark-lag i terrengbiblioteket – ferdige stader å velje i Vêr."""
    out=[]
    try:
        for m in (TERR.listing() if T.AVAILABLE else []):
            if m.get("active") and m.get("type")=="barmark":
                la,lo=T.utm_inverse(m["x0"]+m["nx"]*m["dx"]/2,m["y0"]-m["ny"]*m["dy"]/2,m["zone"])
                out.append({"name":m.get("name") or "terrengmodell","lat":round(la,5),"lon":round(lo,5),"src":"terrengmodell"})
    except Exception: pass
    return out
STADNAMN_URL="https://ws.geonorge.no/stedsnavn/v1/navn"
def wx_search(text):
    """Søk i stadnamn frå Kartverket (Sentralt stadnamnregister, CC BY 4.0). Krev nett."""
    import nett
    text=(text or "").strip()[:60]
    if len(text)<2: return {"ok":False,"error":"Skriv minst to bokstavar."}
    q=urllib.parse.urlencode({"sok":text,"fuzzy":"true","utkoordsys":"4258","treffPerSide":"12","side":"1"})
    req=urllib.request.Request(STADNAMN_URL+"?"+q,headers={"User-Agent":WX.ua,"Accept":"application/json"})
    try:
        with nett.urlopen(req,timeout=8) as r: js=json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok":False,"error":"Stadnamnsøket krev nett. "+nett.explain(e)+" Utan nett: vel ein lagra stad, ein terrengmodell, midten av kartet eller skriv inn koordinatar.","detail":str(e)[:200]}
    out=[]
    for n in js.get("navn") or []:
        rp=n.get("representasjonspunkt") or {}
        if rp.get("nord") is None or rp.get("øst") is None: continue
        kom=", ".join(k.get("kommunenavn","") for k in (n.get("kommuner") or []) if k.get("kommunenavn"))
        nm=n.get("skrivemåte") or ((n.get("stedsnavn") or [{}])[0] or {}).get("skrivemåte") or text   # /navn eller /sted
        out.append({"name":nm,"lat":round(float(rp["nord"]),5),"lon":round(float(rp["øst"]),5),
                    "type":n.get("navneobjekttype") or "","kommune":kom,"src":"stadnamn"})
    return {"ok":True,"hits":out,"attr":"Stadnamn: Kartverket (CC BY 4.0)"}
def stad(lat=None,lon=None):
    """Staden Vêr, Frost, snøkart og AI gjeld for: oppgitt → GNSS → sist kjende GNSS-posisjon → midten av terrengmodellen.
    Returnerer (lat, lon, kjelde) – lat er None om ingenting finst."""
    if lat is not None and lon is not None: return lat,lon,"oppgitt"
    if STATE.get("lat") is not None and STATE.get("lon") is not None:
        try:
            if time.time()-getattr(stad,"_saved",0)>300:   # hugs posisjonen (høgst kvart 5. min)
                stad._saved=time.time(); write_atomic(LASTPOS,json.dumps({"lat":STATE["lat"],"lon":STATE["lon"],"t":int(time.time())}))
        except Exception: pass
        return STATE["lat"],STATE["lon"],"GNSS"
    try:
        d=json.loads(LASTPOS.read_text("utf-8")); return d["lat"],d["lon"],"sist kjende posisjon ("+time.strftime("%d.%m. kl. %H:%M",time.localtime(d["t"]))+")"
    except Exception: pass
    c=terrain_centre() if T.AVAILABLE else None
    if c: return c[0],c[1],"midten av terrengmodellen"
    return None,None,None
def terrain_alt(lat,lon,alt=None):
    """Høgda alle Vêr-funksjonane brukar: frå den gjeldande terrengmodellen (aktive barmark-lag), elles GNSS."""
    if alt is not None: return alt,"oppgitt"
    try:
        h=TERR.height(lat,lon) if T.AVAILABLE else None
        if h: return h["h"],"terrengmodell «"+h["name"]+"»"
    except Exception: pass
    a=STATE.get("altitude")
    return a,("GNSS-høgd" if a is not None else None)
def terrain_centre():
    """Midten av det høgast prioriterte aktive barmark-laget (når maskina står utanfor terrengmodellen)."""
    ms=sorted((m for m in TERR.listing() if m.get("active") and m.get("type")=="barmark"),key=lambda m:-m["priority"]) if T.AVAILABLE else []
    if not ms: return None
    m=ms[0]
    return T.utm_inverse(m["x0"]+m["nx"]*m["dx"]/2,m["y0"]-m["ny"]*m["dy"]/2,m["zone"])
SNOW_LEARN={}   # test/ekte → snokart.Learn (lærer kvar det kjem meir eller mindre snø)
def snow_learn(test):
    if test not in SNOW_LEARN: SNOW_LEARN[test]=SK.Learn(DATA/("snokart-laering-test.json" if test else "snokart-laering.json"))
    return SNOW_LEARN[test]
def _grid_utm(P,lat0,lon0,z):
    """UTM-koordinatane (sone z) til midten av kvar rute i snøkartet – same lineære tilnærming som TerrainLibrary.patch."""
    np=SK.np
    n,step,half=P["n"],P["step"],P["half"]
    xs=-half+np.arange(n)*step; X,Y=np.meshgrid(xs,-xs)
    mlat,mlon=111320.0,111320.0*math.cos(math.radians(lat0))
    E0,N0=T.utm_forward(lat0,lon0,z); Ex,Nx=T.utm_forward(lat0,lon0+10/mlon,z); Ey,Ny=T.utm_forward(lat0+10/mlat,lon0,z)
    return E0+(Ex-E0)/10*X+(Ey-E0)/10*Y, N0+(Nx-N0)/10*X+(Ny-N0)/10*Y, X, Y
def _production(P,lat0,lon0,X,Y,R=60.0):
    """Ruter innan R m frå snøkanon eller hydrant (anleggsobjekt): her kan det vere produsert snø."""
    np=SK.np
    m=np.zeros(X.shape,dtype=bool); pts=[]
    if not OBJ: return m,pts
    mlat,mlon=111320.0,111320.0*math.cos(math.radians(lat0))
    for o in OBJ.listing():
        if o.get("type") not in ("snokanon","hydrant"): continue
        x,y=(float(o["lng"])-lon0)*mlon,(float(o["lat"])-lat0)*mlat
        if abs(x)>P["half"]+R or abs(y)>P["half"]+R: continue
        m|=(X-x)**2+(Y-y)**2<=R*R; pts.append([round(x,1),round(y,1),o.get("type")])
    return m,pts
try: import ai as AI; AIPROF=AI.Profiles(DATA/"ai-profil.json")
except Exception: AI=AIPROF=None   # lokal AI krev numpy (same som snøkartet)
import opningstid as OT
OPEN=OT.Opningstid(DATA/"opningstid.json")   # opningstider (helg, kveld, skoleferiar, heilagdagar, manuelle unntak)
AIJ={}
def ai_journal(test):
    """Læringsloggen til den lokale AI-en (test og ekte for seg)."""
    if test not in AIJ: AIJ[test]=AI.Journal(DATA/("ai-laering-test.jsonl" if test else "ai-laering.jsonl"))
    return AIJ[test]
def _bin(lat,lon,size):
    z=SF.zone_of(lon); E,N=T.utm_forward(lat,lon,z); return f"{z},{int(E//size)},{int(N//size)}"
def _ui_cfg():
    try: return (lambda d:d.get("cfg",d))(json.loads(UI_CFG.read_text("utf-8")))
    except Exception: return {}
def ai_response(q):
    """AI-knappen: fem preparéringsråd frå lokal AI (snøkart, trasear, RTK, vêr). Alt er forslag og ESTIMAT."""
    if AI is None or SK is None or not T.AVAILABLE: return {"ok":False,"error":"Lokal AI krev terrengmotoren (numpy)."}
    np=SK.np
    demo=q.get("demo",["0"])[0]=="1"; test=bool(STATE.get("simulated")) or demo
    uc=_ui_cfg(); tgt0=float(uc.get("target",0.8)); tol=float(uc.get("tol",0.1)); openh=float(uc.get("aiOpen",10)); gun=float(uc.get("aiGunRate",AI.GUN_RATE))
    tras=[t for t in (TRA.listing() if TRA else []) if t.get("kind")=="trase"]
    f=lambda k,d=None: float(q[k][0]) if k in q and q[k][0] not in ("","null","undefined") else d
    if tras:
        la=[p[0] for t in tras for p in t["poly"]]; lo=[p[1] for t in tras for p in t["poly"]]
        clat,clon=(min(la)+max(la))/2,(min(lo)+max(lo))/2
        half=min(1500.0,max(300.0,max((max(la)-min(la))*111320,(max(lo)-min(lo))*111320*math.cos(math.radians(clat)))/2+80))
    else:
        clat,clon,_ps=stad(f("lat"),f("lon")); half=600.0
    qq={"half":[str(half)],"demo":["1" if demo else "0"],"cal":["1"],"learn":["1"],"stop":["0"]}
    if clat is not None: qq.update(lat=[str(clat)],lon=[str(clon)])
    ctx=snow_compute(qq)
    if not ctx.get("ok"):   # utan varsel eller terreng: vis likevel opningstider og nye funn
        J=ai_journal(test); nx=OPEN.next_opening()
        return dict(ctx,ok=False,findings=AI.findings(J.ev),journal=J.stats(),
                    opening={"next":[int(nx[0].timestamp()*1000),int(nx[1].timestamp()*1000),nx[2]] if nx else None,"upcoming":OPEN.upcoming(days=14)})
    R=ctx["R"]; P=R["P"]; n,step,half=P["n"],P["step"],P["half"]; lat0,lon0=P["lat0"],P["lon0"]; H=P["h"]
    now_ms=ctx["fc"][0]["t"]
    mlat,mlon=111320.0,111320.0*math.cos(math.radians(lat0))
    xs=-half+np.arange(n)*step; X,Y=np.meshgrid(xs,-xs)
    ll=lambda r,c: [round(lat0+(half-r*step)/mlat,7),round(lon0+(-half+c*step)/mlon,7)]
    Tn=snow_total(ctx,0); T24=snow_total(ctx,24)
    tgt=np.full((n,n),np.nan); tid=np.full((n,n),-1,dtype=int)
    for i,t in enumerate(tras):
        a=np.asarray(t["poly"],float); m=TR.inside_mask((a[:,1]-lon0)*mlon,(a[:,0]-lat0)*mlat,X,Y)
        tgt[m]=t["target"] if t.get("target") is not None else tgt0; tid[m]=i
    if not tras: tgt[:]=tgt0
    st=(TRA.status(with_map=True)["status"] if TRA else {})
    key="pctTest" if test else "pct"
    tinfo=[dict(id=t["id"],name=t["name"],area=t.get("area"),last=(st.get(t["id"]) or {}).get("last"),pct=(st.get(t["id"]) or {}).get(key,0)) for t in tras]
    out={"ok":True,"estimate":True,"demo":ctx["demo"],"test":test,"now":now_ms,"target":tgt0,"tol":tol,"trasear":len(tras),
         "measured":R["M"]["n"],"cal":R["cal"],"pfac":R["pfac"],"learn":{k:v for k,v in R["learn"].items() if k!="prodPts"}}
    # 1 tidspunkt
    nx=OPEN.next_opening()
    op_ms=nx[0].timestamp()*1000 if nx else None
    out["opening"]={"next":[int(nx[0].timestamp()*1000),int(nx[1].timestamp()*1000),nx[2]] if nx else None,"upcoming":OPEN.upcoming(days=14)}
    out["timing"]=AI.timing(ctx["fc"],tinfo,time.time()*1000,openh,op_ms) if tras else {"trasear":[],"opening":op_ms,"scores":[{"t":x["t"],"s":x["score"]} for x in AI.hour_scores(ctx["fc"])[:30]]}
    # objekt (hydrant/kanon) til næraste-avstand
    objs=[o for o in (OBJ.listing() if OBJ else []) if o.get("type") in ("snokanon","hydrant")]
    def nearest(la_,lo_):
        b=None
        for o in objs:
            d=TR.Local(la_,lo_); x,y=d.xy(np.array([float(o["lat"])]),np.array([float(o["lng"])]))
            dist=float(math.hypot(x[0],y[0]))
            if b is None or dist<b["dist"]: b={"name":o.get("name") or TR.OBJ_TYPES[o["type"]][0],"type":o["type"],"dist":round(dist),"lat":float(o["lat"]),"lon":float(o["lng"])}
        return b
    # 5 snøproduksjon: underskot etter venta nysnø dei neste 24 t
    d24,_=AI.deficit_surplus(T24,tgt,tol); dnow,snow_=AI.deficit_surplus(Tn,tgt,tol)
    labD,defc=AI.clusters(np.nan_to_num(d24)>0.05,d24,step,H,tile_m=80)   # område med minst 5 cm for lite, delt i 80 m-rutar
    lim={"good":float(uc.get("wxGood",-5)),"marg":float(uc.get("wxMarg",-2)),"wind":float(uc.get("wxWind",12))}
    prod=[]
    for c in sorted(defc,key=lambda c:-c["vol"])[:15]:
        la_,lo_=ll(c["r"],c["c"]); m=labD==c["k"]
        now_def=float(np.nansum(np.maximum(dnow[m],0)))*step*step
        w=AI.windows_at(ctx["fc"],c["z"]-ctx["z0"],lim,VER.wetbulb,VER.classify,VER.windows)
        ti=int(np.bincount(tid[m][tid[m]>=0]).argmax()) if (tid[m]>=0).any() else -1
        prod.append({"lat":la_,"lon":lo_,"area":c["area"],"vol":c["vol"],"mean":c["mean"],"max":c["max"],"z":c["z"],
                     "water":round(c["vol"]*AI.SNOW_WATER),"gunHours":round(c["vol"]/max(gun,1),1),
                     "naturalHelp":round(100*(1-c["vol"]/now_def)) if now_def>c["vol"] else 0,
                     "trase":tras[ti]["name"] if ti>=0 else None,"near":nearest(la_,lo_),"window":w[0] if w else None})
    cls=np.zeros((n,n),dtype=np.uint8); dd=np.nan_to_num(d24)
    cls[dd>0]=1; cls[dd>0.2]=2; cls[dd>0.4]=3
    out["production"]={"areas":prod,"totalVol":int(sum(c["vol"] for c in defc)),"totalArea":int(sum(c["area"] for c in defc)),
                       "gunRate":gun,"grid":base64.b64encode(cls.tobytes()).decode(),"n":n,
                       "bounds":[[lat0-(half+step/2)/mlat,lon0-(half+step/2)/mlon],[lat0+(half+step/2)/mlat,lon0+(half+step/2)/mlon]]}
    # 2 snøflytting: overskot → underskot i same trasé (no-situasjonen)
    _,defn=AI.clusters(np.nan_to_num(dnow)>0.05,dnow,step,H,tile_m=60); _,surn=AI.clusters(np.nan_to_num(snow_)>0.05,snow_,step,H,tile_m=60)
    tidof=lambda c: int(tid[int(round(c["r"])),int(round(c["c"]))])
    mv=AI.snow_moves(defn,surn,step,{c["k"]:tidof(c) for c in defn},{c["k"]:tidof(c) for c in surn})
    out["moves"]=[{"from":ll(m_["from"]["r"],m_["from"]["c"]),"to":ll(m_["to"]["r"],m_["to"]["c"]),"vol":m_["vol"],"dist":m_["dist"],"dz":m_["dz"],
                   "trase":tras[tidof(m_["to"])]["name"] if tras and tidof(m_["to"])>=0 else None,"surplus":m_["from"]["mean"],"deficit":m_["to"]["mean"]} for m_ in mv[:10]]
    # 3 hol og 4 kvalitet per trasé
    hol,qual=[],[]
    for i,t in enumerate(tras):
        s_=st.get(t["id"]) or {}; mp=s_.get("map")
        hs=[]
        if mp:
            hs,_m=AI.holes(base64.b64decode(mp["all" if test else "real"]),mp["W"],mp["H"],mp["cell"],s_.get(key,0))
            for h in hs:
                hol.append({"trase":t["name"],"area":h["area"],"len":h["len"],"lat":round(mp["lat0"]+(mp["y0"]+h["y"])/mp["my"],7),"lon":round(mp["lon0"]+(mp["x0"]+h["x"])/mp["mx"],7)})
        a=np.asarray(t["poly"],float)
        qq_=AI.quality(s_.get(key,0),len(hs),Tn[tid==i] if (tid==i).any() else None,t["target"] if t.get("target") is not None else tgt0,tol)
        qq_.update(name=t["name"],pct=s_.get(key,0),lat=float(a[:,0].mean()),lon=float(a[:,1].mean()),holes=len(hs))
        qual.append(qq_)
    out["holes"]=hol; out["quality"]=sorted(qual,key=lambda x:x["score"])
    out["coverTest"]=test
    # læringslogg: kva som går igjen (éi registrering per prepareringsdøgn) → nye funn
    J=ai_journal(test); day=time.strftime("%Y-%m-%d",time.localtime(TR.prep_day_start()))
    if prod: J.add("deficit",{"cells":sorted({_bin(a["lat"],a["lon"],40) for a in prod}),"vol":out["production"]["totalVol"]},day=day,unique=True)
    for tn in {h["trase"] for h in hol}:
        J.add("holes",{"trase":tn,"cells":sorted({_bin(h["lat"],h["lon"],20) for h in hol if h["trase"]==tn})},day=day+"|"+tn,unique=True)
    if R["cal"].get("n",0)>=10: J.add("cal",{k:R["cal"].get(k) for k in ("n","mae","bias","factor")},day=day,unique=True)
    out["findings"]=AI.findings(J.ev); out["journal"]=J.stats()
    # områdeprofil: lærer staden automatisk
    site=AIPROF.site(lat0,lon0,float(np.nanmin(H)),float(np.nanmax(H)),(ctx["HI"] or {}).get("stations"),test)
    AIPROF.learn(site,ctx["hist"]); out["profile"]=AI.Profiles.summary(site)
    return out
SNOW_HIST_H=72   # timar vêrhistorikk (Frost) i snøkartet – målingar eldre enn dette får berre endringa sidan då
SNOW_STOPS=(0,6,12,24,48)
def _snow_measured(P,lat0,lon0,test):
    """Målt snødjupne frå snøflate-minnet på rutenettet til snøkartet: djupne (m), tid (s), endring sidan førre besøk (m)
    og tida for førre besøk – snitt per rute. Berre målingar av same slag (test/ekte) som SNOWMAN køyrer no."""
    np=SK.np
    n,step,half=P["n"],P["step"],P["half"]
    sm=SURF.samples(test=test)
    out={"n":0}
    if not sm: return out
    A=np.array([(z,e,nn,S,t,ps if ps is not None else np.nan,pt if pt is not None else np.nan) for z,e,nn,S,t,ps,pt in sm],dtype=np.float64)
    X=np.full(len(A),np.nan); Y=np.full(len(A),np.nan)
    mlat,mlon=111320.0,111320.0*math.cos(math.radians(lat0))
    for z in set(A[:,0].astype(int)):
        E0,N0=T.utm_forward(lat0,lon0,z); Ex,Nx=T.utm_forward(lat0,lon0+10/mlon,z); Ey,Ny=T.utm_forward(lat0+10/mlat,lon0,z)
        J=np.array([[(Ex-E0)/10,(Ey-E0)/10],[(Nx-N0)/10,(Ny-N0)/10]]); Ji=np.linalg.inv(J)
        m=A[:,0]==z; dE,dN=A[m,1]-E0,A[m,2]-N0
        X[m]=Ji[0,0]*dE+Ji[0,1]*dN; Y[m]=Ji[1,0]*dE+Ji[1,1]*dN
    c=(X+half)/step; r=(half-Y)/step
    ins=np.isfinite(c)&(c>=0)&(r>=0)&(c<=n-1)&(r<=n-1)
    if not ins.any(): return out
    A,c,r=A[ins],c[ins],r[ins]
    H=P["h"]; c0=np.clip(np.floor(c).astype(int),0,n-2); r0=np.clip(np.floor(r).astype(int),0,n-2); fc=c-c0; fr=r-r0
    ter=(H[r0,c0]*(1-fc)*(1-fr)+H[r0,c0+1]*fc*(1-fr)+H[r0+1,c0]*(1-fc)*fr+H[r0+1,c0+1]*fc*fr)   # terreng der målinga er
    dep=A[:,3]-ter
    ok=np.isfinite(dep)
    ci=np.clip(np.round(c).astype(int),0,n-1)[ok]; ri=np.clip(np.round(r).astype(int),0,n-1)[ok]; A,dep=A[ok],dep[ok]
    lin=ri*n+ci
    cnt=np.bincount(lin,minlength=n*n).astype(float)
    D=np.bincount(lin,dep,minlength=n*n)/np.maximum(cnt,1)
    Tm=np.zeros(n*n); np.maximum.at(Tm,lin,A[:,4])
    hp=np.isfinite(A[:,5])
    cp=np.bincount(lin[hp],minlength=n*n).astype(float)
    dS=np.bincount(lin[hp],(A[hp,3]-A[hp,5]),minlength=n*n)/np.maximum(cp,1)
    Tp=np.bincount(lin[hp],A[hp,6],minlength=n*n)/np.maximum(cp,1)
    has=cnt>0
    # fyll mellom spora: snitt av målte ruter innan ca. 12 m (som snøflate-minnet gjer framfor maskina)
    k=max(1,int(round(12.0/step)))
    hm=has.reshape(n,n).astype(float); Dg=np.where(has,D,0.0).reshape(n,n); Tg=np.where(has,Tm,0.0).reshape(n,n)
    cntb=SK._box(hm,k); fill=(cntb>0)&~has.reshape(n,n)
    Dg=np.where(has.reshape(n,n),Dg,np.where(fill,SK._box(Dg,k)/np.maximum(cntb,1e-9),0.0))
    Tg=np.where(has.reshape(n,n),Tg,np.where(fill,SK._box(Tg,k)/np.maximum(cntb,1e-9),0.0))
    has2=has.reshape(n,n)|fill
    D=Dg.reshape(-1); Tm=Tg.reshape(-1); has=has2.reshape(-1)
    out.update(n=int(has.sum()),D=np.where(has,D,np.nan).reshape(n,n),T=np.where(has,Tm,np.nan).reshape(n,n),
               dS=np.where(cp>0,dS,np.nan).reshape(n,n),Tp=np.where(cp>0,Tp,np.nan).reshape(n,n),
               newest=float(A[:,4].max()),oldest=float(A[:,4].min()))
    return out
def snowmap_response(q):
    ctx=snow_compute(q)
    if not ctx.get("ok"): return ctx
    return snowmap_encode(ctx,q)
def snow_total(ctx,stop):
    """Estimert totaldjupne (cm) ved stoppet (0 = no, 6/12/24/48 t fram) – NaN der det ikkje er målt."""
    np=SK.np; R=ctx["R"]; M,run=R["M"],R["run"]
    if not M["n"]: return np.full(R["P"]["h"].shape,np.nan)
    cap=run["caps"]["t"]; S=run["snaps"]; ks=ctx["stops"][stop]
    return np.where(np.isfinite(M["D"])&np.isfinite(cap["w"]),np.maximum(0.0,M["D"]*100.0+(S[ks]["w"]-cap["w"])),np.nan)
def snow_compute(q):
    f=lambda k,d=None: float(q[k][0]) if k in q and q[k][0] not in ("","null","undefined") else d
    if not T.AVAILABLE or SK is None: return {"ok":False,"error":"Terrengmotoren er ikkje tilgjengeleg (numpy manglar)."}
    np=SK.np
    half=min(1500.0,max(150.0,f("half",600.0))); stop=int(f("stop",0)); stop=stop if stop in SNOW_STOPS else 0
    loose=min(50.0,max(0.0,f("loose",0.0))); demo=q.get("demo",["0"])[0]=="1"; usecal=q.get("cal",["0"])[0]=="1"; uselearn=q.get("learn",["0"])[0]=="1"
    test=bool(STATE.get("simulated")) or demo
    lat,lon,_ps=stad(f("lat"),f("lon")); centred="maskina" if _ps in ("GNSS","oppgitt") else (_ps or "maskina")
    if lat is None or TERR.height(lat,lon) is None:
        c=terrain_centre()
        if c is None: return {"ok":False,"error":"Ingen aktiv terrengmodell (barmark). Snøkartet byggjer på den gjeldande terrengmodellen – legg inn eller slå på eit lag under Innst. › Terreng."}
        lat,lon=c; centred="terrengmodellen"
    g=50.0   # fest midten til eit 50 m-rutenett, så utrekninga kan gjenbrukast medan maskina køyrer
    lat=round(lat*111320/g)*g/111320; mx=111320*math.cos(math.radians(lat)); lon=round(lon*mx/g)*g/mx
    step=max(1.0,round(half/150.0,1))
    z0,altsrc=terrain_alt(lat,lon)
    if z0 is None: return {"ok":False,"error":"Fann ikkje høgda i terrengmodellen."}
    W=WX.forecast(lat,lon,z0,demo=demo)
    if not W.get("ok"): return {"ok":False,"error":W.get("error","Ingen vêrdata"),"detail":W.get("detail")}
    now=time.time()
    fc=[h for h in W["hours"] if h["t"]>=now*1000-3600000][:48]
    if not fc: return {"ok":False,"error":"Varselet har ingen timar framover."}
    try:
        FROST.cid=(CFG.get("frost_client_id") or "").strip() or FR.CLIENT_ID
        fixed=re.sub(r"[^A-Za-z0-9,]","",CFG.get("frost_stations") or "") or None
        HI=FROST.history(lat,lon,z0,SNOW_HIST_H,fixed,demo=demo,now=now)
    except Exception as e: HI={"ok":False,"error":str(e),"hours":[]}
    hist=[h for h in HI.get("hours",[]) if h["t"]<fc[0]["t"]]
    for h in hist: h["tw"]=round(VER.wetbulb(h["temp"],h.get("rh") or 90.0),1)
    line=hist+fc; know=len(hist); t_line0=line[0]["t"]/1000
    stops={s:min(len(line),know+s) for s in SNOW_STOPS}
    layers=tuple(m["id"]+str(m.get("priority")) for m in TERR.listing() if m.get("active"))
    ck=(round(lat,6),round(lon,6),half,loose,demo,test,usecal,uselearn,W.get("updated") or W.get("age_min"),fc[0]["t"],len(hist),layers,int((SURF.stats(test).get("newest") or 0)//600))
    c=SNOWMAP_CACHE.get(ck)   # inntil 3 utrekningar (snøkart og AI kan ha ulike utsnitt)
    if c and time.time()-c[1]<600: R=c[2]
    else:
        P=TERR.patch(lat,lon,half,step)
        if P is None: return {"ok":False,"error":"Terrengmodellen dekkjer ikkje området."}
        M=_snow_measured(P,lat,lon,test)
        n=P["n"]
        it=np.full((n,n),-1,dtype=int); ip=np.full((n,n),-1,dtype=int)
        if M["n"]:
            tt=M["T"]; okm=np.isfinite(tt)
            it[okm]=np.clip(np.floor((tt[okm]-t_line0)/3600).astype(int)+1,0,know)        # tilstanden like etter målinga
            tp=M["Tp"]; okp=np.isfinite(tp)&(tp>=t_line0)
            ip[okp]=np.clip(np.floor((tp[okp]-t_line0)/3600).astype(int)+1,0,know)
            ip[it<=ip]=-1
        key=(round(lat,6),round(lon,6),half,step,layers)
        run=SNOWMAP.run(P,line,z0,loose,key=key,stops=list(stops.values())+[0],capture={"t":it,"p":ip})
        z=SF.zone_of(lon); GE,GN,GX,GY=_grid_utm(P,lat,lon,z)
        prod,prodpts=_production(P,lat,lon,GX,GY)
        cal={"n":0}; lr={"added":0,"rejected":0}
        if M["n"] and (ip>=0).any():
            ds=run["caps"]["t"]["s"]-run["caps"]["p"]["s"]
            cal=SK.calibration(ds,M["dS"]*100.0,(ip>=0)&~prod)
            a_,r_=snow_learn(test).update(z,GE,GN,100.0*ds/SK.RHO_GROOMED,M["dS"]*100.0,M["T"],(ip>=0)&~prod)   # lær kvar det kjem snø
            lr={"added":a_,"rejected":r_}
        spat=snow_learn(test).factor(z,GE,GN)
        used=1.0
        if (usecal and cal.get("factor")) or (uselearn and np.isfinite(spat).any()):
            used=cal["factor"] if usecal and cal.get("factor") else 1.0
            run=SNOWMAP.run(P,line,z0,loose,key=key,pfac=used,stops=list(stops.values())+[0],capture={"t":it,"p":ip},
                            spatial=spat if uselearn else None)
        lr.update(snow_learn(test).stats()); lr["cells"]=int(np.isfinite(spat).sum()); lr["prodCells"]=int(prod.sum()); lr["prodPts"]=prodpts
        R={"P":P,"M":M,"run":run,"cal":cal,"pfac":used,"it":it,"learn":lr,"spat":spat}
        SNOWMAP_CACHE[ck]=(ck,time.time(),R)
        while len(SNOWMAP_CACHE)>3: SNOWMAP_CACHE.pop(min(SNOWMAP_CACHE,key=lambda k:SNOWMAP_CACHE[k][1]))
    return {"ok":True,"R":R,"stops":stops,"line":line,"know":know,"hist":hist,"HI":HI,"W":W,"fc":fc,"test":test,"demo":demo,
            "lat":lat,"lon":lon,"half":half,"step":step,"z0":z0,"altsrc":altsrc,"centred":centred,"usecal":usecal,"uselearn":uselearn,"loose":loose,"now":now}
def snowmap_encode(ctx,q):
    np=SK.np
    stop=int(float(q.get("stop",["0"])[0] or 0)); stop=stop if stop in SNOW_STOPS else 0
    R,stops,line,know,hist,HI,W,fc,test=ctx["R"],ctx["stops"],ctx["line"],ctx["know"],ctx["hist"],ctx["HI"],ctx["W"],ctx["fc"],ctx["test"]
    half,step,z0,altsrc,centred,usecal,uselearn,loose,now=ctx["half"],ctx["step"],ctx["z0"],ctx["altsrc"],ctx["centred"],ctx["usecal"],ctx["uselearn"],ctx["loose"],ctx["now"]
    P,M,run,ok=R["P"],R["M"],R["run"],R["run"]["ok"]
    S=run["snaps"]; ks=stops[stop]; kn=stops[0]
    if stop==0:   # sidan sist målt (eller sidan starten på historikken der det ikkje er målt)
        cap=run["caps"]["t"]; has=np.isfinite(cap["w"])
        rw=np.where(has,cap["w"],S[0]["w"]); rn=np.where(has,cap["n"],S[0]["n"])
        a,b=0,know
    else:
        rw,rn=S[kn]["w"],S[kn]["n"]; a,b=kn,ks
    cw,cn=S[ks]["w"]-rw,S[ks]["n"]-rn
    tot=np.full(cw.shape,np.nan); age=np.full(cw.shape,255,dtype=np.uint8); tstat={}
    if M["n"]:
        cap=run["caps"]["t"]
        tot=np.where(np.isfinite(M["D"])&np.isfinite(cap["w"]),np.maximum(0.0,M["D"]*100.0+(S[ks]["w"]-cap["w"])),np.nan)
        ah=(now-M["T"])/3600.0
        age=np.where(np.isfinite(ah),np.clip(np.round(ah),0,254),255).astype(np.uint8)
        v=tot[np.isfinite(tot)]
        if v.size: tstat={"n":int(v.size),"mean":round(float(v.mean()),1),"p10":round(float(np.percentile(v,10)),1),"p90":round(float(np.percentile(v,90)),1),
                          "min":round(float(v.min()),1),"max":round(float(v.max()),1)}
    hs=SK.hour_stats(line,a,b,run["driftHours"]); hs.update(SK.field_stats(cw,cn,ok))
    enc=lambda a_: base64.b64encode(np.where(np.isfinite(a_),np.clip(np.round(a_*10),-32000,32000),-32768).astype("<i2").tobytes()).decode()
    H=P["h"]
    return {"ok":True,"estimate":True,"demo":W.get("demo",False),"test":test,"offline":W.get("offline",False),"age_min":W.get("age_min"),
       "lat0":P["lat0"],"lon0":P["lon0"],"half":half,"step":step,"n":P["n"],"layers":P["layers"],"centred":centred,
       "z0":round(z0),"altSrc":altsrc,"zmin":round(float(np.nanmin(H))),"zmax":round(float(np.nanmax(H))),
       "stop":stop,"from":line[a]["t"] if a<len(line) else None,"to":(line[b-1]["t"]+3600000) if 0<b<=len(line) else None,
       "now":fc[0]["t"],"histFrom":line[0]["t"] if hist else None,"histHours":len(hist),
       "hist":{"ok":HI.get("ok",False),"error":HI.get("error"),"stations":HI.get("stations"),"missing":HI.get("missing"),"demo":HI.get("demo",False)},
       "loose":loose,"stats":hs,"total":tstat,"measured":{"n":M["n"],"newest":M.get("newest"),"oldest":M.get("oldest")},
       "cal":R["cal"],"pfac":R["pfac"],"usecal":usecal,"uselearn":uselearn,"learn":R["learn"],"secs":run["secs"],
       "spat":enc(R["spat"]*10.0),
       "hill":base64.b64encode(SK.hillshade(H,step).tobytes()).decode(),
       "with":enc(cw),"without":enc(cn),"tot":enc(tot),"age":base64.b64encode(age.tobytes()).decode(),
       "z":base64.b64encode(np.where(np.isfinite(H),H,-9999).astype("<f4").tobytes()).decode(),
       "attr":"Varsel: MET Norway (CC BY 4.0) · Målingar: MET Frost · Terreng: "+", ".join(P["layers"])}
def ui_bounds():
    """Snøintervalla frå førarskjermen (Innst. › Snøintervall), til fargane i PDF-rapporten."""
    try: return (lambda d:d.get("cfg",d))(json.loads(UI_CFG.read_text("utf-8"))).get("bounds")
    except Exception: return None
def ui_machine():
    try: return json.loads(UI_CFG.read_text("utf-8")).get("mname","")
    except Exception: return ""
def export_now():
    c=report_cfg()
    if not (FUEL and c["on"]): return
    try:
        n,files=DS.export_reports(FUEL,c["dir"],ui_machine(),bounds=ui_bounds())
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
    motor_start()
    print(f"SNOWMAN PC v{VERSION} køyrer: http://127.0.0.1:{a.http_port}")
    if a.lan or CFG.get("hudLan"): set_hud_lan(True)
    # Hovudtenesta (styring, innstillingar) er berre tilgjengeleg på denne PC-en.
    if O.system_cfg().get("logAlways"): start_log(f"Starta automatisk. SNOWMAN v{VERSION}")
    SERVER[0]=http.server.ThreadingHTTPServer(("127.0.0.1",a.http_port),API)
    try: SERVER[0].serve_forever()
    except KeyboardInterrupt: pass
    finally:
        STOP.set(); save_cfg(); LOG.stop()
        try: SURF.save(force=True)
        except Exception: pass
        try:
            if serial_obj: serial_obj.close()   # frigjer COM-porten til Leica
        except Exception: pass
        print("SNOWMAN-tenesta er avslutta.")
    if RESTART[0]: sys.exit(3)   # oppstartsprogrammet startar tenesta og vindauget på nytt

if __name__=="__main__": main()
