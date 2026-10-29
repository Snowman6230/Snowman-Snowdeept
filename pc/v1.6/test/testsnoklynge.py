# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Snøflata i 3D (v1.6.115): feilmålingar i små, ujamne klynger skal ikkje visast, ekte spor skal.
Køyr frå pc/v1.6:  python3 test/testsnoklynge.py   Venta: «ALT OK»."""
import os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import snoflate as SF

random.seed(1)
ok = True
def check(name, cond):
    global ok
    print(("OK   " if cond else "FEIL ") + name)
    ok &= bool(cond)

items = []
# ekte spor: 80 m langt, 4 m breitt, jamn overflate (terreng skrånar 10 %, snø 0,8–1,2 m)
for e in range(1000, 1080):
    for n in range(500, 504):
        items.append(((32, e, n), [100 + 0.1 * (e - 1000) + 1.0 + 0.2 * random.random(), 0, False, 100 + 0.1 * (e - 1000)]))
# feilmålingar som 28.10: tett klynge på 20 ruter med 1,6–6 m «snø» om kvarandre
for i in range(20):
    e, n = 2000 + i % 5, 600 + i // 5
    items.append(((32, e, n), [50 + random.choice([1.8, 3.5, 5.9, 2.9, 4.6]), 0, False, 50.0]))
# to like feilruter (ei lita klynge som passar med kvarandre)
items += [((32, 3000, 700), [61.85, 0, False, 60.0]), ((32, 3001, 700), [61.88, 0, False, 60.0]),
          ((32, 3000, 701), [61.82, 0, False, 60.0])]
kept = {k for k, _ in SF.drop_small_clusters(items)}
real = {k for k, _ in items if 1000 <= k[1] < 1080}
check("ekte spor blir vist (alle 320 ruter)", real <= kept)
check("ujamn feilklynge (20 ruter, 1,6–6 m) blir fjerna", not any(2000 <= k[1] < 2010 for k in kept))
check("lita klynge (3 ruter) blir fjerna", not any(k[1] >= 3000 for k in kept))
print("ALT OK" if ok else "FEIL")
sys.exit(0 if ok else 1)
