#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Lagar eksempel på rapportane SNOWMAN kan levere, med OPPDIKTA data (ingen ekte målingar).

Alt blir laga i ei eiga mappe – data/ til SNOWMAN blir ikkje rørt. Kvar PDF er merkt «EKSEMPEL – oppdikta data».
Bruk:  python3 lag-eksempel.py [utmappe]        (standard: ../../docs/eksempel-rapportar)

Lagar:
  1 dagsrapport med trasear (PDF)        – kart per trasé i snødjupnefargar, tid i traseen, økter, drivstoff
  2 dagsrapport utan trasear (PDF)       – kart over heile området som er køyrt (delt i område)
  3 dagsrapport (CSV til Excel)          – same tal som tabellar
"""
import json, math, shutil, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trasear as TR, drivstoff as DS, pdfrapport as PR

NOTE = "EKSEMPEL – oppdikta data, ikkje ekte målingar"
LAT0, LON0 = 62.3905, 6.5810          # Fjellsætra (same stad som simulatoren)
MY, MX = 111320.0, 111320.0 * math.cos(math.radians(LAT0))
ll = lambda x, y: (LAT0 + y / MY, LON0 + x / MX)


def rect(x0, y0, w, h):
    return [list(ll(x0, y0)), list(ll(x0 + w, y0)), list(ll(x0 + w, y0 + h)), list(ll(x0, y0 + h))]


def snow(x, y):
    """Oppdikta snødjupne (m): jamn variasjon, tynt felt nede i Storebakken, djupt i ei fylt grop."""
    d = 0.80 + 0.012 * (y - 150) / 10 + 0.28 * math.sin(y / 40.0) * math.cos(x / 21.0)
    d -= 0.75 * math.exp(-((x - 120) ** 2 + (y - 70) ** 2) / (2 * 22 ** 2))     # tynt felt (vind)
    d += 0.95 * math.exp(-((x - 10) ** 2 + (y - 250) ** 2) / (2 * 20 ** 2))     # fylt grop / bekkefar
    return round(max(0.08, d), 3)


def session(sid, t0, lanes, width=5.5, speed=2.6, machine="PB600"):
    """Spor fram og tilbake: lanes = [(x, y_frå, y_til), …]. Eitt punkt i sekundet."""
    pts, t = [], t0
    for x, ya, yb in lanes:
        n = int(abs(yb - ya) / speed)
        for i in range(n + 1):
            y = ya + (yb - ya) * i / max(n, 1)
            la, lo = ll(x, y)
            pts.append({"lat": round(la, 8), "lng": round(lo, 8), "t": int(t * 1000), "speed": speed, "heading": 0 if yb > ya else 180,
                        "depth": snow(x, y), "fix": "RTK FIX"})
            t += 1
        t += 20  # snu
    return {"id": sid, "date": time.strftime("%Y-%m-%d", time.localtime(t0)), "start": int(t0 * 1000), "end": int(t * 1000),
            "machine": machine, "width": width, "points": pts}, t


def lanes(x0, x1, ya, yb, step=5.0):
    out, x, up = [], x0, True
    while x <= x1 + 1e-6:
        out.append((x, ya, yb) if up else (x, yb, ya))
        x += step
        up = not up
    return out


def build_data(root, with_trasear=True):
    data = root / "data"
    (data / "sessions").mkdir(parents=True)
    tra = TR.Trasear(data / "trasear.json", data / "sessions")
    if with_trasear:
        tra.save({"name": "Familiebakken", "kind": "trase", "level": "bla", "target": 0.8, "poly": rect(-20, 120, 60, 260)})
        tra.save({"name": "Storebakken", "kind": "trase", "level": "raud", "target": 0.9, "poly": rect(80, 0, 90, 300)})
    day = time.mktime(time.strptime("2026-10-08 12:00", "%Y-%m-%d %H:%M"))
    s1, e1 = session("eks-1", day + 5.5 * 3600, lanes(-17, 37, 125, 375))                 # Familiebakken 17:30
    s2, e2 = session("eks-2", day + 7.7 * 3600, lanes(83, 140, 5, 295))                   # Storebakken 19:42
    s3, e3 = session("eks-3", day + 10.2 * 3600, lanes(145, 165, 5, 200))  # 22:12
    for s in (s1, s2, s3):
        (data / "sessions" / (s["id"] + ".json")).write_text(json.dumps(s), "utf-8")
    fuel = DS.Drivstoff(data / "drivstoff.json", tra)
    fuel.add({"litres": 210, "full": True, "hours": 4310.2, "t": int((day - 0.5 * 3600) * 1000)}, "PB600")
    fuel.add({"litres": 172, "full": True, "hours": 4316.6, "t": int((e3 + 600) * 1000)}, "PB600")
    return fuel, "2026-10-08"


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent.parent / "docs" / "eksempel-rapportar"
    out.mkdir(parents=True, exist_ok=True)
    bounds = [0.3, 0.5, 0.8, 1.2, 1.6]
    for with_tr, name in ((True, "1-dagsrapport-med-trasear"), (False, "2-dagsrapport-utan-trasear")):
        tmp = Path(tempfile.mkdtemp())
        try:
            fuel, date = build_data(tmp, with_tr)
            rep = fuel.report(date, maps=True)
            (out / f"{name}.pdf").write_bytes(PR.build(rep, "PB600 – Trakkemaskin 1", bounds, note=NOTE))
            if with_tr:
                (out / "3-dagsrapport.csv").write_text("EKSEMPEL – oppdikta data;;;\n" + fuel.report_csv(date).lstrip("﻿"), "utf-8-sig")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("Laga i", out)


if __name__ == "__main__":
    main()
