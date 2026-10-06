# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Hellingskorreksjon: antenna står ikkje rett over beltet når maskina står på skrå.

Antenna sit antZ meter over snøflata, vinkelrett på maskina. På skrå (helling θ) blir då
  - høgda frå antenna ned til snøflata h·cos θ, ikkje h, og
  - punktet der maskina står (under midten av maskina) flytt h·sin θ opp i bakken frå punktet rett under antenna.
Utan korreksjon blir snødjupna for høg med h·(1/cos θ − 1): 4 cm ved 10°, 18 cm ved 20°, 43 cm ved 30° (h = 2,8 m).
Berre høgdekorreksjon utan å flytte punktet gjer feilen STØRRE, så begge delar blir alltid gjorde saman.

Kjelder for hellinga (Innst. › Kalibrering › Helling):
  auto    – hellingsmålar i antenna om ho sender han (NMEA HPR, PSAT,HPR, PASHR eller PTNL,AVR), elles utrekna
  estimat – alltid utrekna: helling langs køyreretninga frå GNSS-høgda (presist når maskina køyrer),
            sidehelling frå terrengmodellen der maskina står
  av      – ingen korreksjon (som før v1.6.31)

Forteikn (kan snuast i innstillingane om antenna er montert annleis): stamp + = fronten opp, krenging + = høgre side ned.
"""
import math, time
from collections import deque

MAX_SLOPE = math.tan(math.radians(40))  # meir enn 40° er ikkje truverdig for ei trakkemaskin
ANT_FRESH = 2.0  # sekund: så lenge er ei hellingsmåling frå antenna gyldig


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


class Helling:
    def __init__(self):
        self.ant = None  # siste måling frå antenna: {roll, pitch, heading, t, src}
        self.hist = deque(maxlen=200)  # (t, lat, lon, alt) – til helling langs køyreretninga
        self.sentences = set()  # kva hellingsmeldingar antenna har sendt (vist i innstillingane)

    # ---------- hellingsmålar i antenna ----------
    def feed(self, line):
        """Les ei NMEA-linje. Returnerer True om ho hadde helling."""
        if not line.startswith("$"):
            return False
        body = line[1:].split("*")[0]
        p = body.split(",")
        tag = p[0]
        roll = pitch = hdg = None
        if tag.endswith("HPR") and len(p) >= 5:  # $GNHPR,tid,kurs,stamp,krenging,...
            hdg, pitch, roll, src = _f(p[2]), _f(p[3]), _f(p[4]), tag
        elif tag == "PSAT" and len(p) >= 6 and p[1] == "HPR":  # $PSAT,HPR,tid,kurs,stamp,krenging,...
            hdg, pitch, roll, src = _f(p[3]), _f(p[4]), _f(p[5]), "PSAT,HPR"
        elif tag == "PASHR" and len(p) >= 6:  # $PASHR,tid,kurs,T,krenging,stamp,...
            hdg, roll, pitch, src = _f(p[2]), _f(p[4]), _f(p[5]), "PASHR"
        elif tag == "PTNL" and len(p) >= 8 and p[1] == "AVR":  # $PTNL,AVR,tid,kurs,Yaw,stamp,Tilt,krenging,Roll,...
            hdg, pitch, roll, src = _f(p[3]), _f(p[5]), _f(p[7]), "PTNL,AVR"
        else:
            return False
        if roll is None or pitch is None:
            return False
        self.ant = {"roll": roll, "pitch": pitch, "heading": hdg, "t": time.time(), "src": src}
        self.sentences.add(src)
        return True

    def antenna_ok(self):
        return self.ant is not None and time.time() - self.ant["t"] < ANT_FRESH

    # ---------- utrekning ----------
    def add_position(self, lat, lon, alt):
        if lat is not None and alt is not None:
            self.hist.append((time.time(), lat, lon, alt))

    def _track_slope(self, lat, lon, alt, heading):
        """Helling langs køyreretninga frå GNSS-høgda dei siste metrane (dz/ds), eller None."""
        if heading is None or len(self.hist) < 5:
            return None
        now = time.time()
        mx = 111320 * math.cos(math.radians(lat))
        for t, la, lo, al in reversed(self.hist):  # nyaste først: første punkt minst 4 m bak (kort vindauge = lite etterslep)
            if now - t > 15:
                break
            dE, dN = (lon - lo) * mx, (lat - la) * 111320
            s = dE * math.sin(math.radians(heading)) + dN * math.cos(math.radians(heading))  # køyrd lengd framover
            side = abs(dE * math.cos(math.radians(heading)) - dN * math.sin(math.radians(heading)))
            if s >= 4:
                return (alt - al) / s if s <= 10 and side < 0.25 * s else None  # berre på rett nok strekning
        return None

    @staticmethod
    def _terrain_grad(terr, lat, lon, d=2.0):
        """Terrenghelling (dz/dE, dz/dN) frå terrengmodellen, eller None."""
        if terr is None:
            return None
        dlat, dlon = d / 111320, d / (111320 * math.cos(math.radians(lat)))
        try:
            e1, e0 = terr.height(lat, lon + dlon), terr.height(lat, lon - dlon)
            n1, n0 = terr.height(lat + dlat, lon), terr.height(lat - dlat, lon)
        except Exception:
            return None
        if not (e1 and e0 and n1 and n0):
            return None
        return (e1["h"] - e0["h"]) / (2 * d), (n1["h"] - n0["h"]) / (2 * d)

    def gradient(self, lat, lon, alt, heading, speed, terr, cfg):
        """Helling på snøflata der maskina står som (gE, gN) = dz/dE, dz/dN, og info til skjerm og logg.
        Returnerer (None, info) når det ikkje skal korrigerast."""
        mode = cfg.get("tiltMode") or "auto"
        info = {"mode": mode, "src": "av"}
        if mode == "av" or lat is None:
            return None, info
        g = None
        if mode == "auto" and self.antenna_ok():
            a = self.ant
            hdg = a["heading"] if a["heading"] is not None else heading
            if hdg is not None:
                pitch = -a["pitch"] if cfg.get("tiltFlipPitch") else a["pitch"]
                roll = -a["roll"] if cfg.get("tiltFlipRoll") else a["roll"]
                along, right = math.tan(math.radians(pitch)), -math.tan(math.radians(roll))  # høgre side ned → fell mot høgre
                h = math.radians(hdg)
                g = (along * math.sin(h) + right * math.cos(h), along * math.cos(h) - right * math.sin(h))
                info.update(src="antenne", sentence=a["src"])
        if g is None:
            tg = self._terrain_grad(terr, lat, lon)
            ts = self._track_slope(lat, lon, alt, heading) if (speed or 0) > 0.8 else None
            if tg is None and ts is None:
                return None, dict(info, src="ingen")
            g = tg or (0.0, 0.0)
            if ts is not None:  # byt ut komponenten langs køyreretninga med den målte frå GNSS
                h = math.radians(heading)
                f = (math.sin(h), math.cos(h))
                cur = g[0] * f[0] + g[1] * f[1]
                g = (g[0] + (ts - cur) * f[0], g[1] + (ts - cur) * f[1])
            info["src"] = "utrekna" + (" (GNSS + terreng)" if ts is not None and tg else " (GNSS)" if ts is not None else " (terreng)")
        mag = math.hypot(*g)
        if mag > MAX_SLOPE:
            g = (g[0] * MAX_SLOPE / mag, g[1] * MAX_SLOPE / mag)
        tot = math.degrees(math.atan(math.hypot(*g)))
        if heading is not None:
            h = math.radians(heading)
            along = g[0] * math.sin(h) + g[1] * math.cos(h)
            right = g[0] * math.cos(h) - g[1] * math.sin(h)
            info.update(pitch=round(math.degrees(math.atan(along)), 1), roll=round(-math.degrees(math.atan(right)), 1))
        info["total"] = round(tot, 1)
        return g, info


def correct(lat, lon, g, antZ):
    """Punktet der maskina står (under midten) og høgda frå antenna ned til snøflata, gitt hellinga g.
    Antenna A = C + h·n, n = (−gE, −gN, 1)/√(1+|g|²)  ⇒  C = A + h·g/√(…), høgd ned = h/√(…)."""
    k = 1 / math.sqrt(1 + g[0] ** 2 + g[1] ** 2)
    dE, dN = antZ * g[0] * k, antZ * g[1] * k
    return lat + dN / 111320, lon + dE / (111320 * math.cos(math.radians(lat))), antZ * k, math.hypot(dE, dN)
