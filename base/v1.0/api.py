# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Nettsider og API i SNOWMAN Base (standard port 8780).

Sider:   /           statussida (straumar, kjelder, maskiner, hendingar)
         /kontor/    kontorsida (maskiner, anleggspakke, forslag, forbetringar, AI, oppdatering)

API v1 (JSON). Innlogging: «Authorization: Bearer <nøkkel>».
  Ope:        GET  /api/v1/info                     versjon, API-versjon, funksjonar, minste SNOWMAN-versjon
              GET  /api/status                      status (om web.status_open, elles kontornøkkel)
  Maskin:     POST /api/v1/maskin                   hjarteslag {id, namn, versjon, pakke, lat, lon, fix, fixdel}
  (anleggs-   POST /api/v1/maalingar                {maskin, punkt: [{t, lat, lon, h, djupne, fix, kalibrert}]}
   nøkkel)    GET  /api/v1/maalingar?etter=&utan=   delte målingar siste 12 t (berre nye sidan «etter»)
              GET  /api/v1/maskiner                 alle maskiner (posisjon, sist sett)
              GET  /api/v1/anleggspakke             aktiv versjon {versjon, sha256, storleik}
              GET  /api/v1/anleggspakke/fil         zip-fila (?versjon= for ein bestemt)
              POST /api/v1/forslag                  {maskin, type: hindring|merknad|program|anna, tekst, lat, lon}
              GET  /api/v1/baner                    siste BRDC-banefil (om Base hentar baner)
  Kontor:     POST /api/v1/anleggspakke             ny versjon (zip i body, X-Merknad), blir aktiv
  (kontor-    POST /api/v1/anleggspakke/aktiv       {versjon} – rull tilbake/fram
   nøkkel)    GET  /api/v1/forslag  ·  POST /api/v1/forslag/svar {id, status, svar}
              POST /api/v1/maskin/fjern {id}
              GET  /api/v1/forbetringar  ·  GET /api/v1/forbetringar.md  ·  POST /api/v1/forbetringar/status
              POST /api/v1/forbetringar/analyser
              GET  /api/v1/ai  ·  POST /api/v1/ai/innstillingar  ·  GET /api/v1/ai/forehandsvis
              POST /api/v1/ai/analyser  ·  POST /api/v1/ai/sporsmal {tekst}
              POST /api/v1/oppdatering/sjekk  ·  POST /api/v1/oppdater
              GET  /api/v1/hendingar
              GET  /api/v1/mountpoints              mountpoints med kjelder (utan passord)
              POST /api/v1/mountpoint               {namn, skildring, byte_etter_s, innmalt, kjelder, gamalt_namn}
                                                    – nytt eller endra, blir teke i bruk med éin gong
              POST /api/v1/mountpoint/fjern {namn}
              POST /api/v1/kjeldetabell             {caster, port, brukar, passord | kjelde_id} – mountpoints
                                                    på ein annan caster (til relé)
              GET  /api/v1/serieportar              COM-portar / USB-einingar på maskina Base køyrer på
Brot i API-et gir ny API-versjon (/api/v2/…); v1 blir verande så lenge maskiner brukar han.
"""
import http.server
import json
import mimetypes
import os
import socketserver
import threading
import time
import urllib.parse
from pathlib import Path

import forbetring
import mountoppsett
import ntripklient
from konfig import API_VERSION, FUNKSJONAR, SNOWMAN_MIN, VERSION

HERE = Path(__file__).resolve().parent
STATIC = {"/": HERE / "web" / "status.html", "/kontor": HERE / "kontor" / "index.html",
          "/kontor/": HERE / "kontor" / "index.html"}


class Handler(http.server.BaseHTTPRequestHandler):
    base = None
    server_version = f"SNOWMAN-Base/{VERSION}"
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
    def key(self):
        a = self.headers.get("Authorization", "")
        return a[7:].strip() if a.lower().startswith("bearer ") else ""

    def is_office(self):
        return self.base.cfg.key_ok(self.key(), "kontor")

    def is_machine(self):
        k = self.key()
        return self.base.cfg.key_ok(k, "anlegg") or self.base.cfg.key_ok(k, "kontor")

    def deny(self):
        time.sleep(1)                               # bremsar gjetting av nøklar
        self.send_json({"ok": False, "feil": "Manglar eller feil nøkkel"}, 401)

    def body_json(self, limit=20_000_000):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("for stor førespurnad")
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    # ---------- GET ----------
    def do_GET(self):
        b = self.base
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
                return self.send_json({"ok": True, "namn": b.cfg["namn"], "anlegg": b.cfg["anlegg"], "versjon": VERSION,
                                       "api": API_VERSION, "snowman_min": SNOWMAN_MIN, "funksjonar": FUNKSJONAR,
                                       "caster_port": b.caster_port, "mountpoints": list(b.mounts)})
            if p == "/api/status":
                if not b.cfg["web"].get("status_open", True) and not self.is_office():
                    return self.deny()
                return self.send_json(b.status())
            if p.startswith("/api/v1/"):
                return self.api_get(p[8:], q)
            return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            b.events.add(f"API-feil {p}: {e}", "feil")
            self.send_json({"ok": False, "feil": str(e)}, 500)

    def api_get(self, p, q):
        b, st = self.base, self.base.store
        machine_paths = {"maalingar", "maskiner", "anleggspakke", "anleggspakke/fil", "baner"}
        if p in machine_paths:
            if not self.is_machine():
                return self.deny()
            if p == "maalingar":
                rows, last = st.measurements(int(q.get("etter") or 0), b.cfg["deling"].get("timar", 12),
                                             q.get("utan"), int(q.get("maks") or 5000))
                return self.send_json({"ok": True, "maalingar": rows, "siste": last,
                                       "timar": b.cfg["deling"].get("timar", 12)})
            if p == "maskiner":
                return self.send_json({"ok": True, "maskiner": st.machines()})
            if p == "anleggspakke":
                pk = st.package()
                return self.send_json({"ok": True, "pakke": pk})
            if p == "anleggspakke/fil":
                pk = st.package(q.get("versjon")) if q.get("versjon") else st.package()
                if not pk:
                    return self.send_json({"ok": False, "feil": "ingen anleggspakke"}, 404)
                return self.send_file(st.pkgdir / pk["fil"], "application/zip", pk["fil"])
            if p == "baner":
                f = b.baner.latest()
                if not f:
                    return self.send_json({"ok": False, "feil": "Base har ikkje henta banefil (baner.hent)"}, 404)
                return self.send_file(f, "text/plain", f.name)
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
                                  f"snowman-base-forbetringar-{time.strftime('%Y%m%d')}.md")
        if p == "ai":
            c = b.cfg["ai"]
            return self.send_json({"ok": True, "leverandor": c.get("leverandor", "av"), "modell": c.get("modell", ""),
                                   "adresse": c.get("adresse", ""), "har_nokkel": bool(c.get("api_nokkel")),
                                   "siste": b.ai.last})
        if p == "ai/forehandsvis":
            return self.send_json({"ok": True, **b.ai.preview(b)})
        if p == "hendingar":
            return self.send_json({"ok": True, "hendingar": b.events.latest(int(q.get("n") or 200))})
        if p == "konfig":
            return self.send_json({"ok": True, "konfig": b.cfg.public()})
        if p == "mountpoints":
            st_ = {m.name: m for m in list(b.mounts.values())}
            ut = []
            for mc in b.cfg["mountpoints"]:
                d = mountoppsett.offentleg(mc)
                m = st_.get(mc.get("namn"))
                d["aktiv"] = m.active.name if m and m.active else None
                d["klientar"] = len(m.clients) if m else 0
                d["kjeldestatus"] = {x.name: {"tilkopla": x.connected, "feil": x.err} for x in (m.sources if m else [])}
                ut.append(d)
            return self.send_json({"ok": True, "mountpoints": ut, "caster_port": b.caster_port,
                                   "typar": list(mountoppsett.TYPAR), "baud": list(mountoppsett.BAUD)})
        if p == "serieportar":
            try:
                from serial.tools import list_ports
                portar = [{"port": x.device, "skildring": x.description or ""} for x in list_ports.comports()]
            except Exception as e:
                return self.send_json({"ok": True, "portar": [], "feil": f"Kan ikkje liste portar ({e})"})
            return self.send_json({"ok": True, "portar": sorted(portar, key=lambda x: x["port"])})
        return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)

    # ---------- POST ----------
    def do_POST(self):
        b = self.base
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
            b.events.add(f"API-feil {p}: {e}", "feil")
            self.send_json({"ok": False, "feil": str(e)}, 500)

    def api_post(self, p):
        b, st = self.base, self.base.store
        ip = self.client_address[0]
        if p in ("maskin", "maalingar", "forslag"):
            if not self.is_machine():
                return self.deny()
            d = self.body_json()
            if p == "maskin":
                mid = _safe(d.get("id") or d.get("namn"))
                if not mid:
                    raise ValueError("id manglar")
                ok, err = st.heartbeat(mid, d, ip, int(b.cfg["deling"].get("maskinplassar") or 0))
                pk = st.package()
                return self.send_json({"ok": ok, "feil": err, "tid": time.time(), "base": VERSION, "api": API_VERSION,
                                       "snowman_min": SNOWMAN_MIN, "pakke": pk["versjon"] if pk else None},
                                      200 if ok else 403)
            if p == "maalingar":
                mid = _safe(d.get("maskin"))
                if not mid:
                    raise ValueError("maskin manglar")
                n, bad = st.add_measurements(mid, d.get("punkt"), b.cfg["deling"].get("timar", 12))
                return self.send_json({"ok": True, "lagra": n, "avvist": bad})
            if p == "forslag":
                pid = st.add_proposal(_safe(d.get("maskin")) or "kontor", d)
                b.events.add(f"Nytt forslag ({d.get('type', 'anna')}) frå {d.get('maskin') or 'kontor'}", "info")
                return self.send_json({"ok": True, "id": pid})
        if not self.is_office():
            return self.deny()
        if p == "anleggspakke":
            return self.upload_package()
        d = self.body_json()
        if p == "anleggspakke/aktiv":
            ok = st.activate(d["versjon"])
            if ok:
                b.events.add(f"Anleggspakke v{d['versjon']} er aktiv", "ok")
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
            found = forbetring.run(b)
            return self.send_json({"ok": True, "tal": len(found)})
        if p == "ai/innstillingar":
            c = b.cfg["ai"]
            if d.get("leverandor") not in ("av", "ollama", "anthropic"):
                raise ValueError("leverandor må vere av, ollama eller anthropic")
            with b.cfg.lock:
                c["leverandor"] = d["leverandor"]
                c["modell"] = str(d.get("modell") or "")[:80]
                c["adresse"] = str(d.get("adresse") or "")[:200]
                if d.get("api_nokkel"):
                    c["api_nokkel"] = str(d["api_nokkel"]).strip()
                if d.get("fjern_nokkel"):
                    c["api_nokkel"] = ""
                b.cfg.save()
            b.events.add(f"AI: {c['leverandor']}" + (f" ({c['modell']})" if c["modell"] else ""), "info")
            return self.send_json({"ok": True})
        if p == "ai/analyser":
            items = b.ai.analyse(b)
            return self.send_json({"ok": True, "tal": len(items), "forslag": items})
        if p == "ai/sporsmal":
            return self.send_json({"ok": True, "svar": b.ai.ask(b, d.get("tekst", ""))})
        if p == "mountpoint":
            m, melding = b.lagre_mountpoint(d, d.get("gamalt_namn") or None)
            return self.send_json({"ok": True, "mountpoint": mountoppsett.offentleg(m), "melding": melding})
        if p == "mountpoint/fjern":
            return self.send_json({"ok": b.fjern_mountpoint(str(d.get("namn") or ""))})
        if p == "kjeldetabell":
            return self.send_json(self.sourcetable(d))
        if p == "oppdatering/sjekk":
            return self.send_json({"ok": True, **b.updates.check()})
        if p == "oppdater":
            changed, text = b.updates.run_now()
            return self.send_json({"ok": True, "endra": changed, "tekst": text})
        return self.send_json({"ok": False, "feil": "ukjend adresse"}, 404)

    def sourcetable(self, d):
        """Mountpoints på ein annan caster. Tomt passord: bruk det lagra passordet til kjelda (kjelde_id)."""
        b = self.base
        vert = str(d.get("caster") or "").strip()
        vert = vert.split("://")[-1].rstrip("/")
        if not vert or " " in vert or "/" in vert:
            raise ValueError("Skriv casteradressa, t.d. gpsbase.dyndns.org")
        port = int(d.get("port") or 2101)
        brukar, pw = str(d.get("brukar") or ""), str(d.get("passord") or "")
        if not pw and d.get("kjelde_id"):
            for mc in b.cfg["mountpoints"]:
                for k in mc.get("kjelder", []):
                    if k.get("id") == d["kjelde_id"] and k.get("type") == "ntrip":
                        pw = k.get("passord", "")
        try:
            r = ntripklient.fetch_sourcetable(vert, port, brukar, pw, f"Base {VERSION}", timeout=8)
        except Exception as e:
            return {"ok": False, "feil": str(e)}
        return {"ok": True, "caster": r["caster"], "proto": r["proto"],
                "mountpoints": [{k: m.get(k) for k in ("mountpoint", "name", "format", "systems", "lat", "lon",
                                                       "nmea", "network_rtk")} for m in r["mounts"]]}

    def upload_package(self):
        b = self.base
        n = int(self.headers.get("Content-Length") or 0)
        limit = int(b.cfg["anleggspakke"].get("maks_mb", 4000)) * 1_000_000
        if n <= 0 or n > limit:
            raise ValueError(f"anleggspakka må vere mellom 1 byte og {limit // 1_000_000} MB")
        tmp = b.store.pkgdir / f"opplasting-{os.getpid()}-{threading.get_ident()}.tmp"
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
        with open(tmp, "rb") as f:
            if f.read(2) != b"PK":
                tmp.unlink(missing_ok=True)
                raise ValueError("anleggspakka må vere ei zip-fil")
        note = urllib.parse.unquote(self.headers.get("X-Merknad", ""))
        pk = b.store.add_package(tmp, note, int(b.cfg["anleggspakke"].get("behald_versjonar", 20)))
        b.events.add(f"Ny anleggspakke v{pk['versjon']} ({pk['storleik'] // 1024} kB) – maskinene hentar henne", "ok")
        return self.send_json({"ok": True, "pakke": pk})


def _safe(x):
    return "".join(c for c in str(x or "") if c.isalnum() or c in "-_.")[:64]


def start(base, port):
    h = type("H", (Handler,), {"base": base})

    class Srv(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    srv = Srv(("0.0.0.0", int(port)), h)
    threading.Thread(target=srv.serve_forever, daemon=True, name="web").start()
    return srv
