# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Eigen LiDAR inn i terrengmodellen (v1.6.95): LAS, LAZ og XYZ/CSV/TXT → høgderutenett (barmark).

  analyse_pointcloud(path, filename, hint)  → (rutenett, info, feil, åtvaringar) – same form som analyse_geotiff

LAS blir lese direkte (header, VLR med koordinatsystem, punkt som minnekartlagd tabell – store filer går fint).
LAZ (komprimert LAS) treng laspy (BSD-2) + lazrs (MIT). Dei blir installerte med pip første gong ei LAZ-fil blir
opna (krev nett éin gong), som pyrtklib i rtkmotor.py. Headeren og koordinatsystemet i LAZ blir lese direkte.

Bakkepunkt (klasse 2) blir brukte når fila er klassifisert: snitthøgda i kvar rute. Utan klassifisering: snittet av
punkta som ligg mindre enn BAND over lågaste punkt i ruta (to gjennomgangar) – lågaste punkt åleine ligg for lågt i
bratt terreng. Støy (klasse 7 og 18) blir alltid hoppa over. Åtvaring når fila ikkje er klassifisert. Små hol blir fylte frå nabo-
rutene. Høgdesystemet blir lese frå fila når det står der (NN2000 = EPSG 5941, 5972/5973/5975); elles vel føraren
ved import om høgdene er NN2000 eller ellipsoidiske (EUREF89) – ellipsoidiske blir gjorde om med geoiden.
"""
import math, re, struct, subprocess, sys
from pathlib import Path

import numpy as np

LASPY_PINS = ("laspy==2.7.0", "lazrs==0.8.2")
MAX_CELLS = 10_000_000          # tak på rutenettet (minne): oppløysinga blir grovare om området er stort
CHUNK = 2_000_000               # punkt per bit
RES_STEPS = (0.25, 0.5, 1.0, 2.0, 5.0)
NOISE = (7, 18)                 # ASPRS: låg og høg støy
GROUND = 2
BAND = 0.4                      # m over lågaste punkt i ruta som blir rekna som bakke (uklassifisert sky)
UTM_EPSG = {25832: 32, 25833: 33, 25835: 35, 32632: 32, 32633: 33, 32635: 35, 5972: 32, 5973: 33, 5975: 35}
_laspy = [None]


def ensure_laspy(install=True):
    """laspy + lazrs for LAZ. Installer med pip første gong. Returnerer (modul eller None, feiltekst)."""
    if _laspy[0] is not None:
        return _laspy[0], ""
    try:
        import laspy
        import lazrs  # noqa: F401 – laspy brukar han til LAZ
        _laspy[0] = laspy
        return laspy, ""
    except Exception as e:
        err = f"laspy/lazrs manglar ({e})"
    if not install:
        return None, err
    try:
        p = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet", *LASPY_PINS],
                           capture_output=True, text=True, timeout=600)
        if p.returncode != 0:
            return None, "Klarte ikkje å installere LAZ-lesaren (laspy/lazrs): " + (p.stderr or p.stdout).strip()[-300:]
        import importlib
        importlib.invalidate_caches()
        import laspy
        import lazrs  # noqa: F401
        _laspy[0] = laspy
        return laspy, ""
    except Exception as e:
        return None, f"Klarte ikkje å installere LAZ-lesaren (laspy/lazrs): {e}. Lagre fila som LAS i staden."


# ---------------------------------------------------------------------------------------------
# LAS/LAZ-header og koordinatsystem
# ---------------------------------------------------------------------------------------------
def read_las_header(path):
    with open(path, "rb") as f:
        b = f.read(375)
        if b[:4] != b"LASF":
            raise ValueError("Ikkje ei LAS/LAZ-fil (manglar «LASF»).")
        vmaj, vmin = b[24], b[25]
        hsize, = struct.unpack_from("<H", b, 94)
        off_pts, nvlr = struct.unpack_from("<II", b, 96)
        fmt_raw = b[104]
        reclen, = struct.unpack_from("<H", b, 105)
        npts, = struct.unpack_from("<I", b, 107)
        sx, sy, sz, ox, oy, oz = struct.unpack_from("<6d", b, 131)
        maxx, minx, maxy, miny, maxz, minz = struct.unpack_from("<6d", b, 179)
        evlr_start, nevlr = 0, 0
        if (vmaj, vmin) >= (1, 4) and hsize >= 375:
            evlr_start, nevlr = struct.unpack_from("<QI", b, 235)
            n64, = struct.unpack_from("<Q", b, 247)
            if n64:
                npts = n64
        h = dict(version=f"{vmaj}.{vmin}", off_pts=off_pts, fmt=fmt_raw & 0x3F, laz=bool(fmt_raw & 0xC0), reclen=reclen,
                 npts=int(npts), scale=(sx, sy, sz), offset=(ox, oy, oz), bounds=(minx, miny, minz, maxx, maxy, maxz), vlrs=[])
        f.seek(hsize)
        for _ in range(nvlr):
            vh = f.read(54)
            if len(vh) < 54:
                break
            user = vh[2:18].split(b"\0")[0].decode("latin1", "ignore")
            rid, ln = struct.unpack_from("<HH", vh, 18)
            h["vlrs"].append((user, rid, f.read(ln)))
        if evlr_start and nevlr:
            f.seek(evlr_start)
            for _ in range(nevlr):
                vh = f.read(60)
                if len(vh) < 60:
                    break
                user = vh[2:18].split(b"\0")[0].decode("latin1", "ignore")
                rid, ln = struct.unpack_from("<HQ", vh, 18)
                h["vlrs"].append((user, rid, f.read(min(ln, 1 << 20))))
    return h


def crs_from_vlrs(vlrs):
    """(epsg, vdatum) frå GeoKey-katalogen (34735) eller WKT (2112). vdatum: "NN2000", "NN54" eller None."""
    epsg, vd = None, None
    for user, rid, data in vlrs:
        if user != "LASF_Projection":
            continue
        if rid == 34735 and len(data) >= 8:
            v = struct.unpack(f"<{len(data) // 2}H", data[:len(data) // 2 * 2])
            keys = {}
            for i in range(v[3]):
                k, loc, cnt, val = v[4 + i * 4: 8 + i * 4]
                if loc == 0:
                    keys[k] = val
            epsg = epsg or keys.get(3072)
            vd = vd or {5941: "NN2000", 5776: "NN54"}.get(keys.get(4096))
        elif rid == 2112:
            wkt = data.decode("latin1", "ignore")
            codes = [int(c) for c in re.findall(r'(?:AUTHORITY|ID)\[\s*"EPSG"\s*,\s*"?(\d+)', wkt)]
            for c in codes:
                if c in UTM_EPSG and not epsg:
                    epsg = c
            if not epsg:
                m = re.search(r"UTM[ _]zone[ _](3[235])N", wkt, re.I)
                if m:
                    z = int(m.group(1))
                    epsg = ({32: 32632, 33: 32633, 35: 32635} if "WGS" in wkt.upper() and "ETRS" not in wkt.upper() and "EUREF" not in wkt.upper()
                            else {32: 25832, 33: 25833, 35: 25835})[z]
            if 5941 in codes or {5972, 5973, 5975} & set(codes) or "NN2000" in wkt.upper():
                vd = "NN2000"
            elif 5776 in codes or "NN54" in wkt.upper():
                vd = vd or "NN54"
    if epsg in (5972, 5973, 5975):
        vd = "NN2000"
    return epsg, vd


def epsg_from_name(name):
    """Sone frå filnamnet: «utm32», «_33_», «25833», «euref89_utm33» o.l."""
    n = Path(name or "").name.lower()
    m = re.search(r"(?:258|326|59)(3[235]|7[235])\b", n)
    if m:
        z = int(m.group(1)) if m.group(1).startswith("3") else {72: 32, 73: 33, 75: 35}[int(m.group(1))]
        return {32: 25832, 33: 25833, 35: 25835}[z]
    m = re.search(r"utm[ _-]?(3[235])", n) or re.search(r"(?:^|[_-])(3[235])(?:[_-]|$)", Path(n).stem)
    return {"32": 25832, "33": 25833, "35": 25835}[m.group(1)] if m else None


def epsg_from_hint(cx, cy, hint, utm_inverse):
    """Utan koordinatsystem: vel den sona der midten av fila ligg nær maskina (innan 30 km)."""
    if not hint or hint[0] is None:
        return None
    lat0, lon0 = hint
    for z, e in ((32, 25832), (33, 25833), (35, 25835)):
        try:
            la, lo = utm_inverse(cx, cy, z)
        except Exception:
            continue
        d = math.hypot((la - lat0) * 111.32, (lo - lon0) * 111.32 * math.cos(math.radians(lat0)))
        if d < 30:
            return e
    return None


# ---------------------------------------------------------------------------------------------
# Punkt
# ---------------------------------------------------------------------------------------------
def iter_las(path, h):
    """(x, y, z, klasse) i bitar frå ei ukomprimert LAS-fil (minnekartlagd – heile fila blir aldri lesen inn)."""
    cls_off = 15 if h["fmt"] <= 5 else 16
    dt = np.dtype({"names": ["X", "Y", "Z", "c"], "formats": ["<i4", "<i4", "<i4", "u1"],
                   "offsets": [0, 4, 8, cls_off], "itemsize": h["reclen"]})
    mm = np.memmap(path, dtype=dt, mode="r", offset=h["off_pts"], shape=(h["npts"],))
    (sx, sy, sz), (ox, oy, oz) = h["scale"], h["offset"]
    for i in range(0, h["npts"], CHUNK):
        p = mm[i:i + CHUNK]
        c = np.asarray(p["c"])
        yield p["X"] * sx + ox, p["Y"] * sy + oy, p["Z"] * sz + oz, (c & 0x1F) if h["fmt"] <= 5 else c


def iter_laz(path):
    laspy, err = ensure_laspy()
    if laspy is None:
        raise RuntimeError(err)
    with laspy.open(str(path)) as rd:
        for p in rd.chunk_iterator(CHUNK):
            yield np.asarray(p.x), np.asarray(p.y), np.asarray(p.z), np.asarray(p.classification, dtype=np.uint8)


def read_xyz(path):
    """Tekstfil med austing, nording, høgd (mellomrom, komma, semikolon eller tab; desimalkomma ved semikolon)."""
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s or s[0] in "#/":
                continue
            if ";" in s:
                s = s.replace(",", ".").replace(";", " ")
            else:
                s = s.replace(",", " ")
            parts = s.split()
            if len(parts) < 3:
                continue
            try:
                rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError:
                continue  # overskriftsline o.l.
    if not rows:
        raise ValueError("Fann ingen punkt (venta tre tal per linje: austing nording høgd).")
    a = np.asarray(rows, dtype=np.float64)
    swapped = False
    if np.median(a[:, 0]) > 1e6 > np.median(a[:, 1]):  # nording først (N E H) – byt om
        a[:, [0, 1]] = a[:, [1, 0]]
        swapped = True
    return a, swapped


# ---------------------------------------------------------------------------------------------
# Rutenett
# ---------------------------------------------------------------------------------------------
def choose_res(npts, area, ground_share=0.5):
    """Finaste oppløysing med minst ca. 2 bakkepunkt per rute, og under MAX_CELLS."""
    dens = max(npts * ground_share / max(area, 1.0), 1e-9)
    for r in RES_STEPS:
        if r * r * dens >= 2 and area / (r * r) <= MAX_CELLS:
            return r
    r = RES_STEPS[-1]
    while area / (r * r) > MAX_CELLS:
        r *= 2
    return r


class Gridder:
    def __init__(self, minx, miny, maxx, maxy, res):
        self.res = res
        self.x0 = math.floor(minx / res) * res
        self.y0 = math.ceil(maxy / res) * res
        self.nx = int(math.floor((maxx - self.x0) / res)) + 1
        self.ny = int(math.floor((self.y0 - miny) / res)) + 1
        n = self.nx * self.ny
        self.gsum = np.zeros(n, np.float64)
        self.gcnt = np.zeros(n, np.int32)
        self.amin = np.full(n, np.inf, np.float32)
        self.n_all = self.n_ground = self.n_noise = 0
        self.classes = {}

    def add(self, x, y, z, c):
        c = np.asarray(c, dtype=np.uint8)
        u, k = np.unique(c, return_counts=True)
        for a, b in zip(u.tolist(), k.tolist()):
            self.classes[a] = self.classes.get(a, 0) + b
        col = np.floor((np.asarray(x) - self.x0) / self.res).astype(np.int64)
        row = np.floor((self.y0 - np.asarray(y)) / self.res).astype(np.int64)
        z = np.asarray(z, dtype=np.float64)
        ok = (col >= 0) & (col < self.nx) & (row >= 0) & (row < self.ny) & np.isfinite(z) & (z > -500) & (z < 9000)
        noise = np.isin(c, NOISE)
        self.n_noise += int((ok & noise).sum())
        ok &= ~noise
        idx = row * self.nx + col
        self.n_all += int(ok.sum())
        g = ok & (c == GROUND)
        if g.any():
            self.n_ground += int(g.sum())
            self.gsum += np.bincount(idx[g], weights=z[g], minlength=self.gsum.size)
            self.gcnt += np.bincount(idx[g], minlength=self.gcnt.size).astype(np.int32)
        if ok.any():  # lågaste punkt per rute (reserve når fila ikkje er klassifisert)
            ii, zz = idx[ok], z[ok].astype(np.float32)
            o = np.argsort(ii, kind="stable")
            ii, zz = ii[o], zz[o]
            starts = np.flatnonzero(np.r_[True, ii[1:] != ii[:-1]])
            mins = np.minimum.reduceat(zz, starts)
            cells = ii[starts]
            self.amin[cells] = np.minimum(self.amin[cells], mins)

    def use_ground(self):
        return self.n_ground >= max(1000, 0.02 * self.n_all)

    def add_low(self, x, y, z, c):
        """Andre gjennomgang (uklassifisert sky): summer punkta som ligg mindre enn BAND over lågaste punkt i ruta."""
        if not hasattr(self, "lsum"):
            self.lsum = np.zeros(self.amin.size, np.float64)
            self.lcnt = np.zeros(self.amin.size, np.int32)
        c = np.asarray(c, dtype=np.uint8)
        col = np.floor((np.asarray(x) - self.x0) / self.res).astype(np.int64)
        row = np.floor((self.y0 - np.asarray(y)) / self.res).astype(np.int64)
        z = np.asarray(z, dtype=np.float64)
        ok = (col >= 0) & (col < self.nx) & (row >= 0) & (row < self.ny) & np.isfinite(z) & ~np.isin(c, NOISE)
        idx = row * self.nx + col
        ok[ok] &= z[ok] <= self.amin[idx[ok]] + BAND
        self.lsum += np.bincount(idx[ok], weights=z[ok], minlength=self.lsum.size)
        self.lcnt += np.bincount(idx[ok], minlength=self.lcnt.size).astype(np.int32)

    def grid(self):
        if self.use_ground():
            g = np.where(self.gcnt > 0, self.gsum / np.maximum(self.gcnt, 1), np.nan)
        elif hasattr(self, "lsum"):
            g = np.where(self.lcnt > 0, self.lsum / np.maximum(self.lcnt, 1), np.nan)
        else:
            g = np.where(np.isfinite(self.amin), self.amin, np.nan)
        return fill_holes(g.reshape(self.ny, self.nx).astype(np.float32)), self.use_ground()


def fill_holes(g, rounds=3):
    """Fyll små hol (ruter utan punkt) med snittet av naborutene – berre der minst 3 av 8 naboar har verdi."""
    for _ in range(rounds):
        nan = np.isnan(g)
        if not nan.any():
            break
        p = np.pad(g, 1, constant_values=np.nan)
        s = np.zeros(g.shape, np.float64)
        n = np.zeros(g.shape, np.int32)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                v = p[1 + dr:1 + dr + g.shape[0], 1 + dc:1 + dc + g.shape[1]]
                f = np.isfinite(v)
                s += np.where(f, v, 0)
                n += f
        fill = nan & (n >= 3)
        if not fill.any():
            break
        g = g.copy()
        g[fill] = (s[fill] / n[fill]).astype(np.float32)
    return g


# ---------------------------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------------------------
def analyse_pointcloud(path, filename, hint=None, utm_inverse=None, crs_name=None):
    """Returnerer (rutenett, info, feil, åtvaringar) for LAS/LAZ/XYZ. hint = (lat, lon) til maskina, eller None."""
    ext = Path(filename).suffix.lower()
    errors, warns = [], []
    info = {"format": {".las": "LAS (punktsky)", ".laz": "LAZ (komprimert punktsky)"}.get(ext, "XYZ (punkt i tekst)")}
    try:
        if ext in (".las", ".laz"):
            h = read_las_header(path)
            if ext == ".las" and h["laz"]:
                ext = ".laz"
            if ext == ".laz" and not h["laz"]:
                ext = ".las"
            minx, miny, minz, maxx, maxy, maxz = h["bounds"]
            npts = h["npts"]
            epsg, vd = crs_from_vlrs(h["vlrs"])
            info.update(lasVersion=h["version"], pointFormat=h["fmt"])
            src = (lambda: iter_laz(path)) if ext == ".laz" else (lambda: iter_las(path, h))
        else:
            a, swapped = read_xyz(path)
            if swapped:
                warns.append("Kolonnane såg ut som nording, austing – dei er bytte om til austing, nording.")
            minx, miny = a[:, 0].min(), a[:, 1].min()
            maxx, maxy = a[:, 0].max(), a[:, 1].max()
            npts, epsg, vd = len(a), None, None
            src = lambda: iter([(a[:, 0], a[:, 1], a[:, 2], np.full(len(a), GROUND, np.uint8))])
    except Exception as e:
        return None, info, [f"Kunne ikkje lese fila: {e}"], warns
    if npts == 0 or not (maxx > minx and maxy > miny):
        return None, info, ["Fila inneheld ingen punkt."], warns
    if not epsg:
        epsg = epsg_from_name(filename)
        if epsg:
            warns.append(f"Koordinatsystemet står ikkje i fila – tolka frå filnamnet som {crs_name(epsg)}. Sjekk at laget ligg rett på kartet.")
        elif utm_inverse:
            epsg = epsg_from_hint((minx + maxx) / 2, (miny + maxy) / 2, hint, utm_inverse)
            if epsg:
                warns.append(f"Koordinatsystemet står ikkje i fila – tolka ut frå posisjonen til maskina som {crs_name(epsg)}. "
                             "Sjekk at laget ligg rett på kartet.")
    if not epsg:
        return None, info, ["Fila manglar koordinatsystem. Eksporter med EUREF89 UTM 32 eller 33, eller skriv sona i filnamnet "
                            "(t.d. «bakke_utm32.laz»)."], warns
    if epsg not in UTM_EPSG:
        return None, info, [f"Koordinatsystemet (EPSG:{epsg}) er ikkje støtta. Bruk EUREF89 UTM 32 eller 33."], warns
    if not (100000 < minx and maxx < 900000 and 6.3e6 < miny and maxy < 8.0e6):
        return None, info, ["Koordinatane passar ikkje med UTM i Noreg – sjekk koordinatsystem og kolonnerekkjefølgje."], warns
    area = (maxx - minx) * (maxy - miny)
    res = choose_res(npts, area, 0.5 if ext in (".las", ".laz") else 1.0)
    G = Gridder(minx, miny, maxx, maxy, res)
    try:
        for x, y, z, c in src():
            G.add(x, y, z, c)
        if not G.use_ground():  # uklassifisert: andre gjennomgang for snittet nær botnen i kvar rute
            for x, y, z, c in src():
                G.add_low(x, y, z, c)
    except Exception as e:
        return None, info, [f"Kunne ikkje lese punkta: {e}"], warns
    grid, ground = G.grid()
    valid = np.isfinite(grid)
    frac = float(valid.mean()) if grid.size else 0.0
    if not valid.any():
        return None, info, ["Ingen brukbare punkt i fila (berre støy eller utanfor området)."], warns
    if ext in (".las", ".laz"):
        if ground:
            info["ground"] = True
        else:
            warns.append("Punktskya er ikkje klassifisert (ingen bakkepunkt, klasse 2). Punkta nærast botnen i kvar rute er brukte – tre, "
                         "bygg og maskiner kan gi for høgt terreng. Klassifiser bakkepunkt før import om du kan.")
    if G.n_noise:
        info["noise"] = G.n_noise
    if frac < 0.5:
        warns.append(f"Berre {frac:.0%} av området har punkt (resten er tomt). Det er normalt for skanning av smale bakkar.")
    if vd == "NN54":
        warns.append("Høgdesystemet er NN54 (gammalt). Det skil ofte 10–20 cm frå NN2000 – bruk helst NN2000.")
    info.update(epsg=epsg, crs=crs_name(epsg), zone=UTM_EPSG[epsg], vdatum=vd or "ukjent",
                x0=G.x0, y0=G.y0, dx=res, dy=res, nx=G.nx, ny=G.ny, res=res, valid=round(frac, 3),
                hmin=float(np.nanmin(grid)), hmax=float(np.nanmax(grid)), area_km2=round(float(valid.sum()) * res * res / 1e6, 3),
                points=int(npts), groundPoints=int(G.n_ground), usedPoints=int(G.n_ground if ground else G.n_all))
    if vd is None:
        warns.append("Høgdesystemet står ikkje i fila. Vel ved import om høgdene er NN2000 eller ellipsoidiske (rå GPS-høgd, "
                     "vanleg frå eiga drone-/GNSS-skanning).")
    return grid, info, errors, warns
