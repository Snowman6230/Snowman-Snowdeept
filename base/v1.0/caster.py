# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""NTRIP-caster i SNOWMAN Base (NTRIP 1 og 2) – same protokoll som SNOWMAN snødjupne brukar mot TH og CPOS.

    GET /                   kjeldetabellen (lista over mountpoints)
    GET /<mountpoint>       korreksjonar til ei maskin (Basic-innlogging). GGA frå maskina blir lagra (posisjon på kartet)
    SOURCE <pw> /<mp>       NTRIP 1-opplasting inn i Base (t.d. str2str på ein Raspberry Pi ved antenna)
    POST /<mp>              NTRIP 2-opplasting inn i Base

Kvar maskin får ein eigen tråd og les frå ringen til mountpointet i sitt eige tempo. Ei treg maskin hoppar fram
til nyaste korreksjonar (gamle korreksjonar er verdilause for RTK).
"""
import base64
import itertools
import socket
import socketserver
import threading
import time

from konfig import VERSION, check_pw
from ntripklient import Dechunker

SERVER = f"SNOWMAN Base/{VERSION}"
_ids = itertools.count(1)


def parse_gga(line):
    """GGA → (lat, lon, kvalitet, satellittar) eller None."""
    try:
        f = line.strip().split("*")[0].split(",")
        if not f[0].endswith("GGA") or not f[2] or not f[4]:
            return None
        lat = int(f[2][:2]) + float(f[2][2:]) / 60
        lon = int(f[4][:3]) + float(f[4][3:]) / 60
        if f[3] == "S":
            lat = -lat
        if f[5] == "W":
            lon = -lon
        return lat, lon, int(f[6] or 0), int(f[7] or 0)
    except (ValueError, IndexError):
        return None


class Client:
    def __init__(self, mount, user, peer, proto, agent):
        self.id = next(_ids)
        self.mount = mount
        self.user = user
        self.peer = peer
        self.proto = proto
        self.agent = agent
        self.since = time.time()
        self.sent = 0
        self.gga = None              # (lat, lon, kvalitet, sat, tid)
        self.fixlog = []             # kvalitet frå GGA siste døgn (til forbetringsforslag)

    def on_gga(self, line):
        g = parse_gga(line)
        if g:
            self.gga = (*g, time.time())
            self.fixlog.append((time.time(), g[2]))
            if len(self.fixlog) > 20000:
                del self.fixlog[:5000]

    def status(self):
        s = {"id": self.id, "brukar": self.user, "ip": self.peer, "protokoll": self.proto, "program": self.agent,
             "sidan": self.since, "sendt": self.sent}
        if self.gga:
            lat, lon, q, n, t = self.gga
            s["gga"] = {"lat": round(lat, 7), "lon": round(lon, 7), "kvalitet": q, "sat": n, "age": round(time.time() - t)}
        return s


class Handler(socketserver.BaseRequestHandler):
    base = None                       # sett av Caster: objekt med .cfg, .mounts, .events, .stats

    def setup(self):
        self.request.settimeout(10)
        self.buf = b""

    def _line(self):
        while b"\r\n" not in self.buf and b"\n" not in self.buf:
            d = self.request.recv(4096)
            if not d:
                raise ConnectionError("lukka")
            self.buf += d
            if len(self.buf) > 16384:
                raise ValueError("for lang førespurnad")
        i = self.buf.find(b"\n")
        line, self.buf = self.buf[:i], self.buf[i + 1:]
        return line.rstrip(b"\r").decode("latin1")

    def send(self, text):
        self.request.sendall(text.encode("latin1"))

    def handle(self):
        b = self.base
        peer = self.client_address[0]
        try:
            req = self._line()
            headers = {}
            while True:
                ln = self._line()
                if not ln:
                    break
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
        except Exception:
            return
        parts = req.split()
        if len(parts) < 2:
            return self.send("HTTP/1.0 400 Bad Request\r\n\r\n")
        method = parts[0].upper()
        v2 = "ntrip/2" in headers.get("ntrip-version", "").lower()
        if method == "SOURCE":          # NTRIP 1-opplasting: «SOURCE passord /MP»
            pw = parts[1] if len(parts) >= 3 else ""
            mp = (parts[2] if len(parts) >= 3 else parts[1]).lstrip("/")
            return self.upload(mp, pw, peer, False, headers)
        path = parts[1].split("?")[0]
        mp = path.lstrip("/")
        if method == "POST" and mp:
            user, pw = self.basic(headers)
            return self.upload(mp, pw, peer, True, headers)
        if method != "GET":
            return self.send("HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
        if not mp:
            return self.sourcetable(v2)
        m = b.mounts.get(mp)
        if m is None:
            if v2:
                return self.send("HTTP/1.1 404 Not Found\r\nNtrip-Version: Ntrip/2.0\r\nConnection: close\r\n\r\n")
            return self.sourcetable(False)          # NTRIP 1: ukjent mountpoint → kjeldetabellen (standard)
        user, pw = self.basic(headers)
        if b.cfg["caster"].get("krev_innlogging", True) and not b.cfg.user_ok(user, pw, mp):
            b.events.add(f"Avvist innlogging «{user or '–'}» til {mp} frå {peer}", "feil")
            time.sleep(1)                            # bremsar gjetting av passord
            return self.send(("HTTP/1.1" if v2 else "HTTP/1.0") +
                             f" 401 Unauthorized\r\nWWW-Authenticate: Basic realm=\"/{mp}\"\r\n"
                             + ("Ntrip-Version: Ntrip/2.0\r\n" if v2 else "") + "Connection: close\r\n\r\n")
        self.stream(m, user, peer, v2, headers)

    @staticmethod
    def basic(headers):
        a = headers.get("authorization", "")
        if a.lower().startswith("basic "):
            try:
                u, _, p = base64.b64decode(a[6:].strip()).decode("utf-8", "replace").partition(":")
                return u, p
            except Exception:
                pass
        return "", ""

    def sourcetable(self, v2):
        b = self.base
        lines = [f"CAS;{b.host_hint()};{b.cfg['caster']['port']};SNOWMAN Base;Alpindata;0;NOR;0.00;0.00;0.0.0.0;0;",
                 "NET;SNOWMAN;Alpindata;B;N;;;;"]
        lines += [m.str_line() for m in b.mounts.values()]
        body = ("\r\n".join(lines) + "\r\nENDSOURCETABLE\r\n").encode("utf-8")
        if v2:
            head = ("HTTP/1.1 200 OK\r\nNtrip-Version: Ntrip/2.0\r\n"
                    f"Server: {SERVER}\r\nContent-Type: gnss/sourcetable\r\n")
        else:
            head = f"SOURCETABLE 200 OK\r\nServer: {SERVER}\r\nContent-Type: text/plain\r\n"
        self.request.sendall((head + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body)

    def stream(self, m, user, peer, v2, headers):
        b = self.base
        c = Client(m, user, peer, "NTRIP 2" if v2 else "NTRIP 1", headers.get("user-agent", ""))
        if headers.get("ntrip-gga"):
            c.on_gga(headers["ntrip-gga"])
        if v2:
            self.send("HTTP/1.1 200 OK\r\nNtrip-Version: Ntrip/2.0\r\n"
                      f"Server: {SERVER}\r\nCache-Control: no-store, no-cache\r\nContent-Type: gnss/data\r\n"
                      "Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n")
        else:
            self.send("ICY 200 OK\r\n")
        m.clients[c.id] = c
        b.on_client(c, True)
        stop = threading.Event()

        def reader():                       # GGA og anna frå maskina (NTRIP 1: rett i straumen)
            data = self.buf
            self.request.settimeout(1)
            while not stop.is_set():
                while b"\n" in data:
                    i = data.find(b"\n")
                    ln, data = data[:i], data[i + 1:]
                    t = ln.decode("latin1", "ignore")
                    if "GGA" in t:
                        c.on_gga(t[t.find("$"):] if "$" in t else t)
                if len(data) > 8192:
                    data = b""
                try:
                    d = self.request.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not d:
                    break
                data += d
            stop.set()

        threading.Thread(target=reader, daemon=True, name=f"gga-{c.id}").start()
        seq = m.seq
        try:
            while not stop.is_set() and not m.closed:
                seq, frames = m.read_after(seq, 1.0)
                if not frames:
                    continue
                payload = b"".join(frames)
                if v2:
                    payload = f"{len(payload):X}\r\n".encode() + payload + b"\r\n"
                self.request.sendall(payload)
                c.sent += len(payload)
                b.stats["sendt"] += len(payload)
        except OSError:
            pass
        finally:
            stop.set()
            m.clients.pop(c.id, None)
            b.on_client(c, False)

    def upload(self, mp, pw, peer, v2, headers):
        b = self.base
        m = b.mounts.get(mp)
        src = m.upload_source() if m else None
        ok = src is not None and check_pw(pw, src.cfg.get("hash", ""))
        if not ok:
            b.events.add(f"Avvist opplasting til {mp} frå {peer}", "feil")
            time.sleep(1)
            if v2:
                return self.send("HTTP/1.1 401 Unauthorized\r\nNtrip-Version: Ntrip/2.0\r\nConnection: close\r\n\r\n")
            return self.send("ERROR - Bad Password\r\n")
        if v2:
            self.send("HTTP/1.1 200 OK\r\nNtrip-Version: Ntrip/2.0\r\nConnection: close\r\n\r\n")
        else:
            self.send("ICY 200 OK\r\n")
        src.attach(peer)
        # NTRIP 2-opplasting kan kome «chunked» (t.d. frå str2str) – pakkast ut før rammene blir funne
        dech = Dechunker() if "chunked" in headers.get("transfer-encoding", "").lower() else None
        try:
            if self.buf:
                src.push(dech.feed(self.buf) if dech else self.buf)
            self.request.settimeout(60)
            while not m.closed:
                d = self.request.recv(8192)
                if not d:
                    break
                src.push(dech.feed(d) if dech else d)
        except OSError:
            pass
        finally:
            src.detach()


class Caster:
    def __init__(self, cfg, mounts, events):
        self.cfg = cfg
        self.mounts = mounts
        self.events = events
        self.stats = {"sendt": 0, "tilkoplingar": 0}
        self.history = []            # (tid, brukar, ip, mountpoint, "inn"/"ut")
        self.server = None

    def host_hint(self):
        try:
            return socket.gethostname()
        except OSError:
            return "snowman-base"

    def on_client(self, c, connected):
        if connected:
            self.stats["tilkoplingar"] += 1
            self.events.add(f"{c.user or 'open'} kopla til {c.mount.name} frå {c.peer} ({c.proto})", "info")
        else:
            self.events.add(f"{c.user or 'open'} kopla frå {c.mount.name} ({c.sent // 1024} kB sendt)", "info")
        self.history.append((time.time(), c.user, c.peer, c.mount.name, "inn" if connected else "ut", c.fixlog[-500:]))
        cut = time.time() - 86400
        while self.history and self.history[0][0] < cut:
            self.history.pop(0)

    def start(self, port=None):
        h = type("H", (Handler,), {"base": self})

        class Srv(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.server = Srv(("0.0.0.0", int(self.cfg["caster"]["port"] if port is None else port)), h)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="caster").start()
        return self.server.server_address[1]

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
