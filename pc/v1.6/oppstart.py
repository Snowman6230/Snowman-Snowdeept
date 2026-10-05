# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Autostart og maskinoppsett (Windows og Linux) – brukt av installasjonen og av Innst. › System.

Autostart blir lagt inn for brukaren som er logga inn, utan administratorrettar:
- Windows: snarveg «SNOWMAN» i Oppstart-mappa. Startar utan svart vindauge (pythonw).
- Linux:   ~/.config/autostart/snowman.desktop (GNOME, KDE, XFCE …) og ei merkt linje i Hyprland-oppsettet
           (Omarchy) dersom det finst.
Oppstarten brukar `start_snowman.py --auto`: kiosk eller vanleg vindauge etter Innst. › System.
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WIN = os.name == "nt"
SYSTEM = HERE / "data" / "system.json"
MARK = "# SNOWMAN autostart"


def system_cfg():
    try:
        return json.loads(SYSTEM.read_text("utf-8"))
    except Exception:
        return {}


def save_system(**kw):
    cur = system_cfg()
    cur.update(kw)
    SYSTEM.parent.mkdir(parents=True, exist_ok=True)
    tmp = SYSTEM.with_name(SYSTEM.name + ".tmp")
    tmp.write_text(json.dumps(cur, indent=1), "utf-8")
    os.replace(tmp, SYSTEM)
    return cur


# ---------------- Windows ----------------
def _win_startup():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup" / "SNOWMAN.lnk"


def _win_python():
    """pythonw.exe (utan konsollvindauge) i SNOWMAN sitt eige Python-miljø."""
    for c in (HERE / ".venv/Scripts/pythonw.exe", Path(sys.executable).with_name("pythonw.exe")):
        if c.exists():
            return c
    return Path(sys.executable)


def _ps(script):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True)


# ---------------- Linux ----------------
def _linux_cmd():
    return f'sh "{HERE / "start-snowman.sh"}" --auto'


def _xdg_file():
    return Path.home() / ".config/autostart/snowman.desktop"


def _hypr_file():
    d = Path.home() / ".config/hypr"
    if not d.is_dir():
        return None
    for name in ("autostart.conf", "hyprland.conf"):  # Omarchy har autostart.conf
        if (d / name).exists():
            return d / name
    return None


def _hypr_lines(f):
    try:
        return f.read_text("utf-8").splitlines()
    except Exception:
        return []


# ---------------- felles ----------------
def autostart_status():
    if WIN:
        return _win_startup().exists()
    if _xdg_file().exists():
        return True
    h = _hypr_file()
    return bool(h and any(MARK in l for l in _hypr_lines(h)))


def autostart_set(on):
    """Slå autostart av/på. Returnerer (ok, melding)."""
    if WIN:
        lnk = _win_startup()
        if not on:
            lnk.unlink(missing_ok=True)
            return True, "Autostart er slått av."
        lnk.parent.mkdir(parents=True, exist_ok=True)
        py, script = _win_python(), HERE / "start_snowman.py"
        r = _ps(
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath='%s'; $s.Arguments='\"%s\" --auto'; "
            "$s.WorkingDirectory='%s'; $s.Description='SNOWMAN by Alpindata'; $s.IconLocation='%s'; $s.Save()" % (lnk, py, script, HERE, HERE / "ikon" / "snowman.ico")
        )
        return (lnk.exists(), "SNOWMAN startar no automatisk når du loggar inn." if lnk.exists() else "Kunne ikkje lage autostart: " + r.stderr.strip())
    # Linux
    xdg, hypr = _xdg_file(), _hypr_file()
    if hypr:  # fjern gammal linje først
        lines = [l for l in _hypr_lines(hypr) if MARK not in l]
        if on:
            lines.append(f"exec-once = {_linux_cmd()}  {MARK}")
        hypr.write_text("\n".join(lines) + "\n", "utf-8")
    if on and not hypr:
        xdg.parent.mkdir(parents=True, exist_ok=True)
        xdg.write_text(
            "[Desktop Entry]\nType=Application\nName=SNOWMAN\nComment=SNOWMAN by Alpindata – autostart\n"
            f"Exec={_linux_cmd()}\nIcon={HERE / 'ikon' / 'snowman-256.png'}\nX-GNOME-Autostart-enabled=true\nTerminal=false\n", "utf-8")
    elif not on:
        xdg.unlink(missing_ok=True)
    return True, ("SNOWMAN startar no automatisk når du loggar inn." if on else "Autostart er slått av.")


def no_sleep():
    """Maskin-PC: aldri dvale eller svart skjerm på straum (Windows). På Linux held SNOWMAN skjermen vaken sjølv i kiosk."""
    if not WIN:
        return "Skjermen blir halden vaken av SNOWMAN i kioskmodus."
    for a in ("standby-timeout-ac", "monitor-timeout-ac", "hibernate-timeout-ac"):
        subprocess.run(["powercfg", "/change", a, "0"], capture_output=True)
    return "Dvale og skjermsparar er slått av når PC-en går på straum."


def install(kind):
    """Val i installasjonen: «maskin» (kiosk + autostart + ingen dvale) eller «kontor» (vanleg, ingen autostart)."""
    if kind == "maskin":
        save_system(kiosk=True)
        ok, msg = autostart_set(True)
        print("  Maskin-PC: SNOWMAN startar i kioskmodus når PC-en startar.")
        print("  " + msg)
        print("  " + no_sleep())
        print("  Tips: slå på automatisk innlogging i Windows/Linux, så startar alt utan at nokon gjer noko.")
    else:
        save_system(kiosk=False)
        autostart_set(False)
        print("  Kontor-PC: start SNOWMAN med snarvegen eller menyen. Kan endrast under Innst. › System.")
