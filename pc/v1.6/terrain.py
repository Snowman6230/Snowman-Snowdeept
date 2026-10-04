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

    def import_pending(self, token, name, ltype="barmark", priority=None, replace_id=None, source=""):
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
            self.layers[lid] = {
                "id": lid, "name": name or Path(p["file"]).stem, "type": ltype, "file": p["file"], "source": source,
                "imported": time.strftime("%Y-%m-%d %H:%M"), "priority": int(priority), "active": True,
                "epsg": i["epsg"], "crs": i["crs"], "zone": i["zone"], "vdatum": i["vdatum"], "res": i["res"],
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
