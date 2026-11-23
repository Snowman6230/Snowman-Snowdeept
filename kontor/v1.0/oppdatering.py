# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Oppdatering av SNOWMAN Office – same måte som SNOWMAN Snowdeep (pc/v1.6/start_snowman.py).

    Med git (repoet er klona):  git pull --ff-only
    Utan git (zip):             last ned zip frå GitHub og skriv berre endra filer i kontor/ og pc/ (kart og anlegg)

Mappa data/ (innstillingar, logg, anleggspakkar) blir aldri rørt. Etter oppdateringa startar Office på nytt:
som teneste avsluttar han med kode 3 og blir starta att; elles startar han seg sjølv på nytt. Korreksjonane
(SNOWMAN Base) blir ikkje påverka.

Sjekk (frå 1.1.1): Office les BÅDE sin eigen versjon (kontor/v1.0/konfig.py) og versjonen av kartet – SNOWMAN
snødjupne i pc/ (snowman_pc.py) – på GitHub ved oppstart og kvar 3. time, og viser eit varsel øvst på kontorsida og i
kartet med knappen «Oppdater no». Ein ny versjon av snødjupne treng difor ingen ny versjon av Office: er berre kartet
nytt, blir berre kartet starta på nytt (kontorsida og maskinporten held fram).
NB: når repoet blir privat (VEGEN-VIDARE kap. 17), må sjekken og nedlastinga få ein tilgangsnøkkel.
"""
import io
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from konfig import VERSION
import nett

HERE = Path(__file__).resolve().parent            # kontor/v1.0
REPO = HERE.parent.parent
ZIP_URL = "https://github.com/Snowman6230/Snowman-Snowdeept/archive/refs/heads/main.zip"
RAW_URL = "https://raw.githubusercontent.com/Snowman6230/Snowman-Snowdeept/main/kontor/{ver}/konfig.py"
PC_RAW_URL = "https://raw.githubusercontent.com/Snowman6230/Snowman-Snowdeept/main/pc/{ver}/snowman_pc.py"
PC_LIST_URL = "https://api.github.com/repos/Snowman6230/Snowman-Snowdeept/contents/pc?ref=main"
PC = REPO / "pc"
SKIP = {"data", ".venv", "__pycache__"}


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def _dir_key(name):
    return tuple(int(x) for x in name[1:].split(".") if x.isdigit())


def pc_mappe():
    """Nyaste SNOWMAN Snowdeep ved sida av Office (pc/v*, med snowman_pc.py)."""
    dirs = sorted((d for d in PC.glob("v*") if (d / "snowman_pc.py").exists()), key=lambda d: _dir_key(d.name))
    return dirs[-1] if dirs else None


def _pc_ver_text(text):
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.M)
    return m.group(1) if m else None


def kart_versjon():
    """Installert versjon av kartet (SNOWMAN Snowdeep i pc/), eller None."""
    d = pc_mappe()
    try:
        return _pc_ver_text((d / "snowman_pc.py").read_text("utf-8", "ignore")) if d else None
    except OSError:
        return None


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": f"SNOWMAN Office/{VERSION}"})
    with nett.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def latest_version(timeout=15):
    """VERSION i kontor-mappa på GitHub (eller None)."""
    m = re.search(r'^VERSION = "([^"]+)"', _get(RAW_URL.format(ver=HERE.name), timeout), re.M)
    return m.group(1) if m else None


def latest_kart(timeout=15):
    """(mappe, versjon) for nyaste SNOWMAN Snowdeep på GitHub. Ny versjonsmappe (t.d. v1.7) blir funnen via lista
    over pc/; går ikkje det, blir den lokale mappa brukt."""
    import json
    mappe = pc_mappe().name if pc_mappe() else "v1.6"
    try:
        namn = [x["name"] for x in json.loads(_get(PC_LIST_URL, timeout))
                if x.get("type") == "dir" and re.fullmatch(r"v\d+(\.\d+)*", x.get("name", ""))]
        if namn:
            beste = max(namn, key=_dir_key)
            if _dir_key(beste) >= _dir_key(mappe):
                mappe = beste
    except Exception:
        pass
    return mappe, _pc_ver_text(_get(PC_RAW_URL.format(ver=mappe), timeout))


def _pc_apps(names):
    """Versjonsmapper i pc/ som kan køyrast (har snowman_pc.py) – ikkje dei gamle prototypane."""
    return {n.split("/")[2] for n in names if n.count("/") == 3 and n.endswith("/snowman_pc.py") and n.split("/")[1] == "pc"}


def installer_kart_pakkar(log=print, d=None):
    """pip-pakkane kartet treng (pc/<nyaste>/requirements.txt). Berre når fila er endra sidan sist."""
    d = d or pc_mappe()
    req = d / "requirements.txt" if d else None
    if not req or not req.exists():
        return True
    merke = HERE / "data" / "kart-pakkar.txt"
    import hashlib
    sig = f"{d.name}:{hashlib.sha256(req.read_bytes()).hexdigest()}"
    try:
        if merke.read_text("utf-8") == sig:
            return True
    except OSError:
        pass
    log(f"Installerer pakkane kartet treng ({d.name}/requirements.txt) …")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(req)])
    if r.returncode == 0:
        merke.parent.mkdir(parents=True, exist_ok=True)
        merke.write_text(sig, "utf-8")
    return r.returncode == 0


def apply(log=print):
    """Hent siste versjon av Office og kartet. Returnerer (kontor_endra, tekst, kart_endra)."""
    old, old_kart = VERSION, kart_versjon()
    out = []
    say = lambda t: (out.append(t), log(t))
    if (REPO / ".git").exists() and shutil.which("git"):
        say("Hentar siste versjon frå GitHub (git) …")
        r = subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only"], capture_output=True, text=True)
        say((r.stdout or "").strip() or (r.stderr or "").strip())
        if r.returncode != 0:
            say("Oppdateringa feila. Sjekk nettet, eller om nokon har endra filer i SNOWMAN-mappa.")
            return False, "\n".join(out), False
    else:
        say("Lastar ned siste versjon frå GitHub …")
        try:
            data = nett.urlopen(urllib.request.Request(ZIP_URL, headers={"User-Agent": "SNOWMAN Office"}),
                                timeout=180).read()
        except Exception as e:
            say(f"Fekk ikkje lasta ned: {nett.forklar(e)}")
            return False, "\n".join(out), False
        n = 0
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            apps = _pc_apps(z.namelist())
            for m in z.infolist():
                parts = m.filename.split("/")
                # kontor/ (Office) og pc/<versjon> (SNOWMAN Snowdeep – kart og anlegg i kontormodus)
                if m.is_dir() or len(parts) < 3 or parts[1] not in ("kontor", "pc"):
                    continue
                rel = parts[2:]
                if parts[1] == "pc" and (len(rel) < 2 or rel[0] not in apps):
                    continue
                if SKIP & set(rel):
                    continue
                dst = REPO.joinpath(parts[1], *rel)
                new = z.read(m)
                if dst.exists() and dst.read_bytes() == new:
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                tmp = dst.with_suffix(dst.suffix + ".ny")
                tmp.write_bytes(new)
                tmp.replace(dst)
                n += 1
        say(f"{n} filer oppdaterte.")
    req = HERE / "requirements.txt"
    if req.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(req)])
    installer_kart_pakkar(say)
    new, new_kart = _read_version(), kart_versjon()
    changed, kart_changed = new != old, new_kart != old_kart
    if changed:
        say(f"Ferdig: Office v{old} → v{new}" + (f", kart v{old_kart} → v{new_kart}" if kart_changed else "")
            + ". Office startar på nytt.")
    elif kart_changed:
        say(f"Ferdig: kartet (SNOWMAN Snowdeep) v{old_kart} → v{new_kart}. Kartet startar på nytt – kontorsida held fram.")
    else:
        say(f"Du har siste versjon (Office v{new}, kart v{new_kart}).")
    return changed, "\n".join(out), kart_changed


def _read_version():
    m = re.search(r'^VERSION = "([^"]+)"', (HERE / "konfig.py").read_text("utf-8"), re.M)
    return m.group(1) if m else VERSION


class Updates:
    """Dagleg sjekk etter ny versjon (og valfri automatisk oppdatering om natta)."""

    def __init__(self, cfg, events, restart, restart_kart=None):
        self.cfg = cfg
        self.events = events
        self.restart = restart
        self.restart_kart = restart_kart
        # ny = ny Office-versjon (eller None), ny_kart = ny versjon av kartet (SNOWMAN Snowdeep), tilgjengeleg = ein av dei
        self.info = {"versjon": VERSION, "kart": kart_versjon(), "ny": None, "ny_kart": None, "tilgjengeleg": False,
                     "sjekka": None, "feil": "", "koyrer": False}
        self.lock = threading.Lock()
        self._varsla = None

    def check(self):
        self.info["kart"] = kart_versjon()
        try:
            v = latest_version()
            _, kv = latest_kart()
            self.info.update(sjekka=time.time(), feil="",
                             ny=v if v and vtuple(v) > vtuple(VERSION) else None,
                             ny_kart=kv if kv and vtuple(kv) > vtuple(self.info["kart"] or "0") else None)
        except Exception as e:
            self.info.update(sjekka=time.time(), feil=nett.forklar(e))
        self.info["tilgjengeleg"] = bool(self.info["ny"] or self.info["ny_kart"])
        nytt = (self.info["ny"], self.info["ny_kart"])
        if self.info["tilgjengeleg"] and nytt != self._varsla:
            self._varsla = nytt
            self.events.add("Ny versjon tilgjengeleg: " + tekst(self.info) + " – trykk «Oppdater no» på kontorsida", "info")
        return self.info

    def run_now(self):
        with self.lock:
            self.info["koyrer"] = True
            try:
                changed, text, kart_changed = apply(log=lambda t: None)
            finally:
                self.info["koyrer"] = False
            self.events.add("Oppdatering: " + text.splitlines()[-1] if text else "Oppdatering køyrd", "info")
            self.info.update(kart=kart_versjon(), ny_kart=None if kart_changed else self.info["ny_kart"])
            if changed:
                threading.Thread(target=lambda: (time.sleep(1.0), self.restart()), daemon=True).start()
            elif kart_changed:
                self.info["tilgjengeleg"] = bool(self.info["ny"])
                if self.restart_kart:
                    threading.Thread(target=lambda: (time.sleep(1.0), self.restart_kart()), daemon=True).start()
            return changed or kart_changed, text

    def loop(self, stop_ev):
        stop_ev.wait(20)
        while not stop_ev.is_set():
            if self.cfg["oppdatering"].get("sjekk", True):
                self.check()
                hour = time.localtime().tm_hour
                if self.info.get("tilgjengeleg") and self.cfg["oppdatering"].get("auto") and 3 <= hour < 5:
                    self.events.add(f"Automatisk oppdatering ({tekst(self.info)})", "info")
                    self.run_now()
            stop_ev.wait(3600 if self.cfg["oppdatering"].get("auto") else 3 * 3600)


def tekst(info):
    """«Office 1.1.2 og kart 1.6.140» – kva som er nytt."""
    t = []
    if info.get("ny"):
        t.append(f"SNOWMAN Office {info['ny']}")
    if info.get("ny_kart"):
        t.append(f"kart (SNOWMAN Snowdeep) {info['ny_kart']}")
    return " og ".join(t)
