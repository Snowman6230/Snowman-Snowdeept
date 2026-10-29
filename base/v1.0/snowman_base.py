# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""SNOWMAN Base – RTK-base, NTRIP-caster og anleggsserver for SNOWMAN snødjupne.

Køyrer på Linux, Windows, NAS (Docker) eller ein liten PC / Raspberry Pi. Berre Python 3.10+ (pyserial for USB).

    python snowman_base.py                         start Base (standard)
    python snowman_base.py brukar legg-til NAMN    ny NTRIP-brukar (passord blir laga og vist)
    python snowman_base.py brukar fjern NAMN       fjern NTRIP-brukar
    python snowman_base.py brukar liste
    python snowman_base.py nokkel anlegg|kontor    ny anleggsnøkkel (maskinene) eller kontornøkkel
    python snowman_base.py mountpoint ny NAMN --seriell /dev/ttyACM0 | --rele caster:port/MP | --opplasting | --tcp-tenar PORT
                                         [--reserve caster:port/MP] [--brukar B --passord P] [--baud 115200]
    python snowman_base.py oppdater                hent siste versjon frå GitHub
    python snowman_base.py versjon

Mappa for data: --data DIR (standard: data/ ved sida av programmet, eller SNOWMAN_BASE_DATA).
"""
import argparse
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
from konfig import API_VERSION, SNOWMAN_MIN, VERSION, Config, new_secret, hash_pw   # noqa: E402
from lager import Store         # noqa: E402
from oppdatering import Updates, apply  # noqa: E402

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
        self.caster = Caster(self.cfg, self.mounts, self.events)
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
        for m in self.mounts.values():
            m.start()
        self.caster_port = self.caster.start(self._caster_port)
        self.web = api.start(self, self._web_port if self._web_port is not None else self.cfg["web"]["port"])
        self.web_port = self.web.server_address[1]
        for target in (lambda: straum.ticker(self.mounts, self.stop_ev), self._analyse_loop,
                       lambda: self.updates.loop(self.stop_ev), lambda: self.baner.loop(self.stop_ev)):
            threading.Thread(target=target, daemon=True).start()
        self.events.add(f"SNOWMAN Base {VERSION} starta: caster på port {self.caster_port}, nettside på port "
                        f"{self.web_port}, {len(self.mounts)} mountpoint", "ok")
        return self

    def stop(self):
        self.stop_ev.set()
        for m in self.mounts.values():
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

    # ---------- mountpoints frå kontorsida ----------
    def lagre_mountpoint(self, inn, gamalt_namn=None):
        """Lagrar eit nytt eller endra mountpoint og tek det i bruk med éin gong (utan omstart av Base)."""
        with self.mount_lock, self.cfg.lock:
            reserverte = {p for p in (self.caster_port, self.web_port, self.cfg["caster"]["port"],
                                      self.cfg["web"]["port"]) if p}
            m, melding = mountoppsett.lag(inn, self.cfg["mountpoints"], gamalt_namn, reserverte)
            liste = self.cfg["mountpoints"]
            i = next((k for k, x in enumerate(liste) if x.get("namn") == gamalt_namn), None) if gamalt_namn else None
            if i is None:
                liste.append(m)
            else:
                liste[i] = m
            self.cfg.save()
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
        return m, melding

    def fjern_mountpoint(self, namn):
        with self.mount_lock, self.cfg.lock:
            liste = self.cfg["mountpoints"]
            if not any(x.get("namn") == namn for x in liste):
                return False
            self.cfg.data["mountpoints"] = [x for x in liste if x.get("namn") != namn]
            self.cfg.save()
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
                           "klientar": sum(len(m.clients) for m in self.mounts.values()), **self.caster.stats},
                "web_port": self.web_port, "mountpoints": [m.status() for m in self.mounts.values()],
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
        sys.exit(f"Mountpointet {name} finst alt (endre data/base.json for å endre det).")
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
    cfg["mountpoints"].append({"namn": name, "skildring": a.skildring or name, "kjelder": src, "tillegg": [],
                               "byte_etter_s": 10, "innmalt": None, "test": False})
    cfg.save()
    print(f"Mountpoint {name} lagra med {len(src)} kjelde(r). Start Base på nytt for å ta det i bruk.")
    for e in extra:
        print(e)


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
    b.add_argument("handling", choices=["legg-til", "fjern", "liste"])
    b.add_argument("namn", nargs="?")
    b.add_argument("--passord")
    b.add_argument("--mountpoints", help="kommaseparert, standard alle")
    k = sub.add_parser("nokkel")
    k.add_argument("kva", choices=["anlegg", "kontor"])
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
    if a.cmd in ("brukar", "nokkel", "mountpoint"):
        cfg = Config(data_dir(a))
        cfg.first_setup()
        if a.cmd == "brukar":
            if a.handling == "liste":
                for u in cfg["brukarar"]:
                    print(f"{u['namn']:20} mountpoints: {', '.join(u.get('mountpoints') or ['*'])}")
                return
            if not a.namn:
                sys.exit("Oppgi namn.")
            if a.handling == "fjern":
                return print("Fjerna." if cfg.remove_user(a.namn) else "Fann ikkje brukaren.")
            pw = a.passord or new_secret(12)
            cfg.set_user(a.namn, pw, a.mountpoints.split(",") if a.mountpoints else None)
            return print(f"NTRIP-brukar {a.namn} / {pw}  (verkar med éin gong, ingen omstart)")
        if a.cmd == "nokkel":
            key = cfg.set_key(a.kva)
            return print(f"Ny {a.kva}snøkkel: {key}\nDen gamle verkar ikkje lenger. Nøkkelen blir berre vist no.")
        return cmd_mountpoint(a, cfg)

    base = SnowmanBase(data_dir(a), a.caster_port, a.web_port).start()
    print(f"SNOWMAN Base {VERSION}")
    print(f"  Data:        {base.data}")
    print(f"  NTRIP:       port {base.caster_port}  ({len(base.mounts)} mountpoint: {', '.join(base.mounts) or 'ingen enno'})")
    print(f"  Statusside:  http://localhost:{base.web_port}/   Kontor: http://localhost:{base.web_port}/kontor/")
    for line in base.first:
        print("  NY: " + line)
    if base.first:
        print(f"  (Innloggingane står òg i {base.data / 'NOKLAR.txt'} – ta vare på dei og slett fila.)")
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
