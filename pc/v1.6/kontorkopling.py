# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Kopling til SNOWMAN Office – anleggspakke frå kontoret (v1.6.136, v1.6.137: Office i staden for Base).

Avgjerd 2026-11-22: SNOWMAN Base (Pi ved antenna) har berre med korreksjonane (NTRIP) å gjere. Anleggsdata kjem frå
SNOWMAN Office, eit eige program på ein PC på anlegget (port 8790). Maskina når Office når ho er på nettet på
anlegget (wifi i garasjen) – Office er aldri ope mot internett.

Valfri: SNOWMAN Snowdeep fungerer fullt ut utan Office (kap. 19). Når koplinga er på:
- «Hent frå Office» hentar den aktive anleggspakka (trasear, forbodne område, hindringar, kontrollpunkt).
- Pakka blir kontrollert (manifest, sha256, innhald) og lagra lokalt i data/anleggspakke/. Er Office borte (PC-en
  av, eller maskina ute i bakken), gjeld siste pakke. Det som var i maskina før, blir teke vare på i
  data/anleggspakke/forrige/.
- Trasear, forbodne område og kontrollpunkt er då styrte frå kontoret. Føraren kan berre sende forslag.
  Ei ny hindring blir lagd inn lokalt med éin gong (varsel med det same) og sendt til kontoret som forslag
  (avgjerd 1, 2026-11-20). Forslag som ikkje kom fram, ligg i kø og blir sende ved neste henting.
- Terreng (v1.6.138, eigaren 2026-11-22): terrenglaga frå kontoret blir lasta ned med pakka (på wifi) og lagde
  til side. Føraren trykkjer TA I BRUK NYTT TERRENG når prepareringa er stoppa – då blir laga installerte i
  terrengbiblioteket, og lokale lag blir slått AV (ikkje sletta). Det gamle blir teke vare på (forrige-terreng/).

SNOWMAN sender aldri noko til GNSS-mottakaren – dette er berre nettverk mellom maskina og Office.
"""
import base64
import hashlib
import http.client
import io
import json
import os
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
MAKS_PAKKE = 4000 * 1024 * 1024       # med terreng kan pakka vere stor (blir lasta ned til disk, på wifi)
TIMEOUT = 20
PORT = 8790                           # standardporten til SNOWMAN Office (på anlegget)
PORT_UTE = 8791                       # maskinporten til Office – den som kan opnast i ruteren (ute i bakken)
MAKS_UTE = 50 * 1024 * 1024           # større pakkar (terreng) blir berre henta på wifi på anlegget


class Feil(Exception):
    pass


class _Nett(Feil):
    """Ingen kontakt (nettverk) – då blir neste veg til Office prøvd."""


def vtuple(v):
    out = []
    for x in str(v or "0").split("."):
        try:
            out.append(int("".join(c for c in x if c.isdigit()) or 0))
        except ValueError:
            out.append(0)
    return tuple(out)


def les_pakke(src, terreng_til=None):
    """Kontrollerer ei anleggspakke (bytes eller sti) og returnerer (manifest, {fil: innhald}, [terrenglag]).
    Terrenglaga (terreng/<id>/meta.json + grid.npy) blir pakka ut til mappa terreng_til (om gitt). Kastar Feil."""
    try:
        z = zipfile.ZipFile(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src)
    except (zipfile.BadZipFile, OSError):
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
        innhald, lag = {}, {}
        for n, h in filer.items():
            if n not in namn:
                raise Feil(f"{n} manglar i anleggspakka.")
            if n.startswith("terreng/"):
                parts = n.split("/")
                if len(parts) != 3 or parts[2] not in ("meta.json", "grid.npy") or \
                        not all(c.isalnum() or c in "-_" for c in parts[1]):
                    raise Feil(f"Ukjend terrengfil i anleggspakka: {n[:80]}")
                hh = hashlib.sha256()
                dst = None
                if terreng_til is not None:
                    d = Path(terreng_til) / parts[1]
                    d.mkdir(parents=True, exist_ok=True)
                    dst = open(d / parts[2], "wb")
                try:
                    with z.open(namn[n]) as f:
                        for chunk in iter(lambda: f.read(1 << 20), b""):
                            hh.update(chunk)
                            if dst:
                                dst.write(chunk)
                finally:
                    if dst:
                        dst.close()
                if hh.hexdigest() != str(h).lower():
                    raise Feil(f"{n} i anleggspakka er skadd (sha256 stemmer ikkje).")
                if parts[2] == "meta.json":
                    try:
                        mm = json.loads(z.read(n).decode("utf-8"))
                    except ValueError:
                        raise Feil(f"{n} er ikkje gyldig JSON.")
                    lag.setdefault(parts[1], {})["meta"] = mm
                else:
                    lag.setdefault(parts[1], {})["grid"] = True
                continue
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
        terreng = []
        for lid, x in lag.items():
            if "meta" not in x or "grid" not in x:
                raise Feil(f"Terrenglaget {lid} i anleggspakka manglar meta.json eller grid.npy.")
            terreng.append({"id": lid, "name": str(x["meta"].get("name") or lid)[:80], "type": x["meta"].get("type")})
        if not innhald and not terreng:
            raise Feil("Anleggspakka har verken trasear, hindringar, kontrollpunkt eller terreng.")
        return m, innhald, terreng


def lag_pakke(path, anlegg="", laga_av="", trasear=None, objekt=None, kontrollpunkt=None, terreng=None, snowman_min=""):
    """Lagar ei anleggspakke (formatversjon 1) – brukt av kontormodus («Publiser til maskinene»).
    terreng: [(meta, sti til grid.npy)] frå terrengbiblioteket."""
    filer = {}
    data = {}
    for n, key, val in (("trasear.json", "trasear", trasear), ("objekt.json", "objekt", objekt),
                        ("kontrollpunkt.json", "points", kontrollpunkt)):
        if val is not None:
            data[n] = json.dumps({key: val}, ensure_ascii=False, indent=1).encode("utf-8")
            filer[n] = hashlib.sha256(data[n]).hexdigest()
    tlist = []
    for meta, grid in terreng or []:
        meta = {k: v for k, v in meta.items() if k not in ("overlap", "warnings", "versions", "fraKontor", "avAvKontoret")}
        mb = json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8")
        data[f"terreng/{meta['id']}/meta.json"] = mb
        filer[f"terreng/{meta['id']}/meta.json"] = hashlib.sha256(mb).hexdigest()
        h = hashlib.sha256()
        with open(grid, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        filer[f"terreng/{meta['id']}/grid.npy"] = h.hexdigest()
        tlist.append((f"terreng/{meta['id']}/grid.npy", grid))
    m = {"format": FORMAT, "formatversjon": FORMATVERSJON, "anlegg": anlegg, "laga": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
         "laga_av": laga_av, "filer": filer}
    if snowman_min:
        m["snowman_min"] = snowman_min
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.writestr("manifest.json", json.dumps(m, ensure_ascii=False, indent=1))
        for n, b in data.items():
            z.writestr(n, b)
        for n, f in tlist:
            z.write(f, n)
    return path


class KontorKopling:
    def __init__(self, data_dir, version, log=None):
        self.dir = Path(data_dir) / "anleggspakke"
        self.version = version
        self.log = log or (lambda s: None)
        self.lock = threading.Lock()
        self.sist = {"t": None, "ok": None, "melding": ""}
        self.aktiv = self._read("aktiv.json") or None
        self.ko = self._read("forslag-ko.json") or []
        self.terreng = self._read("terreng.json") or {}
        self.via = None                                     # «lokal» (wifi) eller «ute» – kvar Office sist svarte
        self._pref = (None, 0.0)                            # (vegen som sist verka, tid)
        self.live_st = {"t": None, "ok": None, "feil": ""}     # {"i_bruk": versjon, "ventar": {versjon, lag, mappe}}
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
        """Fast ID for maskina mot Office (hjarteslag og forslag). Laga éin gong og lagra i data/maskin-id.txt."""
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
        """(vert, port, brukar, passord) for SNOWMAN Office."""
        host = str(cfg.get("kontor_host") or "").strip()
        for pre in ("http://", "https://"):
            if host.lower().startswith(pre):
                host = host[len(pre):]
        host = host.rstrip("/")
        port = int(cfg.get("kontor_port") or PORT)
        if ":" in host and host.rsplit(":", 1)[1].isdigit():
            host, port = host.rsplit(":", 1)[0], int(host.rsplit(":", 1)[1])
        return host, port, cfg.get("kontor_user") or "", cfg.get("kontor_pass") or ""

    @staticmethod
    def targets(cfg):
        """Kvar Office kan nåast: på anlegget (wifi) og ute i bakken (maskinporten via ruteren, valfri)."""
        out = []
        h, p, _, _ = KontorKopling.target(cfg)
        if h:
            out.append((h, p, "lokal"))
        ute = str(cfg.get("kontor_host_ute") or "").strip()
        for pre in ("http://", "https://"):
            if ute.lower().startswith(pre):
                ute = ute[len(pre):]
        ute = ute.rstrip("/")
        if ute:
            up = int(cfg.get("kontor_port_ute") or PORT_UTE)
            if ":" in ute and ute.rsplit(":", 1)[1].isdigit():
                ute, up = ute.rsplit(":", 1)[0], int(ute.rsplit(":", 1)[1])
            out.append((ute, up, "ute"))
        return out

    def styrt(self, cfg):
        """Er trasear, forbodne område og kontrollpunkt styrte frå kontoret no?"""
        return bool(cfg.get("kontor_on") and self.aktiv)

    def status(self, cfg):
        host, port, user, _ = self.target(cfg)
        return {"on": bool(cfg.get("kontor_on")), "styrt": self.styrt(cfg), "adresse": f"{host}:{port}" if host else "",
                "vert": host, "port": port, "brukar": user, "aktiv": self.aktiv, "sist": dict(self.sist),
                "ko": len(self.ko), "maskin_id": self.mid, "maskinnamn": cfg.get("kontor_maskinnamn") or "",
                "ute": next((f"{h}:{p}" for h, p, k in self.targets(cfg) if k == "ute"), ""),
                "via": self.via, "sanntid": dict(self.live_st), "sanntid_on": bool(cfg.get("kontor_sanntid", True)),
                "vert_ute": (cfg.get("kontor_host_ute") or "").strip(), "port_ute": int(cfg.get("kontor_port_ute") or PORT_UTE),
                "terreng": {"i_bruk": self.terreng.get("i_bruk"), "teke_i_bruk": self.terreng.get("teke_i_bruk"),
                            "ventar": {k: v for k, v in (self.terreng.get("ventar") or {}).items() if k != "mappe"}
                            or None, "resultat": self.terreng.get("resultat")}}

    # ---------- HTTP mot Office ----------
    def _req(self, cfg, path, body=None, raw=False, maks=2_000_000, til=None, timeout=None):
        """Prøver Office på anlegget først, så ute (maskinporten). Den vegen som sist verka, blir prøvd først i 2 min."""
        tg = self.targets(cfg)
        if not tg:
            raise Feil("Adressa til PC-en med SNOWMAN Office manglar (Innst. › Trasear › Kopling til SNOWMAN Office).")
        pv, pt = self._pref
        if pv and time.time() - pt < 120:
            tg.sort(key=lambda x: x[2] != pv)
        last = None
        for i, (host, port, kind) in enumerate(tg):
            try:
                r = self._req1(cfg, host, port, path, body, raw, maks, til,
                               timeout or (TIMEOUT if i == len(tg) - 1 else 4))
                self.via, self._pref = kind, (kind, time.time())
                return r
            except _Nett as e:
                last = e
        raise Feil(str(last) if len(tg) == 1 else
                   "Får ikkje kontakt med SNOWMAN Office – verken på anlegget eller ute (" + str(last) + ")")

    def _req1(self, cfg, host, port, path, body, raw, maks, til, timeout):
        _, _, user, pw = self.target(cfg)
        url = f"http://{host}:{port}{path}"
        data = json.dumps(body).encode() if body is not None else None
        rq = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
        rq.add_header("User-Agent", f"SNOWMAN/{self.version}")
        if user:
            rq.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
        if data is not None:
            rq.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(rq, timeout=timeout) as r:
                if til is not None:                    # stor fil: rett til disk, med sha256 undervegs
                    h, n = hashlib.sha256(), 0
                    with open(til, "wb") as f:
                        for chunk in iter(lambda: r.read(1 << 20), b""):
                            n += len(chunk)
                            if n > maks:
                                raise Feil("Anleggspakka er for stor.")
                            h.update(chunk)
                            f.write(chunk)
                    return h.hexdigest()
                b = r.read(maks + 1)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise Feil("Office avviste innlogginga. Sjekk brukarnamn og passord (ein brukar med rolla maskin i "
                           "SNOWMAN Office › Brukarar).")
            if e.code == 404:
                raise Feil(f"{host}:{port} svarar, men ikkje som SNOWMAN Office. Er adressa og porten (8790) rett?")
            try:                                        # Office forklarer feilen i svaret ({"feil": …})
                msg = json.loads(e.read(20_000).decode("utf-8")).get("feil")
            except Exception:
                msg = None
            raise Feil(f"Office: {msg}" if msg else f"Office svarte med feil {e.code}.")
        except http.client.HTTPException:
            raise Feil(f"{host}:{port} svarar, men ikkje som SNOWMAN Office – det ser ut som ein NTRIP-caster "
                       "(SNOWMAN Base). Office har eigen port (8790) på PC-en.")
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            raise _Nett(f"Får ikkje kontakt med SNOWMAN Office på {host}:{port} ({getattr(e, 'reason', e)}). "
                        "Er maskina på wifi på anlegget, og står PC-en med Office på?")
        if len(b) > maks:
            raise Feil("Svaret frå Office er for stort.")
        if raw:
            return b
        try:
            return json.loads(b.decode("utf-8"))
        except ValueError:
            raise Feil(f"{host}:{port} svarar, men ikkje som SNOWMAN Office. Er det SNOWMAN Base eller ein NTRIP-caster? "
                       "Office har eigen port (8790) på PC-en.")

    # ---------- henting ----------
    def fetch(self, cfg, apply, force=False):
        """Hentar aktiv anleggspakke. apply(innhald) tek ho i bruk. Returnerer eit svar til skjermen."""
        if not self.lock.acquire(blocking=False):
            raise Feil("Hentar alt frå Office – vent litt.")
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
                raise Feil("Adressa går til SNOWMAN Base. Anleggsdata kjem frå SNOWMAN Office på PC-en (port 8790).")
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
        v = int(pk["versjon"])
        if self.via == "ute" and int(pk.get("storleik") or 0) > MAKS_UTE:
            msg = (f"Anleggspakke v{v} er stor ({int(pk['storleik']) // 1_000_000} MB, truleg terreng). Ho blir henta når "
                   "maskina er på wifi på anlegget.")
            self.sist = {"t": time.time(), "ok": True, "melding": msg}
            return {"ok": True, "ny": False, "melding": msg, "sendt": sendt}
        self.dir.mkdir(parents=True, exist_ok=True)
        zp = self.dir / f"anleggspakke-v{v}.zip"
        tmp = self.dir / f"anleggspakke-v{v}.zip.del"
        sha = self._req(cfg, f"/api/v1/anleggspakke/fil?versjon={v}", maks=MAKS_PAKKE, til=tmp)
        if sha != pk.get("sha256"):
            tmp.unlink(missing_ok=True)
            raise Feil("Anleggspakka kom ikkje heil fram (sha256 stemmer ikkje). Prøv igjen.")
        stage = self.dir / f"terreng-v{v}"
        shutil.rmtree(stage, ignore_errors=True)
        try:
            m, innhald, terreng = les_pakke(tmp, stage)
        except Feil:
            tmp.unlink(missing_ok=True)
            shutil.rmtree(stage, ignore_errors=True)
            raise
        if m.get("snowman_min") and vtuple(self.version) < vtuple(m["snowman_min"]):
            tmp.unlink(missing_ok=True)
            shutil.rmtree(stage, ignore_errors=True)
            raise Feil(f"Anleggspakka krev SNOWMAN {m['snowman_min']} eller nyare (denne er {self.version}).")
        os.replace(tmp, zp)
        for gammal in sorted(self.dir.glob("anleggspakke-v*.zip"), key=lambda p: p.stat().st_mtime)[:-3]:
            gammal.unlink(missing_ok=True)                 # tek vare på dei tre siste
        godkjende = apply(innhald) if innhald else 0
        tal = {}                                           # berre det som var med i pakka (det som manglar, er uendra)
        if "trasear.json" in innhald:
            tal["trasear"] = sum(1 for t in innhald["trasear.json"] if t.get("kind", "trase") == "trase")
            tal["forbodne_omrade"] = sum(1 for t in innhald["trasear.json"] if t.get("kind") == "forbode")
        if "objekt.json" in innhald:
            tal["hindringar"] = len(innhald["objekt.json"])
        if "kontrollpunkt.json" in innhald:
            tal["kontrollpunkt"] = len(innhald["kontrollpunkt.json"])
        if terreng:
            tal["terrenglag"] = len(terreng)
            old = (self.terreng or {}).get("ventar")
            if old and old.get("mappe") and Path(old["mappe"]) != stage:
                shutil.rmtree(old["mappe"], ignore_errors=True)
            self.terreng = dict(self.terreng or {}, ventar={"versjon": v, "lag": terreng, "mappe": str(stage),
                                                            "henta": time.strftime("%Y-%m-%d %H:%M")})
            self._write("terreng.json", self.terreng)
        else:
            shutil.rmtree(stage, ignore_errors=True)
        self.aktiv = {"versjon": int(pk["versjon"]), "sha256": pk["sha256"], "henta": time.strftime("%Y-%m-%d %H:%M"),
                      "anlegg": str(m.get("anlegg") or "")[:80], "laga": str(m.get("laga") or "")[:40],
                      "laga_av": str(m.get("laga_av") or "")[:40], "merknad": str(pk.get("merknad") or "")[:200],
                      "filer": sorted(innhald), "tal": tal}
        self._write("aktiv.json", self.aktiv)
        self._heartbeat(cfg)
        msg = f"Anleggspakke v{self.aktiv['versjon']} er teken i bruk."
        if terreng:
            msg += (f" Nytt terreng frå kontoret ({len(terreng)} lag) er lasta ned – trykk TA I BRUK NYTT TERRENG "
                    "når prepareringa er stoppa.")
        if godkjende:
            msg += f" {godkjende} lokal(e) hindring(ar) er no godkjende av kontoret."
        self.sist = {"t": time.time(), "ok": True, "melding": msg}
        self.log(f"Office: anleggspakke v{self.aktiv['versjon']} teken i bruk ({', '.join(f'{v} {k}' for k, v in tal.items())})")
        return {"ok": True, "ny": True, "melding": msg, "aktiv": self.aktiv, "sendt": sendt}

    def terreng_ta_i_bruk(self, install):
        """Føraren har trykt TA I BRUK NYTT TERRENG (berre når prepareringa er stoppa – sjekka av kallaren).
        install(mappe, backup_mappe) installerer laga i terrengbiblioteket og returnerer eit samandrag."""
        ventar = (self.terreng or {}).get("ventar")
        if not ventar or not Path(ventar["mappe"]).is_dir():
            raise Feil("Det ventar ikkje noko nytt terreng frå kontoret.")
        backup = self.dir / "forrige-terreng" / time.strftime("%Y%m%d-%H%M%S")
        res = install(ventar["mappe"], backup)
        shutil.rmtree(ventar["mappe"], ignore_errors=True)
        for gammal in sorted((self.dir / "forrige-terreng").glob("*"))[:-3]:
            shutil.rmtree(gammal, ignore_errors=True)      # tek vare på dei tre siste
        self.terreng = {"i_bruk": ventar["versjon"], "teke_i_bruk": time.strftime("%Y-%m-%d %H:%M"), "resultat": res,
                        "lag": ventar["lag"]}
        self._write("terreng.json", self.terreng)
        self.log(f"Office: terreng frå anleggspakke v{ventar['versjon']} teke i bruk ({res})")
        return self.terreng

    # ---------- sanntid (2026-11-22) ----------
    def live(self, cfg, status, punkt=None):
        """Posisjon, snødjupne og status til Office (kvart 10. s), og målingar for deling. Feil blir berre noterte."""
        try:
            self._req(cfg, "/api/v1/maskin", dict(status, id=self.mid, namn=cfg.get("kontor_maskinnamn") or self.mid,
                                                   versjon=self.version, pakke=(self.aktiv or {}).get("versjon"),
                                                   terreng=self.terreng.get("i_bruk")), timeout=6)
            if punkt:
                self._req(cfg, "/api/v1/maalingar", {"maskin": self.mid, "punkt": punkt}, timeout=10)
            self.live_st = {"t": time.time(), "ok": True, "feil": "", "via": self.via}
            if self.ko:
                self._send_queue(cfg)
            return True
        except Feil as e:
            self.live_st = {"t": time.time(), "ok": False, "feil": str(e)[:200], "via": None}
            return False

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
                                              "versjon": self.version, "pakke": (self.aktiv or {}).get("versjon"),
                                              "terreng": self.terreng.get("i_bruk")})
        except Feil:
            pass

    # ---------- forslag til kontoret ----------
    def forslag(self, cfg, f):
        """Sender eit forslag (t.d. ny hindring) til kontoret. Kjem det ikkje fram, blir det lagt i kø."""
        # namnet frå innstillingane (t.d. «PB600_1») – maskin-ID-en (PC-namn) seier lite på kontoret
        f = dict(f, maskin=(cfg.get("kontor_maskinnamn") or "").strip() or self.mid, t=time.strftime("%Y-%m-%d %H:%M"))
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
