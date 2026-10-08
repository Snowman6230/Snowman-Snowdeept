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
RHO_DRIFT = 250.0     # kg/m³ fokksnø (brukt i dokumentasjonen; i modellen 200–400 etter vindstyrken)
RHO_OLD = 90.0        # kg/m³ laus snø frå før
RHO_SETTLED = 300.0   # kg/m³ – laus snø søkk saman mot dette
RHO_OLDPACK = 350.0   # kg/m³ – eldre snøpakke (smelting)
RHO_GROOMED = 450.0   # kg/m³ – snø under beltet / preparert (det maskina måler på)
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

    def run(self, P, hours, z0, loose_cm=0.0, key=None, pfac=1.0, stops=None, capture=None, spatial=None):
        """Køyr modellen time for time over `hours` (historikk + varsel).
        P = terrengutsnitt frå TerrainLibrary.patch. pfac = nedbørsfaktor frå kalibreringa.
        stops = timeindeksar der heile tilstanden blir teken vare på (0 = før første time, len(hours) = etter siste).
        capture = {namn: int-rutenett med timeindeks per rute (−1 = ingen)} – tilstanden i kvar rute ved den timen
        (t.d. når ruta sist vart målt). Tilstand = (endring med vind cm, endring utan vind cm, SWE-endring med vind mm)."""
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
        sw = np.zeros_like(Z)          # SWE-endring med vind (mm vatn) – til kalibreringa
        Ln_swe, Ln_dep = Lswe.copy(), Ldep.copy()
        oro = np.clip(1 + ORO * dz / 100.0, 0.5, 2.0) * pfac
        if spatial is not None:      # lært fordeling (kvar det pleier å kome meir eller mindre snø)
            oro = oro * np.where(np.isfinite(spatial), np.clip(spatial, 0.4, 2.5), 1.0)
        kb = max(1, int(round(25.0 / step)))
        okf = ok.astype(np.float64)
        stops = sorted(set(stops or [len(hours)]))
        snaps, caps = {}, {k: {"w": np.full_like(Z, np.nan), "n": np.full_like(Z, np.nan), "s": np.full_like(Z, np.nan)} for k in (capture or {})}
        drift_h = np.zeros(len(hours), dtype=bool)

        def keep(k):
            if k in stops:
                snaps[k] = {"w": dw.copy(), "n": dn.copy(), "s": sw.copy()}
            for name, idx in (capture or {}).items():
                m = idx == k
                if m.any():
                    caps[name]["w"][m] = dw[m]; caps[name]["n"][m] = dn[m]; caps[name]["s"][m] = sw[m]

        for k, h in enumerate(hours):
            keep(k)
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
            for Ls, Ld, d in ((Lswe, Ldep, dw), (Ln_swe, Ln_dep, dn)):
                Ls += Psn; Ld += add; d += add
            sw += Psn
            # steg 3: setjing – laus snø søkk saman (raskare nær 0 °C), til ca. 300 kg/m³
            kset = 0.010 * np.exp(0.08 * np.minimum(T, 0.0)) * (1.0 + 0.5 * (T > 0))
            for Ls, Ld, d in ((Lswe, Ldep, dw), (Ln_swe, Ln_dep, dn)):
                rl = np.where(Ld > 0.05, Ls / np.maximum(Ld, 0.05) * 100.0, 300.0)
                st_ = np.where(Ld > 0.05, Ld * kset * np.clip(1.0 - rl / RHO_SETTLED, 0, 1), 0.0)
                Ld -= st_; d -= st_
            # steg 3: smelting – først snøen i perioden, så eldre snø (graddøgn, regn gir ekstra varme)
            melt = np.where(T > 0, 0.15 * T + 0.0125 * p0 * (1 - fs) * T, 0.0)
            for i, (Ls, Ld, d) in enumerate(((Lswe, Ldep, dw), (Ln_swe, Ln_dep, dn))):
                m = np.minimum(melt, Ls)
                frac = np.where(Ls > 1e-6, m / np.maximum(Ls, 1e-6), 0.0)
                cut = Ld * frac
                Ls -= m; Ld -= cut; d -= cut
                d -= 100.0 * (melt - m) / RHO_OLDPACK       # eldre snø (ruter utan snø blir klipte i totaldjupna)
            sw -= melt
            # steg 2: vindflytting
            dirf = h.get("dir")
            if dirf is not None and U0 > 3.0:
                Sx0, Sxr0 = self._sx(key, H, step, dirf)
                Sxr = np.nan_to_num(Sxr0)
                Uc = U0 * np.clip(1.0 - 0.35 * np.tanh(Sxr / 6.0), 0.6, 1.4)   # sterkare på ryggar, svakare i søkk
                rl = np.where(Ldep > 0.05, Lswe / np.maximum(Ldep, 0.05) * 100.0, 300.0)
                Ut = np.where(T < -2, 5.0, np.where(T < 0, 7.0, 10.0)) + np.clip((rl - 120.0) / 30.0, 0, 6)   # eldre, tettare snø ligg betre
                expo = np.clip(0.25 - Sxr / 5.0, 0, 1)
                e = 0.003 * np.maximum(0.0, Uc - Ut) ** 3 * expo
                R = np.where(ok, np.minimum(e, Lswe), 0.0)
                if R.sum() > 1e-6:
                    drift_h[k] = True
                    frac = np.where(Lswe > 1e-6, R / np.maximum(Lswe, 1e-6), 0.0)
                    cut = Ldep * frac
                    Lswe -= R; Ldep -= cut; dw -= cut; sw -= R
                    th = math.radians(dirf)
                    sh = int(round(DRIFT_L / step))
                    cnt = np.maximum(_box(okf, kb), 1.0)
                    Rm = _box(_shift(R, int(round(sh * math.cos(th))), int(round(-sh * math.sin(th)))), kb) / cnt   # medvinds snitt
                    w = np.where(ok, np.clip(0.3 + Sxr / 3.0, 0, 3.0), 0.0)
                    wm = _box(w, kb) / cnt
                    Dp = np.where(ok, Rm * np.minimum(w / np.maximum(wm, 0.05), 4.0), 0.0)   # avgrensa ved kantane
                    s_ = Dp.sum()
                    if s_ > 0:
                        Dp *= (1 - SUBLIM) * R.sum() / s_
                        rho_d = min(400.0, max(200.0, 150.0 + 15.0 * U0))   # fokksnø blir pakka: tettare i sterkare vind
                        dw += 100.0 * Dp / rho_d
                        sw += Dp
        keep(len(hours))
        for d in list(snaps.values()) + list(caps.values()):
            for a in d.values():
                a[~ok] = np.nan
        return {"snaps": snaps, "caps": caps, "ok": ok, "driftHours": drift_h, "secs": round(time.time() - t0, 2)}


def hour_stats(hours, a, b, drift=None):
    """Vêret i timane [a, b): nedbør, snødel, vind (snittretning og -styrke), temperatur."""
    hs = hours[a:b]
    if not hs:
        return {"hours": 0}
    pr = [(h.get("precip") if h.get("precip") is not None else (h.get("precip6") or 0) / 6.0) for h in hs]
    sn = [p * min(1, max(0, (1.5 - (h.get("tw") if h.get("tw") is not None else h["temp"])) / 2.0)) for p, h in zip(pr, hs)]
    ve = sum((h.get("wind") or 0) * math.sin(math.radians(h["dir"])) for h in hs if h.get("dir") is not None)
    vn = sum((h.get("wind") or 0) * math.cos(math.radians(h["dir"])) for h in hs if h.get("dir") is not None)
    nw = sum(1 for h in hs if h.get("dir") is not None)
    return {"hours": len(hs), "precip": round(sum(pr), 1), "snowmm": round(sum(sn), 1),
            "windDir": round(math.degrees(math.atan2(ve, vn)) % 360) if nw else None, "windMean": round(math.hypot(ve, vn) / max(nw, 1), 1),
            "windMax": round(max((h.get("wind") or 0) for h in hs), 1), "tmin": min(h["temp"] for h in hs), "tmax": max(h["temp"] for h in hs),
            "driftHours": int(drift[a:b].sum()) if drift is not None else None}


def field_stats(w, n, ok):
    """Statistikk for eit endringsfelt (med vind w, utan vind n)."""
    m = ok & np.isfinite(w) & np.isfinite(n)
    if not m.any():
        return {}
    v, v0, eff = w[m], n[m], (w - n)[m]
    r1 = lambda x: round(float(x), 1)
    return {"mean": r1(np.mean(v)), "max": r1(np.max(v)), "p10": r1(np.percentile(v, 10)), "p90": r1(np.percentile(v, 90)),
            "meanNo": r1(np.mean(v0)),
            "blown": round(100.0 * float(np.mean(eff < -np.maximum(0.25 * np.abs(v0), 1.0)))),
            "filled": round(100.0 * float(np.mean(eff > np.maximum(0.25 * np.abs(v0), 1.0))))}


def calibration(pred_swe, meas_cm, mask):
    """Samanlikn modellen med RTK: endring i snøoverflata mellom to besøk i same rute.
    Maskina måler overflata under beltet (pakka snø), så modellen sin SWE-endring blir gjort om med RHO_GROOMED.
    Returnerer treffsikkerheit og forslag til nedbørsfaktor (krev minst 30 ruter med tydeleg venta endring)."""
    m = mask & np.isfinite(pred_swe) & np.isfinite(meas_cm)
    n = int(m.sum())
    if n < 10:
        return {"n": n}
    pred = 100.0 * pred_swe[m] / RHO_GROOMED
    meas = meas_cm[m]
    err = meas - pred
    r = {"n": n, "mae": round(float(np.mean(np.abs(err))), 1), "bias": round(float(np.mean(err)), 1),
         "pred": round(float(np.mean(pred)), 1), "meas": round(float(np.mean(meas)), 1)}
    sig = pred > 0.5
    if sig.sum() >= 30 and pred[sig].sum() > 0:
        r["factor"] = round(float(np.clip(meas[sig].sum() / pred[sig].sum(), 0.5, 2.0)), 2)
        r["nf"] = int(sig.sum())
    return r


LEARN_BIN = 10.0     # m – læringa blir lagra i faste 10 × 10 m UTM-ruter (uavhengig av kartutsnittet)
LEARN_MIN = 3        # hendingar før ei rute får lært faktor


class Learn:
    """Lærer kvar i terrenget det kjem meir eller mindre snø enn modellen ventar.

    Kvar gong ei rute er målt med RTK to gonger (to besøk), blir målt endring samanlikna med modellen. Summen per
    10 m-rute over sesongen gir ein faktor: (Σ målt + 5) / (Σ venta + 5). Fordelinga = faktor / median i området,
    så ho viser MØNSTERET (meir i søkk og le, mindre på ryggar), medan nivået blir teke av kalibreringa.
    Utelate: ruter innan 60 m frå snøkanon/hydrant (snøproduksjon), og hendingar som ser ut som produksjon eller
    skjerarbeid (målt meir enn 3 × venta + 8 cm, eller meir enn 10 cm under venta). Kvar hending blir rekna éin gong.
    Data: data/snokart-laering.json (test: snokart-laering-test.json) – høyrer til anlegget, ikkje i git."""

    def __init__(self, path):
        self.path = path
        try:
            import json
            self.d = json.loads(path.read_text("utf-8"))
        except Exception:
            self.d = {"bins": {}, "events": 0}

    def save(self):
        import json
        try:
            tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.d, separators=(",", ":")), "utf-8"); tmp.replace(self.path)
        except Exception:
            pass

    def bins_of(self, E, N, z):
        return np.floor(E / LEARN_BIN).astype(np.int64), np.floor(N / LEARN_BIN).astype(np.int64)

    def update(self, z, E, N, pred_cm, meas_cm, t_new, valid):
        """Legg til hendingar (éi per rute) som ikkje er rekna før. Returnerer (lagt til, avvist)."""
        m = valid & np.isfinite(pred_cm) & np.isfinite(meas_cm) & np.isfinite(t_new)
        bad = m & ((meas_cm > 3 * np.maximum(pred_cm, 0) + 8) | (meas_cm < pred_cm - 10))
        m &= ~bad
        be, bn = self.bins_of(E[m], N[m], z)
        agg = {}                                             # snitt av rutene i kvar 10 m-rute
        for e, n, p, ms, t in zip(be.tolist(), bn.tolist(), pred_cm[m].tolist(), meas_cm[m].tolist(), t_new[m].tolist()):
            a = agg.setdefault(f"{z},{e},{n}", [0.0, 0.0, 0, 0.0])
            a[0] += ms; a[1] += max(p, 0.0); a[2] += 1; a[3] = max(a[3], t)
        added = 0
        B = self.d["bins"]
        for k, a in agg.items():
            b = B.get(k)
            if b is None:
                b = B[k] = [0.0, 0.0, 0, 0.0]               # Σ målt, Σ venta, tal hendingar, tid for siste hending
            if a[3] <= b[3] + 3600:                          # same besøk er alt rekna
                continue
            b[0] += a[0] / a[2]; b[1] += a[1] / a[2]; b[2] += 1; b[3] = a[3]
            added += 1
        if added:
            self.d["events"] = self.d.get("events", 0) + added
            self.save()
        return added, int(bad.sum())

    def factor(self, z, E, N):
        """Lært fordeling for kvar rute (NaN der det ikkje er nok hendingar)."""
        be, bn = self.bins_of(E, N, z)
        B = self.d["bins"]
        f = np.full(E.shape, np.nan)
        for idx in np.ndindex(E.shape):
            b = B.get(f"{z},{be[idx]},{bn[idx]}")
            if b and b[2] >= LEARN_MIN:
                f[idx] = (b[0] + 5.0) / (b[1] + 5.0)
        v = f[np.isfinite(f)]
        if v.size:
            f = f / float(np.median(v))
        return f

    def stats(self):
        B = self.d["bins"]
        return {"bins": sum(1 for b in B.values() if b[2] >= LEARN_MIN), "started": len(B), "events": self.d.get("events", 0)}


if __name__ == "__main__":     # sjølvtest: vindflytting på ein kunstig rygg, setjing og smelting, kalibrering
    n, step = 121, 4.0
    x = (np.arange(n) - 60) * step
    X, Y = np.meshgrid(x, -x)
    H = (700 + 40 * np.exp(-(X / 60.0) ** 2)).astype(np.float32)          # rygg nord–sør midt i
    P = {"h": H, "step": step, "lat0": 62.39, "lon0": 6.58, "half": 240}
    hrs = [{"temp": -6.0, "rh": 85, "wind": 12.0, "dir": 270, "precip": 1.0} for _ in range(12)]
    SM = SnowMap()
    r = SM.run(P, hrs, 700.0)
    w, n0 = r["snaps"][12]["w"], r["snaps"][12]["n"]
    ridge, lee, wind = w[60, 60], np.nanmean(w[60, 64:72]), np.nanmean(w[60, 40:52])
    print("vind: utan vind %.1f cm | rygg %.1f | le (aust) %.1f | lo (vest) %.1f" % (np.nanmean(n0), ridge, lee, wind))
    assert ridge < np.nanmean(n0) and lee > np.nanmean(n0), "vindflytting feil veg"
    # setjing: 12 t snø, så 24 t roleg og kaldt – djupna skal minke, SWE skal stå
    calm = [{"temp": -4.0, "rh": 85, "wind": 1.0, "dir": 270, "precip": 1.0}] * 12 + [{"temp": -4.0, "rh": 85, "wind": 1.0, "dir": 270, "precip": 0.0}] * 24
    r2 = SM.run(P, calm, 700.0, stops=[12, 36])
    d12, d36 = np.nanmean(r2["snaps"][12]["n"]), np.nanmean(r2["snaps"][36]["n"])
    print("setjing: %.1f cm etter snøfall → %.1f cm etter 24 t (SWE %.1f → %.1f mm)" % (d12, d36, np.nanmean(r2["snaps"][12]["s"]), np.nanmean(r2["snaps"][36]["s"])))
    assert d36 < d12 * 0.95
    # smelting: mildvêr skal gi negativ endring (eldre snø smeltar)
    r3 = SM.run(P, [{"temp": 4.0, "rh": 90, "wind": 2.0, "dir": 200, "precip": 0.0}] * 24, 700.0)
    print("smelting: 24 t med +4 °C → %.1f cm" % np.nanmean(r3["snaps"][24]["n"]))
    assert np.nanmean(r3["snaps"][24]["n"]) < -1
    # kalibrering: «målt» endring 1,3 × modellen → faktor ca. 1,3
    cap = {"t": np.full(H.shape, 12), "p": np.zeros(H.shape, dtype=int)}
    r4 = SM.run(P, calm, 700.0, capture=cap)
    ps = r4["caps"]["t"]["s"] - r4["caps"]["p"]["s"]
    meas = 1.3 * 100 * ps / RHO_GROOMED
    c = calibration(ps, meas, np.isfinite(H))
    print("kalibrering:", c)
    assert abs(c["factor"] - 1.3) < 0.05
    # læring: målt dobbelt så mykje i aust som i vest over tre hendingar → fordeling > 1 i aust, < 1 i vest
    import tempfile
    from pathlib import Path
    Lr = Learn(Path(tempfile.mkdtemp()) / "l.json")
    E = 400000.0 + X; N = 6900000.0 + Y
    pred = np.full(H.shape, 3.0)
    for i in range(3):
        meas = np.where(X > 0, 4.0, 2.0)
        Lr.update(32, E, N, pred, meas, np.full(H.shape, 1e9 + i * 86400.0), np.ones(H.shape, dtype=bool))
    fl = Lr.factor(32, E, N)
    print("læring: aust %.2f, vest %.2f, %s" % (np.nanmean(fl[:, X[0] > 20]), np.nanmean(fl[:, X[0] < -20]), Lr.stats()))
    assert np.nanmean(fl[:, X[0] > 20]) > 1.1 and np.nanmean(fl[:, X[0] < -20]) < 0.9
    print("OK")
