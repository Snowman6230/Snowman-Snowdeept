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
# v1.6.129: éin gjennomgang med anslåtte kantar frå prøvar, og ny gjennomgang når prøvane bommar
n2, sw2, lo2, hi2, exact = PS.sample_xyz(p, k=8, size=4096)
sjekk("7 prøvar: anslag på tal punkt og kantar", not exact and sw2 and 0.7 * n < n2 < 1.3 * n and lo2[0] < 383050, (n2, lo2, hi2))
orig = PS.sample_xyz
PS.sample_xyz = lambda path: (n, True, np.array([383100.0, 6913400.0, 0]), np.array([383150.0, 6913450.0, 0]), True)
fasar = []
grid, info, err, warns = PS.analyse_pointcloud(p, os.path.basename(p), (62.36, 6.76), T.utm_inverse, lambda e: f"EPSG:{e}",
                                               progress=lambda d, t, f=None: fasar.append(f) if f else None)
PS.sample_xyz = orig
sjekk("8 for små kantar → rutenettet blir utvida, heile området kjem med", not err and info["points"] == n and abs(info["hmax"] - 630) < 0.5
      and abs(info["hmin"] - 600) < 0.5, (err, info.get("points"), info.get("hmin"), info.get("hmax")))
sjekk("9 fila blir lesen berre éin gong (ingen ny gjennomgang)", not any("ein gong til" in (f or "") for f in fasar)
      and any("utvida" in w for w in warns), (fasar, warns))
# rutenettet etter utviding skal gi same høgder som utan
g_ref, i_ref, _, _ = PS.analyse_pointcloud(p, os.path.basename(p), (62.36, 6.76), T.utm_inverse, lambda e: f"EPSG:{e}")
sjekk("9b same høgder som utan utviding (snitt)", abs(float(np.nanmean(grid)) - float(np.nanmean(g_ref))) < 0.05,
      (float(np.nanmean(grid)), float(np.nanmean(g_ref))))
# v1.6.131: utan GNSS (heime) – sona blir funnen frå sist kjende posisjon eller midten av eit terrenglag
cx, cy = 383150.0, 6913450.0
sjekk("10 ingen stad → inga sone", PS.epsg_from_hint(cx, cy, [], T.utm_inverse) is None)
sjekk("11 berre posisjon heime (Ålesund, 45 km) → inga sone", PS.epsg_from_hint(cx, cy, [(62.47, 6.15)], T.utm_inverse) is None)
lag = T.utm_inverse(383500, 6914000, 32)   # midten av eit terrenglag ved Fjellsætra
sjekk("12 GNSS manglar, men terrenglag i nærleiken → sone 32",
      PS.epsg_from_hint(cx, cy, [(None, None), (62.47, 6.15), lag], T.utm_inverse) == 25832)
sjekk("13 éin stad som tuppel fungerer som før", PS.epsg_from_hint(cx, cy, (62.36, 6.76), T.utm_inverse) == 25832)
print("ALT OK" if not feil else f"FEIL: {feil}")
sys.exit(1 if feil else 0)
