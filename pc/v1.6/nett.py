# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Samband til nettenestene (MET-varsel og Frost): forklaring av feil på norsk, og ein test føraren kan køyre frå Vêr.

Vanlege årsaker på ein maskin-PC:
  * ikkje nett (mobil-ruter av, flymodus) eller DNS som ikkje svarar  → «finn ikkje adressa»
  * sertifikatfeil (Python manglar rotsertifikat, eller ein brannmur/proxy byter sertifikat) → «sertifikat»
  * proxy eller brannmur som stengjer trafikk ut                       → «proxy/brannmur»
  * tenesta svarar med feil (403 MET: avvist, 401/403 Frost: klient-ID) → «avvist»
"""
import json, socket, ssl, time, urllib.error, urllib.request

TESTS = [("MET vêrvarsel (api.met.no)", "https://api.met.no/weatherapi/locationforecast/2.0/status"),
         ("MET Frost målingar (frost.met.no)", "https://frost.met.no/sources/v0.jsonld?ids=SN18700")]


def explain(e):
    """Kort forklaring på norsk av ein nettverksfeil (til føraren)."""
    s = str(getattr(e, "reason", "") or e)
    low = s.lower()
    if isinstance(e, urllib.error.HTTPError):
        if e.code in (401, 403):
            return f"Tenesta avviste førespurnaden ({e.code}). For Frost: sjekk klient-ID. For MET: programmet må ha eigen User-Agent."
        if e.code == 429:
            return "For mange førespurnader (429) – vent litt."
        return f"Tenesta svarte med feil {e.code}."
    if "certificate" in low or "ssl" in low:
        return ("Sertifikatfeil: PC-en godtek ikkje sertifikatet til tenesta. Sjekk at klokka på PC-en er rett, "
                "eller om ein brannmur/proxy byter sertifikat. Køyr Windows Update (rotsertifikat).")
    if "getaddrinfo" in low or "name or service" in low or "nodename" in low or "11001" in low or "11002" in low:
        return "Finn ikkje adressa: PC-en har ikkje nett, eller DNS svarar ikkje. Sjekk mobil-ruter/Wi-Fi."
    if "timed out" in low or isinstance(e, (socket.timeout, TimeoutError)):
        return "Tidsavbrot: nettet er for tregt eller stengt. Sjekk dekning og ruter."
    if "tunnel" in low or "proxy" in low or "407" in low:
        return "Ein proxy stengjer trafikken ut. Sjekk proxy-innstillingane i Windows."
    if "refused" in low or "10061" in low or "unreachable" in low or "10051" in low or "10065" in low:
        return "Sambandet vart avvist/nettet er ikkje tilgjengeleg. Sjekk nett og brannmur."
    return "Ukjend nettverksfeil: " + s[:160]


def test(ua, frost_id=None, timeout=8):
    """Test samband til MET og Frost. Returnerer liste med {name, ok, ms, status, text}."""
    import base64
    out = []
    try:
        socket.getaddrinfo("api.met.no", 443)
        dns = True
    except Exception:
        dns = False
    for name, url in TESTS:
        t0 = time.time()
        h = {"User-Agent": ua}
        if "frost" in url and frost_id:
            h["Authorization"] = "Basic " + base64.b64encode((frost_id + ":").encode()).decode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                r.read(2000)
                out.append({"name": name, "ok": True, "ms": int((time.time() - t0) * 1000), "status": r.status, "text": "OK"})
        except Exception as e:
            out.append({"name": name, "ok": False, "ms": int((time.time() - t0) * 1000),
                        "status": getattr(e, "code", None), "text": explain(e), "detail": str(e)[:200]})
    proxies = urllib.request.getproxies()
    return {"dns": dns, "tests": out, "proxy": {k: v for k, v in proxies.items() if k in ("http", "https")},
            "ssl": ssl.OPENSSL_VERSION, "time": time.strftime("%Y-%m-%d %H:%M:%S")}
