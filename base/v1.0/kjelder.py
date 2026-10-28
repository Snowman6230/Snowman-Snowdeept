# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Kjelder til korreksjonsstraumane i SNOWMAN Base.

    seriell     GNSS-mottakaren på USB/seriellport (t.d. ZED-F9P eller UM980 i basemodus)
    tcp         mottakar eller anna eining som sender på nettverket (Base koplar seg til)
    tcp-tenar   Base lyttar på ein port, og ei eining sender inn (t.d. str2str på ein Raspberry Pi ved antenna)
    opplasting  NTRIP-opplasting til casteren i Base (SOURCE / POST) – t.d. frå ein Pi eller ein annan base
    ntrip       relé frå ein annan caster (t.d. TH eller Kartverket CPOS) – reserve, eller før eigen base er klar
    fil         avspeling av eit opptak (berre test og demo – mountpointet blir merkt TEST)

Alle kjeldene les byte, finn RTCM-rammer og sender rammene til mountpointet. Base sender aldri noko til mottakaren.
"""
import socket
import threading
import time
from pathlib import Path

import ntripklient
from rtcm import Framer, Stats


def make_gga(lat, lon, h=0.0, t=None):
    """GGA-linje med fast posisjon – til castarar med nettverks-RTK (VRS) som krev posisjonen til «roveren»."""
    t = time.gmtime(t or time.time())
    la, lo = abs(lat), abs(lon)
    body = ("GPGGA,%02d%02d%02d.00,%02d%08.5f,%s,%03d%08.5f,%s,1,12,1.0,%.1f,M,0.0,M,,"
            % (t.tm_hour, t.tm_min, t.tm_sec, int(la), (la - int(la)) * 60, "N" if lat >= 0 else "S",
               int(lo), (lo - int(lo)) * 60, "E" if lon >= 0 else "W", h))
    ck = 0
    for c in body:
        ck ^= ord(c)
    return f"${body}*{ck:02X}"


class Source:
    """Felles for alle kjelder: tråd, statistikk, rådatalogg og vidaresending av rammer."""

    kind = "?"

    def __init__(self, cfg, mount, events, rawlog=None, role="kjelde"):
        self.cfg = cfg
        self.mount = mount               # Mountpoint (straum.py)
        self.events = events
        self.rawlog = rawlog             # RawLog eller None
        self.role = role                 # "kjelde" | "tillegg"
        self.name = cfg.get("namn") or self.default_name()
        self.framer = Framer()
        self.stats = Stats()
        self.connected = False
        self.err = ""
        self.since = None
        self.bytes_in = 0
        self.stop_ev = threading.Event()
        self.thread = None

    def default_name(self):
        return self.kind

    def label(self):
        return f"{self.mount.name}/{self.name}"

    def start(self):
        self.thread = threading.Thread(target=self._run_forever, name=self.label(), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_ev.set()

    def _run_forever(self):
        while not self.stop_ev.is_set():
            try:
                self.run()
            except Exception as e:
                self.err = str(e)[:200]
            if self.connected:
                self.events.add(f"{self.label()}: samband borte ({self.err or 'lukka'})", "feil")
            self.connected = False
            self.stop_ev.wait(self.cfg.get("ventetid_s", 5))

    def up(self, text):
        self.connected = True
        self.err = ""
        self.since = time.time()
        self.events.add(f"{self.label()}: {text}", "ok")

    def data(self, chunk):
        """Rå byte inn frå kjelda."""
        if not chunk:
            return
        self.bytes_in += len(chunk)
        if self.rawlog:
            self.rawlog.write(self.mount.name, self.name, chunk)
        now = time.time()
        frames = self.framer.feed(chunk)
        for fr in frames:
            self.stats.add(fr, now)
        if frames:
            self.mount.feed(self, frames)

    def age(self, now=None):
        return (now or time.time()) - self.stats.last if self.stats.last else None

    def status(self):
        s = self.stats.summary()
        s.update({"namn": self.name, "type": self.kind, "rolle": self.role, "tilkopla": self.connected,
                  "feil": self.err, "sidan": self.since, "bytesInn": self.bytes_in, "crcFeil": self.framer.crc_err,
                  "anna": self.framer.junk, "kjelde": self.where()})
        return s

    def where(self):
        return ""

    def run(self):
        raise NotImplementedError


class SerialSource(Source):
    kind = "seriell"

    def where(self):
        return f"{self.cfg.get('port')} {self.cfg.get('baud', 115200)} baud"

    def run(self):
        try:
            import serial
        except ImportError:
            self.err = "pyserial manglar – køyr: pip install pyserial"
            self.stop_ev.wait(30)
            return
        with serial.Serial(self.cfg["port"], int(self.cfg.get("baud", 115200)), timeout=1) as sp:
            self.up(f"opna {self.where()}")
            while not self.stop_ev.is_set():
                self.data(sp.read(4096))


class TcpSource(Source):
    kind = "tcp"

    def where(self):
        return f"{self.cfg.get('vert')}:{self.cfg.get('port')}"

    def run(self):
        with socket.create_connection((self.cfg["vert"], int(self.cfg["port"])), timeout=10) as s:
            s.settimeout(2)
            self.up(f"kopla til {self.where()}")
            quiet = 0.0
            while not self.stop_ev.is_set():
                try:
                    d = s.recv(4096)
                except socket.timeout:
                    quiet += 2
                    if quiet > 60:
                        raise ConnectionError("ingen data på 60 s")
                    continue
                if not d:
                    raise ConnectionError("eininga lukka sambandet")
                quiet = 0.0
                self.data(d)


class TcpServerSource(Source):
    """Base lyttar; éi eining sender inn om gongen (ny tilkopling tek over)."""
    kind = "tcp-tenar"

    def where(self):
        return f"lyttar på port {self.cfg.get('port')}"

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.cfg.get("adresse", "0.0.0.0"), int(self.cfg["port"])))
        srv.listen(2)
        srv.settimeout(1)
        self.listening = True
        try:
            while not self.stop_ev.is_set():
                try:
                    c, addr = srv.accept()
                except socket.timeout:
                    continue
                c.settimeout(2)
                self.up(f"eining kopla til frå {addr[0]}")
                try:
                    while not self.stop_ev.is_set():
                        try:
                            d = c.recv(4096)
                        except socket.timeout:
                            continue
                        if not d:
                            break
                        self.data(d)
                except OSError as e:
                    self.err = str(e)
                finally:
                    c.close()
                    self.connected = False
                    self.events.add(f"{self.label()}: eininga kopla frå", "feil")
        finally:
            srv.close()


class UploadSource(Source):
    """NTRIP-opplasting til Base sin eigen caster. Casteren kallar push()."""
    kind = "opplasting"

    def where(self):
        return "NTRIP-opplasting til denne casteren"

    def run(self):
        self.stop_ev.wait(3600)        # passiv – dataa kjem frå casteren

    def _run_forever(self):
        self.stop_ev.wait()

    def attach(self, peer):
        self.up(f"opplasting starta frå {peer}")

    def detach(self):
        self.connected = False
        self.events.add(f"{self.label()}: opplastinga stoppa", "feil")

    def push(self, chunk):
        self.data(chunk)


class NtripSource(Source):
    kind = "ntrip"

    def where(self):
        return f"{self.cfg.get('caster')}:{self.cfg.get('port', 2101)}/{self.cfg.get('mountpoint')}"

    def _gga(self):
        p = self.cfg.get("gga") or self.mount.cfg.get("innmalt")
        if p and p.get("lat") is not None:
            return make_gga(float(p["lat"]), float(p["lon"]), float(p.get("h", 0)))
        return None

    def run(self):
        gga = self._gga()
        st = ntripklient.open_stream(self.cfg["caster"], self.cfg.get("port", 2101), self.cfg["mountpoint"],
                                     self.cfg.get("brukar", ""), self.cfg.get("passord", ""),
                                     str(self.cfg.get("versjon", "auto")), f"Base {self._ver()}", gga)
        try:
            self.up(f"kopla til {self.where()} ({st.proto})")
            last_gga, quiet = 0.0, time.time()
            while not self.stop_ev.is_set():
                if gga and time.time() - last_gga > 10:
                    try:
                        st.send_gga(self._gga())
                    except OSError:
                        pass
                    last_gga = time.time()
                d = st.read()
                if d:
                    quiet = time.time()
                    self.data(d)
                elif time.time() - quiet > 60:
                    raise ConnectionError("ingen korreksjonar på 60 s")
        finally:
            st.close()

    @staticmethod
    def _ver():
        from konfig import VERSION
        return VERSION


class FileSource(Source):
    """Avspeling av eit RTCM-opptak i ring (test og demo)."""
    kind = "fil"

    def where(self):
        return f"{self.cfg.get('sti')} ({self.cfg.get('byte_per_s', 1000)} B/s)"

    def run(self):
        data = Path(self.cfg["sti"]).read_bytes()
        if not data:
            raise ValueError("tom fil")
        rate = max(50, int(self.cfg.get("byte_per_s", 1000)))
        step = max(1, rate // 10)
        self.up(f"spelar av {self.where()}")
        i = 0
        while not self.stop_ev.is_set():
            self.data(data[i:i + step])
            i += step
            if i >= len(data):
                i = 0
            self.stop_ev.wait(0.1)


KINDS = {"seriell": SerialSource, "tcp": TcpSource, "tcp-tenar": TcpServerSource, "opplasting": UploadSource,
         "ntrip": NtripSource, "fil": FileSource}


def make(cfg, mount, events, rawlog=None, role="kjelde"):
    cls = KINDS.get(cfg.get("type"))
    if not cls:
        raise ValueError(f"ukjend kjeldetype «{cfg.get('type')}» – bruk ein av: {', '.join(KINDS)}")
    return cls(cfg, mount, events, rawlog, role)
