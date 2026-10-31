# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Mountpoint: éin korreksjonsstraum ut til maskinene, med reserve, tillegg og rådatalogg.

    kjelder  [eigen base, reserve 1, reserve 2 …]  – første kjelde med ferske data blir sendt ut
    tillegg  [t.d. satellittbaner frå ein annan caster] – berre utvalde meldingstypar, alltid med
                                                      → ring med rammer → kvar klient (maskin) les i sitt tempo

Byte av kjelde gir ny baseposisjon (1005/1006) i straumen; RTK-motoren i SNOWMAN startar då på nytt (kort FLOAT).
Difor byter Base ikkje fram og tilbake: ei kjelde med høgare prioritet blir teken i bruk att først når ho har sendt
utan opphald i «tilbake_etter_s» sekund (standard 60). Fell aktiv kjelde ut, blir neste teken i bruk med éin gong.
"""
import collections
import math
import os
import threading
import time
from pathlib import Path

import kjelder
from rtcm import EPHEMERIS, Stats, geo_to_ecef


class Events:
    """Hendingar til statussida og loggfila (data/hendingar.log)."""

    def __init__(self, folder=None, n=300):
        self.items = collections.deque(maxlen=n)
        self.lock = threading.Lock()
        self.file = Path(folder) / "hendingar.log" if folder else None

    MAKS_BYTE = 5_000_000            # hendingar.log blir rotert til hendingar.log.1 ved 5 MB

    def add(self, text, level="info"):
        e = {"t": time.time(), "tekst": text, "niva": level}
        with self.lock:
            self.items.append(e)
            if self.file:
                try:
                    self._n = getattr(self, "_n", 0) + 1
                    if self._n % 200 == 1 and self.file.exists() and self.file.stat().st_size > self.MAKS_BYTE:
                        os.replace(self.file, self.file.with_suffix(".log.1"))
                    with open(self.file, "a", encoding="utf-8") as f:
                        f.write(time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime(e["t"])) + f"[{level}] {text}\n")
                except OSError:
                    pass

    def latest(self, n=100):
        with self.lock:
            return list(self.items)[-n:][::-1]


class RawLog:
    """Rådata frå kjeldene, éi fil per kjelde per time: data/radata/<mountpoint>/<dato>/<kjelde>_<dato>_<time>.raw.
    Alt mottakaren sender blir lagra (også u-blox/Unicore-data) – grunnlag for PPP-innmåling av basen og feilsøking."""

    def __init__(self, folder, days=30, max_mb=5000):
        self.folder = Path(folder) / "radata"
        self.days, self.max_mb = days, max_mb
        self.lock = threading.Lock()
        self.files = {}
        self.last_clean = 0.0
        self.closed = False

    def close(self):
        with self.lock:
            self.closed = True
            for _, f in self.files.values():
                f.close()
            self.files.clear()

    def write(self, mount, source, chunk):
        hour = time.strftime("%Y%m%d_%H", time.gmtime())
        key = (mount, source)
        with self.lock:
            if self.closed:
                return
            cur = self.files.get(key)
            if not cur or cur[0] != hour:
                if cur:
                    cur[1].close()
                d = self.folder / safe(mount) / hour[:8]
                d.mkdir(parents=True, exist_ok=True)
                f = open(d / f"{safe(source)}_{hour}.raw", "ab")
                self.files[key] = cur = (hour, f)
            cur[1].write(chunk)
            cur[1].flush()
        if time.time() - self.last_clean > 3600:
            self.last_clean = time.time()
            threading.Thread(target=self.clean, daemon=True).start()

    def clean(self):
        """Slett filer eldre enn grensa, og dei eldste når samla storleik er over grensa."""
        with self.lock:
            open_hours = {h for h, _ in self.files.values()}
        files = []
        for p in self.folder.rglob("*.raw"):
            try:
                files.append((p.stat().st_mtime, p.stat().st_size, p))
            except OSError:
                pass
        files.sort()
        cut = time.time() - self.days * 86400
        total = sum(x[1] for x in files)
        for mtime, size, p in files:
            open_now = any(p.name.endswith(h + ".raw") for h in open_hours)
            if open_now:
                continue
            if mtime < cut or total > self.max_mb * 1e6:
                total -= size
                try:
                    p.unlink()
                except OSError:
                    pass
        for d in sorted(self.folder.rglob("*"), reverse=True):
            try:
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    def usage(self):
        files = list(self.folder.rglob("*.raw"))
        return {"filer": len(files), "mb": round(sum(p.stat().st_size for p in files) / 1e6, 1)}


def safe(x):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in str(x))[:64] or "x"


class Mountpoint:
    def __init__(self, cfg, events, rawlog=None):
        self.cfg = cfg
        self.name = cfg["namn"]
        self.events = events
        self.sources = []
        self.extras = []
        for i, sc in enumerate(cfg.get("kjelder", [])):
            sc.setdefault("namn", f"{sc.get('type')}{i + 1}")
            self.sources.append(kjelder.make(sc, self, events, rawlog if sc.get("logg", True) else None))
        for i, sc in enumerate(cfg.get("tillegg", [])):
            sc.setdefault("namn", f"tillegg{i + 1}")
            self.extras.append(kjelder.make(sc, self, events, None, role="tillegg"))
        self.active = None
        self.cond = threading.Condition()
        self.ring = collections.deque(maxlen=4000)
        self.seq = 0
        self.out = Stats()            # det som faktisk går ut til maskinene
        self.switch_after = float(cfg.get("byte_etter_s", 10))
        self.back_after = float(cfg.get("tilbake_etter_s", 60))
        self.clients = {}             # id → Client (sett av casteren)
        self.lock = threading.Lock()
        self.day = {"dato": time.strftime("%Y-%m-%d"), "ok": 0, "tot": 0, "bytte": 0}   # oppetid og byte i dag
        self.closed = False           # sett når mountpointet blir endra eller sletta frå kontorsida

    def start(self):
        for s in self.sources + self.extras:
            s.start()

    def stop(self):
        self.closed = True
        with self.cond:
            self.cond.notify_all()        # klientane (maskinene) blir kopla frå og koplar til det nye oppsettet
        for s in self.sources + self.extras:
            s.stop()

    def upload_source(self):
        return next((s for s in self.sources if s.kind == "opplasting"), None)

    # ---------- inn ----------
    def _fresh(self, now):
        return [s for s in self.sources if s.age(now) is not None and s.age(now) < self.switch_after]

    def _choose(self, now):
        """Kva kjelde som skal sendast ut.
        - Aktiv kjelde blir verande så lenge ho sender, med mindre ei kjelde med høgare prioritet har sendt utan
          opphald i minst «tilbake_etter_s» sekund (ventetid – hindrar byte fram og tilbake mellom to basar).
        - Har aktiv kjelde stoppa, blir den første kjelda (i prioritert rekkjefølgje) som sender, teken i bruk."""
        fresh = self._fresh(now)
        if not fresh:
            return None
        cur = self.active
        if cur in fresh:
            ci = self.sources.index(cur)
            for s in fresh:
                if self.sources.index(s) >= ci:
                    break
                if now - getattr(s, "stable_since", now) >= self.back_after:
                    return s
            return cur
        return fresh[0]

    def _set_active(self, best):
        """Byt aktiv kjelde – alltid logga og talt (kallast med self.lock)."""
        old = self.active
        if best is old:
            return
        self.active = best
        if best is None:
            self.events.add(f"{self.name}: ingen kjelde sender korreksjonar", "feil")
        elif old is None:
            self.events.add(f"{self.name}: sender frå {best.name}", "ok")
        else:
            self.day["bytte"] += 1
            better = self.sources.index(best) < self.sources.index(old)
            self.events.add(f"{self.name}: bytte frå {old.name} til {best.name}"
                            + (f" (stabil i {self.back_after:.0f} s)" if better else " (ingen data frå "
                               f"{old.name} på {self.switch_after:.0f} s)"), "ok" if better else "feil")

    def feed(self, src, frames):
        now = time.time()
        if src.role == "tillegg":
            types = set(src.cfg.get("typar") or EPHEMERIS)
            frames = [f for f in frames if ((f[3] << 4) | (f[4] >> 4)) in types]
            if frames:
                self._publish(frames, now)
            return
        with self.lock:
            last = getattr(src, "last_frame", None)
            if last is None or now - last > self.switch_after:
                src.stable_since = now                # opphald → stabil tid tel frå no
            src.last_frame = now
            self._set_active(self._choose(now))
            if src is not self.active:
                return
        self._publish(frames, now)

    def tick(self):
        """Kallast kvart sekund: oppdagar at aktiv kjelde har stoppa sjølv om ingen andre sender."""
        now = time.time()
        today = time.strftime("%Y-%m-%d")
        if self.day["dato"] != today:
            self.day = {"dato": today, "ok": 0, "tot": 0, "bytte": 0}
        self.day["tot"] += 1
        age = now - self.out.last if self.out.last else None
        if age is not None and age < self.switch_after:
            self.day["ok"] += 1
        with self.lock:
            if self.active is not None and (self.active.age(now) or 1e9) >= self.switch_after:
                self._set_active(self._choose(now))

    def station_conflict(self):
        """Stasjons-ID-ar som fleire kjelder brukar (RTKLIB ser då ikkje at basen er bytt)."""
        seen = {}
        for s in self.sources:
            b = s.stats.base
            if b:
                seen.setdefault(b["station"], []).append(s.name)
        return {st: names for st, names in seen.items() if len(names) > 1}

    def _publish(self, frames, now):
        with self.cond:
            for fr in frames:
                self.out.add(fr, now)
                self.seq += 1
                self.ring.append((self.seq, fr))
            self.cond.notify_all()

    # ---------- ut ----------
    def read_after(self, seq, timeout=1.0):
        """Rammer etter seq. Klientar som har kome for langt bak, hoppar fram (ingen gamle korreksjonar)."""
        with self.cond:
            if self.seq <= seq:
                self.cond.wait(timeout)
            if self.seq <= seq:
                return seq, []
            first = self.ring[0][0] if self.ring else self.seq + 1
            if seq < first - 1:
                seq = first - 1
            out = [fr for s, fr in self.ring if s > seq]
            return self.seq, out

    # ---------- status ----------
    def base_check(self):
        """Samanlikn baseposisjonen i straumen (1005/1006) med den innmålte. Avvik → åtvaring."""
        b = self.out.base
        src = self.active
        if not b or src is None:
            return None
        # Innmålt posisjon gjeld eigen base (første kjelde) – ei reservekjelde er ein annan base med eigen posisjon.
        # Ei kjelde kan ha sin eigen «innmalt» om ho også skal kontrollerast.
        m = src.cfg.get("innmalt") or (self.cfg.get("innmalt") if src is self.sources[0] else None)
        if not m or m.get("lat") is None:
            return None
        x, y, z = geo_to_ecef(float(m["lat"]), float(m["lon"]), float(m.get("h", 0)))
        d = math.dist((x, y, z), (b["x"], b["y"], b["z"]))
        if d < 0.05:
            v = "OK"
        elif d < 0.5:
            v = f"ÅTVARING: basen sender ein posisjon {d * 100:.0f} cm frå den innmålte"
        else:
            v = f"FEIL: basen sender ein posisjon {d:.2f} m frå den innmålte – snødjupna blir feil"
        return {"avvik_m": round(d, 3), "vurdering": v}

    def verdict(self):
        s = self.out.summary()
        if not self.sources:
            return "Ingen kjelder sett opp."
        if s["age"] is None:
            return "Ventar på korreksjonar frå kjeldene."
        if s["age"] > self.switch_after:
            return f"FEIL: ingen korreksjonar på {s['age']:.0f} s."
        if self.active is None:
            return "FEIL: ingen kjelde sender korreksjonar (berre tillegg)."
        if not s["systems"]:
            return "FEIL: straumen har ingen observasjonar – RTK er ikkje mogleg."
        if "base" not in s:
            return "Ventar på baseposisjonen (1005/1006)."
        if s["msm3"]:
            return "ÅTVARING: basen sender MSM3, som RTKLIB i SNOWMAN ikkje les. Bruk MSM4/MSM7 eller 1004/1012."
        bc = self.base_check()
        if bc and bc["vurdering"] != "OK":
            return bc["vurdering"]
        if self.active is not self.sources[0]:
            return (f"ÅTVARING: reserve i bruk ({self.active.name}) – {self.sources[0].name} sender ikkje. Maskinene får "
                    f"korreksjonar, men frå ein annan base.")
        if not s["eph"]:
            return ("OK – men straumen har ingen satellittbaner (1019/1020/…). SNOWMAN hentar dei då frå mottakaren "
                    "eller nettet. Legg gjerne til eit tillegg med baner.")
        return "OK: korreksjonar med baseposisjon og satellittbaner."

    def status(self):
        s = self.out.summary()
        s.update({"namn": self.name, "skildring": self.cfg.get("skildring", ""), "test": bool(self.cfg.get("test")),
                  "aktiv": self.active.name if self.active else None, "bitrate": self.out.bitrate(),
                  "kjelder": [x.status() for x in self.sources], "tillegg": [x.status() for x in self.extras],
                  "basekontroll": self.base_check(), "vurdering": self.verdict(),
                  "klientar": [c.status() for c in list(self.clients.values())]})
        return s

    def str_line(self):
        """STR-linja i kjeldetabellen (NTRIP)."""
        s = self.out.summary()
        types = ",".join(f"{t['type']}({max(1, round(t['iv']))})" if t["iv"] else str(t["type"])
                         for t in s["types"] if t["aktiv"])
        sysmap = {"GPS": "GPS", "GLONASS": "GLO", "Galileo": "GAL", "BeiDou": "BDS", "QZSS": "QZS", "SBAS": "SBAS"}
        nav = "+".join(sysmap.get(x, x) for x in s["systems"]) or "GPS"
        b = s.get("base") or self.cfg.get("innmalt") or {}
        lat, lon = b.get("lat") or 0.0, b.get("lon") or 0.0
        msm = any(t["type"] >= 1070 for t in s["types"] if system_of_safe(t["type"]))
        ident = (self.cfg.get("skildring") or self.name)[:60].replace(";", ",")
        if self.cfg.get("test"):
            ident = "TEST " + ident
        return (f"STR;{self.name};{ident};{'RTCM 3.3' if msm else 'RTCM 3.2'};{types};2;{nav};SNOWMAN;NOR;"
                f"{lat:.2f};{lon:.2f};0;0;SNOWMAN Base;none;B;N;{self.out.bitrate()};")


def system_of_safe(t):
    from rtcm import system_of
    return system_of(t)


def build(cfg_list, events, rawlog):
    mounts = {}
    for mc in cfg_list:
        if not mc.get("namn"):
            continue
        mounts[mc["namn"]] = Mountpoint(mc, events, rawlog)
    return mounts


def ticker(mounts, stop_ev):
    while not stop_ev.wait(1.0):
        for m in list(mounts.values()):
            m.tick()


def disk_free(folder):
    try:
        st = os.statvfs(folder)
        return round(st.f_bavail * st.f_frsize / 1e9, 1)
    except (AttributeError, OSError):
        import shutil
        try:
            return round(shutil.disk_usage(folder).free / 1e9, 1)
        except OSError:
            return None
