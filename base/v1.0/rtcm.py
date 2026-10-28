# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""RTCM 3 i SNOWMAN Base: rammer, CRC-24Q, meldingstypar, satellittal og baseposisjon (1005/1006).

Base endrar aldri innhaldet i korreksjonane. Han finn heile rammer med rett CRC i straumen frå mottakaren (der det
også kan liggje tekst eller u-blox-data), og sender berre desse vidare til maskinene.
"""
import math
import time

CRC24Q_POLY = 0x1864CFB


def _crc24q_table():
    t = []
    for i in range(256):
        c = i << 16
        for _ in range(8):
            c <<= 1
            if c & 0x1000000:
                c ^= CRC24Q_POLY
        t.append(c & 0xFFFFFF)
    return t


_T = _crc24q_table()


def crc24q(data):
    c = 0
    for b in data:
        c = ((c << 8) & 0xFFFFFF) ^ _T[(c >> 16) ^ b]
    return c


def bits(buf, pos, n):
    """Les n bit (usignert) frå bitposisjon pos."""
    v = 0
    for i in range(pos, pos + n):
        v = (v << 1) | ((buf[i >> 3] >> (7 - (i & 7))) & 1)
    return v


def sbits(buf, pos, n):
    v = bits(buf, pos, n)
    return v - (1 << n) if v & (1 << (n - 1)) else v


def setbits(buf, pos, n, v):
    """Skriv n bit (to-komplement for negative tal) frå bitposisjon pos. Brukt til testdata."""
    if v < 0:
        v += 1 << n
    for i in range(n):
        bit = (v >> (n - 1 - i)) & 1
        p = pos + i
        if bit:
            buf[p >> 3] |= 1 << (7 - (p & 7))
        else:
            buf[p >> 3] &= ~(1 << (7 - (p & 7))) & 0xFF


def frame(payload):
    """Pakk inn ei melding som RTCM 3-ramme (0xD3, lengd, data, CRC-24Q)."""
    n = len(payload)
    head = bytes([0xD3, (n >> 8) & 0x03, n & 0xFF]) + bytes(payload)
    return head + crc24q(head).to_bytes(3, "big")


def msg_type(fr):
    """Meldingstypen i ei heil ramme (eller None)."""
    return bits(fr, 24, 12) if len(fr) >= 8 else None


SYSTEM = {"GPS": "GPS", "GLONASS": "GLO", "Galileo": "GAL", "BeiDou": "BDS", "QZSS": "QZS", "SBAS": "SBS"}


def system_of(t):
    """Satellittsystem for ei observasjonsmelding, eller None."""
    if 1001 <= t <= 1004:
        return "GPS"
    if 1009 <= t <= 1012:
        return "GLONASS"
    for base, name in ((1070, "GPS"), (1080, "GLONASS"), (1090, "Galileo"), (1100, "SBAS"), (1110, "QZSS"),
                       (1120, "BeiDou")):
        if base + 1 <= t <= base + 7:
            return name
    return None


EPHEMERIS = {1019: "GPS", 1020: "GLONASS", 1042: "BeiDou", 1044: "QZSS", 1045: "Galileo", 1046: "Galileo"}
ANTENNA = (1007, 1008, 1033)


def describe(t):
    """Kort forklaring på nynorsk av ein meldingstype (statussida)."""
    s = system_of(t)
    if s:
        if t <= 1012:
            return f"{s} observasjonar (eldre RTCM 3)"
        msm = t % 10
        return f"{s} observasjonar MSM{msm}" + (" – RTKLIB les ikkje MSM3" if msm == 3 else "")
    if t in EPHEMERIS:
        return f"{EPHEMERIS[t]} satellittbaner"
    return {1005: "Baseposisjon", 1006: "Baseposisjon med antennehøgd", 1007: "Antennenamn",
            1008: "Antennenamn og serienummer", 1013: "Systemparametrar", 1033: "Mottakar og antenne",
            1230: "GLONASS-bias", 4072: "u-blox (proprietær)"}.get(t, "Anna")


def n_sats(p, t):
    """Talet på satellittar i ei observasjonsmelding (p = meldinga utan rammehovud)."""
    try:
        if t in (1001, 1002, 1003, 1004):
            return bits(p, 55, 5)
        if t in (1009, 1010, 1011, 1012):
            return bits(p, 52, 5)
        if system_of(t) and len(p) >= 18:
            return bin(bits(p, 73, 32)).count("1") + bin(bits(p, 105, 32)).count("1")
    except IndexError:
        return None
    return None


# ---------- koordinatar (WGS84/EUREF89 – same ellipsoide på cm-nivå i denne samanhengen) ----------
A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)


def ecef_to_geo(x, y, z):
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - E2))
    for _ in range(6):
        n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - E2 * n / (n + h)))
    n = A / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return math.degrees(lat), math.degrees(lon), h


def geo_to_ecef(lat, lon, h):
    la, lo = math.radians(lat), math.radians(lon)
    n = A / math.sqrt(1 - E2 * math.sin(la) ** 2)
    return ((n + h) * math.cos(la) * math.cos(lo), (n + h) * math.cos(la) * math.sin(lo),
            (n * (1 - E2) + h) * math.sin(la))


def base_position(p):
    """1005/1006 → (stasjons-ID, x, y, z, antennehøgd eller None)."""
    t = bits(p, 0, 12)
    if t not in (1005, 1006) or len(p) < 19:
        return None
    x, y, z = sbits(p, 34, 38) * 1e-4, sbits(p, 74, 38) * 1e-4, sbits(p, 114, 38) * 1e-4
    hgt = bits(p, 152, 16) * 1e-4 if t == 1006 and len(p) >= 21 else None
    return bits(p, 12, 12), x, y, z, hgt


def make_1005(station, x, y, z):
    """Lag ei 1005-melding (baseposisjon). Brukt til testdata og simulator."""
    p = bytearray(19)
    setbits(p, 0, 12, 1005)
    setbits(p, 12, 12, station)
    setbits(p, 30, 1, 1)          # GPS
    setbits(p, 31, 1, 1)          # GLONASS
    setbits(p, 32, 1, 1)          # Galileo
    setbits(p, 34, 38, round(x * 1e4))
    setbits(p, 74, 38, round(y * 1e4))
    setbits(p, 114, 38, round(z * 1e4))
    return bytes(p)


class Framer:
    """Finn heile RTCM 3-rammer i ein bytestraum. Anna (tekst, UBX, støy) blir talt og hoppa over."""

    def __init__(self):
        self.buf = bytearray()
        self.crc_err = 0
        self.junk = 0

    def feed(self, data):
        self.buf += data
        b = self.buf
        out = []
        while True:
            i = b.find(0xD3)
            if i < 0:
                self.junk += len(b)
                b.clear()
                break
            if i:
                self.junk += i
                del b[:i]
            if len(b) < 3:
                break
            if b[1] & 0xFC:          # dei 6 reserverte bita skal vere 0 – ikkje ein rammestart
                self.junk += 1
                del b[:1]
                continue
            n = ((b[1] & 0x03) << 8) | b[2]
            if len(b) < n + 6:
                break
            fr = bytes(b[:n + 6])
            if crc24q(fr[:n + 3]) != int.from_bytes(fr[n + 3:], "big"):
                self.crc_err += 1
                self.junk += 1
                del b[:1]
                continue
            del b[:n + 6]
            out.append(fr)
        if len(b) > 8192:            # vern mot uendeleg buffer ved søppeldata
            self.junk += len(b) - 1100
            del b[:-1100]
        return out


class Stats:
    """Statistikk for éin straum: meldingstypar med intervall, satellittar per system og baseposisjon."""

    def __init__(self):
        self.types = {}             # type → {"n", "last", "iv"}
        self.sats = {}              # system → (tal, tid)
        self.base = None            # {"station", "x","y","z", "lat","lon","h", "hgt", "t"}
        self.frames = 0
        self.nbytes = 0
        self.last = 0.0
        self.first = 0.0

    def add(self, fr, now=None):
        now = now or time.time()
        self.frames += 1
        self.nbytes += len(fr)
        self.last = now
        if not self.first:
            self.first = now
        p = fr[3:-3]
        if len(p) < 2:
            return None
        t = bits(p, 0, 12)
        s = self.types.get(t)
        if s is None:
            s = self.types[t] = {"n": 0, "last": 0.0, "iv": None}
        if s["last"]:
            d = now - s["last"]
            if d > 0.05:            # fleire meldingar i same epoke (MSM med fleire delar) tel ikkje som nytt intervall
                s["iv"] = d if s["iv"] is None else 0.8 * s["iv"] + 0.2 * d
        s["n"] += 1
        s["last"] = now
        sy = system_of(t)
        if sy:
            k = n_sats(p, t)
            if k is not None:
                self.sats[sy] = (k, now)
        bp = base_position(p)
        if bp:
            st, x, y, z, hgt = bp
            if abs(x) + abs(y) + abs(z) > 1e6:
                lat, lon, h = ecef_to_geo(x, y, z)
                self.base = {"station": st, "x": x, "y": y, "z": z, "lat": lat, "lon": lon, "h": h, "hgt": hgt,
                             "t": now}
        return t

    def summary(self, now=None):
        now = now or time.time()
        types = []
        for t, s in sorted(self.types.items()):
            age = now - s["last"]
            types.append({"type": t, "n": s["n"], "iv": round(s["iv"], 1) if s["iv"] else None,
                          "age": round(age, 1), "aktiv": age < max(60.0, 3 * (s["iv"] or 0)), "kva": describe(t)})
        active = [x for x in types if x["aktiv"]]
        systems = sorted({system_of(x["type"]) for x in active if system_of(x["type"])})
        sats = {k: v[0] for k, v in self.sats.items() if now - v[1] < 30}
        r = {"frames": self.frames, "bytes": self.nbytes, "age": round(now - self.last, 1) if self.last else None,
             "types": types, "systems": systems, "sats": sats, "satsTotal": sum(sats.values()),
             "eph": sorted({EPHEMERIS[x["type"]] for x in active if x["type"] in EPHEMERIS}),
             "msm3": any(system_of(x["type"]) and x["type"] > 1070 and x["type"] % 10 == 3 for x in active)}
        if self.base:
            b = self.base
            r["base"] = {"station": b["station"], "lat": round(b["lat"], 8), "lon": round(b["lon"], 8),
                         "h": round(b["h"], 3), "hgt": b["hgt"], "age": round(now - b["t"], 1)}
        return r

    def bitrate(self, now=None):
        now = now or time.time()
        span = (self.last - self.first) if self.first else 0
        return int(self.nbytes * 8 / span) if span > 5 else 0
