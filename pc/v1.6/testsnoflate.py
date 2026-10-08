#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av snøflateminnet (snoflate.py) med syntetisk terreng – utan GNSS og utan terrengfil.

Bakke med 14° helling, ei stor bølgje, eit bekkefar (1,2 m djupt) på tvers og ein kul. Maskina har køyrt fire
spor (x = −10, −5, 5, 10 m) og skal no køyre sporet x = 0. Estimatet framfor maskina blir samanlikna med fasit for:
  - PLANERT: snøoverflata følgjer den store forma, men ikkje bekk/kul (slik det er etter tråkking)
  - IKKJE PLANERT: snøen ligg jamt oppå terrenget (t.d. naturleg snø før første tråkking)
og mot den enkle metoden (interpolere snødjupna), som førarskjermen brukar når estimatet frå tidlegare overflate er av.

Bruk: python3 testsnoflate.py
"""
import math, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snoflate as SF
from terrain import utm_forward, utm_inverse

E0, N0 = utm_forward(62.39, 6.58, 32)


def ter(E, N):
    x, y = E - E0, N - N0
    h = 900 + 0.25 * y + 1.0 * math.sin(x / 40)                              # helling og stor bølgje
    h -= 1.2 * math.exp(-((y - 60) ** 2) / (2 * 1.7 ** 2))                  # bekkefar på tvers ved y = 60 m
    h += 0.6 * math.exp(-((x - 12) ** 2 + (y - 90) ** 2) / (2 * 2.0 ** 2))  # kul
    return h


def snow(E, N):
    x, y = E - E0, N - N0
    return 0.9 + 0.2 * math.sin(y / 30) * math.cos(x / 25)


def th(la, lo):
    E, N = utm_forward(la, lo, 32)
    return {"h": ter(E, N)}


def tg(E, N):
    v = [ter(E + a, N + b) for a in range(-6, 7, 2) for b in range(-6, 7, 2)]
    return sum(v) / len(v)


def run(groomed):
    surf = (lambda E, N: tg(E, N) + snow(E, N)) if groomed else (lambda E, N: ter(E, N) + snow(E, N))
    S = SF.SnowSurface(Path(tempfile.mkdtemp()) / "snoflate.json")
    for x in (-10, -5, 5, 10):
        for y in range(0, 121):
            la, lo = utm_inverse(E0 + x, N0 + y, 32)
            S.add(la, lo, surf(E0 + x, N0 + y), th, test=True)
    res = {"tidlegare overflate": [], "berre snødjupne": []}
    stream = []
    for y0 in (20, 45, 70):
        la, lo = utm_inverse(E0, N0 + y0, 32)
        for c in S.ahead(la, lo, 0, 5.5, th, test=True)["cells"]:
            E, N = utm_forward(c["lat"], c["lon"], 32)
            fasit = surf(E, N) - ter(E, N)
            res["tidlegare overflate"].append(abs(c["d"] - fasit))
            sw = sd = 0.0
            n, near = 0, 99.0
            for (z, e, nn), v in S.cells.items():
                d = math.hypot(e + 0.5 - E, nn + 0.5 - N)
                if d < 8:
                    w = 1 / max(d, 0.5) ** 2
                    sw += w
                    sd += w * (v[0] - ter(e + 0.5, nn + 0.5))
                    n += 1
                    near = min(near, d)
            idw = max(0.0, sd / sw) if n >= 3 and near < 6 else None
            if idw is not None:
                res["berre snødjupne"].append(abs(idw - fasit))
            if abs(N - N0 - 60) < 1.5 and abs(E - E0) < 1.5:
                stream.append((c["d"], idw, fasit))
    print("PLANERT – overflata følgjer ikkje bekk og kul" if groomed else "IKKJE PLANERT – snøen ligg jamt oppå terrenget")
    for k, v in res.items():
        print(f"  {k:20s} snittavvik {sum(v) / len(v):.3f} m   største {max(v):.3f} m   ({len(v)} ruter)")
    for d, i, f in stream[:2]:
        print(f"  midt i bekken: tidlegare overflate {d:.2f} m · berre snødjupne {i:.2f} m · fasit {f:.2f} m")
    return res


if __name__ == "__main__":
    a = run(True)
    b = run(False)
    ok = max(a["tidlegare overflate"]) < 0.05 and max(b["berre snødjupne"]) < 0.05
    print("OK" if ok else "FEIL – sjå tala over")
    sys.exit(0 if ok else 1)
