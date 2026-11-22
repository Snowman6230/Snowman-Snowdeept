# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Kopling til SNOWMAN Base – anleggspakke frå kontoret (v1.6.136, VEGEN-VIDARE kap. 16 steg 2).

Valfri: SNOWMAN snødjupne fungerer fullt ut utan Base (kap. 19). Når koplinga er på:
- «Hent frå Base» hentar den aktive anleggspakka (trasear, forbodne område, hindringar, kontrollpunkt) gjennom
  maskin-API-et i Base (port 2101, same innlogging som NTRIP – Base 1.3.0 eller nyare).
- Pakka blir kontrollert (manifest, sha256, innhald) og lagra lokalt i data/anleggspakke/. Er Base borte, gjeld siste
  pakke. Det som var i maskina før, blir teke vare på i data/anleggspakke/forrige/.
- Trasear, forbodne område og kontrollpunkt er då styrte frå kontoret. Føraren kan berre sende forslag.
  Ei ny hindring blir lagd inn lokalt med éin gong (varsel med det same) og sendt til kontoret som forslag
  (avgjerd 1, 2026-11-20). Forslag som ikkje kom fram, ligg i kø og blir sende ved neste henting.
- Terreng blir ikkje sendt i formatversjon 1 (avgjerd 2).

SNOWMAN sender aldri noko til GNSS-mottakaren – dette er berre nettverk mellom maskina og Base.
"""
import base64
import hashlib
import io
import json
import shutil
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

FORMAT = "snowman-anleggspakke"
FORMATVERSJON = 1
KJENDE = {"trasear.json": "trasear", "objekt.json": "objekt", "kontrollpunkt.json": "points"}
MAKS_PAKKE = 200 * 1024 * 1024        # utan terreng er pakka berre nokre MB
TIMEOUT = 20


class Feil(Exception):
    pass


def vtuple(v):
    out = []
    for x in str(v or "0").split("."):
        try:
            out.append(int("".join(c for c in x if c.isdigit()) or 0))
        except ValueError:
            out.append(0)
    return tuple(out)


def les_pakke(data):
    """Kontrollerer ei anleggspakke (bytes) og returnerer (manifest, {fil: innhald}). Kastar Feil."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise Feil("Anleggspakka er ikkje ei gyldig zip-fil.")
    with z:
        namn = {i.filename: i for i in z.infolist() if not i.is_dir()}
        if "manifest.json" not in namn:
            raise Feil("Anleggspakka manglar manifest.json (krev SNOWMAN Base 1.3.0 eller nyare).")
        try:
            m = json.loads(z.read("manifest.json").decode("utf-8"))
        except ValueError:
            raise Feil("manifest.json i anleggspakka er ikkje gyldig JSON.")
        if m.get("format") != FORMAT:
            raise Feil("Fila er ikkje ei SNOWMAN-anleggspakke.")
        if m.get("formatversjon") != FORMATVERSJON:
            raise Feil(f"Anleggspakka har formatversjon {m.get('formatversjon')}. Denne SNOWMAN kjenner berre "
                       f"versjon {FORMATVERSJON} – oppdater SNOWMAN.")
        filer = m.get("filer") or {}
        innhald = {}
        for n, h in filer.items():
            if n not in namn:
                raise Feil(f"{n} manglar i anleggspakka.")
            b = z.read(n)
            if hashlib.sha256(b).hexdigest() != str(h).lower():
                raise Feil(f"{n} i anleggspakka er skadd (sha256 stemmer ikkje).")
            if n in KJENDE:
                try:
                    d = json.loads(b.decode("utf-8"))
                except ValueError:
                    raise Feil(f"{n} i anleggspakka er ikkje gyldig JSON.")
                if not isinstance(d, dict) or not isinstance(d.get(KJENDE[n]), list):
                    raise Feil(f"{n} i anleggspakka har feil oppbygnad.")
                innhald[n] = d[KJENDE[n]]
        if not innhald:
            raise Feil("Anleggspakka har verken trasear, hindringar eller kontrollpunkt.")
        return m, innhald


class BaseKopling:
    def __init__(self, data_dir, version, log=None):
        self.dir = Path(data_dir) / "anleggspakke"
        self.version = version
        self.log = log or (lambda s: None)
        self.lock = threading.Lock()
        self.sist = {"t": None, "ok": None, "melding": ""}
        self.aktiv = self._read("aktiv.json") or None
        self.ko = self._read("forslag-ko.json") or []
        self.mid = self._machine_id(Path(data_dir) / "maskin-id.txt")

    # ---------- lagring ----------
    def _read(self, name):
        try:
            return json.loads((self.dir / name).read_text("utf-8"))
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Kunne ikkje lese {name}:", e)
            return None

    def _write(self, name, obj):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / (name + ".tmp")
        tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), "utf-8")
        tmp.replace(self.dir / name)

    @staticmethod
    def _machine_id(path):
        """Fast ID for maskina mot Base (hjarteslag og forslag). Laga éin gong og lagra i data/maskin-id.txt."""
        try:
            v = path.read_text("utf-8").strip()
            if v:
                return v[:40]
        except FileNotFoundError:
            pass
        host = "".join(c for c in socket.gethostname() if c.isalnum() or c in "-_")[:20] or "maskin"
        v = f"{host}-{uuid.uuid4().hex[:6]}"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(v, "utf-8")
        except OSError:
            pass
        return v

    # ---------- oppsett ----------
    @staticmethod
    def target(cfg):
        """(vert, port, brukar, passord) – tomme felt = same som NTRIP-oppsettet."""
        host = (cfg.get("base_host") or cfg.get("caster") or "").strip()
        port = int(cfg.get("base_port") or cfg.get("caster_port") or 2101)
        user = cfg.get("base_user") or cfg.get("username") or ""
        pw = cfg.get("base_pass") or cfg.get("password") or ""
        return host, port, user, pw

    def styrt(self, cfg):
        """Er trasear, forbodne område og kontrollpunkt styrte frå kontoret no?"""
        return bool(cfg.get("base_on") and self.aktiv)

    def status(self, cfg):
        host, port, user, _ = self.target(cfg)
        return {"on": bool(cfg.get("base_on")), "styrt": self.styrt(cfg), "adresse": f"{host}:{port}" if host else "",
                "brukar": user, "eigen_adresse": bool(cfg.get("base_host")), "eiga_innlogging": bool(cfg.get("base_user")),
                "aktiv": self.aktiv, "sist": dict(self.sist), "ko": len(self.ko), "maskin_id": self.mid,
                "maskinnamn": cfg.get("base_maskinnamn") or ""}

    # ---------- HTTP mot Base ----------
    def _req(self, cfg, path, body=None, raw=False, maks=2_000_000):
        host, port, user, pw = self.target(cfg)
        if not host:
            raise Feil("Adressa til SNOWMAN Base manglar (eller caster i NTRIP-oppsettet).")
        url = f"http://{host}:{port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        rq = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
        rq.add_header("User-Agent", f"SNOWMAN/{self.version}")
        if user:
            rq.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
        if data is not None:
            rq.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(rq, timeout=TIMEOUT) as r:
                b = r.read(maks + 1)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise Feil("Base avviste innlogginga. Sjekk brukarnamn og passord (ein brukar med rolla ntrip).")
            if e.code == 404:
                raise Feil("Base svarar ikkje på maskin-API-et. Krev SNOWMAN Base 1.3.0 eller nyare.")
            raise Feil(f"Base svarte med feil {e.code}.")
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            raise Feil(f"Får ikkje kontakt med SNOWMAN Base på {host}:{port} ({getattr(e, 'reason', e)}).")
        if len(b) > maks:
            raise Feil("Svaret frå Base er for stort.")
        if raw:
            return b
        try:
            return json.loads(b.decode("utf-8"))
        except ValueError:
            raise Feil(f"{host}:{port} svarar, men ikkje som SNOWMAN Base. Er det ein vanleg NTRIP-caster?")

    # ---------- henting ----------
    def fetch(self, cfg, apply, force=False):
        """Hentar aktiv anleggspakke. apply(innhald) tek ho i bruk. Returnerer eit svar til skjermen."""
        if not self.lock.acquire(blocking=False):
            raise Feil("Hentar alt frå Base – vent litt.")
        try:
            return self._fetch(cfg, apply, force)
        except Feil as e:
            self.sist = {"t": time.time(), "ok": False, "melding": str(e)}
            raise
        finally:
            self.lock.release()

    def _fetch(self, cfg, apply, force):
        info = self._req(cfg, "/api/v1/info")
        if "anleggspakke-format-1" not in (info.get("funksjonar") or []):
            raise Feil(f"SNOWMAN Base {info.get('versjon', '?')} er for gammal. Oppdater Base til 1.3.0 eller nyare.")
        sendt = self._send_queue(cfg)
        r = self._req(cfg, "/api/v1/anleggspakke")
        pk = r.get("pakke")
        if not pk:
            self._heartbeat(cfg)
            msg = "Kontoret har ikkje lagt ut noka anleggspakke enno."
            self.sist = {"t": time.time(), "ok": True, "melding": msg}
            return {"ok": True, "ny": False, "melding": msg, "sendt": sendt}
        if not force and self.aktiv and self.aktiv.get("sha256") == pk.get("sha256"):
            self._heartbeat(cfg)
            msg = f"Har alt nyaste anleggspakke (v{pk['versjon']})."
            self.sist = {"t": time.time(), "ok": True, "melding": msg}
            return {"ok": True, "ny": False, "melding": msg, "sendt": sendt}
        data = self._req(cfg, f"/api/v1/anleggspakke/fil?versjon={int(pk['versjon'])}", raw=True, maks=MAKS_PAKKE)
        if hashlib.sha256(data).hexdigest() != pk.get("sha256"):
            raise Feil("Anleggspakka kom ikkje heil fram (sha256 stemmer ikkje). Prøv igjen.")
        m, innhald = les_pakke(data)
        if m.get("snowman_min") and vtuple(self.version) < vtuple(m["snowman_min"]):
            raise Feil(f"Anleggspakka krev SNOWMAN {m['snowman_min']} eller nyare (denne er {self.version}).")
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / f"anleggspakke-v{int(pk['versjon'])}.zip").write_bytes(data)
        for gammal in sorted(self.dir.glob("anleggspakke-v*.zip"), key=lambda p: p.stat().st_mtime)[:-3]:
            gammal.unlink(missing_ok=True)                 # tek vare på dei tre siste
        godkjende = apply(innhald)
        tal = {}                                           # berre det som var med i pakka (det som manglar, er uendra)
        if "trasear.json" in innhald:
            tal["trasear"] = sum(1 for t in innhald["trasear.json"] if t.get("kind", "trase") == "trase")
            tal["forbodne_omrade"] = sum(1 for t in innhald["trasear.json"] if t.get("kind") == "forbode")
        if "objekt.json" in innhald:
            tal["hindringar"] = len(innhald["objekt.json"])
        if "kontrollpunkt.json" in innhald:
            tal["kontrollpunkt"] = len(innhald["kontrollpunkt.json"])
        self.aktiv = {"versjon": int(pk["versjon"]), "sha256": pk["sha256"], "henta": time.strftime("%Y-%m-%d %H:%M"),
                      "anlegg": str(m.get("anlegg") or "")[:80], "laga": str(m.get("laga") or "")[:40],
                      "laga_av": str(m.get("laga_av") or "")[:40], "merknad": str(pk.get("merknad") or "")[:200],
                      "filer": sorted(innhald), "tal": tal}
        self._write("aktiv.json", self.aktiv)
        self._heartbeat(cfg)
        msg = f"Anleggspakke v{self.aktiv['versjon']} er teken i bruk."
        if godkjende:
            msg += f" {godkjende} lokal(e) hindring(ar) er no godkjende av kontoret."
        self.sist = {"t": time.time(), "ok": True, "melding": msg}
        self.log(f"Base: anleggspakke v{self.aktiv['versjon']} teken i bruk ({', '.join(f'{v} {k}' for k, v in tal.items())})")
        return {"ok": True, "ny": True, "melding": msg, "aktiv": self.aktiv, "sendt": sendt}

    def backup(self, files):
        """Det som låg i maskina før pakka vart teken i bruk (blir skrive over ved kvar nye pakke)."""
        d = self.dir / "forrige"
        d.mkdir(parents=True, exist_ok=True)
        for f in files:
            f = Path(f)
            if f.exists():
                shutil.copy2(f, d / f.name)

    def _heartbeat(self, cfg):
        try:
            self._req(cfg, "/api/v1/maskin", {"id": self.mid, "namn": cfg.get("base_maskinnamn") or self.mid,
                                              "versjon": self.version, "pakke": (self.aktiv or {}).get("versjon")})
        except Feil:
            pass

    # ---------- forslag til kontoret ----------
    def forslag(self, cfg, f):
        """Sender eit forslag (t.d. ny hindring). Kjem det ikkje fram, blir det lagt i kø."""
        f = dict(f, maskin=self.mid, t=time.strftime("%Y-%m-%d %H:%M"))
        try:
            self._req(cfg, "/api/v1/forslag", f)
            return True
        except Feil:
            self.ko.append(f)
            self.ko = self.ko[-200:]
            self._write("forslag-ko.json", self.ko)
            return False

    def _send_queue(self, cfg):
        n = 0
        while self.ko:
            try:
                self._req(cfg, "/api/v1/forslag", self.ko[0])
            except Feil:
                break
            self.ko.pop(0)
            n += 1
        if n:
            self._write("forslag-ko.json", self.ko)
        return n
