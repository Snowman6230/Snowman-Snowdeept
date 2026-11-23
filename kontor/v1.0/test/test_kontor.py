# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Testar for SNOWMAN Kontor. Køyr frå kontor/v1.0:   python -m unittest discover -s test -v

Maskinsida (anleggspakke, forslag, kø) blir testa mot SNOWMAN snødjupne i pc/v1.6/test/testkontorkopling.py.
"""
import base64
import hashlib
import http.server
import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import anleggspakke as AP                     # noqa: E402
import konfig                                 # noqa: E402
import snowman_kontor as SK                   # noqa: E402
from hendingar import Events                  # noqa: E402

LAT, LON = 62.3802, 6.7811
TRASE = {"id": "t1", "name": "Bakke 1", "kind": "trase", "level": "bla", "target": 0.6,
         "poly": [[62.38, 6.78], [62.381, 6.78], [62.381, 6.782]]}
HINDRING = {"id": "o1", "type": "hydrant", "name": "Hydrant 4", "lat": 62.3805, "lng": 6.781, "radius": 0.5}
KPUNKT = {"id": "k1", "name": "Bolt ved heishus", "E": 389000.0, "N": 6918000.0, "zone": 32, "h": 702.3}


class FakeOllama(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.seen.append(body)
        out = {"forslag": [{"kategori": "snowman", "alvor": "middels", "tittel": "Vis alder på korreksjonane i HUD",
                            "grunn": "Fleire avbrot i mobilnettet.", "tiltak": "Legg alder i sekund på HUD-en."}]}
        data = json.dumps({"message": {"content": "Her er forslaga:\n" + json.dumps(out, ensure_ascii=False)}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class FakeBase(http.server.BaseHTTPRequestHandler):
    """Statussida til SNOWMAN Base 1.4 (berre det Kontor les)."""

    def log_message(self, *a):
        pass

    def do_GET(self):
        st = {"ok": True, "program": "SNOWMAN Base", "versjon": "1.4.0", "tilkoplingar_i_dag": 3,
              "mountpoints": [{"namn": "FJELL", "aktiv": "mottakar", "systems": ["GPS", "Galileo"], "satsTotal": 18,
                               "eph": False, "vurdering": "OK: 18 satellittar", "klientar": [],
                               "base": {"lat": LAT, "lon": LON}, "dag": {"ok": 90, "tot": 100, "bytte": 1}}],
              "forslag": [{"nokkel": "FJELL:ikkje-innmalt", "kategori": "drift", "alvor": "høg",
                           "tittel": "FJELL: basen er ikkje kontrollert mot innmålt punkt", "grunn": "g", "tiltak": "t"}]}
        data = json.dumps(st).encode()
        self.send_response(200 if self.path == "/api/status" else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class KontorCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        cfg = konfig.Config(self.dir / "data")
        cfg.first_setup()
        cfg.set_user("pb600", "maskin-passord-1", roles=["maskin"])
        cfg.set_user("admin", "kontor-passord-1", roles=["kontor"])
        cfg.data["oppdatering"]["sjekk"] = False
        cfg.save()
        self.mkey = ("pb600", "maskin-passord-1")
        self.kkey = ("admin", "kontor-passord-1")
        self.k = SK.SnowmanKontor(self.dir / "data", 0, False, 0).start()
        self.web = f"http://127.0.0.1:{self.k.web_port}"

    def tearDown(self):
        self.k.stop()
        time.sleep(0.2)
        self.tmp.cleanup()

    def call(self, path, body=None, key=None, method=None, raw=None, headers=None):
        h = dict(headers or {})
        if isinstance(key, tuple):
            h["Authorization"] = "Basic " + base64.b64encode(f"{key[0]}:{key[1]}".encode()).decode()
        elif key:
            h["Authorization"] = "Bearer " + key
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if body is not None:
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(self.web + path, data=data, headers=h, method=method or ("POST" if data else "GET"))
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                ct = r.headers.get("content-type", "")
                b = r.read()
                return r.status, (json.loads(b) if "json" in ct else b)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


class TestApi(KontorCase):
    def test_info_og_sider(self):
        c, d = self.call("/api/v1/info")
        self.assertEqual((c, d["program"], d["versjon"]), (200, "SNOWMAN Kontor", konfig.VERSION))
        self.assertIn("anleggspakke-format-1", d["funksjonar"])
        self.assertNotIn("ntrip-caster", d["funksjonar"])
        for p in ("/", "/kontor/", "/vendor/leaflet.js"):
            with urllib.request.urlopen(self.web + p, timeout=5) as r:
                self.assertEqual(r.status, 200)
        self.assertNotIn("hash", json.dumps(self.call("/api/v1/konfig", key=self.kkey)[1]))

    def test_roller(self):
        self.assertEqual(self.call("/api/v1/maskiner")[0], 401)
        self.assertEqual(self.call("/api/v1/maskiner", key=self.mkey)[0], 200)        # maskin → maskin-API
        self.assertEqual(self.call("/api/v1/brukarar", key=self.mkey)[0], 401)        # maskin → ikkje kontor
        self.assertEqual(self.call("/api/status", key=self.mkey)[0], 401)
        self.assertEqual(self.call("/api/v1/maskiner", key=self.kkey)[0], 200)        # kontor → alt
        self.assertEqual(self.call("/api/v1/maskiner", key=("pb600", "feil"))[0], 401)
        c, d = self.call("/api/v1/logg-inn", {"brukar": "admin", "passord": "kontor-passord-1"})
        tok = d["okt"]
        self.assertEqual(self.call("/api/v1/brukarar", key=tok)[0], 200)
        self.call("/api/v1/logg-ut", {}, tok)
        self.assertEqual(self.call("/api/v1/brukarar", key=tok)[0], 401)

    def test_hjarteslag_og_maskinplassar(self):
        c, d = self.call("/api/v1/maskin", {"id": "PB1", "namn": "PB 600 nr 1", "versjon": "1.6.137", "pakke": None,
                                            "fixdel": 0.92, "lat": LAT, "lon": LON}, self.mkey)
        self.assertEqual((c, d["snowman_min"]), (200, konfig.SNOWMAN_MIN))
        self.k.cfg["deling"]["maskinplassar"] = 1
        self.assertEqual(self.call("/api/v1/maskin", {"id": "PB2"}, self.mkey)[0], 403)
        self.assertEqual(self.call("/api/v1/maskin", {"id": "PB1"}, self.mkey)[0], 200)

    def test_maskinporten(self):
        """Port 8791 (ute i bakken): berre maskin-API-et, berre rolla maskin. Kontorsida blir aldri opna her."""
        port = self.k.maskin_srv.server_address[1]
        self.assertNotEqual(port, self.k.web_port)
        web, self.web = self.web, f"http://127.0.0.1:{port}"
        try:
            c, d = self.call("/api/v1/maskin", {"id": "PB1", "namn": "PB 600 nr 1", "versjon": "1.6.139", "lat": LAT,
                                                "lon": LON, "fix": 4, "djupne": 0.74, "prep": True}, self.mkey)
            self.assertEqual(c, 200)
            c, d = self.call("/api/v1/maskiner", key=self.mkey)
            m = d["maskiner"][0]
            self.assertEqual((c, m["fix"], m["ekstra"]["djupne"], m["ekstra"]["prep"]), (200, 4, 0.74, True))
            self.assertIn("pos_t", m["ekstra"])
            self.assertEqual(self.call("/api/v1/maskiner")[0], 401)                    # utan innlogging
            self.assertEqual(self.call("/api/v1/maskiner", key=self.kkey)[0], 401)     # kontorbrukar → nei
            for p in ("/", "/kontor/", "/api/status", "/api/v1/brukarar", "/api/v1/konfig"):
                self.assertEqual(self.call(p, key=self.mkey)[0], 404, p)
            self.assertEqual(self.call("/api/v1/logg-inn", {"brukar": "admin", "passord": "kontor-passord-1"})[0], 404)
            # hjarteslag utan posisjon (berre pakkehenting) held på siste posisjon
            self.call("/api/v1/maskin", {"id": "PB1", "versjon": "1.6.139"}, self.mkey)
            m = self.call("/api/v1/maskiner", key=self.mkey)[1]["maskiner"][0]
            self.assertEqual((m["lat"], m["ekstra"]["djupne"]), (LAT, 0.74))
        finally:
            self.web = web

    def test_maalingar_berre_gyldige_og_inkrementelt(self):
        now = time.time()
        pts = [{"t": now, "lat": LAT, "lon": LON, "h": 700, "djupne": 1.2, "fix": 4, "kalibrert": True},
               {"t": now, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 5, "kalibrert": True},          # FLOAT
               {"t": now, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 4, "kalibrert": False},          # ikkje kalibrert
               {"t": now, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 4, "kalibrert": True, "demo": True},
               {"t": now - 13 * 3600, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 4, "kalibrert": True}]
        c, d = self.call("/api/v1/maalingar", {"maskin": "PB1", "punkt": pts}, self.mkey)
        self.assertEqual((d["lagra"], d["avvist"]), (1, 4))
        c, d = self.call("/api/v1/maalingar?etter=0", key=self.mkey)
        self.assertEqual(len(d["maalingar"]), 1)
        c, d2 = self.call(f"/api/v1/maalingar?etter={d['siste']}", key=self.mkey)
        self.assertEqual(d2["maalingar"], [])

    def test_anleggspakke(self):
        zipdata = Path(AP.lag(self.dir / "p.zip", "Fjellsætra", "admin", trasear=[TRASE], objekt=[HINDRING],
                              kontrollpunkt=[KPUNKT])).read_bytes()
        self.assertEqual(self.call("/api/v1/anleggspakke", raw=zipdata, key=self.mkey)[0], 401)
        self.assertEqual(self.call("/api/v1/anleggspakke", raw=b"ikkje zip", key=self.kkey)[0], 400)
        c, d = self.call("/api/v1/anleggspakke", raw=zipdata, key=self.kkey, headers={"X-Merknad": "Ny%20tras%C3%A9"})
        self.assertEqual(d["pakke"]["versjon"], 1)
        self.assertEqual(d["pakke"]["innhald"]["tal"], {"trasear": 1, "forbodne_omrade": 0, "hindringar": 1,
                                                        "kontrollpunkt": 1})
        self.call("/api/v1/anleggspakke", raw=zipdata, key=self.kkey)
        c, d = self.call("/api/v1/anleggspakke", key=self.mkey)
        self.assertEqual(d["pakke"]["versjon"], 2)
        self.call("/api/v1/anleggspakke/aktiv", {"versjon": 1}, self.kkey)
        c, d = self.call("/api/v1/anleggspakke", key=self.mkey)
        self.assertEqual((d["pakke"]["versjon"], d["pakke"]["merknad"]), (1, "Ny trasé"))
        c, b = self.call("/api/v1/anleggspakke/fil", key=self.mkey)
        self.assertEqual(b, zipdata)

    def test_forslag_frå_maskin(self):
        c, d = self.call("/api/v1/forslag", {"maskin": "PB1", "type": "program", "tekst": "Større tal på HUD"}, self.mkey)
        self.assertTrue(d["ok"])
        c, d = self.call("/api/v1/forslag", key=self.kkey)
        self.assertEqual(d["forslag"][0]["tekst"], "Større tal på HUD")
        self.call("/api/v1/forslag/svar", {"id": d["forslag"][0]["id"], "status": "godkjent"}, self.kkey)
        md = self.call("/api/v1/forbetringar.md", key=self.kkey)[1].decode()
        self.assertIn("Større tal på HUD", md)

    def test_status_frå_base_og_forbetringar(self):
        c, d = self.call("/api/v1/forbetringar/analyser", {}, self.kkey)
        c, d = self.call("/api/v1/forbetringar", key=self.kkey)
        keys = {r["nokkel"] for r in d["forbetringar"]}
        self.assertIn("base-ukjend", keys)                   # adressa til Base er ikkje sett
        srv = http.server.HTTPServer(("127.0.0.1", 0), FakeBase)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            c, d = self.call("/api/v1/base", {"adresse": f"127.0.0.1:{srv.server_address[1]}"}, self.kkey)
            self.assertTrue(d["ok"])
            c, s = self.call("/api/status", key=self.kkey)
            self.assertEqual((s["base"]["ok"], s["base"]["versjon"]), (True, "1.4.0"))
            self.assertEqual(s["base"]["mountpoints"][0]["namn"], "FJELL")
            self.call("/api/v1/forbetringar/analyser", {}, self.kkey)
            c, d = self.call("/api/v1/forbetringar", key=self.kkey)
            r = {x["nokkel"]: x for x in d["forbetringar"]}
            self.assertEqual(r["base:FJELL:ikkje-innmalt"]["kjelde"], "Base")
            self.assertNotIn("base-ukjend", r)
            self.assertEqual(d["dagar"][0]["mountpoints"]["FJELL"]["oppetid"], 0.9)
        finally:
            srv.shutdown()
        c, d = self.call("/api/v1/base", {"adresse": "127.0.0.1:1"}, self.kkey)
        self.assertFalse(d["ok"])
        self.assertTrue(d["feil"])

    def test_ai_anonymisert_og_lokal_modell(self):
        self.call("/api/v1/maskin", {"id": "PB1", "namn": "Kjetil sin PB", "versjon": "1.6.137"}, self.mkey)
        self.k.store.upsert_improvement({"nokkel": "x", "kategori": "drift", "alvor": "låg",
                                         "tittel": "Kjetil sin PB: kopla til frå 10.0.0.12", "grunn": "", "tiltak": ""})
        srv = http.server.HTTPServer(("127.0.0.1", 0), FakeOllama)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.assertEqual(self.call("/api/v1/ai/analyser", {}, self.kkey)[0], 500)      # AI er av
            self.call("/api/v1/ai/innstillingar", {"leverandor": "ollama", "modell": "test",
                                                   "adresse": f"http://127.0.0.1:{srv.server_address[1]}"}, self.kkey)
            c, p = self.call("/api/v1/ai/forehandsvis", key=self.kkey)
            self.assertNotIn("Kjetil", p["melding"])
            self.assertNotIn("10.0.0.12", p["melding"])
            self.assertNotIn("maskin-passord-1", p["melding"])
            c, d = self.call("/api/v1/ai/analyser", {}, self.kkey)
            self.assertEqual(d["tal"], 1)
            c, d = self.call("/api/v1/forbetringar", key=self.kkey)
            ai = [r for r in d["forbetringar"] if r["kjelde"] == "ai"]
            self.assertEqual(ai[0]["kategori"], "snowman")
            self.assertNotIn("Kjetil", json.dumps(FakeOllama.seen[-1], ensure_ascii=False))
        finally:
            srv.shutdown()


class TestOppsett(unittest.TestCase):
    def test_første_administrator_og_kommandoar(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "data"
            k = SK.SnowmanKontor(d, 0, False, False).start()
            try:
                web = f"http://127.0.0.1:{k.web_port}"
                st = json.loads(urllib.request.urlopen(web + "/api/v1/oppsett", timeout=5).read())
                self.assertTrue(st["treng_admin"] and st["lokal"])
                body = json.dumps({"brukar": "hans", "passord": "kontor-pw-1", "maskin_brukar": "pb600",
                                   "maskin_passord": "maskin-pw-1"}).encode()
                r = json.loads(urllib.request.urlopen(urllib.request.Request(
                    web + "/api/v1/oppsett", data=body, headers={"Content-Type": "application/json"}), timeout=5).read())
                self.assertTrue(r["ok"] and r["okt"])
                self.assertEqual(k.cfg.find_user("pb600")["roller"], ["maskin"])
                with self.assertRaises(urllib.error.HTTPError):                     # berre éin gong
                    urllib.request.urlopen(urllib.request.Request(
                        web + "/api/v1/oppsett", data=body, headers={"Content-Type": "application/json"}), timeout=5)
                SK.main(["--data", str(d), "brukar", "passord", "hans", "--passord", "nytt-kontor-2"])
                time.sleep(2.5)                                                    # Kontor les fila på nytt
                self.assertIsNotNone(k.cfg.check_user("hans", "nytt-kontor-2", "kontor"))
            finally:
                k.stop()


class TestAnleggspakkeFormat(unittest.TestCase):
    """Anleggspakka må følgje formatversjon 1 (anleggspakke.py) – feil blir avviste med forklaring."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def zipp(self, files, manifest=None):
        data = {n: (b if isinstance(b, bytes) else json.dumps(b).encode()) for n, b in files.items()}
        m = {"format": AP.FORMAT, "formatversjon": 1, "filer": {n: hashlib.sha256(b).hexdigest() for n, b in data.items()}}
        if manifest is not None:
            m.update(manifest)
        p = self.dir / "x.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("manifest.json", json.dumps(m))
            for n, b in data.items():
                z.writestr(n, b)
        return p

    def feil(self, p, tekst):
        with self.assertRaises(AP.Feil) as e:
            AP.kontroller(p, 10**9)
        self.assertIn(tekst, str(e.exception))

    def test_gyldig(self):
        r = AP.kontroller(AP.lag(self.dir / "ok.zip", trasear=[TRASE, dict(TRASE, id="t2", kind="forbode")]), 10**9)
        self.assertEqual(r["tal"], {"trasear": 1, "forbodne_omrade": 1})

    def test_feil_blir_avviste(self):
        p = self.dir / "r.zip"
        p.write_bytes(b"ikkje zip")
        self.feil(p, "zip-fil")
        self.feil(self.zipp({"trasear.json": {"trasear": []}}, {"format": "anna"}), "format må vere")
        self.feil(self.zipp({"trasear.json": {"trasear": []}}, {"formatversjon": 2}), "formatversjon 2")
        self.feil(self.zipp({}), "ingen innhaldsfiler")
        self.feil(self.zipp({"trasear.json": {"trasear": []}}, {"filer": {"trasear.json": "0" * 64}}), "sha256")
        self.feil(self.zipp({"trasear.json": [TRASE]}), '{"trasear": [...]}')
        self.feil(self.zipp({"trasear.json": {"trasear": [dict(TRASE, poly=[[62, 6], [62, 7]])]}}), "minst 3 hjørne")
        self.feil(self.zipp({"trasear.json": {"trasear": [TRASE, TRASE]}}), "same id")
        self.feil(self.zipp({"objekt.json": {"objekt": [dict(HINDRING, radius=50)]}}), "radius")
        self.feil(self.zipp({"kontrollpunkt.json": {"points": [dict(KPUNKT, zone=31)]}}), "UTM-sone")
        self.feil(self.zipp({"innstillingar.json": {}}), "ikkje støtta enno")
        self.feil(self.zipp({"virus.exe": b"MZ"}), "ukjend fil")
        self.feil(self.zipp({"../ut.json": b"{}"}), "ugyldig filnamn")

    def test_terreng_og_zipbombe(self):
        meta = {"id": "lag1", "name": "Fjellsætra DTM", "type": "barmark", "nx": 2, "ny": 2, "x0": 1.0, "y0": 2.0, "zone": 32}
        npy = b"\x93NUMPY" + b"\0" * 40
        r = AP.kontroller(self.zipp({"objekt.json": {"objekt": [HINDRING]}, "terreng/lag1/meta.json": meta,
                                     "terreng/lag1/grid.npy": npy}), 10**9)
        self.assertEqual(r["tal"]["terrenglag"], 1)
        self.feil(self.zipp({"terreng/lag1/meta.json": meta}), "manglar meta.json eller grid.npy")
        self.feil(self.zipp({"terreng/dtm1.tif": b"II*\0"}), "ukjend terrengfil")
        self.feil(self.zipp({"terreng/lag1/meta.json": dict(meta, type="x"), "terreng/lag1/grid.npy": npy}), "feil id eller type")
        with self.assertRaises(AP.Feil):
            AP.kontroller(self.zipp({"trasear.json": {"trasear": [TRASE]}}), 10)


class TestOppdatering(unittest.TestCase):
    """v1.1.1: Kontor følgjer både sin eigen versjon og kartet (SNOWMAN snødjupne i pc/)."""

    def setUp(self):
        import oppdatering as O
        self.O = O
        self.d = Path(tempfile.mkdtemp())
        self.gamle = {k: getattr(O, k) for k in ("REPO", "PC", "HERE", "VERSION", "_get")}
        (self.d / "kontor" / "v1.0").mkdir(parents=True)
        (self.d / "kontor" / "v1.0" / "konfig.py").write_text('VERSION = "1.1.1"\n')
        for v, ver in (("v1.5", "1.5.9"), ("v1.6", "1.6.140")):
            (self.d / "pc" / v).mkdir(parents=True)
            (self.d / "pc" / v / "snowman_pc.py").write_text(f'VERSION="{ver}"\n')
        (self.d / "pc" / "v1.2").mkdir()                       # gamal prototype utan snowman_pc.py
        O.REPO, O.PC, O.HERE, O.VERSION = self.d, self.d / "pc", self.d / "kontor" / "v1.0", "1.1.1"

    def tearDown(self):
        for k, v in self.gamle.items():
            setattr(self.O, k, v)
        shutil.rmtree(self.d, ignore_errors=True)

    def nett(self, kontor, kart, mapper=("v1.2", "v1.6")):
        import json as J
        def get(url, timeout):
            if "api.github.com" in url:
                return J.dumps([{"name": m, "type": "dir"} for m in mapper] + [{"name": "SNOWMAN.bat", "type": "file"}])
            if "/kontor/" in url:
                return f'VERSION = "{kontor}"\n'
            return f'VERSION="{kart}"\n'
        self.O._get = get

    def test_mappe_og_versjon(self):
        self.assertEqual(self.O.pc_mappe().name, "v1.6")
        self.assertEqual(self.O.kart_versjon(), "1.6.140")

    def test_ny_versjon_av_berre_kartet_gir_varsel(self):
        ev = Events()
        u = self.O.Updates({"oppdatering": {}}, ev, lambda: None)
        self.nett("1.1.1", "1.6.141")
        i = u.check()
        self.assertEqual((i["ny"], i["ny_kart"], i["tilgjengeleg"]), (None, "1.6.141", True))
        self.assertIn("kart (SNOWMAN snødjupne) 1.6.141", self.O.tekst(i))
        self.assertTrue(any("Ny versjon tilgjengeleg" in e["tekst"] for e in ev.latest(10)))
        u.check()                                               # same versjon → ikkje nytt varsel i hendingane
        self.assertEqual(sum("Ny versjon tilgjengeleg" in e["tekst"] for e in ev.latest(10)), 1)
        self.nett("1.1.1", "1.6.140")
        self.assertFalse(u.check()["tilgjengeleg"])

    def test_ny_versjonsmappe_blir_funnen(self):
        self.nett("1.1.1", "1.7.0", ("v1.5", "v1.6"))
        self.assertEqual(self.O.latest_kart()[0], "v1.6")
        self.nett("1.1.1", "1.7.0", ("v1.6", "v1.7"))
        self.assertEqual(self.O.latest_kart(), ("v1.7", "1.7.0"))
        self.nett("1.2.0", "1.7.0", ("v1.6", "v1.7"))
        i = self.O.Updates({"oppdatering": {}}, Events(), lambda: None).check()
        self.assertEqual((i["ny"], i["ny_kart"]), ("1.2.0", "1.7.0"))

    def test_oppdater_berre_kartet_startar_berre_kartet(self):
        import io as IO
        b = IO.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("repo-main/kontor/v1.0/konfig.py", 'VERSION = "1.1.1"\n')
            z.writestr("repo-main/pc/v1.6/snowman_pc.py", 'VERSION="1.6.141"\n')
            z.writestr("repo-main/pc/v1.6/data/hemmeleg.json", "{}")
            z.writestr("repo-main/pc/v1.2/gamal.html", "x")
            z.writestr("repo-main/base/v1.0/caster.py", "x")
        class R:
            def __init__(s, data): s.data = data
            def read(s): return s.data
        gamal = self.O.nett.urlopen
        self.O.nett.urlopen = lambda *a, **k: R(b.getvalue())
        kall = {"heile": 0, "kart": 0}
        try:
            u = self.O.Updates({"oppdatering": {}}, Events(), lambda: kall.__setitem__("heile", 1),
                               lambda: kall.__setitem__("kart", 1))
            with mock.patch.object(self.O.subprocess, "run"):
                endra, tekst = u.run_now()
            time.sleep(1.4)
        finally:
            self.O.nett.urlopen = gamal
        self.assertTrue(endra)
        self.assertEqual(kall, {"heile": 0, "kart": 1})
        self.assertIn("1.6.140 → v1.6.141", tekst)
        self.assertEqual(self.O.kart_versjon(), "1.6.141")
        self.assertFalse((self.d / "pc" / "v1.6" / "data").exists())
        self.assertFalse((self.d / "pc" / "v1.2" / "gamal.html").exists())
        self.assertFalse((self.d / "base").exists())


class TestDiverse(unittest.TestCase):
    def test_versjonar_og_passord(self):
        import forbetring
        import oppdatering
        self.assertGreater(oppdatering.vtuple("1.0.10"), oppdatering.vtuple("1.0.9"))
        self.assertLess(forbetring.vtuple("1.6.136"), forbetring.vtuple(konfig.SNOWMAN_MIN))
        self.assertIn("kontor/", oppdatering.RAW_URL)
        h = konfig.hash_pw("hemmeleg")
        self.assertTrue(konfig.check_pw("hemmeleg", h))
        self.assertNotIn("hemmeleg", h)


if __name__ == "__main__":
    unittest.main()
