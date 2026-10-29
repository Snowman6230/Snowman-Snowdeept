# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""RAIM-FDE i RTK-motoren (v1.6.113) – éin satellitt med stor feil (som ein dårleg bane) skal ikkje stoppe RTK.

Felttest 29.10 (R12i mot TH): «point pos error (chi-square error nv=16 vv=130.0 cs=26.1)» – den enkle posisjonen
(første steg i RTK) feila kontrollen, og heile epoka vart forkasta. Her får éin satellitt i roveren +60 m feil i
kodemålinga i midten av opptaket. Utan RAIM: epokar utan løysing. Med RAIM: satellitten blir kasta ut.
Køyr frå test/rtk etter «python3 lagrtcm.py 1077»:  python3 testraim.py [raim=0|1]
Venta med raim=1 (standard): «ALT OK».
"""
import sys
sys.path.insert(0, "../..")
import rtkmotor as M
from rtcm import _bits

RAIM = int(sys.argv[1].split("=")[1]) if len(sys.argv) > 1 else 1
BIAS, FRA, TIL = 60.0, 40, 80                     # +60 m, epoke 40–79 (satellitten blir vald i epoke 40)
BAD = [None]


def frames(b):
    i, out = 0, []
    while i < len(b):
        n = ((b[i + 1] & 3) << 8) | b[i + 2]
        out.append(b[i:i + n + 6])
        i += n + 6
    return out


base = frames(open("base.rtcm3", "rb").read())
rov = frames(open("rover.rtcm3", "rb").read())
sols = []
m = M.RtkMotor(on_solution=lambda g, i: sols.append((epoke[0], i["stat"], g)))
M.RAIM_FDE = RAIM
assert m.start(install=False), M.LIB_ERR
import pyrtklib as R
ep = R.Arr1Ddouble(6)
for k, v in enumerate([2005, 4, 2, 0, 0, 0]):
    ep[k] = v
t0 = R.epoch2time(ep)
m.rb.time = t0
m.rv.time = t0
m.load_nav("rtklib/test/data/rinex/07590920.05n")
base = [f for f in base if _bits(f[3:], 0, 12) != 1019]
epoke = [0]
orig = m._solve


def solve(obs):
    if FRA <= epoke[0] < TIL:
        if BAD[0] is None:
            BAD[0] = obs.data[obs.n // 2].sat
        for i in range(obs.n):
            if obs.data[i].sat == BAD[0]:
                obs.data[i].P[0] += BIAS
                obs.data[i].P[1] += BIAS
    return orig(obs)


m._solve = solve
bi = 0
errs = set()
for fr in rov:
    while bi < len(base):
        f = base[bi]
        bi += 1
        m.base_feed(f)
        if _bits(f[3:], 0, 12) in (1004, 1077):
            break
    m.rover_bytes(fr)
    if m.stats.get("err"):
        errs.add(m.stats["err"].split(":", 3)[-1].strip()[:60])
    epoke[0] += 1
s = m.status()
inne = [x for x in sols if FRA <= x[0] < TIL]
fix_inne = [x for x in inne if x[1] == 1]
lats = [float(g.split(",")[2]) for _, st, g in sols if st == 1]
spread = (max(lats) - min(lats)) / 60 * 111320 if lats else None
print(f"Feil på satellitt {BAD[0]} (+{BIAS:.0f} m kode)")
print(f"RAIM={RAIM}: løysingar {s['sol']}/{len(rov)} · FIX {s['fix']} · ingen {s['none']} · "
      f"i feilperioden: {len(inne)}/{TIL - FRA} løysingar, {len(fix_inne)} FIX · spreiing FIX {spread and round(spread, 3)} m")
print("feilmeldingar:", sorted(errs)[:4])
if RAIM:
    ok = len(inne) >= (TIL - FRA) - 2 and spread is not None and spread < 0.05
    print("ALT OK" if ok else "FEIL")
