# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Testar for SNOWMAN Base. Køyr frå base/v1.0:   python -m unittest discover -s test -v

«Kompatibilitet» testar Base mot NTRIP-klienten i SNOWMAN snødjupne (pc/v1.6/ntripklient.py) – køyr alltid denne
når casteren eller API-et blir endra (sjå konfig.py, SNOWMAN_MIN).
"""
import base64
import http.server
import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import rtcm                                   # noqa: E402
import konfig                                 # noqa: E402
import snowman_base as SB                     # noqa: E402

PC = HERE.parent.parent / "pc" / "v1.6" / "ntripklient.py"
spec = importlib.util.spec_from_file_location("pc_ntripklient", PC)
PCN = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PCN)

LAT, LON, H = 62.3802, 6.7811, 702.35
GGA = "$GPGGA,120000.00,6222.8000,N,00646.8000,E,4,20,0.6,700.0,M,40.0,M,1.0,0001*55"


def msm(t, station=7, nsat=4):
    p = bytearray(40)
    rtcm.setbits(p, 0, 12, t)
    rtcm.setbits(p, 12, 12, station)
    rtcm.setbits(p, 73, 32, (1 << nsat) - 1)
    return bytes(p)


def eph(t=1019):
    p = bytearray(61)
    rtcm.setbits(p, 0, 12, t)
    return bytes(p)


def epoch(station=7, lat=LAT, lon=LON, h=H):
    x, y, z = rtcm.geo_to_ecef(lat, lon, h)
    return (rtcm.frame(rtcm.make_1005(station, x, y, z)) + rtcm.frame(msm(1077, station))
            + rtcm.frame(msm(1087, station, 3)) + rtcm.frame(msm(1097, station, 5)) + rtcm.frame(msm(1127, station, 6)))


def types_in(data):
    return [rtcm.msg_type(f) for f in rtcm.Framer().feed(data)]


def read_for(stream, secs):
    got, t0 = b"", time.time()
    while time.time() - t0 < secs:
        got += stream.read()
    return got


class BaseCase(unittest.TestCase):
    """Startar ein Base med gitte mountpoints på tilfeldige portar."""

    mounts = []

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        cfg = konfig.Config(self.dir / "data")
        lines = cfg.first_setup()
        self.pw = next(l for l in lines if "NTRIP" in l).split("/ ")[1].strip()
        self.akey = next(l for l in lines if "Anleggsnøkkel" in l).split(": ")[-1].strip()
        self.kkey = next(l for l in lines if "Kontornøkkel" in l).split(": ")[-1].strip()
        cfg.data["mountpoints"] = json.loads(json.dumps(self.make_mounts()))
        cfg.data["oppdatering"]["sjekk"] = False
        cfg.save()
        self.base = SB.SnowmanBase(self.dir / "data", 0, 0).start()
        self.port = self.base.caster_port
        self.web = f"http://127.0.0.1:{self.base.web_port}"

    def tearDown(self):
        self.base.stop()
        time.sleep(0.2)
        self.tmp.cleanup()

    def make_mounts(self):
        return []

    def write(self, name, data):
        p = self.dir / name
        p.write_bytes(data)
        return str(p)

    def call(self, path, body=None, key=None, method=None, raw=None, headers=None):
        h = dict(headers or {})
        if key:
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


class TestRtcm(unittest.TestCase):
    def test_framer_finn_rammer_i_stoy(self):
        good = rtcm.frame(msm(1077))
        bad = bytearray(rtcm.frame(msm(1087)))
        bad[10] ^= 0xFF
        f = rtcm.Framer()
        out = f.feed(b"$GNGGA,tekst\r\n" + good[:5]) + f.feed(good[5:] + bytes(bad) + b"\xb5\x62ubx" + good)
        self.assertEqual(out, [good, good])
        self.assertEqual(f.crc_err, 1)

    def test_baseposisjon_og_satellittar(self):
        s = rtcm.Stats()
        for fr in rtcm.Framer().feed(epoch()):
            s.add(fr)
        r = s.summary()
        self.assertEqual(r["base"]["station"], 7)
        self.assertAlmostEqual(r["base"]["lat"], LAT, places=6)
        self.assertAlmostEqual(r["base"]["h"], H, delta=0.01)
        self.assertEqual(r["sats"], {"GPS": 4, "GLONASS": 3, "Galileo": 5, "BeiDou": 6})
        self.assertFalse(r["msm3"])


class TestKompatibilitet(BaseCase):
    """Base mot NTRIP-klienten i SNOWMAN snødjupne (pc/v1.6)."""

    def make_mounts(self):
        f = self.write("t.rtcm3", (epoch() + rtcm.frame(eph())) * 40)
        return [{"namn": "FJELL", "skildring": "Fjellsætra", "kjelder": [{"type": "fil", "sti": f, "byte_per_s": 40000}],
                 "innmalt": {"lat": LAT, "lon": LON, "h": H}}]

    def test_ntrip1_ntrip2_auto(self):
        time.sleep(0.5)
        for ver in ("1", "2", "auto"):
            st = PCN.open_stream("127.0.0.1", self.port, "FJELL", "snowman", self.pw, ver, "test", GGA)
            data = read_for(st, 1.0)
            st.close()
            t = types_in(data)
            self.assertIn(1005, t, ver)
            self.assertIn(1077, t, ver)
            self.assertEqual(rtcm.Framer().feed(data) and rtcm.Framer().crc_err, 0)
            self.assertEqual(st.proto, "NTRIP 2" if ver == "2" else "NTRIP 1")

    def test_kjeldetabell(self):
        time.sleep(0.6)
        r = PCN.fetch_sourcetable("127.0.0.1", self.port, "snowman", self.pw, lat=LAT, lon=LON)
        m = r["mounts"][0]
        self.assertEqual(m["mountpoint"], "FJELL")
        self.assertEqual(m["format"], "RTCM 3.3")
        self.assertIn("GPS", m["systems"])
        self.assertLess(m["km"], 1)

    def test_feil_passord_og_ukjent_mountpoint(self):
        with self.assertRaises(PCN.NtripError) as e:
            PCN.open_stream("127.0.0.1", self.port, "FJELL", "snowman", "feil", "1", "t")
        self.assertEqual(e.exception.code, "auth")
        with self.assertRaises(PCN.NtripError) as e:
            PCN.open_stream("127.0.0.1", self.port, "FINST", "snowman", self.pw, "auto", "t")
        self.assertEqual(e.exception.code, "mount")

    def test_gga_frå_maskina_blir_lagra(self):
        st = PCN.open_stream("127.0.0.1", self.port, "FJELL", "snowman", self.pw, "1", "t")
        st.send_gga(GGA)
        time.sleep(1.5)
        c = self.base.mounts["FJELL"].status()["klientar"][0]
        st.close()
        self.assertEqual(c["gga"]["kvalitet"], 4)
        self.assertAlmostEqual(c["gga"]["lat"], 62.38, places=3)

    def test_basekontroll_og_vurdering(self):
        time.sleep(0.6)
        m = self.base.mounts["FJELL"]
        self.assertEqual(m.base_check()["vurdering"], "OK")
        self.assertTrue(m.verdict().startswith("OK"), m.verdict())
        m.cfg["innmalt"] = {"lat": LAT, "lon": LON, "h": H + 0.30}
        self.assertTrue(m.base_check()["vurdering"].startswith("ÅTVARING"))


class TestOpplastingOgReserve(BaseCase):
    def make_mounts(self):
        reserve = self.write("reserve.rtcm3", epoch(station=99) * 40)
        upw = "opp123"
        self.upw = upw
        return [{"namn": "EIGEN", "byte_etter_s": 1.5,
                 "kjelder": [{"type": "opplasting", "namn": "pi", "hash": konfig.hash_pw(upw)},
                             {"type": "fil", "namn": "reserve", "sti": reserve, "byte_per_s": 20000}],
                 "tillegg": [{"type": "fil", "namn": "baner", "sti": self.write("eph.rtcm3",
                                                                              (rtcm.frame(eph(1019)) + epoch(55)) * 20),
                              "byte_per_s": 20000}]}]

    def test_reserve_så_opplasting_og_tilbake(self):
        m = self.base.mounts["EIGEN"]
        time.sleep(0.8)
        self.assertEqual(m.active.name, "reserve")
        # NTRIP 1-opplasting (SOURCE) tek over som første prioritet
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(f"SOURCE {self.upw} /EIGEN\r\nSource-Agent: NTRIP str2str\r\n\r\n".encode())
        self.assertIn(b"ICY 200 OK", s.recv(100))
        for _ in range(15):
            s.sendall(epoch(station=7))
            time.sleep(0.1)
        self.assertEqual(m.active.name, "pi")
        self.assertEqual(m.out.base["station"], 7)
        s.close()
        time.sleep(2.2)
        m.tick()
        time.sleep(0.3)
        self.assertEqual(m.active.name, "reserve")
        self.assertGreaterEqual(m.day["bytte"], 2)
        m.cfg["innmalt"] = {"lat": LAT, "lon": LON, "h": H}      # gjeld eigen base, ikkje reserven (stasjon 99)
        self.assertIsNone(m.base_check())
        self.assertTrue(m.verdict().startswith("ÅTVARING: reserve i bruk"), m.verdict())

    def test_tillegg_gir_berre_baner(self):
        time.sleep(0.8)
        st = PCN.open_stream("127.0.0.1", self.port, "EIGEN", "snowman", self.pw, "1", "t")
        data = read_for(st, 1.0)
        st.close()
        frames = rtcm.Framer().feed(data)
        stations = {rtcm.bits(f[3:], 12, 12) for f in frames if rtcm.msg_type(f) in (1005, 1077)}
        self.assertIn(1019, types_in(data))
        self.assertEqual(stations, {99})               # ingen observasjonar frå tillegget (stasjon 55)

    def test_ntrip2_opplasting_chunked(self):
        s = socket.create_connection(("127.0.0.1", self.port))
        auth = base64.b64encode(f"pi:{self.upw}".encode()).decode()
        s.sendall(("POST /EIGEN HTTP/1.1\r\nHost: x\r\nNtrip-Version: Ntrip/2.0\r\nAuthorization: Basic " + auth +
                   "\r\nTransfer-Encoding: chunked\r\n\r\n").encode())
        self.assertIn(b"200 OK", s.recv(200))
        for _ in range(10):
            d = epoch(station=7)
            s.sendall(f"{len(d):X}\r\n".encode() + d + b"\r\n")
            time.sleep(0.1)
        self.assertEqual(self.base.mounts["EIGEN"].active.name, "pi")
        s.close()

    def test_feil_opplastingspassord(self):
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(b"SOURCE feil /EIGEN\r\n\r\n")
        self.assertIn(b"ERROR", s.recv(100))
        s.close()


class TestMountpointFraKontor(BaseCase):
    """Mountpoints lagde og endra frå kontorsida (manuelt), tekne i bruk utan omstart."""

    def make_mounts(self):
        return [{"namn": "FJELL", "kjelder": [{"type": "fil", "namn": "opptak", "sti": self.write("a.rtcm3", epoch() * 400),
                                                "byte_per_s": 20000}]}]

    def rele(self, **kw):
        k = {"type": "ntrip", "caster": "127.0.0.1", "port": self.port, "mountpoint": "FJELL",
             "brukar": "snowman", "passord": self.pw}
        k.update(kw)
        return k

    def test_krev_kontornokkel(self):
        self.assertEqual(self.call("/api/v1/mountpoints", key=self.akey)[0], 401)
        self.assertEqual(self.call("/api/v1/mountpoint", {"namn": "X", "kjelder": [self.rele()]}, self.akey)[0], 401)

    def test_nytt_rele_manuelt_og_snowman_les_det(self):
        c, d = self.call("/api/v1/mountpoint", {"namn": "TH2", "skildring": "Relé", "kjelder": [self.rele()]}, self.kkey)
        self.assertEqual(c, 200, d)
        self.assertNotIn('"passord"', json.dumps(d))                     # passord kjem aldri tilbake
        self.assertNotIn(self.pw, json.dumps(d))
        self.assertIn("TH2", self.base.mounts)
        st = PCN.open_stream("127.0.0.1", self.port, "TH2", "snowman", self.pw, "auto", "test")
        self.assertIn(1005, types_in(read_for(st, 3.0)))                 # SNOWMAN-klienten får korreksjonar
        st.close()
        c, d = self.call("/api/v1/mountpoints", key=self.kkey)
        th2 = next(m for m in d["mountpoints"] if m["namn"] == "TH2")
        self.assertTrue(th2["kjelder"][0]["har_passord"])
        self.assertNotIn(self.pw, json.dumps(d))
        lagra = json.loads((self.dir / "data" / "base.json").read_text(encoding="utf-8"))
        self.assertEqual(next(m for m in lagra["mountpoints"] if m["namn"] == "TH2")["kjelder"][0]["passord"], self.pw)

    def test_endre_utan_passord_beheld_det_og_klientar_blir_kopla_om(self):
        self.call("/api/v1/mountpoint", {"namn": "R", "kjelder": [self.rele()]}, self.kkey)
        kid = self.call("/api/v1/mountpoints", key=self.kkey)[1]["mountpoints"][1]["kjelder"][0]["id"]
        st = PCN.open_stream("127.0.0.1", self.port, "R", "snowman", self.pw, "1", "test")
        read_for(st, 1.0)
        gamal = self.base.mounts["R"]
        c, d = self.call("/api/v1/mountpoint", {"gamalt_namn": "R", "namn": "R", "byte_etter_s": 5,
                                                "kjelder": [self.rele(id=kid, passord="")]}, self.kkey)
        self.assertEqual(c, 200, d)
        self.assertTrue(gamal.closed)
        self.assertIsNot(self.base.mounts["R"], gamal)
        self.assertEqual(self.base.mounts["R"].cfg["kjelder"][0]["passord"], self.pw)
        self.assertEqual(self.base.mounts["R"].cfg["kjelder"][0]["id"], kid)
        time.sleep(1.5)
        self.assertEqual(len(gamal.clients), 0)                         # den gamle straumen er stengd
        st.close()
        st = PCN.open_stream("127.0.0.1", self.port, "R", "snowman", self.pw, "auto", "test")
        self.assertIn(1005, types_in(read_for(st, 3.0)))
        st.close()

    def test_kjeldetabell_via_base(self):
        c, d = self.call("/api/v1/kjeldetabell", {"caster": "127.0.0.1", "port": self.port, "brukar": "snowman",
                                                  "passord": self.pw}, self.kkey)
        self.assertTrue(d["ok"], d)
        self.assertIn("FJELL", [m["mountpoint"] for m in d["mountpoints"]])
        c, d = self.call("/api/v1/kjeldetabell", {"caster": "127.0.0.1", "port": 1}, self.kkey)
        self.assertFalse(d["ok"])

    def test_kontroll_av_det_som_blir_skrive_inn(self):
        def feil(body):
            c, d = self.call("/api/v1/mountpoint", body, self.kkey)
            self.assertEqual(c, 400, d)
            return d["feil"]
        self.assertIn("Namnet", feil({"namn": "Fjell sætra", "kjelder": [self.rele()]}))
        self.assertIn("finst alt", feil({"namn": "fjell", "kjelder": [self.rele()]}))
        self.assertIn("minst éi kjelde", feil({"namn": "A", "kjelder": []}))
        self.assertIn("mountpoint", feil({"namn": "A", "kjelder": [self.rele(mountpoint="")]}))
        self.assertIn("casteradressa", feil({"namn": "A", "kjelder": [self.rele(caster="http://a b")]}))
        self.assertIn("i bruk av Base", feil({"namn": "A", "kjelder": [{"type": "tcp-tenar",
                                                                          "port": self.base.web_port}]}))
        self.assertIn("COM5", feil({"namn": "A", "kjelder": [{"type": "seriell", "port": "feil port"}]}))
        self.assertIn("ukjend type", feil({"namn": "A", "kjelder": [{"type": "fil", "sti": "/etc/passwd"}]}))
        self.assertNotIn("A", self.base.mounts)

    def test_opplasting_gir_passord_ein_gong(self):
        c, d = self.call("/api/v1/mountpoint", {"namn": "PI", "kjelder": [{"type": "opplasting"}]}, self.kkey)
        self.assertEqual(c, 200, d)
        pw = d["melding"].split("PI: ")[1].split(" ")[0]
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(f"SOURCE {pw} /PI\r\nSource-Agent: NTRIP str2str\r\n\r\n".encode())
        self.assertIn(b"ICY 200 OK", s.recv(100))
        for _ in range(10):
            s.sendall(epoch(station=7))
            time.sleep(0.05)
        time.sleep(0.3)
        self.assertEqual(self.base.mounts["PI"].active.name, "opplasting")
        s.close()
        kid = self.call("/api/v1/mountpoints", key=self.kkey)[1]["mountpoints"][1]["kjelder"][0]["id"]
        c, d = self.call("/api/v1/mountpoint", {"gamalt_namn": "PI", "namn": "PI", "kjelder": [{"type": "opplasting",
                                                                                                  "id": kid}]}, self.kkey)
        self.assertEqual(d["melding"], "")                               # passordet blir ståande

    def test_slett_og_avspeling_blir_ståande(self):
        kid = self.call("/api/v1/mountpoints", key=self.kkey)[1]["mountpoints"][0]["kjelder"][0]["id"]
        c, d = self.call("/api/v1/mountpoint", {"gamalt_namn": "FJELL", "namn": "FJELL",
                                                "kjelder": [{"type": "fil", "id": kid}, self.rele(mountpoint="X")]},
                         self.kkey)
        self.assertEqual(c, 200, d)
        self.assertEqual(self.base.mounts["FJELL"].cfg["kjelder"][0]["type"], "fil")
        self.assertTrue(self.call("/api/v1/mountpoint/fjern", {"namn": "FJELL"}, self.kkey)[1]["ok"])
        self.assertNotIn("FJELL", self.base.mounts)
        with self.assertRaises(PCN.NtripError):
            PCN.open_stream("127.0.0.1", self.port, "FJELL", "snowman", self.pw, "auto", "t")


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


class TestApi(BaseCase):
    def make_mounts(self):
        return [{"namn": "FJELL", "kjelder": [{"type": "fil", "sti": self.write("a.rtcm3", epoch() * 40),
                                                "byte_per_s": 20000}]}]

    def test_info_utan_nokkel(self):
        c, d = self.call("/api/v1/info")
        self.assertEqual(c, 200)
        self.assertEqual(d["api"], konfig.API_VERSION)
        self.assertEqual(d["snowman_min"], konfig.SNOWMAN_MIN)
        self.assertIn("deling-v1", d["funksjonar"])

    def test_nokkel_krevst(self):
        self.assertEqual(self.call("/api/v1/maskiner")[0], 401)
        self.assertEqual(self.call("/api/v1/maskiner", key="feil")[0], 401)
        self.assertEqual(self.call("/api/v1/forslag", key=self.akey)[0], 401)     # kontor krev kontornøkkel
        self.assertEqual(self.call("/api/v1/maskiner", key=self.akey)[0], 200)

    def test_hjarteslag_og_maskinplassar(self):
        c, d = self.call("/api/v1/maskin", {"id": "PB1", "namn": "PB 600 nr 1", "versjon": "1.8.0", "fix": 4,
                                            "fixdel": 0.92, "lat": LAT, "lon": LON}, self.akey)
        self.assertEqual(c, 200)
        self.assertEqual(d["snowman_min"], konfig.SNOWMAN_MIN)
        self.base.cfg["deling"]["maskinplassar"] = 1
        self.assertEqual(self.call("/api/v1/maskin", {"id": "PB2"}, self.akey)[0], 403)
        self.assertEqual(self.call("/api/v1/maskin", {"id": "PB1"}, self.akey)[0], 200)

    def test_maalingar_berre_gyldige_og_inkrementelt(self):
        now = time.time()
        pts = [{"t": now, "lat": LAT, "lon": LON, "h": 700, "djupne": 1.2, "fix": 4, "kalibrert": True},
               {"t": now, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 5, "kalibrert": True},          # FLOAT
               {"t": now, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 4, "kalibrert": False},          # ikkje kalibrert
               {"t": now, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 4, "kalibrert": True, "demo": True},
               {"t": now - 13 * 3600, "lat": LAT, "lon": LON, "djupne": 1.0, "fix": 4, "kalibrert": True}]
        c, d = self.call("/api/v1/maalingar", {"maskin": "PB1", "punkt": pts}, self.akey)
        self.assertEqual((d["lagra"], d["avvist"]), (1, 4))
        c, d = self.call("/api/v1/maalingar?etter=0", key=self.akey)
        self.assertEqual(len(d["maalingar"]), 1)
        c, d2 = self.call(f"/api/v1/maalingar?etter={d['siste']}", key=self.akey)
        self.assertEqual(d2["maalingar"], [])
        c, d3 = self.call("/api/v1/maalingar?etter=0&utan=PB1", key=self.akey)
        self.assertEqual(d3["maalingar"], [])

    def test_anleggspakke(self):
        import io
        import zipfile
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, "w") as z:
            z.writestr("trasear.json", "[]")
        zipdata = bio.getvalue()
        self.assertEqual(self.call("/api/v1/anleggspakke", raw=zipdata, key=self.akey)[0], 401)
        self.assertEqual(self.call("/api/v1/anleggspakke", raw=b"ikkje zip", key=self.kkey)[0], 400)
        c, d = self.call("/api/v1/anleggspakke", raw=zipdata, key=self.kkey, headers={"X-Merknad": "Ny%20tras%C3%A9"})
        self.assertEqual(d["pakke"]["versjon"], 1)
        self.call("/api/v1/anleggspakke", raw=zipdata, key=self.kkey)
        c, d = self.call("/api/v1/anleggspakke", key=self.akey)
        self.assertEqual(d["pakke"]["versjon"], 2)
        self.call("/api/v1/anleggspakke/aktiv", {"versjon": 1}, self.kkey)
        c, d = self.call("/api/v1/anleggspakke", key=self.akey)
        self.assertEqual((d["pakke"]["versjon"], d["pakke"]["merknad"]), (1, "Ny trasé"))
        c, b = self.call("/api/v1/anleggspakke/fil", key=self.akey)
        self.assertEqual(b, zipdata)

    def test_forslag_frå_maskin(self):
        c, d = self.call("/api/v1/forslag", {"maskin": "PB1", "type": "program", "tekst": "Større tal på HUD"}, self.akey)
        self.assertTrue(d["ok"])
        c, d = self.call("/api/v1/forslag", key=self.kkey)
        self.assertEqual(d["forslag"][0]["tekst"], "Større tal på HUD")
        self.call("/api/v1/forslag/svar", {"id": d["forslag"][0]["id"], "status": "godkjent"}, self.kkey)
        md = self.call("/api/v1/forbetringar.md", key=self.kkey)[1].decode()
        self.assertIn("Større tal på HUD", md)

    def test_forbetringar_reglar(self):
        time.sleep(0.5)
        c, d = self.call("/api/v1/forbetringar/analyser", {}, self.kkey)
        self.assertGreater(d["tal"], 0)
        c, d = self.call("/api/v1/forbetringar", key=self.kkey)
        keys = {r["nokkel"] for r in d["forbetringar"]}
        self.assertIn("FJELL:ikkje-innmalt", keys)         # basen er ikkje kontrollert mot innmålt punkt
        self.assertIn("FJELL:ingen-baner", keys)            # straumen manglar satellittbaner
        self.assertIn("ai-av", keys)
        self.call("/api/v1/forbetringar/status", {"nokkel": "ai-av", "status": "avvist"}, self.kkey)
        c, d = self.call("/api/v1/forbetringar", key=self.kkey)
        self.assertNotIn("ai-av", {r["nokkel"] for r in d["forbetringar"]})
        self.assertTrue(d["dagar"])

    def test_ai_anonymisert_og_lokal_modell(self):
        self.call("/api/v1/maskin", {"id": "PB1", "namn": "Kjetil sin PB", "versjon": "1.8.0"}, self.akey)
        self.base.store.upsert_improvement({"nokkel": "x", "kategori": "drift", "alvor": "låg",
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
            self.assertNotIn(self.pw, p["melding"])
            c, d = self.call("/api/v1/ai/analyser", {}, self.kkey)
            self.assertEqual(d["tal"], 1)
            c, d = self.call("/api/v1/forbetringar", key=self.kkey)
            ai = [r for r in d["forbetringar"] if r["kjelde"] == "ai"]
            self.assertEqual(ai[0]["kategori"], "snowman")
            sent = json.dumps(FakeOllama.seen[-1], ensure_ascii=False)
            self.assertNotIn("Kjetil", sent)
        finally:
            srv.shutdown()

    def test_status_og_sider(self):
        c, d = self.call("/api/status")
        self.assertEqual(d["mountpoints"][0]["namn"], "FJELL")
        self.assertNotIn("hash", json.dumps(self.call("/api/v1/konfig", key=self.kkey)[1]))
        for p in ("/", "/kontor/", "/vendor/leaflet.js"):
            with urllib.request.urlopen(self.web + p, timeout=5) as r:
                self.assertEqual(r.status, 200)


class TestDiverse(unittest.TestCase):
    def test_versjonar(self):
        import oppdatering
        self.assertGreater(oppdatering.vtuple("1.0.10"), oppdatering.vtuple("1.0.9"))
        import forbetring
        self.assertLess(forbetring.vtuple("1.6.112"), forbetring.vtuple(konfig.SNOWMAN_MIN))

    def test_passord_hash(self):
        h = konfig.hash_pw("hemmeleg")
        self.assertTrue(konfig.check_pw("hemmeleg", h))
        self.assertFalse(konfig.check_pw("feil", h))
        self.assertNotIn("hemmeleg", h)

    def test_gga_for_vrs(self):
        from kjelder import make_gga
        from caster import parse_gga
        lat, lon, q, n = parse_gga(make_gga(LAT, LON, 700))
        self.assertAlmostEqual(lat, LAT, places=5)
        self.assertAlmostEqual(lon, LON, places=5)


if __name__ == "__main__":
    unittest.main()
