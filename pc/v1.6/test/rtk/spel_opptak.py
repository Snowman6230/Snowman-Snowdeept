"""Spel av eit opptak frå SNOWMAN (v1.6.104): mottakar- og basedata i same rekkjefølgje som dei kom, gjennom RTK-motoren.

Bruk: python3 spel_opptak.py opptak-ÅÅÅÅMMDD-TTMMSS.bin [banefil.rnx] [--detalj] [--dato=ÅÅÅÅ-MM-DD]
  banefil: BRDC-fila SNOWMAN brukte (data/brdc/…) – trengst når verken mottakar eller base sender baner.
  --detalj: skriv kvar epoke (status, ratio, satellittar, feilmelding).
  --dato: veka for RTCM-tida (berre for test, når opptaket er laga med simulerte data frå ein annan dato).

Veka for RTCM-tida blir teken frå tidspunktet i opptaket (ikkje PC-klokka no), så opptaket kan spelast av seinare.
"""
import struct
import sys
import time

sys.path.insert(0, "../..")
import rtkmotor as M


def les(path):
    """Postane i opptaket: (tid, kind, byte)."""
    out = []
    with open(path, "rb") as f:
        while True:
            h = f.read(13)
            if len(h) < 13:
                break
            t, k, n = struct.unpack("<dcI", h)
            out.append((t, k.decode(), f.read(n)))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    detalj = "--detalj" in sys.argv
    if not args:
        print(__doc__)
        return 2
    post = les(args[0])
    if not post:
        print("Tomt opptak.")
        return 1
    t0 = time.gmtime(post[0][0])
    ref = (t0.tm_year, t0.tm_mon, t0.tm_mday)
    for a in sys.argv[1:]:
        if a.startswith("--dato="):
            ref = tuple(int(x) for x in a[7:].split("-"))
    sols = []
    m = M.RtkMotor(on_solution=lambda g, i: sols.append(i))
    assert m.start(install=False, ref_time=ref), M.LIB_ERR
    if len(args) > 1:
        print("baner frå fil:", m.load_nav(args[1]))
    n_r = n_b = 0
    last = (0, 0)
    for t, k, b in post:
        if k == "B":
            m.base_feed(b); n_b += 1
        else:
            m.rover_bytes(b); n_r += 1
        s = m.stats
        cnt = (s["rover_obs"], s["none"])
        if detalj and cnt != last and s["rover_obs"]:
            last = cnt
            print(time.strftime("%H:%M:%S", time.localtime(t)), M.STATNAME.get(s["last_stat"], "–"),
                  "ratio", s["last_ratio"], "sats", s.get("sats"), s["err"][:100])
    s = m.status()
    print(f"Postar: mottakar {n_r}, base {n_b} · tid {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(post[0][0]))}"
          f" – {time.strftime('%H:%M:%S', time.localtime(post[-1][0]))}")
    print({k: s[k] for k in ("rover_obs", "base_obs", "eph", "eph_file", "fix", "float", "single", "none", "tdiff",
                             "rover_types", "base_types", "err", "sats")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
