# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Feltlogg: lagrar alt mottakaren sender, og kva SNOWMAN rekna ut, til filer – for prøving i trakkemaskina og feilsøking.

Kvar logg har to filer i data/logg/:
  <namn>.nmea  alle linjer frå mottakaren (NMEA), med PC-tid framfor:  2026-10-05T12:00:00.123 $GNGGA,...
               og hendingar (NTRIP tilkopla/fråkopla, feil) som linjer med # framfor
  <namn>.csv   éi linje per posisjon: tid, fix, satellittar, HDOP, breidd, lengd, høgd, geoidehøgd, terrenghøgd,
               terrenglag, utrekna snødjupne (rå og vist), status, fart, kurs, antennehøgd, høgdeoffset, helling
  <namn>.json  samandrag (v1.6.51): start/slutt, linjer, posisjonar, hendingar, feil og kor stor del av tida det var RTK FIX
Loggane kan lastast ned frå Innst. › System og sendast til Alpindata. Dei inneheld ingen passord.
Gamle loggar blir sletta når mappa blir større enn MAX_MB. Nesten tomme loggar (under TINY_BYTES, t.d. oppstart
utan mottakar) blir ikkje viste i lista og blir sletta etter TINY_DAYS dagar.
"""
import csv, io, json, threading, time
from pathlib import Path

MAX_MB = 500
TINY_BYTES = 10_000
TINY_DAYS = 7
COLS = ["tid", "fix", "satellittar", "hdop", "breidd", "lengd", "hogd", "geoidehogd", "terrenghogd", "terrenglag",
        "snodjupne_raa", "snodjupne", "status", "fart_ms", "kurs", "antZ", "zOff", "simulert",
        "helling_kjelde", "helling_grader", "stamp", "krenging", "malepunkt_flytt_m"]


class FeltLogg:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.lock = threading.Lock()
        self.name = None
        self.nmea = None
        self.csv = None
        self.lines = 0
        self.rows = 0
        self.started = 0
        self.events = 0
        self.errors = 0
        self.fixes = {}
        self.last_meta = 0

    @staticmethod
    def _ts():
        t = time.time()
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)) + f".{int(t * 1000) % 1000:03d}"

    def active(self):
        return self.name is not None

    def start(self, note=""):
        with self.lock:
            if self.name:
                return self.name
            self.dir.mkdir(parents=True, exist_ok=True)
            self._trim()
            self.name = time.strftime("snowman-%Y%m%d-%H%M%S")
            self.nmea = open(self.dir / (self.name + ".nmea"), "a", encoding="utf-8", errors="replace", buffering=1)
            self.csv = open(self.dir / (self.name + ".csv"), "a", encoding="utf-8", newline="", buffering=1)
            csv.writer(self.csv).writerow(COLS)
            self.lines = self.rows = self.events = self.errors = 0
            self.fixes = {}
            self.started = time.time()
            self.nmea.write(f"# {self._ts()} Logg starta. {note}\n")
            return self.name

    def stop(self):
        with self.lock:
            if not self.name:
                return
            try:
                self.nmea.write(f"# {self._ts()} Logg stoppa. {self.lines} linjer, {self.rows} posisjonar.\n")
                self._meta(final=True)
                self.nmea.close()
                self.csv.close()
            except Exception:
                pass
            self.name = self.nmea = self.csv = None

    def raw(self, line):
        """Ei linje frå mottakaren (alle typar NMEA, ikkje berre GGA)."""
        if not self.name:
            return
        with self.lock:
            if self.nmea:
                self.nmea.write(f"{self._ts()} {line}\n")
                self.lines += 1

    def event(self, text, err=False):
        """Hending i loggen (# framfor). err=True: feil (GNSS stoppa, NTRIP-feil, mottakarfeil …) – blir talde og
        merkte «FEIL:» så dei er lette å finne."""
        if not self.name:
            return
        with self.lock:
            if self.nmea:
                self.nmea.write(f"# {self._ts()} {'FEIL: ' if err else ''}{text}\n")
                self.events += 1
                if err:
                    self.errors += 1
                    self._meta()

    def _meta(self, final=False):
        """Samandrag ved sida av loggen (lite, blir lese av lista i Innst. › System). Kallast med låsen halden."""
        try:
            n = sum(self.fixes.values()) or 1
            m = {"start": int(self.started * 1000), "end": int(time.time() * 1000), "final": final,
                 "lines": self.lines, "rows": self.rows, "events": self.events, "errors": self.errors,
                 "fix": {k: round(100 * v / n, 1) for k, v in sorted(self.fixes.items(), key=lambda x: -x[1])}}
            (self.dir / (self.name + ".json")).write_text(json.dumps(m), "utf-8")
            self.last_meta = time.time()
        except Exception:
            pass

    def row(self, st, cfg):
        """Éin posisjon med det SNOWMAN rekna ut."""
        if not self.name:
            return
        det = st.get("depth_detail") or {}
        ter = st.get("terrain") or {}
        r = [self._ts(), st.get("fix"), st.get("satellites"), st.get("hdop"), st.get("lat"), st.get("lon"), st.get("altitude"),
             st.get("geoid_sep"), det.get("terrain"), ter.get("name", ""), det.get("raw"), st.get("depth"), st.get("depth_status"),
             st.get("speed"), st.get("course"), cfg.get("antZ"), cfg.get("zOff"), int(bool(st.get("simulated")))]
        tl = st.get("tilt") or {}
        r += [tl.get("src"), tl.get("total"), tl.get("pitch"), tl.get("roll"), tl.get("shift")]
        with self.lock:
            if self.csv:
                csv.writer(self.csv).writerow(r)
                self.rows += 1
                f = st.get("fix") or "?"
                self.fixes[f] = self.fixes.get(f, 0) + 1
                if time.time() - self.last_meta > 60:
                    self._meta()

    def status(self):
        size = sum(f.stat().st_size for f in self.dir.glob("snowman-*")) if self.dir.exists() else 0
        return {"active": self.active(), "name": self.name, "lines": self.lines, "rows": self.rows,
                "seconds": int(time.time() - self.started) if self.active() else 0, "totalMB": round(size / 1e6, 1)}

    def listing(self):
        """Alle loggar, nyaste først, med samandrag (om det finst) og «tiny» for nesten tomme loggar."""
        out = {}
        if self.dir.exists():
            for f in sorted(self.dir.glob("snowman-*"), reverse=True):
                g = out.setdefault(f.stem, {"name": f.stem, "files": [], "bytes": 0})
                if f.suffix == ".json":
                    try:
                        g["meta"] = json.loads(f.read_text("utf-8"))
                    except Exception:
                        pass
                    continue
                g["files"].append(f.name)
                g["bytes"] += f.stat().st_size
        for g in out.values():
            # nesten tom: liten, ikkje i gang, og utan feil (loggar med feil blir alltid viste)
            g["tiny"] = g["bytes"] < TINY_BYTES and g["name"] != self.name and not (g.get("meta") or {}).get("errors")
        return list(out.values())

    def events_of(self, name, limit=400):
        """Hendingane (# -linjene) i ein logg – til visinga i Innst. › System. Dei siste «limit»."""
        p = self.path(name + ".nmea")
        ev = []
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("# "):
                    ev.append(line[2:].rstrip())
                    if len(ev) > limit * 2:
                        ev = ev[-limit:]
        return ev[-limit:]

    def zip_day(self, day):
        """Alle loggane frå éin dag (ÅÅÅÅMMDD) i éi zip-fil."""
        import zipfile
        if not (len(day) == 8 and day.isdigit()):
            raise ValueError("Ugyldig dato")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(self.dir.glob(f"snowman-{day}-*")):
                if p.suffix in (".nmea", ".csv", ".json"):
                    z.write(p, p.name)
        return buf.getvalue()

    def path(self, filename):
        p = (self.dir / filename).resolve()
        if p.parent != self.dir.resolve() or not p.name.startswith("snowman-") or p.suffix not in (".nmea", ".csv", ".json"):
            raise ValueError("Ukjend loggfil")
        return p

    def zip(self, name):
        """Begge filene i ein logg som zip (for nedlasting)."""
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for ext in (".nmea", ".csv", ".json"):
                p = self.path(name + ext)
                if p.exists():
                    z.write(p, p.name)
        return buf.getvalue()

    def delete_all(self):
        with self.lock:
            for f in self.dir.glob("snowman-*"):
                if self.name and f.stem == self.name:
                    continue  # ikkje slett loggen som er i gang
                f.unlink(missing_ok=True)

    def _trim(self):
        # nesten tomme loggar (oppstart utan mottakar o.l.) eldre enn TINY_DAYS blir sletta
        groups = {}
        for f in self.dir.glob("snowman-*"):
            groups.setdefault(f.stem, []).append(f)
        now = time.time()
        for stem, fs in groups.items():
            data = [f for f in fs if f.suffix != ".json"]
            meta = next((f for f in fs if f.suffix == ".json"), None)
            try:
                errors = json.loads(meta.read_text("utf-8")).get("errors", 0) if meta else 0
            except Exception:
                errors = 0
            if errors == 0 and sum(f.stat().st_size for f in data) < TINY_BYTES and all(now - f.stat().st_mtime > TINY_DAYS * 86400 for f in fs):
                for f in fs:
                    f.unlink(missing_ok=True)
        files = sorted(self.dir.glob("snowman-*"), key=lambda f: f.stat().st_mtime)
        total = sum(f.stat().st_size for f in files)
        while files and total > MAX_MB * 1e6:
            f = files.pop(0)
            total -= f.stat().st_size
            f.unlink(missing_ok=True)
