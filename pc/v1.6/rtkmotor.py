# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""RTK i SNOWMAN: SNOWMAN reknar RTK sjølv frå rådata – mottakaren berre måler (eigaren 2026-10-09: «RTK og NTRIP
skal kun vere i SNOWMAN»).

    NTRIP (basen, RTCM 3) ──► base-avkodar ──┐
                                             ├──► RTKLIB rtkpos ──► GGA (kvalitet 4 FIX / 5 FLOAT) ──► resten av SNOWMAN
    mottakar (rådata RTCM 3) ► rover-avkodar ┘
         └─ NMEA (GGA) frå mottakaren blir framleis lese, men brukt berre når RTK-motoren ikkje har løysing

Krav til mottakaren: han må sende RÅDATA som RTCM 3 – MSM (1074/1084/1094/1124 …) eller 1004/1012 – på same port som
SNOWMAN les. GGA åleine er ein ferdig rekna posisjon og kan ikkje gi RTK. Satellittbaner (1019/1020/1042/1046) blir
tekne frå rover- eller basestraumen; manglar dei, kan ei BRDC-fil lastast inn (load_nav).

Motoren er RTKLIB (T. Takasu, BSD-2) via pyrtklib (IPNL-POLYU, MIT). pyrtklib blir installert med pip første gong
(sjå ensure_lib), sidan oppdateringa av SNOWMAN ikkje køyrer pip.
"""
import math
import subprocess
import sys
import threading
import time

from rtcm import crc24q, _bits

R = None            # pyrtklib-modulen når han er lasta
LIB_ERR = ""        # kvifor RTK-motoren ikkje er tilgjengeleg
LIB_VERSION = "0.2.7"
_lib_lock = threading.Lock()


def ensure_lib(install=True, log=None):
    """Last pyrtklib; manglar han og install=True, installer han med pip (krev nett éin gong). Returnerer True/False."""
    global R, LIB_ERR
    with _lib_lock:
        if R is not None:
            return True
        try:
            import pyrtklib as _R
            R = _R
            LIB_ERR = ""
            return True
        except Exception as e:
            LIB_ERR = f"pyrtklib manglar ({e})"
        if not install:
            return False
        try:
            if log:
                log("RTK-motor: installerer pyrtklib (RTKLIB) med pip …")
            p = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--quiet",
                                f"pyrtklib=={LIB_VERSION}"], capture_output=True, text=True, timeout=600)
            if p.returncode != 0:
                LIB_ERR = "Klarte ikkje å installere pyrtklib: " + (p.stderr or p.stdout).strip()[-300:]
                return False
            import importlib
            importlib.invalidate_caches()
            import pyrtklib as _R
            R = _R
            LIB_ERR = ""
            return True
        except Exception as e:
            LIB_ERR = f"Klarte ikkje å installere pyrtklib: {e}"
            return False


class Demux:
    """Skil ein straum frå mottakaren i RTCM 3-rammer (med rett CRC) og tekst (NMEA o.l.)."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        b = self.buf
        b += data
        frames, text = [], bytearray()
        i = 0
        while i < len(b):
            if b[i] != 0xD3:
                j = b.find(0xD3, i)
                j = len(b) if j < 0 else j
                text += b[i:j]
                i = j
                continue
            if len(b) - i < 3:
                break
            n = ((b[i + 1] & 0x03) << 8) | b[i + 2]
            if b[i + 1] & 0xFC:            # ikkje ein rammestart
                text.append(b[i])
                i += 1
                continue
            if len(b) - i < n + 6:
                break                      # vent på resten av ramma
            fr = bytes(b[i:i + n + 6])
            if crc24q(fr[:n + 3]) == int.from_bytes(fr[n + 3:], "big"):
                frames.append(fr)
                i += n + 6
            else:
                text.append(b[i])
                i += 1
        del b[:i]
        if len(b) > 8192:                  # vern mot uendeleg buffer
            del b[:-2048]
        return frames, bytes(text)


QUAL = {1: 4, 2: 5, 3: 2, 4: 2, 5: 1}      # RTKLIB SOLQ_* → GGA-kvalitet (FIX, FLOAT, SBAS→DGPS, DGPS, SINGLE)
STATNAME = {0: "INGA", 1: "FIX", 2: "FLOAT", 3: "SBAS", 4: "DGPS", 5: "SINGLE", 6: "PPP"}


def _nmea(body):
    cs = 0
    for c in body:
        cs ^= ord(c)
    return f"${body}*{cs:02X}"


class RtkMotor:
    """RTK-utrekning i SNOWMAN. Trådsikker: basen kjem frå NTRIP-tråden, roveren frå mottakartråden."""

    def __init__(self, on_solution=None, log=None):
        self.on_solution = on_solution     # kallast med (gga_linje, info) for kvar ny løysing
        self.log = log
        self.lock = threading.Lock()
        self.ready = False
        self.demux = Demux()
        self.reset()

    # ---------- oppsett ----------
    def reset(self):
        self.ready = False
        self.stats = {"base_obs": 0, "rover_obs": 0, "eph": 0, "sol": 0, "fix": 0, "float": 0, "single": 0,
                      "none": 0, "last_stat": None, "last_ratio": None, "last_sol": 0.0, "base_time": 0.0,
                      "rover_time": 0.0, "base_pos": None, "rover_types": {}, "base_types": {}, "err": ""}
        self.base_obs = None
        self.base_n = 0
        self.base_t = None
        self.hdop = None

    def start(self, install=True, ref_time=None):
        """Last RTKLIB og set opp motoren. Returnerer True når han er klar.
        ref_time = (år, md, dag) berre for avspeling av gamle opptak: RTCM har tid i veka, ikkje veke – utan dette
        blir veka teken frå klokka på PC-en (rett i sanntid)."""
        if not ensure_lib(install, self.log):
            self.stats["err"] = LIB_ERR
            return False
        with self.lock:
            opt = R.prcopt_default
            opt.mode = 2                                    # PMODE_KINEMA – maskina flyttar seg
            opt.nf = 2                                      # L1 + L2
            opt.navsys = R.SYS_GPS | R.SYS_GLO | R.SYS_GAL | R.SYS_CMP
            opt.elmin = 15.0 * math.pi / 180.0              # 15° elevasjonsmaske
            opt.modear = 1                                  # ARMODE_CONT – løyser heiltal kontinuerleg
            opt.glomodear = 0                               # GLONASS-heiltal av: trygt mellom ulike mottakarmerke
            opt.thresar[0] = 3.0                            # ratio-test for FIX
            opt.dynamics = 0
            opt.refpos = 0                                  # baseposisjon frå opt.rb (set frå RTCM 1005/1006)
            self.rtk = R.rtk_t()
            R.rtkinit(self.rtk, opt)
            self.rb = R.rtcm_t()
            R.init_rtcm(self.rb)                            # basestraumen (frå NTRIP)
            self.rv = R.rtcm_t()
            R.init_rtcm(self.rv)                            # roverstraumen (frå mottakaren)
            self.nav = self.rb.nav                          # felles satellittbaner (base, rover og ev. BRDC-fil)
            self.base_obs = R.Arr1Dobsd_t(128)
            self.navfile = None
            if ref_time:
                ep = R.Arr1Ddouble(6)
                for k, v in enumerate(list(ref_time) + [0] * (6 - len(ref_time))):
                    ep[k] = v
                t0 = R.epoch2time(ep)
                self.rb.time = t0
                self.rv.time = t0
            self.ready = True
        return True

    def load_nav(self, path):
        """Les satellittbaner frå ei RINEX-navigasjonsfil (BRDC) – brukt når verken base eller rover sender
        1019/1020. RTKLIB vel sjølv rett bane for tida frå heile lista. Returnerer talet på baner."""
        if not self.ready:
            return 0
        tmp = R.nav_t()
        R.readrnx(path, 0, "", R.obs_t(), tmp, R.sta_t())
        with self.lock:
            if tmp.n or tmp.ng:
                self.navfile = tmp
                self.navfile_time = time.time()
        self.stats["eph_file"] = int(tmp.n + tmp.ng)
        return int(tmp.n + tmp.ng)

    def _nav(self):
        """Banene til utrekninga: straumane når dei har baner, elles BRDC-fila."""
        if self.navfile is not None and self.stats["eph"] < 4:
            return self.navfile
        return self.nav

    # ---------- basen (frå NTRIP) ----------
    def base_feed(self, data):
        """RTCM 3 frå casteren. Lagrar siste base-epoke, baseposisjon og satellittbaner."""
        if not self.ready:
            return
        with self.lock:
            for c in data:
                ret = R.input_rtcm3(self.rb, c)
                if ret == 1:                                # heil observasjonsepoke frå basen
                    n = min(self.rb.obs.n, 128)
                    for i in range(n):
                        self.base_obs[i] = self.rb.obs.data[i]
                        self.base_obs[i].rcv = 2
                    self.base_n = n
                    self.base_t = self.rb.obs.data[0].time if n else None
                    self.stats["base_obs"] += 1
                    self.stats["base_time"] = time.time()
                elif ret == 2:
                    self.stats["eph"] += 1
                elif ret == 5:                              # baseposisjon (1005/1006)
                    p = [self.rb.sta.pos[k] for k in range(3)]
                    if sum(abs(x) for x in p) > 1e6:
                        for k in range(3):
                            self.rtk.opt.rb[k] = p[k]
                        self.stats["base_pos"] = p
                if ret > 0:
                    t = self.rb.msgtype if hasattr(self.rb, "msgtype") else None
                    if isinstance(t, str) and t:
                        k = t.split()[0][5:] if t.startswith("RTCM ") else t.split()[0]
                        self.stats["base_types"][k] = self.stats["base_types"].get(k, 0) + 1

    # ---------- roveren (frå mottakaren) ----------
    def rover_bytes(self, data):
        """Rå straum frå mottakaren: returnerer teksten (NMEA) som SNOWMAN skal lese som før; RTCM går til motoren."""
        frames, text = self.demux.feed(data)
        for fr in frames:
            n = ((fr[1] & 3) << 8) | fr[2]
            t = _bits(fr[3:3 + n], 0, 12) if n >= 2 else 0
            self.stats["rover_types"][str(t)] = self.stats["rover_types"].get(str(t), 0) + 1
            self.rover_feed(fr)
        return text

    def rover_feed(self, data):
        if not self.ready:
            return
        sols = []
        with self.lock:
            for c in data:
                ret = R.input_rtcm3(self.rv, c)
                if ret == 1:
                    self.stats["rover_obs"] += 1
                    self.stats["rover_time"] = time.time()
                    s = self._solve()
                    if s:
                        sols.append(s)
                elif ret == 2:                              # satellittbane frå mottakaren → felles nav
                    s = self.rv.ephsat
                    if s > 0:
                        try:
                            self.nav.eph[s - 1] = self.rv.nav.eph[s - 1]
                        except Exception:
                            pass
                        self.stats["eph"] += 1
        for g, info in sols:
            if self.on_solution:
                self.on_solution(g, info)

    def _solve(self):
        nr = min(self.rv.obs.n, 128)
        if nr == 0:
            return None
        nb = self.base_n if self.base_t is not None else 0
        arr = R.Arr1Dobsd_t(nr + nb)
        for i in range(nr):
            arr[i] = self.rv.obs.data[i]
            arr[i].rcv = 1
        for i in range(nb):
            arr[nr + i] = self.base_obs[i]
        R.rtkpos(self.rtk, arr[0], nr + nb, self._nav())
        sol = self.rtk.sol
        st = int(sol.stat)
        key = {1: "fix", 2: "float"}.get(st, "single" if st in (3, 4, 5) else "none")
        self.stats[key] += 1
        self.stats["last_stat"] = st
        self.stats["last_ratio"] = round(float(sol.ratio), 1)
        if st == 0:
            eb = "".join(self.rtk.errbuf[i] for i in range(min(self.rtk.neb, 300))).strip("\x00").strip()
            if eb:
                self.stats["err"] = eb.splitlines()[-1][:200]
            return None
        self.stats["sol"] += 1
        self.stats["last_sol"] = time.time()
        return self._gga(sol, st), {"stat": st, "ratio": float(sol.ratio), "ns": int(sol.ns), "age": float(sol.age)}

    def _gga(self, sol, st):
        rr = R.Arr1Ddouble(3)
        for k in range(3):
            rr[k] = sol.rr[k]
        pos = R.Arr1Ddouble(3)
        R.ecef2pos(rr, pos)
        lat, lon, h = pos[0] * 180 / math.pi, pos[1] * 180 / math.pi, pos[2]
        t = R.gpst2utc(sol.time)
        ep = R.Arr1Ddouble(6)
        R.time2epoch(t, ep)
        hh, mm, ss = int(ep[3]), int(ep[4]), ep[5]
        la, lo = abs(lat), abs(lon)
        body = ("GPGGA,%02d%02d%05.2f,%02d%010.7f,%s,%03d%010.7f,%s,%d,%02d,%.1f,%.3f,M,0.000,M,%.1f,%04d" % (
            hh, mm, ss, int(la), (la - int(la)) * 60, "N" if lat >= 0 else "S", int(lo), (lo - int(lo)) * 60,
            "E" if lon >= 0 else "W", QUAL.get(st, 1), int(sol.ns), self.hdop or 1.0, h, float(sol.age),
            int(getattr(self.rb, "staid", 0)) % 10000))
        # Høgda er ELLIPSOIDISK med geoideseparasjon 0 – SNOWMAN reknar om til NN2000 med Kartverket-geoiden.
        return _nmea(body)

    def status(self):
        s = dict(self.stats)
        now = time.time()
        s.update(ready=self.ready, lib=R is not None, lib_err=LIB_ERR,
                 base_age=round(now - s["base_time"], 1) if s["base_time"] else None,
                 rover_age=round(now - s["rover_time"], 1) if s["rover_time"] else None,
                 sol_age=round(now - s["last_sol"], 1) if s["last_sol"] else None,
                 last_name=STATNAME.get(s["last_stat"], "–") if s["last_stat"] is not None else "–")
        return s


BRDC_URL = "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/{y}/{d:03d}/"   # IGS-baner (BKG), samla døgnfiler


def fetch_brdc(folder, ua="SNOWMAN", now=None):
    """Hent siste samla banefil (RINEX nav) frå BKG/IGS til folder og returner stien, eller None.
    NB: døgnfilene blir fullstendige først etter midnatt – for sanntid er baner frå mottakaren (eller basen) best.
    Brukt som reserve når straumane ikkje har baner."""
    import datetime as dt
    import gzip
    import re
    import urllib.request
    from pathlib import Path
    import nett
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    now = now or dt.datetime.now(dt.timezone.utc)
    for back in (0, 1):
        day = now - dt.timedelta(days=back)
        url = BRDC_URL.format(y=day.year, d=day.timetuple().tm_yday)
        try:
            with nett.urlopen(urllib.request.Request(url, headers={"User-Agent": ua}), timeout=15) as r:
                html = r.read().decode("utf-8", "ignore")
        except Exception:
            continue
        names = re.findall(r'href="([^"]*BRDC00(?:WRD|IGS|DLR)_[SR]_\d{11}_01D_MN\.rnx\.gz)"', html) or \
            re.findall(r'href="([^"]*brdc\d{3}0\.\d{2}[np]\.gz)"', html)
        if not names:
            continue
        name = sorted(set(n.split("/")[-1] for n in names))[-1]
        out = folder / name[:-3]
        if out.exists() and time.time() - out.stat().st_mtime < 3600:
            return out
        with nett.urlopen(urllib.request.Request(url + name, headers={"User-Agent": ua}), timeout=60) as r:
            data = gzip.decompress(r.read())
        tmp = out.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(out)
        return out
    return None
