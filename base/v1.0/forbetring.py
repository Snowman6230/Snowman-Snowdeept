# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Åtvaringar i SNOWMAN Base: faste reglar om korreksjonane, basemottakaren og Base sjølv.

Base 1.4 (avgjerd 2026-11-22): Base har berre med satellittar og NTRIP å gjere. Reglane blir rekna på nytt kvar gong
statusen blir henta, og blir viste på statussida (ingen database, ingen AI). SNOWMAN Office les statusen og tek
åtvaringane med i forbetringslista si – der kan dei godtakast, avvisast og eksporterast.

Kvart funn har ein fast nøkkel (same funn får same nøkkel kvar gong).
Kategoriar:  base (SNOWMAN Base) · utstyr (mottakar/antenne) · drift (anlegget)
"""
import time

from konfig import VERSION

CATEGORIES = {"base": "SNOWMAN Base", "utstyr": "Mottakar og antenne", "drift": "Drift av anlegget"}


def S(key, cat, level, title, why, what):
    return {"nokkel": key, "kategori": cat, "alvor": level, "tittel": title, "grunn": why, "tiltak": what,
            "kjelde": "regel"}


def vtuple(v):
    out = []
    for p in str(v or "0").split("."):
        try:
            out.append(int("".join(c for c in p if c.isdigit()) or 0))
        except ValueError:
            out.append(0)
    return tuple(out + [0] * (3 - len(out)))


def rules(base):
    """Alle reglane. base = SnowmanBase (snowman_base.py). Returnerer liste med forslag."""
    out = []
    cfg = base.cfg
    now = time.time()
    if not base.mounts:
        out.append(S("ingen-mountpoint", "base", "høg", "Ingen mountpoint er sett opp",
                     "Base har ingen korreksjonsstraum å sende til maskinene.",
                     "Legg til eit mountpoint med kjelde (mottakar på USB, opplasting frå Pi, eller relé frå TH/CPOS). "
                     "Sjå LES-MEG.md, «Kom i gang»."))
    for m in list(base.mounts.values()):
        s = m.out.summary()
        k = m.name
        if not any(x.kind != "ntrip" for x in m.sources):
            out.append(S(f"{k}:berre-rele", "drift", "middels", f"{k}: berre relé frå ein annan caster",
                         "Straumen kjem frå ein lånt eller betalt base. Eigen base gir uavhengigheit og fleire "
                         "satellittsystem.", "Set opp eigen base (sjå claude/lokal-base.md) og legg reléet som reserve."))
        if len(m.sources) == 1 and m.sources[0].kind != "ntrip":
            out.append(S(f"{k}:ingen-reserve", "drift", "låg", f"{k}: ingen reserve",
                         "Fell eigen base ut (straum, nett, mottakar), får maskinene ingen korreksjonar.",
                         "Legg til ei reservekjelde (relé frå TH eller CPOS) etter eigen base i «kjelder»."))
        if s["msm3"]:
            out.append(S(f"{k}:msm3", "utstyr", "høg", f"{k}: basen sender MSM3",
                         "RTKLIB i SNOWMAN les ikkje MSM3 (1073/1083 …), så maskinene får ikkje RTK.",
                         "Set basemottakaren til MSM4 eller MSM7 (eller eldre 1004/1012)."))
        if s["systems"] and set(s["systems"]) <= {"GPS", "GLONASS"}:
            out.append(S(f"{k}:berre-gps-glo", "utstyr", "middels", f"{k}: berre GPS og GLONASS",
                         "Med Galileo og BeiDou i tillegg får maskinene om lag dobbelt så mange satellittar – "
                         "raskare og meir stabil FIX, særleg med skjerma sikt.",
                         "Set basen til å sende MSM for alle fire systema (t.d. 1074/1084/1094/1124 eller MSM7)."))
        if s["age"] is not None and s["systems"] and not s["eph"] and not m.extras:
            out.append(S(f"{k}:ingen-baner", "base", "middels", f"{k}: ingen satellittbaner i straumen",
                         "RTK-motoren i SNOWMAN treng baner. Utan dei i straumen må kvar maskin hente dei frå "
                         "mottakaren eller nettet (BRDC), og FIX kan ta lengre tid etter oppstart.",
                         "Slå på 1019/1020/1042/1046 i basemottakaren (UM980 kan), eller legg til eit tillegg med "
                         "baner frå ein annan caster."))
        if "base" in s and not m.cfg.get("innmalt") and not m.cfg.get("test"):
            out.append(S(f"{k}:ikkje-innmalt", "drift", "høg", f"{k}: basen er ikkje kontrollert mot innmålt punkt",
                         "Ein feil i baseposisjonen flyttar alle snødjupnene like mykje. Base kan kontrollere "
                         "1005/1006 mot innmålt koordinat.",
                         "Mål inn basepunktet (EUREF89, ellipsoidisk høgd for ARP) og legg det inn under «innmalt»."))
        bc = m.base_check()
        if bc and bc["vurdering"] != "OK":
            out.append(S(f"{k}:baseavvik", "drift", "høg", f"{k}: baseposisjonen avvik {bc['avvik_m']} m",
                         bc["vurdering"], "Sjekk koordinaten i basemottakaren mot innmålinga. Er antenna flytt?"))
        if s["age"] is not None and s["age"] > 60:
            out.append(S(f"{k}:stille", "drift", "høg", f"{k}: ingen korreksjonar på {s['age']:.0f} s",
                         "Maskinene manglar korreksjonar og får ikkje FIX.",
                         "Sjekk straum og kabel til basemottakaren, og hendingane på statussida."))
        if m.out.bitrate() > 6000:
            out.append(S(f"{k}:bitrate", "base", "låg", f"{k}: høg datamengd ({m.out.bitrate() // 1000} kbit/s)",
                         "Kvar maskin brukar då om lag " + f"{m.out.bitrate() * 3600 / 8e6:.0f} MB mobildata i timen.",
                         "Bruk MSM4 i staden for MSM7, eller send antenne- og mottakarmeldingar sjeldnare."))
        if m.active is not None and m.sources and m.active is not m.sources[0]:
            out.append(S(f"{k}:reserve-aktiv", "drift", "middels", f"{k}: reserve i bruk ({m.active.name})",
                         f"{m.sources[0].name} sender ikkje. Maskinene får korreksjonar frå ein annan base, ofte lenger "
                         "unna og med færre satellittsystem.",
                         f"Sjekk {m.sources[0].name}: straum, kabel, nett og hendingane på statussida."))
        d = m.day
        if d["bytte"] >= 4:
            out.append(S(f"{k}:mange-bytte", "drift", "middels", f"{k}: {d['bytte']} byte av kjelde i dag",
                         "Hyppig byte mellom eigen base og reserve gir FLOAT på maskinene kvar gong.",
                         "Sjekk straum, nett og kabel til eigen base (hendingane viser tidspunkta)."))
        if d["tot"] > 3600 and d["ok"] / d["tot"] < 0.98:
            out.append(S(f"{k}:oppetid", "drift", "middels", f"{k}: oppetid {100 * d['ok'] / d['tot']:.1f} % i dag",
                         "Korreksjonane har vore borte i periodar.", "Sjå hendingane for når og kvifor."))
        for st, names in m.station_conflict().items():
            out.append(S(f"{k}:stasjon-{st}", "utstyr", "middels", f"{k}: same stasjons-ID ({st}) på {', '.join(names)}",
                         "Når to basar har same stasjons-ID, ser ikkje RTKLIB i SNOWMAN at basen er bytt.",
                         "Gi eigen base ein eigen stasjons-ID i mottakaren (ikkje 0, og ikkje same som reserven)."))
        for src in m.sources:
            fr = src.stats.frames
            if fr > 200 and src.framer.crc_err / fr > 0.01:
                out.append(S(f"{k}:{src.name}:crc", "utstyr", "middels", f"{k}/{src.name}: CRC-feil",
                             f"{100 * src.framer.crc_err / fr:.1f} % øydelagde rammer frå kjelda.",
                             "Sjekk kabel, baudrate og at ingen andre program les same port."))
    # maskiner (gjennom casteren)
    seen = {}
    for t, user, ip, mp, kind, _ in base.caster.history:
        if kind == "inn":
            seen[(user, ip)] = seen.get((user, ip), 0) + 1
    for (user, ip), n in seen.items():
        if n > 30:
            out.append(S(f"samband:{user}:{ip}", "drift", "middels", f"Maskin {user} ({ip}) kopla til {n} gonger i dag",
                         "Mange nye tilkoplingar tyder på ustabilt mobilnett eller at maskina mistar straum.",
                         "Sjekk dekning der maskina køyrer. SNOWMAN held fram med siste korreksjonar ei stund, "
                         "men FIX kan gå tapt."))
    # Base sjølv
    free = base.disk_free()
    if free is not None and free < 5:
        out.append(S("disk", "base", "høg", f"Lite diskplass ({free} GB ledig)",
                     "Rådataloggen kan fylle disken.",
                     "Set ned «logg.dagar» eller «logg.maks_mb», eller flytt data/ til ein større disk."))
    up = base.updates.info
    if up.get("ny"):
        out.append(S("oppdatering", "base", "låg", f"Ny versjon av SNOWMAN Base: {up['ny']}",
                     f"Du har {VERSION}.", "Oppdater når ingen preparerer (oppsettsida › System), eller køyr "
                     "«snowman-base oppdater». Maskinene mistar korreksjonane nokre sekund medan Base startar på nytt."))
    if cfg["web"].get("status_open") and cfg["caster"].get("krev_innlogging") is False:
        out.append(S("open-caster", "base", "middels", "Casteren er open utan innlogging",
                     "Kven som helst som når porten, kan bruke korreksjonane.",
                     "Set «caster.krev_innlogging» til true (standard)."))
    return out
