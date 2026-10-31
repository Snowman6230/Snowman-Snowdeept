# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""SNOWMAN Base – RTK-base, NTRIP-caster og anleggsserver for SNOWMAN snødjupne.

Køyrer på Linux, Windows, NAS (Docker) eller ein liten PC / Raspberry Pi. Berre Python 3.10+ (pyserial for USB).

    python snowman_base.py                         start Base (standard)
    python snowman_base.py brukar legg-til NAMN [--rolle ntrip|kontor|begge]   ny brukar (spør etter passord)
    python snowman_base.py brukar passord NAMN     nytt passord (t.d. gløymt passord til kontorsida)
    python snowman_base.py brukar fjern NAMN
    python snowman_base.py brukar liste
    python snowman_base.py mountpoint ny NAMN --seriell /dev/ttyACM0 | --rele caster:port/MP | --opplasting | --tcp-tenar PORT
                                         [--reserve caster:port/MP] [--brukar B --passord P] [--baud 115200]
    python snowman_base.py oppdater                hent siste versjon frå GitHub
    python snowman_base.py versjon

Mappa for data: --data DIR (standard: data/ ved sida av programmet, eller SNOWMAN_BASE_DATA).
Kommandoane kan køyrast medan Base køyrer (t.d. i eit anna vindauge): Base les endringa innan to sekund.
"""
import argparse
import copy
import getpass
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import api                      # noqa: E402
import forbetring               # noqa: E402
import mountoppsett             # noqa: E402
import straum                   # noqa: E402
from ai import AI               # noqa: E402
from baner import Baner         # noqa: E402
from caster import Caster       # noqa: E402
from konfig import API_VERSION, SNOWMAN_MIN, VERSION, Config, new_secret, hash_pw, valid_pw   # noqa: E402
from lager import Store         # noqa: E402
from oppdatering import Updates, apply  # noqa: E402
from tilgang import Tilgang     # noqa: E402
from vern import Vern           # noqa: E402

RESTART_CODE = 3


class SnowmanBase:
    def __init__(self, data_dir, caster_port=None, web_port=None):
        self.data = Path(data_dir)
        self.cfg = Config(self.data)
        self.first = self.cfg.first_setup()
        self.events = straum.Events(self.data)
        lg = self.cfg["logg"]
        self.rawlog = straum.RawLog(self.data, lg.get("dagar", 30), lg.get("maks_mb", 5000))
        if mountoppsett.sikre_id(self.cfg):
            self.cfg.save()
        self.mounts = straum.build(self.cfg["mountpoints"], self.events, self.rawlog)
        self.mount_lock = threading.Lock()
        self.store = Store(self.data)
        self.vern = Vern(self.cfg, self.events)
        self.caster = Caster(self.cfg, self.mounts, self.events, self.vern)
        self.tilgang = Tilgang(self)
        self.ai = AI(self.cfg, self.store, self.events)
        self.updates = Updates(self.cfg, self.events, self.restart)
        self.baner = Baner(self.data, self.cfg, self.events)
        self.stop_ev = threading.Event()
        self.started = time.time()
        self._caster_port = caster_port
        self._web_port = web_port
        self.caster_port = None
        self.web_port = None
        self.web = None
        self._usage = (0.0, None)

    # ---------- drift ----------
    def start(self):
        for m in list(self.mounts.values()):
            m.start()
        self.caster_port = self.caster.start(self._caster_port)
        self.web = api.start(self, self._web_port if self._web_port is not None else self.cfg["web"]["port"])
        self.web_port = self.web.server_address[1]
        for target in (lambda: straum.ticker(self.mounts, self.stop_ev), self._analyse_loop, self._config_loop,
                       lambda: self.updates.loop(self.stop_ev), lambda: self.baner.loop(self.stop_ev),
                       lambda: self.tilgang.loop(self.stop_ev)):
            threading.Thread(target=target, daemon=True).start()
        self.events.add(f"SNOWMAN Base {VERSION} starta: caster på port {self.caster_port}, nettside på port "
                        f"{self.web_port}, {len(self.mounts)} mountpoint", "ok")
        return self

    def stop(self):
        self.stop_ev.set()
        for m in list(self.mounts.values()):
            m.stop()
        self.caster.stop()
        if self.web:
            self.web.shutdown()
            self.web.server_close()
        self.rawlog.close()
        time.sleep(0.1)
        self.store.close()

    def restart(self):
        """Etter oppdatering. Under systemd/Docker: avslutt med kode 3 (tenesta startar Base att). Elles: start på nytt."""
        self.events.add("Startar på nytt etter oppdatering", "info")
        self.stop()
        if os.environ.get("SNOWMAN_BASE_TENESTE"):
            os._exit(RESTART_CODE)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _analyse_loop(self):
        self.stop_ev.wait(120)
        last_ai = 0.0
        while not self.stop_ev.is_set():
            try:
                forbetring.run(self)
                self.store.clean(self.cfg["deling"].get("behald_dagar", 30))
                hours = float(self.cfg["ai"].get("intervall_t", 24) or 24)
                if self.ai.enabled() and time.time() - last_ai > hours * 3600:
                    last_ai = time.time()
                    try:
                        self.ai.analyse(self)
                    except Exception:
                        pass                       # feilen står i hendingane og på kontorsida
            except Exception as e:
                self.events.add(f"Forbetringsanalysen feila: {e}", "feil")
            self.stop_ev.wait(900)

    # ---------- innstillingar endra utanfrå (kommandoar medan Base køyrer) ----------
    def _config_loop(self):
        while not self.stop_ev.wait(2.0):
            try:
                self.cfg.refresh()
                if self.cfg.pop_external():
                    self.apply_config()
            except Exception as e:
                self.events.add(f"Kunne ikkje ta i bruk endra innstillingar: {e}", "feil")

    @staticmethod
    def _norm(mc):
        d = copy.deepcopy(mc)
        for i, sc in enumerate(d.get("kjelder", [])):
            sc.setdefault("namn", f"{sc.get('type')}{i + 1}")
        for i, sc in enumerate(d.get("tillegg", [])):
            sc.setdefault("namn", f"tillegg{i + 1}")
        return json.dumps(d, sort_keys=True, ensure_ascii=False)

    def apply_config(self):
        """Ta i bruk innstillingar som er endra i fila (brukarar gjeld med éin gong; mountpoints blir bygde på nytt)."""
        with self.mount_lock:
            if mountoppsett.sikre_id(self.cfg):
                self.cfg.save()
            new = {mc["namn"]: mc for mc in self.cfg["mountpoints"] if mc.get("namn")}
            endra = []
            for name in list(self.mounts):
                if name not in new:
                    self.mounts.pop(name).stop()
                    endra.append(f"{name} sletta")
            for name, mc in new.items():
                old = self.mounts.get(name)
                if old is not None and self._norm(old.cfg) == self._norm(mc):
                    old.cfg = mc                       # same oppsett – bruk den nye utgåva av dicten
                    continue
                if old is not None:
                    old.stop()
                m = straum.Mountpoint(mc, self.events, self.rawlog)
                self.mounts[name] = m
                m.start()
                endra.append(f"{name} {'endra' if old else 'ny'}")
        self.events.add("Innstillingane er endra utanfrå (kommando eller fil) og tekne i bruk"
                        + (f": mountpoint {', '.join(endra)}" if endra else " (brukarar/innstillingar)"), "ok")

    # ---------- mountpoints frå kontorsida ----------
    def lagre_mountpoint(self, inn, gamalt_namn=None):
        """Lagrar eit nytt eller endra mountpoint og tek det i bruk med éin gong (utan omstart av Base)."""
        reserverte = {p for p in (self.caster_port, self.web_port, self.cfg["caster"]["port"],
                                  self.cfg["web"]["port"]) if p}
        with self.mount_lock:
            def fn(d):
                m, melding = mountoppsett.lag(inn, d["mountpoints"], gamalt_namn, reserverte)
                liste = d["mountpoints"]
                i = next((k for k, x in enumerate(liste) if x.get("namn") == gamalt_namn), None) if gamalt_namn else None
                if i is None:
                    liste.append(m)
                else:
                    liste[i] = m
                return m, melding
            m, melding = self.cfg.update(fn)
            self.cfg.pop_external()                    # resten av fila er teken i bruk under
            gamal = self.mounts.pop(gamalt_namn, None) if gamalt_namn else None
            if gamal:
                gamal.stop()
            ny = straum.Mountpoint(m, self.events, self.rawlog)
            self.mounts[m["namn"]] = ny
            ny.start()
        kva = "endra" if gamalt_namn else "oppretta"
        namn = m["namn"] + (f" (før {gamalt_namn})" if gamalt_namn and gamalt_namn != m["namn"] else "")
        self.events.add(f"Mountpoint {namn} {kva} frå kontorsida: {len(m['kjelder'])} kjelde(r) – "
                        + ", ".join(k.get("namn", "") for k in m["kjelder"]), "ok")
        self.apply_config_quiet()
        return m, melding

    def apply_config_quiet(self):
        """Etter ei endring frå kontorsida: ta òg i bruk andre mountpoints som var endra i fila (sjeldan)."""
        names = {mc.get("namn") for mc in self.cfg["mountpoints"]}
        if names != set(self.mounts):
            self.apply_config()

    def fjern_mountpoint(self, namn):
        with self.mount_lock:
            def fn(d):
                if not any(x.get("namn") == namn for x in d["mountpoints"]):
                    return False
                d["mountpoints"] = [x for x in d["mountpoints"] if x.get("namn") != namn]
                return True
            ok = self.cfg.update(fn)
            if not ok:
                return False
            gamal = self.mounts.pop(namn, None)
            if gamal:
                gamal.stop()
        self.events.add(f"Mountpoint {namn} sletta frå kontorsida", "feil")
        return True

    def disk_free(self):
        return straum.disk_free(self.data)

    def status(self):
        t, u = self._usage
        if time.time() - t > 60:
            self._usage = (time.time(), self.rawlog.usage())
        imp = self.store.improvements()
        return {"ok": True, "namn": self.cfg["namn"], "anlegg": self.cfg["anlegg"], "versjon": VERSION,
                "api": API_VERSION, "snowman_min": SNOWMAN_MIN, "oppetid": round(time.time() - self.started),
                "caster": {"port": self.caster_port, "innlogging": self.cfg["caster"].get("krev_innlogging", True),
                           "klientar": sum(len(m.clients) for m in list(self.mounts.values())), **self.caster.stats},
                "web_port": self.web_port, "mountpoints": [m.status() for m in list(self.mounts.values())],
                "treng_admin": not self.cfg.has_admin(),
                "maskiner": self.store.machines(), "oppdatering": self.updates.info, "baner": self.baner.info,
                "disk_gb": self.disk_free(), "radata": self._usage[1],
                "pakke": self.store.package(), "forbetringar": {k: sum(1 for r in imp if r["alvor"] == k)
                                                                 for k in ("høg", "middels", "låg")},
                "ai": {"leverandor": self.cfg["ai"].get("leverandor", "av"), "siste": self.ai.last},
                "hendingar": self.events.latest(60)}


# ---------- kommandolinja ----------
def data_dir(a):
    return Path(a.data or os.environ.get("SNOWMAN_BASE_DATA") or HERE / "data")


def parse_caster(s):
    """«caster:port/MP» → (caster, port, mp)."""
    host, _, mp = s.partition("/")
    h, _, p = host.partition(":")
    return h, int(p or 2101), mp


def cmd_mountpoint(a, cfg):
    name = a.namn
    if any(m["namn"] == name for m in cfg["mountpoints"]):
        sys.exit(f"Mountpointet {name} finst alt (endre det på kontorsida › Mountpoints).")
    src, extra = [], []
    if a.seriell:
        src.append({"type": "seriell", "namn": "mottakar", "port": a.seriell, "baud": a.baud})
    if a.tcp_tenar:
        src.append({"type": "tcp-tenar", "namn": "inn", "port": a.tcp_tenar})
    if a.opplasting:
        pw = new_secret(12)
        src.append({"type": "opplasting", "namn": "opplasting", "hash": hash_pw(pw)})
        extra.append(f"Opplastingspassord for {name}: {pw}  (str2str: -out ntrips://:{pw}@<base>:"
                     f"{cfg['caster']['port']}/{name})")
    for i, r in enumerate(([a.rele] if a.rele else []) + (a.reserve or [])):
        h, p, mp = parse_caster(r)
        src.append({"type": "ntrip", "namn": f"rele-{mp}" if i == 0 and a.rele else f"reserve-{mp}", "caster": h,
                    "port": p, "mountpoint": mp, "brukar": a.brukar or "", "passord": a.passord or ""})
    if not src:
        sys.exit("Oppgi minst éi kjelde: --seriell, --tcp-tenar, --opplasting eller --rele.")
    cfg.update(lambda d: d["mountpoints"].append({"namn": name, "skildring": a.skildring or name, "kjelder": src,
                                                  "tillegg": [], "byte_etter_s": 10, "innmalt": None, "test": False}))
    print(f"Mountpoint {name} lagra med {len(src)} kjelde(r). Base tek det i bruk innan to sekund (om han køyrer).")
    for e in extra:
        print(e)


def ask_pw():
    if not sys.stdin or not sys.stdin.isatty():
        sys.exit("Oppgi passordet med --passord (eller køyr kommandoen i eit vindauge, så blir du spurd).")
    p1 = getpass.getpass("Nytt passord (minst 8 teikn, blir ikkje vist): ")
    valid_pw(p1)
    if getpass.getpass("Skriv passordet ein gong til: ") != p1:
        sys.exit("Passorda var ikkje like. Ingenting er endra.")
    return p1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="snowman-base", description="SNOWMAN Base – RTK-base og anleggsserver")
    ap.add_argument("--data", help="mappe for innstillingar og data")
    ap.add_argument("--caster-port", type=int)
    ap.add_argument("--web-port", type=int)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("start")
    sub.add_parser("versjon")
    sub.add_parser("oppdater")
    b = sub.add_parser("brukar")
    b.add_argument("handling", choices=["legg-til", "passord", "fjern", "liste"])
    b.add_argument("namn", nargs="?")
    b.add_argument("--passord", help="utan: spør (passordet blir ikkje vist)")
    b.add_argument("--rolle", choices=["ntrip", "kontor", "begge"], help="ntrip = maskinene (standard), kontor = administrator")
    b.add_argument("--mountpoints", help="kommaseparert, standard alle")
    k = sub.add_parser("nokkel")
    k.add_argument("kva", nargs="?")
    m = sub.add_parser("mountpoint")
    m.add_argument("handling", choices=["ny"])
    m.add_argument("namn")
    m.add_argument("--skildring")
    m.add_argument("--seriell")
    m.add_argument("--baud", type=int, default=115200)
    m.add_argument("--tcp-tenar", type=int)
    m.add_argument("--opplasting", action="store_true")
    m.add_argument("--rele")
    m.add_argument("--reserve", action="append")
    m.add_argument("--brukar")
    m.add_argument("--passord")
    a = ap.parse_args(argv)

    if a.cmd == "versjon":
        return print(f"SNOWMAN Base {VERSION} (API v{API_VERSION}, krev SNOWMAN {SNOWMAN_MIN} for deling)")
    if a.cmd == "oppdater":
        changed, _ = apply()
        return sys.exit(RESTART_CODE if changed and os.environ.get("SNOWMAN_BASE_TENESTE") else 0)
    if a.cmd == "nokkel":
        return print("Nøklar er erstatta av brukarnamn og passord (v1.2).\n"
                     "  Nytt passord:        brukar passord NAMN\n"
                     "  Ny administrator:    brukar legg-til NAMN --rolle kontor\n"
                     "  Ny maskinbrukar:     brukar legg-til NAMN")
    if a.cmd in ("brukar", "mountpoint"):
        cfg = Config(data_dir(a))
        cfg.first_setup()
        if a.cmd == "brukar":
            if a.handling == "liste":
                if not cfg["brukarar"]:
                    print("Ingen brukarar enno. Lag administrator: brukar legg-til NAMN --rolle kontor")
                for u in cfg["brukarar"]:
                    print(f"{u['namn']:20} roller: {', '.join(u.get('roller', [])):14} "
                          f"mountpoints: {', '.join(u.get('mountpoints') or ['*'])}")
                return
            if not a.namn:
                sys.exit("Oppgi brukarnamn.")
            try:
                if a.handling == "fjern":
                    return print("Sletta." if cfg.remove_user(a.namn) else "Fann ikkje brukaren.")
                finst = cfg.find_user(a.namn)
                if a.handling == "passord" and not finst:
                    sys.exit(f"Fann ikkje brukaren {a.namn}. Sjå «brukar liste».")
                if a.handling == "legg-til" and finst:
                    sys.exit(f"Brukaren {finst['namn']} finst alt. Nytt passord: brukar passord {finst['namn']}")
                pw = a.passord if a.passord is not None else ask_pw()
                roles = {"ntrip": ["ntrip"], "kontor": ["kontor"], "begge": ["ntrip", "kontor"]}.get(a.rolle)
                if a.handling == "legg-til" and roles is None:
                    roles = ["ntrip"]
                u = cfg.set_user(a.namn, pw, a.mountpoints.split(",") if a.mountpoints else None, roles)
            except ValueError as e:
                sys.exit(str(e))
            kva = "nytt passord" if a.handling == "passord" else f"oppretta med rolle {', '.join(u['roller'])}"
            return print(f"Brukar {u['namn']}: {kva}. Gjeld med éin gong – også om Base køyrer.")
        return cmd_mountpoint(a, cfg)

    try:
        base = SnowmanBase(data_dir(a), a.caster_port, a.web_port).start()
    except OSError as e:
        sys.exit(f"Kunne ikkje starte SNOWMAN Base: {e}\n"
                 f"Er porten i bruk? Køyrer SNOWMAN Base alt (sjå etter eit anna vindauge, eller tenesta)?")
    print(f"SNOWMAN Base {VERSION}")
    print(f"  Data:        {base.data}")
    print(f"  NTRIP:       port {base.caster_port}  ({len(base.mounts)} mountpoint: {', '.join(base.mounts) or 'ingen enno'})")
    print(f"  Statusside:  http://localhost:{base.web_port}/   Kontor: http://localhost:{base.web_port}/kontor/")
    if not base.cfg.has_admin():
        print(f"  FØRST:       lag administrator (brukarnamn og passord) på http://localhost:{base.web_port}/kontor/")
        print("               eller med kommandoen:  brukar legg-til NAMN --rolle kontor")
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: stop.set())
        except (ValueError, OSError):
            pass
    try:
        while not stop.wait(1):
            pass
    finally:
        base.stop()
        print("SNOWMAN Base stoppa.")


if __name__ == "__main__":
    main()
