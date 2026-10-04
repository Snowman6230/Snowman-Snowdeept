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
  --kiosk   fullskjerm (trakkemaskin)   --hud   HUD i eige vindauge   --lan   HUD på mobil
"""
import argparse, json, os, shutil, signal, socket, subprocess, sys, time, webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIDS = HERE / "data" / "run.pids"
PROFILE = HERE / "data" / "nettlesar"        # eigen nettlesarprofil: eigne innstillingar, og vindauget kan lukkast av SNOWMAN
KREQ = HERE / "data" / "kiosk-request.txt"   # skriven av tenesta når føraren trykkjer «Avslutt fullskjerm»
LAUNCHER = HERE / "data" / "launcher.json"
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
    if browser:
        base = [browser, f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check", "--noerrdialogs"]
        args = base + (["--kiosk", url + "/?kiosk=1", "--edge-kiosk-type=fullscreen", "--disable-infobars"] if kiosk else ["--app=" + url])
        return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    webbrowser.open(url)
    return None


def close_window(p):
    """Lukk eit nettlesarvindauge som SNOWMAN opna (heile prosesstreet på Windows)."""
    if p is None or p.poll() is not None:
        return
    if WIN:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    else:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()


def version():
    import re
    m = re.search(r'^VERSION="([^"]+)"', (HERE / "snowman_pc.py").read_text("utf-8"), re.M)
    return m.group(1) if m else HERE.name


def oppdater():
    repo = HERE.parent.parent
    if (repo / ".git").exists() and shutil.which("git"):
        print("Hentar siste versjon frå GitHub …")
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"])
        print("Ferdig. Start SNOWMAN på nytt for å bruke den nye versjonen." if r.returncode == 0 else
              "Oppdateringa feila. Sjekk nettet, eller om du har endra filer i SNOWMAN-mappa.")
    else:
        print("Denne SNOWMAN-mappa er ikkje kopla til GitHub (git manglar).")
        print("Last ned ny versjon (zip) og pakk ut over den gamle mappa. Terrengmodellar, kalibrering og")
        print("kontrollmålingar ligg i mappa «data» og blir verande.")


def meny():
    print()
    print(f"  SNOWMAN by Alpindata  (v{version()})")
    print("  ─────────────────────────────")
    print("  1  Start (Leica-mottakar)")
    print("  2  Demo – simulert mottakar")
    print("  3  Test over terrengmodellane dine")
    print("  4  Start i fullskjerm (trakkemaskin)")
    print("  5  Hent siste versjon frå GitHub")
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
    ap.add_argument("mode", nargs="?", default="", help="sim | simterreng | simanlegg | stopp | seriellport (COM3, /dev/ttyUSB0)")
    ap.add_argument("--kiosk", action="store_true", help="fullskjerm (trakkemaskin)")
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
    procs.append(subprocess.Popen([py, str(HERE / "snowman_pc.py")] + extra, cwd=HERE))
    PIDS.write_text(json.dumps([p.pid for p in procs]))
    for _ in range(50):  # vent til tenesta svarar
        if port_busy(8765):
            break
        time.sleep(0.1)
    b, win = None, None
    if not a.no_browser:
        b = find_browser()
        if a.hud:
            open_window(b, URL + "/hud")
        win = open_window(b, URL, kiosk=a.kiosk)
    KREQ.unlink(missing_ok=True)
    LAUNCHER.write_text(json.dumps({"pid": os.getpid(), "kiosk": bool(a.kiosk), "browser": bool(b)}))
    print(f"SNOWMAN køyrer på {URL} – trykk Ctrl + C her for å stoppe.")
    if a.kiosk:
        print("Fullskjerm: avslutt med knappen «Avslutt fullskjerm» i SNOWMAN, eller Alt + F4.")
    try:
        while procs[-1].poll() is None:
            time.sleep(0.5)
            if KREQ.exists():  # «Avslutt fullskjerm»: lukk fullskjermvindauget og opne SNOWMAN i vanleg vindauge
                req = KREQ.read_text().strip()
                KREQ.unlink(missing_ok=True)
                if req == "window" and b:
                    close_window(win)
                    time.sleep(0.5)
                    win = open_window(b, URL)
                    print("Fullskjerm avslutta – SNOWMAN er opna i vanleg vindauge.")
    except KeyboardInterrupt:
        pass
    finally:
        LAUNCHER.unlink(missing_ok=True)
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
