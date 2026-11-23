# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Nettsider og API i SNOWMAN Office (standard port 8790, berre på nettet på anlegget).

Sider:   /  og  /kontor/    kontorsida (oversikt, anleggspakke, forslag, forbetringar, AI, brukarar, system)

API v1 (JSON). Innlogging med brukarnamn og passord:
  Maskin-API:  «Authorization: Basic» med ein brukar med rolla «maskin»
  Office-API:  økt frå POST /api/v1/logg-inn («Authorization: Bearer <økt>»), eller Basic med ein kontor-brukar
  Ope:        GET  /api/v1/info                     versjon, API-versjon, funksjonar, minste SNOWMAN-versjon
              GET  /api/v1/oppsett                  {treng_admin, lokal}
              POST /api/v1/oppsett                  {brukar, passord, maskin_brukar?, maskin_passord?} – berre når ingen
                                                    administrator finst, og berre frå det lokale nettet
              POST /api/v1/logg-inn {brukar, passord} → {okt}   ·   POST /api/v1/logg-ut
  Maskin:     POST /api/v1/maskin                   hjarteslag {id, namn, versjon, pakke, lat, lon, fix, fixdel}
              POST /api/v1/maalingar                {maskin, punkt: [{t, lat, lon, h, djupne, fix, kalibrert}]}
              GET  /api/v1/maalingar?etter=&utan=   delte målingar siste 12 t (berre nye sidan «etter»)
              GET  /api/v1/maskiner                 alle maskiner (posisjon, sist sett)
              GET  /api/v1/anleggspakke             aktiv versjon {versjon, sha256, storleik}
              GET  /api/v1/anleggspakke/fil         zip-fila (?versjon= for ein bestemt)
              POST /api/v1/forslag                  {maskin, type: hindring|merknad|program|anna, tekst, lat, lon}
  Office:     GET  /api/status                      status for Office (og siste status frå SNOWMAN Base)
              POST /api/v1/anleggspakke             ny versjon (zip i body, X-Merknad), blir aktiv
              GET  /api/v1/anleggspakke/versjonar  ·  POST /api/v1/anleggspakke/aktiv {versjon}
              GET  /api/v1/forslag  ·  POST /api/v1/forslag/svar {id, status, svar}
              POST /api/v1/maskin/fjern {id}
              GET  /api/v1/forbetringar  ·  GET /api/v1/forbetringar.md  ·  POST /api/v1/forbetringar/status
              POST /api/v1/forbetringar/analyser
              GET  /api/v1/ai  ·  POST /api/v1/ai/innstillingar  ·  GET /api/v1/ai/forehandsvis
              POST /api/v1/ai/analyser  ·  POST /api/v1/ai/sporsmal {tekst}
              GET  /api/v1/ai/lokal  ·  POST /api/v1/ai/lokal/hent {modell}  ·  POST /api/v1/ai/lokal/ta-i-bruk {modell}
  Maskin:     POST /api/v1/ai/maskin {maskin, tekst, kontekst}  (SNOWMAN AI for førarane, også på maskinporten)
              GET  /api/v1/base  ·  POST /api/v1/base {adresse, brukar, passord}   SNOWMAN Base (berre lesing)
              GET  /api/v1/brukarar  ·  POST /api/v1/brukar {namn, passord?, roller?}  ·  POST /api/v1/brukar/fjern
              POST /api/v1/oppdatering/sjekk  ·  POST /api/v1/oppdater
              GET  /api/v1/hendingar  ·  GET /api/v1/konfig
  Maskinport (standard 8791 – den einaste porten som kan opnast i ruteren): berre maskin-API-et over, berre rolla maskin.
Brot i API-et gir ny API-versjon (/api/v2/…); v1 blir verande så lenge maskiner brukar han.
"""
import base64
import http.server
import json
import mimetypes
import os
import secrets
import socket
import socketserver
import threading
import time
import urllib.parse
from pathlib import Path

import ai as aimod
import anleggspakke
import forbetring
import vern as vernmod
from konfig import API_VERSION, FUNKSJONAR, SNOWMAN_MIN, VERSION, valid_name, valid_pw

HERE = Path(__file__).resolve().parent
PAGE = HERE / "web" / "kontor.html"
STATIC = {"/": PAGE, "/kontor": PAGE, "/kontor/": PAGE}


class Handler(http.server.BaseHTTPRequestHandler):
    k = None
    server_version = f"SNOWMAN-Office/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    # ---------- svar ----------
    def send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path, ctype=None, name=None):
        path = Path(path)
        if not path.is_file():
            return self.send_json({"ok": False, "feil": "fann ikkje fila"}, 404)
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", ctype or mimetypes.guess_type(str(path))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-cache")
        if name:
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.end_headers()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def send_text(self, text, ctype="text/plain; charset=utf-8", name=None):
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if name:
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.end_headers()
        self.wfile.write(data)

    # ---------- innlogging ----------
    def ip(self):
        return self.client_address[0]

    def key(self):
        a = self.headers.get("Authorization", "")
        return a[7:].strip() if a.lower().startswith("bearer ") else ""

    def basic(self):
        a = self.headers.get("Authorization", "")
        if a.lower().startswith("basic "):
            try:
                u, _, p = base64.b64decode(a[6:].strip()).decode("utf-8", "replace").partition(":")
                return u, p
            except Exception:
                pass
        return None, None

    def _user(self, role):
        """Brukarnamnet når innlogginga gjeld rolla, elles None. Feil passord blir talt (sperre)."""
        k = self.k
        lok = self.headers.get("X-Lokal-Nokkel", "")
        if lok and k.lokal_nokkel and self.ip() in ("127.0.0.1", "::1") and \
                secrets.compare_digest(lok, k.lokal_nokkel):
            return "kontormodus"                    # SNOWMAN Snowdeep i kontormodus på same PC
        tok = self.key()
        if tok:
            name = k.vern.session_user(tok)
            u = k.cfg.find_user(name) if name else None
            if u and "kontor" in u.get("roller", []):
                return u["namn"]                    # kontoret har tilgang til alt
            return None
        name, pw = self.basic()
        if name is None:
            return None
        if k.vern.is_blocked(self.ip()):
            return None
        u = k.cfg.check_user(name, pw)
        if u is None:
            k.vern.failed(self.ip(), "nettside/API")
            return None
        k.vern.ok(self.ip())
        roles = u.get("roller", [])
        return u["namn"] if (role in roles or "kontor" in roles) else None

    def is_office(self):
        return self._user("kontor") is not None

    def is_machine(self):
        return self._user("maskin") is not None

    def deny(self):
        time.sleep(1)                               # bremsar gjetting av passord
        if self.k.vern.is_blocked(self.ip()):
            return self.send_json({"ok": False, "feil": "For mange feil innloggingar – prøv att om litt"}, 429)
        self.send_json({"ok": False, "feil": "Manglar innlogging, eller feil brukarnamn/passord"}, 401)

    def body_json(self, limit=20_000_000):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("for stor førespurnad")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    # ---------- GET ----------
    def do_GET(self):
        k = self.k
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        p = u.path
        try:
            if p in STATIC:
                return self.send_file(STATIC[p], "text/html; charset=utf-8")
            if p.startswith("/vendor/"):
                f = (HERE / "vendor" / p[8:]).resolve()
                if HERE / "vendor" in f.parents:
                    return self.send_file(f)
                return self.send_json({"ok": False}, 404)
            if p == "/api/v1/info":
                return self.send_json({"ok": True, "program": "SNOWMAN Office", "namn": k.cfg["namn"],
                                       "anlegg": k.cfg["anlegg"], "versjon": VERSION, "api": API_VERSION,
                                       "snowman_min": SNOWMAN_MIN, "funksjonar": FUNKSJONAR})
            if p == "/api/v1/oppsett":
                return self.send_json({"ok": True, "treng_admin": not k.cfg.has_admin(),
                                       "lokal": vernmod.is_local(self.ip())})
            if p == "/api/status":
                if not self.is_office():
                    return self.deny()
                return self.send_json(k.status())
            if p.startswith("/api/v1/"):
                return self.api_get(p[8:], q)
            return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            k.events.add(f"API-feil {p}: {e}", "feil")
            self.send_json({"ok": False, "feil": str(e)}, 500)

    def api_get(self, p, q):
        k, st = self.k, self.k.store
        if p in ("maalingar", "maskiner", "anleggspakke", "anleggspakke/fil"):
            if not self.is_machine():
                return self.deny()
            if p == "maalingar":
                rows, last = st.measurements(int(q.get("etter") or 0), k.cfg["deling"].get("timar", 12),
                                             q.get("utan"), int(q.get("maks") or 5000))
                return self.send_json({"ok": True, "maalingar": rows, "siste": last,
                                       "timar": k.cfg["deling"].get("timar", 12)})
            if p == "maskiner":
                return self.send_json({"ok": True, "maskiner": st.machines()})
            if p == "anleggspakke":
                return self.send_json({"ok": True, "pakke": st.package()})
            pk = st.package(q.get("versjon")) if q.get("versjon") else st.package()
            if not pk:
                return self.send_json({"ok": False, "feil": "ingen anleggspakke"}, 404)
            return self.send_file(st.pkgdir / pk["fil"], "application/zip", pk["fil"])
        if not self.is_office():
            return self.deny()
        if p == "anleggspakke/versjonar":
            return self.send_json({"ok": True, "versjonar": st.packages()})
        if p == "forslag":
            return self.send_json({"ok": True, "forslag": st.proposals(q.get("status"))})
        if p == "forbetringar":
            return self.send_json({"ok": True, "forbetringar": st.improvements(q.get("alle") == "1"),
                                   "kategoriar": forbetring.CATEGORIES, "dagar": st.days(30)})
        if p == "forbetringar.md":
            return self.send_text(forbetring.export_markdown(st, q.get("alle") == "1"), "text/markdown; charset=utf-8",
                                  f"snowman-kontor-forbetringar-{time.strftime('%Y%m%d')}.md")
        if p == "ai":
            c = k.cfg["ai"]
            return self.send_json({"ok": True, "leverandor": c.get("leverandor", "av"), "modell": c.get("modell", ""),
                                   "adresse": c.get("adresse", ""), "har_nokkel": bool(c.get("api_nokkel")),
                                   "siste": k.ai.last})
        if p == "ai/lokal":
            return self.send_json({"ok": True, **k.ai.lokal()})
        if p == "ai/forehandsvis":
            return self.send_json({"ok": True, **k.ai.preview(k)})
        if p == "base":
            c = k.cfg["base"]
            return self.send_json({"ok": True, "adresse": c.get("adresse", ""), "brukar": c.get("brukar", ""),
                                   "har_passord": bool(c.get("passord")), **k.basestatus.last})
        if p == "hendingar":
            return self.send_json({"ok": True, "hendingar": k.events.latest(int(q.get("n") or 200))})
        if p == "konfig":
            return self.send_json({"ok": True, "konfig": k.cfg.public()})
        if p == "brukarar":
            return self.send_json({"ok": True, "brukarar": k.cfg.users_public(), "eg": self._user("kontor")})
        return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)

    # ---------- POST ----------
    def do_POST(self):
        k = self.k
        p = urllib.parse.urlparse(self.path).path
        try:
            if not p.startswith("/api/v1/"):
                return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)
            return self.api_post(p[8:])
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (ValueError, KeyError, TypeError) as e:
            self.send_json({"ok": False, "feil": str(e)}, 400)
        except Exception as e:
            k.events.add(f"API-feil {p}: {e}", "feil")
            self.send_json({"ok": False, "feil": str(e)}, 500)

    def api_post(self, p):
        k, st = self.k, self.k.store
        ip = self.client_address[0]
        if p == "logg-inn":
            d = self.body_json(10_000)
            if k.vern.is_blocked(ip):
                time.sleep(1)
                return self.send_json({"ok": False, "feil": "For mange feil innloggingar – prøv att om litt"}, 429)
            u = k.cfg.check_user(d.get("brukar"), d.get("passord"), "kontor")
            if u is None:
                k.vern.failed(ip, "kontorsida")
                k.events.add(f"Feil innlogging på kontorsida («{str(d.get('brukar') or '–')[:32]}») frå {ip}", "feil")
                time.sleep(1)
                return self.send_json({"ok": False, "feil": "Feil brukarnamn eller passord (eller brukaren har ikkje "
                                                            "kontor-rolla)"}, 401)
            k.vern.ok(ip)
            k.events.add(f"{u['namn']} logga inn på kontorsida frå {ip}", "info")
            return self.send_json({"ok": True, "okt": k.vern.new_session(u["namn"]), "brukar": u["namn"],
                                   "anlegg_port": k.anlegg_port()})
        if p == "logg-ut":
            k.vern.end_session(self.key())
            return self.send_json({"ok": True})
        if p == "oppsett":
            d = self.body_json(10_000)
            if not vernmod.is_local(ip):
                return self.send_json({"ok": False, "feil": "Første administrator kan berre lagast frå det lokale "
                                                            "nettet (eller med kommandoen på PC-en)."}, 403)
            name, pw = valid_name(d.get("brukar")), valid_pw(d.get("passord"))
            nb, npw = str(d.get("maskin_brukar") or "").strip(), d.get("maskin_passord")
            if nb:
                valid_name(nb)
                valid_pw(npw)
                if nb.lower() == name.lower():
                    raise ValueError("Brukaren til maskinene må ha eit anna namn enn administratoren")

            def fn(data):
                if any("kontor" in u.get("roller", []) for u in data["brukarar"]):
                    raise PermissionError("Administrator finst alt – logg inn")
                return True
            try:
                k.cfg.update(fn)
            except PermissionError as e:
                return self.send_json({"ok": False, "feil": str(e)}, 409)
            k.cfg.set_user(name, pw, roles=["kontor"])
            if nb:
                k.cfg.set_user(nb, npw, roles=["maskin"])
            k.events.add(f"Første administrator «{name}» laga frå {ip}" + (f", og maskinbrukaren «{nb}»" if nb else ""), "ok")
            return self.send_json({"ok": True, "okt": k.vern.new_session(name), "brukar": name})
        if p in ("maskin", "maalingar", "forslag", "ai/maskin"):
            if not self.is_machine():
                return self.deny()
            d = self.body_json()
            if p == "ai/maskin":   # SNOWMAN AI for førarane (1.3.0)
                namn = _safe(d.get("maskin")) or "ei maskin"
                return self.send_json({"ok": True, "svar": k.ai.driver(namn, d.get("tekst"), d.get("kontekst"))})
            if p == "maskin":
                mid = _safe(d.get("id") or d.get("namn"))
                if not mid:
                    raise ValueError("id manglar")
                ok, err = st.heartbeat(mid, d, ip, int(k.cfg["deling"].get("maskinplassar") or 0))
                pk = st.package()
                return self.send_json({"ok": ok, "feil": err, "tid": time.time(), "kontor": VERSION, "api": API_VERSION,
                                       "ai": k.ai.enabled(),
                                       "snowman_min": SNOWMAN_MIN, "pakke": pk["versjon"] if pk else None},
                                      200 if ok else 403)
            if p == "maalingar":
                mid = _safe(d.get("maskin"))
                if not mid:
                    raise ValueError("maskin manglar")
                n, bad = st.add_measurements(mid, d.get("punkt"), k.cfg["deling"].get("timar", 12))
                return self.send_json({"ok": True, "lagra": n, "avvist": bad})
            pid = st.add_proposal(_safe(d.get("maskin")) or "kontor", d)
            k.events.add(f"Nytt forslag ({d.get('type', 'anna')}) frå {d.get('maskin') or 'kontor'}", "info")
            return self.send_json({"ok": True, "id": pid})
        if not self.is_office():
            return self.deny()
        if p == "anleggspakke":
            return self.upload_package()
        d = self.body_json()
        if p == "anleggspakke/aktiv":
            ok = st.activate(d["versjon"])
            if ok:
                k.events.add(f"Anleggspakke v{d['versjon']} er aktiv", "ok")
            return self.send_json({"ok": ok})
        if p == "forslag/svar":
            if d.get("status") not in ("ny", "godkjent", "avvist", "gjort"):
                raise ValueError("status må vere ny, godkjent, avvist eller gjort")
            return self.send_json({"ok": st.set_proposal(d["id"], d["status"], d.get("svar", "")) > 0})
        if p == "maskin/fjern":
            return self.send_json({"ok": st.remove_machine(d["id"])})
        if p == "forbetringar/status":
            if d.get("status") not in ("ny", "godteke", "avvist", "gjort"):
                raise ValueError("status må vere ny, godteke, avvist eller gjort")
            return self.send_json({"ok": st.set_improvement(d["nokkel"], d["status"], d.get("merknad", "")) > 0})
        if p == "forbetringar/analyser":
            found = forbetring.run(k)
            return self.send_json({"ok": True, "tal": len(found)})
        if p == "ai/innstillingar":
            if d.get("leverandor") not in ("av", "ollama", "anthropic"):
                raise ValueError("leverandor må vere av, ollama eller anthropic")

            def fn(data):
                c = data["ai"]
                c["leverandor"] = d["leverandor"]
                c["modell"] = str(d.get("modell") or "")[:80]
                c["adresse"] = str(d.get("adresse") or "")[:200]
                if d.get("api_nokkel"):
                    c["api_nokkel"] = str(d["api_nokkel"]).strip()
                if d.get("fjern_nokkel"):
                    c["api_nokkel"] = ""
                return dict(c)
            c = k.cfg.update(fn)
            k.events.add(f"AI: {c['leverandor']}" + (f" ({c['modell']})" if c["modell"] else ""), "info")
            return self.send_json({"ok": True})
        if p == "ai/lokal/hent":
            return self.send_json({"ok": True, "henting": k.ai.hent_modell(d.get("modell"))})
        if p == "ai/lokal/ta-i-bruk":
            m = str(d.get("modell") or "").strip()[:80] or aimod.LOKAL_MODELL

            def fn(data):
                data["ai"].update(leverandor="ollama", modell=m)
            k.cfg.update(fn)
            k.events.add(f"AI: lokal modell {m} (Ollama) teken i bruk – også for maskinene", "ok")
            return self.send_json({"ok": True})
        if p == "ai/analyser":
            items = k.ai.analyse(k)
            return self.send_json({"ok": True, "tal": len(items), "forslag": items})
        if p == "ai/sporsmal":
            return self.send_json({"ok": True, "svar": k.ai.ask(k, d.get("tekst", ""))})
        if p == "base":
            adr = str(d.get("adresse") or "").strip()[:200]
            if adr and (" " in adr or not all(c.isprintable() for c in adr)):
                raise ValueError("Ugyldig adresse")

            def fn(data):
                c = data["base"]
                c["adresse"] = adr
                c["brukar"] = str(d.get("brukar") or "").strip()[:64]
                if d.get("passord"):
                    c["passord"] = str(d["passord"])[:128]
                if d.get("fjern_passord") or not c["brukar"]:
                    c["passord"] = ""
            k.cfg.update(fn)
            k.events.add(f"Adressa til SNOWMAN Base: {adr or '(ingen)'}", "info")
            return self.send_json({"ok": True, **(k.basestatus.fetch() if adr else k.basestatus.last)})
        if p == "brukar":
            name = valid_name(d.get("namn"))
            pw = d.get("passord") or None
            roles = d.get("roller")
            ny = k.cfg.find_user(name) is None
            u = k.cfg.set_user(name, pw, roles)
            if pw and not ny:
                k.vern.end_user_sessions(name)
            k.events.add(f"Brukar «{name}» {'oppretta' if ny else 'endra'}" + (" (nytt passord)" if pw and not ny else "")
                         + f" av {self._user('kontor')}", "info")
            return self.send_json({"ok": True, "brukar": {"namn": u["namn"], "roller": u["roller"]}})
        if p == "brukar/fjern":
            name = str(d.get("namn") or "")
            ok = k.cfg.remove_user(name)
            if ok:
                k.vern.end_user_sessions(name)
                k.events.add(f"Brukar «{name}» sletta av {self._user('kontor')}", "info")
            return self.send_json({"ok": ok})
        if p == "oppdatering/sjekk":
            return self.send_json({"ok": True, **k.updates.check()})
        if p == "oppdater":
            changed, text = k.updates.run_now()
            return self.send_json({"ok": True, "endra": changed, "tekst": text})
        return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)

    def upload_package(self):
        k = self.k
        n = int(self.headers.get("Content-Length") or 0)
        limit = int(k.cfg["anleggspakke"].get("maks_mb", 4000)) * 1_000_000
        if n <= 0 or n > limit:
            raise ValueError(f"anleggspakka må vere mellom 1 byte og {limit // 1_000_000} MB")
        tmp = k.store.pkgdir / f"opplasting-{os.getpid()}-{threading.get_ident()}.tmp"
        left = n
        with open(tmp, "wb") as f:
            while left:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk:
                    break
                f.write(chunk)
                left -= len(chunk)
        if left:
            tmp.unlink(missing_ok=True)
            raise ValueError("opplastinga vart avbroten")
        try:
            innhald = anleggspakke.kontroller(tmp, limit * 4)
        except anleggspakke.Feil:
            tmp.unlink(missing_ok=True)
            raise
        note = urllib.parse.unquote(self.headers.get("X-Merknad", ""))
        pk = k.store.add_package(tmp, note, int(k.cfg["anleggspakke"].get("behald_versjonar", 20)), innhald)
        tal = ", ".join(f"{v} {kk.replace('_', ' ')}" for kk, v in innhald["tal"].items())
        k.events.add(f"Ny anleggspakke v{pk['versjon']} ({tal}) – maskinene hentar henne", "ok")
        return self.send_json({"ok": True, "pakke": pk})


# ---------- port for maskinene ute i bakken (sanntid, 2026-11-22) ----------
# Maskinene på mobilnettet når Office gjennom denne porten (standard 8791), som ruteren sender vidare til kontor-PC-en.
# Berre maskin-API-et er ope her, og berre for brukarar med rolla «maskin». Kontorsida (8790) blir aldri opna utanfrå.
MASKIN_GET = {"/api/v1/info", "/api/v1/maalingar", "/api/v1/maskiner", "/api/v1/anleggspakke", "/api/v1/anleggspakke/fil"}
MASKIN_POST = {"/api/v1/maskin", "/api/v1/maalingar", "/api/v1/forslag", "/api/v1/ai/maskin"}


class MaskinHandler(Handler):
    def key(self):
        return ""                                   # økter frå kontorsida gjeld ikkje her

    def _user(self, role):
        name, pw = self.basic()
        if name is None or self.k.vern.is_blocked(self.ip()):
            return None
        u = self.k.cfg.check_user(name, pw, "maskin")
        if u is None:
            self.k.vern.failed(self.ip(), "maskinport")
            return None
        self.k.vern.ok(self.ip())
        return u["namn"] if role == "maskin" else None

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path not in MASKIN_GET:
            return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)
        return super().do_GET()

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path not in MASKIN_POST:
            return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)
        return super().do_POST()


def start_maskinport(k, port):
    h = type("HM", (MaskinHandler,), {"k": k})

    class Srv(ExclusiveMixin, socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    srv = Srv(("0.0.0.0", int(port)), h)
    threading.Thread(target=srv.serve_forever, daemon=True, name="maskinport").start()
    return srv


def _safe(x):
    return "".join(c for c in str(x or "") if c.isalnum() or c in "-_.")[:64]


class ExclusiveMixin:
    """Éin Office per port. Windows: SO_EXCLUSIVEADDRUSE, så to Office på same PC gir feilmelding."""
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def start(k, port):
    h = type("H", (Handler,), {"k": k})

    class Srv(ExclusiveMixin, socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    srv = Srv(("0.0.0.0", int(port)), h)
    threading.Thread(target=srv.serve_forever, daemon=True, name="web").start()
    return srv
