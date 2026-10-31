# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Oppsett av mountpoints frå kontorsida: kontroll av det som blir skrive inn, og passord som ikkje skal visast.

Kontorsida får aldri passord eller hash tilbake. Kvar kjelde har ein fast id; når kontoret lagrar med tomt
passordfelt, blir det lagra passordet for same id ståande. Opplasting får nytt passord berre når ho er ny, eller
når kontoret ber om det – og passordet blir då vist éin gong.
"""
import copy
import re
import secrets

from konfig import MOUNT_DEFAULT, hash_pw, new_secret

TYPAR = ("ntrip", "seriell", "tcp", "tcp-tenar", "opplasting")   # «fil» (avspeling) berre frå kommandolinja
NAMN_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
VERT_RE = re.compile(r"^[A-Za-z0-9._:\[\]-]{1,120}$")
BAUD = (4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
MAKS_KJELDER = 6


def _txt(v, n, felt, tom_ok=True):
    s = str(v if v is not None else "").strip()
    if not s and not tom_ok:
        raise ValueError(f"{felt} manglar")
    if len(s) > n:
        raise ValueError(f"{felt} er for langt (maks {n} teikn)")
    if any(c in s for c in "\r\n\t"):
        raise ValueError(f"{felt} kan ikkje innehalde linjeskift")
    return s


def _port(v, felt, lo=1):
    try:
        p = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"{felt} må vere eit tal")
    if not lo <= p <= 65535:
        raise ValueError(f"{felt} må vere mellom {lo} og 65535")
    return p


def _tal(v, felt, lo, hi):
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{felt} må vere eit tal")
    if not lo <= x <= hi:
        raise ValueError(f"{felt} må vere mellom {lo} og {hi}")
    return x


def ny_id():
    return secrets.token_hex(4)


def sikre_id(cfg):
    """Gi alle kjelder og tillegg ein fast id (eldre oppsett frå kommandolinja manglar han). Returnerer True om endra."""
    endra = False
    for m in cfg["mountpoints"]:
        for s in m.get("kjelder", []) + m.get("tillegg", []):
            if not s.get("id"):
                s["id"] = ny_id()
                endra = True
    return endra


def offentleg(m):
    """Mountpointet slik kontorsida får det: utan passord og hash."""
    d = copy.deepcopy(m)
    for s in d.get("kjelder", []) + d.get("tillegg", []):
        har = bool(s.pop("passord", "")) or bool(s.pop("hash", ""))
        if s.get("type") in ("ntrip", "opplasting"):
            s["har_passord"] = har
    return d


def lag(inn, alle, gamalt_namn=None, reserverte_portar=()):
    """Kontrollerer eit mountpoint frå kontorsida og flettar inn lagra passord.

    inn          det kontoret sende (namn, skildring, byte_etter_s, innmalt, kjelder)
    alle         noverande mountpoints (lista i base.json)
    gamalt_namn  namnet før endring (None = nytt)
    Returnerer (mountpoint, melding) – meldinga har opplastingspassordet når det er laga nytt.
    """
    namn = _txt(inn.get("namn"), 32, "Namnet", False)
    if not NAMN_RE.match(namn):
        raise ValueError("Namnet kan berre ha bokstavane A–Z, tal, - og _ (utan mellomrom eller æøå), maks 32 teikn")
    gamal = next((m for m in alle if m.get("namn") == gamalt_namn), None) if gamalt_namn else None
    if gamalt_namn and gamal is None:
        raise ValueError(f"Fann ikkje mountpointet {gamalt_namn}")
    for m in alle:
        if m is not gamal and m.get("namn", "").lower() == namn.lower():
            raise ValueError(f"Mountpointet {m['namn']} finst alt")
    ut = copy.deepcopy(gamal) if gamal else copy.deepcopy(MOUNT_DEFAULT)
    ut["namn"] = namn
    ut["skildring"] = _txt(inn.get("skildring"), 60, "Skildringa") or namn
    ut["byte_etter_s"] = _tal(inn.get("byte_etter_s", 10) or 10, "Byte til reserve etter", 2, 120)
    ut["tilbake_etter_s"] = _tal(inn.get("tilbake_etter_s", 60) if inn.get("tilbake_etter_s") not in (None, "")
                                 else 60, "Tilbake til første kjelde etter", 0, 3600)
    im = inn.get("innmalt")
    if im and any(str(im.get(k, "")).strip() for k in ("lat", "lon", "h")):
        ut["innmalt"] = {"lat": _tal(im.get("lat"), "Breiddegrad", -90, 90),
                         "lon": _tal(im.get("lon"), "Lengdegrad", -180, 180),
                         "h": _tal(im.get("h"), "Høgd", -500, 9000)}
    else:
        ut["innmalt"] = None

    gamle = {s.get("id"): s for s in (gamal or {}).get("kjelder", []) if s.get("id")}
    andre_tenarportar = {int(s.get("port")) for m in alle if m is not gamal
                         for s in m.get("kjelder", []) if s.get("type") == "tcp-tenar" and s.get("port")}
    kjelder, namn_brukt, melding = [], set(), ""
    liste = inn.get("kjelder") or []
    if not isinstance(liste, list) or not liste:
        raise ValueError("Legg til minst éi kjelde")
    if len(liste) > MAKS_KJELDER:
        raise ValueError(f"Maks {MAKS_KJELDER} kjelder per mountpoint")
    for i, k in enumerate(liste, 1):
        if not isinstance(k, dict):
            raise ValueError("Ugyldig kjelde")
        kid = str(k.get("id") or "")
        old = gamle.get(kid)
        typ = k.get("type")
        if typ == "fil" and old and old.get("type") == "fil":
            s = copy.deepcopy(old)                  # avspeling frå kommandolinja blir ståande uendra
        elif typ not in TYPAR:
            raise ValueError(f"Kjelde {i}: ukjend type «{typ}»")
        else:
            s = {"id": kid if old and old.get("type") == typ else ny_id(), "type": typ}
            f = f"Kjelde {i}"
            if typ == "ntrip":
                vert = _txt(k.get("caster"), 120, f"{f}: casteradressa", False)
                vert = re.sub(r"^[a-z]+://", "", vert, flags=re.I).rstrip("/")
                if not VERT_RE.match(vert):
                    raise ValueError(f"{f}: casteradressa kan ikkje innehalde mellomrom eller / (berre t.d. "
                                     f"gpsbase.dyndns.org)")
                mp = _txt(k.get("mountpoint"), 64, f"{f}: mountpoint", False).lstrip("/")
                if any(c in mp for c in " /;"):
                    raise ValueError(f"{f}: mountpoint kan ikkje innehalde mellomrom, / eller ;")
                s.update({"caster": vert, "port": _port(k.get("port") or 2101, f"{f}: port"), "mountpoint": mp,
                          "brukar": _txt(k.get("brukar"), 64, f"{f}: brukarnamn"),
                          "versjon": str(k.get("versjon") or "auto") if str(k.get("versjon") or "auto")
                          in ("auto", "1", "2") else "auto"})
                pw = str(k.get("passord") or "")
                if len(pw) > 128:
                    raise ValueError(f"{f}: passordet er for langt")
                if pw:
                    s["passord"] = pw
                elif old and old.get("type") == "ntrip" and not k.get("fjern_passord"):
                    s["passord"] = old.get("passord", "")
                else:
                    s["passord"] = ""
                if old and old.get("gga") and old.get("type") == "ntrip":
                    s["gga"] = old["gga"]
                base = f"rele-{mp}"
            elif typ == "seriell":
                p = _txt(k.get("port"), 64, f"{f}: port", False)
                if not re.match(r"^(COM\d{1,3}|/dev/[A-Za-z0-9_./-]+)$", p, re.I):
                    raise ValueError(f"{f}: porten må vere t.d. COM5 (Windows) eller /dev/ttyACM0 (Linux)")
                b = int(_tal(k.get("baud") or 115200, f"{f}: baud", 1200, 921600))
                if b not in BAUD:
                    raise ValueError(f"{f}: baud må vere ein av {', '.join(map(str, BAUD))}")
                s.update({"port": p.upper() if p.upper().startswith("COM") else p, "baud": b})
                base = "mottakar"
            elif typ == "tcp":
                vert = _txt(k.get("vert"), 120, f"{f}: adressa", False)
                if not VERT_RE.match(vert):
                    raise ValueError(f"{f}: adressa kan ikkje innehalde mellomrom eller /")
                s.update({"vert": vert, "port": _port(k.get("port"), f"{f}: port")})
                base = "nett"
            elif typ == "tcp-tenar":
                p = _port(k.get("port"), f"{f}: port", 1024)
                if p in reserverte_portar:
                    raise ValueError(f"{f}: port {p} er i bruk av Base (caster eller nettside)")
                if p in andre_tenarportar:
                    raise ValueError(f"{f}: port {p} er alt i bruk av eit anna mountpoint")
                s.update({"port": p})
                base = "inn"
            else:  # opplasting
                if any(x["type"] == "opplasting" for x in kjelder):
                    raise ValueError("Berre éi opplasting per mountpoint")
                if old and old.get("type") == "opplasting" and old.get("hash") and not k.get("nytt_passord"):
                    s["hash"] = old["hash"]
                else:
                    pw = new_secret(12)
                    s["hash"] = hash_pw(pw)
                    melding = (f"Opplastingspassord for {namn}: {pw} – skriv det ned no, det blir ikkje vist att. "
                               f"Bruk det i NTRIP-serveren (t.d. str2str: -out ntrips://:{pw}@<base-adresse>:<port>/{namn}).")
                base = "opplasting"
            n, j = _txt(k.get("namn"), 32, f"{f}: namn") or base, 2
            n = re.sub(r"[^A-Za-z0-9_-]", "-", n)[:32] or base
            while n.lower() in namn_brukt:
                n, j = f"{base}-{j}", j + 1
            s["namn"] = n
        namn_brukt.add(s.get("namn", "").lower())
        kjelder.append(s)
    ut["kjelder"] = kjelder
    ut.setdefault("tillegg", [])
    return ut, melding
