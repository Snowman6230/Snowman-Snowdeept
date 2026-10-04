#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Leica-simulator for testing utan mottakar (berre Linux/macOS).

Lagar ein virtuell seriellport og sender NMEA GGA med RTK FIX, 5 Hz.
Maskina står i ro 8 s, køyrer så lanar på 120 m med 5 m mellomrom i 2,2 m/s (ca. 8 km/t).
Ein kort RTK FLOAT-periode kjem etter 40–46 s.

Med --terreng blir høgda rekna frå testterrenget (testterreng.py) + fasit-snødjupne + antennehøgd,
slik at SNOWMAN si utrekna snødjupne kan kontrollerast mot fasit.

Bruk: python3 simuler-leica.py [fil-for-portnamn] [--terreng] [--antenne 2.8]
"""
import argparse, os, pty, time, math, random
from terrain import utm_forward

ap = argparse.ArgumentParser()
ap.add_argument("portfil", nargs="?")
ap.add_argument("--terreng", action="store_true", help="høgd frå testterreng + fasit-snø")
ap.add_argument("--antenne", type=float, default=2.8, help="antennehøgd over snøoverflata (m)")
a = ap.parse_args()
if a.terreng:
    from testterreng import terrain_h, snow_truth

m, s = pty.openpty(); port = os.ttyname(s)
if a.portfil: open(a.portfil, "w").write(port)
print("Virtuell Leica på", port, "(høgd frå testterreng + fasit-snø)" if a.terreng else "", flush=True)


def cs(x):
    c = 0
    for ch in x: c ^= ord(ch)
    return "%02X" % c


def dm(val, deg):
    dd = int(val); return f"{dd:0{deg}d}{(val-dd)*60:010.7f}"


lat0, lon0 = 62.3905, 6.5810
mlat = 111320; mlon = 111320 * math.cos(math.radians(lat0))
L, W, v, hz = 120, 5.0, 2.2, 5
t0 = time.time()
while True:
    t = time.time() - t0; d = max(0, t - 8) * v
    lane = int(d // (L + W)); r = d % (L + W)
    if r < L: y = r if lane % 2 == 0 else L - r; x = lane * W
    else: y = L if lane % 2 == 0 else 0; x = lane * W + (r - L)
    y += random.gauss(0, 0.01); x += random.gauss(0, 0.01)
    lat = lat0 + y / mlat; lon = lon0 + x / mlon
    q = 5 if 40 < t < 46 else 4
    if a.terreng:
        E, N = utm_forward(lat, lon, 32)
        alt = terrain_h(E, N) + snow_truth(E, N) + a.antenne + random.gauss(0, 0.008)  # RTK-støy ca. 1 cm
    else:
        alt = 905.31 + 0.01 * math.sin(t)
    body = f"GNGGA,{time.strftime('%H%M%S')}.00,{dm(lat,2)},N,{dm(lon,3)},E,{q},19,0.6,{alt:.3f},M,40.0,M,1.0,0001"
    os.write(m, f"${body}*{cs(body)}\r\n".encode()); time.sleep(1 / hz)
