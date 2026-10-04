#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Syntetisk testterreng og «fasit-snø» for å teste Terrain Engine utan ekte LiDAR.

Terrenget er ein bakke ved simulatorposisjonen ved Fjellsætra: jamn stigning mot nord, bølgjer og eit søkk.
Snødjupna (fasit) varierer mellom ca. 0,2 og 1,4 m, med eit tynt felt. Same funksjonar blir brukte av
simuler-leica.py, så SNOWMAN si utrekna snødjupne kan samanliknast med fasit.

Bruk:  python3 testterreng.py [utfil.tif] [--detalj]
       --detalj lagar eit mindre lag med 0,25 m oppløysing (for å teste prioritet mellom lag).
"""
import math, sys
from terrain import utm_forward

LAT0, LON0 = 62.3905, 6.5810               # same startpunkt som simuler-leica.py
E0, N0 = utm_forward(LAT0, LON0, 32)       # LAT0/LON0 i EUREF89 UTM 32N


def terrain_h(E, N):
    """Barmarkshøgd (NN2000, meter) i punktet (austing, nording) i UTM 32."""
    x, y = E - E0, N - N0
    h = 905.0 + 0.25 * y                                   # stigning mot nord (ca. 14°)
    h += 1.5 * math.sin(x / 37.0) * math.cos(y / 23.0)     # bølgjer
    h -= 2.0 * math.exp(-((x - 60) ** 2 + (y - 70) ** 2) / (2 * 15 ** 2))  # søkk
    return h


def snow_truth(E, N):
    """Fasit-snødjupne (meter)."""
    x, y = E - E0, N - N0
    d = 0.8 + 0.45 * math.sin(x / 23.0) * math.sin(y / 31.0)
    if 30 < x < 45 and 20 < y < 60:                        # tynt felt (raudt)
        d = 0.2
    return max(0.05, d)


def write(path, detail=False):
    import numpy as np, tifffile
    res = 0.25 if detail else 0.5
    if detail:   # lite detaljlag midt i området
        xa, xb, ya, yb = 20, 120, 20, 110
    else:
        xa, xb, ya, yb = -100, 300, -100, 250
    nx, ny = int((xb - xa) / res), int((yb - ya) / res)
    xs = E0 + xa + (np.arange(nx) + 0.5) * res
    ys = N0 + yb - (np.arange(ny) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    x, y = X - E0, Y - N0
    H = 905.0 + 0.25 * y + 1.5 * np.sin(x / 37.0) * np.cos(y / 23.0) - 2.0 * np.exp(-((x - 60) ** 2 + (y - 70) ** 2) / (2 * 15 ** 2))
    H = H.astype(np.float32)
    H[:6, :6] = -9999  # litt nodata i eitt hjørne (test av handtering)
    geokeys = [1, 1, 0, 4,
               1024, 0, 1, 1,        # projisert koordinatsystem
               1025, 0, 1, 1,        # PixelIsArea
               3072, 0, 1, 25832,    # EUREF89 / UTM 32N
               4096, 0, 1, 5941]     # NN2000
    tifffile.imwrite(path, H, compression="deflate", extratags=[
        (33550, "d", 3, (res, res, 0.0), False),
        (33922, "d", 6, (0.0, 0.0, 0.0, E0 + xa, N0 + yb, 0.0), False),
        (34735, "H", len(geokeys), geokeys, False),
        (42113, "s", 0, "-9999", False),
    ])
    print(f"Skreiv {path}: {nx}×{ny} ruter à {res} m, EUREF89 UTM 32N, NN2000")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    det = "--detalj" in sys.argv
    write(args[0] if args else ("testterreng-detalj.tif" if det else "testterreng.tif"), det)
