# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Vêr og snøproduksjon (prototype): varsel frå MET Norway og utrekning av våttemperatur og produksjonsvindauge.

Kjelde: MET Norway Locationforecast 2.0 (api.met.no), fritt til bruk med kjeldeangiving («Data frå MET Norway»).
MET sine vilkår blir følgde: programmet sender ein eigen User-Agent, koordinatane har maks 4 desimalar,
svaret blir lagra og ikkje henta på nytt før «Expires», og If-Modified-Since blir brukt ved ny henting.

Offline først: siste varsel blir lagra i data/ver-cache.json. Utan nett blir det lagra varselet vist med alder.
Demo: oppdikta vêrdata (demo=True) er alltid merkte «DEMO» og blir aldri lagra som ekte varsel.

Våttemperatur (Tw) etter Stull (2011), gyldig for RH 5–99 % og T −20…50 °C (godt nok til snøproduksjon).
Grensene er standard  godt ≤ −5 °C,  marginalt ≤ −2 °C,  maks vind 12 m/s – kan stillast inn i førarskjermen.
"""
from pathlib import Path
import calendar, json, math, threading, time, urllib.request, urllib.error
from email.utils import parsedate_to_datetime

URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
ATTR = "Data frå MET Norway (CC BY 4.0)"
LAPSE = 0.0065          # °C per meter – berre brukt i demo (MET justerer sjølv for høgda vi sender)
DEFAULT_LIMITS = {"good": -5.0, "marg": -2.0, "wind": 12.0}
ICON_DIR = Path(__file__).resolve().parent / "vendor" / "vaersymbol"   # MET weathericons (MIT), sjå LES-MEG.txt der
ICON_ATTR = "Vêrsymbol: MET Norway / Yr (MIT-lisens)"


def _legend():
    """symbol_code (utan _day/_night/_polartwilight) → nynorsk tekst, frå legend.csv i weathericons."""
    try:
        rows = (ICON_DIR / "legend.csv").read_text("utf-8").splitlines()[1:]
        return {r.split(",")[0]: r.split(",")[3] for r in rows if r.count(",") >= 5}
    except Exception:
        return {}


LEGEND = _legend()


def sym_text(code):
    return LEGEND.get((code or "").split("_")[0], "") if code else ""


def wetbulb(t, rh):
    """Våttemperatur (°C) frå lufttemperatur t (°C) og relativ fukt rh (%) – Stull 2011."""
    rh = max(5.0, min(99.0, rh))
    return (t * math.atan(0.151977 * math.sqrt(rh + 8.313659)) + math.atan(t + rh) - math.atan(rh - 1.676331)
            + 0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh) - 4.686035)


def classify(tw, wind, lim):
    if tw <= lim["marg"] and wind is not None and wind > lim["wind"]:
        return "vind"          # kaldt nok, men for mykje vind (avdrift, ujamn snø)
    if tw <= lim["good"]:
        return "godt"
    if tw <= lim["marg"]:
        return "marg"
    return "nei"


def windows(hours, min_h=2):
    """Samanhengande timar der produksjon er mogleg (godt eller marginalt)."""
    out, cur = [], []
    for h in hours + [None]:
        if h and h["cls"] in ("godt", "marg"):
            cur.append(h)
            continue
        if len(cur) >= min_h:
            g = sum(1 for x in cur if x["cls"] == "godt")
            tws = [x["tw"] for x in cur]
            out.append({"start": cur[0]["t"], "end": cur[-1]["t"] + 3600000, "hours": len(cur), "good": g,
                        "quality": "godt" if g * 2 >= len(cur) else "marg",
                        "twMin": round(min(tws), 1), "twMean": round(sum(tws) / len(tws), 1)})
        cur = []
    return out


def _parse_met(js):
    hours = []
    for e in js.get("properties", {}).get("timeseries", []):
        d = e.get("data", {})
        i = d.get("instant", {}).get("details", {})
        n1 = d.get("next_1_hours") or {}
        n6 = d.get("next_6_hours") or {}
        if "air_temperature" not in i:
            continue
        t = calendar.timegm(time.strptime(e["time"], "%Y-%m-%dT%H:%M:%SZ")) * 1000
        pr = (n1.get("details") or {}).get("precipitation_amount")
        hours.append({"t": t, "temp": i.get("air_temperature"), "rh": i.get("relative_humidity", 90.0),
                      "wind": i.get("wind_speed"), "dir": i.get("wind_from_direction"),
                      "cloud": i.get("cloud_area_fraction"), "precip": pr,
                      "precip6": None if pr is not None else (n6.get("details") or {}).get("precipitation_amount"),
                      "sym": (n1.get("summary") or n6.get("summary") or {}).get("symbol_code")})
    return hours


def demo_hours(alt, now=None, k0=0, n=72):
    """Oppdikta varsel for demo og skjermbilete: kalde netter, mildare dagar, snøbyer med vestaversvind.
    k0 < 0 gir timar bakover i tid (demo-historikk til snøkartet)."""
    now = now or time.time()
    t0 = int(now // 3600 * 3600)
    out = []
    for k in range(k0, k0 + n):
        t = t0 + k * 3600
        lh = time.localtime(t).tm_hour
        temp = -1.2 + 3.6 * math.cos(2 * math.pi * (lh - 15) / 24) - 2.2 * math.sin(k / 20.0) - max(-300, min(300, alt - 700)) * LAPSE
        rh = 82 + 10 * math.sin(k / 9.0) + (8 if 30 <= k <= 40 else 0)
        wind = 4 + 3 * math.sin(k / 7.0) + (12 if 33 <= k <= 38 else 0) + (7 * math.sin((k - 3) / 14 * math.pi) if 3 <= k <= 17 else 0)
        pr = round(max(0.0, 1.6 * math.sin((k - 30) / 10 * math.pi)), 1) if 30 <= k <= 40 else 0.0
        if 4 <= k <= 16:      # snøbye med vestaversvind dei første timane (gir noko å sjå i snøkartet)
            pr = round(1.2 * math.sin((k - 3) / 14 * math.pi), 1)
            temp -= 1.5
        if -40 <= k <= -26:   # snøbye i går (demo-historikk)
            pr = round(1.4 * math.sin((k + 41) / 16 * math.pi), 1)
            wind += 6 * math.sin((k + 41) / 16 * math.pi)
            temp -= 2.0
        out.append({"t": t * 1000, "temp": round(temp, 1), "rh": round(min(99, rh), 0), "wind": round(wind, 1),
                    "dir": round(215 + 70 * math.sin(k / 12.0)) % 360, "cloud": 80 if pr else 30, "precip": pr, "precip6": None,
                    "sym": _demo_sym(pr, temp, 7 <= lh < 18, k)})
    return out


def _demo_sym(pr, temp, day, k):
    v = "_day" if day else "_night"
    if pr:
        if temp < 0.5:
            return "heavysnow" if pr > 1.2 else ("snow" if pr > 0.6 else "lightsnow")
        return "sleet" if temp < 1.5 else "rain"
    return ("clearsky", "fair", "partlycloudy", "cloudy")[(k // 7) % 4] + ("" if (k // 7) % 4 == 3 else v)


class Weather:
    def __init__(self, cache_path, version="1.6"):
        self.path = cache_path
        self.ua = f"SNOWMAN/{version} (Alpindata snoproduksjon; https://github.com/Snowman6230)"
        self.lock = threading.Lock()
        try:
            self.cache = json.loads(cache_path.read_text("utf-8"))
        except Exception:
            self.cache = {}

    def _key(self, lat, lon, alt):
        return f"{lat:.4f},{lon:.4f},{int(round(alt or 0))}"

    def _fetch(self, lat, lon, alt):
        """Hentar frå MET berre når lagra varsel har gått ut. Returnerer (hours, meta) eller kastar feil."""
        key = self._key(lat, lon, alt)
        with self.lock:
            c = self.cache.get(key)
        if c and time.time() < c.get("expires", 0):
            return c
        q = f"lat={lat:.4f}&lon={lon:.4f}" + (f"&altitude={int(round(alt))}" if alt is not None else "")
        req = urllib.request.Request(URL + "?" + q, headers={"User-Agent": self.ua, "Accept-Encoding": "identity"})
        if c and c.get("lastMod"):
            req.add_header("If-Modified-Since", c["lastMod"])
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                js = json.loads(r.read().decode("utf-8"))
                exp, lm = r.headers.get("Expires"), r.headers.get("Last-Modified")
            c = {"hours": _parse_met(js), "fetched": time.time(), "lastMod": lm,
                 "expires": parsedate_to_datetime(exp).timestamp() if exp else time.time() + 1800,
                 "updated": js.get("properties", {}).get("meta", {}).get("updated_at")}
        except urllib.error.HTTPError as e:
            if e.code == 304 and c:         # ikkje endra – bruk det lagra og vent til neste Expires
                exp = e.headers.get("Expires")
                c["expires"] = parsedate_to_datetime(exp).timestamp() if exp else time.time() + 1800
                c["fetched"] = time.time()
            else:
                raise
        with self.lock:
            self.cache = {key: c}            # berre éin stad lagra (maskina er på eitt anlegg om gongen)
            try:
                tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.cache), "utf-8"); tmp.replace(self.path)
            except Exception:
                pass
        return c

    def forecast(self, lat, lon, alt, limits=None, demo=False, now=None):
        lim = dict(DEFAULT_LIMITS)
        lim.update({k: float(v) for k, v in (limits or {}).items() if k in lim and v is not None})
        now = now or time.time()
        res = {"ok": True, "demo": bool(demo), "lat": round(lat, 4), "lon": round(lon, 4),
               "alt": None if alt is None else round(alt), "limits": lim, "attr": ATTR, "source": "MET Norway Locationforecast 2.0"}
        if demo:
            hours, res["age_min"], res["offline"] = demo_hours(alt or 600, now), 0, False
            res["source"] = "DEMO – oppdikta vêrdata"
        else:
            err = None
            try:
                c = self._fetch(lat, lon, alt)
            except Exception as e:
                import nett
                err, why = str(e), nett.explain(e)
                with self.lock:
                    c = next(iter(self.cache.values()), None)   # offline: siste lagra varsel (kan vere for ein annan stad)
            if not c:
                return {"ok": False, "offline": True, "error": "Ingen vêrdata endå – SNOWMAN får ikkje kontakt med api.met.no. " + why,
                        "detail": err, "attr": ATTR, "nett": True}
            hours = c["hours"]
            res["offline"] = err is not None
            res["age_min"] = round((now - c.get("fetched", now)) / 60)
            res["updated"] = c.get("updated")
            if err:
                res["error"] = err
                res["why"] = why
        cut = (now - 3600) * 1000
        hours = [h for h in hours if h["t"] >= cut][:96]
        for h in hours:
            h["tw"] = round(wetbulb(h["temp"], h["rh"] if h["rh"] is not None else 90.0), 1)
            h["cls"] = classify(h["tw"], h["wind"], lim)
            h["symText"] = sym_text(h.get("sym"))
        res["hours"] = hours
        res["now"] = hours[0] if hours else None
        hourly = [h for h in hours if h["precip"] is not None]
        res["windows"] = windows(hourly)
        days = {}
        for h in hours:
            d = time.strftime("%Y-%m-%d", time.localtime(h["t"] / 1000))
            x = days.setdefault(d, {"date": d, "good": 0, "marg": 0, "tmin": 99, "tmax": -99, "twmin": 99, "precip": 0.0, "n": 0})
            x["n"] += 1
            x["good"] += h["cls"] == "godt"
            x["marg"] += h["cls"] == "marg"
            x["tmin"], x["tmax"] = min(x["tmin"], h["temp"]), max(x["tmax"], h["temp"])
            x["twmin"] = min(x["twmin"], h["tw"])
            x["precip"] = round(x["precip"] + (h["precip"] or h["precip6"] or 0), 1)
        for d in days.values():   # symbol for dagen: timen nærast kl. 12
            hs = [h for h in hours if time.strftime("%Y-%m-%d", time.localtime(h["t"] / 1000)) == d["date"] and h.get("sym")]
            if hs:
                m = min(hs, key=lambda h: abs(time.localtime(h["t"] / 1000).tm_hour - 12))
                d["sym"], d["symText"] = m["sym"], m["symText"]
        res["days"] = list(days.values())[:7]
        res["iconAttr"] = ICON_ATTR
        return res


if __name__ == "__main__":       # rask sjølvtest: python3 ver.py
    assert abs(wetbulb(20, 50) - 13.7) < 0.2, wetbulb(20, 50)
    assert abs(wetbulb(-2, 60) - (-4.6)) < 0.6, wetbulb(-2, 60)
    from pathlib import Path
    import tempfile
    W = Weather(Path(tempfile.mkdtemp()) / "c.json")
    r = W.forecast(62.3905, 6.5810, 640, demo=True)
    print("Tw no:", r["now"]["tw"], r["now"]["cls"], "| vindauge:", len(r["windows"]), "| dagar:", len(r["days"]))
    print("OK")
