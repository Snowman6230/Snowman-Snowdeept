# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Format for anleggspakka (formatversjon 1) – VEGEN-VIDARE kap. 16, avgjerd 2026-11-20.

Anleggspakka er det kontoret sender ut til alle tråkkemaskinene. Ho brukar **dei same filformata som SNOWMAN
snødjupne alt lagrar** i `pc/v1.6/data/`, så maskina ikkje treng å omsetje noko:

    manifest.json        sjå under (påkravd)
    trasear.json         {"trasear": [...]}  same som data/trasear.json (trasear og forbodne område)
    objekt.json          {"objekt":  [...]}  same som data/objekt.json  (hindringar)
    kontrollpunkt.json   {"points":  [...]}  kontrollpunkta i data/kontroll.json (ikkje kontrollmålingane – dei
                                             høyrer til kvar maskin)
    terreng/…            terrenglag – plass i formatet, men blir ikkje sendt i første versjon (kap. 16, avgjerd 2)

Alle filene er valfrie, men pakka må ha minst éi av dei. Fil som manglar = maskina held på det ho har.

manifest.json:
    {"format": "snowman-anleggspakke", "formatversjon": 1,
     "anlegg": "Fjellsætra", "laga": "2026-11-20T09:00:00+01:00", "laga_av": "admin",
     "snowman_min": "1.7.0",                      # valfri: eldre SNOWMAN skal ikkje ta pakka i bruk
     "filer": {"trasear.json": "<sha256>", ...}}  # alle filer i pakka utanom manifest.json

Versjonsnummeret blir sett av Kontor ved opplasting (1, 2, 3 …) og står ikkje i manifestet.
Innstillingar til maskinene (innstillingar.json) kjem seinare (steg 4) og blir avviste i formatversjon 1.
"""
import hashlib
import json
import math
import zipfile

FORMAT = "snowman-anleggspakke"
FORMATVERSJON = 1
KJENDE = {"trasear.json", "objekt.json", "kontrollpunkt.json"}
TERRENG = "terreng/"
KINDS = {"trase", "forbode"}
MAKS_FILER = 2000
MAKS_JSON = 50_000_000          # ei JSON-fil i pakka (trasear med mange punkt er likevel berre nokre MB)


class Feil(ValueError):
    pass


def _num(x, namn, lo=None, hi=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise Feil(f"{namn} er ikkje eit tal")
    if not math.isfinite(v) or (lo is not None and v < lo) or (hi is not None and v > hi):
        raise Feil(f"{namn} er utanfor gyldig område")
    return v


def _id(o, fil, i):
    if not isinstance(o, dict):
        raise Feil(f"{fil}: element {i + 1} er ikkje eit objekt")
    if not str(o.get("id") or "").strip():
        raise Feil(f"{fil}: element {i + 1} manglar id")
    return str(o["id"])


def _unik(ids, fil):
    if len(ids) != len(set(ids)):
        raise Feil(f"{fil}: same id er brukt to gonger")


def sjekk_trasear(d):
    rows = d.get("trasear") if isinstance(d, dict) else None
    if not isinstance(rows, list):
        raise Feil('trasear.json må vere {"trasear": [...]}')
    ids = []
    for i, t in enumerate(rows):
        ids.append(_id(t, "trasear.json", i))
        namn = f"trasear.json: «{str(t.get('name') or t['id'])[:40]}»"
        if not str(t.get("name") or "").strip():
            raise Feil(f"{namn} manglar namn")
        if t.get("kind", "trase") not in KINDS:
            raise Feil(f"{namn}: kind må vere trase eller forbode")
        poly = t.get("poly")
        if not isinstance(poly, list) or len(poly) < 3:
            raise Feil(f"{namn}: omrisset må ha minst 3 hjørne")
        for p in poly:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                raise Feil(f"{namn}: hjørne må vere [breidd, lengd]")
            _num(p[0], f"{namn}: breiddegrad", -90, 90)
            _num(p[1], f"{namn}: lengdegrad", -180, 180)
        if t.get("target") not in (None, ""):
            _num(t["target"], f"{namn}: måldjupne", 0, 10)
    _unik(ids, "trasear.json")
    return {"trasear": sum(1 for t in rows if t.get("kind", "trase") == "trase"),
            "forbodne_omrade": sum(1 for t in rows if t.get("kind") == "forbode")}


def sjekk_objekt(d):
    rows = d.get("objekt") if isinstance(d, dict) else None
    if not isinstance(rows, list):
        raise Feil('objekt.json må vere {"objekt": [...]}')
    ids = []
    for i, o in enumerate(rows):
        ids.append(_id(o, "objekt.json", i))
        namn = f"objekt.json: «{str(o.get('name') or o['id'])[:40]}»"
        _num(o.get("lat"), f"{namn}: lat", -90, 90)
        _num(o.get("lng"), f"{namn}: lng", -180, 180)
        if o.get("radius") not in (None, ""):
            r = _num(o["radius"], f"{namn}: radius", 0, 30)
            if r <= 0:
                raise Feil(f"{namn}: radius må vere over 0")
    _unik(ids, "objekt.json")
    return {"hindringar": len(rows)}


def sjekk_kontrollpunkt(d):
    rows = d.get("points") if isinstance(d, dict) else None
    if not isinstance(rows, list):
        raise Feil('kontrollpunkt.json må vere {"points": [...]}')
    ids = []
    for i, p in enumerate(rows):
        ids.append(_id(p, "kontrollpunkt.json", i))
        namn = f"kontrollpunkt.json: «{str(p.get('name') or p['id'])[:40]}»"
        if p.get("zone") not in (32, 33, 35):
            raise Feil(f"{namn}: UTM-sone må vere 32, 33 eller 35")
        _num(p.get("E"), f"{namn}: austing", 100_000, 900_000)
        _num(p.get("N"), f"{namn}: nording", 6_000_000, 8_000_000)
        _num(p.get("h"), f"{namn}: høgd", -100, 3000)
    _unik(ids, "kontrollpunkt.json")
    return {"kontrollpunkt": len(rows)}


SJEKK = {"trasear.json": sjekk_trasear, "objekt.json": sjekk_objekt, "kontrollpunkt.json": sjekk_kontrollpunkt}


def _sha(z, info):
    h = hashlib.sha256()
    with z.open(info) as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def kontroller(path, maks_utpakka):
    """Les og kontrollerer ei anleggspakke. Returnerer innhaldet (manifest + tal) eller kastar Feil med forklaring."""
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise Feil("anleggspakka må vere ei zip-fil")
    with z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > MAKS_FILER:
            raise Feil(f"for mange filer i pakka (maks {MAKS_FILER})")
        if sum(i.file_size for i in infos) > maks_utpakka:
            raise Feil("pakka blir for stor når ho blir pakka ut")
        namn = {}
        for i in infos:
            n = i.filename
            if n.startswith(("/", "\\")) or "\\" in n or ".." in n.split("/") or ":" in n:
                raise Feil(f"ugyldig filnamn i pakka: {n[:80]}")
            if n in namn:
                raise Feil(f"fila {n} ligg to gonger i pakka")
            namn[n] = i
        if "manifest.json" not in namn:
            raise Feil("manifest.json manglar – sjå formatet i LES-MEG (Anleggspakke)")
        try:
            m = json.loads(z.read(namn["manifest.json"]).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise Feil("manifest.json er ikkje gyldig JSON")
        if not isinstance(m, dict) or m.get("format") != FORMAT:
            raise Feil(f'manifest.json: format må vere "{FORMAT}"')
        if m.get("formatversjon") != FORMATVERSJON:
            raise Feil(f"manifest.json: formatversjon {m.get('formatversjon')} er ukjend – denne Kontor kjenner "
                       f"formatversjon {FORMATVERSJON}")
        filer = m.get("filer")
        if not isinstance(filer, dict):
            raise Feil("manifest.json: «filer» manglar")
        andre = sorted(n for n in namn if n != "manifest.json")
        if not andre:
            raise Feil("pakka har ingen innhaldsfiler (trasear.json, objekt.json eller kontrollpunkt.json)")
        for n in andre:
            if n == "innstillingar.json":
                raise Feil("innstillingar.json er ikkje støtta enno (innstillingar til maskinene kjem seinare)")
            if n not in KJENDE and not n.startswith(TERRENG):
                raise Feil(f"ukjend fil i pakka: {n[:80]}")
            if n not in filer:
                raise Feil(f"{n} står ikkje i manifest.json")
        for n, h in filer.items():
            if n not in namn:
                raise Feil(f"manifest.json viser til {n}, men fila manglar i pakka")
            if _sha(z, namn[n]) != str(h).lower():
                raise Feil(f"{n}: sha256 stemmer ikkje med manifest.json (fila er endra eller skadd)")
        tal = {}
        for n in sorted(KJENDE & set(namn)):
            if namn[n].file_size > MAKS_JSON:
                raise Feil(f"{n} er for stor")
            try:
                d = json.loads(z.read(namn[n]).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise Feil(f"{n} er ikkje gyldig JSON")
            tal.update(SJEKK[n](d))
        terreng = [n for n in andre if n.startswith(TERRENG)]
        if terreng:
            tal["terrengfiler"] = len(terreng)
        return {"anlegg": str(m.get("anlegg") or "")[:80], "laga": str(m.get("laga") or "")[:40],
                "laga_av": str(m.get("laga_av") or "")[:40], "snowman_min": str(m.get("snowman_min") or "")[:20],
                "formatversjon": FORMATVERSJON, "filer": andre, "tal": tal}


def lag(path, anlegg="", laga_av="", trasear=None, objekt=None, kontrollpunkt=None, snowman_min=""):
    """Lagar ei anleggspakke (brukt av testane, og seinare av kartfana på kontoret)."""
    import time
    filer = {}
    if trasear is not None:
        filer["trasear.json"] = {"trasear": trasear}
    if objekt is not None:
        filer["objekt.json"] = {"objekt": objekt}
    if kontrollpunkt is not None:
        filer["kontrollpunkt.json"] = {"points": kontrollpunkt}
    data = {n: json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8") for n, d in filer.items()}
    m = {"format": FORMAT, "formatversjon": FORMATVERSJON, "anlegg": anlegg,
         "laga": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "laga_av": laga_av,
         "filer": {n: hashlib.sha256(b).hexdigest() for n, b in data.items()}}
    if snowman_min:
        m["snowman_min"] = snowman_min
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(m, ensure_ascii=False, indent=1))
        for n, b in data.items():
            z.writestr(n, b)
    return path
