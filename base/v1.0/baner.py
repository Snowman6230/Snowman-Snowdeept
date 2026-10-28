# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Satellittbaner (BRDC) for maskinene: Base hentar siste samla banefil frå BKG/IGS og deler henne på /api/v1/baner.

RTK-motoren i SNOWMAN brukar banefila som reserve når straumane manglar baner (sjå pc/v1.6/rtkmotor.py fetch_brdc).
Med Base hentar éin maskin (Base) fila, og alle maskinene får henne frå Base – også over lokalt nett utan internett.
Best er likevel baner i sjølve straumen (1019/1020/1042/1046) – frå basemottakaren eller som tillegg.
"""
import gzip
import re
import time
import urllib.request
from pathlib import Path

from konfig import VERSION

BRDC_URL = "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/{y}/{d:03d}/"


class Baner:
    def __init__(self, folder, cfg, events):
        self.folder = Path(folder) / "baner"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.cfg = cfg
        self.events = events
        self.info = {"fil": None, "henta": None, "feil": ""}

    def latest(self):
        files = sorted(self.folder.glob("*.rnx")) + sorted(self.folder.glob("*[np]"))
        return max(files, key=lambda p: p.stat().st_mtime) if files else None

    def fetch(self):
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc)
        ua = {"User-Agent": f"SNOWMAN Base/{VERSION}"}
        for back in (0, 1):
            day = now - dt.timedelta(days=back)
            url = BRDC_URL.format(y=day.year, d=day.timetuple().tm_yday)
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=20) as r:
                    html = r.read().decode("utf-8", "ignore")
            except Exception as e:
                self.info["feil"] = str(e)[:200]
                continue
            names = re.findall(r'href="([^"]*BRDC00(?:WRD|IGS|DLR)_[SR]_\d{11}_01D_MN\.rnx\.gz)"', html)
            if not names:
                continue
            name = sorted(set(n.split("/")[-1] for n in names))[-1]
            with urllib.request.urlopen(urllib.request.Request(url + name, headers=ua), timeout=60) as r:
                data = gzip.decompress(r.read())
            out = self.folder / name[:-3]
            tmp = out.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(out)
            for old in self.folder.glob("*.rnx"):
                if old != out and time.time() - old.stat().st_mtime > 3 * 86400:
                    old.unlink(missing_ok=True)
            self.info.update(fil=out.name, henta=time.time(), feil="")
            return out
        return None

    def loop(self, stop_ev):
        while not stop_ev.is_set():
            if self.cfg["baner"].get("hent"):
                try:
                    self.fetch()
                except Exception as e:
                    self.info["feil"] = str(e)[:200]
                    self.events.add(f"Henting av banefil feila: {e}", "feil")
            stop_ev.wait(max(10, int(self.cfg["baner"].get("intervall_min", 30))) * 60)
