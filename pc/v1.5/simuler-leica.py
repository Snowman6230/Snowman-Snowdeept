#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Leica-simulator for testing utan mottakar (berre Linux/macOS).
Lagar ein virtuell seriellport og sender NMEA GGA med RTK FIX, 5 Hz.
Maskina står i ro 8 s, køyrer så lanar på 120 m med 5 m mellomrom i 2,2 m/s (ca. 8 km/t).
Ein kort RTK FLOAT-periode kjem etter 40–46 s.
Bruk: python3 simuler-leica.py [fil-for-portnamn]"""
import os, pty, time, math, sys, random
m, s = pty.openpty(); port = os.ttyname(s)
if len(sys.argv) > 1: open(sys.argv[1], "w").write(port)
print("Virtuell Leica på", port, flush=True)
def cs(x):
    c = 0
    for ch in x: c ^= ord(ch)
    return '%02X' % c
lat0, lon0 = 62.3905, 6.5810
mlat = 111320; mlon = 111320 * math.cos(math.radians(lat0))
L, W, v, hz = 120, 5.0, 2.2, 5
t0 = time.time()
def dm(val, deg):
    dd = int(val); return f"{dd:0{deg}d}{(val-dd)*60:010.7f}"
while True:
    t = time.time() - t0; d = max(0, t - 8) * v
    lane = int(d // (L + W)); r = d % (L + W)
    if r < L: y = r if lane % 2 == 0 else L - r; x = lane * W
    else: y = L if lane % 2 == 0 else 0; x = lane * W + (r - L)
    y += random.gauss(0, 0.01); x += random.gauss(0, 0.01)
    lat = lat0 + y / mlat; lon = lon0 + x / mlon
    q = 5 if 40 < t < 46 else 4
    body = f"GNGGA,{time.strftime('%H%M%S')}.00,{dm(lat,2)},N,{dm(lon,3)},E,{q},19,0.6,{905.31+0.01*math.sin(t):.3f},M,40.0,M,1.0,0001"
    os.write(m, f"${body}*{cs(body)}\r\n".encode()); time.sleep(1 / hz)
