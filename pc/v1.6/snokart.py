# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Snøkart – ESTIMAT av snøendring i terrengmodellen frå vêrvarselet (prototype, steg 1 og 2).

Byggjer alltid på DEN GJELDANDE TERRENGMODELLEN i SNOWMAN (aktive barmark-lag, høgast prioritet vinn – same som
resten av Vêr og snødjupnemålinga). Resultatet er eit ESTIMAT frå ein vêrmodell og skal aldri visast som måling.

Steg 1 – nysnø frå nedbør og høgd (kvar time i perioden, kvar rute):
  * temperatur i høgda: T = T0 − 0,65 °C/100 m · (z − z0)          (z0 = høgda varselet gjeld for)
  * nedbør i høgda:     P = P0 · (1 + 7 %/100 m · (z − z0)), avgrensa til 0,5–2 ×   (orografisk auke, må kalibrerast)
  * snødel frå våttemperatur (Stull): alt snø under −0,5 °C, alt regn over +1,5 °C, lineært imellom
  * tettleik på nysnø (Hedstrom & Pomeroy 1998): ρ = 67,9 + 51,3·e^(T/2,59) kg/m³ ved T ≤ 0, tyngre i vind
  * smelting av snøen frå perioden (og laus snø frå før): 0,15 mm vatn per °C og time over 0 °C
Steg 2 – vindflytting:
  * lé-tal Sx (Winstral m.fl. 2002) for kvar rute og vindretning: største vinkel opp mot terrenget i lo, inntil 100 m.
    Sx > 0 = skjerma (le), Sx < 0 = utsett (rygg / lo-side). Rekna ut éin gong per terrengutsnitt og 16 retningar.
    Erosjon og avsetjing brukar relativt lé-tal (Sx minus 70 % av snittet innan ca. 100 m), så det er ryggar, kantar
    og søkk som skil seg ut – ikkje heile lo-bakken.
  * vind i ruta: varselvinden justert med Sx (sterkare på utsette rygger, svakare i le)
  * snø blir flytt når vinden er over terskelen (5 m/s kald laus snø, 7 m/s nær 0 °C, 10 m/s over 0 °C);
    mengda aukar med (U − Ut)³ og kan ikkje vere meir enn den lause snøen som ligg der
  * snøen blir ført 40 m med vinden, spreidd, og lagd att i skjerma ruter. Massen blir halden (15 % fordampar),
    og fokksnø er tettare (250 kg/m³) enn nysnø.
Ikkje med enno (steg 3–5): setjing, smelting av eldre snø, totaldjupne, kalibrering mot RTK, snøproduksjon.
"""
import math, time
import numpy as np

LAPSE = 0.0065
ORO = 0.07            # nedbørauke per 100 m
RHO_DRIFT = 250.0     # kg/m³ fokksnø
RHO_OLD = 90.0        # kg/m³ laus snø frå før
SUBLIM = 0.15
SX_DMAX = 100.0
DRIFT_L = 40.0
NDIR = 16


def wetbulb_np(t, rh):
    rh = np.clip(rh, 5.0, 99.0)
    return (t * np.arctan(0.151977 * np.sqrt(rh + 8.313659)) + np.arctan(t + rh) - np.arctan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * np.arctan(0.023101 * rh) - 4.686035)


def _shift(a, dr, dc, fill=0.0):
    """Flytt rutenettet dr rader ned og dc kolonnar mot aust (heile ruter), fyll kanten."""
    out = np.full_like(a, fill)
    n, m = a.shape
    r0s, r1s = max(0, -dr), min(n, n - dr)
    c0s, c1s = max(0, -dc), min(m, m - dc)
    if r1s > r0s and c1s > c0s:
        out[r0s + dr:r1s + dr, c0s + dc:c1s + dc] = a[r0s:r1s, c0s:c1s]
    return out


def _box(a, k):
    """Glatting med boks på (2k+1)² ruter (summert areal), via kumulative summar."""
    if k <= 0:
        return a.copy()
    p = np.pad(a, k + 1, mode="constant")
    c = p.cumsum(0).cumsum(1)
    n, m = a.shape
    s = 2 * k + 1
    return c[s:s + n, s:s + m] - c[0:n, s:s + m] - c[s:s + n, 0:m] + c[0:n, 0:m]


def sx_field(H, step, dir_from):
    """Winstral sitt lé-tal (grader) for vind frå retninga dir_from (0 = nord, 90 = aust)."""
    th = math.radians(dir_from)
    ue, un = math.sin(th), math.cos(th)            # eining mot der vinden kjem frå (aust, nord)
    best = np.full(H.shape, -90.0, dtype=np.float32)
    ok = np.isfinite(H)
    Hf = np.where(ok, H, np.nan)
    d = step
    while d <= SX_DMAX + 1e-6:
        dc, dr = int(round(d * ue / step)), int(round(-d * un / step))   # rad 0 = nord
        if dc or dr:
            up = _shift(Hf, -dr, -dc, np.nan)        # høgda d meter i lo for kvar rute
            ang = np.degrees(np.arctan((up - Hf) / d))
            best = np.where(np.isfinite(ang), np.maximum(best, ang), best)
        d += step if d < 30 else 2 * step
    best[best <= -89.0] = 0.0
    best[~ok] = np.nan
    return best


def hillshade(H, step, az=315.0, alt=45.0):
    Hf = np.where(np.isfinite(H), H, np.nanmean(H))
    rel = float(np.nanmax(H) - np.nanmin(H)) if np.isfinite(H).any() else 0.0
    zf = 3.0 if rel < 150 else 2.0 if rel < 400 else 1.0      # overdriv relieffet i slakt terreng, så formene synest
    gy, gx = np.gradient(Hf * zf, step)                   # gy: endring nedover rader (sørover)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    a, z = math.radians(az), math.radians(90 - alt)
    hs = np.cos(z) * np.cos(slope) + np.sin(z) * np.sin(slope) * np.cos(a - aspect - math.pi / 2)
    lo, hi = np.percentile(hs, 2), np.percentile(hs, 98)
    hs = np.clip((hs - lo) / max(hi - lo, 1e-6), 0, 1)       # strekk kontrasten
    return (hs * 255).astype(np.uint8)


class SnowMap:
    def __init__(self):
        self.sx_cache = {}

    def _sx(self, key, H, step, d):
        b = int(round((d % 360) / (360 / NDIR))) % NDIR
        k = (key, b)
        if k not in self.sx_cache:
            if len(self.sx_cache) > 4 * NDIR:
                self.sx_cache.clear()
            sx = sx_field(H, step, b * 360 / NDIR)
            # relativt lé-tal: samanlikna med terrenget rundt (ca. 100 m), så ein jamn lo-bakke ikkje blir rekna som rygg
            ok = np.isfinite(sx)
            kk = max(1, int(round(100.0 / step)))
            mean = _box(np.where(ok, sx, 0.0), kk) / np.maximum(_box(ok.astype(np.float64), kk), 1)
            self.sx_cache[k] = (sx, np.where(ok, sx - 0.7 * mean, np.nan))
        return self.sx_cache[k]

    def run(self, P, hours, z0, loose_cm=0.0, key=None):
        """P = terrengutsnitt frå TerrainLibrary.patch (h, step, lat0, lon0, half). hours = timeliste frå ver.forecast."""
        t0 = time.time()
        H = np.asarray(P["h"], dtype=np.float32)
        step = float(P["step"])
        ok = np.isfinite(H)
        key = key or (P["lat0"], P["lon0"], P["half"], step)
        Z = np.where(ok, H, np.nanmean(H) if ok.any() else 0)
        dz = Z - z0
        Lswe = np.where(ok, loose_cm / 100.0 * RHO_OLD, 0.0)        # laus snø (kg/m² = mm vatn)
        Ldep = np.where(ok, float(loose_cm), 0.0)                   # djupna til den lause snøen (cm)
        dw = np.zeros_like(Z)          # endring med vind (cm)
        dn = np.zeros_like(Z)          # endring utan vind (cm)
        Ln_swe, Ln_dep = Lswe.copy(), Ldep.copy()
        tot = {"precip": 0.0, "snowmm": 0.0, "drifth": 0, "ve": 0.0, "vn": 0.0, "wsum": 0.0, "umax": 0.0, "tmin": 99, "tmax": -99}
        oro = np.clip(1 + ORO * dz / 100.0, 0.5, 2.0)
        kb = max(1, int(round(25.0 / step)))
        okf = ok.astype(np.float64)
        for h in hours:
            p0 = h.get("precip")
            if p0 is None:
                p0 = (h.get("precip6") or 0.0) / 6.0
            T = h["temp"] - LAPSE * dz
            Tw = wetbulb_np(T, np.full_like(T, h.get("rh") or 90.0))
            fs = np.clip((1.5 - Tw) / 2.0, 0, 1)
            U0 = float(h.get("wind") or 0.0)
            Psn = p0 * oro * fs
            rho = np.where(T <= 0, 67.92 + 51.25 * np.exp(np.minimum(T, 0) / 2.59), np.minimum(200.0, 119.0 + 20.0 * T))
            rho = np.minimum(rho + 12.0 * max(0.0, U0 - 3.0), 300.0)
            add = 100.0 * Psn / rho
            # nysnø (begge variantane)
            for Ls, Ld, d in ((Lswe, Ldep, dw), (Ln_swe, Ln_dep, dn)):
                Ls += Psn; Ld += add; d += add
            # smelting av snøen i perioden
            melt = np.where(T > 0, 0.15 * T + 0.0125 * p0 * (1 - fs) * T, 0.0)
            for Ls, Ld, d in ((Lswe, Ldep, dw), (Ln_swe, Ln_dep, dn)):
                m = np.minimum(melt, Ls)
                frac = np.where(Ls > 1e-6, m / np.maximum(Ls, 1e-6), 0.0)
                cut = Ld * frac
                Ls -= m; Ld -= cut; d -= cut
            # vindflytting (steg 2)
            dirf = h.get("dir")
            if dirf is not None and U0 > 3.0:
                Sx0, Sxr0 = self._sx(key, H, step, dirf)
                Sx, Sxr = np.nan_to_num(Sx0), np.nan_to_num(Sxr0)
                Uc = U0 * np.clip(1.0 - 0.35 * np.tanh(Sxr / 6.0), 0.6, 1.4)   # sterkare på ryggar, svakare i søkk
                Ut = np.where(T < -2, 5.0, np.where(T < 0, 7.0, 10.0))
                expo = np.clip(0.25 - Sxr / 5.0, 0, 1)
                e = 0.003 * np.maximum(0.0, Uc - Ut) ** 3 * expo
                R = np.where(ok, np.minimum(e, Lswe), 0.0)
                if R.sum() > 1e-6:
                    tot["drifth"] += 1
                    frac = np.where(Lswe > 1e-6, R / np.maximum(Lswe, 1e-6), 0.0)
                    cut = Ldep * frac
                    Lswe -= R; Ldep -= cut; dw -= cut
                    th = math.radians(dirf)
                    sh = int(round(DRIFT_L / step))
                    cnt = np.maximum(_box(okf, kb), 1.0)
                    Rm = _box(_shift(R, int(round(sh * math.cos(th))), int(round(-sh * math.sin(th)))), kb) / cnt   # medvinds snitt
                    w = np.where(ok, np.clip(0.3 + Sxr / 3.0, 0, 3.0), 0.0)
                    wm = _box(w, kb) / cnt
                    Dp = np.where(ok, Rm * np.minimum(w / np.maximum(wm, 0.05), 4.0), 0.0)   # avgrensa ved kantane
                    s = Dp.sum()
                    if s > 0:
                        Dp *= (1 - SUBLIM) * R.sum() / s
                        dw += 100.0 * Dp / RHO_DRIFT
            tot["precip"] += p0
            tot["snowmm"] += p0 * float(np.clip((1.5 - (h.get("tw") if h.get("tw") is not None else h["temp"])) / 2.0, 0, 1))
            if dirf is not None:
                tot["ve"] += U0 * math.sin(math.radians(dirf)); tot["vn"] += U0 * math.cos(math.radians(dirf)); tot["wsum"] += 1
            tot["umax"] = max(tot["umax"], U0)
            tot["tmin"], tot["tmax"] = min(tot["tmin"], h["temp"]), max(tot["tmax"], h["temp"])
        dw[~ok] = np.nan; dn[~ok] = np.nan
        eff = dw - dn
        v = dw[ok]
        vm = math.hypot(tot["ve"], tot["vn"]) / max(tot["wsum"], 1)
        st = {
            "hours": len(hours), "precip": round(tot["precip"], 1), "snowmm": round(tot["snowmm"], 1),
            "mean": round(float(np.mean(v)), 1) if v.size else None, "max": round(float(np.max(v)), 1) if v.size else None,
            "p10": round(float(np.percentile(v, 10)), 1) if v.size else None, "p90": round(float(np.percentile(v, 90)), 1) if v.size else None,
            "meanNo": round(float(np.nanmean(dn)), 1) if v.size else None,
            "blown": round(100.0 * float(np.mean(eff[ok] < -np.maximum(0.25 * dn[ok], 1.0))), 0) if v.size else None,
            "filled": round(100.0 * float(np.mean(eff[ok] > np.maximum(0.25 * dn[ok], 1.0))), 0) if v.size else None,
            "driftHours": tot["drifth"], "windDir": round(math.degrees(math.atan2(tot["ve"], tot["vn"])) % 360) if tot["wsum"] else None,
            "windMean": round(vm, 1), "windMax": round(tot["umax"], 1), "tmin": tot["tmin"], "tmax": tot["tmax"],
            "secs": round(time.time() - t0, 2),
        }
        return {"with": dw, "without": dn, "effect": eff, "stats": st}


if __name__ == "__main__":     # sjølvtest på ein kunstig rygg: vest-vind skal blåse reint på ryggen og fylle austsida
    n, step = 121, 4.0
    x = (np.arange(n) - 60) * step
    X, Y = np.meshgrid(x, -x)
    H = (700 + 40 * np.exp(-(X / 60.0) ** 2)).astype(np.float32)          # rygg nord–sør midt i
    P = {"h": H, "step": step, "lat0": 62.39, "lon0": 6.58, "half": 240}
    hrs = [{"temp": -6.0, "rh": 85, "wind": 12.0, "dir": 270, "precip": 1.0} for _ in range(12)]
    r = SnowMap().run(P, hrs, 700.0)
    w, n0 = r["with"], r["without"]
    ridge, lee, wind = w[60, 60], np.nanmean(w[60, 64:72]), np.nanmean(w[60, 40:52])
    print("utan vind (snitt) %.1f cm | rygg %.1f | le (aust) %.1f | lo (vest) %.1f | %s" % (np.nanmean(n0), ridge, lee, wind, r["stats"]))
    assert ridge < np.nanmean(n0) and lee > np.nanmean(n0), "vindflytting feil veg"
    print("OK")
