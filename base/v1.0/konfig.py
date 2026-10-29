# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Innstillingar for SNOWMAN Base (data/base.json) og innloggingar.

Fila blir laga ved første oppstart. Passord blir lagra som hash (PBKDF2-SHA256 med salt), aldri i klartekst – med
eitt unntak: innlogging mot ein ANNAN caster (relé frå t.d. CPOS) må lagrast slik at Base kan logge inn der.
data/ ligg aldri i repoet (.gitignore).
"""
import copy
import hashlib
import hmac
import json
import os
import secrets
import threading
from pathlib import Path

VERSION = "1.1.0"
API_VERSION = 1

# Samspel med SNOWMAN snødjupne (pc/). Endrar du casteren eller API-et, skal kompatibilitetstesten
# (test/test_base.py, «Kompatibilitet») køyrast mot pc/v1.6, og desse tala oppdaterast:
#   - Casteren (NTRIP 1/2) fungerer med alle SNOWMAN-versjonar.
#   - API v1 (deling, anleggspakke, forslag) krev SNOWMAN med deling – planlagt v1.8.
#   - Eit brot i API-et gir ny API_VERSION; gamle maskiner får då beskjed om å oppdatere, ikkje feil data.
SNOWMAN_MIN = "1.8.0"
FUNKSJONAR = ["ntrip-caster", "ntrip-opplasting", "rele", "reserve", "tillegg-baner", "radata-logg", "basekontroll",
              "mountpoint-kontor", "deling-v1", "anleggspakke-v1", "forslag-v1", "baner-brdc", "forbetringar", "ai"]

DEFAULT = {
    "namn": "SNOWMAN Base",
    "anlegg": "",
    "caster": {"port": 2101, "krev_innlogging": True},
    "web": {"port": 8780, "status_open": True},
    "brukarar": [],                     # NTRIP-brukarar: {"namn", "hash", "mountpoints": ["*"]}
    "mountpoints": [],
    "logg": {"dagar": 30, "maks_mb": 5000},
    "deling": {"timar": 12, "behald_dagar": 30, "maskinplassar": 0},
    "anleggspakke": {"maks_mb": 4000, "behald_versjonar": 20},
    "baner": {"hent": False, "intervall_min": 30},
    "oppdatering": {"sjekk": True, "auto": False},   # auto: installer ny versjon sjølv om natta (03–05)
    "ai": {"leverandor": "av", "modell": "", "adresse": "", "api_nokkel": "", "intervall_t": 24},
    "noklar": {"anlegg": "", "kontor": ""},   # hash av anleggsnøkkel (maskiner) og kontornøkkel (administrator)
}

MOUNT_DEFAULT = {
    "namn": "",
    "skildring": "",
    "kjelder": [],          # i prioritert rekkjefølgje: første som har data, blir brukt (reserve ved utfall)
    "tillegg": [],          # kjelder som berre gir utvalde meldingar (t.d. satellittbaner) inn i straumen
    "byte_etter_s": 10,     # reserve blir teken i bruk når aktiv kjelde har vore stille så lenge
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
        self.data = copy.deepcopy(DEFAULT)
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self._merge(self.data, json.load(f))
        for m in self.data["mountpoints"]:
            for k, v in MOUNT_DEFAULT.items():
                m.setdefault(k, copy.deepcopy(v))

    @staticmethod
    def _merge(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                Config._merge(dst[k], v)
            else:
                dst[k] = v

    def __getitem__(self, k):
        return self.data[k]

    def save(self):
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def first_setup(self):
        """Første oppstart: lag NTRIP-brukar og nøklar, og skriv dei éin gong til data/NOKLAR.txt."""
        lines = []
        with self.lock:
            if not self.data["brukarar"]:
                pw = new_secret(12)
                self.data["brukarar"].append({"namn": "snowman", "hash": hash_pw(pw), "mountpoints": ["*"]})
                lines.append(f"NTRIP-brukar (alle maskiner kan bruke same): snowman / {pw}")
            if not self.data["noklar"]["anlegg"]:
                k = new_secret(24)
                self.data["noklar"]["anlegg"] = hash_pw(k)
                lines.append(f"Anleggsnøkkel (SNOWMAN på maskinene – deling og anleggspakke): {k}")
            if not self.data["noklar"]["kontor"]:
                k = new_secret(24)
                self.data["noklar"]["kontor"] = hash_pw(k)
                lines.append(f"Kontornøkkel (administrator – kontorsida og opplasting): {k}")
            self.save()
        if lines:
            f = self.folder / "NOKLAR.txt"
            with open(f, "a", encoding="utf-8") as out:
                out.write("SNOWMAN Base – innloggingar laga ved oppstart. Ta vare på dei og slett fila.\n")
                out.write("Nøklane blir berre lagra som hash i base.json og kan ikkje hentast fram att.\n\n")
                out.write("\n".join(lines) + "\n\n")
            try:
                os.chmod(f, 0o600)
            except OSError:
                pass
        return lines

    # ---------- brukarar ----------
    def user_ok(self, name, pw, mount):
        for u in self.data["brukarar"]:
            if u.get("namn") == name and check_pw(pw, u.get("hash", "")):
                allowed = u.get("mountpoints") or ["*"]
                return "*" in allowed or mount in allowed
        return False

    def set_user(self, name, pw, mounts=None):
        with self.lock:
            self.data["brukarar"] = [u for u in self.data["brukarar"] if u.get("namn") != name]
            self.data["brukarar"].append({"namn": name, "hash": hash_pw(pw), "mountpoints": mounts or ["*"]})
            self.save()

    def remove_user(self, name):
        with self.lock:
            before = len(self.data["brukarar"])
            self.data["brukarar"] = [u for u in self.data["brukarar"] if u.get("namn") != name]
            self.save()
            return len(self.data["brukarar"]) < before

    def key_ok(self, key, kind):
        h = self.data["noklar"].get(kind) or ""
        return bool(h) and bool(key) and check_pw(key, h)

    def set_key(self, kind):
        k = new_secret(24)
        with self.lock:
            self.data["noklar"][kind] = hash_pw(k)
            self.save()
        return k

    def public(self):
        """Innstillingane utan hash og passord (statussida)."""
        d = copy.deepcopy(self.data)
        d["brukarar"] = [{"namn": u.get("namn"), "mountpoints": u.get("mountpoints")} for u in d["brukarar"]]
        d["noklar"] = {k: bool(v) for k, v in d["noklar"].items()}
        d["ai"]["api_nokkel"] = bool(d["ai"].get("api_nokkel"))
        for m in d["mountpoints"]:
            for s in m.get("kjelder", []) + m.get("tillegg", []):
                for k in ("passord", "hash"):
                    if k in s:
                        s[k] = "***"
        return d
