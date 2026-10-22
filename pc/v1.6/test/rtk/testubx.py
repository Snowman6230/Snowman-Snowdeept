# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av UBX (RXM-RAWX + RXM-SFRBX) i RTK-motoren – dei fire krava frå eigaren 2026-10-22:

  1  Demuxen handterer ufullstendige rammer over fleire USB-lesingar utan å miste synkronisering
  2  raw_t (UBX) og rtcm_t (RTCM) gir observasjonar og baner som RTK-motoren kan bruke – same svar som med RTCM-rover
  3  Rådata frå rover og base blir tidsjusterte rett (same epoke, forsinka base, feil PC-klokke/veke)
  4  SFRBX-banene kjem faktisk inn i den felles nav-strukturen (ingen andre baner tilgjengelege)

Krev rover.ubx (lagubx.py), base.rtcm3 og rover.rtcm3 (lagrtcm.py 1077) og RTKLIB-testdata i ./rtklib/.
Kvart scenario køyrer i eigen prosess, sidan RTKLIB si klokke (timeset) gjeld heile prosessen.
Bruk:  python3 testubx.py
"""
import json
import math
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
os.chdir(HERE)
import rtkmotor as M                       # noqa: E402
from rtcm import _bits                     # noqa: E402

NAVFILE = "rtklib/test/data/rinex/07590920.05n"
OBSFILE = "rtklib/test/data/rinex/07590920.05o"


def rtcm_frames(b):
    i, out = 0, []
    while i < len(b):
        n = ((b[i + 1] & 3) << 8) | b[i + 2]
        out.append(b[i:i + n + 6])
        i += n + 6
    return out


def ubx_split(b):
    """Del rover.ubx i UBX-rammer og NMEA-linjer (fasit for demux-testen)."""
    i, fr, txt = 0, [], bytearray()
    while i < len(b):
        if b[i] == 0xB5:
            n = b[i + 4] | (b[i + 5] << 8)
            fr.append(b[i:i + n + 8])
            i += n + 8
        else:
            j = b.index(b"\n", i) + 1
            txt += b[i:j]
            i = j
    return fr, bytes(txt)


# ---------------------------------------------------------------------------------------------- 1 Demux
def test_demux():
    ubx = open("rover.ubx", "rb").read()
    rtcm = open("rover.rtcm3", "rb").read()
    uf, utxt = ubx_split(ubx)
    rf = rtcm_frames(rtcm)
    # Straum som frå ein mottakar: UBX, RTCM og NMEA om kvarandre, starta midt i ei ramme, med ei øydelagd ramme
    want_frames, stream, want_txt = [], bytearray(), bytearray()
    stream += uf[5][37:]                                            # oppstart midt i ein RAWX (B5 62 kan finnast inni)
    for k in range(max(len(uf), len(rf))):
        if k < len(uf):
            stream += uf[k]
            want_frames.append(uf[k])
        if k < len(rf):
            stream += rf[k]
            want_frames.append(rf[k])
        line = b"$GNGGA,%06d.00,6223.5,N,00635.4,E,1,12,0.8,400.0,M,40.0,M,,*00\r\n" % k
        stream += line
        want_txt += line
        if k == 40:                                                 # øydelagd UBX-ramme (feil kontrollsum)
            bad = bytearray(uf[k])
            bad[30] ^= 0xFF
            stream += bad
    res = {}
    for name, chunks in (("1 byte", lambda: 1), ("tilfeldig 1–700", lambda: random.randint(1, 700)),
                         ("USB 64", lambda: 64), ("alt i éin", None)):
        random.seed(1)
        d = M.Demux()
        got, txt, i = [], bytearray(), 0
        while i < len(stream):
            n = len(stream) - i if chunks is None else chunks()
            f, t = d.feed(bytes(stream[i:i + n]))
            got += [x[1] for x in f]
            txt += t
            i += n
        ok_frames = got == want_frames
        ok_txt = all(line in txt for line in want_txt.split(b"\r\n") if line)
        res[name] = {"rammer": f"{len(got)}/{len(want_frames)}", "rett": ok_frames, "nmea_heil": ok_txt,
                     "att_i_buffer": len(d.buf)}
    ok = all(r["rett"] and r["nmea_heil"] and r["att_i_buffer"] == 0 for r in res.values())
    return ok, res


# ---------------------------------------------------------------------------------------------- scenario-køyring
def scenario(name):
    """Køyrer i eigen prosess. Skriv JSON med resultatet."""
    import pyrtklib as R
    sols = []
    m = M.RtkMotor(on_solution=lambda g, i: sols.append((g, i)))
    ref = None if name in ("feil_klokke", "baner_for_rover") else (2005, 4, 2)
    assert m.start(install=False, ref_time=ref), M.LIB_ERR
    if name == "rtcm_rover":                                       # samanlikningsgrunnlag: same rover som RTCM
        m.load_nav(NAVFILE)
    base = rtcm_frames(open("base.rtcm3", "rb").read())
    if name in ("sfrbx_aleine", "feil_klokke"):                    # ingen 1019 frå basen og inga BRDC-fil
        base = [f for f in base if _bits(f[3:], 0, 12) != 1019]
    epochs_base = []                                               # [[rammer for éi baseepoke], …]
    cur = []
    for f in base:
        cur.append(f)
        if _bits(f[3:], 0, 12) == 1077:
            epochs_base.append(cur)
            cur = []
    if name == "rtcm_rover":
        rover = [[f] for f in rtcm_frames(open("rover.rtcm3", "rb").read())]
    else:
        uf, _ = ubx_split(open("rover.ubx", "rb").read())
        if name == "baner_for_rover":                              # alle SFRBX før første RAWX (oppstart)
            uf = [f for f in uf if f[2:4] == b"\x02\x13"] + [f for f in uf if f[2:4] != b"\x02\x13"]
        rover, cur = [], []
        for f in uf:
            cur.append(f)
            if f[2:4] == b"\x02\x15":
                rover.append(cur)
                cur = []
    delay = 1 if name == "forsinka_base" else 0
    if name == "baner_for_rover":                                  # basen (med 1019) kjem før mottakaren
        for f in epochs_base[0] + epochs_base[1]:
            m.base_feed(f)
        epochs_base = [[]] * 2 + epochs_base[2:]
    rover_t = []
    random.seed(7)
    for k, rv in enumerate(rover):
        kb = k - delay
        if 0 <= kb < len(epochs_base):
            for f in epochs_base[kb]:
                m.base_feed(f)
        blob = b"".join(rv)
        if name == "rtcm_rover":
            m.rover_bytes(blob)
        else:
            i = 0
            while i < len(blob):                                    # USB-bitar av tilfeldig storleik
                n = random.randint(1, 512)
                m.rover_bytes(blob[i:i + n])
                i += n
        o = (m.rv if name == "rtcm_rover" else m.ru).obs
        if o.n:
            rover_t.append(o.data[0].time.time + o.data[0].time.sec)
    s = m.status()
    fix = [(g, i) for g, i in sols if i["stat"] == 1]

    def ecef_of(g):
        p = g.split(",")
        lat = int(p[2][:2]) + float(p[2][2:]) / 60
        lon = int(p[4][:3]) + float(p[4][3:]) / 60
        return [round(lat, 10), round(lon, 10), float(p[9]), p[1]]
    out = {"name": name, "sol": len(sols), "fix": len(fix), "rover_obs": s["rover_obs"], "rover_fmt": s["rover_fmt"],
           "eph": s["eph"], "eph_rover": s["eph_rover"], "eph_fixed": s["eph_fixed"], "clock_off": s["clock_off"],
           "tdiff": s["tdiff"], "err": s["err"], "types": s["rover_types"], "ubx_bad": s["ubx_bad"],
           "fixpos": [ecef_of(g) for g, _ in fix], "ages": sorted(set(round(i["age"], 2) for _, i in sols)),
           "rover_t": rover_t}
    # Krav 4: banene i den felles nav-strukturen skal vere dei same som i RINEX-fila (same veke, toe, iode, bane)
    if name in ("sfrbx_aleine", "feil_klokke", "baner_for_rover"):
        rin = R.nav_t()
        R.readrnx(NAVFILE, 0, "", R.obs_t(), rin, R.sta_t())
        t0 = rover_t[0]
        best = {}
        for i in range(rin.n):
            e = rin.eph[i]
            if e.sat and (e.sat not in best or abs(e.toe.time - t0) < abs(best[e.sat].toe.time - t0)):
                best[e.sat] = e
        cmp_, bad = 0, []
        for sat, e in best.items():
            g = m.nav.eph[sat - 1]
            cmp_ += 1
            if not (g.sat == sat and g.week == e.week and g.toe.time == e.toe.time and g.iode == e.iode
                    and abs(g.A - e.A) < 1e-3 and abs(g.M0 - e.M0) < 1e-9 and abs(g.f0 - e.f0) < 1e-15):
                bad.append([sat, g.week, e.week, g.toe.time, e.toe.time])
        out["nav_samanlikna"] = cmp_
        out["nav_feil"] = bad
    # Krav 3: tida i løysingane skal vere roverepokane
    if sols:
        import calendar
        st = []
        for g, _ in sols:
            hh, mm, ss = int(g.split(",")[1][:2]), int(g.split(",")[1][2:4]), float(g.split(",")[1][4:])
            st.append(hh * 3600 + mm * 60 + ss)
        rv_utc = [(t - 13) % 86400 for t in rover_t]                # GPS → UTC (13 s i 2005)
        # Løysingstida er roverepoka retta for mottakarklokka (ms-nivå), avrunda til 0,01 s i GGA
        out["sol_tider_i_rover"] = all(min(abs(x - r) for r in rv_utc) < 0.02 for x in st)
        out["maks_alder"] = max(abs(i["age"]) for _, i in sols)
    print(json.dumps(out))


def run(name):
    p = subprocess.run([sys.executable, __file__, "--scenario", name], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return {"name": name, "crash": p.stderr[-800:]}
    return json.loads(p.stdout.strip().splitlines()[-1])


def main():
    print("1  Demux (ufullstendige rammer, oppstart midt i ramme, øydelagd ramme, RTCM+UBX+NMEA om kvarandre)")
    ok1, r1 = test_demux()
    for k, v in r1.items():
        print(f"   {k:16s} {v}")
    print("   →", "OK" if ok1 else "FEIL")

    R = {n: run(n) for n in ("rtcm_rover", "ubx_rover", "forsinka_base", "feil_klokke", "sfrbx_aleine", "baner_for_rover")}
    for n, r in R.items():
        if "crash" in r:
            print("KRASJ i", n, r["crash"])
            sys.exit(1)
    ref, ub = R["rtcm_rover"], R["ubx_rover"]

    print("\n2  UBX og RTCM gir same RTK-svar (raw_t vs rtcm_t inn i same motor)")
    a = {p[3]: p for p in ref["fixpos"]}
    b = {p[3]: p for p in ub["fixpos"]}
    common = sorted(set(a) & set(b))
    dmax = max((max(abs(a[t][0] - b[t][0]) * 111320, abs(a[t][1] - b[t][1]) * 111320 * math.cos(math.radians(a[t][0])), abs(a[t][2] - b[t][2]))
                for t in common), default=None)
    print(f"   RTCM-rover: FIX {ref['fix']}/{ref['sol']}   UBX-rover: FIX {ub['fix']}/{ub['sol']} ({ub['rover_fmt']}, "
          f"typar {ub['types']})")
    print(f"   felles FIX-epokar {len(common)}, største avvik UBX mot RTCM {dmax if dmax is None else round(dmax, 4)} m")
    ok2 = ub["fix"] >= ref["fix"] - 2 and dmax is not None and dmax < 0.002 and ub["rover_fmt"] == "UBX RAWX"
    print("   →", "OK" if ok2 else "FEIL")

    print("\n3  Tidsjustering rover/base")
    fb, fk, bf = R["forsinka_base"], R["feil_klokke"], R["baner_for_rover"]
    print(f"   same epoke:      tdiff {ub['tdiff']} s, alder {ub['ages']}, løysingstid = roverepoke: "
          f"{ub.get('sol_tider_i_rover')}")
    print(f"   base éi epoke (30 s) seint: tdiff {fb['tdiff']} s, største alder brukt {fb.get('maks_alder')} s "
          f"(grense {M.MAX_BASE_AGE} s), løysingstid = roverepoke: {fb.get('sol_tider_i_rover')}")
    print(f"   PC-klokke 2026, data 2005 (ingen ref_time): største klokkeavvik retta {fk['clock_off']} s, "
          f"tdiff {fk['tdiff']} s, FIX {fk['fix']}/{fk['sol']}")
    ok3 = (abs(ub["tdiff"]) < 0.02 and ub.get("sol_tider_i_rover") and abs(fb["tdiff"] - 30) < 0.02
           and fb.get("sol_tider_i_rover") and fb.get("maks_alder", 99) <= M.MAX_BASE_AGE + 0.02
           and fk["fix"] >= ub["fix"] - 3 and abs(fk["clock_off"] or 0) > 1e8 and abs(fk["tdiff"]) < 0.02)
    print("   →", "OK" if ok3 else "FEIL")

    print("\n4  SFRBX → felles nav")
    sa = R["sfrbx_aleine"]
    for r, txt in ((sa, "basen utan 1019, inga BRDC-fil"), (fk, "same, og PC-klokka 21 år feil"),
                   (bf, "baner frå base og SFRBX før første RAWX, PC-klokka feil")):
        print(f"   {txt:55s} baner frå mottakaren {r['eph_rover']}, veke retta {r['eph_fixed']}, "
              f"mot RINEX {r['nav_samanlikna']} sat, avvik {r['nav_feil'] or 'ingen'}, FIX {r['fix']}/{r['sol']}")
    ok4 = (sa["eph_rover"] >= 20 and not sa["nav_feil"] and not fk["nav_feil"] and not bf["nav_feil"]
           and bf["eph_fixed"] > 0 and min(sa["fix"], fk["fix"], bf["fix"]) >= ub["fix"] - 3)
    print("   →", "OK" if ok4 else "FEIL")

    allok = ok1 and ok2 and ok3 and ok4
    print("\nALT OK" if allok else "\nNOKO FEILA")
    sys.exit(0 if allok else 1)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--scenario":
        scenario(sys.argv[2])
    else:
        main()
