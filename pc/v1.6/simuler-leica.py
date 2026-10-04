#!/usr/bin/env python3
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Leica-simulator for testing utan mottakar (berre Linux/macOS).

Lagar ein virtuell seriellport og sender NMEA GGA med RTK FIX, 5 Hz.
Maskina står i ro 8 s, køyrer så lanar på 120 m med 5 m mellomrom i 2,2 m/s (ca. 8 km/t).
Ein kort RTK FLOAT-periode kjem etter 40–46 s.

Med --terreng blir høgda rekna frå testterrenget (testterreng.py) + fasit-snødjupne + antennehøgd,
slik at SNOWMAN si utrekna snødjupne kan kontrollerast mot fasit.

Med --anlegg køyrer maskina over det øvste aktive terrenglaget i terrengbiblioteket (t.d. ein Topocad-modell
frå Fjellsætra). Lanane følgjer lengderetninga til modellen. Høgda er ekte terreng + simulert snø + antennehøgd.
Når du legg inn, slår av/på eller endrar prioritet på eit lag, flyttar maskina seg dit innan nokre sekund.
Snøen er SIMULERT – berre for å teste korleis SNOWMAN brukar terrengmodellen.

Bruk: python3 simuler-leica.py [fil-for-portnamn] [--terreng | --anlegg] [--antenne 2.8]
"""
import argparse, os, pty, time, math, random
from pathlib import Path
from terrain import utm_forward, utm_inverse

ap = argparse.ArgumentParser()
ap.add_argument("portfil", nargs="?")
ap.add_argument("--terreng", action="store_true", help="høgd frå testterreng + fasit-snø")
ap.add_argument("--anlegg", action="store_true", help="køyr over øvste aktive lag i terrengbiblioteket, med simulert snø")
ap.add_argument("--antenne", type=float, default=2.8, help="antennehøgd over snøoverflata (m)")
a = ap.parse_args()
if a.terreng:
    from testterreng import terrain_h, snow_truth

m, s = pty.openpty(); port = os.ttyname(s)
if a.portfil: open(a.portfil, "w").write(port)
print("Virtuell Leica på", port,
      "(høgd frå testterreng + fasit-snø)" if a.terreng else "(over terrengbiblioteket, simulert snø)" if a.anlegg else "",
      flush=True)


def cs(x):
    c = 0
    for ch in x: c ^= ord(ch)
    return "%02X" % c


def dm(val, deg):
    dd = int(val); return f"{dd:0{deg}d}{(val-dd)*60:010.7f}"


def sim_snow(s_, t_):
    """Simulert snødjupne (m) langs (s_) og på tvers (t_) av køyreretninga. Jamn variasjon og eit tynt felt."""
    d = 0.8 + 0.4 * math.sin(s_ / 23.0) * math.sin(t_ / 17.0)
    if 40 < s_ < 60 and 10 < t_ < 25:
        d = 0.25
    return max(0.05, d)


class Anlegg:
    """Les terrengbiblioteket (data/terrain) og planlegg lanar over det øvste aktive barmarkslaget."""
    def __init__(self):
        self.root = Path(__file__).resolve().parent / "data" / "terrain"
        self.sig = None; self.lib = None; self.route = None

    def _signature(self):
        try:
            return tuple(sorted((p.parent.name, p.stat().st_mtime_ns) for p in self.root.glob("*/meta.json")))
        except Exception:
            return ()

    def refresh(self):
        sig = self._signature()
        if sig == self.sig:
            return False
        first = self.sig is None; self.sig = sig
        import terrain as T
        self.lib = T.TerrainLibrary(self.root)
        layers = [l for l in self.lib.listing() if l["active"] and l["type"] == "barmark"]
        old = self.route["id"] if self.route else None
        self.route = self._plan(layers[0]) if layers else None
        new = self.route["id"] if self.route else None
        if new != old or first:
            print("Simulator:", f"køyrer over «{self.route['name']}»" if self.route else "ingen aktive terrenglag – står ved Fjellsætra", flush=True)
            return True
        return False

    def _plan(self, l):
        import numpy as np
        g = self.lib._grid(l["id"])
        step = max(1, int(max(l["nx"], l["ny"]) / 400))           # tynn ut store rutenett
        sub = np.asarray(g[::step, ::step])
        r, c = np.nonzero(np.isfinite(sub))
        if len(r) < 10:
            return None
        E = l["x0"] + (c * step + 0.5) * l["dx"]; N = l["y0"] - (r * step + 0.5) * l["dy"]
        # midtpunkt: den gyldige ruta nærast tyngdepunktet (eit bøygd trasé kan ha tyngdepunktet utanfor)
        i0 = int(np.argmin((E - E.mean()) ** 2 + (N - N.mean()) ** 2)); ce, cn = E[i0], N[i0]
        L = 100.0
        for rad in (L * 0.7, L * 0.7):                           # to rundar: retning og senter lokalt rundt midtpunktet
            k = (E - ce) ** 2 + (N - cn) ** 2 < rad ** 2
            w, v = np.linalg.eigh(np.cov(np.vstack([E[k] - E[k].mean(), N[k] - N[k].mean()])))
            u = v[:, 1]                                          # lengderetning (største spreiing)
            p = np.array([-u[1], u[0]])                          # på tvers
            su = (E - ce) * u[0] + (N - cn) * u[1]; sp = (E - ce) * p[0] + (N - cn) * p[1]
            k = (np.abs(su) < L / 2) & (np.abs(sp) < 80)
            ce, cn = ce + p[0] * np.median(sp[k]), cn + p[1] * np.median(sp[k])
        su = (E - ce) * u[0] + (N - cn) * u[1]; sp = (E - ce) * p[0] + (N - cn) * p[1]
        k = (np.abs(su) < L / 2) & (np.abs(sp) < 80)
        lo_p, hi_p = np.percentile(sp[k], [10, 90])              # lanane held seg innanfor den sentrale delen
        L = float(min(L, max(30.0, np.ptp(su[k]))))
        n = int(max(2, min(14, (hi_p - lo_p) / 5.0)))
        mp = (lo_p + hi_p) / 2
        start = np.array([ce, cn]) - u * (L / 2) + p * (mp - (n - 1) * 5.0 / 2)
        return {"id": l["id"], "name": l["name"], "zone": l["zone"], "u": u, "p": p, "start": start, "L": L, "n": n}

    def pos(self, d):
        """Posisjon (lat, lon, s, t) etter d meter køyring i lanar fram og tilbake."""
        R = self.route; L, W, n = R["L"], 5.0, R["n"]
        d = d % (2 * n * (L + W))
        li = int(d // (L + W)); rr = d % (L + W)                  # li: lane nr. i runden (fram og tilbake)
        lane = li if li < n else 2 * n - 1 - li
        side = 1 if li < n - 1 else (-1 if n <= li < 2 * n - 1 else 0)   # kva veg maskina snur
        if rr < L: s_ = rr if li % 2 == 0 else L - rr; t_ = lane * W
        else: s_ = L if li % 2 == 0 else 0; t_ = lane * W + side * min(rr - L, W)
        e, nn = R["start"] + R["u"] * s_ + R["p"] * t_
        lat, lon = utm_inverse(e, nn, R["zone"])
        return lat, lon, s_, t_

    def height(self, lat, lon):
        h = self.lib.height(lat, lon) if self.lib else None
        return h["h"] if h else None


lat0, lon0 = 62.3905, 6.5810
mlat = 111320; mlon = 111320 * math.cos(math.radians(lat0))
L, W, v, hz = 120, 5.0, 2.2, 5
AN = Anlegg() if a.anlegg else None
last_alt, last_chk = 350.0, 0
t0 = time.time()
while True:
    t = time.time() - t0; d = max(0, t - 8) * v
    q = 5 if 40 < t < 46 else 4
    if AN:
        if time.time() - last_chk > 3:
            last_chk = time.time()
            if AN.refresh():
                t0 = time.time() - 8; d = 0                     # nytt lag: start ny runde der
        if AN.route:
            lat, lon, s_, t_ = AN.pos(d)
            h = AN.height(lat, lon)
            if h is not None:
                last_alt = h + sim_snow(s_, t_) + a.antenne + random.gauss(0, 0.008)
            alt = last_alt                                       # utanfor modellen: SNOWMAN viser UTANFOR TERRENGMODELL
        else:
            lat, lon, alt = 62.3365, 6.7650, 350.0               # Fjellsætra, parkeringsplassen
    else:
        lane = int(d // (L + W)); r = d % (L + W)
        if r < L: y = r if lane % 2 == 0 else L - r; x = lane * W
        else: y = L if lane % 2 == 0 else 0; x = lane * W + (r - L)
        lat = lat0 + y / mlat; lon = lon0 + x / mlon
        if a.terreng:
            E, N = utm_forward(lat, lon, 32)
            alt = terrain_h(E, N) + snow_truth(E, N) + a.antenne + random.gauss(0, 0.008)  # RTK-støy ca. 1 cm
        else:
            alt = 905.31 + 0.01 * math.sin(t)
    lat += random.gauss(0, 0.01) / mlat; lon += random.gauss(0, 0.01) / mlon
    body = f"GNGGA,{time.strftime('%H%M%S')}.00,{dm(lat,2)},N,{dm(lon,3)},E,{q},19,0.6,{alt:.3f},M,40.0,M,1.0,0001"
    os.write(m, f"${body}*{cs(body)}\r\n".encode()); time.sleep(1 / hz)
