# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Lag ein u-blox UBX-straum (RXM-RAWX + RXM-SFRBX) av RTKLIB-testdata 0759 – til test av UBX i RTK-motoren.

Same rover som lagrtcm.py, men i det formatet ein ZED-F9P sender som rover:
  RXM-RAWX  – éi melding per epoke: pseudoavstand, berefase, doppler, lock-tid, sporingsstatus per signal
  RXM-SFRBX – navigasjonsdataa frå satellitten: GPS LNAV underramme 1–3 (banene), 10 ord à 30 bit
Banene blir koda frå RINEX-navigasjonsfila etter IS-GPS-200 og kontrollerte med RTKLIB decode_frame før dei blir skrivne.

Bruk:  python3 lagubx.py          → rover.ubx (og kontroll av SFRBX-kodinga)
"""
import math
import struct
import pyrtklib as R

D = "./rtklib/test/data/rinex/"
SC2RAD = math.pi


def ubx(cls, mid, payload):
    body = bytes([cls, mid]) + struct.pack("<H", len(payload)) + payload
    a = b = 0
    for x in body:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return b"\xb5\x62" + body + bytes([a, b])


class Bits:
    """Bitstraum utan paritet: 24 databit per ord, slik RTKLIB pakkar underrammene."""
    def __init__(self):
        self.v, self.n = 0, 0

    def put(self, val, nbit, signed=False):
        val = int(round(val))
        lo, hi = (-(1 << (nbit - 1)), (1 << (nbit - 1)) - 1) if signed else (0, (1 << nbit) - 1)
        assert lo <= val <= hi, (val, nbit)
        self.v = (self.v << nbit) | (val & ((1 << nbit) - 1))
        self.n += nbit

    def words(self):
        assert self.n == 240, self.n
        return [(self.v >> (24 * (9 - i))) & 0xFFFFFF for i in range(10)]


def subframes(e, tow_s):
    """GPS LNAV underramme 1–3 for ephemeris e. tow_s = sendetid (s i veka) for underramme 1."""
    out = []
    for sid in (1, 2, 3):
        b = Bits()
        b.put(0x8B, 8); b.put(0, 16)                                   # TLM: preamble + meldingar/reservert
        b.put(int(tow_s // 6) + sid, 17); b.put(0, 2); b.put(sid, 3); b.put(0, 2)   # HOW
        if sid == 1:
            b.put(e.week % 1024, 10); b.put(e.code, 2); b.put(e.sva, 4); b.put(e.svh, 6)
            b.put(e.iodc >> 8, 2); b.put(e.flag, 1); b.put(0, 87)
            b.put(e.tgd[0] / 2 ** -31, 8, True); b.put(e.iodc & 0xFF, 8)
            toc = R.time2gpst(e.toc, R.Arr1Dint(1))
            b.put(toc / 16, 16); b.put(e.f2 / 2 ** -55, 8, True); b.put(e.f1 / 2 ** -43, 16, True)
            b.put(e.f0 / 2 ** -31, 22, True); b.put(0, 2)
        elif sid == 2:
            b.put(e.iode, 8); b.put(e.crs / 2 ** -5, 16, True); b.put(e.deln / SC2RAD / 2 ** -43, 16, True)
            b.put(e.M0 / SC2RAD / 2 ** -31, 32, True); b.put(e.cuc / 2 ** -29, 16, True); b.put(e.e / 2 ** -33, 32)
            b.put(e.cus / 2 ** -29, 16, True); b.put(math.sqrt(e.A) / 2 ** -19, 32); b.put(e.toes / 16, 16)
            b.put(0 if e.fit <= 4 else 1, 1); b.put(0, 5); b.put(0, 2)
        else:
            b.put(e.cic / 2 ** -29, 16, True); b.put(e.OMG0 / SC2RAD / 2 ** -31, 32, True)
            b.put(e.cis / 2 ** -29, 16, True); b.put(e.i0 / SC2RAD / 2 ** -31, 32, True)
            b.put(e.crc / 2 ** -5, 16, True); b.put(e.omg / SC2RAD / 2 ** -31, 32, True)
            b.put(e.OMGd / SC2RAD / 2 ** -43, 24, True); b.put(e.iode, 8); b.put(e.idot / SC2RAD / 2 ** -43, 14, True)
            b.put(0, 2)
        out.append(b.words())
    return out


def sfrbx(prn, words):
    p = struct.pack("<BBBBBBBB", 0, prn, 0, 0, 10, 0, 2, 0)            # gnssId GPS, svId, sigId L1C/A, numWords 10, version 2
    p += b"".join(struct.pack("<I", w << 6) for w in words)          # databit i bit 29–6, paritet (ikkje brukt) i 5–0
    return ubx(0x02, 0x13, p)


def check_eph(words3, e):
    """Kontroll: RTKLIB skal lese underrammene attende til same bane."""
    buf = getattr(R, "Arr1Dunsigned char")(150)
    for k in range(150):
        buf[k] = 0
    for s, words in enumerate(words3):
        for i, w in enumerate(words):
            for j in range(3):
                buf[s * 30 + i * 3 + j] = (w >> (16 - 8 * j)) & 0xFF
    out = R.eph_t()
    ion, utc = R.Arr1Ddouble(8), R.Arr1Ddouble(8)
    R.decode_frame(buf, out, R.alm_t(), ion, utc)
    bad = [k for k, tol in (("iode", 0), ("iodc", 0), ("toes", 0), ("A", 1e-3), ("e", 1e-12), ("M0", 1e-9), ("omg", 1e-9),
                            ("i0", 1e-9), ("OMG0", 1e-9), ("f0", 1e-15), ("f1", 1e-20), ("crs", 1e-3), ("idot", 1e-15))
           if abs(getattr(out, k) - getattr(e, k)) > tol]
    return bad


def rawx(epoch, week):
    """RXM-RAWX for éi epoke (liste av obsd_t). Lock-tid aukar så lenge det ikkje er brot (LLI)."""
    tow = R.time2gpst(epoch[0].time, R.Arr1Dint(1))
    meas = []
    for d in epoch:
        for f, sig in ((0, 0), (1, 3)):                                  # L1 C/A (sigId 0) og L2 (sigId 3 L2 CL)
            if d.P[f] == 0.0:
                continue
            key = (d.sat, f)
            if d.LLI[f] & 1 or key not in LOCK:
                LOCK[key] = tow
            lock_ms = min(64500, int((tow - LOCK[key]) * 1000))
            trk = 0x01 | (0x02 | 0x04 if d.L[f] != 0.0 else 0)          # pr gyldig, fase gyldig, halv syklus løyst
            meas.append(struct.pack("<ddfBBBBHBBBBBB", d.P[f], d.L[f], d.D[f], 0, d.sat, sig, 0, lock_ms,
                                    45, 3, 1, 3, trk, 0))
    head = struct.pack("<dHbBBB2s", tow, week, 13, len(meas), 0x01, 1, b"\0\0")
    return ubx(0x02, 0x15, head + b"".join(meas))


LOCK = {}


def main():
    nav = R.nav_t()
    R.readrnx(D + "07590920.05n", 0, "", R.obs_t(), nav, R.sta_t())
    obs = R.obs_t()
    R.readrnx(D + "07590920.05o", 1, "", obs, R.nav_t(), R.sta_t())
    ep = {}
    for i in range(obs.n):
        d = obs.data[i]
        ep.setdefault(d.time.time, []).append(d)
    t0 = min(ep)
    w = R.Arr1Dint(1)
    tow0 = R.time2gpst(obs.data[0].time, w)
    week = w[0]
    # Éi bane per satellitt: den med toe nærast starten (som mottakaren ville sendt ved oppstart)
    best = {}
    for i in range(nav.n):
        e = nav.eph[i]
        if e.sat and (e.sat not in best or abs(e.toe.time - t0) < abs(best[e.sat].toe.time - t0)):
            best[e.sat] = e
    sf = {}
    for sat, e in sorted(best.items()):
        words3 = subframes(e, tow0)
        bad = check_eph(words3, e)
        assert not bad, f"SFRBX-koding for G{sat:02d} gir feil i {bad}"
        sf[sat] = words3
    out = bytearray()
    for n, t in enumerate(sorted(ep)):
        if n < 3:                                       # banene kjem over dei første epokane, som frå ein ekte mottakar
            for sat, words3 in sf.items():
                out += sfrbx(sat, words3[n])
        out += rawx(ep[t], week)
        out += b"$GNGGA,000000.00,6216.0,N,00636.0,E,1,08,1.0,100.0,M,0.0,M,,*00\r\n"   # NMEA i same straum
    open("rover.ubx", "wb").write(out)
    print(f"rover.ubx: {len(ep)} RAWX-epokar, SFRBX for {len(sf)} satellittar (alle kontrollerte mot RTKLIB), {len(out)} byte")


if __name__ == "__main__":
    main()
