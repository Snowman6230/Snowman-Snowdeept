# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Lokal AI i SNOWMAN (prototype): preparéringsråd som køyrer på PC-en i maskina, utan nett og utan skyteneste.

Dette er ikkje ein språkmodell. Det er ein lokal, lærande modell som kombinerer det SNOWMAN veit om akkurat dette
området – terrengmodellen, RTK-målingane, trasear og anleggsobjekt, vêret frå næraste stasjonar og varselet – og
lærer av det over tid. Alt blir tilpassa automatisk etter GPS-posisjonen:
  * Områdeprofil: blir laga automatisk første gong SNOWMAN er på ein ny stad (meir enn 5 km frå førre), med høgder
    frå terrengmodellen og stasjonar valde etter GPS. Profilen lærer vindrosa og nattetemperaturane på staden.
  * Snøkartet sin kalibrering (nedbørsfaktor) og læring (kvar det kjem meir/mindre snø) er lagra per stad i faste
    UTM-ruter – dei gjeld berre der dei er lærte.
Dei fem råda:
  1 Tidspunkt å preparere – beste start per trasé før opning, ut frå nedbør, vind og temperatur i varselet
  2 Snøflytting med skjeret – frå område med overskot til område med underskot (same trasé, inntil 120 m, oppover maks 40 m)
  3 Hol i spora – uprepart areal inne i traseane dette prepareringsdøgnet
  4 Kvalitetsscore per trasé – dekning, snødjupne mot mål, jamnleik og hol
  5 Snøproduksjon – område med mindre snø enn måldjupna (etter venta nysnø), volum, næraste hydrant/kanon og
    produksjonsvindauge for høgda der
Alt er FORSLAG og ESTIMAT. Føraren og driftsleiaren avgjer. Data: data/ai-profil.json (ikkje i git).
"""
import json, math, time
from collections import deque
from pathlib import Path

import numpy as np

SITE_KM = 5.0                 # ny områdeprofil når SNOWMAN er lenger enn dette frå næraste kjende
PREP_SPEED, PREP_WIDTH, PREP_EFF = 2.5, 5.5, 0.6     # m/s, m, del av tida med effektiv preparering (til tidsbruk)
MOVE_MAX = 120.0              # m – lengste snøflytting med skjer som blir foreslått
MOVE_UP = 40.0                # m – lengste flytting oppover (å skyve snø opp er tungt)
SNOW_WATER = 0.45             # m³ vatn per m³ produsert (pakka) snø – grovt
GUN_RATE = 25.0               # m³ snø per time per kanon ved gode forhold – grovt, kan endrast (aiGunRate)
HIM = ["nord", "nordaust", "aust", "søraust", "sør", "sørvest", "vest", "nordvest"]


def him(d):
    return HIM[int(round((d % 360) / 45)) % 8]


def km(a, b, c, d):
    p = math.pi / 180
    h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


# ------------------------------------------------------------------ områdeprofil (lærer staden)
class Profiles:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.d = json.loads(self.path.read_text("utf-8"))
        except Exception:
            self.d = {"sites": {}}

    def save(self):
        try:
            tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.d, ensure_ascii=False, indent=1), "utf-8"); tmp.replace(self.path)
        except Exception:
            pass

    def site(self, lat, lon, zmin=None, zmax=None, stations=None, test=False):
        """Områdeprofilen for staden – blir laga automatisk om SNOWMAN er på ein ny stad."""
        best = None
        for sid, s in self.d["sites"].items():
            if bool(s.get("test")) != bool(test):
                continue
            k = km(lat, lon, s["lat"], s["lon"])
            if k <= SITE_KM and (best is None or k < best[0]):
                best = (k, sid)
        if best:
            s = self.d["sites"][best[1]]
        else:
            sid = time.strftime("%Y%m%d%H%M%S")
            s = self.d["sites"][sid] = {"id": sid, "lat": round(lat, 5), "lon": round(lon, 5), "test": bool(test),
                                        "name": f"Område {lat:.3f} N {lon:.3f} Ø".replace(".", ","), "created": int(time.time()),
                                        "rose": [0.0] * 16, "windH": 0, "nightT": 0.0, "nightN": 0, "hours": 0, "precip": 0.0, "lastHour": 0}
        if zmin is not None:
            s["zmin"], s["zmax"] = round(zmin), round(zmax)
        if stations:
            s["stations"] = stations
        return s

    def learn(self, s, hours):
        """Lær vêret på staden: vindrose (timar over 3 m/s, vekta med vindstyrken), nattetemperatur (kl. 22–06), nedbør."""
        new = [h for h in hours if h["t"] / 1000 > s.get("lastHour", 0)]
        for h in new:
            u, d = h.get("wind") or 0.0, h.get("dir")
            if d is not None and u > 3:
                s["rose"][int(round((d % 360) / 22.5)) % 16] += u
                s["windH"] += 1
            if time.localtime(h["t"] / 1000).tm_hour in (22, 23, 0, 1, 2, 3, 4, 5):
                s["nightT"] += h["temp"]; s["nightN"] += 1
            s["precip"] += h.get("precip") or 0.0
            s["hours"] += 1
        if new:
            s["lastHour"] = max(h["t"] for h in new) / 1000
            self.save()
        return len(new)

    @staticmethod
    def summary(s):
        r = {"name": s["name"], "days": round(s["hours"] / 24, 1), "zmin": s.get("zmin"), "zmax": s.get("zmax"), "stations": s.get("stations")}
        if s["windH"] >= 6:
            i = int(np.argmax(s["rose"]))
            r["windFrom"] = him(i * 22.5)
            r["leeFacing"] = him(i * 22.5)       # vinden kjem frå … → fokksnø i heng som vender bort frå vinden
            r["leeText"] = f"mest vind frå {him(i * 22.5)} – fokksnø samlar seg typisk i heng som vender mot {him(i * 22.5 + 180)}"
        if s["nightN"]:
            r["nightT"] = round(s["nightT"] / s["nightN"], 1)
        return r


# ------------------------------------------------------------------ læringslogg og nye funn
class Journal:
    """Lokal læringslogg for AI-en (data/ai-laering.jsonl, test for seg). Ingenting blir sendt nokon stad.

    Hendingar: «deficit» (område under måldjupna, 40 m-ruter), «holes» (hol i spora, 20 m-ruter), «cal» (treffsikkerheit
    mot RTK), «feedback» (føraren: nyttig / ikkje nyttig per råd) og «voice» (talekommando: forstått eller ikkje).
    Rutene er faste UTM-ruter, så det same området blir kjent att natt etter natt. Av dette lagar `findings` «nye funn»:
    ting som går igjen, ting modellen bommar på, og forslag til korleis SNOWMAN kan bli betre.
    Seinare kan loggen (anonymisert) sendast til ein sentral SNOWMAN-AI – berre om anlegget slår det på."""

    def __init__(self, path):
        self.path = Path(path)
        self.ev = []
        try:
            for line in self.path.read_text("utf-8").splitlines():
                if line.strip():
                    self.ev.append(json.loads(line))
        except Exception:
            pass

    def add(self, kind, data, day=None, unique=False):
        """Legg til ei hending. unique: berre éi av slaget per prepareringsdøgn (siste vinn ikkje – første blir ståande)."""
        if unique and any(e["kind"] == kind and e.get("day") == day for e in self.ev):
            return False
        e = {"t": int(time.time()), "kind": kind, "day": day, **data}
        self.ev.append(e)
        self.ev = self.ev[-20000:]
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return True

    def stats(self):
        k = {}
        for e in self.ev:
            k[e["kind"]] = k.get(e["kind"], 0) + 1
        days = {e.get("day") for e in self.ev if e.get("day")}
        return {"events": len(self.ev), "kinds": k, "days": len(days)}


def findings(ev, now=None):
    """Nye funn frå læringsloggen: kva som går igjen, kva modellen bommar på, og forslag til vidareutvikling."""
    out = []
    # hol som går igjen same stad
    seen = {}
    for e in ev:
        if e["kind"] == "holes":
            for c in e.get("cells", []):
                seen.setdefault((e.get("trase"), c), set()).add(e.get("day"))
    rep = {}
    for (tr, c), days in seen.items():
        if len(days) >= 2:
            rep.setdefault(tr, []).append(len(days))
    for tr, ns in rep.items():
        out.append({"cat": "drift", "level": "warn", "title": f"Hol går igjen i {tr}",
                    "text": f"{len(ns)} stad(er) har hatt hol i fleire netter (inntil {max(ns)}). Sjå over køyremønsteret der – "
                            "kanskje svingar, kantar eller hindringar gjer at spora ikkje møtest."})
    # fast underskot same stad
    dseen = {}
    for e in ev:
        if e["kind"] == "deficit":
            for c in e.get("cells", []):
                dseen.setdefault(c, set()).add(e.get("day"))
    fast = [c for c, d in dseen.items() if len(d) >= 3]
    if fast:
        out.append({"cat": "drift", "level": "warn", "title": "Fast underskot av snø",
                    "text": f"{len(fast)} område (40 × 40 m) har vore under måldjupna i minst 3 døgn. "
                            "Vurder fast produksjon der (kanon/lanse), snøgjerde, eller lågare måldjupne."})
    # modellen bommar systematisk
    cal = [e for e in ev if e["kind"] == "cal" and e.get("n", 0) >= 30][-6:]
    if len(cal) >= 3:
        b = [e["bias"] for e in cal]
        if all(x > 1 for x in b) or all(x < -1 for x in b):
            out.append({"cat": "modell", "level": "info", "title": "Snømodellen bommar same vegen",
                        "text": f"Dei siste {len(b)} samanlikningane med RTK viser {'meir' if b[0] > 0 else 'mindre'} snø enn venta "
                                f"(snitt {(sum(b) / len(b)):+.1f} cm)".replace(".", ",") + f". Nedbørsfaktoren blir justert automatisk; held det fram, bør "
                                "høgdejusteringa av nedbøren kalibrerast for anlegget."})
    # tilbakemelding frå føraren
    fb = {}
    for e in ev:
        if e["kind"] == "feedback":
            f = fb.setdefault(e.get("sec"), [0, 0])
            f[0 if e.get("val") > 0 else 1] += 1
    NAMES = {"p1": "Tidspunkt", "p2": "Snøflytting", "p3": "Hol i spora", "p4": "Kvalitet", "p5": "Snøproduksjon", "f": "Nye funn"}
    for sec, (up, down) in fb.items():
        if down >= 3 and down > up:
            out.append({"cat": "utvikling", "level": "info", "title": f"Rådet «{NAMES.get(sec, sec)}» bør forbetrast",
                        "text": f"Førarane har sagt «ikkje nyttig» {down} gonger (nyttig {up}). Dette er eit forslag til vidareutvikling."})
        elif up >= 3 and up > 2 * down:
            out.append({"cat": "utvikling", "level": "ok", "title": f"Rådet «{NAMES.get(sec, sec)}» er nyttig",
                        "text": f"{up} × nyttig, {down} × ikkje nyttig."})
    # tale som ikkje vart forstått → nye kommandoar
    miss = [e.get("text", "") for e in ev if e["kind"] == "voice" and not e.get("ok")]
    if len(miss) >= 3:
        ex = ", ".join(f"«{m[:40]}»" for m in miss[-3:])
        out.append({"cat": "utvikling", "level": "info", "title": "Nye talekommandoar trengst",
                    "text": f"{len(miss)} spørsmål vart ikkje forstått, t.d. {ex}. Dette viser kva førarane vil spørje om."})
    if not out:
        out.append({"cat": "info", "level": "ok", "title": "Ingen nye funn endå",
                    "text": "AI-en treng nokre netter med preparering og RTK-målingar før mønster kan kjennast att."})
    return out


# ------------------------------------------------------------------ hjelparar
def label(mask):
    """Samanhengande område (4-naboar). Returnerer (etikett-rutenett, tal område)."""
    H, W = mask.shape
    lab = np.zeros((H, W), dtype=np.int32)
    n = 0
    idx = np.flatnonzero(mask)
    flat = lab.reshape(-1)
    m = mask.reshape(-1)
    for i in idx:
        if flat[i]:
            continue
        n += 1
        flat[i] = n
        q = deque([i])
        while q:
            j = q.popleft()
            r, c = divmod(j, W)
            for k, ok in ((j - W, r > 0), (j + W, r < H - 1), (j - 1, c > 0), (j + 1, c < W - 1)):
                if ok and m[k] and not flat[k]:
                    flat[k] = n
                    q.append(k)
    return lab, n


def _hours_until(h, ts):
    return (ts - h["t"]) / 3600000.0


# ------------------------------------------------------------------ 1 tidspunkt
def hour_scores(fc):
    """Kor godt kvar time i varselet er til å preparere (0–100) og kvifor."""
    out = []
    for i, h in enumerate(fc):
        p = h.get("precip") if h.get("precip") is not None else (h.get("precip6") or 0) / 6
        u, T = h.get("wind") or 0, h["temp"]
        s, why = 60.0, []
        if p >= 0.3:
            s -= 35; why.append("nedbør")
        elif p >= 0.1:
            s -= 15; why.append("litt nedbør")
        if u > 10:
            s -= 30; why.append("sterk vind (snøen fyk)")
        elif u > 7:
            s -= 15; why.append("frisk vind")
        if T > 1:
            s -= 20; why.append("våt snø")
        elif -12 < T < -2:
            s += 10
        elif T <= -15:
            s -= 10; why.append("svært kaldt (sprø snø)")
        nxt = fc[i + 1:i + 4]
        if nxt and min(x["temp"] for x in nxt) < min(T, -1) - 1.5:
            s += 15; why.append("+kuldegrader etter preparering gir fast underlag")
        prev = fc[max(0, i - 3):i]
        pp = sum((x.get("precip") or 0) for x in prev)
        pn = sum((x.get("precip") or 0) for x in nxt)
        if pp > 0.5 and pn < 0.2:
            s += 15; why.append("+snøfallet er over")
        if pn > 1.0 and p < 0.3:
            s -= 15; why.append("meir snø kjem straks")
        out.append({"t": h["t"], "score": int(max(0, min(100, s))), "why": why})
    return out


def timing(fc, trasear, now_ms, open_hour=10, opening_ms=None):
    """Beste starttid per trasé: preparering ferdig før opning, høgast snittscore i timane ho tek.
    opening_ms: neste opning frå opningstidene (opningstid.py); elles open_hour same dag/neste dag."""
    sc = hour_scores(fc)
    if opening_ms:
        op = opening_ms
    else:
        lt = time.localtime(now_ms / 1000)
        op = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, int(open_hour), 0, 0, 0, 0, -1)) * 1000
        if op <= now_ms + 3600000:
            op += 86400000
    res = []
    for t in trasear:
        dur = max(0.5, (t.get("area") or 10000) / (PREP_SPEED * PREP_WIDTH * PREP_EFF) / 3600.0)
        n = max(1, int(math.ceil(dur)))
        best = None
        for i in range(len(sc)):
            end = sc[i]["t"] + dur * 3600000
            if sc[i]["t"] < now_ms - 3600000 or end > op:
                continue
            seg = sc[i:i + n]
            if len(seg) < n:
                break
            m = sum(x["score"] for x in seg) / n
            if best is None or m > best[0] + 2:      # tidlegast av like gode
                best = (m, i)
        since = (now_ms - t["last"]) / 3600000.0 if t.get("last") else None
        need = "høg" if (since is None or since > 30) else "middels" if since > 16 or (t.get("pct", 100) < 50) else "låg"
        r = {"id": t["id"], "name": t["name"], "hours": round(dur, 1), "need": need, "since": round(since, 1) if since is not None else None,
             "opening": int(op)}
        if best:
            i = best[1]
            seg = sc[i:i + n]
            whys = []
            for x in seg:
                for w in x["why"]:
                    if w not in whys:
                        whys.append(w)
            r.update(start=sc[i]["t"], end=int(sc[i]["t"] + dur * 3600000), score=int(best[0]),
                     good=[w[1:] for w in whys if w.startswith("+")], bad=[w for w in whys if not w.startswith("+")])
        else:
            r["note"] = "Rekk ikkje å bli ferdig før opning – start så snart som mogleg."
        res.append(r)
    order = {"høg": 0, "middels": 1, "låg": 2}
    res.sort(key=lambda r: (order[r["need"]], r.get("start") or 0))
    return {"scores": [{"t": x["t"], "s": x["score"]} for x in sc[:30]], "opening": int(op), "trasear": res}


# ------------------------------------------------------------------ 2 snøflytting, 5 produksjon
def deficit_surplus(total, target, tol):
    """Underskot og overskot (m) mot måldjupna – berre der det finst både estimert djupne og mål."""
    ok = np.isfinite(total) & np.isfinite(target)
    d = np.where(ok, target - tol - total / 100.0, np.nan)        # > 0 = for lite
    s = np.where(ok, total / 100.0 - target - tol, np.nan)        # > 0 = for mykje
    return d, s


def clusters(mask, amount, step, Z, min_m2=40.0, tile_m=None):
    """Samanhengande område. tile_m: del store område i rutar (t.d. 80 m), så føraren får handterlege bitar."""
    lab, n = label(mask)
    if tile_m and n:
        H, W = mask.shape
        k = max(1, int(round(tile_m / step)))
        rr, cc = np.mgrid[0:H, 0:W]
        tile = (rr // k) * (W // k + 1) + (cc // k)
        comb = np.where(lab > 0, lab.astype(np.int64) * 1_000_000 + tile, 0)
        u, inv = np.unique(comb, return_inverse=True)
        lab = inv.reshape(H, W).astype(np.int32)
        if u[0] != 0:
            lab += 1
        n = int(lab.max())
    out = []
    a = step * step
    for k in range(1, n + 1):
        m = lab == k
        cnt = int(m.sum())
        if cnt * a < min_m2:
            continue
        rr, cc = np.nonzero(m)
        v = float(np.nansum(amount[m])) * a
        out.append({"k": k, "cells": cnt, "area": round(cnt * a), "vol": round(v), "mean": round(float(np.nanmean(amount[m])) * 100),
                    "max": round(float(np.nanmax(amount[m])) * 100), "r": float(rr.mean()), "c": float(cc.mean()),
                    "z": round(float(np.nanmean(Z[m])))})
    return lab, out


def snow_moves(defc, surc, step, tras_id_def, tras_id_sur):
    """Par overskot → underskot i same trasé innan MOVE_MAX, helst nedover (lettare å skyve)."""
    moves = []
    left = {s["k"]: s["vol"] for s in surc}
    for d in sorted(defc, key=lambda x: -x["vol"]):
        need = d["vol"]
        cand = []
        for s in surc:
            if tras_id_sur.get(s["k"]) != tras_id_def.get(d["k"]) or left[s["k"]] <= 5:
                continue
            dist = math.hypot((s["r"] - d["r"]) * step, (s["c"] - d["c"]) * step)
            if dist > MOVE_MAX or (s["z"] < d["z"] - 1 and dist > MOVE_UP):
                continue
            cand.append((dist - 0.5 * (s["z"] - d["z"]), dist, s))
        for _, dist, s in sorted(cand, key=lambda x: x[0]):
            if need <= 5:
                break
            v = min(need, left[s["k"]])
            left[s["k"]] -= v
            need -= v
            moves.append({"from": s, "to": d, "vol": round(v), "dist": round(dist), "dz": round(s["z"] - d["z"])})
    moves = [m for m in moves if m["vol"] >= 20]       # små flyttingar er ikkje verdt turen
    moves.sort(key=lambda m: -m["vol"])
    return moves


# ------------------------------------------------------------------ 3 hol, 4 kvalitet
def holes(bits, W, H, cell, pct, min_m2=8.0):
    """Uprepart areal inne i ein trasé (bitmap frå trasear.status, rad 0 = sør). Hol = avgrensa flekkar."""
    m = np.unpackbits(np.frombuffer(bits, dtype=np.uint8))[:W * H].reshape(H, W).astype(bool)
    if pct < 50:
        return [], m
    lab, n = label(m)
    a = cell * cell
    tot = m.size * a
    out = []
    for k in range(1, n + 1):
        mm = lab == k
        ar = float(mm.sum()) * a
        if ar < min_m2 or ar > 0.25 * tot:
            continue
        rr, cc = np.nonzero(mm)
        ln = max(np.ptp(rr) + 1, np.ptp(cc) + 1) * cell
        if ar / ln < 2.5:          # smale stripar langs kanten av traseen er ikkje hol i spora
            continue
        out.append({"area": round(ar), "x": float((cc.mean() + 0.5) * cell), "y": float((rr.mean() + 0.5) * cell),
                    "len": round(max(np.ptp(rr) + 1, np.ptp(cc) + 1) * cell)})
    out.sort(key=lambda h: -h["area"])
    return out[:12], m


def quality(pct, nholes, tot_in, target, tol):
    """0–100: dekning 40 %, djupne innan mål 30 %, jamnleik 15 %, hol 15 % (vekta om når djupne manglar)."""
    parts = {"dekning": max(0.0, min(100.0, pct))}
    v = tot_in[np.isfinite(tot_in)] / 100.0 if tot_in is not None else np.array([])
    if v.size >= 20 and target is not None:
        parts["djupne"] = 100.0 * float(np.mean(v >= target - tol))
        parts["jamnleik"] = max(0.0, 100.0 - 2.0 * float(np.std(v)) * 100.0)
    parts["hol"] = max(0.0, 100.0 - 15.0 * nholes)
    w = {"dekning": 0.4, "djupne": 0.3, "jamnleik": 0.15, "hol": 0.15}
    ws = sum(w[k] for k in parts)
    score = sum(parts[k] * w[k] for k in parts) / ws
    worst = min(parts, key=parts.get)
    tips = {"dekning": "ikkje heile traseen er preparert", "djupne": "for lite snø i delar av traseen",
            "jamnleik": "ujamn snødjupne", "hol": "hol i spora"}
    return {"score": int(round(score)), "parts": {k: int(round(x)) for k, x in parts.items()},
            "grade": "god" if score >= 85 else "brukbar" if score >= 70 else "svak", "issue": tips[worst] if parts[worst] < 85 else None}


# ------------------------------------------------------------------ produksjonsvindauge i høgda
def windows_at(fc, dz, lim, wetbulb, classify, windows):
    """Produksjonsvindauge for ei høgd dz meter over varselet (−0,65 °C/100 m)."""
    hs = []
    for h in fc[:48]:
        T = h["temp"] - 0.0065 * dz
        tw = wetbulb(T, h.get("rh") or 90.0)
        hs.append(dict(h, temp=T, tw=tw, cls=classify(tw, h.get("wind"), lim)))
    return windows([h for h in hs if h.get("precip") is not None])


if __name__ == "__main__":     # sjølvtest: python3 ai.py
    # tidspunkt: snø til kl. +3, så kaldt og roleg → beste start etter snøfallet
    t0 = (time.time() // 3600 + 1) * 3600 * 1000
    fc = [{"t": t0 + i * 3600000, "temp": -3.0 - (0.5 * i if i > 3 else 0), "rh": 85, "wind": 9 if i < 3 else 3, "dir": 270,
           "precip": 1.0 if i < 3 else 0.0} for i in range(30)]
    tm = timing(fc, [{"id": "a", "name": "Test", "area": 30000, "last": None, "pct": 0}], t0, open_hour=time.localtime(t0 / 1000 + 14 * 3600).tm_hour)
    r = tm["trasear"][0]
    print("tidspunkt: start", time.strftime("%H:%M", time.localtime(r["start"] / 1000)), "score", r["score"], r["good"], r["bad"])
    assert r["start"] >= t0 + 3 * 3600000, "skal starte etter snøfallet"
    # snøflytting: overskot oppe til venstre, underskot 60 m unna
    n, step = 60, 2.0
    Z = np.tile(np.linspace(900, 880, n), (n, 1)).astype(float)
    tot = np.full((n, n), 80.0); tot[10:20, 5:15] = 120; tot[10:20, 35:45] = 50
    d, s_ = deficit_surplus(tot, np.full((n, n), 0.8), 0.1)
    _, dc = clusters(np.nan_to_num(d) > 0.05, d, step, Z)
    _, sc = clusters(np.nan_to_num(s_) > 0.05, s_, step, Z)
    mv = snow_moves(dc, sc, step, {c["k"]: 0 for c in dc}, {c["k"]: 0 for c in sc})
    print("snøflytting:", [(m["vol"], m["dist"], m["dz"]) for m in mv])
    assert mv and mv[0]["dist"] == 60 and mv[0]["dz"] > 0
    # hol: trasé 40 × 40 m, preparert utanom eit hol på 6 × 6 m
    W = H = 40
    unprep = np.zeros((H, W), bool); unprep[10:16, 20:26] = True
    hs, _ = holes(np.packbits(unprep).tobytes(), W, H, 1.0, 97.0)
    print("hol:", hs)
    assert len(hs) == 1 and hs[0]["area"] == 36
    q = quality(97.0, 1, np.full(200, 85.0), 0.8, 0.1)
    print("kvalitet:", q)
    assert q["score"] > 80
    print("OK")
