# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Målingar frå næraste vêrstasjonar (MET Frost) til vêr-overlayet («MÅLT NO»).

Frost: https://frost.met.no – opne observasjonar frå MET og samarbeidspartnarar (m.a. vegvêrstasjonar).
Lisens for data: CC BY 4.0 («Data frå MET Norway»). Kvar førespurnad blir sendd med klient-ID som brukarnamn
(HTTP basic auth, tomt passord). Client secret trengst ikkje for opne data og blir ikkje brukt.

Klient-ID: SNOWMAN har ein innebygd ID (eigaren si avgjerd 2026-10-09: ID-en gir berre tilgang til opne data).
Eit anlegg kan bruke sin eigen ved å setje "frost_client_id" i snowman-config.local.json.

Stasjonsval: dei næraste stasjonane frå GPS-posisjonen (Frost «nearest»), eller ein fast liste ("frost_stations",
t.d. "SN60190,SN60225"). Berre stasjonar som faktisk har ferske målingar blir viste.
Offline først: stasjonslista blir lagra i 7 dagar og siste målingar i data/frost-cache.json og vist med alder.
"""
import base64, calendar, json, math, threading, time, urllib.error, urllib.parse, urllib.request

BASE = "https://frost.met.no"
CLIENT_ID = "ca39bc1b-eb35-4c23-acbd-1956b4a2d1cd"   # SNOWMAN (Alpindata) – berre opne data
LAPSE = 0.0065
ELEMENTS = ["air_temperature", "relative_humidity", "wind_speed", "wind_from_direction",
            "max(wind_speed_of_gust PT1H)", "sum(precipitation_amount PT1H)", "surface_snow_thickness"]
BASIC = ["air_temperature", "wind_speed", "sum(precipitation_amount PT1H)"]
KEYS = {"air_temperature": "temp", "relative_humidity": "rh", "wind_speed": "wind", "wind_from_direction": "dir",
        "max(wind_speed_of_gust PT1H)": "gust", "sum(precipitation_amount PT1H)": "precip", "surface_snow_thickness": "snow"}
OBS_TTL = 600        # sekund: nye målingar kjem typisk kvar 10. min – 1 t
SRC_TTL = 7 * 86400  # stasjonslista endrar seg sjeldan


def dist_km(a, b, c, d):
    p = math.pi / 180
    h = math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _iso(s):
    return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


class Frost:
    def __init__(self, cache_path, version="1.6", client_id=None):
        self.path = cache_path
        self.cid = client_id or CLIENT_ID
        self.ua = f"SNOWMAN/{version} (Alpindata snoproduksjon; https://github.com/Snowman6230)"
        self.lock = threading.Lock()
        try:
            self.cache = json.loads(cache_path.read_text("utf-8"))
        except Exception:
            self.cache = {}

    def _get(self, path, params):
        url = BASE + path + "?" + urllib.parse.urlencode(params, safe="(),: ")
        auth = base64.b64encode((self.cid + ":").encode()).decode()
        req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Authorization": "Basic " + auth})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))

    def _save(self):
        try:
            tmp = self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.cache), "utf-8"); tmp.replace(self.path)
        except Exception:
            pass

    def sources(self, lat, lon, fixed=None):
        """Stasjonar (id, namn, høgd, koordinatar, avstand), næraste først."""
        key = "fixed:" + fixed if fixed else f"near:{lat:.2f},{lon:.2f}"
        c = self.cache.get("src", {})
        if c.get("key") == key and time.time() - c.get("t", 0) < SRC_TTL:
            out = c["list"]
        else:
            p = {"types": "SensorSystem", "fields": "id,name,masl,geometry"}
            if fixed:
                p["ids"] = fixed
            else:
                p.update(geometry=f"nearest(POINT({lon:.4f} {lat:.4f}))", nearestmaxcount=8)
            js = self._get("/sources/v0.jsonld", p)
            out = []
            for s in js.get("data", []):
                co = (s.get("geometry") or {}).get("coordinates") or [None, None]
                nm = s.get("name") or s["id"]
                if nm.isupper():
                    nm = nm.title()          # Frost skriv namna med store bokstavar: «FV60 STRANDAFJELLET» → «Fv60 Strandafjellet»
                out.append({"id": s["id"], "name": nm, "masl": s.get("masl"), "lat": co[1], "lon": co[0]})
            with self.lock:
                self.cache["src"] = {"key": key, "t": time.time(), "list": out}
                self._save()
        for s in out:
            s["km"] = round(dist_km(lat, lon, s["lat"], s["lon"]), 1) if s["lat"] is not None else None
        return sorted(out, key=lambda s: s["km"] if s["km"] is not None else 999)

    def _latest(self, ids):
        c = self.cache.get("obs", {})
        if c.get("ids") == ids and time.time() - c.get("t", 0) < OBS_TTL:
            return c["data"], c["t"]
        data = None
        for els in (ELEMENTS, ELEMENTS[:-1], BASIC):     # nokre stasjonar/element finst ikkje – prøv då med færre element
            try:
                data = self._get("/observations/v0.jsonld", {"sources": ids, "referencetime": "latest", "maxage": "PT6H",
                                                            "elements": ",".join(els)}).get("data", [])
                break
            except urllib.error.HTTPError as e:
                if e.code in (404, 412):   # ingen data for nokon av stasjonane
                    data = []
                    break
                if e.code != 400 or els is BASIC:
                    raise
        with self.lock:
            self.cache["obs"] = {"ids": ids, "t": time.time(), "data": data}
            self._save()
        return data, time.time()

    def history(self, lat, lon, alt, hours=72, fixed=None, demo=False, now=None):
        """Vêret time for time dei siste `hours` timane (til snøkartet: nedbør og vind sidan sist målt).
        Returnerer {"ok", "hours": [...], "stations": {...}, "missing": {...}} – timane er omrekna til høgda alt."""
        now = now or time.time()
        end = int(now // 3600 * 3600)
        t0 = end - hours * 3600
        if demo:
            return {"ok": True, "demo": True, "hours": demo_history(alt, now, hours), "stations": {"alle": "DEMO"}, "missing": {}}
        key = f"{lat:.2f},{lon:.2f},{hours},{fixed}"
        c = self.cache.get("hist", {})
        series = None
        err = None
        if c.get("key") == key and time.time() - c.get("t", 0) < HIST_TTL:
            series, src = {k: {int(t): v for t, v in ser.items()} for k, ser in c["series"].items()}, c["src"]
        else:
            try:
                src = self.sources(lat, lon, fixed)[:4]
                rt = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)) + "/" + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end + 3600))
                data = self._get("/observations/v0.jsonld", {"sources": ",".join(x["id"] for x in src), "referencetime": rt,
                                                            "elements": ",".join(HIST_EL)}).get("data", [])
                series = {}
                for d in data:
                    sid = d.get("sourceId", "").split(":")[0]
                    t = _iso(d["referenceTime"]) if d.get("referenceTime") else None
                    if t is None:
                        continue
                    hb = int(t // 3600 * 3600)   # timen målinga høyrer til (siste verdi i timen vinn)
                    for o in d.get("observations", []):
                        k = KEYS.get(o.get("elementId"))
                        if k and o.get("value") is not None:
                            series.setdefault(sid, {}).setdefault(hb, {})[k] = o["value"]
                with self.lock:
                    self.cache["hist"] = {"key": key, "t": time.time(), "src": src,
                                          "series": {k: {str(t): v for t, v in ser.items()} for k, ser in series.items()}}
                    self._save()
            except Exception as e:
                err = str(e)
                if c.get("series"):        # offline: bruk siste lagra historikk
                    series, src = {k: {int(t): v for t, v in ser.items()} for k, ser in c["series"].items()}, c["src"]
        if series is None:
            return {"ok": False, "error": "Ingen vêrhistorikk frå Frost (" + (err or "ukjend feil") + ")", "hours": []}
        for s in src:
            s["km"] = round(dist_km(lat, lon, s["lat"], s["lon"]), 1) if s.get("lat") is not None else None
        out, used, miss = _compose(series, src, alt, t0, hours)
        r = {"ok": bool(out), "hours": out, "stations": used, "missing": miss, "offline": err is not None}
        if not out:
            r["error"] = "Stasjonane har ikkje temperatur for perioden."
        return r

    def observations(self, lat, lon, alt=None, fixed=None, demo=False, now=None):
        now = now or time.time()
        res = {"ok": True, "demo": bool(demo), "attr": "Data frå MET Norway (CC BY 4.0) · Frost", "stations": []}
        if demo:
            res["stations"] = demo_stations(alt, now)
            return res
        err = None
        try:
            src = self.sources(lat, lon, fixed)
            ids = ",".join(s["id"] for s in src[:8])
            data, t = self._latest(ids)
        except Exception as e:      # offline: siste lagra målingar
            err = str(e)
            src = self.cache.get("src", {}).get("list") or []
            for s in src:
                s["km"] = round(dist_km(lat, lon, s["lat"], s["lon"]), 1) if s.get("lat") is not None else None
            data, t = self.cache.get("obs", {}).get("data"), self.cache.get("obs", {}).get("t", now)
            if data is None:
                return {"ok": False, "offline": True, "error": "Ingen stasjonsmålingar endå – SNOWMAN får ikkje kontakt med frost.met.no.",
                        "detail": err, "stations": []}
        res["offline"], res["fetched_min"] = err is not None, round((now - t) / 60)
        by = {}
        for d in data or []:
            sid = d.get("sourceId", "").split(":")[0]
            rt = _iso(d["referenceTime"]) if d.get("referenceTime") else None
            for o in d.get("observations", []):
                k = KEYS.get(o.get("elementId"))
                if not k:
                    continue
                st = by.setdefault(sid, {"t": rt})
                if k not in st or (rt or 0) >= st.get("_t_" + k, 0):
                    st[k], st["_t_" + k] = o.get("value"), rt or 0
                    st["t"] = max(st.get("t") or 0, rt or 0)
        out = []
        for s in sorted(src, key=lambda s: s["km"] if s.get("km") is not None else 999):
            v = by.get(s["id"])
            if not v or v.get("temp") is None and v.get("wind") is None:
                continue
            x = dict(s, **{k: v.get(k) for k in KEYS.values()})
            x["age_min"] = round((now - v["t"]) / 60) if v.get("t") else None
            if x.get("temp") is not None and alt is not None and s.get("masl") is not None:
                x["tempAtMachine"] = round(x["temp"] + (s["masl"] - alt) * LAPSE, 1)   # omrekna med 0,65 °C/100 m
            out.append(x)
        res["stations"] = out[:3]
        if err:
            res["error"] = err
        return res


HIST_EL = ["air_temperature", "relative_humidity", "wind_speed", "wind_from_direction", "sum(precipitation_amount PT1H)"]
HIST_TTL = 1800
ORO = 0.07   # same nedbørauke per 100 m som snøkartet


def _compose(series, src, alt, t0, n):
    """Lag éi timeserie for staden (høgd alt) frå fleire stasjonar:
    temperatur frå stasjonen nærast i høgd (omrekna −0,65 °C/100 m), vind frå stasjonen nærast i høgd,
    nedbør frå næraste stasjon med nedbør (omrekna til høgda: +7 %/100 m), luftfukt frå kven som helst.
    Manglande timar for temperatur og vind blir fylte frå næraste time med data (maks 3 t)."""
    by = {s["id"]: s for s in src}
    def pick(key, order):
        for sid in order:
            ser = series.get(sid, {})
            if any(key in v for v in ser.values()):
                return sid
        return None
    hgt = sorted(by, key=lambda i: abs((by[i].get("masl") or 0) - (alt or 0)))
    near = sorted(by, key=lambda i: by[i].get("km") if by[i].get("km") is not None else 999)
    st = {k: pick(k, hgt if k in ("temp", "wind", "dir") else near) for k in ("temp", "wind", "dir", "precip", "rh")}
    out, miss = [], {"temp": 0, "wind": 0, "precip": 0}
    for i in range(n):
        t = t0 + i * 3600
        h = {"t": t * 1000, "hist": True}
        for k in ("temp", "wind", "dir", "rh", "precip"):
            sid = st[k]
            v = None
            if sid:
                ser = series[sid]
                v = ser.get(t, {}).get(k)
                if v is None and k != "precip":
                    for d in (1, -1, 2, -2, 3, -3):
                        v = ser.get(t + d * 3600, {}).get(k)
                        if v is not None:
                            break
            if v is not None and k == "temp" and alt is not None and by[sid].get("masl") is not None:
                v = v - LAPSE * (alt - by[sid]["masl"])
            if v is not None and k == "precip" and alt is not None and by[sid].get("masl") is not None:
                v = v * min(2.0, max(0.5, 1 + ORO * (alt - by[sid]["masl"]) / 100.0))
            h[k] = v
            if v is None and k in miss:
                miss[k] += 1
        if h["temp"] is None:
            continue                       # utan temperatur kan ikkje timen brukast
        if h["precip"] is None:
            h["precip"] = 0.0
        if h["rh"] is None:
            h["rh"] = 90.0
        if h["wind"] is None:
            h["wind"] = 0.0
        out.append(h)
    used = {k: (by[v]["name"] if v else None) for k, v in st.items()}
    return out, used, miss


def demo_history(alt, now, hours):
    """Oppdikta vêr bakover i tid (DEMO), same mønster som demo-varselet i ver.py."""
    import ver
    return [dict(h, hist=True) for h in ver.demo_hours(alt, now, k0=-hours, n=hours)]


def demo_stations(alt, now):
    """Oppdikta stasjonsmålingar til demo – namna er merkte DEMO."""
    lh = time.localtime(now).tm_hour
    base = -1.2 + 3.6 * math.cos(2 * math.pi * (lh - 15) / 24)
    out = []
    for name, masl, km, dt, w in (("DEMO Fjelltopp", 1050, 16.8, -1.5, 7.5), ("DEMO Vegvêr", 504, 9.4, 1.8, 3.1)):
        t = round(base + dt, 1)
        x = {"id": "DEMO", "name": name, "masl": masl, "km": km, "temp": t, "rh": 84 if masl < 900 else None, "wind": w,
             "gust": round(w * 1.6, 1), "dir": 250, "precip": 0.0, "snow": None, "age_min": 7}
        if alt is not None:
            x["tempAtMachine"] = round(t + (masl - alt) * LAPSE, 1)
        out.append(x)
    return out


if __name__ == "__main__":
    import sys
    from pathlib import Path
    import tempfile
    F = Frost(Path(tempfile.mkdtemp()) / "f.json")
    r = F.observations(62.3905, 6.5810, 640, demo="--demo" in sys.argv)
    print(json.dumps(r, ensure_ascii=False, indent=1)[:1500])
