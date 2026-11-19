# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av IMU-helling frå Unicore UM981 (INSPVAXA) – v1.6.117.

Køyr frå pc/v1.6:  python3 test/testimu.py   → venta «ALT OK».
  1 CRC: eksempelet i Unicore-manualen godteke; éin endra byte forkasta.
  2 INS-status: INS_ALIGNING og INS_INACTIVE blir ikkje brukte (SNOWMAN reknar sjølv), INS_SOLUTION_GOOD blir brukt.
  3 IMU på (auto): kjelda er «IMU», og forteikna stemmer: fronten opp mot nord gir fall mot sør (gN > 0 betyr høgd
    aukar mot nord), høgre side ned gir fall mot høgre side.
  4 IMU av (estimat): IMU-en blir ikkje brukt, sjølv om han sender.
  5 Gammal måling (> 2 s) blir ikkje brukt.
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import helling as HL

EKS = ("#INSPVAXA,COM1,0,73.5,FINESTEERING,1695,309428.000,00000040,4e77,43562;INS_SOLUTION_GOOD,INS_PSRSP,"
       "51.11637873403,-114.03825114994,1063.6093,-16.9000,-0.0845,-0.0464,-0.0127,0.138023492,0.069459386,"
       "90.000923268,0.9428,0.6688,1.4746,0.0430,0.0518,0.0521,0.944295466,0.944567084,1.000131845,3,0*e877c178")


def lag(status, roll, pitch, az):
    body = (f"INSPVAXA,COM1,0,80.0,FINESTEERING,2394,300000.000,00000000,0000,1;{status},INS_RTKFIXED,"
            f"62.4,6.6,100.0,44.8,0,0,0,{roll},{pitch},{az},0.01,0.01,0.02,0.01,0.01,0.01,0.05,0.05,0.2,0,0")
    return "#" + body + "*%08x" % HL.crc32_novatel(body.encode())


class Terr:
    """Flatt terreng – utrekna helling blir 0, så alt anna enn 0 kjem frå IMU-en."""
    def height(self, lat, lon):
        return {"h": 100.0}


feil = []


def sjekk(namn, ok, info=""):
    print(("OK   " if ok else "FEIL ") + namn + (f" – {info}" if info else ""))
    if not ok:
        feil.append(namn)


# 1 CRC
h = HL.Helling()
sjekk("1a eksempel frå manualen (CRC) godteke", h.feed(EKS) and h.ant["src"] == "INSPVAXA")
h = HL.Helling()
sjekk("1b endra byte forkasta", not h.feed(EKS.replace("0.138023492", "0.138023493")) and h.ins_bad == 1)

# 2 INS-status
h = HL.Helling()
sjekk("2a INS_ALIGNING ikkje brukt", not h.feed(lag("INS_ALIGNING", 5, 5, 0)) and h.ant is None and h.ins == "INS_ALIGNING")
sjekk("2b INS_INACTIVE ikkje brukt", not h.feed(lag("INS_INACTIVE", 5, 5, 0)) and h.ant is None)
sjekk("2c INS_SOLUTION_GOOD brukt", h.feed(lag("INS_SOLUTION_GOOD", 0, 10, 0)) and h.ant["heading"] == 0)
h2 = HL.Helling()
h2.feed(lag("INS_HIGH_VARIANCE", 0, 10, 123))
sjekk("2d INS_HIGH_VARIANCE: helling brukt, kurs frå GNSS", h2.ant is not None and h2.ant["heading"] is None)

# 3 IMU på: forteikn
cfg = {"tiltMode": "auto"}
h = HL.Helling()
h.feed(lag("INS_SOLUTION_GOOD", 0, 10, 0))          # fronten 10° opp, køyrer mot nord
g, info = h.gradient(62.4, 6.6, 100, 0, 1.0, Terr(), cfg)
sjekk("3a kjelde IMU", info["src"] == "IMU" and info["sentence"] == "INSPVAXA", info)
sjekk("3b fronten opp mot nord → høgd aukar mot nord", g[1] > 0 and abs(g[0]) < 1e-9 and abs(info["pitch"] - 10) < 0.2, g)
h = HL.Helling()
h.feed(lag("INS_SOLUTION_GOOD", 8, 0, 90))          # høgre side 8° ned, køyrer mot aust (høgre = sør)
g, info = h.gradient(62.4, 6.6, 100, 90, 1.0, Terr(), cfg)
sjekk("3c høgre side ned mot aust → høgd aukar mot nord (venstre)", g[1] > 0 and abs(g[0]) < 1e-9 and abs(info["roll"] - 8) < 0.2, (g, info))

# 4 IMU av
g, info = h.gradient(62.4, 6.6, 100, 90, 1.0, Terr(), {"tiltMode": "estimat"})
sjekk("4 IMU av: utrekna, ikkje IMU", info["src"].startswith("utrekna") and abs(info["total"]) < 0.01, info)

# 5 gammal måling
h.ant["t"] = time.time() - 3
g, info = h.gradient(62.4, 6.6, 100, 90, 1.0, Terr(), cfg)
sjekk("5 gammal IMU-måling ikkje brukt", info["src"].startswith("utrekna"), info)

print("ALT OK" if not feil else f"FEIL: {feil}")
sys.exit(1 if feil else 0)
