# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Kontroll av RTCM 3-korreksjonane frå NTRIP-casteren – før dei blir sende vidare til mottakaren.

Dataa blir ikkje endra; SNOWMAN berre «lyttar» for å kunne seie om korreksjonane er gyldige:
  - gyldige rammer (0xD3 + lengd + CRC-24Q) og CRC-feil
  - kva meldingstypar og satellittsystem basen sender
  - basestasjonen (ID og posisjon frå 1005/1006) og avstanden til maskina
Då kan ein skilje mellom feil i basen/mountpointet og feil i mottakaren.
"""
import math, time

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


def _bits(buf, pos, n):
    """Les n bit (usignert) frå bitposisjon pos."""
    v = 0
    for i in range(pos, pos + n):
        v = (v << 1) | ((buf[i >> 3] >> (7 - (i & 7))) & 1)
    return v


def _sbits(buf, pos, n):
    v = _bits(buf, pos, n)
    return v - (1 << n) if v & (1 << (n - 1)) else v


def system_of(t):
    """Satellittsystem for ei observasjonsmelding, eller None."""
    if 1001 <= t <= 1004:
        return "GPS"
    if 1009 <= t <= 1012:
        return "GLONASS"
    for base, name in ((1070, "GPS"), (1080, "GLONASS"), (1090, "Galileo"), (1100, "SBAS"), (1110, "QZSS"), (1120, "BeiDou")):
        if base + 1 <= t <= base + 7:
            return name
    return None


def ecef_to_geo(x, y, z):
    """EUREF89/WGS84 ECEF → (lat, lon) i grader."""
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(6):
        n = a / math.sqrt(1 - e2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1 - e2 * n / (n + h)))
    return math.degrees(lat), math.degrees(lon)


def dist_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class RtcmMonitor:
    def __init__(self):
        self.reset()

    def reset(self):
        self.buf = bytearray()
        self.frames = 0
        self.crc_err = 0
        self.junk = 0  # byte som ikkje høyrde til ei RTCM-ramme (t.d. tekst frå casteren)
        self._jraw = ""
        self.junk_text = ""  # siste lesbare tekst blant desse (t.d. «Server: …» etter «ICY 200 OK») – til diagnose
        self.types = {}
        self.station = None
        self.base = None  # (lat, lon)
        self.last = 0.0
        self.first = 0.0  # tida for første gyldige ramme etter oppkoplinga
        self.nbytes = 0   # byte motteke på DENNE oppkoplinga (ikkje samla for heile økta)

    def _skip(self, chunk):
        """Byte som ikkje er RTCM: tel dei og hugs lesbar tekst (vist i statusen, aldri sendt til mottakaren)."""
        self.junk += len(chunk)
        self._jraw = (getattr(self, "_jraw", "") + "".join(chr(c) if 32 <= c < 127 else (" " if c in (9, 10, 13) else "\x00") for c in chunk))[-400:]

    def _flush_text(self):
        """Ein samanhengande bit med ikkje-RTCM er ferdig (ei ramme kom): lagre teksten i han, om han er lesbar."""
        raw = getattr(self, "_jraw", "")
        t = " ".join(raw.replace("\x00", " ").split())
        self._jraw = ""
        # berre tekst – ikkje restar av øydelagde rammer (få lesbare teikn innimellom binære byte)
        if len(t) >= 6 and sum(c != "\x00" for c in raw) >= 0.8 * len(raw):
            self.junk_text = (self.junk_text + " | " + t if self.junk_text else t)[-160:]

    def feed(self, data):
        """Kontrollerer straumen og returnerer berre heile RTCM 3-rammer med rett CRC (v1.6.83).
        Det er desse – og ikkje rådataa – som blir sende til mottakaren: tekst frå casteren (t.d. «Server:»/«Date:»-linjer
        etter «ICY 200 OK») eller øydelagde byte kunne elles bli tolka som kommandoar av mottakaren («@GNSS,…,ERROR»)."""
        self.nbytes += len(data)
        self.buf += data
        b = self.buf
        out = bytearray()
        while True:
            i = b.find(0xD3)
            if i < 0:
                self._skip(bytes(b))
                b.clear()
                break
            if i:
                self._skip(bytes(b[:i]))
                del b[:i]
            if len(b) < 3:
                break
            n = ((b[1] & 0x03) << 8) | b[2]
            if b[1] & 0xFC:  # dei 6 reserverte bita skal vere 0 – ikkje ein rammestart
                self.junk += 1
                del b[:1]
                continue
            if len(b) < n + 6:
                break
            frame = bytes(b[:n + 6])
            if crc24q(frame[:n + 3]) != int.from_bytes(frame[n + 3:n + 6], "big"):
                self.crc_err += 1
                self.junk += 1
                del b[:1]
                continue
            del b[:n + 6]
            self._flush_text()
            self._frame(frame[3:3 + n])
            out += frame
        if len(b) > 4096:  # vern mot uendeleg buffer ved søppeldata
            self.junk += len(b) - 1024
            del b[:-1024]
        return bytes(out)

    def _frame(self, p):
        self.frames += 1
        self.last = time.time()
        if not self.first:
            self.first = self.last
        if len(p) < 2:
            return
        t = _bits(p, 0, 12)
        self.types[t] = self.types.get(t, 0) + 1
        if t in (1005, 1006) and len(p) >= 19:
            self.station = _bits(p, 12, 12)
            x = _sbits(p, 34, 38) * 1e-4
            y = _sbits(p, 74, 38) * 1e-4
            z = _sbits(p, 114, 38) * 1e-4
            if abs(x) + abs(y) + abs(z) > 1e6:
                self.base = ecef_to_geo(x, y, z)

    def status(self, lat=None, lon=None, bytes_in=None):
        """bytes_in blir ikkje lenger brukt (v1.6.48): vurderinga byggjer på byte motteke på denne oppkoplinga."""
        systems = sorted({s for t in self.types for s in [system_of(t)] if s})
        obs = any(system_of(t) for t in self.types)
        r = {"frames": self.frames, "crcErr": self.crc_err, "junk": self.junk, "junkText": self.junk_text,
             "types": {str(k): v for k, v in sorted(self.types.items())}, "systems": systems,
             "station": self.station, "age": round(time.time() - self.last, 1) if self.last else None}
        if self.base:
            r["base"] = [round(self.base[0], 6), round(self.base[1], 6)]
            if lat is not None and lon is not None:
                r["baseKm"] = round(dist_km(lat, lon, *self.base), 2)
        # Kort vurdering på nynorsk – vist på NTRIP-sida
        since = time.time() - self.first if self.first else 0.0
        if self.nbytes < 200:
            msg = "Ventar på data frå casteren."
        elif self.frames == 0:
            msg = ("Ventar på første gyldige RTCM-melding …" if self.nbytes < 2000
                   else "FEIL: dataa frå casteren er ikkje RTCM 3 (feil mountpoint eller format).")
        elif not obs:
            msg = ("Ventar på observasjonar frå basen …" if since < 10
                   else "FEIL: basen sender ingen observasjonar – RTK er ikkje mogleg.")
        elif self.station is None:
            # 1005/1006 kjem typisk kvart 5.–30. sekund – ikkje FEIL før det har gått 30 s
            msg = (f"Ventar på posisjonen til basen (1005/1006) – kan ta opptil 30 s ({since:.0f} s)." if since < 30
                   else "FEIL: basen sender ikkje posisjonen sin (1005/1006) – RTK er ikkje mogleg.")
        elif r.get("age") is not None and r["age"] > 10:
            msg = f"FEIL: ingen nye korreksjonar på {r['age']:.0f} s."
        elif r.get("baseKm") is not None and r["baseKm"] > 35:
            msg = f"ÅTVARING: basen er {r['baseKm']} km unna – for langt for sikker RTK FIX."
        else:
            msg = "OK: gyldige RTCM-korreksjonar frå basen. Står mottakaren likevel utan RTK, ligg feilen i mottakaren."
        r["verdict"] = msg
        return r
