# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""RTK i SNOWMAN: SNOWMAN reknar RTK sjølv frå rådata – mottakaren berre måler (eigaren 2026-10-09: «RTK og NTRIP
skal kun vere i SNOWMAN»).

    NTRIP (basen, RTCM 3) ─────────────► base-avkodar (rtcm_t) ──┐
                                                                  ├──► RTKLIB rtkpos ──► GGA (4 FIX / 5 FLOAT) ──► SNOWMAN
    mottakar ─► Demux ─┬─ RTCM 3 ──────► rover-avkodar (rtcm_t) ──┤
                       ├─ UBX RAWX/SFRBX ► rover-avkodar (raw_t) ──┘   (v1.6.99)
                       └─ tekst (NMEA) ─► resten av SNOWMAN som før
    Satellittbaner frå alle tre kjeldene (1019/1020/1042/1046 og SFRBX) blir samla i éin felles nav-struktur.

Krav til mottakaren: han må sende RÅDATA på same port som SNOWMAN les – anten RTCM 3 (MSM 1074/1077/1084 … eller
1004/1012) eller u-blox UBX RXM-RAWX (+ RXM-SFRBX for banene), som ZED-F9P sender som rover. GGA åleine er ein ferdig
rekna posisjon og kan ikkje gi RTK. Manglar banene i straumane, kan ei BRDC-fil lastast inn (load_nav).

Tid: RTCM har berre tid i veka, og GPS-banene (SFRBX) berre veka modulo 1024 – RTKLIB vel veka ut frå PC-klokka.
UBX RAWX har full GPS-veke frå mottakaren. Er PC-klokka feil, blir RTKLIB si klokke, basen si referansetid og banene
retta etter mottakaren (sjå _gnss_time), så rover, base og baner alltid har same veke.

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


UBX_MAX = 8192                     # lengste UBX-melding som blir godteken (RAWX med 255 signal er ca. 8 200 byte)


def ubx_ck(body):
    """Fletcher-kontrollsum i UBX (over klasse, id, lengd og innhald)."""
    a = b = 0
    for x in body:
        a = (a + x) & 0xFF
        b = (b + a) & 0xFF
    return bytes((a, b))


class Demux:
    """Skil ein straum frå mottakaren i RTCM 3-rammer (CRC-24Q), UBX-rammer (Fletcher) og tekst (NMEA o.l.).

    Straumen kjem i bitar av vilkårleg storleik (USB/seriell). Ei ramme som ikkje er heilt komen, blir verande i bufferen
    til neste lesing. Ein rammestart med feil kontrollsum blir rekna som tekst éin byte om gongen, så synkroniseringa
    blir funnen att på neste ekte ramme utan at gyldige rammer eller tekst går tapt."""

    def __init__(self):
        self.buf = bytearray()
        self.bad = 0                       # rammestartar med feil kontrollsum (statistikk)

    def feed(self, data):
        """Returnerer ([(«rtcm»|«ubx», ramme), …], tekst)."""
        b = self.buf
        b += data
        frames, text = [], bytearray()
        i = 0
        while i < len(b):
            c = b[i]
            if c != 0xD3 and c != 0xB5:
                j1, j2 = b.find(0xD3, i), b.find(0xB5, i)
                j = min(x for x in (j1, j2, len(b)) if x >= 0)
                text += b[i:j]
                i = j
                continue
            if c == 0xB5:                          # UBX: B5 62 klasse id lengd(2, LE) innhald ck_a ck_b
                if len(b) - i < 2:
                    break
                if b[i + 1] != 0x62:
                    text.append(c)
                    i += 1
                    continue
                if len(b) - i < 6:
                    break
                n = b[i + 4] | (b[i + 5] << 8)
                if n > UBX_MAX:                    # ikkje ein ekte rammestart
                    text.append(c)
                    i += 1
                    continue
                if len(b) - i < n + 8:
                    break                          # vent på resten av ramma
                fr = bytes(b[i:i + n + 8])
                if ubx_ck(fr[2:n + 6]) == fr[n + 6:]:
                    frames.append(("ubx", fr))
                    i += n + 8
                else:
                    self.bad += 1
                    text.append(c)
                    i += 1
                continue
            # RTCM 3: D3 000000ll llllllll innhald crc(3)
            if len(b) - i < 3:
                break
            n = ((b[i + 1] & 0x03) << 8) | b[i + 2]
            if b[i + 1] & 0xFC:                    # ikkje ein rammestart
                text.append(c)
                i += 1
                continue
            if len(b) - i < n + 6:
                break                              # vent på resten av ramma
            fr = bytes(b[i:i + n + 6])
            if crc24q(fr[:n + 3]) == int.from_bytes(fr[n + 3:], "big"):
                frames.append(("rtcm", fr))
                i += n + 6
            else:
                self.bad += 1
                text.append(c)
                i += 1
        del b[:i]
        if len(b) > 4 * UBX_MAX:               # vern mot uendeleg buffer (kan ikkje skje med gyldige rammer)
            del b[:-UBX_MAX]
        return frames, bytes(text)


UBX_NAMES = {(0x02, 0x15): "UBX-RAWX", (0x02, 0x13): "UBX-SFRBX", (0x01, 0x07): "UBX-PVT", (0x01, 0x3C): "UBX-RELPOSNED"}
SNR_MASK = 35.0                              # dBHz – minste signalstyrke for roversatellittar (L1), alle elevasjonar
MAX_BASE_AGE = 30.0                         # s – eldre basedata blir ikkje brukte (same som RTKLIB maxtdiff)
QUAL = {1: 4, 2: 5, 3: 2, 4: 2, 5: 1}      # RTKLIB SOLQ_* → GGA-kvalitet (FIX, FLOAT, SBAS→DGPS, DGPS, SINGLE)
STATNAME = {0: "INGA", 1: "FIX", 2: "FLOAT", 3: "SBAS", 4: "DGPS", 5: "SINGLE", 6: "PPP"}


def _nmea(body):
    cs = 0
    for c in body:
        cs ^= ord(c)
    return f"${body}*{cs:02X}"


GLO_EXT_MIN = 90        # min – GLONASS-baner blir rekna fram i tid så langt (sjå extend_glonass)
GLO_EXT_STEP = 15       # min mellom framrekna baner


def _gpos(g, t):
    rs, dts, var = R.Arr1Ddouble(3), R.Arr1Ddouble(1), R.Arr1Ddouble(1)
    R.geph2pos(t, g, rs, dts, var)
    return [rs[0], rs[1], rs[2]]


def extend_glonass(nav):
    """Rekn GLONASS-banene i ei BRDC-fil fram i tid (v1.6.106). Returnerer talet på nye baner.

    Bakgrunn (felttest 28.10): BRDC-fila frå BKG vart oppdatert ofte, men dei nyaste GLONASS-banene i ho var 35–60 min
    gamle. RTKLIB godtek berre GLONASS-baner innanfor ±30 min (MAXDTOE_GLO), så GLONASS fall ut av RTK.
    GLONASS-banene er tilstandsvektorar (posisjon, fart, akselerasjon) som RTKLIB integrerer frå toe. Her blir den
    nyaste banen for kvar satellitt integrert fram til toe + 15, 30 … 90 min og lagra som nye baner med same
    akselerasjon og klokkemodell. Målt mot ekte baner i fila: banefeil ≤ ca. 40 m etter 90 min. I RTK (dobbeldifferanse)
    blir feilen omtrent banefeil × basestand / 20 000 km: under 1 mm ved 0,5 km og ca. 1 cm ved 5 km.
    Klokkefeilen til satellitten fell heilt bort i dobbeldifferansen. Gjeld berre korte basestandar (lokal base).

    Nye baner tek plassen til dei eldste banene for same satellitt (meir enn 2 t eldre enn den nyaste), sidan nav_t
    ikkje kan veksast trygt frå Python. Finst det ikkje nok gamle plassar, blir det færre framrekna baner."""
    by = {}
    for i in range(nav.ng):
        g = nav.geph[i]
        if g.sat:
            by.setdefault(g.sat, []).append(i)
    made = 0
    for sat, idx in by.items():
        idx.sort(key=lambda i: nav.geph[i].toe.time)
        newest = nav.geph[idx[-1]]
        t_new = newest.toe
        free = [i for i in idx if newest.toe.time - nav.geph[i].toe.time > 7200]
        for k in range(1, GLO_EXT_MIN // GLO_EXT_STEP + 1):
            if not free:
                break
            dt = k * GLO_EXT_STEP * 60.0
            t = R.timeadd(t_new, dt)
            p0 = _gpos(newest, R.timeadd(t, -0.5))
            p1 = _gpos(newest, R.timeadd(t, 0.5))
            pc = _gpos(newest, t)
            slot = free.pop(0)
            nav.geph[slot] = newest                      # kopi: frekvens, helse, akselerasjon, klokkemodell
            e = nav.geph[slot]
            for j in range(3):
                e.pos[j] = pc[j]
                e.vel[j] = p1[j] - p0[j]
            e.taun = newest.taun - newest.gamn * dt      # same klokke: -taun' + gamn·(t−toe') = -taun + gamn·(t−toe)
            e.toe = t
            e.tof = t
            e.iode = (newest.iode + k) % 128
            nav.geph[slot] = e
            made += 1
    return made


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
                      "rover_time": 0.0, "base_pos": None, "rover_types": {}, "base_types": {}, "err": "",
                      "rover_fmt": None, "eph_rover": 0, "eph_fixed": 0, "clock_off": None, "tdiff": None,
                      "ubx_bad": 0, "sats": None, "glo_ext": 0}
        self._diag_t = 0.0
        self.base_obs = None
        self.base_n = 0
        self.base_t = None
        self.hdop = None
        self.t_gnss = None                 # siste GPS-tid frå mottakaren (UBX RAWX har full veke)
        self.t_ref = None                  # tida til eit opptak (ref_time ved avspeling)

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
            # GLONASS: autokalibrering av skilnaden mellom mottakarmerke (RTKLIB glomodear=2, v1.6.106). Med «av» (0)
            # vart GLONASS-fasen med i flytløysinga med ukjend skilnad (Trimble-base mot u-blox i Reach: 6–19 cm i
            # dobbeldifferansane), og opptaket frå 28.10 gav 26 FIX der alle var 1–2 m feil. Med 2: ingen falske FIX.
            opt.glomodear = 2
            opt.thresar[0] = 3.0                            # ratio-test for FIX
            # SNR-maske for roveren (v1.6.105): felttest 28.10 med Reach RS+ – satellittar under ~30 dBHz hadde 2–5 m
            # kodestøy og fasebrot, gav «large residual» og tok ned heile løysinga. Masken blir berre slått på når
            # mottakaren faktisk rapporterer SNR (sjå _solve), elles ville alle satellittar falle bort.
            for i in range(9):
                opt.snrmask.mask[(0, i)] = SNR_MASK
            opt.snrmask.ena[0] = 0
            opt.dynamics = 0
            opt.refpos = 0                                  # baseposisjon frå opt.rb (set frå RTCM 1005/1006)
            self.rtk = R.rtk_t()
            R.rtkinit(self.rtk, opt)
            self.rb = R.rtcm_t()
            R.init_rtcm(self.rb)                            # basestraumen (frå NTRIP)
            self.rv = R.rtcm_t()
            R.init_rtcm(self.rv)                            # roverstraumen (frå mottakaren), RTCM 3
            self.ru = R.raw_t()
            R.init_raw(self.ru, R.STRFMT_UBX)               # roverstraumen (frå mottakaren), u-blox UBX
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
                self.ru.time = t0
                self.t_ref = t0
            self.ready = True
        return True

    def load_nav(self, path):
        """Les satellittbaner frå ei RINEX-navigasjonsfil (BRDC) – brukt når verken base eller rover sender
        1019/1020. RTKLIB vel sjølv rett bane for tida frå heile lista. Returnerer talet på baner."""
        if not self.ready:
            return 0
        tmp = R.nav_t()
        R.readrnx(path, 0, "", R.obs_t(), tmp, R.sta_t())
        try:
            self.stats["glo_ext"] = extend_glonass(tmp)
        except Exception as e:
            self.stats["err"] = f"GLONASS-baner fram i tid: {e}"[:200]
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
                    k = self.rb.ephsat - 1 + (R.MAXSAT if getattr(self.rb, "ephset", 0) else 0)
                    if self.rb.ephsat > 0 and R.satsys(self.rb.ephsat, R.Arr1Dint(1)) != R.SYS_GLO:
                        sec = self._week_shift(self.nav.eph[k])  # 1019 har veke modulo 1024, som SFRBX
                        if sec:
                            self._shift(self.nav.eph[k], sec)
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
        """Rå straum frå mottakaren: returnerer teksten (NMEA) som SNOWMAN skal lese som før.
        RTCM 3- og UBX-rammer går til RTK-motoren."""
        frames, text = self.demux.feed(data)
        self.stats["ubx_bad"] = self.demux.bad
        for kind, fr in frames:
            if kind == "rtcm":
                n = ((fr[1] & 3) << 8) | fr[2]
                t = str(_bits(fr[3:3 + n], 0, 12)) if n >= 2 else "0"
                self.rover_feed(fr)
            else:
                t = UBX_NAMES.get((fr[2], fr[3]), "UBX-%02X-%02X" % (fr[2], fr[3]))
                self.rover_feed_ubx(fr)
            self.stats["rover_types"][t] = self.stats["rover_types"].get(t, 0) + 1
        return text

    def rover_feed(self, data):
        """RTCM 3 frå mottakaren."""
        if not self.ready:
            return
        sols = []
        with self.lock:
            for c in data:
                ret = R.input_rtcm3(self.rv, c)
                if ret == 1:
                    self._rover_epoch(self.rv.obs, "RTCM 3", sols)
                elif ret == 2:                              # satellittbane frå mottakaren → felles nav
                    self._copy_eph(self.rv.nav, self.rv.ephsat, getattr(self.rv, "ephset", 0))
        self._emit(sols)

    def rover_feed_ubx(self, data):
        """u-blox UBX frå mottakaren: RXM-RAWX (observasjonar) og RXM-SFRBX (navigasjonsdata → baner)."""
        if not self.ready:
            return
        sols = []
        with self.lock:
            for c in data:
                ret = R.input_ubx(self.ru, c)
                if ret == 1:
                    if self.ru.obs.n:
                        self._gnss_time(self.ru.obs.data[0].time)
                    self._rover_epoch(self.ru.obs, "UBX RAWX", sols)
                elif ret == 2:                              # heil bane frå SFRBX → felles nav
                    self._copy_eph(self.ru.nav, self.ru.ephsat, self.ru.ephset)
        self._emit(sols)

    def _emit(self, sols):
        for g, info in sols:
            if self.on_solution:
                self.on_solution(g, info)

    def _rover_epoch(self, obs, fmt, sols):
        self.stats["rover_obs"] += 1
        self.stats["rover_time"] = time.time()
        self.stats["rover_fmt"] = fmt
        s = self._solve(obs)
        if s:
            sols.append(s)

    # ---------- tid og baner ----------
    def _gnss_time(self, t):
        """Ny epoke med full GPS-tid frå mottakaren (UBX). Rett opp klokka om PC-en tek feil:
        1) RTKLIB si klokke (timeget) – avgjer veka for banene (SFRBX har veke modulo 1024) og for RTCM utan referanse
        2) referansetida til basestraumen – RTCM har berre tid i veka
        3) baner som alt er lagra med feil veke (1024 veker for mykje eller for lite)"""
        first = self.t_gnss is None
        self.t_gnss = t
        off = R.timediff(R.utc2gpst(R.timeget()), t)
        if abs(off) > 60.0:                                 # PC-klokka avvik meir enn eitt minutt frå GNSS-tida
            R.timeset(R.gpst2utc(t))
            if abs(off) > abs(self.stats["clock_off"] or 0):
                self.stats["clock_off"] = round(off)        # største avvik som er retta (til feilsøkaren)
            first = True
        if self.rb.time.time == 0 or abs(R.timediff(self.rb.time, t)) > 86400.0:
            self.rb.time = t
        if first:
            self._fix_weeks()

    def _week_shift(self, e):
        """Kor mange sekund banen e må flyttast (heile veker) for å liggje rundt GNSS-tida (0 = rett).
        Ein kringkasta bane har toe innanfor nokre timar frå no. Er han meir enn ei halv veke unna, er veka vald
        frå feil klokke – typisk 1024 veker feil (SFRBX/1019 har veke modulo 1024), ± 1 veke frå RTKLIB si eiga
        justering mot referansetida i RTCM."""
        ref = self.t_gnss if self.t_gnss is not None else self.t_ref
        if ref is None or not e.sat:
            return 0.0
        d = R.timediff(ref, e.toe)
        if abs(d) < 302400.0:
            return 0.0
        return round(d / 604800.0) * 604800.0

    def _shift(self, e, sec):
        e.toe = R.timeadd(e.toe, sec)
        e.toc = R.timeadd(e.toc, sec)
        e.ttr = R.timeadd(e.ttr, sec)
        e.week += int(round(sec / 604800.0))
        self.stats["eph_fixed"] += 1

    def _fix_weeks(self):
        for i in range(2 * R.MAXSAT):                       # GPS/Galileo/BeiDou … (andre halvdel: Galileo F/NAV)
            e = self.nav.eph[i]
            if e.sat:
                sec = self._week_shift(e)
                if sec:
                    self._shift(e, sec)

    def _copy_eph(self, src, sat, eset=0):
        """Kopier ei ny bane frå ein roverstraum til den felles nav-strukturen som rtkpos brukar."""
        if not sat or sat < 1:
            return
        prn = R.Arr1Dint(1)
        sys_ = R.satsys(sat, prn)
        try:
            if sys_ == R.SYS_GLO:
                if not 1 <= prn[0] <= self.nav.ng:
                    return
                self.nav.geph[prn[0] - 1] = src.geph[prn[0] - 1]
            else:
                k = sat - 1 + (R.MAXSAT if eset else 0)     # Galileo F/NAV ligg i andre halvdel
                self.nav.eph[k] = src.eph[k]
                sec = self._week_shift(self.nav.eph[k])
                if sec:
                    self._shift(self.nav.eph[k], sec)
        except Exception as e:
            self.stats["err"] = f"Bane frå mottakaren: {e}"
            return
        self.stats["eph"] += 1
        self.stats["eph_rover"] += 1

    def _solve(self, obs):
        nr = min(obs.n, 128)
        if nr == 0:
            return None
        nb = self.base_n if self.base_t is not None else 0
        if nb:
            # Alder på basedataa: tid rover − tid base. Same epoke gir 0; basen er normalt 1 Hz og roveren opp til 10 Hz.
            dt = R.timediff(obs.data[0].time, self.base_t)
            self.stats["tdiff"] = round(dt, 3)
            if abs(dt) > MAX_BASE_AGE:
                self.stats["err"] = (f"Basen og roveren har {dt:.0f} s ulik tid – "
                                     + ("sjekk klokka/veka" if abs(dt) > 3600 else "basedataa er for gamle"))
                nb = 0
        # RTKLIB (rtkpos/selsat) krev at rover- og baseobservasjonane kvar for seg er sorterte etter satellittnummer.
        # Avkodaren legg satellittane inn i den rekkjefølgja meldingane kjem: ein mottakar som sender fleire meldingar
        # per epoke (t.d. Emlid RS+: 1002, 1010, 1107, 1117, 1127) gir då usortert liste og «no common satellite».
        arr = R.Arr1Dobsd_t(nr + nb)
        for k, i in enumerate(sorted(range(nr), key=lambda i: obs.data[i].sat)):
            arr[k] = obs.data[i]
            arr[k].rcv = 1
        for k, i in enumerate(sorted(range(nb), key=lambda i: self.base_obs[i].sat)):
            arr[nr + k] = self.base_obs[i]
        nav = self._nav()
        if time.time() - self._diag_t > 5.0:                 # oversikt til feilsøkaren kvart 5. s
            self._diag_t = time.time()
            try:
                self.stats["sats"] = self._satdiag(arr, nr, nb, nav)
            except Exception as e:
                self.stats["sats"] = {"feil": str(e)[:120]}
        # SNR-maska berre når roveren rapporterer SNR (RTKLIB reknar SNR 0 som under maska)
        self.rtk.opt.snrmask.ena[0] = 1 if any(arr[i].SNR[0] for i in range(nr)) else 0
        self.rtk.neb = 0                                    # feilmeldingar berre frå denne epoka (bufferen blir elles full
                                                            # og viser gamle meldingar – retta i v1.6.103)
        R.rtkpos(self.rtk, arr[0], nr + nb, nav)
        sol = self.rtk.sol
        st = int(sol.stat)
        key = {1: "fix", 2: "float"}.get(st, "single" if st in (3, 4, 5) else "none")
        self.stats[key] += 1
        self.stats["last_stat"] = st
        self.stats["last_ratio"] = round(float(sol.ratio), 1)
        if st == 0:
            # pyrtklib: errbuf[i] gir C-strengen frå posisjon i (til første NUL), ikkje eitt teikn – errbuf[0] er heile
            # bufferen for denne epoka (neb blir nullstilt før rtkpos).
            eb = str(self.rtk.errbuf[0] if self.rtk.neb else "").strip("\x00").strip()
            if eb:
                self.stats["err"] = eb.splitlines()[-1][:200]
            return None
        self.stats["sol"] += 1
        self.stats["last_sol"] = time.time()
        return self._gga(sol, st), {"stat": st, "ratio": float(sol.ratio), "ns": int(sol.ns), "age": float(sol.age)}

    def _satdiag(self, arr, nr, nb, nav):
        """Kor mange satellittar per system hos roveren, basen, felles, og felles med gyldig bane i nav.
        Gyldig bane = som i RTKLIB (seleph): GPS/Galileo/BeiDou/QZSS innanfor MAXDTOE (2 t), GLONASS innanfor
        MAXDTOE_GLO (30 min) frå epoka. Manglar banane, blir satellitten ikkje brukt – t.d. GLONASS når BRDC-fila
        er eldre enn ein halvtime og verken basen eller mottakaren sender 1020."""
        names = {R.SYS_GPS: "GPS", R.SYS_GLO: "GLONASS", R.SYS_GAL: "Galileo", R.SYS_CMP: "BeiDou",
                 R.SYS_QZS: "QZSS", R.SYS_SBS: "SBAS"}
        if nr == 0:
            return None
        t = arr[0].time
        prn = R.Arr1Dint(1)
        rov = {arr[i].sat for i in range(nr)}
        bas = {arr[nr + i].sat for i in range(nb)}
        ok = set()
        for i in range(nav.n):
            e = nav.eph[i]
            if e.sat and e.sat in rov and abs(R.timediff(t, e.toe)) <= R.MAXDTOE:
                ok.add(e.sat)
        for i in range(nav.ng):
            g = nav.geph[i]
            if g.sat and g.sat in rov and abs(R.timediff(t, g.toe)) <= R.MAXDTOE_GLO:
                ok.add(g.sat)
        out = {}
        for sat in rov | bas:
            n = names.get(R.satsys(sat, prn), "anna")
            d = out.setdefault(n, {"rover": 0, "base": 0, "felles": 0, "bane": 0})
            d["rover"] += sat in rov
            d["base"] += sat in bas
            if sat in rov and sat in bas:
                d["felles"] += 1
                d["bane"] += sat in ok
        return out

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


def fetch_brdc(folder, ua="SNOWMAN", now=None, max_age=3600):
    """Hent siste samla banefil (RINEX nav) frå BKG/IGS til folder og returner stien, eller None.
    NB: døgnfilene blir fullstendige først etter midnatt – for sanntid er baner frå mottakaren (eller basen) best.
    Brukt som reserve når straumane ikkje har baner."""
    import datetime as dt
    import gzip
    import os
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
        if out.exists() and time.time() - out.stat().st_mtime < max_age:
            BRDC_LAST.update(changed=False)
            return out
        # Spør først om fila hos kjelda er endra (HEAD: Last-Modified + storleik) – då kan SNOWMAN sjekke ofte utan å
        # laste ned heile fila kvar gong (v1.6.102). Kjelda kan svare utan desse felta; då blir fila lasta ned.
        meta = out.with_suffix(".meta")
        key = ""
        try:
            with nett.urlopen(urllib.request.Request(url + name, headers={"User-Agent": ua}, method="HEAD"), timeout=15) as r:
                lm, ln = r.headers.get("Last-Modified") or "", r.headers.get("Content-Length") or ""
                key = f"{lm}|{ln}" if (lm or ln) else ""
        except Exception:
            lm = ""
        BRDC_LAST.update(remote=lm or None, checked=time.time())
        if key and out.exists() and meta.exists() and meta.read_text() == key:
            os.utime(out, None)                             # uendra hos kjelda: rekna som fersk sjekk
            BRDC_LAST.update(changed=False)
            return out
        with nett.urlopen(urllib.request.Request(url + name, headers={"User-Agent": ua}), timeout=60) as r:
            data = gzip.decompress(r.read())
        tmp = out.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(out)
        if key:
            meta.write_text(key)
        BRDC_LAST.update(changed=True, loaded=time.time())
        return out
    return None


BRDC_LAST = {"changed": False, "remote": None, "checked": None, "loaded": None}   # siste sjekk av banefila (feilsøkaren)
