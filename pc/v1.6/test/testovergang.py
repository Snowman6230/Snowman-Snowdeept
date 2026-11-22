# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av mjuk overgang mellom terrenglag og samanlikning med overlappande lag – v1.6.136.

Køyr frå pc/v1.6:  python3 test/testovergang.py   → venta «ALT OK».
To lag i same skråning: eit grovt grunnlag (1 m, «DTM1») som ligg 0,20 m over, og eit detaljert lag (0,5 m) med eit hol
på 30 × 30 m og eit lite hol på 1 × 1 m. Ved kanten og kring det store holet skal høgda gå mjukt over (ingen trinn),
inne i laget skal ho vere lik det detaljerte laget, og samanlikninga skal finne skilnaden på −0,20 m.
"""
import os
import sys
import tempfile
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import terrain as T

feil = []


def sjekk(namn, ok, info=""):
    print(("OK   " if ok else "FEIL ") + namn + (f" – {info}" if info else ""))
    if not ok:
        feil.append(namn)


def terreng(E, N):
    return 600 + 0.3 * (6914000 - N) * -1 + 0.1 * (E - 383000) + 2 * np.sin((E - 383000) / 30)


def lag(L, lid, x0, y0, res, n, off, prio, name, hol=None):
    d = L.root / lid
    d.mkdir(parents=True)
    c = np.arange(n) + 0.5
    E, N = np.meshgrid(x0 + c * res, y0 - c * res)
    g = (terreng(E, N) + off).astype(np.float32)
    for (r0, r1, c0, c1) in hol or []:
        g[r0:r1, c0:c1] = np.nan
    np.save(d / "grid.npy", g)
    L.layers[lid] = {"id": lid, "name": name, "type": "barmark", "res": res, "dx": res, "dy": res, "zone": 32, "x0": x0, "y0": y0,
                     "nx": n, "ny": n, "hmin": float(np.nanmin(g)), "hmax": float(np.nanmax(g)), "priority": prio, "active": True,
                     "vdatum": "NN2000"}
    L._save_meta(lid)
    return g


with tempfile.TemporaryDirectory() as td:
    L = T.TerrainLibrary(os.path.join(td, "terreng"))
    lag(L, "grov", 382800, 6914200, 1.0, 400, +0.20, 10, "DTM1")
    # detaljert lag 200 × 200 m midt i, hol 30 × 30 m og 1 × 1 m
    lag(L, "fin", 382900, 6914100, 0.5, 400, 0.0, 20, "Drone", hol=[(140, 200, 140, 200), (300, 302, 60, 62)])

    def h(E, N):
        la, lo = T.utm_inverse(E, N, 32)
        r = L.height(la, lo)
        return r["h"] - float(terreng(np.array(E), np.array(N))), r

    # langs ei linje frå grov (vest) inn i det fine laget (kant ved E = 382900)
    xs = np.arange(382870, 382960, 0.25)
    d = np.array([h(x, 6913960)[0] for x in xs])
    sjekk("utanfor det fine laget: grunnlaget (+0,20)", abs(d[0] - 0.20) < 0.01, f"{d[0]:+.3f}")
    sjekk("godt inne (> 15 m): berre det fine laget", abs(d[-1]) < 0.01, f"{d[-1]:+.3f}")
    steg = np.max(np.abs(np.diff(d)))
    sjekk("ingen trinn over kanten (maks 0,75 cm per 25 cm, utan overgang 20 cm)", steg < 0.0075, f"største sprang {steg * 100:.2f} cm")
    r = h(382905, 6914000)[1]
    sjekk("i overgangssona: blend-vekt rapportert", "blend" in r and 0 < r["blend"] < 1 and r["name"] == "Drone", str(r.get("blend")))
    # kring det store holet (rad 140–200, kol 140–200 → E 382970–383000, N 6914030–6914000)
    xs = np.arange(382950, 383010, 0.25)
    d = np.array([h(x, 6914015)[0] for x in xs])
    sjekk("over det store holet: ingen trinn", np.max(np.abs(np.diff(d))) < 0.0075, f"{np.max(np.abs(np.diff(d))) * 100:.2f} cm")
    sjekk("midt i holet: grunnlaget", abs(h(382985, 6914015)[0] - 0.20) < 0.01)
    # det vesle holet (1 × 1 m) skal ikkje lage overgangssone rundt seg
    sjekk("vesle holet lagar inga overgangssone", abs(h(382933, 6913948)[0]) < 0.01, f"{h(382933, 6913948)[0]:+.3f}")
    # 3D-utsnitt
    la, lo = T.utm_inverse(382905, 6914000, 32)
    P = L.patch(la, lo, half=60, step=1.0)
    H = P["h"]
    gy, gx = np.gradient(H.astype(np.float64))
    # fasit-gradient ved same punkt: fjern terrenget sin del ved å samanlikne mot eit utsnitt med berre eitt lag
    L.layers["grov"]["active"] = False
    P1 = L.patch(la, lo, half=60, step=1.0)
    L.layers["grov"]["active"] = True
    D = H - P1["h"]
    ok = np.isfinite(D)
    jump = max(np.nanmax(np.abs(np.diff(D, axis=0))), np.nanmax(np.abs(np.diff(D, axis=1))))
    sjekk("3D-utsnitt: ingen trinn (maks 3 cm per meter)", jump < 0.03, f"{jump * 100:.2f} cm")
    sjekk("3D-utsnitt: begge laga namngitt", P["layers"] == ["Drone", "DTM1"], str(P["layers"]))
    # fart
    t = time.time()
    for i in range(200):
        L.height(*T.utm_inverse(382905 + i * 0.1, 6914000, 32))
    ms = (time.time() - t) / 200 * 1000
    sjekk("oppslag raskt nok (under 5 ms)", ms < 5, f"{ms:.2f} ms")
    # samanlikning
    ov = L._overlap(L._grid("fin"), L.layers["fin"], exclude="fin")
    o = ov[0] if ov else {}
    sjekk("samanlikning: −0,20 m mot DTM1", o.get("layer") == "DTM1" and abs(o["median"] + 0.20) < 0.02, str(o))
    w = T.TerrainLibrary.overlap_warnings(ov, "Laget")
    sjekk("åtvaring om trinn", len(w) == 1 and "−0,20" not in w[0] and "-0.20" in w[0], w[0][:80] if w else "")
    t0 = time.time()
    L.refresh_overlaps()
    while not L.overlaps and time.time() - t0 < 30:
        time.sleep(0.1)
    lst = {m["id"]: m for m in L.listing()}
    sjekk("listing har samanlikninga", "overlap" in lst["fin"] and lst["fin"]["overlap"][0]["layer"] == "DTM1")
    L.grids.clear()

print("ALT OK" if not feil else f"{len(feil)} FEIL: {feil}")
sys.exit(1 if feil else 0)
