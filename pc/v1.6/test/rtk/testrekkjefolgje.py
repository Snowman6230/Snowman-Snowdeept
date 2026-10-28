"""Test (v1.6.100): roverobservasjonar som ikkje kjem sorterte etter satellittnummer.

Bakgrunn (felttest 28.10.2026, Emlid Reach RS+): mottakaren sender fleire RTCM-meldingar per epoke
(1002, 1010, 1107, 1117, 1127 …). RTKLIB legg satellittane inn i den rekkjefølgja meldingane kjem, men
rtkpos/selsat krev at rover- og baseobservasjonane er sorterte etter satellittnummer. Utan sortering fann
motoren «no common satellite», og det vart ingen løysing i det heile.

Testen etterliknar dette med RTKLIB-testdataa 0759/3040: roveren blir koda som 1002 (berre L1, som RS+)
i to meldingar per epoke, der dei høgaste satellittnummera kjem først (sync=1) og dei lågaste sist (sync=0).
Basen er 1006 + 1077 (L1 + L2, som lagrtcm.py). Same roverdata blir òg køyrde sorterte (éi melding per epoke).
Venta: usortert gir nøyaktig same resultat som sortert, RTK FIX i minst 90 % av epokane (berre L1, GPS), og
ingen «no common satellite».

NB (v1.6.102): RINEX-testdataa har berebølgjefasen langt frå kodeavstanden. I 1002 er fasen lagra som skilnad mot
koden i eit felt på ±262 m, og RTKLIB sin kodar flyt då over, slik at nokre satellittar får ein brøkdels syklus-feil
(berre FLOAT). Ein ekte mottakar held fasen nær koden. Testen flyttar difor fasen heile syklusar per satellitt før
kodinga – det endrar ikkje heiltalsløysinga.

Køyr: python3 testrekkjefolgje.py   (krev rtklib/test/data/rinex, sjå LES-MEG.txt)
"""
import sys
sys.path.insert(0, "../..")
import pyrtklib as R
import rtkmotor as M
from rtcm import _bits

D = "./rtklib/test/data/rinex/"


def frames(b):
    i = 0; out = []
    while i < len(b):
        n = ((b[i + 1] & 3) << 8) | b[i + 2]; out.append(b[i:i + n + 6]); i += n + 6
    return out


def rover_1002(usortert=True):
    """Roveren som 1002. usortert: to meldingar per epoke, høge satellittnummer først, låge sist.
    Elles: éi sortert melding per epoke."""
    obs, sta = R.obs_t(), R.sta_t()
    R.readrnx(D + "07590920.05o", 1, "", obs, R.nav_t(), sta)
    ep = {}
    for i in range(obs.n):
        d = obs.data[i]; ep.setdefault((d.time.time, d.time.sec), []).append(i)
    r = R.rtcm_t(); R.init_rtcm(r); r.staid = 0
    out = bytearray(); off = {}
    lam = R.CLIGHT / R.FREQ1
    for key in sorted(ep):
        idx = sorted(ep[key], key=lambda i: obs.data[i].sat)
        half = len(idx) // 2
        parts = ((idx[half:], 1), (idx[:half], 0)) if usortert else ((idx, 0),)   # høge PRN først, så låge
        for part, sync in parts:
            r.time = obs.data[idx[0]].time; r.obs.n = len(part)
            for j, i in enumerate(part):
                r.obs.data[j] = obs.data[i]
                d = r.obs.data[j]
                if d.sat not in off:                                # fasen nær koden, heile syklusar (sjå NB)
                    off[d.sat] = round(d.L[0] - d.P[0] / lam)
                d.L[0] -= off[d.sat]
            if R.gen_rtcm3(r, 1002, 0, sync):
                out.extend(bytes(r.buff[k] for k in range(r.nbyte)))
    return bytes(out)


def run(usortert):
    base = [f for f in frames(open("base.rtcm3", "rb").read()) if _bits(f[3:], 0, 12) != 1019]
    rov = frames(rover_1002(usortert))
    sols = []
    m = M.RtkMotor(on_solution=lambda g, i: sols.append(i["stat"]))
    assert m.start(install=False), M.LIB_ERR
    ep = R.Arr1Ddouble(6)
    for k, v in enumerate([2005, 4, 2, 0, 0, 0]):
        ep[k] = v
    t0 = R.epoch2time(ep); m.rb.time = t0; m.rv.time = t0
    m.load_nav(D + "07590920.05n")
    bi = 0; last = None
    for fr in rov:
        tow = _bits(fr[3:], 24, 30)                                 # tid i veka (ms) – same plass i 1002/1004/MSM
        if tow != last:                                             # ny roverepoke: mat basen for same epoke først
            last = tow
            while bi < len(base):
                f = base[bi]; bi += 1; m.base_feed(f)
                if _bits(f[3:], 0, 12) == 1077:
                    break
        m.rover_bytes(fr)
    s = m.status()
    o = m.rv.obs
    print("usortert" if usortert else "sortert ", {k: s[k] for k in ("rover_obs", "base_obs", "fix", "float", "none", "err")},
          "· siste roverepoke frå avkodaren:", [o.data[i].sat for i in range(o.n)])
    return s


def main():
    u, s = run(True), run(False)
    same = all(u[k] == s[k] for k in ("fix", "float", "none"))
    ok = same and u["rover_obs"] > 100 and u["fix"] >= 0.9 * u["rover_obs"] and "no common" not in u["err"]
    print("ALT OK" if ok else "FEIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
