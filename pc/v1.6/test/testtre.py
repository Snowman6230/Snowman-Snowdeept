# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av «FJERN TRE» (v1.6.134): tre og bygg i ein terrengmodell frå punktsky utan klassar.

Køyr frå pc/v1.6:  python3 test/testtre.py   → venta «ALT OK».
Syntetisk skiløype: bratt skråning (35 %) med bølger, ein knaus (4 m), eit hus og 400 tre (4–18 m høge) på 0,5 m rute.
Fasit = terrenget utan tre. Testar òg laget i terrengbiblioteket: filter, original teken vare på, og angre.
"""
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import punktsky as PS
import terrain as T

feil = []


def sjekk(namn, ok, info=""):
    print(("OK   " if ok else "FEIL ") + namn + (f" – {info}" if info else ""))
    if not ok:
        feil.append(namn)


res, n = 0.5, 1200
y, x = np.mgrid[0:n, 0:n] * res
fasit = (600 + 0.35 * y + 3 * np.sin(x / 40) + 2 * np.cos(y / 55)).astype(np.float32)
knaus = np.hypot(x - 450, y - 150) < 30
fasit += np.where(knaus, 4 * (1 - (np.hypot(x - 450, y - 150) / 30) ** 2), 0).astype(np.float32)
g = fasit.copy()
rng = np.random.default_rng(3)
for _ in range(400):
    cx, cy = rng.random(2) * n * res
    h, r = 4 + rng.random() * 14, 2 + rng.random() * 4
    if np.hypot(cx - 450, cy - 150) < 35:
        continue
    d = np.hypot(x - cx, y - cy)
    g = np.maximum(g, np.where(d < r, fasit + h * (1 - d / r), -1e9)).astype(np.float32)
hus = (x > 200) & (x < 215) & (y > 200) & (y < 212)
g[hus] = fasit[hus] + 6
g[100:140, 200:260] = np.nan     # hol i data
g[:, :40] = np.nan               # utanfor dekninga

f, frac = PS.ground_filter(g, res)
m = np.isfinite(f)
e = np.abs(f - fasit)[m]
e0 = np.abs(g - fasit)[m]
sjekk("NaN (inga data) er uendra", np.array_equal(np.isnan(f), np.isnan(g)))
sjekk("tre og hus fjerna: snittfeil under 3 cm", e.mean() < 0.03, f"før {e0.mean():.2f} m, etter {e.mean():.3f} m")
sjekk("under 0,2 % av rutene feil med meir enn 1 m", (e > 1).mean() < 0.002, f"før {100 * (e0 > 1).mean():.1f} %, etter {100 * (e > 1).mean():.2f} %")
sjekk("huset er borte (maks feil under 0,6 m)", np.abs(f - fasit)[hus].max() < 0.6, f"{np.abs(f - fasit)[hus].max():.2f} m")
sjekk("knausen (4 m) er ikkje teken", np.nanmax(np.abs(f - fasit)[knaus]) < 0.05, f"{np.nanmax(np.abs(f - fasit)[knaus]):.3f} m")
f2, fr2 = PS.ground_filter(fasit, res)
sjekk("terreng utan tre blir ikkje endra", np.nanmax(np.abs(f2 - fasit)) < 0.05, f"maks {np.nanmax(np.abs(f2 - fasit)):.3f} m")
plan = (500 + 0.6 * y).astype(np.float32)
f3, _ = PS.ground_filter(plan, res)
sjekk("bratt plan (60 %) uendra, også i kantane", np.nanmax(np.abs(f3 - plan)) < 0.01)

# --- i terrengbiblioteket ---
with tempfile.TemporaryDirectory() as td:
    L = T.TerrainLibrary(os.path.join(td, "terreng"))
    lid = "test-tre"
    d = L.root / lid
    d.mkdir(parents=True)
    np.save(d / "grid.npy", g)
    L.layers[lid] = {"id": lid, "name": "Test", "type": "barmark", "res": res, "dx": res, "dy": res,
                     "hmin": float(np.nanmin(g)), "hmax": float(np.nanmax(g)), "priority": 10, "active": True}
    L._save_meta(lid)
    _ = L._grid(lid)[5, 5]                               # opna (minnekartlagt) før filteret
    mm = L.degrove(lid)
    gn = np.asarray(L._grid(lid))
    sjekk("laget er jamna ut", np.nanmax(np.abs(gn - f)) < 1e-4)
    sjekk("originalen er teken vare på", (d / "grid_orig.npy").exists())
    sjekk("meta har degrove og ny hmax", "degrove" in mm and mm["hmax"] < float(np.nanmax(g)), str(mm.get("degrove")))
    mm = L.degrove(lid)                                  # to gonger = frå originalen, ikkje dobbelt
    sjekk("køyrt to gonger gir same resultat", np.nanmax(np.abs(np.asarray(L._grid(lid)) - f)) < 1e-4)
    mm = L.degrove_undo(lid)
    go = np.asarray(L._grid(lid))
    sjekk("angre gir originalen tilbake", np.array_equal(np.isnan(go), np.isnan(g)) and np.nanmax(np.abs(go - g)) == 0)
    sjekk("angre fjernar merket", "degrove" not in mm and not (d / "grid_orig.npy").exists())

    # --- eigne område (v1.6.135) ---
    x0, y0 = 383000.0, 6914000.0
    L.layers[lid].update(zone=32, x0=x0, y0=y0, nx=n, ny=n)

    def ll(px, py):   # meter i testterrenget (x aust, y = rad·res nedover) → lat/lon
        la, lo = T.utm_inverse(x0 + px, y0 - py, 32)
        return [la, lo]

    def sq(cx, cy, r):
        return [ll(cx - r, cy - r), ll(cx + r, cy - r), ll(cx + r, cy + r), ll(cx - r, cy + r)]

    tre = (g - fasit) > 2
    # eit tre utanfor knausen og huset å verne / fjerne
    ty, tx = np.argwhere(tre & (np.hypot(x - 450, y - 150) > 60) & ~hus & (x > 100) & (x < 540) & (y > 60) & (y < 540))[0]
    tcx, tcy = tx * res, ty * res
    A_vern = {"id": "v1", "kind": "vern", "poly": sq(tcx, tcy, 8)}
    mm = L.degrove(lid, whole=True, areas=[A_vern])
    gv = np.asarray(L._grid(lid))
    V = L.area_mask(mm, g.shape, A_vern["poly"])
    sjekk("vern: treet inni er uendra", np.nanmax(np.abs(gv[V] - g[V])) == 0 and V.sum() > 900, f"{V.sum()} ruter")
    sjekk("vern: resten er filtrert", np.nanmax(np.abs(gv[~V] - f[~V])) < 1e-4)
    A_fj = {"id": "f1", "kind": "fjern", "poly": sq(tcx, tcy, 10)}
    mm = L.degrove(lid, whole=False, areas=[A_fj])
    gf = np.asarray(L._grid(lid))
    Fm = L.area_mask(mm, g.shape, A_fj["poly"])
    sjekk("fjern tre her: berre inni er endra", np.nanmax(np.abs(gf[~Fm] - g[~Fm])) == 0 and np.nanmax(np.abs(gf[Fm] - f[Fm])) < 1e-4)
    sjekk("fjern tre her: treet er borte (maks under 1,5 m)", np.nanmax(np.abs(gf[Fm] - fasit[Fm])) < 1.5, f"{np.nanmax(np.abs(gf[Fm] - fasit[Fm])):.2f} m")
    # jamn ut heilt: eit 40 × 40 m område med tett skog (filteret åleine tek ikkje skog breiare enn vindauget)
    skog = (x > 380) & (x < 420) & (y > 400) & (y < 440)
    g2 = g.copy(); g2[skog] = fasit[skog] + 12 + rng.random(skog.sum()).astype(np.float32) * 4
    np.save(d / "grid_orig.npy", g2)
    A_j = {"id": "j1", "kind": "jamn", "poly": sq(400, 420, 23)}
    mm = L.degrove(lid, whole=False, areas=[A_j])
    gj = np.asarray(L._grid(lid))
    J = L.area_mask(mm, g.shape, A_j["poly"])
    ej = np.abs(gj - fasit)[J & np.isfinite(gj)]
    sjekk("jamn ut heilt: tett skog 40 × 40 m er borte", ej.max() < 1.0, f"maks feil {ej.max():.2f} m, snitt {ej.mean():.2f} m (før 12–16 m)")
    sjekk("jamn ut heilt: utanfor er uendra", np.nanmax(np.abs(gj[~J] - g2[~J])) == 0)
    try:
        L.degrove(lid, whole=False, areas=[{"id": "u", "kind": "jamn", "poly": [ll(-900, -900), ll(-800, -900), ll(-800, -800)]}])
        sjekk("område utanfor laget blir avvist", False)
    except ValueError as e:
        sjekk("område utanfor laget blir avvist", "utanfor" in str(e), str(e))
    mm = L.degrove(lid, whole=False, areas=[])
    sjekk("ingen område og filter av = originalen", "degrove" not in mm and np.array_equal(np.asarray(L._grid(lid)), g2, equal_nan=True))
    L.grids.clear()

print("ALT OK" if not feil else f"{len(feil)} FEIL: {feil}")
sys.exit(1 if feil else 0)
