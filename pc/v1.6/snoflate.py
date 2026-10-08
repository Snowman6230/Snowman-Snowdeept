# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Snøflateminne: målt snøoverflate frå tidlegare køyring, brukt til å estimere snødjupna framfor maskina.

Kvar gong SNOWMAN har ei gyldig snødjupne (RTK FIX, kalibrert, inne i terrengmodellen), blir høgda på snøoverflata
(NN2000, der maskina står) lagra i ei rute på 1 × 1 m saman med tidspunktet. Nyaste måling i ruta gjeld.

Modell: etter planering følgjer snøoverflata den STORE forma på terrenget (bakken, hellinga), men ikkje dei små
formene (bekkar, groper, kular), som blir fylte eller skorne vekk. Difor:
    Tg(x)  = glatta terreng (snitt av barmarkshøgda innanfor ±6 m)
    r      = snøoverflate − Tg   (blir lagra for kvar måling, varierer lite og jamt)
    estimert snødjupne(x) = interpolert r(x) + Tg(x) − terreng(x)
På ein jamn bakke er dette same som å interpolere snødjupna. Over eit gjenfylt bekkefar (terreng under Tg) blir
djupna større, oppå ein kul (terreng over Tg) mindre – sjølv om ein berre har køyrt på kvar side av forma.
(Å interpolere sjølve overflata direkte vart prøvd og forkasta: i bratt bakke blir det store feil framfor maskina.)

Alt herifrå er ESTIMAT og skal alltid visast merka som det, med alder. Nysnø, vind og setningar etter siste
køyring er ikkje med. Simulerte målingar (testmodus) blir lagra merka som test og berre brukte i testmodus.
Data: data/snoflate.json (høyrer til anlegget, ikkje i git).
"""
import json, math, os, threading, time
from pathlib import Path

from terrain import utm_forward, utm_inverse

KEEP_DAYS = 7          # ruter eldre enn dette blir sletta
R = 8.0                # søkjeradius for interpolasjonen (m)
NEAR = 6.0             # næraste måling må vere innanfor dette (m)
MIN_PTS = 3            # minst så mange ruter med måling innanfor R
SMOOTH = 6             # glatta terreng: snitt innanfor ±SMOOTH m (prøvar kvar 2. m)


def zone_of(lon):
    return 33 if lon >= 12 else 32


def smooth_terrain(z, E, N, terrain_height):
    """Snitt av barmarkshøgda i eit 13 × 13 m kvadrat (49 punkt) rundt punktet, eller None."""
    s = n = 0
    for de in range(-SMOOTH, SMOOTH + 1, 2):
        for dn in range(-SMOOTH, SMOOTH + 1, 2):
            la, lo = utm_inverse(E + de, N + dn, z)
            t = terrain_height(la, lo)
            if t is not None:
                s += t["h"]
                n += 1
    return s / n if n >= 25 else None


class SnowSurface:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.cells = {}        # (sone, E, N) -> [overflate_m, tid_s, test, glatta_terreng_m]
        self.dirty = False
        self.saved = 0.0
        self._load()

    def _load(self):
        try:
            d = json.loads(self.path.read_text("utf-8"))
            lim = time.time() - KEEP_DAYS * 86400
            for k, v in d.get("cells", {}).items():
                z, e, n = (int(x) for x in k.split(","))
                if v[1] >= lim and len(v) >= 4:
                    self.cells[(z, e, n)] = [float(v[0]), float(v[1]), bool(v[2]), float(v[3])]
        except FileNotFoundError:
            pass
        except Exception:
            self.cells = {}

    def save(self, force=False):
        """Lagre til fil (høgst kvart 30. sekund, eller med force)."""
        if not self.dirty or (not force and time.time() - self.saved < 30):
            return
        with self.lock:
            lim = time.time() - KEEP_DAYS * 86400
            self.cells = {k: v for k, v in self.cells.items() if v[1] >= lim}
            data = {"cells": {f"{k[0]},{k[1]},{k[2]}": [round(v[0], 3), round(v[1]), 1 if v[2] else 0, round(v[3], 3)] for k, v in self.cells.items()}}
            self.dirty = False
            self.saved = time.time()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, separators=(",", ":")))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def add(self, lat, lon, surface, terrain_height, test=False, t=None):
        if lat is None or lon is None or surface is None or not math.isfinite(surface):
            return
        z = zone_of(lon)
        E, N = utm_forward(lat, lon, z)
        k = (z, int(math.floor(E)), int(math.floor(N)))
        old = self.cells.get(k)
        tg = old[3] if old else smooth_terrain(z, math.floor(E) + 0.5, math.floor(N) + 0.5, terrain_height)
        if tg is None:
            return
        with self.lock:
            self.cells[k] = [float(surface), t or time.time(), bool(test), tg]
            self.dirty = True

    def stats(self, test=False):
        with self.lock:
            v = [c for c in self.cells.values() if c[2] == bool(test)]
        if not v:
            return {"cells": 0}
        return {"cells": len(v), "newest": max(c[1] for c in v), "oldest": min(c[1] for c in v)}

    def clear(self, test=None):
        with self.lock:
            self.cells = {k: v for k, v in self.cells.items() if test is not None and v[2] != bool(test)}
            self.dirty = True
        self.save(force=True)

    def _resid_at(self, z, E, N, test, lim):
        """IDW av r = overflate − glatta terreng rundt punktet. Returnerer (r, alder_s) eller None."""
        e0, n0 = int(math.floor(E)), int(math.floor(N))
        r = int(R) + 1
        sw = sh = st = 0.0
        cnt = 0
        near = 1e9
        now = time.time()
        cells = self.cells
        for de in range(-r, r + 1):
            for dn in range(-r, r + 1):
                c = cells.get((z, e0 + de, n0 + dn))
                if c is None or c[2] != test or c[1] < lim:
                    continue
                d = math.hypot(e0 + de + 0.5 - E, n0 + dn + 0.5 - N)
                if d >= R:
                    continue
                w = 1.0 / max(d, 0.5) ** 2
                sw += w
                sh += w * (c[0] - c[3])
                st += w * (now - c[1])
                cnt += 1
                near = min(near, d)
        if cnt < MIN_PTS or near >= NEAR:
            return None
        return sh / sw, st / sw

    def ahead(self, lat, lon, hdg, width, terrain_height, test=False, max_age_h=72, cell=2.0):
        """Ruter på 2 × 2 m frå 4 til 40 m framfor maskina, 1,5 × fresbreidda til kvar side (minst 6 m) –
        same mønster som estimatet i førarskjermen. terrain_height(lat, lon) -> {"h": ...} eller None."""
        if lat is None or lon is None or hdg is None:
            return {"cells": [], "summary": None}
        z = zone_of(lon)
        E0, N0 = utm_forward(lat, lon, z)
        h = math.radians(hdg)
        fx, fy = math.sin(h), math.cos(h)
        W = max(6.0, width * 1.5)
        lim = time.time() - max_age_h * 3600
        out = []
        sum_d = cnt = 0
        mn = None
        ages = []
        with self.lock:
            s = 4.0
            while s <= 40.0 + 1e-6:
                t = -W
                while t <= W + 1e-6:
                    E = E0 + fx * s + fy * t
                    N = N0 + fy * s - fx * t
                    r = self._resid_at(z, E, N, test, lim)
                    if r is not None:
                        clat, clon = utm_inverse(E, N, z)
                        ter = terrain_height(clat, clon)
                        tg = smooth_terrain(z, E, N, terrain_height) if ter is not None else None
                        if tg is not None:
                            d = max(0.0, r[0] + tg - ter["h"])
                            out.append({"lat": round(clat, 7), "lon": round(clon, 7), "d": round(d, 3), "age": round(r[1] / 3600, 1)})
                            if abs(t) <= width / 2 + 1e-6 and 6 <= s <= 30:
                                sum_d += d
                                cnt += 1
                                mn = d if mn is None else min(mn, d)
                                ages.append(r[1])
                    t += cell
                s += cell
        summary = {"mean": round(sum_d / cnt, 3), "min": round(mn, 3), "ageH": round(sum(ages) / len(ages) / 3600, 1)} if cnt else None
        return {"cells": out, "summary": summary, "cell": cell, "hdg": hdg}
