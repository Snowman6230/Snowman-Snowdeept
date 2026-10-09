#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Oppstart av SNOWMAN på alle system (Windows, Linux, macOS).

Gjer det same som start-snowman.sh: startar eventuelt simulatoren, så den lokale tenesta, og opnar
førarskjermen i nettlesaren. Ctrl + C (eller å lukke vindauget) stoppar alt.

  python start_snowman.py                 seriellporten som er lagra i innstillingane (Leica)
  python start_snowman.py COM3            denne porten (Windows), eller /dev/ttyUSB0 (Linux)
  python start_snowman.py sim             simulert mottakar
  python start_snowman.py simterreng      simulert mottakar over testterreng med fasit
  python start_snowman.py simanlegg       simulert mottakar over terrengmodellane du har lagt inn
  python start_snowman.py stopp           stopp SNOWMAN som køyrer
  python start_snowman.py meny            meny (brukt av SNOWMAN.bat på Windows)
  python start_snowman.py oppdater        hent siste versjon frå GitHub (krev git)
  python start_snowman.py versjon         skriv versjonsnummeret
  --kiosk   kioskmodus (berre SNOWMAN på skjermen)      --hud   HUD i eige vindauge   --lan   HUD på mobil
  --auto    bruk innstillinga i SNOWMAN (Innst. › System) for kiosk – brukt ved autostart

Kioskmodus: knappen «Vanleg skjerm» i SNOWMAN lukkar kioskvindauget og opnar vanleg vindauge,
«Kioskmodus» går tilbake. Lukkar nokon kioskvindauget (t.d. Alt + F4), blir det opna att (vakthund).
"""
import argparse, json, os, shutil, signal, socket, subprocess, sys, time, webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIDS = HERE / "data" / "run.pids"
# Eigne nettlesarprofilar for kiosk og vanleg vindauge: kvart vindauge blir sin eigen prosess som SNOWMAN kan lukke og
# opne att. (Innstillingane i førarskjermen ligg i tenesta, så dei er like i begge.)
PROFILE = {"kiosk": HERE / "data" / "nettlesar-kiosk", "window": HERE / "data" / "nettlesar"}
LAUNCHER = HERE / "data" / "launcher.json"
WREQ = HERE / "data" / "window-request.txt"   # skriven av tenesta når føraren byter mellom kiosk og vanleg skjerm
SYSTEM = HERE / "data" / "system.json"        # Innst. › System: kiosk ved oppstart, autostart
URL = "http://127.0.0.1:8765"
WIN = os.name == "nt"


def port_busy(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def stopp(quiet=False):
    """Stopp prosessar som ein tidlegare oppstart har sett i gang."""
    n = 0
    try:
        for pid in json.loads(PIDS.read_text()):
            if pid == os.getpid():
                continue
            try:
                if WIN:
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
                else:
                    os.kill(pid, signal.SIGTERM)
                n += 1
            except (OSError, ProcessLookupError):
                pass
        PIDS.unlink()
    except (FileNotFoundError, ValueError):
        pass
    for _ in range(20):
        if not port_busy(8765):
            break
        time.sleep(0.2)
    if not quiet:
        print("SNOWMAN er stoppa." if n else "SNOWMAN køyrde ikkje.")


def find_browser():
    """Edge eller Chrome/Chromium – desse kan opne førarskjermen som eige vindauge eller i fullskjerm."""
    cands = []
    if WIN:
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [Path(base) / "Microsoft/Edge/Application/msedge.exe", Path(base) / "Google/Chrome/Application/chrome.exe"]
        cands = [str(c) for c in cands if c.exists()]
    else:
        cands = [shutil.which(b) for b in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge")]
    return next((c for c in cands if c), None)


def open_window(browser, url, kiosk=False):
    """Opne førarskjermen: kiosk (heile skjermen, ingen nettlesarmeny) eller vanleg app-vindauge."""
    if browser:
        mode = "kiosk" if kiosk else "window"
        base = [browser, f"--user-data-dir={PROFILE[mode]}", "--no-first-run", "--no-default-browser-check", "--noerrdialogs",
                "--disable-session-crashed-bubble", "--hide-crash-restore-bubble"]
        if kiosk:
            args = base + ["--kiosk", url + "/?kiosk=1", "--edge-kiosk-type=fullscreen", "--disable-infobars", "--disable-pinch"]
        else:
            args = base + ["--app=" + url, "--start-maximized"]
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    webbrowser.open(url)
    return None


def open_checked(browser, url, kiosk):
    """Opne vindauge og sjekk at det faktisk kom opp (prosessen lever etter 3 s). Prøv ein gong til om ikkje."""
    for attempt in range(2):
        p = open_window(browser, url, kiosk)
        if p is None:
            return None
        for _ in range(30):
            if p.poll() is not None:
                break
            time.sleep(0.1)
        if p.poll() is None:
            return p
        time.sleep(1.5)  # profilen var truleg framleis i bruk av eit vindauge som held på å lukke seg
    print("Fekk ikkje opna SNOWMAN-vindauget – opnar i vanleg nettlesar.")
    webbrowser.open(url)
    return None


def close_window(p):
    """Lukk eit nettlesarvindauge som SNOWMAN opna (heile prosesstreet på Windows) og vent til det er heilt borte."""
    if p is None or p.poll() is not None:
        return
    if WIN:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    else:
        p.terminate()
    try:
        p.wait(8)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait(3)
    time.sleep(1.0)  # la nettlesaren sleppe profilen før eit nytt vindauge blir opna


def system_cfg():
    try:
        return json.loads(SYSTEM.read_text("utf-8"))
    except Exception:
        return {}


def version():
    import re
    m = re.search(r'^VERSION="([^"]+)"', (HERE / "snowman_pc.py").read_text("utf-8"), re.M)
    return m.group(1) if m else HERE.name


ZIP_URL = "https://github.com/Snowman6230/Snowman-Snowdeept/archive/refs/heads/main.zip"


def oppdater():
    """Hent siste versjon. Med git: git pull. Utan git (t.d. Windows med zip): last ned zip frå GitHub og
    skriv berre filer som er endra inn i pc-mappa. Mappene data og .venv blir aldri rørte."""
    repo = HERE.parent.parent
    old = version()
    if (repo / ".git").exists() and shutil.which("git"):
        print("Hentar siste versjon frå GitHub …")
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"])
        if r.returncode != 0:
            return print("Oppdateringa feila. Sjekk nettet, eller om du har endra filer i SNOWMAN-mappa.")
    else:
        import io, urllib.request, zipfile
        print("Lastar ned siste versjon frå GitHub …")
        try:
            try:
                import nett                      # sertifikat frå Windows (truststore), same som Vêr
                data = nett.urlopen(urllib.request.Request(ZIP_URL), timeout=60).read()
            except ImportError:
                data = urllib.request.urlopen(ZIP_URL, timeout=60).read()
        except Exception as e:
            return print(f"Fekk ikkje lasta ned ({e}). Sjekk at PC-en er på nett.")
        pcdir, n = HERE.parent, 0
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            # berre versjonsmapper som kan køyrast (har start_snowman.py) – ikkje dei gamle prototypane
            names = z.namelist()
            apps = {n.split("/")[2] for n in names if n.count("/") == 3 and n.endswith("/start_snowman.py") and n.split("/")[1] == "pc"}
            for m in z.infolist():
                parts = m.filename.split("/")
                if m.is_dir() or len(parts) < 3 or parts[1] != "pc":
                    continue
                rel = parts[2:]
                if len(rel) > 1 and rel[0] not in apps:
                    continue
                if "data" in rel or ".venv" in rel or "__pycache__" in rel:
                    continue
                dst = pcdir.joinpath(*rel)
                new_bytes = z.read(m)
                if dst.exists() and dst.read_bytes() == new_bytes:
                    continue  # uendra (viktig for .bat-fila som køyrer no)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(new_bytes)
                n += 1
        print(f"{n} filer oppdaterte.")
        req = HERE / "requirements.txt"
        if req.exists():
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(req)])
    new = version()
    if new != old:
        print(f"Ferdig: v{old} → v{new}. Start SNOWMAN på nytt for å bruke den nye versjonen.")
    else:
        print(f"Ferdig: du har siste versjon (v{new}).")


def meny():
    print()
    print(f"  SNOWMAN by Alpindata  (v{version()})")
    print("  ─────────────────────────────")
    print("  1  Start (Leica-mottakar)")
    print("  2  Demo – simulert mottakar")
    print("  3  Test over terrengmodellane dine")
    print("  4  Start i kioskmodus (trakkemaskin)")
    print("  5  Hent siste versjon")
    print("  6  Stopp SNOWMAN")
    print("  0  Avslutt")
    print()
    try:
        v = input("  Vel eit tal og trykk Enter: ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if v == "5":
        return oppdater()
    if v == "6":
        return stopp()
    args = {"1": [], "2": ["sim"], "3": ["simanlegg"], "4": ["--kiosk"]}.get(v)
    if args is not None:
        sys.argv = [sys.argv[0]] + args
        main()


def main():
    ap = argparse.ArgumentParser(description="Start SNOWMAN")
    ap.add_argument("mode", nargs="?", default="", help="sim | simterreng | simanlegg | stopp | installer | autostart | seriellport (COM3, /dev/ttyUSB0)")
    ap.add_argument("arg", nargs="?", default="", help="installer: kontor | maskin   autostart: pa | av")
    ap.add_argument("--kiosk", action="store_true", help="kioskmodus (trakkemaskin)")
    ap.add_argument("--auto", action="store_true", help="kiosk eller vanleg etter Innst. › System (autostart)")
    ap.add_argument("--hud", action="store_true", help="opne HUD i eige vindauge")
    ap.add_argument("--lan", action="store_true", help="HUD på mobil i same nett (port 8766)")
    ap.add_argument("--no-browser", action="store_true", help="ikkje opne nettlesaren")
    a = ap.parse_args()
    a.mode = {"demo": "sim", "test": "simanlegg", "start": ""}.get(a.mode, a.mode)
    if a.mode == "stopp":
        return stopp()
    if a.mode == "meny":
        return meny()
    if a.mode == "oppdater":
        return oppdater()
    if a.mode == "versjon":
        return print(version())
    if a.mode == "installer":  # val i installasjonen: kontor eller maskin
        import oppstart
        return oppstart.install("maskin" if a.arg.lower().startswith("m") else "kontor")
    if a.mode == "autostart":
        import oppstart
        return print(oppstart.autostart_set(a.arg.lower() in ("pa", "på", "on", "1"))[1])
    if port_busy(8765):
        print("SNOWMAN køyrde alt – stoppar den gamle først.")
        stopp(quiet=True)
    PIDS.parent.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    procs, extra, port = [], [], None
    if a.mode in ("sim", "simterreng", "simanlegg"):
        pf = HERE / "data" / "sim-port.txt"
        pf.unlink(missing_ok=True)
        sargs = [py, str(HERE / "simuler-leica.py"), str(pf), "--tcp", "7777"]
        if a.mode == "simterreng":
            if not (HERE / "testterreng.tif").exists():
                subprocess.run([py, str(HERE / "testterreng.py"), str(HERE / "testterreng.tif")], cwd=HERE)
            print("Testterreng: last opp testterreng.tif under Innst. › Terreng, og lagre kalibrering (antenne 2,8 m).")
            sargs.append("--terreng")
        elif a.mode == "simanlegg":
            print("Anleggstest: legg inn terrengmodell under Innst. › Terreng og lagre kalibrering (antenne 2,8 m).")
            print("Maskina køyrer over det øvste aktive terrenglaget. Snøen er simulert.")
            sargs.append("--anlegg")
        procs.append(subprocess.Popen(sargs, cwd=HERE))
        for _ in range(50):
            if pf.exists() and pf.read_text().strip():
                break
            time.sleep(0.1)
        port = pf.read_text().strip()
        extra.append("--simulert")
    elif a.mode:
        port = a.mode
    if a.lan:
        extra.append("--lan")
    if port:
        extra += ["--serial", port]
    srv_args = [py, str(HERE / "snowman_pc.py")] + extra
    procs.append(subprocess.Popen(srv_args, cwd=HERE))

    def on_term(*_):  # «stopp» frå eit anna vindauge: rydd opp som ved Ctrl + C
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, on_term)
    except (ValueError, AttributeError):
        pass
    PIDS.write_text(json.dumps([os.getpid()] + [p.pid for p in procs]))  # oppstartsprogrammet først
    for _ in range(80):  # vent til tenesta svarar
        if port_busy(8765):
            break
        time.sleep(0.1)
    kiosk = a.kiosk or (a.auto and bool(system_cfg().get("kiosk")))
    b, win = None, None
    WREQ.unlink(missing_ok=True)

    def write_state():
        LAUNCHER.write_text(json.dumps({"pid": os.getpid(), "mode": "kiosk" if kiosk else "window", "browser": bool(b)}))

    if not a.no_browser:
        b = find_browser()
        write_state()  # før vindauget opnar: førarskjermen spør straks om kiosk er mogleg
        if a.hud:
            open_window(b, URL + "/hud")
        win = open_checked(b, URL, kiosk)
    write_state()
    print(f"SNOWMAN køyrer på {URL} – trykk Ctrl + C her for å stoppe.")
    if kiosk:
        print("Kioskmodus: knappen «Vanleg skjerm» i SNOWMAN går til vanleg vindauge.")
    restarts = []
    try:
        while True:
            time.sleep(0.5)
            srv = procs[-1]
            if srv.poll() is not None:
                # Tenesta stoppa. Avslutt SNOWMAN (kode 0) → ferdig. Krasj → start på nytt (vakthund, maks 5 gonger på 2 min).
                if srv.returncode == 0:
                    break
                if srv.returncode == 3:  # «Start SNOWMAN på nytt» etter oppdatering: ny teneste og nytt vindauge
                    print("Startar SNOWMAN på nytt …")
                    procs[-1] = subprocess.Popen(srv_args, cwd=HERE)
                    PIDS.write_text(json.dumps([os.getpid()] + [p.pid for p in procs]))
                    for _ in range(80):
                        if port_busy(8765):
                            break
                        time.sleep(0.1)
                    if b:
                        close_window(win)
                        win = open_checked(b, URL, kiosk)
                    continue
                restarts = [t for t in restarts if time.time() - t < 120] + [time.time()]
                if len(restarts) > 5:
                    print("SNOWMAN-tenesta krasjar gong på gong – stoppar. Sjå meldingane over.")
                    break
                print("SNOWMAN-tenesta stoppa uventa – startar på nytt …")
                procs[-1] = subprocess.Popen(srv_args, cwd=HERE)
                PIDS.write_text(json.dumps([os.getpid()] + [p.pid for p in procs]))
                continue
            if WREQ.exists():  # «Vanleg skjerm» / «Kioskmodus» frå førarskjermen
                req = WREQ.read_text().strip()
                WREQ.unlink(missing_ok=True)
                want = req == "kiosk"
                if b and want != kiosk:
                    close_window(win)
                    kiosk = want
                    write_state()
                    win = open_checked(b, URL, kiosk)
                    print("Byta til " + ("kioskmodus." if kiosk else "vanleg skjerm."))
                continue
            if kiosk and b and win is not None and win.poll() is not None:
                print("Kioskvindauget vart lukka – opnar det att (vakthund).")
                time.sleep(1.5)
                win = open_checked(b, URL, True)
    except KeyboardInterrupt:
        pass
    finally:
        LAUNCHER.unlink(missing_ok=True)
        WREQ.unlink(missing_ok=True)
        close_window(win)  # SNOWMAN-vindauget blir lukka saman med tenesta
        for p in procs:
            try:
                p.terminate()
            except OSError:
                pass
        PIDS.unlink(missing_ok=True)
        print("SNOWMAN er stoppa.")


if __name__ == "__main__":
    main()
