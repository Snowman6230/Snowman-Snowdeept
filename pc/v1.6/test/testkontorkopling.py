# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Test av koplinga til SNOWMAN Kontor – anleggspakke frå kontoret (v1.6.136, v1.6.137: Kontor i staden for Base).

Køyr frå pc/v1.6:  python3 test/testkontorkopling.py   → venta «ALT OK».
Startar ein ekte SNOWMAN Kontor (kontor/v1.0) i ei mellombels mappe, lastar opp anleggspakkar som kontoret og hentar
dei med kontorkopling.py – med dei same lagra (trasear, hindringar, kontrollpunkt) som SNOWMAN brukar.
"""
import base64
import io
import json
import os
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
KONTOR_DIR = HERE.parent.parent / "kontor" / "v1.0"
import kontorkopling as BK  # noqa: E402
import kontroll as K  # noqa: E402
import trasear as TR  # noqa: E402

feil = []


def sjekk(ok, tekst):
    print(("OK   " if ok else "FEIL ") + tekst)
    if not ok:
        feil.append(tekst)


T1 = {"id": "t1", "name": "Bakke 1", "kind": "trase", "level": "bla", "target": 0.6,
      "poly": [[62.38, 6.78], [62.381, 6.78], [62.381, 6.782]]}
F1 = {"id": "f1", "name": "Vegen", "kind": "forbode", "poly": [[62.37, 6.78], [62.371, 6.78], [62.371, 6.782]]}
H1 = {"id": "o1", "type": "hydrant", "name": "Hydrant 4", "lat": 62.3805, "lng": 6.781, "radius": 0.5}
K1 = {"id": "k1", "name": "Bolt", "E": 389000.0, "N": 6918000.0, "zone": 32, "h": 702.3}


def main():
    if not KONTOR_DIR.is_dir():
        print("Fann ikkje kontor/v1.0 – hoppar over testen.")
        return
    sys.path.insert(0, str(KONTOR_DIR))
    import anleggspakke as AP
    import konfig
    import snowman_kontor as SK
    tmp = tempfile.TemporaryDirectory()
    d = Path(tmp.name)
    cfg = konfig.Config(d / "kontor")
    cfg.first_setup()
    cfg.set_user("pb600", "maskin-pw-1", roles=["maskin"])
    cfg.set_user("admin", "kontor-pw-1", roles=["kontor"])
    cfg.data["oppdatering"]["sjekk"] = False
    cfg.save()
    base = SK.SnowmanKontor(d / "kontor", 0).start()
    web = f"http://127.0.0.1:{base.web_port}"

    def last_opp(**kw):
        z = Path(AP.lag(d / "p.zip", "Fjellsætra", "admin", **kw)).read_bytes()
        rq = urllib.request.Request(web + "/api/v1/anleggspakke", data=z, method="POST")
        rq.add_header("Authorization", "Basic " + base64.b64encode(b"admin:kontor-pw-1").decode())
        return json.loads(urllib.request.urlopen(rq, timeout=10).read())["pakke"]["versjon"]

    try:
        data = d / "maskin"
        tra, obj = TR.Trasear(data / "trasear.json", data / "sessions"), TR.Objekt(data / "objekt.json")
        kon = K.Kontroll(data / "kontroll.json", None, None)
        tra.save({"name": "Lokal trasé", "poly": [[62.39, 6.7], [62.391, 6.7], [62.391, 6.702]]})
        mcfg = {"kontor_host": "127.0.0.1", "kontor_port": base.web_port, "kontor_user": "pb600",
                "kontor_pass": "maskin-pw-1", "kontor_on": True, "kontor_maskinnamn": "PB 1"}
        bk = BK.KontorKopling(data, "1.6.137")

        def apply(inn):
            for f, fn in (("trasear.json", tra.replace_all), ("objekt.json", obj.replace_from_package),
                          ("kontrollpunkt.json", kon.replace_points)):
                if f in inn:
                    fn(inn[f], dry=True)
            bk.backup([data / "trasear.json", data / "objekt.json", data / "kontroll.json"])
            g = 0
            if "trasear.json" in inn:
                tra.replace_all(inn["trasear.json"])
            if "objekt.json" in inn:
                g = obj.replace_from_package(inn["objekt.json"])
            if "kontrollpunkt.json" in inn:
                kon.replace_points(inn["kontrollpunkt.json"])
            return g

        r = bk.fetch(mcfg, apply)
        sjekk(r["ok"] and not r["ny"] and "ikkje lagt ut" in r["melding"], "ingen pakke på kontoret enno")
        sjekk(not bk.styrt(mcfg), "ikkje styrt før ei pakke er henta")
        last_opp(trasear=[T1, F1], objekt=[H1], kontrollpunkt=[K1])
        r = bk.fetch(mcfg, apply)
        sjekk(r["ny"] and r["aktiv"]["versjon"] == 1, "pakke v1 henta frå Kontor")
        sjekk([t["name"] for t in tra.listing()] == ["Bakke 1", "Vegen"], "trasear frå kontoret erstattar dei lokale")
        sjekk((data / "anleggspakke" / "forrige" / "trasear.json").exists(), "det lokale er teke vare på (forrige/)")
        sjekk([p["name"] for p in kon.data["points"]] == ["Bolt"], "kontrollpunkt frå kontoret")
        sjekk(bk.styrt(mcfg), "styrt frå kontoret etter henting")
        sjekk("Har alt nyaste" in bk.fetch(mcfg, apply)["melding"], "same pakke blir ikkje henta to gonger")

        o = obj.save({"lat": 62.38061, "lng": 6.78111, "type": "stein", "name": "Stor stein", "radius": 1, "lokal": True})
        sjekk(o.get("lokal") is True, "ny hindring blir merkt lokal")
        sjekk(bk.forslag(mcfg, {"type": "hindring", "tekst": "Ny hindring: Stor stein", "lat": o["lat"], "lon": o["lng"]}),
              "forslag sendt til kontoret")
        last_opp(trasear=[T1], objekt=[H1])
        r = bk.fetch(mcfg, apply)
        sjekk(r["aktiv"]["versjon"] == 2 and "kontrollpunkt" not in r["aktiv"]["tal"], "v2 utan kontrollpunkt-fil")
        sjekk([p["name"] for p in kon.data["points"]] == ["Bolt"], "fil som manglar i pakka = uendra i maskina")
        sjekk([x["name"] for x in obj.listing()] == ["Hydrant 4", "Stor stein"] and obj.listing()[1]["lokal"],
              "lokal hindring blir verande når kontoret ikkje har teke ho med")
        last_opp(trasear=[T1], objekt=[H1, {"id": "s9", "type": "stein", "name": "Stein (godkjent)", "lat": 62.380615,
                                            "lng": 6.781105, "radius": 1}])
        r = bk.fetch(mcfg, apply)
        sjekk("godkjende" in r["melding"] and [x["name"] for x in obj.listing()] == ["Hydrant 4", "Stein (godkjent)"],
              "lokal hindring blir fjerna når kontoret har teke ho med (same type innan 2 m)")

        try:
            bk.fetch(dict(mcfg, kontor_pass="feil"), apply)
            sjekk(False, "feil passord blir avvist")
        except BK.Feil as e:
            sjekk("avviste innlogginga" in str(e), "feil passord blir avvist")
        rq = urllib.request.Request(f"{web}/api/v1/brukarar")
        rq.add_header("Authorization", "Basic " + base64.b64encode(b"pb600:maskin-pw-1").decode())
        try:
            urllib.request.urlopen(rq, timeout=5)
            sjekk(False, "maskinbrukaren når ikkje kontordelen")
        except urllib.error.HTTPError as e:
            sjekk(e.code == 401, "maskinbrukaren når ikkje kontordelen")
        try:
            bk.fetch(dict(mcfg, kontor_port=1), apply)
            sjekk(False, "feil port gir forklaring")
        except BK.Feil as e:
            sjekk("wifi" in str(e), "feil port gir forklaring (wifi / PC-en på)")
        sjekk(BK.KontorKopling.target({"kontor_host": "http://192.168.1.20:8790/"})[:2] == ("192.168.1.20", 8790),
              "adresse med http:// og port blir forstått")
        base.stop()
        time.sleep(0.3)
        sjekk(not bk.forslag(mcfg, {"type": "merknad", "tekst": "test"}) and bk.status(mcfg)["ko"] == 1,
              "forslag blir lagt i kø når Kontor er borte")
        try:
            bk.fetch(mcfg, apply)
            sjekk(False, "feilmelding når Kontor er borte")
        except BK.Feil as e:
            sjekk("kontakt" in str(e), "feilmelding når Kontor er borte")
        sjekk([t["name"] for t in tra.listing()] == ["Bakke 1"] and bk.styrt(mcfg), "siste pakke gjeld når Kontor er borte")
        bk2 = BK.KontorKopling(data, "1.6.137")
        sjekk(bk2.aktiv["versjon"] == 3 and bk2.status(mcfg)["ko"] == 1 and bk2.mid == bk.mid,
              "aktiv pakke, kø og maskin-ID blir hugsa etter omstart")

        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("manifest.json", json.dumps({"format": BK.FORMAT, "formatversjon": 1,
                                                    "filer": {"trasear.json": "0" * 64}}))
            z.writestr("trasear.json", "{}")
        try:
            BK.les_pakke(b.getvalue())
            sjekk(False, "skadd pakke blir avvist")
        except BK.Feil:
            sjekk(True, "skadd pakke blir avvist")
    finally:
        try:
            base.stop()
        except Exception:
            pass
        tmp.cleanup()
    print("ALT OK" if not feil else f"{len(feil)} FEIL")
    sys.exit(1 if feil else 0)


if __name__ == "__main__":
    main()
