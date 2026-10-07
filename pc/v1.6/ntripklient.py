# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""NTRIP-klient: kopling til casteren (NTRIP 1 og 2), og kjeldetabellen (lista over mountpoints).

  open_stream(...)       → Stream: les korreksjonar med .read(), send GGA med .send_gga()
  fetch_sourcetable(...) → liste over mountpoints med format, satellittsystem og posisjon

NTRIP 1: «GET /TH HTTP/1.0» → «ICY 200 OK», så RTCM rett etter.
NTRIP 2: «GET /TH HTTP/1.1» + «Ntrip-Version: Ntrip/2.0» → «HTTP/1.1 200 OK», ofte med «Transfer-Encoding: chunked»
         (korreksjonane kjem i bitar med lengd framfor kvar – dei blir pakka ut her før dei går til mottakaren).
Versjon «auto»: prøver NTRIP 1 først (som før v1.6.41); svarar casteren med feil som tyder på at han krev NTRIP 2,
blir NTRIP 2 prøvd. Feil passord (401) og ukjent mountpoint blir ikkje prøvde på nytt.
"""
import base64, math, socket

UA = "NTRIP SNOWMAN/{ver}"


class NtripError(RuntimeError):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code  # "auth" | "mount" | "proto" | None


class Dechunker:
    """Pakkar ut HTTP «chunked» straum bit for bit."""

    def __init__(self):
        self.buf = b""
        self.left = 0  # byte att i gjeldande bit
        self.state = "size"  # size | data | crlf | done

    def feed(self, data):
        self.buf += data
        out = bytearray()
        while True:
            if self.state == "size":
                i = self.buf.find(b"\r\n")
                if i < 0:
                    if len(self.buf) > 1024:
                        raise NtripError("Ugyldig NTRIP 2-straum frå casteren (chunk-lengd)", "proto")
                    break
                line = self.buf[:i].split(b";")[0].strip()
                self.buf = self.buf[i + 2:]
                if not line:
                    continue
                try:
                    self.left = int(line, 16)
                except ValueError:
                    raise NtripError("Ugyldig NTRIP 2-straum frå casteren (chunk-lengd)", "proto")
                if self.left == 0:
                    self.state = "done"
                    break
                self.state = "data"
            elif self.state == "data":
                if not self.buf:
                    break
                take = self.buf[:self.left]
                out += take
                self.buf = self.buf[len(take):]
                self.left -= len(take)
                if self.left == 0:
                    self.state = "crlf"
            elif self.state == "crlf":
                if len(self.buf) < 2:
                    break
                self.buf = self.buf[2:]
                self.state = "size"
            else:
                break
        return bytes(out)


def _host_port(caster, port):
    host = str(caster).replace("http://", "").replace("https://", "").split("/")[0].strip()
    if ":" in host:  # «gpsbase.dyndns.org:2101» skrive i caster-feltet
        host, p = host.rsplit(":", 1)
        if p.isdigit():
            port = int(p)
    return host, int(port)


def _auth(user, pw):
    if not str(user or "").strip():
        return ""
    a = base64.b64encode(f"{str(user).strip()}:{str(pw or '').strip()}".encode("utf-8")).decode()
    return f"Authorization: Basic {a}\r\n"


def _readline(s, limit=8192):
    l = b""
    while not l.endswith(b"\r\n") and len(l) < limit:
        c = s.recv(1)
        if not c:
            break
        l += c
    return l


def _headers(s):
    h = {}
    while True:
        l = _readline(s)
        if l in (b"\r\n", b""):
            return h
        if b":" in l:
            k, v = l.split(b":", 1)
            h[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()


def _request(host, port, path, user, pw, version, ver, gga=None, timeout=10):
    s = socket.create_connection((host, port), timeout=timeout)
    if version == 2:
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nNtrip-Version: Ntrip/2.0\r\n"
               f"User-Agent: {UA.format(ver=ver)}\r\n{_auth(user, pw)}"
               + (f"Ntrip-GGA: {gga}\r\n" if gga else "") + "Connection: close\r\n\r\n")
    else:  # NTRIP 1: User-Agent må byrje med «NTRIP » – nokre castarar avviser elles førespurnaden
        req = (f"GET {path} HTTP/1.0\r\nHost: {host}:{port}\r\nUser-Agent: {UA.format(ver=ver)}\r\n"
               f"{_auth(user, pw)}Accept: */*\r\nConnection: close\r\n\r\n")
    try:
        s.sendall(req.encode())
        first = _readline(s).decode("latin1", "ignore").strip()
    except Exception:
        s.close()  # ikkje lat sambandet liggje ope når casteren ikkje svarar
        raise
    return s, first


class Stream:
    def __init__(self, sock, proto, rest=b"", chunked=False):
        self.sock = sock
        self.proto = proto  # "NTRIP 1" | "NTRIP 2"
        self.dech = Dechunker() if chunked else None
        self.pending = self.dech.feed(rest) if (self.dech and rest) else rest

    def read(self, n=4096):
        """Korreksjonar (byte). b"" = ingenting akkurat no. Kastar ConnectionError når casteren lukkar."""
        if self.pending:
            d, self.pending = self.pending, b""
            return d
        try:
            d = self.sock.recv(n)
        except socket.timeout:
            return b""
        if not d:
            raise ConnectionError("Casteren lukka sambandet")
        if self.dech:
            d = self.dech.feed(d)
            if self.dech.state == "done":
                raise ConnectionError("Casteren avslutta straumen")
        return d

    def send_gga(self, gga):
        self.sock.sendall((gga.strip() + "\r\n").encode("ascii", "ignore"))

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


def _open(host, port, mp, user, pw, version, ver, gga):
    s, first = _request(host, port, "/" + mp, user, pw, version, ver, gga)
    up = first.upper()
    try:
        if up.startswith("SOURCETABLE"):
            raise NtripError(f"Mountpointet «{mp}» finst ikkje på casteren (casteren sende kjeldetabellen i staden "
                             f"for korreksjonar). Bruk HENT MOUNTPOINTS for å sjå kva som finst.", "mount")
        if not first:
            raise NtripError("Casteren svarte ikkje på førespurnaden", "proto")
        if "401" in first:
            raise NtripError(f"NTRIP svar: {first} – feil brukarnamn/passord, kontoen har ikkje tilgang til "
                             f"mountpointet, eller kontoen er i bruk på ei anna eining", "auth")
        if "404" in first:
            raise NtripError(f"NTRIP svar: {first} – mountpointet finst ikkje (sjekk stavinga, store/små bokstavar)", "mount")
        if " 200" not in " " + first:
            raise NtripError("NTRIP svar: " + first, "proto")
        if up.startswith("ICY"):
            # NTRIP 1: «ICY 200 OK\r\n» – nokre castarar sender ei tom linje etter, andre startar RTCM med éin gong
            s.settimeout(2)
            try:
                rest = s.recv(2)
            except socket.timeout:
                rest = b""
            if rest == b"\r\n":
                rest = b""
            s.settimeout(1)
            return Stream(s, "NTRIP 1", rest)
        h = _headers(s)
        if "gnss/sourcetable" in h.get("content-type", "").lower():
            raise NtripError(f"Mountpointet «{mp}» finst ikkje på casteren (casteren sende kjeldetabellen). "
                             f"Bruk HENT MOUNTPOINTS for å sjå kva som finst.", "mount")
        s.settimeout(1)
        return Stream(s, "NTRIP 2" if version == 2 or first.startswith("HTTP/1.1") else "NTRIP 1",
                      b"", "chunked" in h.get("transfer-encoding", "").lower())
    except Exception:
        s.close()
        raise


def open_stream(caster, port, mp, user, pw, version="auto", ver="", gga=None):
    """Opnar korreksjonsstraumen. version: "auto" | "1" | "2"."""
    host, port = _host_port(caster, port)
    mp = str(mp).strip().lstrip("/")
    if version in ("1", 1):
        return _open(host, port, mp, user, pw, 1, ver, None)
    if version in ("2", 2):
        return _open(host, port, mp, user, pw, 2, ver, gga)
    try:
        return _open(host, port, mp, user, pw, 1, ver, None)
    except (ConnectionRefusedError, socket.gaierror):
        raise  # casteren er ikkje å nå i det heile – NTRIP 2 hjelper ikkje
    except (NtripError, OSError) as e:
        # Også når casteren tek imot sambandet men aldri svarar på NTRIP 1 (tidsavbrot), blir NTRIP 2 prøvd
        if isinstance(e, NtripError) and e.code in ("auth", "mount"):
            raise
        try:  # casteren godtok ikkje NTRIP 1 – prøv NTRIP 2
            return _open(host, port, mp, user, pw, 2, ver, gga)
        except NtripError as e2:
            raise NtripError(f"{e2} (prøvde NTRIP 1 og 2)", e2.code)
        except OSError as e2:
            raise NtripError(f"Casteren svarar ikkje ({e2}) – prøvde NTRIP 1 og 2")


# ---------- kjeldetabellen ----------
def _dist_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def parse_sourcetable(text, lat=None, lon=None):
    """STR-linjene i kjeldetabellen → liste med mountpoints (nærmaste først når posisjonen er kjend)."""
    out = []
    for line in text.splitlines():
        if not line.startswith("STR;"):
            continue
        f = line.split(";")
        f += [""] * (19 - len(f))
        try:
            la, lo = float(f[9]), float(f[10])
        except ValueError:
            la = lo = None
        m = {"mountpoint": f[1], "name": f[2], "format": f[3], "details": f[4], "carrier": f[5],
             "systems": f[6].replace("+", ", "), "network": f[7], "country": f[8], "lat": la, "lon": lo,
             "nmea": f[11] == "1", "network_rtk": f[12] == "1", "auth": f[15], "bitrate": f[17]}
        if None not in (lat, lon, la, lo) and not (la == 0 and lo == 0):
            m["km"] = round(_dist_km(lat, lon, la, lo), 1)
        out.append(m)
    out.sort(key=lambda m: (m.get("km") is None, m.get("km") or 0, m["mountpoint"].lower()))
    return out


def fetch_sourcetable(caster, port, user="", pw="", ver="", lat=None, lon=None, timeout=10):
    """Hentar kjeldetabellen («GET /»). Prøver NTRIP 2 først (gir ofte meir), så NTRIP 1."""
    host, port = _host_port(caster, port)
    last = None
    for version in (2, 1):
        try:
            s, first = _request(host, port, "/", user, pw, version, ver, None, timeout)
        except OSError as e:
            raise NtripError(f"Får ikkje kontakt med {host}:{port} – {e}")
        try:
            if " 200" not in " " + first:
                last = NtripError("Casteren svarte: " + (first or "(ingenting)"))
                continue
            chunked = False
            if not first.upper().startswith("SOURCETABLE") or version == 2:
                h = _headers(s) if not first.upper().startswith("ICY") else {}
                chunked = "chunked" in h.get("transfer-encoding", "").lower()
            else:
                _headers(s)
            s.settimeout(timeout)
            data, dech = b"", (Dechunker() if chunked else None)
            while b"ENDSOURCETABLE" not in data and len(data) < 4_000_000:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    break
                if not d:
                    break
                data += dech.feed(d) if dech else d
            mounts = parse_sourcetable(data.decode("utf-8", "replace"), lat, lon)
            if mounts or version == 1:
                return {"mounts": mounts, "proto": "NTRIP 2" if first.startswith("HTTP/1.1") else "NTRIP 1",
                        "caster": f"{host}:{port}"}
        finally:
            s.close()
    raise last or NtripError("Fann ingen mountpoints på casteren")
