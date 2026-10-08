# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Trasear: yttergrensa for kvar bakke/løype, og forbodne område.

- Ein trasé er eit polygon (breidd/lengd) med namn, kategori (farge) og ev. måldjupne.
- Eit forbode område (veg, bygg, bekk, parkering …) gir raudt varsel når maskina kjem inn i det.
- Omrisset kan teiknast på kartet, eller hentast frå eit terrenglag (yttergrensa av cellene som har høgd).
- «Prosent preparert» blir rekna frå arbeidsøktene (data/sessions): kvar strekning maskina har køyrt med
  fresbreidda blir merkt i eit rutenett over trasé-polygonet.

Prepareringsdøgnet går frå kl. 12 til kl. 12 neste dag, slik at ei natt med preparering (t.d. 17–03) blir
rekna som éin dag. Data blir lagra i data/trasear.json og høyrer til anlegget.
"""
import base64, json, math, threading, time, uuid
from collections import deque
from pathlib import Path

import numpy as np

DAY_START_HOUR = 12           # prepareringsdøgnet startar kl. 12
KINDS = {"trase": "Trasé", "forbode": "Forbode område"}
LEVELS = {"gron": "#27d84d", "bla": "#2f7bff", "raud": "#ed2024", "svart": "#202020", "langrenn": "#08cbea", "anna": "#ffd33f"}
MAX_GAP_M = 30.0              # lengre hopp mellom to punkt blir ikkje rekna som køyrt (GNSS-hopp, pause)
MAX_GAP_S = 60.0
MAX_PREP_SPEED = 40 / 3.6     # m/s: fortare enn 40 km/t er transport (vegkøyring, bil) – ikkje preparert areal


def prep_day_start(t=None, date=None):
    """Starten på prepareringsdøgnet (epoch-sekund) som tidspunktet høyrer til, eller som startar kl. 12 på datoen."""
    if date:
        tm = time.strptime(date + f" {DAY_START_HOUR}", "%Y-%m-%d %H")
        return time.mktime(tm)
    t = time.time() if t is None else t
    lt = time.localtime(t)
    start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, DAY_START_HOUR, 0, 0, 0, 0, -1))
    if t < start:
        start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - 1, DAY_START_HOUR, 0, 0, 0, 0, -1))
    return start


class Local:
    """Flat tilnærming rundt eit punkt (same som førarskjermen): meter mot aust (x) og nord (y)."""

    def __init__(self, lat0, lon0):
        self.lat0, self.lon0 = lat0, lon0
        self.my = 111320.0
        self.mx = 111320.0 * math.cos(math.radians(lat0))

    def xy(self, lat, lon):
        return (np.asarray(lon) - self.lon0) * self.mx, (np.asarray(lat) - self.lat0) * self.my


def poly_area_m2(poly):
    if len(poly) < 3:
        return 0.0
    a = np.asarray(poly, float)
    L = Local(a[:, 0].mean(), a[:, 1].mean())
    x, y = L.xy(a[:, 0], a[:, 1])
    return float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2)


def inside_mask(px, py, X, Y):
    """Punkt-i-polygon (partal/oddetal) for alle punkta i X, Y."""
    ins = np.zeros(X.shape, bool)
    n = len(px)
    j = n - 1
    for i in range(n):
        xi, yi, xj, yj = px[i], py[i], px[j], py[j]
        if yi != yj:
            cross = ((yi > Y) != (yj > Y)) & (X < (xj - xi) * (Y - yi) / (yj - yi) + xi)
            ins ^= cross
        j = i
    return ins


# ---------------------------------------------------------------------------------------------
# Omriss frå terrenglag
# ---------------------------------------------------------------------------------------------
def _largest_component(m):
    """Største samanhengande område (4-naboar) i ei boolsk maske."""
    lab = np.zeros(m.shape, np.int32)
    best, best_n, cur = 0, 0, 0
    H, W = m.shape
    for r0, c0 in zip(*np.nonzero(m)):
        if lab[r0, c0]:
            continue
        cur += 1
        lab[r0, c0] = cur
        q, n = deque([(r0, c0)]), 0
        while q:
            r, c = q.popleft()
            n += 1
            for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if 0 <= rr < H and 0 <= cc < W and m[rr, cc] and not lab[rr, cc]:
                    lab[rr, cc] = cur
                    q.append((rr, cc))
        if n > best_n:
            best, best_n = cur, n
    return lab == best if best else m


def _shift_or(m, it):
    for _ in range(it):
        o = m.copy()
        o[1:] |= m[:-1]; o[:-1] |= m[1:]; o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
        m = o
    return m


def _shift_and(m, it):
    for _ in range(it):
        o = m.copy()
        o[1:] &= m[:-1]; o[:-1] &= m[1:]; o[:, 1:] &= m[:, :-1]; o[:, :-1] &= m[:, 1:]
        o[0] = o[-1] = False; o[:, 0] = o[:, -1] = False
        m = o
    return m


def _trace(m):
    """Moore-nabo-sporing av ytterkanten (pikselsentra, med klokka). m må ha False langs kanten."""
    nb = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1)]
    flat = np.flatnonzero(m.ravel())
    if not len(flat):
        return []
    start = divmod(int(flat[0]), m.shape[1])
    cur, back = start, 0  # første piksel funnen radvis: nabo mot vest er tom
    path, first, limit = [start], None, 4 * m.size
    while limit:
        limit -= 1
        for k in range(1, 9):
            d = (back + k) % 8
            nr, nc = cur[0] + nb[d][0], cur[1] + nb[d][1]
            if m[nr, nc]:
                pd = (back + k - 1) % 8
                pr, pc = cur[0] + nb[pd][0], cur[1] + nb[pd][1]
                cur, back = (nr, nc), nb.index((pr - nr, pc - nc))
                break
        else:
            return path  # éin einsleg piksel
        if first is None:
            first = (cur, back)
        elif (cur, back) == first:
            break
        path.append(cur)
    if len(path) > 1 and path[-1] == start:
        path.pop()
    return path


def _rdp(pts, tol):
    """Douglas–Peucker-forenkling av ein open linje."""
    pts = np.asarray(pts, float)
    keep = np.zeros(len(pts), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        p, q = pts[a], pts[b]
        seg = q - p
        L = math.hypot(*seg)
        mid = pts[a + 1:b]
        if L == 0:
            d = np.hypot(*(mid - p).T)
        else:
            d = np.abs(seg[0] * (mid[:, 1] - p[1]) - seg[1] * (mid[:, 0] - p[0])) / L
        i = int(np.argmax(d))
        if d[i] > tol:
            keep[a + 1 + i] = True
            stack += [(a, a + 1 + i), (a + 1 + i, b)]
    return pts[keep]


def outline_from_layer(grid, meta, utm_inverse, tol_m=2.0, max_cells=400_000):
    """Yttergrensa til eit terrenglag (cellene med høgd), forenkla. Returnerer [[lat, lon], …]."""
    ny, nx = grid.shape
    cell = max(float(meta["dx"]), 1.0)
    f = max(1, int(round(cell / float(meta["dx"]))), int(math.ceil(math.sqrt(nx * ny / max_cells))))
    H, W = ny // f, nx // f
    if H < 3 or W < 3:
        raise ValueError("Laget er for lite til å lage omriss.")
    valid = np.isfinite(np.asarray(grid[:H * f, :W * f], dtype=np.float32)).reshape(H, f, W, f).mean(axis=(1, 3)) > 0.5
    m = np.zeros((H + 2, W + 2), bool)
    m[1:-1, 1:-1] = valid
    m = _shift_and(_shift_or(m, 2), 2)  # lukk små hakk og hol i kanten
    m[0] = m[-1] = False; m[:, 0] = m[:, -1] = False
    m = _largest_component(m)
    ring = _trace(m)
    if len(ring) < 4:
        raise ValueError("Fann ikkje noko samanhengande område med høgder i laget.")
    rc = np.asarray(ring + [ring[0]], float) - 1  # utan kantramma
    dxs, dys = float(meta["dx"]) * f, float(meta["dy"]) * f
    E = meta["x0"] + (rc[:, 1] + 0.5) * dxs
    N = meta["y0"] - (rc[:, 0] + 0.5) * dys
    simp = _rdp(np.c_[E, N], tol_m)[:-1]
    if len(simp) < 3:
        raise ValueError("Omrisset vart for lite etter forenkling.")
    return [[round(a, 7), round(b, 7)] for a, b in (utm_inverse(e, n, meta["zone"]) for e, n in simp)]


# ---------------------------------------------------------------------------------------------
# Lagring og prosent preparert
# ---------------------------------------------------------------------------------------------
class Trasear:
    def __init__(self, path, sessions_dir):
        self.path = Path(path)
        self.sess = Path(sessions_dir)
        self.lock = threading.Lock()
        self.items = []
        self._masks = {}    # trasé-id → (updated, rutenett) – maske for innsida
        self._tracks = {}   # øktfil → (mtime, data) – innlesne punkt
        self._status = (0, None, None)  # (tid, since, svar) – kort mellomlager
        self._stamps = {}   # (økt, mtime, trasé, versjon, periode) → ferdig utrekna dekning
        try:
            self.items = json.loads(self.path.read_text("utf-8")).get("trasear", [])
        except FileNotFoundError:
            pass
        except Exception as e:
            print("Kunne ikkje lese trasear.json:", e)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"trasear": self.items}, indent=1, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)
        self._status = (0, None, None)

    def listing(self):
        with self.lock:
            return [dict(t) for t in self.items]

    def save(self, d):
        poly = [[float(p[0]), float(p[1])] for p in d.get("poly") or []]
        if len(poly) < 3:
            raise ValueError("Ein trasé må ha minst 3 hjørne.")
        if any(not (-90 <= a <= 90 and -180 <= b <= 180) for a, b in poly):
            raise ValueError("Ugyldig koordinat i omrisset.")
        name = str(d.get("name") or "").strip()[:60]
        if not name:
            raise ValueError("Gi traseen eit namn.")
        kind = d.get("kind") if d.get("kind") in KINDS else "trase"
        level = d.get("level") if d.get("level") in LEVELS else ("raud" if kind == "forbode" else "anna")
        tgt = d.get("target")
        tgt = None if tgt in (None, "") else float(tgt)
        if tgt is not None and not (0 <= tgt <= 10):
            raise ValueError("Måldjupna må vere mellom 0 og 10 m.")
        with self.lock:
            old = next((t for t in self.items if t["id"] == d.get("id")), None)
            t = old or {"id": uuid.uuid4().hex[:8], "created": time.strftime("%Y-%m-%d %H:%M")}
            t.update(name=name, kind=kind, level=level, color=LEVELS[level], target=tgt,
                     poly=[[round(a, 8), round(b, 8)] for a, b in poly], area=round(poly_area_m2(poly)),
                     source=str(d.get("source") or t.get("source") or "teikna")[:80],
                     updated=time.strftime("%Y-%m-%d %H:%M:%S"))
            if not old:
                self.items.append(t)
            self._masks.pop(t["id"], None)
            self._save()
            return dict(t)

    def delete(self, tid):
        with self.lock:
            self.items = [t for t in self.items if t["id"] != tid]
            self._masks.pop(tid, None)
            self._save()

    # --- innsida av traseen som rutenett ---
    def _mask(self, t):
        hit = self._masks.get(t["id"])
        if hit and hit[0] == t["updated"]:
            return hit[1]
        a = np.asarray(t["poly"], float)
        L = Local(a[:, 0].mean(), a[:, 1].mean())
        px, py = L.xy(a[:, 0], a[:, 1])
        area = max(poly_area_m2(t["poly"]), 1.0)
        cell = max(1.0, math.sqrt(area / 600_000))  # 1 m rute, grovare for store område
        x0, y0 = px.min() - cell, py.min() - cell
        W = int(math.ceil((px.max() - x0) / cell)) + 2
        H = int(math.ceil((py.max() - y0) / cell)) + 2
        X, Y = np.meshgrid(x0 + (np.arange(W) + 0.5) * cell, y0 + (np.arange(H) + 0.5) * cell)
        g = {"L": L, "x0": x0, "y0": y0, "cell": cell, "W": W, "H": H, "ins": inside_mask(px, py, X, Y)}
        g["n"] = int(g["ins"].sum())
        self._masks[t["id"]] = (t["updated"], g)
        return g

    # --- økter ---
    def sessions(self, since_s, until_s=None):
        with self.lock:
            return self._sessions(since_s, until_s)

    def _sessions(self, since_s, until_s=None):
        out = []
        if not self.sess.exists():
            return out
        for f in self.sess.glob("*.json"):
            try:
                mt = f.stat().st_mtime
                if mt < since_s:
                    continue  # ikkje endra sidan døgnet starta
                hit = self._tracks.get(f.name)
                if not hit or hit[0] != mt:
                    d = json.loads(f.read_text("utf-8"))
                    p = d.get("points") or []
                    arr = np.array([[q.get("lat", np.nan), q.get("lng", np.nan), (q.get("t") or 0) / 1000.0,
                                     np.nan if q.get("depth") is None else q["depth"]] for q in p], float).reshape(-1, 4)
                    test = bool(d.get("demo")) or d.get("source") == "demo" or bool(d.get("simulated"))
                    hit = (mt, {"id": d.get("id"), "width": float(d.get("width") or 5.0), "test": test,
                                "machine": d.get("machine") or "", "pts": arr})
                    self._tracks[f.name] = hit
                s = hit[1]
                sel = s["pts"][:, 2] >= since_s
                if until_s:
                    sel &= s["pts"][:, 2] < until_s
                if sel.sum() >= 1:
                    out.append(dict(s, pts=s["pts"][sel], key=(f.name, mt)))
            except Exception as e:
                print("Hoppar over økt", f.name, e)
        return out

    @staticmethod
    def _stamp(cov, g, x, y, t, width, pad=0.5):
        """Merk rutene innanfor halve breidda frå køyrelinja (x, y i meter).
        pad: ekstra margin i ruter (0,5 = romsleg for trasé-prosent; 0 = rett areal for trakka område)."""
        if len(x) < 2:
            return
        dx, dy, dt = np.diff(x), np.diff(y), np.diff(t)
        seglen = np.hypot(dx, dy)
        ok = (seglen <= MAX_GAP_M) & (dt <= MAX_GAP_S)
        ok &= seglen <= np.maximum(dt, 0.2) * MAX_PREP_SPEED   # transport (> 40 km/t) blir ikkje merkt som preparert
        if not ok.any():
            return
        step = min(0.5, g["cell"] / 2)
        k = np.where(ok, np.maximum(1, np.ceil(seglen / step)).astype(int), 0)
        idx = np.repeat(np.arange(len(k)), k)
        frac = (np.arange(k.sum()) - np.repeat(np.cumsum(k) - k, k)) / np.repeat(np.maximum(k, 1), k)
        sx = x[idx] + dx[idx] * frac
        sy = y[idx] + dy[idx] * frac
        r = width / 2.0
        rc = int(math.ceil(r / g["cell"]))
        oy, ox = np.mgrid[-rc:rc + 1, -rc:rc + 1]
        disk = (np.hypot(ox, oy) * g["cell"] <= r + g["cell"] * pad)
        ox, oy = ox[disk], oy[disk]
        ci = np.floor((sx - g["x0"]) / g["cell"]).astype(int)
        ri = np.floor((sy - g["y0"]) / g["cell"]).astype(int)
        inb = (ci >= -rc) & (ci < g["W"] + rc) & (ri >= -rc) & (ri < g["H"] + rc)
        ci, ri = ci[inb], ri[inb]
        if not len(ci):
            return
        C = (ci[:, None] + ox[None, :]).ravel()
        R = (ri[:, None] + oy[None, :]).ravel()
        v = (C >= 0) & (C < g["W"]) & (R >= 0) & (R < g["H"])
        cov[R[v], C[v]] = True

    def status(self, since_s=None, until_s=None, cache_s=4.0, with_map=False):
        """Prosent preparert per trasé sidan since_s (standard: starten på dette prepareringsdøgnet).
        pct tel berre ekte økter; pctTest tek med demo/simulator (berre til test, alltid merka TEST).
        with_map: ta med kart over uprepart areal (bitmap) for kvar trasé."""
        r = self._status_all(since_s, until_s, cache_s)
        if with_map:
            return r
        return dict(r, status={k: {a: b for a, b in v.items() if a != "map"} for k, v in r["status"].items()})

    def coverage(self, since_s=0, until_s=None, ids=None, include_test=False, max_cells=6_000_000):
        """Trakka område i perioden (eller for utvalde økter) som rutenett i fresbreidda til kvar økt.
        Kvar rute får tidspunktet ho sist vart køyrd og kor mange økter som har køyrt der.
        Overlapp tel éin gong i arealet. Transport (> 40 km/t) og hopp i sporet blir ikkje teikna."""
        with self.lock:
            ses = self._sessions(since_s or 0, until_s)
        if ids:
            ses = [x for x in ses if x["id"] in ids]
        elif not include_test:
            ses = [x for x in ses if not x["test"]]
        ses = [x for x in ses if len(x["pts"]) >= 2]
        if not ses:
            return {"empty": True, "sessions": 0}
        P = np.vstack([x["pts"][:, :2] for x in ses])
        P = P[np.isfinite(P).all(axis=1)]
        L = Local(float(np.median(P[:, 0])), float(np.median(P[:, 1])))
        wmax = max(x["width"] for x in ses)
        segs = []
        for x in ses:  # berre punkt som høyrer til preparering (ikkje transport) avgjer kor stort kartet blir
            q = x["pts"]
            px, py = L.xy(q[:, 0], q[:, 1])
            d, dt = np.hypot(np.diff(px), np.diff(py)), np.diff(q[:, 2])
            ok = (d <= MAX_GAP_M) & (dt <= MAX_GAP_S) & (d <= np.maximum(dt, 0.2) * MAX_PREP_SPEED)
            if ok.any():
                use = np.zeros(len(q), bool)
                use[1:] |= ok
                use[:-1] |= ok
                segs.append((x, px, py, use))
        if not segs:
            return {"empty": True, "sessions": len(ses), "note": "Berre transport (over 40 km/t) i perioden"}
        allx = np.concatenate([sx[u] for _, sx, _, u in segs])
        ally = np.concatenate([sy[u] for _, _, sy, u in segs])
        x0, y0 = float(np.nanmin(allx)) - wmax, float(np.nanmin(ally)) - wmax
        ex, ey = float(np.nanmax(allx)) + wmax - x0, float(np.nanmax(ally)) + wmax - y0
        cell = max(1.0, math.sqrt(ex * ey / max_cells))
        W, H = int(math.ceil(ex / cell)) + 1, int(math.ceil(ey / cell)) + 1
        g = {"x0": x0, "y0": y0, "cell": cell, "W": W, "H": H}
        last = np.zeros((H, W), np.float64)
        passes = np.zeros((H, W), np.uint16)
        for x, px, py, _ in segs:
            q = x["pts"]
            tmp = np.zeros((H, W), bool)
            self._stamp(tmp, g, px, py, q[:, 2], x["width"], pad=0.0)
            passes += tmp
            last[tmp] = np.maximum(last[tmp], float(np.nanmax(q[:, 2])))
        cov = passes > 0
        now = time.time()
        age = np.full((H, W), 255, np.uint8)  # timar sidan sist køyrd, 254 = eldre, 255 = aldri
        age[cov] = np.clip(np.floor((now - last[cov]) / 3600.0), 0, 254).astype(np.uint8)
        return {"empty": False, "lat0": L.lat0, "lon0": L.lon0, "mx": L.mx, "my": L.my, "x0": x0, "y0": y0,
                "cell": cell, "W": W, "H": H, "area": round(float(cov.sum()) * cell * cell),
                "sessions": len(segs), "test": any(x["test"] for x, *_ in segs),
                "first": int(min(float(np.nanmin(x["pts"][:, 2])) for x, *_ in segs) * 1000),
                "last": int(max(float(np.nanmax(x["pts"][:, 2])) for x, *_ in segs) * 1000),
                "age": base64.b64encode(age.tobytes()).decode(),
                "passes": base64.b64encode(np.minimum(passes, 255).astype(np.uint8).tobytes()).decode()}

    def _status_all(self, since_s=None, until_s=None, cache_s=4.0):
        since_s = prep_day_start() if since_s is None else since_s
        now = time.time()
        with self.lock:
            c = self._status
            if c[2] is not None and c[1] == (since_s, until_s) and now - c[0] < cache_s:
                return c[2]
            items = [dict(t) for t in self.items]
            sessions = self._sessions(since_s, until_s)
            res = {}
            for t in items:
                if t["kind"] != "trase":
                    continue
                g = self._mask(t)
                cov_real = np.zeros(g["ins"].shape, bool)
                cov_all = np.zeros(g["ins"].shape, bool)
                depths, last, ids = [], None, []
                secs_real = secs_test = 0.0
                for s in sessions:
                    key = s["key"] + (t["id"], t["updated"], since_s, until_s)
                    hit = self._stamps.get(key)
                    if hit is None:  # berre økta som er i gang blir rekna på nytt
                        P = s["pts"]
                        x, y = g["L"].xy(P[:, 0], P[:, 1])
                        tmp = np.zeros_like(cov_all)
                        self._stamp(tmp, g, x, y, P[:, 2], s["width"])
                        tmp &= g["ins"]
                        ci = np.floor((x - g["x0"]) / g["cell"]).astype(int)
                        ri = np.floor((y - g["y0"]) / g["cell"]).astype(int)
                        ok = (ci >= 0) & (ci < g["W"]) & (ri >= 0) & (ri < g["H"])
                        inside = np.zeros(len(x), bool)
                        inside[ok] = g["ins"][ri[ok], ci[ok]]
                        d = P[inside, 3]
                        # tid i traseen: strekningar der begge endepunkta er inne, utan hopp og transport (> 40 km/t)
                        dt = np.diff(P[:, 2])
                        dl = np.hypot(np.diff(x), np.diff(y))
                        mv = inside[1:] & inside[:-1] & (dt > 0) & (dt <= MAX_GAP_S) & (dl <= np.maximum(dt, 0.2) * MAX_PREP_SPEED)
                        hit = (tmp if tmp.any() else None, float(P[inside, 2].max()) if inside.any() else None, d[np.isfinite(d)],
                               float(dt[mv].sum()))
                        self._stamps = {k: v for k, v in self._stamps.items() if k[0] != key[0] or k[1] == key[1]}
                        if len(self._stamps) > 400:
                            self._stamps.clear()
                        self._stamps[key] = hit
                    tmp, tl, d, sec = hit
                    if s["test"]:
                        secs_test += sec
                    else:
                        secs_real += sec
                    if tl:
                        last = max(last or 0, tl)
                    if tmp is None:
                        continue
                    before = int(cov_all.sum())
                    cov_all |= tmp
                    if not s["test"]:
                        cov_real |= tmp
                        depths += [float(v) for v in d]
                    ids.append({"id": s["id"], "test": s["test"], "cells": int(tmp.sum()), "new": int(cov_all.sum()) - before})
                n = max(g["n"], 1)
                a = g["cell"] ** 2
                res[t["id"]] = {
                    "area": round(g["n"] * a), "covered": round(int(cov_real.sum()) * a), "coveredTest": round(int(cov_all.sum()) * a),
                    "pct": round(100.0 * float(cov_real.sum()) / n, 1), "pctTest": round(100.0 * float(cov_all.sum()) / n, 1),
                    "last": int(last * 1000) if last else None, "sessions": ids,
                    "secs": round(secs_real), "secsTest": round(secs_real + secs_test),
                    "depthAvg": round(sum(depths) / len(depths), 2) if depths else None,
                    "depthMin": round(min(depths), 2) if depths else None, "depthN": len(depths),
                    # uprepart areal: rad 0 = sørkanten, bit = rute inne i traseen som ikkje er køyrd
                    "map": {"lat0": g["L"].lat0, "lon0": g["L"].lon0, "mx": g["L"].mx, "my": g["L"].my, "x0": g["x0"], "y0": g["y0"],
                            "cell": g["cell"], "W": g["W"], "H": g["H"],
                            "real": base64.b64encode(np.packbits(g["ins"] & ~cov_real).tobytes()).decode(),
                            "all": base64.b64encode(np.packbits(g["ins"] & ~cov_all).tobytes()).decode(),
                            # til kartet i rapporten: inne i traseen, trakka (ekte), trakka medrekna TEST
                            "ins": base64.b64encode(np.packbits(g["ins"]).tobytes()).decode(),
                            "cov": base64.b64encode(np.packbits(g["ins"] & cov_real).tobytes()).decode(),
                            "covAll": base64.b64encode(np.packbits(g["ins"] & cov_all).tobytes()).decode()},
                }
            out = {"since": int(since_s * 1000), "until": int(until_s * 1000) if until_s else None, "dayStartHour": DAY_START_HOUR, "status": res}
            self._status = (now, (since_s, until_s), out)
            return out


# ---------------------------------------------------------------------------------------------
# Hindringar og anleggsobjekt (punkt): snøkanon, hydrant, heismast, stein, kum, bygg …
# Føraren får varsel på skjerm og HUD når eit objekt ligg i køyrebana framfor skjeret (sjå driver.html, OBJ).
# ---------------------------------------------------------------------------------------------
OBJ_TYPES = {  # type → (namn, standard radius i meter, kort symbol på kartet)
    "hydrant": ("Hydrant", 0.5, "H"),
    "snokanon": ("Snøkanon", 1.5, "SK"),
    "mast": ("Heismast", 1.0, "M"),
    "stein": ("Stein", 1.0, "S"),
    "kum": ("Kum", 0.6, "K"),
    "bygg": ("Bygg", 3.0, "B"),
    "gjerde": ("Gjerde / stolpe", 0.5, "G"),
    "anna": ("Anna hindring", 1.0, "!"),
}


class Objekt:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.items = []
        try:
            self.items = json.loads(self.path.read_text("utf-8")).get("objekt", [])
        except FileNotFoundError:
            pass
        except Exception as e:
            print("Kunne ikkje lese objekt.json:", e)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"objekt": self.items}, indent=1, ensure_ascii=False), "utf-8")
        tmp.replace(self.path)

    def listing(self):
        with self.lock:
            return [dict(o) for o in self.items]

    def save(self, d):
        lat, lng = float(d["lat"]), float(d["lng"])
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError("Ugyldig koordinat.")
        typ = d.get("type") if d.get("type") in OBJ_TYPES else "anna"
        r = d.get("radius")
        r = OBJ_TYPES[typ][1] if r in (None, "") else float(str(r).replace(",", "."))
        if not (0 < r <= 30):
            raise ValueError("Radius må vere mellom 0 og 30 m.")
        with self.lock:
            old = next((o for o in self.items if o["id"] == d.get("id")), None)
            o = old or {"id": uuid.uuid4().hex[:8], "created": time.strftime("%Y-%m-%d %H:%M")}
            o.update(type=typ, name=str(d.get("name") or "").strip()[:60] or OBJ_TYPES[typ][0], lat=round(lat, 8), lng=round(lng, 8),
                     radius=round(r, 2), note=str(d.get("note") or "")[:120], source=str(d.get("source") or o.get("source") or "kart")[:40],
                     updated=time.strftime("%Y-%m-%d %H:%M:%S"))
            if not old:
                self.items.append(o)
            self._save()
            return dict(o)

    def delete(self, oid):
        with self.lock:
            self.items = [o for o in self.items if o["id"] != oid]
            self._save()
