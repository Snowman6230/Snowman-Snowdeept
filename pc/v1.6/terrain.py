# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""
SNOWMAN Terrain Engine (v1.6)

Terrengbibliotek med fleire lag (legg til, erstatt, av/på, prioritet, slett), oppslag av terrenghøgd
ved GNSS-posisjon, og utrekning av snødjupne. Sjå docs/TERRAIN-ENGINE.md.

Internt blir kvart lag lagra som eit rutenett (numpy .npy, minnekartlagt – berre det som trengst
blir lese frå disk) + meta.json. Opplasta filer blir analyserte før import.

Avhengigheiter: numpy, tifffile, imagecodecs (alle BSD-lisens).
"""
import json, math, os, shutil, threading, time, uuid
from pathlib import Path

try:
    import numpy as np
    import tifffile
    AVAILABLE, IMPORT_ERROR = True, ""
except Exception as e:  # tenesta skal framleis køyre utan terrengmotor
    np = tifffile = None
    AVAILABLE, IMPORT_ERROR = False, f"Terrengmotor manglar bibliotek ({e}). Køyr INSTALL / pip install -r requirements.txt"

# ---------------------------------------------------------------------------------------------
# Koordinatar: GRS80 (EUREF89/ETRS89) ↔ UTM. Krüger-seriar (Karney 2011), mm-nøyaktig i sona.
# ---------------------------------------------------------------------------------------------
_A, _F = 6378137.0, 1 / 298.257222101
_K0 = 0.9996
_n = _F / (2 - _F)
_AR = _A / (1 + _n) * (1 + _n**2 / 4 + _n**4 / 64)
_ALPHA = (_n / 2 - 2 * _n**2 / 3 + 5 * _n**3 / 16, 13 * _n**2 / 48 - 3 * _n**3 / 5, 61 * _n**3 / 240)
_BETA = (_n / 2 - 2 * _n**2 / 3 + 37 * _n**3 / 96, _n**2 / 48 + _n**3 / 15, 17 * _n**3 / 480)
_DELTA = (2 * _n - 2 * _n**2 / 3 - 2 * _n**3, 7 * _n**2 / 3 - 8 * _n**3 / 5, 56 * _n**3 / 15)


def utm_forward(lat, lon, zone):
    """Breidd/lengd (grader) → (austing, nording) i UTM-sone `zone` (nordlege halvkule)."""
    lon0 = math.radians(zone * 6 - 183)
    phi, lam = math.radians(lat), math.radians(lon) - lon0
    e = math.sqrt(_F * (2 - _F))
    t = math.sinh(math.atanh(math.sin(phi)) - e * math.atanh(e * math.sin(phi)))
    xi_, eta_ = math.atan2(t, math.cos(lam)), math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    xi, eta = xi_, eta_
    for j, a in enumerate(_ALPHA, 1):
        xi += a * math.sin(2 * j * xi_) * math.cosh(2 * j * eta_)
        eta += a * math.cos(2 * j * xi_) * math.sinh(2 * j * eta_)
    return 500000 + _K0 * _AR * eta, _K0 * _AR * xi


def utm_inverse(E, N, zone):
    """(austing, nording) i UTM-sone → (breidd, lengd) i grader."""
    xi, eta = N / (_K0 * _AR), (E - 500000) / (_K0 * _AR)
    xi_, eta_ = xi, eta
    for j, b in enumerate(_BETA, 1):
        xi_ -= b * math.sin(2 * j * xi) * math.cosh(2 * j * eta)
        eta_ -= b * math.cos(2 * j * xi) * math.sinh(2 * j * eta)
    chi = math.asin(math.sin(xi_) / math.cosh(eta_))
    phi = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(_DELTA, 1))
    lon = math.radians(zone * 6 - 183) + math.atan2(math.sinh(eta_), math.cos(xi_))
    return math.degrees(phi), math.degrees(lon)


# Godtekne koordinatsystem → UTM-sone. ETRS89/EUREF89 og WGS84 UTM, også samansette med NN2000.
CRS_ZONE = {25832: 32, 25833: 33, 25835: 35, 32632: 32, 32633: 33, 32635: 35, 5972: 32, 5973: 33, 5975: 35}
CRS_NAME = {25832: "EUREF89 UTM 32N", 25833: "EUREF89 UTM 33N", 25835: "EUREF89 UTM 35N",
            32632: "WGS84 UTM 32N", 32633: "WGS84 UTM 33N", 32635: "WGS84 UTM 35N",
            5972: "EUREF89 UTM 32N + NN2000", 5973: "EUREF89 UTM 33N + NN2000", 5975: "EUREF89 UTM 35N + NN2000"}
VDATUM = {5941: "NN2000", 5776: "NN54"}
TYPES = {"barmark": "Barmark (terreng utan snø)", "malflate": "Målflate", "snoflate": "Snøflate (oppmåling)"}

# ---------------------------------------------------------------------------------------------
# GeoTIFF-analyse
# ---------------------------------------------------------------------------------------------

def _geokeys(tag_value):
    v = list(tag_value or [])
    keys = {}
    if len(v) >= 4:
        for i in range(v[3]):
            k, loc, cnt, val = v[4 + i * 4: 8 + i * 4]
            if loc == 0:
                keys[k] = val
    return keys


def analyse_geotiff(path):
    """Les ei GeoTIFF-fil og returner (rutenett, info, feil, åtvaringar). Rutenett er None ved feil."""
    errors, warns, info = [], [], {"format": "GeoTIFF"}
    try:
        with tifffile.TiffFile(path) as tf:
            page = tf.pages[0]
            tags = {t.code: t.value for t in page.tags.values()}
            arr = page.asarray()
    except Exception as e:
        return None, info, [f"Kunne ikkje lese fila som GeoTIFF: {e}"], warns
    if arr.ndim == 3:
        arr = arr[..., 0] if arr.shape[-1] <= 4 else arr[0]
        warns.append("Fila har fleire band – berre det første blir brukt.")
    if arr.ndim != 2:
        return None, info, ["Fila er ikkje eit høgderutenett (feil dimensjonar)."], warns
    if not np.issubdtype(arr.dtype, np.number):
        return None, info, ["Fila inneheld ikkje talverdiar."], warns
    if arr.dtype == np.uint8 and arr.max() <= 255:
        errors.append("Fila ser ut som eit bilete (8-bit), ikkje høgdedata.")
    grid = arr.astype(np.float32)
    scale, tie, gk = tags.get(33550), tags.get(33922), _geokeys(tags.get(34735))
    if not scale or not tie:
        errors.append("Fila manglar georeferanse (pikselstorleik/plassering) – kan ikkje brukast.")
        return None, info, errors, warns
    dx, dy = float(scale[0]), float(scale[1])
    i0, j0, x_t, y_t = float(tie[0]), float(tie[1]), float(tie[3]), float(tie[4])
    if 34264 in tags:
        warns.append("Fila brukar transformasjonsmatrise – rotasjon blir ignorert.")
    x0, y0 = x_t - i0 * dx, y_t + j0 * dy  # øvre venstre hjørne av piksel (0,0)
    if gk.get(1025) == 2:  # RasterPixelIsPoint: tiepunkt er midt i pikselen
        x0, y0 = x0 - dx / 2, y0 + dy / 2
    epsg = gk.get(3072)
    if not epsg or epsg == 32767:
        errors.append("Fila manglar koordinatsystem – kan ikkje brukast. Eksporter med EUREF89 UTM 32 eller 33.")
    elif epsg not in CRS_ZONE:
        errors.append(f"Koordinatsystemet (EPSG:{epsg}) er ikkje støtta. Bruk EUREF89 UTM 32 eller 33 (EPSG:25832/25833).")
    vd = gk.get(4096)
    if epsg in (5972, 5973, 5975):
        vd = 5941
    if vd == 5941:
        info["vdatum"] = "NN2000"
    elif vd == 5776:
        info["vdatum"] = "NN54"
        warns.append("Høgdesystemet er NN54 (gammalt). Det skil ofte 10–20 cm frå NN2000 – bruk helst NN2000.")
    else:
        info["vdatum"] = "ukjent"
        warns.append("Høgdesystem er ikkje oppgitt i fila. Stadfest at høgdene er NN2000 før import.")
    nod = tags.get(42113)
    if nod not in (None, ""):
        try:
            nv = float(str(nod).strip("\x00 "))
            grid[grid == nv] = np.nan
            info["nodata"] = nv
        except ValueError:
            pass
    grid[(grid < -500) | (grid > 9000)] = np.nan  # openberre ugyldige verdiar
    valid = np.isfinite(grid)
    frac = float(valid.mean()) if grid.size else 0
    if frac == 0:
        errors.append("Fila inneheld ingen gyldige høgdeverdiar.")
    elif frac < 0.5:
        warns.append(f"Berre {frac:.0%} av fila har høgdeverdiar (resten er tomt/nodata).")
    if dx > 2:
        warns.append(f"Grov oppløysing ({dx:g} m). Tilrådd er 0,25–1 m.")
    if abs(dx - dy) > 1e-6:
        warns.append(f"Ulik pikselstorleik i x/y ({dx:g} × {dy:g} m).")
    ny, nx = grid.shape
    info.update(epsg=epsg, crs=CRS_NAME.get(epsg, f"EPSG:{epsg}"), zone=CRS_ZONE.get(epsg), x0=x0, y0=y0, dx=dx, dy=dy,
                nx=nx, ny=ny, res=dx, valid=round(frac, 3),
                hmin=float(np.nanmin(grid)) if frac else None, hmax=float(np.nanmax(grid)) if frac else None,
                area_km2=round(nx * dx * ny * dy / 1e6, 3))
    if info.get("zone"):
        info["outline"] = _outline(info)
        if info["hmin"] is not None and (info["hmin"] < -50 or info["hmax"] > 2500):
            warns.append("Høgdeverdiane ser uvanlege ut for norsk terreng – sjekk høgdesystem og einingar (meter).")
    return (None if errors else grid), info, errors, warns


# ---------------------------------------------------------------------------------------------
# Topocad DTM (.dtm) – trekantmodell (TIN) frå landmålingsprogrammet Topocad (Adtollo)
# Binært format, tolka 2026-10-04 frå filer levert til prosjektet (versjon 3):
#   "Topocad DTM File", "TDTMBase", versjon, bbox (N,E,N,E,H,H),
#   punkt: [0 N][0 E][0 H] + attributt (id, kode, ...),
#   brotlinjenodar: (flagg, punktindeks, ?, førre, neste),
#   trekantar: (flagg, p1, p2, p3, nabo1, nabo2, nabo3) med 1-baserte punktindeksar,
#   til slutt innstillingar som tekst, mellom anna ProjPlaneEPSG.
# ---------------------------------------------------------------------------------------------
import struct


def parse_topocad(path):
    b = Path(path).read_bytes()
    if b[9:25] != b"Topocad DTM File" or b"TDTMBase" not in b[:60]:
        raise ValueError("Ikkje ei Topocad DTM-fil.")
    i = b.index(b"TDTMBase") + 8
    ver = struct.unpack_from("<i", b, i)[0]; i += 4
    if ver != 3:
        raise ValueError(f"Topocad DTM versjon {ver} er ikkje testa (berre versjon 3).")
    i += 1 + 48  # bbox
    _, npts = struct.unpack_from("<ii", b, i); i += 8
    P = np.empty((npts, 3), np.float64)
    for k in range(npts):
        for j in range(3):
            if b[i] != 0:
                raise ValueError(f"Uventa punktformat ved punkt {k + 1}.")
            P[k, j] = struct.unpack_from("<d", b, i + 1)[0]; i += 9
        _, _, _, sl = struct.unpack_from("<iiii", b, i); i += 16 + sl
        i += 4; d = b[i]; i += 1
        if d:
            sl2 = struct.unpack_from("<i", b, i)[0]; i += 4 + sl2
    _, nn = struct.unpack_from("<ii", b, i); i += 8 + 20 * nn  # brotlinjer (alt med i trekantane)
    _, nt = struct.unpack_from("<ii", b, i); i += 8
    T = np.frombuffer(b, dtype="<i4", count=nt * 7, offset=i).reshape(nt, 7)
    tris = T[T[:, 0] == 1][:, 1:4] - 1  # synlege trekantar, 0-baserte indeksar
    if tris.size == 0 or tris.min() < 0 or tris.max() >= npts:
        raise ValueError("Trekantane i fila peikar utanfor punktlista.")
    epsg = None
    k = b.find(b"ProjPlaneEPSG", i)
    if k > 0:
        n = struct.unpack_from("<i", b, k + 13)[0]
        try:
            epsg = int(b[k + 17:k + 17 + n].decode("latin1"))
        except ValueError:
            epsg = None
    k = b.find(b"ProjPlaneName", i)
    pname = ""
    if k > 0:
        n = struct.unpack_from("<i", b, k + 13)[0]; pname = b[k + 17:k + 17 + n].decode("latin1", "ignore")
    # Topocad lagrar (N, E, H). Gjer om til (E, N, H).
    pts = np.column_stack([P[:, 1], P[:, 0], P[:, 2]])
    return pts, tris, epsg, pname, len(T) - len(tris), nn


def rasterize_tin(pts, tris, res):
    """Trekantmodell → rutenett (høgd i pikselmidten, NaN utanfor modellen)."""
    E, N, H = pts[:, 0], pts[:, 1], pts[:, 2]
    x0, y1 = math.floor(E.min() / res) * res, math.ceil(N.max() / res) * res
    nx, ny = int(math.ceil((E.max() - x0) / res)) + 1, int(math.ceil((y1 - N.min()) / res)) + 1
    grid = np.full((ny, nx), np.nan, np.float32)
    for a, bb, c in tris:
        xa, ya, xb, yb, xc, yc = E[a], N[a], E[bb], N[bb], E[c], N[c]
        den = (yb - yc) * (xa - xc) + (xc - xb) * (ya - yc)
        if abs(den) < 1e-9:
            continue
        c0, c1 = int((min(xa, xb, xc) - x0) / res), int((max(xa, xb, xc) - x0) / res) + 1
        r0, r1 = int((y1 - max(ya, yb, yc)) / res), int((y1 - min(ya, yb, yc)) / res) + 1
        cs, rs = np.arange(max(c0, 0), min(c1, nx)), np.arange(max(r0, 0), min(r1, ny))
        if not len(cs) or not len(rs):
            continue
        X, Y = np.meshgrid(x0 + (cs + 0.5) * res, y1 - (rs + 0.5) * res)
        l1 = ((yb - yc) * (X - xc) + (xc - xb) * (Y - yc)) / den
        l2 = ((yc - ya) * (X - xc) + (xa - xc) * (Y - yc)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if inside.any():
            sub = grid[rs[0]:rs[-1] + 1, cs[0]:cs[-1] + 1]
            sub[inside] = (l1 * H[a] + l2 * H[bb] + l3 * H[c])[inside]
    return grid, x0, y1, nx, ny


def analyse_topocad(path, res=0.5):
    errors, warns, info = [], [], {"format": "Topocad DTM (trekantmodell)"}
    try:
        pts, tris, epsg, pname, hidden, nbreak = parse_topocad(path)
    except Exception as e:
        return None, info, [f"Kunne ikkje lese Topocad-fila: {e}"], warns
    if not epsg:  # nokre filer manglar EPSG-kode – tolk sona frå namnet (t.d. «EUREF UTM 32»)
        import re as _re
        m = _re.search(r"UTM\s*(?:zone\s*)?(3[2-5])", pname or "", _re.I)
        if m:
            zone = int(m.group(1))
            epsg = {32: 25832, 33: 25833, 35: 25835}.get(zone) if "EUREF" in pname.upper() or "ETRS" in pname.upper() else {32: 32632, 33: 32633, 35: 32635}.get(zone)
            emin, emax = pts[:, 0].min(), pts[:, 0].max()
            nmin = pts[:, 1].min()
            if not (160000 < emin and emax < 840000 and 6.4e6 < nmin < 8.0e6):
                errors.append(f"Koordinatane passar ikkje med «{pname}» – sjekk koordinatsystemet i Topocad.")
            else:
                warns.append(f"EPSG-kode manglar i fila. Koordinatsystemet er tolka frå namnet «{pname}» som {CRS_NAME.get(epsg)}.")
    if not epsg:
        errors.append("Topocad-fila manglar koordinatsystem (ProjPlaneEPSG/ProjPlaneName).")
    elif epsg not in CRS_ZONE:
        errors.append(f"Koordinatsystemet ({pname or 'EPSG:' + str(epsg)}) er ikkje støtta. Bruk UTM 32/33.")
    if errors:
        return None, info, errors, warns
    grid, x0, y0, nx, ny = rasterize_tin(pts, tris, res)
    valid = np.isfinite(grid)
    frac = float(valid.mean())
    warns.append("Topocad-fila oppgir ikkje høgdesystem. Stadfest at høgdene er NN2000 før import.")
    if epsg in (32632, 32633, 32635):
        warns.append(f"Fila seier {CRS_NAME[epsg]}. Er koordinatane verkeleg WGS84 (ikkje EUREF89), ligg dei ca. 0,9 m forskyvde "
                     "– det gir høgdefeil i bratt terreng. Sjekk med eit kontrollpunkt.")
    info.update(vdatum="ukjent", epsg=epsg, crs=CRS_NAME.get(epsg), zone=CRS_ZONE[epsg], x0=x0, y0=y0, dx=res, dy=res,
                nx=nx, ny=ny, res=res, valid=round(frac, 3), hmin=float(np.nanmin(grid)), hmax=float(np.nanmax(grid)),
                area_km2=round(float(valid.sum()) * res * res / 1e6, 3),
                points=int(len(pts)), triangles=int(len(tris)), breaklines=int(nbreak))
    info["outline"] = _outline(info)
    if len(pts) < 200:
        warns.append(f"Modellen har berre {len(pts)} punkt – grov og passar best som oversikt, ikkje til snødjupnemåling.")
    return grid, info, errors, warns


def _outline(m):
    """Omrisset av laget som breidd/lengd-polygon (rotert i forhold til kartet når sona ikkje passar)."""
    x1, y1 = m["x0"] + m["nx"] * m["dx"], m["y0"] - m["ny"] * m["dy"]
    return [list(utm_inverse(x, y, m["zone"])) for x, y in ((m["x0"], m["y0"]), (x1, m["y0"]), (x1, y1), (m["x0"], y1))]


# ---------------------------------------------------------------------------------------------
# Terrengbibliotek
# ---------------------------------------------------------------------------------------------
class TerrainLibrary:
    def __init__(self, root):
        self.root = Path(root)
        self.layers = {}  # id → meta
        self.grids = {}  # id → minnekartlagt rutenett
        self.lock = threading.RLock()
        self.pending = {}  # token → analyse av opplasta fil som ventar på import
        if AVAILABLE:
            self.root.mkdir(parents=True, exist_ok=True)
            self._load()

    def _load(self):
        for d in self.root.iterdir():
            mf = d / "meta.json"
            if d.is_dir() and mf.exists():
                try:
                    self.layers[d.name] = json.loads(mf.read_text("utf-8"))
                except Exception:
                    pass

    def _save_meta(self, lid):
        (self.root / lid / "meta.json").write_text(json.dumps(self.layers[lid], indent=1), "utf-8")

    def _grid(self, lid):
        g = self.grids.get(lid)
        if g is None:
            g = self.grids[lid] = np.load(self.root / lid / "grid.npy", mmap_mode="r")
        return g

    def listing(self):
        with self.lock:
            return sorted(self.layers.values(), key=lambda m: -m["priority"])

    # --- opplasting ---
    def analyse(self, tmp_path, filename):
        ext = Path(filename).suffix.lower()
        if ext in (".tif", ".tiff"):
            grid, info, errors, warns = analyse_geotiff(tmp_path)
        elif ext == ".dtm":
            grid, info, errors, warns = analyse_topocad(tmp_path)
        elif ext in (".las", ".laz", ".xyz", ".csv", ".txt"):
            grid, info, errors, warns = None, {"format": ext[1:].upper()}, [
                f"{ext[1:].upper()} blir støtta frå v1.7. Bruk GeoTIFF (.tif) inntil vidare, t.d. frå hoydedata.no."], []
        else:
            grid, info, errors, warns = None, {"format": ext[1:].upper() or "ukjent"}, [
                "Formatet blir ikkje godteke. Bruk GeoTIFF (.tif) med barmark i EUREF89 UTM 32/33 og NN2000."], []
        token = None
        if grid is not None:
            token = uuid.uuid4().hex
            with self.lock:
                self.pending = {k: v for k, v in self.pending.items() if time.time() - v["t"] < 3600}
                self.pending[token] = {"grid": grid, "info": info, "warns": warns, "file": filename, "t": time.time()}
        info.pop("outline_utm", None)
        return {"ok": grid is not None, "token": token, "file": filename, "info": info, "errors": errors, "warnings": warns}

    def import_pending(self, token, name, ltype="barmark", priority=None, replace_id=None, source="", vdatum_confirmed=False):
        with self.lock:
            p = self.pending.pop(token, None)
            if not p:
                raise ValueError("Analysen er utgått – last opp fila på nytt.")
            if ltype not in TYPES:
                raise ValueError("Ukjend type terreng.")
            if replace_id:
                if replace_id not in self.layers:
                    raise ValueError("Laget som skulle erstattast finst ikkje.")
                lid, old = replace_id, self.layers[replace_id]
                vdir = self.root / lid / "versjonar" / time.strftime("%Y%m%d-%H%M%S")
                vdir.mkdir(parents=True, exist_ok=True)
                self.grids.pop(lid, None)
                for f in ("grid.npy", "meta.json"):
                    if (self.root / lid / f).exists():
                        shutil.move(str(self.root / lid / f), str(vdir / f))
                priority, versions = old["priority"], old.get("versions", []) + [vdir.name]
                name = name or old["name"]
            else:
                lid, versions = time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6], []
                if priority is None:
                    priority = max([m["priority"] for m in self.layers.values()] + [0]) + 10
            d = self.root / lid
            d.mkdir(parents=True, exist_ok=True)
            np.save(d / "grid.npy", p["grid"])
            i = p["info"]
            vd = i["vdatum"]
            if vd != "NN2000" and vdatum_confirmed:
                vd = "NN2000 (stadfesta)"  # føraren har stadfest høgdesystemet ved import
            self.layers[lid] = {
                "id": lid, "name": name or Path(p["file"]).stem, "type": ltype, "file": p["file"], "source": source,
                "imported": time.strftime("%Y-%m-%d %H:%M"), "priority": int(priority), "active": True,
                "epsg": i["epsg"], "crs": i["crs"], "zone": i["zone"], "vdatum": vd, "res": i["res"],
                "x0": i["x0"], "y0": i["y0"], "dx": i["dx"], "dy": i["dy"], "nx": i["nx"], "ny": i["ny"],
                "hmin": i["hmin"], "hmax": i["hmax"], "valid": i["valid"], "area_km2": i["area_km2"],
                "outline": i["outline"], "warnings": p["warns"], "versions": versions,
            }
            self._save_meta(lid)
            return self.layers[lid]

    def update(self, lid, **kw):
        with self.lock:
            m = self.layers[lid]
            for k in ("name", "active", "priority", "source"):
                if k in kw and kw[k] is not None:
                    m[k] = kw[k]
            self._save_meta(lid)
            return m

    def delete(self, lid):
        with self.lock:
            self.layers.pop(lid)
            self.grids.pop(lid, None)
            shutil.rmtree(self.root / lid, ignore_errors=True)

    # --- oppslag ---
    def height(self, lat, lon, ltype="barmark"):
        """Terrenghøgd ved posisjonen frå det høgast prioriterte aktive laget som har gyldig verdi."""
        if not AVAILABLE:
            return None
        with self.lock:
            layers = sorted((m for m in self.layers.values() if m["active"] and m["type"] == ltype), key=lambda m: -m["priority"])
        for m in layers:
            E, N = utm_forward(lat, lon, m["zone"])
            c, r = (E - m["x0"]) / m["dx"] - 0.5, (m["y0"] - N) / m["dy"] - 0.5  # rutenett med senter i pikselmidten
            if c < -0.5 or r < -0.5 or c > m["nx"] - 0.5 or r > m["ny"] - 0.5:
                continue
            g = self._grid(m["id"])
            c0, r0 = int(math.floor(c)), int(math.floor(r))
            fc, fr = c - c0, r - r0
            vals, wsum, hsum = [], 0.0, 0.0
            for dr, dc, w in ((0, 0, (1 - fr) * (1 - fc)), (0, 1, (1 - fr) * fc), (1, 0, fr * (1 - fc)), (1, 1, fr * fc)):
                rr, cc = min(max(r0 + dr, 0), m["ny"] - 1), min(max(c0 + dc, 0), m["nx"] - 1)
                v = float(g[rr, cc])
                if math.isfinite(v) and w > 0:
                    wsum += w
                    hsum += w * v
            if wsum > 0.5:  # minst halve vekta må ha gyldige verdiar – elles prøv neste lag
                return {"h": hsum / wsum, "layer": m["id"], "name": m["name"], "res": m["res"], "vdatum": m["vdatum"]}
        return None

    # --- terrengutsnitt til 3D-visinga ---
    def patch(self, lat0, lon0, half=150.0, step=1.0, ltype="barmark"):
        """Høgder i eit kvadratisk rutenett rundt (lat0, lon0) for 3D-visinga.
        Rutenettet er i lokale meter: x mot aust, y mot nord, same flate tilnærming som førarskjermen brukar
        (111 320 m per breiddegrad, 111 320·cos(lat0) per lengdegrad). Rad 0 er nordkanten.
        Høgast prioriterte aktive lag vinn; NaN der ingen lag har data."""
        if not AVAILABLE:
            return None
        n = int(round(2 * half / step)) + 1
        xs = -half + np.arange(n) * step
        X, Y = np.meshgrid(xs, -xs)                     # rad 0 = nord (y = +half)
        mlat, mlon = 111320.0, 111320.0 * math.cos(math.radians(lat0))
        H = np.full((n, n), np.nan, dtype=np.float32)
        names = []
        with self.lock:
            layers = sorted((m for m in self.layers.values() if m["active"] and m["type"] == ltype), key=lambda m: -m["priority"])
        for m in layers:
            # lokal (x, y) → UTM med lineær tilnærming rundt midtpunktet (feil under 1 mm innanfor nokre hundre meter)
            z = m["zone"]
            E0, N0 = utm_forward(lat0, lon0, z)
            Ex, Nx = utm_forward(lat0, lon0 + 10.0 / mlon, z)
            Ey, Ny = utm_forward(lat0 + 10.0 / mlat, lon0, z)
            E = E0 + (Ex - E0) / 10.0 * X + (Ey - E0) / 10.0 * Y
            N = N0 + (Nx - N0) / 10.0 * X + (Ny - N0) / 10.0 * Y
            c = (E - m["x0"]) / m["dx"] - 0.5
            r = (m["y0"] - N) / m["dy"] - 0.5
            inside = (c > -0.5) & (r > -0.5) & (c < m["nx"] - 0.5) & (r < m["ny"] - 0.5) & np.isnan(H)
            if not inside.any():
                continue
            g = self._grid(m["id"])
            ci, ri = c[inside], r[inside]
            c0 = np.clip(np.floor(ci).astype(int), 0, m["nx"] - 1); r0 = np.clip(np.floor(ri).astype(int), 0, m["ny"] - 1)
            c1 = np.clip(c0 + 1, 0, m["nx"] - 1); r1 = np.clip(r0 + 1, 0, m["ny"] - 1)
            fc = np.clip(ci - c0, 0, 1); fr = np.clip(ri - r0, 0, 1)
            vals = np.zeros(ci.shape); wsum = np.zeros(ci.shape)
            for rr, cc, w in ((r0, c0, (1 - fr) * (1 - fc)), (r0, c1, (1 - fr) * fc), (r1, c0, fr * (1 - fc)), (r1, c1, fr * fc)):
                v = np.asarray(g[rr, cc], dtype=np.float64)
                ok = np.isfinite(v) & (w > 0)
                vals += np.where(ok, w * np.nan_to_num(v), 0); wsum += np.where(ok, w, 0)
            res = np.where(wsum > 0.5, vals / np.maximum(wsum, 1e-9), np.nan)
            sub = H[inside]; fill = np.isnan(sub) & np.isfinite(res)
            if fill.any():
                sub[fill] = res[fill]; H[inside] = sub; names.append(m["name"])
        if not names:
            return None
        return {"lat0": lat0, "lon0": lon0, "half": half, "step": step, "n": n, "h": H, "layers": names}


def snow_depth(gga_alt, gga_sep, fix, terrain, cal):
    """Rekn ut snødjupne. cal: antZ, zOff, heightMode ('nn2000'|'ellipsoid'), geoidN, calibrated.
    Returnerer (djupne eller None, status, detaljar)."""
    if terrain is None:
        return None, "OUTSIDE", {}
    if gga_alt is None:
        return None, "NO_HEIGHT", {}
    if cal.get("heightMode") == "ellipsoid":
        if gga_sep is None or cal.get("geoidN") in (None, ""):
            return None, "NO_GEOID", {}
        H = gga_alt + gga_sep - float(cal["geoidN"])  # ellipsoidisk høgd − geoidehøgd = NN2000
    else:
        H = gga_alt
    surface = H - float(cal.get("antZ", 0)) - float(cal.get("zOff", 0))  # høgd der maskina står (snøoverflata)
    raw = surface - terrain["h"]
    det = {"H": round(H, 3), "surface": round(surface, 3), "terrain": round(terrain["h"], 3), "raw": round(raw, 3)}
    if not cal.get("calibrated"):
        return None, "NO_CAL", det
    if fix != "RTK FIX":
        return None, "NO_FIX", det
    if raw < -0.5:
        return None, "NEGATIVE", det  # maskina under terrenget: feil høgdesystem eller kalibrering
    return max(0.0, raw), "OK", det
