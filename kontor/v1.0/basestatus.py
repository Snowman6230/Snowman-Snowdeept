# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Status frå SNOWMAN Base – berre lesing (avgjerd 2026-11-22: Base har berre med satellittar og NTRIP å gjere).

Office hentar /api/status frå Base kvart minutt når adressa er sett (Innstillingar › SNOWMAN Base), og viser
korreksjonsstraumane på oversikta. Åtvaringane frå Base (reglane om korreksjonane) kjem med i forbetringslista.
Office sender aldri noko til Base og endrar ingenting der.
"""
import base64
import json
import threading
import time
import urllib.error
import urllib.request

import nett


class BaseStatus:
    def __init__(self, cfg, events):
        self.cfg = cfg
        self.events = events
        self.lock = threading.Lock()
        self.last = {"t": None, "ok": None, "feil": "", "status": None}

    def configured(self):
        return bool(self.cfg["base"].get("adresse"))

    def fetch(self):
        c = self.cfg["base"]
        url = str(c.get("adresse") or "").strip().rstrip("/")
        if not url:
            return self.last
        if "://" not in url:
            url = "http://" + url
        req = urllib.request.Request(url + "/api/status", headers={"User-Agent": "SNOWMAN Office"})
        if c.get("brukar"):
            tok = base64.b64encode(f"{c['brukar']}:{c.get('passord') or ''}".encode()).decode()
            req.add_header("Authorization", "Basic " + tok)
        was = self.last.get("ok")
        try:
            with nett.urlopen(req, timeout=10) as r:
                s = json.loads(r.read(5_000_000).decode("utf-8"))
            self.last = {"t": time.time(), "ok": True, "feil": "", "status": s}
            if was is False:
                self.events.add("Kontakt med SNOWMAN Base att", "ok")
        except urllib.error.HTTPError as e:
            self.last = {"t": time.time(), "ok": False, "status": None,
                         "feil": "Base krev innlogging (administrator i Base)" if e.code == 401 else f"Base svarte {e.code}"}
        except Exception as e:
            self.last = {"t": time.time(), "ok": False, "status": None, "feil": nett.forklar(e)}
        if self.last["ok"] is False and was is not False:
            self.events.add(f"Får ikkje status frå SNOWMAN Base: {self.last['feil']}", "feil")
        return self.last

    def loop(self, stop_ev):
        while not stop_ev.is_set():
            if self.configured():
                self.fetch()
            stop_ev.wait(60)
