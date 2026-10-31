# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Testar for SNOWMAN Base. Køyr frå base/v1.0:   python -m unittest discover -s test -v

«Kompatibilitet» testar Base mot NTRIP-klienten i SNOWMAN snødjupne (pc/v1.6/ntripklient.py) – køyr alltid denne
når casteren eller API-et blir endra (sjå konfig.py, SNOWMAN_MIN).
"""
import base64
import os
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
        cfg.first_setup()
        self.pw = "maskin-passord-1"
        cfg.set_user("snowman", self.pw, roles=["ntrip"])
        cfg.set_user("admin", "kontor-passord-1", roles=["kontor"])
        self.akey = ("snowman", self.pw)                 # maskin: Basic med NTRIP-brukaren
        self.kkey = ("admin", "kontor-passord-1")        # kontor: Basic med kontor-brukaren (eller økt)
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
        return [{"namn": "EIGEN", "byte_etter_s": 1.5, "tilbake_etter_s": 0.5,
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


class Ev:
    def __init__(self):
        self.items = []

    def add(self, text, level="info"):
        self.items.append((level, text))


class TestByteAvKjelde(unittest.TestCase):
    """v1.2: ventetid før byte tilbake (H2), alle byte logga (M2), status utan aktiv kjelde (H3), stasjons-ID."""

    def mk(self, extras=False, back=60):
        import straum
        cfg = {"namn": "FJELL", "byte_etter_s": 3, "tilbake_etter_s": back,
               "kjelder": [{"type": "opplasting", "namn": "eigen"}, {"type": "opplasting", "namn": "reserve"}],
               "tillegg": [{"type": "opplasting", "namn": "baner"}] if extras else []}
        ev = Ev()
        return straum.Mountpoint(cfg, ev, None), ev

    def test_ingen_blafring_med_ustabil_eigen_base(self):
        m, ev = self.mk()
        own, res = m.sources
        res.data(epoch(99))
        switches, last = 0, m.active
        for _ in range(10):                          # eigen base sender kvart 4. s – lenger enn byte_etter_s (3 s)
            own.data(epoch(7))
            switches += m.active is not last
            last = m.active
            own.stats.last -= 4
            own.last_frame -= 4
            m.tick()
            res.data(epoch(99))
            switches += m.active is not last
            last = m.active
        self.assertEqual(switches, 0)
        self.assertEqual(m.active.name, "reserve")

    def test_tilbake_når_stabil(self):
        m, ev = self.mk(back=2)
        own, res = m.sources
        res.data(epoch(99))
        own.data(epoch(7))
        self.assertEqual(m.active.name, "reserve")    # ikkje stabil enno
        t0 = time.time()
        while time.time() - t0 < 2.5:
            own.data(epoch(7))
            res.data(epoch(99))
            time.sleep(0.2)
        self.assertEqual(m.active.name, "eigen")
        self.assertTrue(any("stabil" in t for _, t in ev.items), ev.items)

    def test_byte_i_tick_blir_logga_og_talt(self):
        m, ev = self.mk()
        own, res = m.sources
        own.data(epoch(7))
        res.data(epoch(99))
        self.assertEqual(m.active.name, "eigen")
        own.stats.last -= 10
        m.tick()
        self.assertEqual(m.active.name, "reserve")
        self.assertEqual(m.day["bytte"], 1)
        self.assertTrue(any("bytte frå eigen til reserve" in t for _, t in ev.items), ev.items)

    def test_status_når_berre_tillegg_sender(self):
        m, ev = self.mk(extras=True)
        own, _ = m.sources
        own.data(epoch(7))
        own.stats.last -= 10
        m.tick()
        m.extras[0].data(rtcm.frame(eph(1019)))
        self.assertIsNone(m.active)
        self.assertTrue(m.verdict().startswith("FEIL: ingen kjelde"), m.verdict())
        m.status()                                   # skal ikkje krasje

    def test_same_stasjons_id(self):
        m, _ = self.mk()
        own, res = m.sources
        own.data(epoch(7))
        res.data(epoch(7))
        self.assertEqual(m.station_conflict(), {7: ["eigen", "reserve"]})


class TestKjelderTekOver(unittest.TestCase):
    def test_tcp_tenar_ny_tilkopling_tek_over(self):
        import straum
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        m = straum.Mountpoint({"namn": "FJELL", "kjelder": [{"type": "tcp-tenar", "port": port}]}, Ev(), None)
        m.start()
        try:
            time.sleep(0.5)
            gamal = socket.create_connection(("127.0.0.1", port))     # hengande tilkopling som aldri sender
            time.sleep(0.3)
            ny = socket.create_connection(("127.0.0.1", port))
            for _ in range(6):
                ny.sendall(epoch(7))
                time.sleep(0.2)
            self.assertGreater(m.sources[0].bytes_in, 0)
            self.assertEqual(m.active.name, m.sources[0].name)
            gamal.close()
            ny.close()
        finally:
            m.stop()

    def test_ny_opplasting_tek_over_utan_blanding(self):
        import kjelder
        import straum
        m = straum.Mountpoint({"namn": "X", "kjelder": [{"type": "opplasting", "namn": "pi"}]}, Ev(), None)
        src = m.sources[0]
        t1 = src.attach("10.0.0.1")
        t2 = src.attach("10.0.0.2")
        src.push(epoch(1), t1)                        # gammal opplasting blir ignorert
        self.assertEqual(src.bytes_in, 0)
        src.push(epoch(2), t2)
        self.assertGreater(src.bytes_in, 0)
        src.detach(t1)                                # den gamle sin detach endrar ikkje noko
        self.assertEqual(src.current, t2)


class TestVern(unittest.TestCase):
    def test_sperre_etter_mange_feil(self):
        import vern
        cfg = {"vern": {"maks_feil": 3, "minutt": 10, "maks_tilkoplingar": 4, "maks_per_ip": 2}}
        v = vern.Vern(cfg, Ev())
        ip = "203.0.113.5"
        self.assertFalse(v.failed(ip, "t"))
        self.assertFalse(v.failed(ip, "t"))
        self.assertTrue(v.failed(ip, "t"))
        self.assertTrue(v.is_blocked(ip))
        for _ in range(20):
            self.assertFalse(v.failed("127.0.0.1", "t"))
        self.assertFalse(v.is_blocked("127.0.0.1"))
        self.assertTrue(v.open_conn(ip) and v.open_conn(ip))
        self.assertFalse(v.open_conn(ip))            # maks 2 per IP
        v.close_conn(ip)
        self.assertTrue(v.open_conn(ip))

    def test_lokalt_nett(self):
        import vern
        for ip in ("127.0.0.1", "192.168.1.20", "10.1.2.3", "::ffff:192.168.0.5", "fe80::1"):
            self.assertTrue(vern.is_local(ip), ip)
        for ip in ("8.8.8.8", "1.1.1.1", "100.100.1.1"):
            self.assertFalse(vern.is_local(ip), ip)

    def test_hendingslogg_blir_rotert(self):
        import straum
        with tempfile.TemporaryDirectory() as d:
            ev = straum.Events(d)
            ev.MAKS_BYTE = 2000
            for i in range(800):
                ev.add("x" * 50)
            self.assertTrue((Path(d) / "hendingar.log.1").exists())
            self.assertLess((Path(d) / "hendingar.log").stat().st_size, 2000 + 200 * 80)


class TestInnlogging(BaseCase):
    """v1.2: brukarnamn og passord i staden for nøklar."""

    def make_mounts(self):
        return [{"namn": "FJELL", "kjelder": [{"type": "fil", "sti": self.write("a.rtcm3", epoch() * 400),
                                                "byte_per_s": 20000}]}]

    def test_innlogging_økt_og_utlogging(self):
        c, d = self.call("/api/v1/logg-inn", {"brukar": "admin", "passord": "feil-passord"})
        self.assertEqual(c, 401)
        c, d = self.call("/api/v1/logg-inn", {"brukar": "snowman", "passord": self.pw})
        self.assertEqual(c, 401)                     # maskinbrukaren har ikkje kontor-rolla
        c, d = self.call("/api/v1/logg-inn", {"brukar": "ADMIN", "passord": "kontor-passord-1"})
        self.assertEqual(c, 200, d)
        tok = d["okt"]
        self.assertEqual(self.call("/api/v1/brukarar", key=tok)[0], 200)
        self.call("/api/v1/logg-ut", {}, tok)
        self.assertEqual(self.call("/api/v1/brukarar", key=tok)[0], 401)

    def test_roller(self):
        self.assertEqual(self.call("/api/v1/maskiner", key=self.akey)[0], 200)        # ntrip → maskin-API
        self.assertEqual(self.call("/api/v1/brukarar", key=self.akey)[0], 401)        # ntrip → ikkje kontor
        self.assertEqual(self.call("/api/v1/maskiner", key=self.kkey)[0], 200)        # kontor → alt
        self.assertEqual(self.call("/api/v1/maskiner", key=("snowman", "feil"))[0], 401)
        with self.assertRaises(PCN.NtripError):                                          # kontor-brukar ≠ NTRIP
            PCN.open_stream("127.0.0.1", self.port, "FJELL", "admin", "kontor-passord-1", "1", "t")

    def test_brukarar_på_kontorsida(self):
        c, d = self.call("/api/v1/brukar", {"namn": "pb2", "passord": "kort"}, self.kkey)
        self.assertEqual(c, 400)
        c, d = self.call("/api/v1/brukar", {"namn": "pb2", "passord": "pb2-passord", "roller": ["ntrip"]}, self.kkey)
        self.assertEqual(c, 200, d)
        st = PCN.open_stream("127.0.0.1", self.port, "FJELL", "pb2", "pb2-passord", "1", "t")
        st.close()
        self.call("/api/v1/brukar", {"namn": "pb2", "passord": "nytt-passord-2"}, self.kkey)
        with self.assertRaises(PCN.NtripError):
            PCN.open_stream("127.0.0.1", self.port, "FJELL", "pb2", "pb2-passord", "1", "t")
        c, d = self.call("/api/v1/brukarar", key=self.kkey)
        self.assertNotIn("hash", json.dumps(d))
        self.assertEqual(self.call("/api/v1/brukar/fjern", {"namn": "admin"}, self.kkey)[0], 400)   # siste admin
        self.assertTrue(self.call("/api/v1/brukar/fjern", {"namn": "pb2"}, self.kkey)[1]["ok"])

    def test_kommandoar_medan_base_køyrer(self):
        """H1: kommandoar gjeld med éin gong og blir ikkje overskrivne når kontorsida lagrar."""
        d = str(self.dir / "data")
        SB.main(["--data", d, "brukar", "legg-til", "PB1", "--passord", "pb1-passord"])
        SB.main(["--data", d, "brukar", "passord", "admin", "--passord", "nytt-kontor-2"])
        SB.main(["--data", d, "mountpoint", "ny", "CLI", "--rele", f"127.0.0.1:{self.port}/FJELL",
                 "--brukar", "snowman", "--passord", self.pw])
        t0 = time.time()
        while time.time() - t0 < 5 and "CLI" not in self.base.mounts:
            time.sleep(0.2)
        self.assertIn("CLI", self.base.mounts)
        self.assertTrue(self.base.cfg.user_ok("PB1", "pb1-passord", "FJELL"))
        self.assertEqual(self.call("/api/v1/brukarar", key=self.kkey)[0], 401)              # gammalt passord
        nk = ("admin", "nytt-kontor-2")
        self.assertEqual(self.call("/api/v1/ai/innstillingar", {"leverandor": "av"}, nk)[0], 200)   # kontor lagrar
        lagra = konfig.Config(self.dir / "data")
        self.assertIsNotNone(lagra.check_user("PB1", "pb1-passord"))
        self.assertIsNotNone(lagra.check_user("admin", "nytt-kontor-2"))
        self.assertIn("CLI", [m["namn"] for m in lagra["mountpoints"]])
        st = PCN.open_stream("127.0.0.1", self.port, "CLI", "PB1", "pb1-passord", "auto", "t")
        self.assertIn(1005, types_in(read_for(st, 3.0)))
        st.close()

    def test_berre_éin_base_per_port(self):
        with self.assertRaises(OSError):
            SB.SnowmanBase(self.dir / "data2", self.port, 0).start()


class TestFørsteAdministrator(BaseCase):
    def setUp(self):
        super().setUp()
        self.base.cfg.update(lambda d: d["brukarar"].clear())

    def test_oppsett_frå_lokalt_nett(self):
        c, d = self.call("/api/v1/oppsett")
        self.assertTrue(d["treng_admin"])
        self.assertTrue(d["lokal"])
        c, d = self.call("/api/v1/oppsett", {"brukar": "hans", "passord": "hans-passord", "ntrip_brukar": "pb600",
                                             "ntrip_passord": "pb600-passord"})
        self.assertEqual(c, 200, d)
        self.assertEqual(self.call("/api/v1/brukarar", key=d["okt"])[0], 200)
        c, d = self.call("/api/v1/oppsett", {"brukar": "inntrengar", "passord": "inntrengar-1"})
        self.assertEqual(c, 409)                     # administrator finst alt
        self.assertFalse(self.call("/api/v1/oppsett")[1]["treng_admin"])
        self.assertTrue(self.base.cfg.user_ok("pb600", "pb600-passord", "X"))

    def test_gamle_nøklar_blir_ignorerte(self):
        p = self.dir / "data" / "base.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["noklar"] = {"anlegg": konfig.hash_pw("gammal"), "kontor": konfig.hash_pw("gammal")}
        data["brukarar"] = [{"namn": "snowman", "hash": konfig.hash_pw("gammalt-pw"), "mountpoints": ["*"]}]
        p.write_text(json.dumps(data), encoding="utf-8")
        cfg = konfig.Config(self.dir / "data")
        self.assertNotIn("noklar", cfg.data)
        self.assertEqual(cfg.find_user("snowman")["roller"], ["ntrip"])          # NTRIP-brukaren held fram
        self.assertFalse(cfg.has_admin())


class TestTilgang(BaseCase):
    def test_ddns_og_namn(self):
        import tilgang
        self.assertEqual(tilgang.host_from_url("https://www.duckdns.org/update?domains=fjellsatra&token=x"),
                         "fjellsatra.duckdns.org")

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"OK")

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.base.cfg.update(lambda d: d["ddns"].__setitem__(
                "url", f"http://127.0.0.1:{srv.server_address[1]}/update?hostname=localhost"))
            r = self.base.tilgang.ddns_now()["ddns"]
            self.assertTrue(r["ok"], r)
            self.assertEqual(r["peikar_til"], "127.0.0.1")
        finally:
            srv.shutdown()
        self.assertEqual(self.call("/api/v1/ddns", {"url": "http://usikker"}, self.kkey)[0], 400)
        c, d = self.call("/api/v1/tilgang", key=self.kkey)
        self.assertEqual(c, 200)
        self.assertEqual(d["caster_port"], self.port)


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
