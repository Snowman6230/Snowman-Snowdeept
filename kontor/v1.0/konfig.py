# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Innstillingar for SNOWMAN Kontor (data/kontor.json) og innloggingar.

SNOWMAN Kontor er anleggsserveren og kontorsida, og køyrer på ein PC på anlegget (avgjerd 2026-11-22). Han har
ingenting med korreksjonane å gjere – det gjer SNOWMAN Base (Raspberry Pi ved antenna) åleine.

Innlogging er brukarnamn og passord. Kvar brukar har éi eller to roller:
    maskin  tråkkemaskinene: anleggspakke, forslag, hjarteslag og (v1.8) deling – brukarnamn og passord står i
            SNOWMAN snødjupne › Innst. › Trasear › «Kopling til SNOWMAN Kontor»
    kontor  administrator: kontorsida
Første administrator blir laga på kontorsida frå det lokale nettet, eller med «brukar legg-til NAMN --rolle kontor».
Gløymt passord: «brukar passord NAMN» på PC-en Kontor køyrer på.

Passord blir lagra som hash (PBKDF2-SHA256 med salt), aldri i klartekst – med unntak av innlogginga mot SNOWMAN Base
(statusvising) og API-nøkkelen til AI, som må kunne brukast. data/ ligg aldri i repoet (.gitignore).

Fila kan endrast medan Kontor køyrer (kommandoar i eit anna vindauge): Kontor les henne på nytt når ho er endra.
"""
import copy
import hashlib
import hmac
import json
import os
import secrets
import threading
from pathlib import Path

VERSION = "1.1.2"
API_VERSION = 1

# Samspel med SNOWMAN snødjupne (pc/): anleggspakke og forslag frå v1.6.137, terreng, kontormodus og sanntid frå v1.6.139.
# Eit brot i API-et gir ny API_VERSION; gamle maskiner får då beskjed om å oppdatere, ikkje feil data.
SNOWMAN_MIN = "1.6.139"
FUNKSJONAR = ["kontor", "innlogging-brukar", "deling-v1", "anleggspakke-v1", "anleggspakke-format-1", "forslag-v1",
              "forbetringar", "ai", "base-status", "terreng-i-pakke", "kontormodus"]

DEFAULT = {
    "namn": "SNOWMAN Kontor",
    "anlegg": "",
    "web": {"port": 8790, "maskinport": 8791},   # maskinport: berre maskin-API-et – den som kan opnast i ruteren (0 = av)
    # SNOWMAN snødjupne i kontormodus (same kart, 3D, terreng og trasear som i maskina) – Kontor startar det sjølv
    "kartvising": {"start": True, "port": 8765},
    "brukarar": [],                     # {"namn", "hash", "roller": ["maskin"|"kontor"]}
    "deling": {"timar": 12, "behald_dagar": 30, "maskinplassar": 0},
    "anleggspakke": {"maks_mb": 4000, "behald_versjonar": 20},
    "base": {"adresse": "", "brukar": "", "passord": ""},   # SNOWMAN Base (berre lesing av statusen), t.d. http://snowman-base.local:8780
    "oppdatering": {"sjekk": True, "auto": False},   # auto: installer ny versjon sjølv om natta (03–05)
    "ai": {"leverandor": "av", "modell": "", "adresse": "", "api_nokkel": "", "intervall_t": 24},
    "vern": {"maks_feil": 10, "minutt": 10, "maks_tilkoplingar": 200, "maks_per_ip": 20},
}
ROLLER = ("maskin", "kontor")
MIN_PASSORD = 8


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


class Config:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "kontor.json"
        self.lock = threading.RLock()
        self.first_start = not self.path.exists()
        self._mtime = None
        self.data = self._load()

    def _load(self):
        data = copy.deepcopy(DEFAULT)
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self._merge(data, json.load(f))
            self._mtime = self.path.stat().st_mtime_ns
        for u in data["brukarar"]:
            u.setdefault("roller", ["maskin"])
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
                return False
            return True

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
        with self.lock:
            if not self.path.exists():
                self.save()
        return []

    # ---------- brukarar ----------
    def find_user(self, name):
        name = str(name or "").strip()
        return next((u for u in self.data["brukarar"] if u.get("namn", "").lower() == name.lower()), None)

    def check_user(self, name, pw, role=None):
        u = self.find_user(name)
        if not u or not pw or not check_pw(pw, u.get("hash", "")):
            return None
        if role and role not in (u.get("roller") or []):
            return None
        return u

    def has_admin(self):
        return any("kontor" in (u.get("roller") or []) for u in self.data["brukarar"])

    def set_user(self, name, pw=None, roles=None):
        """Ny brukar eller endring. pw=None: behald passordet. roles=None: behald (ny brukar: maskin)."""
        name = valid_name(name)
        if pw is not None:
            valid_pw(pw)
        if roles is not None:
            roles = [r for r in ROLLER if r in roles]
            if not roles:
                raise ValueError("Vel minst éi rolle (maskin eller kontor)")

        def fn(d):
            u = next((x for x in d["brukarar"] if x.get("namn", "").lower() == name.lower()), None)
            if u is None:
                if pw is None:
                    raise ValueError("Ny brukar må ha passord")
                u = {"namn": name, "hash": "", "roller": roles or ["maskin"]}
                d["brukarar"].append(u)
            else:
                if roles is not None and "kontor" in u.get("roller", []) and "kontor" not in roles and \
                        sum("kontor" in x.get("roller", []) for x in d["brukarar"]) <= 1:
                    raise ValueError("Kan ikkje ta kontor-rolla frå den siste administratoren")
                if roles is not None:
                    u["roller"] = roles
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
        return [{"namn": u.get("namn"), "roller": u.get("roller", [])} for u in self.data["brukarar"]]

    def public(self):
        """Innstillingane utan hash, passord og nøklar."""
        d = copy.deepcopy(self.data)
        d["brukarar"] = self.users_public()
        d["ai"]["api_nokkel"] = bool(d["ai"].get("api_nokkel"))
        d["base"]["passord"] = bool(d["base"].get("passord"))
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
