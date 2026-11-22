# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Kopling til SNOWMAN Kontor – anleggspakke frå kontoret (v1.6.136, v1.6.137: Kontor i staden for Base).

Avgjerd 2026-11-22: SNOWMAN Base (Pi ved antenna) har berre med korreksjonane (NTRIP) å gjere. Anleggsdata kjem frå
SNOWMAN Kontor, eit eige program på ein PC på anlegget (port 8790). Maskina når Kontor når ho er på nettet på
anlegget (wifi i garasjen) – Kontor er aldri ope mot internett.

Valfri: SNOWMAN snødjupne fungerer fullt ut utan Kontor (kap. 19). Når koplinga er på:
- «Hent frå Kontor» hentar den aktive anleggspakka (trasear, forbodne område, hindringar, kontrollpunkt).
- Pakka blir kontrollert (manifest, sha256, innhald) og lagra lokalt i data/anleggspakke/. Er Kontor borte (PC-en
  av, eller maskina ute i bakken), gjeld siste pakke. Det som var i maskina før, blir teke vare på i
  data/anleggspakke/forrige/.
- Trasear, forbodne område og kontrollpunkt er då styrte frå kontoret. Føraren kan berre sende forslag.
  Ei ny hindring blir lagd inn lokalt med éin gong (varsel med det same) og sendt til kontoret som forslag
  (avgjerd 1, 2026-11-20). Forslag som ikkje kom fram, ligg i kø og blir sende ved neste henting.
- Terreng blir ikkje sendt i formatversjon 1 (avgjerd 2).

SNOWMAN sender aldri noko til GNSS-mottakaren – dette er berre nettverk mellom maskina og Kontor.
"""
import base64
import hashlib
import http.client
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
PORT = 8790                           # standardporten til SNOWMAN Kontor


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
            raise Feil("Anleggspakka manglar manifest.json.")
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


class KontorKopling:
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
        """Fast ID for maskina mot Kontor (hjarteslag og forslag). Laga éin gong og lagra i data/maskin-id.txt."""
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
        """(vert, port, brukar, passord) for SNOWMAN Kontor."""
        host = str(cfg.get("kontor_host") or "").strip()
        for pre in ("http://", "https://"):
            if host.lower().startswith(pre):
                host = host[len(pre):]
        host = host.rstrip("/")
        port = int(cfg.get("kontor_port") or PORT)
        if ":" in host and host.rsplit(":", 1)[1].isdigit():
            host, port = host.rsplit(":", 1)[0], int(host.rsplit(":", 1)[1])
        return host, port, cfg.get("kontor_user") or "", cfg.get("kontor_pass") or ""

    def styrt(self, cfg):
        """Er trasear, forbodne område og kontrollpunkt styrte frå kontoret no?"""
        return bool(cfg.get("kontor_on") and self.aktiv)

    def status(self, cfg):
        host, port, user, _ = self.target(cfg)
        return {"on": bool(cfg.get("kontor_on")), "styrt": self.styrt(cfg), "adresse": f"{host}:{port}" if host else "",
                "vert": host, "port": port, "brukar": user, "aktiv": self.aktiv, "sist": dict(self.sist),
                "ko": len(self.ko), "maskin_id": self.mid, "maskinnamn": cfg.get("kontor_maskinnamn") or ""}

    # ---------- HTTP mot Kontor ----------
    def _req(self, cfg, path, body=None, raw=False, maks=2_000_000):
        host, port, user, pw = self.target(cfg)
        if not host:
            raise Feil("Adressa til PC-en med SNOWMAN Kontor manglar (Innst. › Trasear › Kopling til SNOWMAN Kontor).")
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
                raise Feil("Kontor avviste innlogginga. Sjekk brukarnamn og passord (ein brukar med rolla maskin i "
                           "SNOWMAN Kontor › Brukarar).")
            if e.code == 404:
                raise Feil(f"{host}:{port} svarar, men ikkje som SNOWMAN Kontor. Er adressa og porten (8790) rett?")
            raise Feil(f"Kontor svarte med feil {e.code}.")
        except http.client.HTTPException:
            raise Feil(f"{host}:{port} svarar, men ikkje som SNOWMAN Kontor – det ser ut som ein NTRIP-caster "
                       "(SNOWMAN Base). Kontor har eigen port (8790) på PC-en.")
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            raise Feil(f"Får ikkje kontakt med SNOWMAN Kontor på {host}:{port} ({getattr(e, 'reason', e)}). "
                       "Er maskina på wifi på anlegget, og står PC-en med Kontor på?")
        if len(b) > maks:
            raise Feil("Svaret frå Kontor er for stort.")
        if raw:
            return b
        try:
            return json.loads(b.decode("utf-8"))
        except ValueError:
            raise Feil(f"{host}:{port} svarar, men ikkje som SNOWMAN Kontor. Er det SNOWMAN Base eller ein NTRIP-caster? "
                       "Kontor har eigen port (8790) på PC-en.")

    # ---------- henting ----------
    def fetch(self, cfg, apply, force=False):
        """Hentar aktiv anleggspakke. apply(innhald) tek ho i bruk. Returnerer eit svar til skjermen."""
        if not self.lock.acquire(blocking=False):
            raise Feil("Hentar alt frå Kontor – vent litt.")
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
            if info.get("program") == "SNOWMAN Base" or "ntrip-caster" in (info.get("funksjonar") or []):
                raise Feil("Adressa går til SNOWMAN Base. Anleggsdata kjem frå SNOWMAN Kontor på PC-en (port 8790).")
            raise Feil(f"{info.get('program') or 'Programmet'} {info.get('versjon', '?')} kan ikkje sende anleggspakke.")
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
        self.log(f"Kontor: anleggspakke v{self.aktiv['versjon']} teken i bruk ({', '.join(f'{v} {k}' for k, v in tal.items())})")
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
            self._req(cfg, "/api/v1/maskin", {"id": self.mid, "namn": cfg.get("kontor_maskinnamn") or self.mid,
                                              "versjon": self.version, "pakke": (self.aktiv or {}).get("versjon")})
        except Feil:
            pass

    # ---------- forslag til kontoret ----------
    def forslag(self, cfg, f):
        """Sender eit forslag (t.d. ny hindring) til kontoret. Kjem det ikkje fram, blir det lagt i kø."""
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
