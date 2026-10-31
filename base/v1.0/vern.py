# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Vern av Base når port 2101 (og ev. 8780) er open: sperre ved mange feil passord, grense for tilkoplingar, og
innloggingsøkter for kontorsida.

    Sperre      maks_feil feil innloggingar frå same IP-adresse innanfor «minutt» → sperra like lenge.
                Gjeld både NTRIP og kontorsida. Lokale adresser (127.0.0.1) blir aldri sperra.
    Tilkoplingar maks_tilkoplingar i alt og maks_per_ip frå same adresse samstundes (casteren).
    Økter       Kontorsida loggar inn med brukarnamn og passord og får ei økt (tilfeldig tekst) som gjeld i 12 timar
                etter siste bruk. Øktene ligg berre i minnet: etter omstart av Base må ein logge inn på nytt.
"""
import ipaddress
import secrets
import threading
import time

OKT_TIMAR = 12


def is_local(ip):
    """Adresse på det lokale nettet (eller same maskin) – brukt til oppsett av første administrator."""
    try:
        a = ipaddress.ip_address(str(ip).split("%")[0])
        if a.version == 6 and a.ipv4_mapped:
            a = a.ipv4_mapped
        return a.is_loopback or a.is_private or a.is_link_local
    except ValueError:
        return False


class Vern:
    def __init__(self, cfg, events):
        self.cfg = cfg
        self.events = events
        self.lock = threading.Lock()
        self.fails = {}          # ip → [tider]
        self.blocked = {}        # ip → til
        self.conns = {}          # ip → tal opne
        self.sessions = {}       # token → {"brukar", "til"}

    def _c(self, k, default):
        try:
            return int(self.cfg["vern"].get(k, default))
        except (KeyError, TypeError, ValueError):
            return default

    # ---------- sperre ----------
    def is_blocked(self, ip):
        with self.lock:
            until = self.blocked.get(ip)
            if until and until > time.time():
                return True
            self.blocked.pop(ip, None)
            return False

    def failed(self, ip, kva):
        """Registrer feil innlogging. Returnerer True når adressa no blir sperra."""
        if ip in ("127.0.0.1", "::1"):
            return False
        win = self._c("minutt", 10) * 60
        now = time.time()
        with self.lock:
            lst = [t for t in self.fails.get(ip, []) if now - t < win]
            lst.append(now)
            self.fails[ip] = lst
            if len(lst) >= self._c("maks_feil", 10) and ip not in self.blocked:
                self.blocked[ip] = now + win
                self.fails.pop(ip, None)
                hit = True
            else:
                hit = False
            if len(self.fails) > 5000:                         # vern mot at lista veks utan grense
                for k in list(self.fails)[:2500]:
                    self.fails.pop(k, None)
        if hit:
            self.events.add(f"{ip} er sperra i {win // 60} min etter {self._c('maks_feil', 10)} feil innloggingar ({kva})",
                            "feil")
        return hit

    def ok(self, ip):
        with self.lock:
            self.fails.pop(ip, None)

    # ---------- tilkoplingar (casteren) ----------
    def open_conn(self, ip):
        with self.lock:
            total = sum(self.conns.values())
            if total >= self._c("maks_tilkoplingar", 200) or self.conns.get(ip, 0) >= self._c("maks_per_ip", 20):
                return False
            self.conns[ip] = self.conns.get(ip, 0) + 1
            return True

    def close_conn(self, ip):
        with self.lock:
            n = self.conns.get(ip, 0) - 1
            if n > 0:
                self.conns[ip] = n
            else:
                self.conns.pop(ip, None)

    # ---------- økter (kontorsida) ----------
    def new_session(self, user):
        tok = secrets.token_urlsafe(32)
        with self.lock:
            now = time.time()
            for k in [k for k, v in self.sessions.items() if v["til"] < now]:
                self.sessions.pop(k, None)
            self.sessions[tok] = {"brukar": user, "til": now + OKT_TIMAR * 3600}
        return tok

    def session_user(self, tok):
        if not tok:
            return None
        with self.lock:
            s = self.sessions.get(tok)
            if not s or s["til"] < time.time():
                self.sessions.pop(tok, None)
                return None
            s["til"] = time.time() + OKT_TIMAR * 3600
            return s["brukar"]

    def end_session(self, tok):
        with self.lock:
            self.sessions.pop(tok, None)

    def end_user_sessions(self, user):
        """Når passordet blir endra eller brukaren sletta: logg ut alle øktene til brukaren."""
        with self.lock:
            for k in [k for k, v in self.sessions.items() if v["brukar"].lower() == str(user).lower()]:
                self.sessions.pop(k, None)
