# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av XYZ-koordinatfil (.pxy) og bit-for-bit-lesing av store tekstfiler – v1.6.128.

Køyr frå pc/v1.6:  python3 test/testpxy.py   → venta «ALT OK».
Lagar ei lita .pxy-fil som den frå Sykkylven Skisenter (overskrift «XYZ-COORD-FILE», nording austing høgd, komma til
slutt på linja) og les henne med små bitar, så linjer blir kutta mellom bitane.
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


rng = np.random.default_rng(7)
n = 200_000
E = 383000 + rng.random(n) * 300
N = 6913300 + rng.random(n) * 300
H = 600 + 0.1 * (E - 383000)
d = tempfile.mkdtemp()
p = os.path.join(d, "Sykkylven Skisenter terreng pxy fil.pxy")
with open(p, "w") as f:
    f.write("XYZ-COORD-FILE  ,V1.00,2025-11-21,                                        ,\n")
    f.write("                                        ,                                 ,\n")
    for a, b, c in zip(N, E, H):
        f.write(f"              {a:.4f} {b:.4f} {c:11.4f}                        ,\n")

npts, swapped, lo, hi = PS.scan_xyz(p)
sjekk("1 alle punkt lesne, overskrifta hoppa over", npts == n, npts)
sjekk("2 nording/austing oppdaga og bytt", swapped and 382999 < lo[0] and hi[1] < 6913601, (lo, hi))
blk = list(PS.iter_xyz_blocks(p, block=4096))     # små bitar: mange linjer blir kutta mellom bitane
sjekk("3 små bitar gir same tal punkt", sum(len(b) for b in blk) == n, sum(len(b) for b in blk))
grid, info, err, warns = PS.analyse_pointcloud(p, os.path.basename(p), (62.36, 6.76), T.utm_inverse, lambda e: f"EPSG:{e}")
sjekk("4 analyse utan feil, sone 32 ut frå posisjonen", not err and info.get("zone") == 32, (err, info.get("zone")))
sjekk("5 format PXY", info.get("format", "").startswith("PXY"), info.get("format"))
sjekk("6 høgdene stemmer (600–630 m)", abs(info["hmin"] - 600) < 0.5 and abs(info["hmax"] - 630) < 0.5, (info["hmin"], info["hmax"]))
print("ALT OK" if not feil else f"FEIL: {feil}")
sys.exit(1 if feil else 0)
