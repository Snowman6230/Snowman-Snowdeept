# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Oppdatering av SNOWMAN Base – same måte som SNOWMAN snødjupne (pc/v1.6/start_snowman.py).

    Med git (repoet er klona):  git pull --ff-only
    Utan git (zip/Docker/NAS):  last ned zip frå GitHub og skriv berre endra filer i base/-mappa

Mappa data/ (innstillingar, nøklar, logg, anleggspakkar) blir aldri rørt. Etter oppdateringa startar Base på nytt:
under systemd/Docker avsluttar han med kode 3 og blir starta att; elles startar han seg sjølv på nytt.

Sjekk: Base les VERSION i base/v1.0/konfig.py på GitHub éin gong i døgnet og viser «Ny versjon» på statussida.
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

HERE = Path(__file__).resolve().parent            # base/v1.0
REPO = HERE.parent.parent
ZIP_URL = "https://github.com/Snowman6230/Snowman-Snowdeept/archive/refs/heads/main.zip"
RAW_URL = "https://raw.githubusercontent.com/Snowman6230/Snowman-Snowdeept/main/base/{ver}/konfig.py"
SKIP = {"data", ".venv", "__pycache__"}


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def latest_version(timeout=15):
    """VERSION i den nyaste base-mappa på GitHub (eller None)."""
    req = urllib.request.Request(RAW_URL.format(ver=HERE.name), headers={"User-Agent": f"SNOWMAN Base/{VERSION}"})
    with nett.urlopen(req, timeout=timeout) as r:
        m = re.search(r'^VERSION = "([^"]+)"', r.read().decode("utf-8", "ignore"), re.M)
    return m.group(1) if m else None


def apply(log=print):
    """Hent siste versjon. Returnerer (endra, tekst)."""
    old = VERSION
    out = []
    say = lambda t: (out.append(t), log(t))
    if (REPO / ".git").exists() and shutil.which("git"):
        say("Hentar siste versjon frå GitHub (git) …")
        r = subprocess.run(["git", "-C", str(REPO), "pull", "--ff-only"], capture_output=True, text=True)
        say((r.stdout or "").strip() or (r.stderr or "").strip())
        if r.returncode != 0:
            say("Oppdateringa feila. Sjekk nettet, eller om nokon har endra filer i SNOWMAN-mappa.")
            return False, "\n".join(out)
    else:
        say("Lastar ned siste versjon frå GitHub …")
        try:
            data = nett.urlopen(urllib.request.Request(ZIP_URL, headers={"User-Agent": "SNOWMAN Base"}),
                                timeout=120).read()
        except Exception as e:
            say(f"Fekk ikkje lasta ned: {nett.forklar(e)}")
            return False, "\n".join(out)
        n = 0
        basedir = HERE.parent                       # base/
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for m in z.infolist():
                parts = m.filename.split("/")
                if m.is_dir() or len(parts) < 3 or parts[1] != "base":
                    continue
                rel = parts[2:]
                if SKIP & set(rel):
                    continue
                dst = basedir.joinpath(*rel)
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
    new = _read_version()
    changed = new != old
    say(f"Ferdig: v{old} → v{new}. Base startar på nytt." if changed else f"Du har siste versjon (v{new}).")
    return changed, "\n".join(out)


def _read_version():
    m = re.search(r'^VERSION = "([^"]+)"', (HERE / "konfig.py").read_text("utf-8"), re.M)
    return m.group(1) if m else VERSION


class Updates:
    """Dagleg sjekk etter ny versjon (og valfri automatisk oppdatering om natta)."""

    def __init__(self, cfg, events, restart):
        self.cfg = cfg
        self.events = events
        self.restart = restart
        self.info = {"versjon": VERSION, "ny": None, "sjekka": None, "feil": ""}
        self.lock = threading.Lock()

    def check(self):
        try:
            v = latest_version()
            self.info.update(sjekka=time.time(), feil="",
                             ny=v if v and vtuple(v) > vtuple(VERSION) else None)
        except Exception as e:
            self.info.update(sjekka=time.time(), feil=nett.forklar(e))
        return self.info

    def run_now(self):
        with self.lock:
            changed, text = apply(log=lambda t: None)
            self.events.add("Oppdatering: " + text.splitlines()[-1] if text else "Oppdatering køyrd", "info")
            if changed:
                threading.Thread(target=lambda: (time.sleep(1.0), self.restart()), daemon=True).start()
            return changed, text

    def loop(self, stop_ev):
        stop_ev.wait(60)
        while not stop_ev.is_set():
            if self.cfg["oppdatering"].get("sjekk", True):
                self.check()
                hour = time.localtime().tm_hour
                if self.info.get("ny") and self.cfg["oppdatering"].get("auto") and 3 <= hour < 5:
                    self.events.add(f"Automatisk oppdatering til {self.info['ny']}", "info")
                    self.run_now()
            stop_ev.wait(3600 if self.cfg["oppdatering"].get("auto") else 6 * 3600)
