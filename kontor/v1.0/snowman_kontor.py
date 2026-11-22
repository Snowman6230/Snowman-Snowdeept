# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""SNOWMAN Kontor – anleggsserveren og kontorsida for SNOWMAN snødjupne (avgjerd 2026-11-22).

Køyrer på ein PC på anlegget (Windows, eller Linux). Berre Python 3.10+. Kontor har ingenting med korreksjonane å
gjere – det gjer SNOWMAN Base på Raspberry Pi-en ved antenna åleine. Ei oppdatering eller ein feil i Kontor kan
difor aldri stoppe korreksjonane til maskinene.

Kontor:  anleggspakkar til maskinene · forslag frå førarane · oversikt over maskinene · deling av snødjupne (v1.8) ·
         forbetringar og AI · status frå SNOWMAN Base (berre lesing).
Maskinene hentar anleggspakka når dei er på nettet på anlegget (wifi). PC-en treng ikkje stå på heile tida:
maskinene brukar siste pakke, og forslag ligg i kø i maskina til Kontor svarar att.

    python snowman_kontor.py                       start Kontor (standard, port 8790)
    python snowman_kontor.py brukar legg-til NAMN [--rolle maskin|kontor|begge]   ny brukar (spør etter passord)
    python snowman_kontor.py brukar passord NAMN   nytt passord (t.d. gløymt passord til kontorsida)
    python snowman_kontor.py brukar fjern NAMN
    python snowman_kontor.py brukar liste
    python snowman_kontor.py oppdater              hent siste versjon frå GitHub
    python snowman_kontor.py versjon

Mappa for data: --data DIR (standard: data/ ved sida av programmet, eller SNOWMAN_KONTOR_DATA).
"""
import argparse
import getpass
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
from ai import AI               # noqa: E402
from basestatus import BaseStatus  # noqa: E402
from hendingar import Events, disk_free  # noqa: E402
from konfig import API_VERSION, SNOWMAN_MIN, VERSION, Config, valid_pw   # noqa: E402
from lager import Store         # noqa: E402
from oppdatering import Updates, apply  # noqa: E402
from vern import Vern           # noqa: E402

RESTART_CODE = 3


class SnowmanKontor:
    def __init__(self, data_dir, web_port=None):
        self.data = Path(data_dir)
        self.cfg = Config(self.data)
        self.cfg.first_setup()
        self.events = Events(self.data)
        self.store = Store(self.data)
        self.vern = Vern(self.cfg, self.events)
        self.ai = AI(self.cfg, self.store, self.events)
        self.updates = Updates(self.cfg, self.events, self.restart)
        self.basestatus = BaseStatus(self.cfg, self.events)
        self.stop_ev = threading.Event()
        self.started = time.time()
        self._web_port = web_port
        self.web_port = None
        self.web = None

    def start(self):
        self.web = api.start(self, self._web_port if self._web_port is not None else self.cfg["web"]["port"])
        self.web_port = self.web.server_address[1]
        for target in (self._analyse_loop, self._config_loop, lambda: self.updates.loop(self.stop_ev),
                       lambda: self.basestatus.loop(self.stop_ev)):
            threading.Thread(target=target, daemon=True).start()
        self.events.add(f"SNOWMAN Kontor {VERSION} starta på port {self.web_port}", "ok")
        return self

    def stop(self):
        self.stop_ev.set()
        if self.web:
            self.web.shutdown()
            self.web.server_close()
        time.sleep(0.1)
        self.store.close()

    def restart(self):
        """Etter oppdatering. Som teneste: avslutt med kode 3 (tenesta startar Kontor att). Elles: start på nytt."""
        self.events.add("Startar på nytt etter oppdatering", "info")
        self.stop()
        if os.environ.get("SNOWMAN_KONTOR_TENESTE"):
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

    def _config_loop(self):
        """Brukarar endra med kommandoen medan Kontor køyrer, gjeld med éin gong."""
        while not self.stop_ev.wait(2.0):
            try:
                self.cfg.refresh()
            except Exception:
                pass

    def disk_free(self):
        return disk_free(self.data)

    def status(self):
        imp = self.store.improvements()
        bs = self.basestatus.last
        s = bs.get("status") or {}
        return {"ok": True, "program": "SNOWMAN Kontor", "namn": self.cfg["namn"], "anlegg": self.cfg["anlegg"],
                "versjon": VERSION, "api": API_VERSION, "snowman_min": SNOWMAN_MIN,
                "oppetid": round(time.time() - self.started), "web_port": self.web_port,
                "treng_admin": not self.cfg.has_admin(), "maskiner": self.store.machines(),
                "oppdatering": self.updates.info, "disk_gb": self.disk_free(), "pakke": self.store.package(),
                "forbetringar": {k: sum(1 for r in imp if r["alvor"] == k) for k in ("høg", "middels", "låg")},
                "ai": {"leverandor": self.cfg["ai"].get("leverandor", "av"), "siste": self.ai.last},
                "base": {"adresse": self.cfg["base"].get("adresse", ""), "t": bs.get("t"), "ok": bs.get("ok"),
                         "feil": bs.get("feil"), "versjon": s.get("versjon"), "mountpoints": s.get("mountpoints") or [],
                         "caster": s.get("caster")},
                "hendingar": self.events.latest(60)}


# ---------- kommandolinja ----------
def data_dir(a):
    return Path(a.data or os.environ.get("SNOWMAN_KONTOR_DATA") or HERE / "data")


def ask_pw():
    if not sys.stdin or not sys.stdin.isatty():
        sys.exit("Oppgi passordet med --passord (eller køyr kommandoen i eit vindauge, så blir du spurd).")
    p1 = getpass.getpass("Nytt passord (minst 8 teikn, blir ikkje vist): ")
    valid_pw(p1)
    if getpass.getpass("Skriv passordet ein gong til: ") != p1:
        sys.exit("Passorda var ikkje like. Ingenting er endra.")
    return p1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="snowman-kontor", description="SNOWMAN Kontor – anleggsserver og kontorside")
    ap.add_argument("--data", help="mappe for innstillingar og data")
    ap.add_argument("--port", type=int, help="port for kontorsida og maskinene (standard 8790)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("start")
    sub.add_parser("versjon")
    sub.add_parser("oppdater")
    b = sub.add_parser("brukar")
    b.add_argument("handling", choices=["legg-til", "passord", "fjern", "liste"])
    b.add_argument("namn", nargs="?")
    b.add_argument("--passord", help="utan: spør (passordet blir ikkje vist)")
    b.add_argument("--rolle", choices=["maskin", "kontor", "begge"], help="maskin = tråkkemaskinene (standard), kontor = administrator")
    a = ap.parse_args(argv)

    if a.cmd == "versjon":
        return print(f"SNOWMAN Kontor {VERSION} (API v{API_VERSION}, krev SNOWMAN {SNOWMAN_MIN})")
    if a.cmd == "oppdater":
        changed, _ = apply()
        return sys.exit(RESTART_CODE if changed and os.environ.get("SNOWMAN_KONTOR_TENESTE") else 0)
    if a.cmd == "brukar":
        cfg = Config(data_dir(a))
        cfg.first_setup()
        if a.handling == "liste":
            if not cfg["brukarar"]:
                print("Ingen brukarar enno. Lag administrator: brukar legg-til NAMN --rolle kontor")
            for u in cfg["brukarar"]:
                print(f"{u['namn']:20} roller: {', '.join(u.get('roller', []))}")
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
            roles = {"maskin": ["maskin"], "kontor": ["kontor"], "begge": ["maskin", "kontor"]}.get(a.rolle)
            if a.handling == "legg-til" and roles is None:
                roles = ["maskin"]
            u = cfg.set_user(a.namn, pw, roles)
        except ValueError as e:
            sys.exit(str(e))
        kva = "nytt passord" if a.handling == "passord" else f"oppretta med rolle {', '.join(u['roller'])}"
        return print(f"Brukar {u['namn']}: {kva}. Gjeld med éin gong – også om Kontor køyrer.")

    try:
        k = SnowmanKontor(data_dir(a), a.port).start()
    except OSError as e:
        sys.exit(f"Kunne ikkje starte SNOWMAN Kontor: {e}\n"
                 f"Er porten i bruk? Køyrer SNOWMAN Kontor alt (sjå etter eit anna vindauge, eller tenesta)?")
    print(f"SNOWMAN Kontor {VERSION}")
    print(f"  Data:        {k.data}")
    print(f"  Kontorsida:  http://localhost:{k.web_port}/")
    print(f"  Maskinene:   http://<IP-adressa til denne PC-en>:{k.web_port} (same nett/wifi på anlegget)")
    if not k.cfg.has_admin():
        print(f"  FØRST:       lag administrator (brukarnamn og passord) på http://localhost:{k.web_port}/")
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
        k.stop()
        print("SNOWMAN Kontor stoppa.")


if __name__ == "__main__":
    main()
