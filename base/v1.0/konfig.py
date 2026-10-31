# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Innstillingar for SNOWMAN Base (data/base.json) og innloggingar.

Innlogging er brukarnamn og passord (ingen nøklar). Kvar brukar har éi eller to roller:
    ntrip   maskinene: korreksjonar frå casteren og API-et (deling, anleggspakke, forslag) – same brukar og passord
    kontor  administrator: kontorsida (mountpoints, brukarar, anleggspakke …)
Første administrator blir laga på kontorsida frå det lokale nettet, eller med «brukar legg-til NAMN --rolle kontor».
Gløymt passord: «brukar passord NAMN» på maskina Base køyrer på.

Passord blir lagra som hash (PBKDF2-SHA256 med salt), aldri i klartekst – med eitt unntak: innlogging mot ein ANNAN
caster (relé frå t.d. CPOS) må lagrast slik at Base kan logge inn der. data/ ligg aldri i repoet (.gitignore).

Fila kan endrast medan Base køyrer (kommandoar i eit anna vindauge): Base les henne på nytt når ho er endra, og alle
endringar frå Base sjølv blir gjorde på den nyaste utgåva av fila (refresh før kvar endring) – ingenting blir overskrive.
"""
import copy
import hashlib
import hmac
import json
import os
import secrets
import threading
from pathlib import Path

VERSION = "1.2.0"
API_VERSION = 1

# Samspel med SNOWMAN snødjupne (pc/). Endrar du casteren eller API-et, skal kompatibilitetstesten
# (test/test_base.py, «Kompatibilitet») køyrast mot pc/v1.6, og desse tala oppdaterast:
#   - Casteren (NTRIP 1/2) fungerer med alle SNOWMAN-versjonar.
#   - API v1 (deling, anleggspakke, forslag) krev SNOWMAN med deling – planlagt v1.8.
#   - Eit brot i API-et gir ny API_VERSION; gamle maskiner får då beskjed om å oppdatere, ikkje feil data.
SNOWMAN_MIN = "1.8.0"
FUNKSJONAR = ["ntrip-caster", "ntrip-opplasting", "rele", "reserve", "tillegg-baner", "radata-logg", "basekontroll",
              "mountpoint-kontor", "innlogging-brukar", "ddns", "deling-v1", "anleggspakke-v1", "forslag-v1", "baner-brdc", "forbetringar", "ai"]

DEFAULT = {
    "namn": "SNOWMAN Base",
    "anlegg": "",
    "caster": {"port": 2101, "krev_innlogging": True},
    "web": {"port": 8780, "status_open": True},
    "brukarar": [],                     # {"namn", "hash", "roller": ["ntrip"|"kontor"], "mountpoints": ["*"]}
    "mountpoints": [],
    "logg": {"dagar": 30, "maks_mb": 5000},
    "deling": {"timar": 12, "behald_dagar": 30, "maskinplassar": 0},
    "anleggspakke": {"maks_mb": 4000, "behald_versjonar": 20},
    "baner": {"hent": False, "intervall_min": 30},
    "oppdatering": {"sjekk": True, "auto": False},   # auto: installer ny versjon sjølv om natta (03–05)
    "ai": {"leverandor": "av", "modell": "", "adresse": "", "api_nokkel": "", "intervall_t": 24},
    "vern": {"maks_feil": 10, "minutt": 10, "maks_tilkoplingar": 200, "maks_per_ip": 20},
    "ddns": {"url": "", "intervall_min": 10},   # oppdaterings-URL for dynamisk DNS (t.d. DuckDNS)
}
ROLLER = ("ntrip", "kontor")
MIN_PASSORD = 8

MOUNT_DEFAULT = {
    "namn": "",
    "skildring": "",
    "kjelder": [],          # i prioritert rekkjefølgje: første som har data, blir brukt (reserve ved utfall)
    "tillegg": [],          # kjelder som berre gir utvalde meldingar (t.d. satellittbaner) inn i straumen
    "byte_etter_s": 10,     # reserve blir teken i bruk når aktiv kjelde har vore stille så lenge
    "tilbake_etter_s": 60,  # kjelde med høgare prioritet blir teken i bruk att når ho har sendt stabilt så lenge
    "innmalt": None,        # {"lat", "lon", "h"}: innmålt ARP (EUREF89, ellipsoidisk høgd) – kontroll av 1005/1006
    "test": False,          # testdata (avspeling) – blir merkt TEST i kjeldetabellen
}


# ---------- hash ----------
def hash_pw(pw, salt=None, n=120_000):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", str(pw).encode("utf-8"), bytes.fromhex(salt), n).hex()
    return f"pbkdf2${n}${salt}${h}"


def check_pw(pw, stored):
    try:
        _, n, salt, h = str(stored).split("$")
        cand = hashlib.pbkdf2_hmac("sha256", str(pw).encode("utf-8"), bytes.fromhex(salt), int(n)).hex()
        return hmac.compare_digest(cand, h)
    except Exception:
        return False


def new_secret(n=18):
    """Lett lesbar nøkkel (utan forvekslingsteikn) – til NTRIP-passord og nøklar."""
    alpha = "abcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alpha) for _ in range(n))


class Config:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "base.json"
        self.lock = threading.RLock()
        self.first_start = not self.path.exists()
        self._mtime = None
        self._external = False
        self.data = self._load()

    def _load(self):
        data = copy.deepcopy(DEFAULT)
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self._merge(data, json.load(f))
            self._mtime = self.path.stat().st_mtime_ns
        data.pop("noklar", None)                       # nøklar (før v1.2) blir ikkje brukte lenger
        for m in data["mountpoints"]:
            for k, v in MOUNT_DEFAULT.items():
                m.setdefault(k, copy.deepcopy(v))
        for u in data["brukarar"]:
            u.setdefault("roller", ["ntrip"])          # brukarar frå før v1.2 var NTRIP-brukarar
            u.setdefault("mountpoints", ["*"])
        return data

    @staticmethod
    def _merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                Config._merge(dst[k], v)
            else:
                dst[k] = v

    def __getitem__(self, k):
        return self.data[k]

    def refresh(self):
        """Les fila på nytt om ho er endra utanfrå (t.d. av ein kommando). Returnerer True når ho vart lesen."""
        with self.lock:
            try:
                mt = self.path.stat().st_mtime_ns
            except OSError:
                return False
            if mt == self._mtime:
                return False
            try:
                self.data = self._load()
            except (OSError, ValueError):
                return False                           # halvskriven fil – prøv att neste gong
            self._external = True
            return True

    def pop_external(self):
        """True éin gong etter at fila er lesen på nytt (endra utanfrå) – Base tek då endringa i bruk."""
        with self.lock:
            x, self._external = self._external, False
            return x

    def save(self):
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            self._mtime = self.path.stat().st_mtime_ns

    def update(self, fn):
        """Endre innstillingane trygt: les nyaste fil, gjer endringa, lagre. Returnerer det fn returnerer."""
        with self.lock:
            self.refresh()
            out = fn(self.data)
            self.save()
            return out

    def first_setup(self):
        """Første oppstart: lag fila. Brukarar blir ikkje laga her – første administrator blir laga på kontorsida
        (frå det lokale nettet) eller med kommandoen «brukar legg-til NAMN --rolle kontor»."""
        with self.lock:
            if not self.path.exists():
                self.save()
        return []

    # ---------- brukarar ----------
    def find_user(self, name):
        name = str(name or "").strip()
        return next((u for u in self.data["brukarar"] if u.get("namn", "").lower() == name.lower()), None)

    def check_user(self, name, pw, role=None):
        """Brukaren om namn og passord stemmer (og brukaren har rolla). Elles None."""
        u = self.find_user(name)
        if not u or not pw or not check_pw(pw, u.get("hash", "")):
            return None
        if role and role not in (u.get("roller") or []):
            return None
        return u

    def user_ok(self, name, pw, mount):
        """NTRIP: rett brukar og passord, rolla «ntrip», og tilgang til mountpointet."""
        u = self.check_user(name, pw, "ntrip")
        if not u:
            return False
        allowed = u.get("mountpoints") or ["*"]
        return "*" in allowed or mount in allowed

    def has_admin(self):
        return any("kontor" in (u.get("roller") or []) for u in self.data["brukarar"])

    def set_user(self, name, pw=None, mounts=None, roles=None):
        """Ny brukar eller endring. pw=None: behald passordet. roles/mounts=None: behald (ny brukar: ntrip, alle)."""
        name = valid_name(name)
        if pw is not None:
            valid_pw(pw)
        if roles is not None:
            roles = [r for r in ROLLER if r in roles]
            if not roles:
                raise ValueError("Vel minst éi rolle (ntrip eller kontor)")

        def fn(d):
            u = next((x for x in d["brukarar"] if x.get("namn", "").lower() == name.lower()), None)
            if u is None:
                if pw is None:
                    raise ValueError("Ny brukar må ha passord")
                u = {"namn": name, "hash": "", "roller": roles or ["ntrip"], "mountpoints": mounts or ["*"]}
                d["brukarar"].append(u)
            else:
                if roles is not None and "kontor" in u.get("roller", []) and "kontor" not in roles and \
                        sum("kontor" in x.get("roller", []) for x in d["brukarar"]) <= 1:
                    raise ValueError("Kan ikkje ta kontor-rolla frå den siste administratoren")
                if roles is not None:
                    u["roller"] = roles
                if mounts is not None:
                    u["mountpoints"] = mounts or ["*"]
            if pw is not None:
                u["hash"] = hash_pw(pw)
            return dict(u)
        return self.update(fn)

    def remove_user(self, name):
        def fn(d):
            u = next((x for x in d["brukarar"] if x.get("namn", "").lower() == str(name).lower()), None)
            if u is None:
                return False
            if "kontor" in u.get("roller", []) and sum("kontor" in x.get("roller", []) for x in d["brukarar"]) <= 1:
                raise ValueError("Kan ikkje slette den siste administratoren")
            d["brukarar"].remove(u)
            return True
        return self.update(fn)

    def users_public(self):
        return [{"namn": u.get("namn"), "roller": u.get("roller", []), "mountpoints": u.get("mountpoints", ["*"])}
                for u in self.data["brukarar"]]

    def public(self):
        """Innstillingane utan hash og passord (statussida)."""
        d = copy.deepcopy(self.data)
        d["brukarar"] = self.users_public()
        d["ai"]["api_nokkel"] = bool(d["ai"].get("api_nokkel"))
        for m in d["mountpoints"]:
            for s in m.get("kjelder", []) + m.get("tillegg", []):
                for k in ("passord", "hash"):
                    if k in s:
                        s[k] = "***"
        return d


def valid_name(name):
    name = str(name or "").strip()
    if not name or len(name) > 32 or not all(c.isalnum() or c in "-_." for c in name):
        raise ValueError("Brukarnamnet kan ha bokstavar, tal, - _ og . (maks 32 teikn, utan mellomrom)")
    return name


def valid_pw(pw):
    pw = str(pw or "")
    if len(pw) < MIN_PASSORD:
        raise ValueError(f"Passordet må ha minst {MIN_PASSORD} teikn")
    if len(pw) > 128 or pw != pw.strip() or any(ord(c) < 32 for c in pw):
        raise ValueError("Passordet kan ikkje byrje eller slutte med mellomrom, og maks 128 teikn")
    return pw
