#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av eigen LiDAR inn i terrengmodellen (v1.6.95) – syntetiske filer frå testterrenget (testterreng.py) med fasit.

  python3 test/lidar/testlidar.py          (frå pc/v1.6)

Lagar LAS (med og utan koordinatsystem/klassifisering), LAZ (om laspy/lazrs finst), XYZ, og ein variant med
ellipsoidiske høgder (NN2000 + geoidehøgda). Sjekkar at rutenettet treffer barmarka (tre og støy skal ikkje vere med),
at ellipsoidiske høgder blir gjorde om til NN2000, og at samanlikninga med eit eksisterande lag gjettar rett høgdesystem.
"""
import math, shutil, struct, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
import numpy as np
import terrain as T
import testterreng as TT

ZONE = 32
rng = np.random.default_rng(7)


def points(n=200_000, half=60.0, trees=True, noise=True):
    x = rng.uniform(-half, half, n) + TT.E0
    y = rng.uniform(-half, half, n) + TT.N0
    z = np.array([TT.terrain_h(a, b) for a, b in zip(x, y)])
    c = np.full(n, 2, np.uint8)
    if trees:  # 25 % vegetasjon 2–12 m over bakken (klasse 5)
        k = rng.random(n) < 0.25
        z[k] += rng.uniform(2, 12, k.sum()); c[k] = 5
    if noise:  # nokre støypunkt langt under og over (klasse 7 og 18)
        k = rng.random(n) < 0.002
        z[k] -= 30; c[k] = 7
        k2 = rng.random(n) < 0.002
        z[k2] += 80; c[k2] = 18
    return x, y, z, c


def geokeys(epsg, vd):
    keys = [(1024, 0, 1, 1), (3072, 0, 1, epsg)] + ([(4096, 0, 1, vd)] if vd else [])
    v = [1, 1, 0, len(keys)] + [a for k in keys for a in k]
    return struct.pack(f"<{len(v)}H", *v)


def write_las(path, x, y, z, c, epsg=25832, vd=5941, classify=True):
    """LAS 1.2, punktformat 1 (28 byte). Skriven direkte, utan bibliotek."""
    vlr = b""
    if epsg:
        data = geokeys(epsg, vd)
        vlr = struct.pack("<H16sHH32s", 0, b"LASF_Projection", 34735, len(data), b"GeoKeyDirectoryTag") + data
    hsize, n = 227, len(x)
    sc, off = (0.001, 0.001, 0.001), (math.floor(x.min()), math.floor(y.min()), 0.0)
    hdr = bytearray(hsize)
    hdr[0:4] = b"LASF"; hdr[24], hdr[25] = 1, 2
    struct.pack_into("<H", hdr, 94, hsize)
    struct.pack_into("<IIBHI", hdr, 96, hsize + len(vlr), 1 if vlr else 0, 1, 28, n)
    struct.pack_into("<6d", hdr, 131, *sc, *off)
    struct.pack_into("<6d", hdr, 179, x.max(), x.min(), y.max(), y.min(), z.max(), z.min())
    rec = np.zeros(n, dtype=np.dtype({"names": ["X", "Y", "Z", "c"], "formats": ["<i4", "<i4", "<i4", "u1"],
                                      "offsets": [0, 4, 8, 15], "itemsize": 28}))
    rec["X"] = np.round((x - off[0]) / sc[0]); rec["Y"] = np.round((y - off[1]) / sc[1]); rec["Z"] = np.round(z / sc[2])
    rec["c"] = c if classify else 0
    Path(path).write_bytes(bytes(hdr) + vlr + rec.tobytes())


def write_laz(path, x, y, z, c):
    import laspy
    h = laspy.LasHeader(point_format=1, version="1.2")
    h.scales = [0.001] * 3; h.offsets = [math.floor(x.min()), math.floor(y.min()), 0]
    h.vlrs.append(laspy.VLR("LASF_Projection", 34735, "GeoKeyDirectoryTag", geokeys(25832, 5941)))
    las = laspy.LasData(h); las.x, las.y, las.z = x, y, z; las.classification = c
    las.write(str(path))


def check(name, grid, info, offset=0.0, tol=0.03):
    """Median og 95-persentil av avviket mot barmarka i fasit (testterreng.terrain_h)."""
    ny, nx = grid.shape
    rr, cc = np.nonzero(np.isfinite(grid))
    k = rng.choice(len(rr), size=min(3000, len(rr)), replace=False)
    d = []
    for i in k:
        E = info["x0"] + (cc[i] + 0.5) * info["dx"]; N = info["y0"] - (rr[i] + 0.5) * info["dy"]
        d.append(float(grid[rr[i], cc[i]]) - offset - TT.terrain_h(E, N))
    d = np.abs(np.asarray(d))
    med, p95 = float(np.median(d)), float(np.percentile(d, 95))
    ok = med < tol and p95 < 5 * tol
    print(f"  {'OK ' if ok else 'FEIL'} {name}: {info['format']}, {info['res']} m, {nx}×{ny}, avvik median {med*100:.1f} cm, "
          f"95 % {p95*100:.1f} cm")
    return ok


def main():
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="snowman-lidar-"))
    try:
        lib = T.TerrainLibrary(tmp / "terreng")
        hint = (TT.LAT0, TT.LON0)
        x, y, z, c = points()
        la, lo = T.utm_inverse(TT.E0, TT.N0, ZONE)
        Ngeo = T.GEOID.n(la, lo)
        print(f"Geoidehøgd ved testterrenget: {Ngeo:.2f} m")

        print("1) LAS med koordinatsystem, NN2000 og klassifisering (tre og støy skal vekk)")
        write_las(tmp / "a.las", x, y, z, c)
        r = lib.analyse(tmp / "a.las", "skanning.las", hint)
        ok &= r["ok"] and r["info"]["vdatum"] == "NN2000" and r["info"].get("ground")
        g = lib.pending[r["token"]]["grid"]; ok &= check("LAS klassifisert", g, r["info"])
        lay = lib.import_pending(r["token"], "Grunnlag LAS", heights="nn2000")
        ok &= lay["vdatum"] == "NN2000"

        print("2) LAS utan koordinatsystem og klassifisering, ingen tre (sona frå posisjonen til maskina)")
        x2, y2, z2, c2 = points(trees=False, noise=False)
        write_las(tmp / "b.las", x2, y2, z2, c2, epsg=None, classify=False)
        r = lib.analyse(tmp / "b.las", "b.las", hint)
        ok &= r["ok"] and r["info"]["zone"] == 32 and not r["info"].get("ground")
        ok &= check("LAS uklassifisert", lib.pending[r["token"]]["grid"], r["info"])
        print("   åtvaringar:", " | ".join(w[:70] for w in r["warnings"]))

        print("3) LAS med ellipsoidiske høgder (eiga drone): samanlikning skal gjette «ell», import gjer om til NN2000")
        write_las(tmp / "c.las", x, y, z + Ngeo, c, vd=None)
        r = lib.analyse(tmp / "c.las", "drone_utm32.las", hint)
        cmp_ = r["info"].get("cmp") or {}
        print(f"   samanlikning: {cmp_}")
        ok &= r["ok"] and cmp_.get("guess") == "ell"
        lay = lib.import_pending(r["token"], "Drone", heights="ell", vdatum_confirmed=True)
        g = lib._grid(lay["id"])
        ok &= check("ellipsoidisk → NN2000", np.asarray(g), dict(lay, format="importert lag"))
        ok &= lay["vdatum"].startswith("NN2000")

        print("4) XYZ med desimalkomma og semikolon, nording først")
        k = rng.choice(len(x2), 40_000, replace=False)
        lines = ["N;E;H"] + [f"{y2[i]:.3f};{x2[i]:.3f};{z2[i]:.3f}".replace(".", ",") for i in k]
        (tmp / "d.csv").write_text("\n".join(lines))
        r = lib.analyse(tmp / "d.csv", "punkt_utm32.csv", hint)
        ok &= r["ok"] and r["info"]["zone"] == 32
        ok &= check("XYZ", lib.pending[r["token"]]["grid"], r["info"], tol=0.05)

        print("5) LAZ (komprimert)")
        try:
            import laspy, lazrs  # noqa: F401
            write_laz(tmp / "e.laz", x, y, z, c)
            r = lib.analyse(tmp / "e.laz", "e.laz", hint)
            ok &= r["ok"] and r["info"]["vdatum"] == "NN2000"
            ok &= check("LAZ", lib.pending[r["token"]]["grid"], r["info"])
        except ImportError:
            print("  (hoppa over: laspy/lazrs er ikkje installert her)")

        print("6) Snødjupne med geoide: RTK-motoren gir ellipsoidisk høgd med separasjon 0")
        lat, lon = TT.LAT0, TT.LON0
        E, N = T.utm_forward(lat, lon, ZONE)
        ter = lib.height(lat, lon)
        cal = {"antZ": 2.8, "zOff": 0.0, "calibrated": True, "_N": T.GEOID.n(lat, lon)}
        surf = TT.terrain_h(E, N) + 0.8
        d, st, _ = T.snow_depth(surf + 2.8 + cal["_N"], 0.0, "RTK FIX", ter, cal)          # ellipsoidisk, sep 0
        d2, st2, _ = T.snow_depth(surf + 2.8, cal["_N"], "RTK FIX", ter, cal)              # NN2000 + sep (vanleg mottakar)
        good = st == st2 == "OK" and abs(d - 0.8) < 0.05 and abs(d2 - 0.8) < 0.05
        print(f"  {'OK ' if good else 'FEIL'} snødjupne {d:.3f} m (ellipsoidisk) og {d2:.3f} m (NN2000 + separasjon), fasit 0,800 m")
        ok &= good
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALLE TESTAR OK" if ok else "NOKO FEILA")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
