# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""«Slik når maskinene Base»: lokale og offentleg IP-adresse, dynamisk DNS, og kva som skal stå i SNOWMAN snødjupne.

Som Norman sin base (gpsbase.dyndns.org:2101) treng maskinene på mobilnettet tre ting:
    1. eit fast namn som peikar på den offentlege IP-adressa til anlegget (dynamisk DNS)
    2. port 2101 opna i ruteren mot maskina Base køyrer på (berre 2101 – aldri 8780)
    3. casteren i Base
Base kan sjølv halde det faste namnet oppdatert: lim inn oppdaterings-adressa frå DDNS-tenesta (t.d. DuckDNS:
https://www.duckdns.org/update?domains=fjellsatra&token=…). Base kallar ho kvart 10. minutt og kontrollerer at namnet
peikar på den offentlege adressa.
"""
import ipaddress
import re
import socket
import threading
import time
import urllib.parse
import urllib.request

import nett
from konfig import VERSION

IP_URL = "https://api.ipify.org"


def local_ips():
    ips = set()
    try:                                             # adressa som blir brukt ut mot nettet (ingen pakkar blir sende)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def host_from_url(url):
    """Namnet DDNS-adressa oppdaterer, når det går an å lese det ut (DuckDNS: domains=…)."""
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    except ValueError:
        return ""
    for k in ("domains", "domain", "hostname", "host"):
        if q.get(k):
            h = q[k][0].split(",")[0].strip()
            if h and "duckdns.org" in url and "." not in h:
                h += ".duckdns.org"
            return h
    return ""


class Tilgang:
    def __init__(self, base):
        self.base = base
        self.lock = threading.Lock()
        self.public = {"ip": None, "t": 0, "feil": ""}
        self.ddns = {"t": None, "ok": None, "svar": "", "namn": "", "peikar_til": None}

    def public_ip(self, fresh=False):
        with self.lock:
            if not fresh and self.public["ip"] and time.time() - self.public["t"] < 600:
                return self.public["ip"]
        try:
            req = urllib.request.Request(IP_URL, headers={"User-Agent": f"SNOWMAN Base/{VERSION}"})
            with nett.urlopen(req, timeout=8) as r:
                ip = r.read(64).decode("ascii", "ignore").strip()
            ipaddress.ip_address(ip)
            with self.lock:
                self.public.update(ip=ip, t=time.time(), feil="")
            return ip
        except Exception as e:
            with self.lock:
                self.public.update(feil=nett.forklar(e), t=time.time())
            return self.public["ip"]

    def ddns_now(self):
        """Køyr oppdateringa av dynamisk DNS no og sjekk kvar namnet peikar."""
        url = (self.base.cfg["ddns"].get("url") or "").strip()
        name = host_from_url(url)
        res = {"t": time.time(), "ok": None, "svar": "", "namn": name, "peikar_til": None}
        if url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": f"SNOWMAN Base/{VERSION}"})
                with nett.urlopen(req, timeout=15) as r:
                    text = r.read(300).decode("utf-8", "ignore").strip()
                res["svar"] = text[:120]
                res["ok"] = not re.match(r"^(KO|ERROR|badauth|nohost|abuse|911|notfqdn)", text, re.I)
            except Exception as e:
                res.update(ok=False, svar=nett.forklar(e))
            if not res["ok"]:
                self.base.events.add(f"Dynamisk DNS feila: {res['svar']}", "feil")
        if name:
            try:
                res["peikar_til"] = socket.gethostbyname(name)
            except OSError:
                res["peikar_til"] = None
        with self.lock:
            self.ddns = res
        return {"ddns": res}

    def loop(self, stop_ev):
        stop_ev.wait(20)
        while not stop_ev.is_set():
            if self.base.cfg["ddns"].get("url"):
                try:
                    self.ddns_now()
                except Exception as e:
                    self.base.events.add(f"Dynamisk DNS feila: {e}", "feil")
            stop_ev.wait(max(5, int(self.base.cfg["ddns"].get("intervall_min", 10) or 10)) * 60)

    def info(self, fresh=False):
        b = self.base
        pub = self.public_ip(fresh)
        d = dict(self.ddns)
        name = d.get("namn") or host_from_url(b.cfg["ddns"].get("url") or "")
        if name and (fresh or not d.get("peikar_til")):
            try:
                d["peikar_til"] = socket.gethostbyname(name)
            except OSError:
                d["peikar_til"] = None
        d["namn"] = name
        d["har_url"] = bool(b.cfg["ddns"].get("url"))
        d["peikar_rett"] = bool(pub and d.get("peikar_til") == pub)
        cgnat = None
        if pub:
            a = ipaddress.ip_address(pub)
            cgnat = a in ipaddress.ip_network("100.64.0.0/10") or a.is_private
        return {"lokale": local_ips(), "offentleg": pub, "offentleg_feil": self.public.get("feil", ""),
                "cgnat": cgnat, "caster_port": b.caster_port, "web_port": b.web_port,
                "mountpoints": list(b.mounts), "ddns": d}
