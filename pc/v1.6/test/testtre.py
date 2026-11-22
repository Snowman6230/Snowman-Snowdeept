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
    L.grids.clear()

print("ALT OK" if not feil else f"{len(feil)} FEIL: {feil}")
sys.exit(1 if feil else 0)
