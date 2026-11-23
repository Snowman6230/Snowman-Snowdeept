# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""SNOWMAN Office – anleggsserveren og kontorsida for SNOWMAN Snowdeep (avgjerd 2026-11-22).

Køyrer på ein PC på anlegget (Windows, eller Linux). Berre Python 3.10+. Office har ingenting med korreksjonane å
gjere – det gjer SNOWMAN Base på Raspberry Pi-en ved antenna åleine. Ei oppdatering eller ein feil i Office kan
difor aldri stoppe korreksjonane til maskinene.

Office:  kart og anlegg – SNOWMAN Snowdeep i kontormodus (same kart, 3D, terreng, trasear, hindringar og
         kontrollpunkt som i maskina, utan GNSS), med «Publiser til maskinene» (Office startar det sjølv, port 8765) ·
         anleggspakkar med terreng · forslag frå førarane · oversikt over maskinene · deling av snødjupne (v1.8) ·
         forbetringar og AI · status frå SNOWMAN Base (berre lesing).
Maskinene hentar anleggspakka når dei er på nettet på anlegget (wifi). PC-en treng ikkje stå på heile tida:
maskinene brukar siste pakke, og forslag ligg i kø i maskina til Office svarar att.

    python snowman_kontor.py                       start Office (standard, port 8790)
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
import secrets
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import api                      # noqa: E402
import oppdatering              # noqa: E402
import forbetring               # noqa: E402
from ai import AI               # noqa: E402
from basestatus import BaseStatus  # noqa: E402
from hendingar import Events, disk_free  # noqa: E402
from konfig import API_VERSION, SNOWMAN_MIN, VERSION, Config, valid_pw   # noqa: E402
from lager import Store         # noqa: E402
from oppdatering import Updates, apply  # noqa: E402
from vern import Vern           # noqa: E402

RESTART_CODE = 3


def lag_snarveg(data, events=None, tving=False):
    """Windows: snarvegen «SNOWMAN Office» på skrivebordet (for alle brukarar) med eige ikon. Blir laga éin gong –
    slettar nokon han, kjem han ikkje att (merket data/snarveg.txt). INSTALLER-WINDOWS.bat lagar han òg."""
    merke = Path(data) / "snarveg.txt"
    if os.name != "nt" or (merke.exists() and not tving):
        return False
    vbs, ico = HERE / "OPNE-SNOWMAN-OFFICE.vbs", HERE / "ikon" / "snowman-office.ico"
    ps = ("$ErrorActionPreference='Stop'; $w=New-Object -ComObject WScript.Shell; "
          "foreach($d in @([Environment]::GetFolderPath('CommonDesktopDirectory'),"
          "[Environment]::GetFolderPath('CommonPrograms'))){ if($d){ "
          "$s=$w.CreateShortcut((Join-Path $d 'SNOWMAN Office.lnk')); "
          f"$s.TargetPath=(Join-Path $env:SystemRoot 'System32\\wscript.exe'); $s.Arguments=[char]34+'{vbs}'+[char]34; "
          f"$s.WorkingDirectory='{HERE}'; $s.IconLocation='{ico},0'; "
          "$s.Description='SNOWMAN Office - kart og anlegg (Alpindata)'; $s.Save() } }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout or "").strip()[:200])
        merke.write_text(time.strftime("%Y-%m-%d %H:%M") + " – snarvegen SNOWMAN Office laga\n", "utf-8")
        events and events.add("Snarvegen «SNOWMAN Office» er lagd på skrivebordet", "ok")
        return True
    except Exception as e:
        events and events.add(f"Snarvegen på skrivebordet kunne ikkje lagast: {e}", "feil")
        return False


class SnowmanKontor:
    def __init__(self, data_dir, web_port=None, kartvising=None, maskinport=None):
        self.data = Path(data_dir)
        self.cfg = Config(self.data)
        self.cfg.first_setup()
        self.events = Events(self.data)
        self.store = Store(self.data)
        self.vern = Vern(self.cfg, self.events)
        self.ai = AI(self.cfg, self.store, self.events)
        self.updates = Updates(self.cfg, self.events, self.restart, self.restart_kart)
        self.basestatus = BaseStatus(self.cfg, self.events)
        self.stop_ev = threading.Event()
        self.started = time.time()
        self._web_port = web_port
        self.web_port = None
        self.web = None
        self.maskin_srv = None
        self._maskinport = maskinport
        self.kartvising = self.cfg["kartvising"].get("start", True) if kartvising is None else kartvising
        self.kart = None                       # SNOWMAN Snowdeep i kontormodus (underprosess)
        self._kart_omstart = False
        self.lokal_nokkel = self._lokal_nokkel()

    def _lokal_nokkel(self):
        """Nøkkel som berre SNOWMAN Snowdeep i kontormodus på same PC får (ny ved kvar oppstart)."""
        return secrets.token_urlsafe(24)

    # ---------- SNOWMAN Snowdeep i kontormodus ----------
    @staticmethod
    def snodjupne_mappe():
        """Nyaste SNOWMAN Snowdeep ved sida av Office (repoet eller SNOWMAN-Office.zip: kontor/ og pc/ side om side)."""
        return oppdatering.pc_mappe()

    def restart_kart(self):
        """Etter ny versjon av kartet (SNOWMAN Snowdeep): start berre kartet på nytt – kontorsida og maskinporten
        held fram, og maskinene merkar ingenting."""
        self._kart_omstart = True
        if self.kart is not None and self.kart.poll() is None:
            self.kart.terminate()
            try:
                self.kart.wait(10)
            except subprocess.TimeoutExpired:
                self.kart.kill()

    def anlegg_port(self):
        return int(self.cfg["kartvising"].get("port") or 8765) if self.kartvising else None

    def _kart_loop(self):
        env = dict(os.environ, SNOWMAN_MODUS="kontor", SNOWMAN_KONTOR_URL=f"http://127.0.0.1:{self.web_port}",
                   SNOWMAN_KONTOR_NOKKEL=self.lokal_nokkel)
        logf = self.data / "kartvising.log"
        feil = 0
        while not self.stop_ev.is_set():
            # mappa blir funnen på nytt kvar gong: etter ei oppdatering kan det ha kome ei nyare (t.d. pc/v1.7)
            d = self.snodjupne_mappe()
            if not d:
                self.events.add("Fann ikkje SNOWMAN Snowdeep (pc/) ved sida av Office – kart og anlegg er ikkje "
                                "tilgjengeleg", "feil")
                return
            try:
                with open(logf, "a", encoding="utf-8") as lf:
                    oppdatering.installer_kart_pakkar(lambda t: lf.write(t + "\n"), d)
            except Exception as e:
                self.events.add(f"Pakkane til kartet kunne ikkje installerast: {e}", "feil")
            cmd = [sys.executable, str(d / "snowman_pc.py"), "--kontor", "--http-port", str(self.anlegg_port())]
            self._kart_omstart = False
            t0 = time.time()
            with open(logf, "a", encoding="utf-8") as lf:
                self.kart = subprocess.Popen(cmd, cwd=str(d), env=env, stdout=lf, stderr=subprocess.STDOUT)
                self.events.add(f"Kart og anlegg (SNOWMAN Snowdeep {d.name} i kontormodus) starta på "
                                f"http://localhost:{self.anlegg_port()}/", "ok")
                while self.kart.poll() is None and not self.stop_ev.wait(1):
                    pass
            if self.stop_ev.is_set():
                break
            if self._kart_omstart:
                self.events.add("Kart og anlegg startar på nytt med den nye versjonen", "info")
                feil = 0
                continue
            feil = feil + 1 if time.time() - t0 < 60 else 0
            self.events.add(f"Kart og anlegg stoppa (kode {self.kart.returncode}) – ny start om {min(60, 5 * feil)} s. "
                            f"Sjå data/kartvising.log", "feil")
            self.stop_ev.wait(min(60, 5 * feil))

    def start(self):
        self.web = api.start(self, self._web_port if self._web_port is not None else self.cfg["web"]["port"])
        self.web_port = self.web.server_address[1]
        # maskinport: None = innstillinga (0 = av), False = av, tal = den porten (0 = ledig port, til testar)
        mp = self.cfg["web"].get("maskinport", 8791) if self._maskinport is None else self._maskinport
        if mp is not False and (mp or self._maskinport is not None):
            try:
                self.maskin_srv = api.start_maskinport(self, mp)
            except OSError as e:
                self.events.add(f"Maskinporten {mp} kunne ikkje opnast: {e}", "feil")
        loops = [self._analyse_loop, self._config_loop, lambda: self.updates.loop(self.stop_ev),
                 lambda: self.basestatus.loop(self.stop_ev)]
        if self.kartvising:
            loops.append(self._kart_loop)
            loops.append(self.snarveg)
        for target in loops:
            threading.Thread(target=target, daemon=True).start()
        self.events.add(f"SNOWMAN Office {VERSION} starta på port {self.web_port}", "ok")
        return self

    def snarveg(self):
        return lag_snarveg(self.data, self.events)

    def stop(self):
        self.stop_ev.set()
        if self.kart is not None and self.kart.poll() is None:
            self.kart.terminate()
            try:
                self.kart.wait(10)
            except subprocess.TimeoutExpired:
                self.kart.kill()
        for srv in (self.web, self.maskin_srv):
            if srv:
                srv.shutdown()
                srv.server_close()
        time.sleep(0.1)
        self.store.close()

    def restart(self):
        """Etter oppdatering. Som teneste: avslutt med kode 3 (tenesta startar Office att). Elles: start på nytt."""
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
        """Brukarar endra med kommandoen medan Office køyrer, gjeld med éin gong."""
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
        return {"ok": True, "program": "SNOWMAN Office", "namn": self.cfg["namn"], "anlegg": self.cfg["anlegg"],
                "versjon": VERSION, "api": API_VERSION, "snowman_min": SNOWMAN_MIN,
                "oppetid": round(time.time() - self.started), "web_port": self.web_port,
                "maskinport": self.maskin_srv.server_address[1] if self.maskin_srv else None,
                "kartvising": {"port": self.anlegg_port(), "koyrer": bool(self.kart and self.kart.poll() is None)},
                "treng_admin": not self.cfg.has_admin(), "maskiner": self.store.machines(),
                "oppdatering": self.updates.info, "kart_versjon": self.updates.info.get("kart"), "disk_gb": self.disk_free(), "pakke": self.store.package(),
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
    ap = argparse.ArgumentParser(prog="snowman-kontor", description="SNOWMAN Office – anleggsserver og kontorside")
    ap.add_argument("--data", help="mappe for innstillingar og data")
    ap.add_argument("--port", type=int, help="port for kontorsida og maskinene (standard 8790)")
    ap.add_argument("--utan-kart", action="store_true", help="ikkje start kart og anlegg (SNOWMAN Snowdeep i kontormodus)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("start")
    sub.add_parser("versjon")
    sub.add_parser("oppdater")
    sub.add_parser("snarveg", help="lag snarvegen «SNOWMAN Office» på skrivebordet på nytt (Windows)")
    b = sub.add_parser("brukar")
    b.add_argument("handling", choices=["legg-til", "passord", "fjern", "liste"])
    b.add_argument("namn", nargs="?")
    b.add_argument("--passord", help="utan: spør (passordet blir ikkje vist)")
    b.add_argument("--rolle", choices=["maskin", "kontor", "begge"], help="maskin = tråkkemaskinene (standard), kontor = administrator")
    a = ap.parse_args(argv)

    if a.cmd == "versjon":
        return print(f"SNOWMAN Office {VERSION} (API v{API_VERSION}, krev SNOWMAN {SNOWMAN_MIN})")
    if a.cmd == "snarveg":
        ok = lag_snarveg(data_dir(a), tving=True)
        return print("Snarvegen «SNOWMAN Office» er lagd på skrivebordet." if ok else
                     "Snarvegen kunne ikkje lagast (berre Windows).")
    if a.cmd == "oppdater":
        changed, _, kart = apply()
        return sys.exit(RESTART_CODE if (changed or kart) and os.environ.get("SNOWMAN_KONTOR_TENESTE") else 0)
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
        return print(f"Brukar {u['namn']}: {kva}. Gjeld med éin gong – også om Office køyrer.")

    try:
        k = SnowmanKontor(data_dir(a), a.port, False if a.utan_kart else None).start()
    except OSError as e:
        sys.exit(f"Kunne ikkje starte SNOWMAN Office: {e}\n"
                 f"Er porten i bruk? Køyrer SNOWMAN Office alt (sjå etter eit anna vindauge, eller tenesta)?")
    print(f"SNOWMAN Office {VERSION}")
    print(f"  Data:        {k.data}")
    print(f"  Kontorsida:  http://localhost:{k.web_port}/")
    if k.kartvising:
        print(f"  Kart og anlegg (kontormodus): http://localhost:{k.anlegg_port()}/")
    print(f"  Maskinene:   http://<IP-adressa til denne PC-en>:{k.web_port} (same nett/wifi på anlegget)")
    if k.maskin_srv:
        print(f"  Ute i bakken: port {k.maskin_srv.server_address[1]} (berre maskin-API-et – den einaste porten som kan "
              "opnast i ruteren)")
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
        print("SNOWMAN Office stoppa.")


if __name__ == "__main__":
    main()
