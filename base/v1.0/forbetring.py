# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Forbetringsmotoren i SNOWMAN Base: finn forbetringar i oppsett, utstyr og program ut frå drifta.

To lag:
  1. Reglar (alltid på, lokalt): faste kontrollar av korreksjonane, basen, maskinene og serveren.
  2. AI (valfritt, ai.py): les eit anonymisert samandrag og foreslår meir – også forbetringar i SNOWMAN-programma.

Kvart forslag har ein fast nøkkel, så same funn blir oppdatert (ikkje dobla). Status: ny → godteke/avvist → gjort.
Forslag som kjem att etter «gjort», blir opna på nytt. Kontoret kan eksportere lista som Markdown til utviklaren.

Kategoriar:  base (SNOWMAN Base) · snowman (SNOWMAN snødjupne) · utstyr (mottakar/antenne) · drift (anlegget)
"""
import time

from konfig import SNOWMAN_MIN, VERSION

CATEGORIES = {"base": "SNOWMAN Base", "snowman": "SNOWMAN snødjupne", "utstyr": "Mottakar og antenne",
              "drift": "Drift av anlegget"}


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
    for m in base.mounts.values():
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
        for src in m.sources:
            fr = src.stats.frames
            if fr > 200 and src.framer.crc_err / fr > 0.01:
                out.append(S(f"{k}:{src.name}:crc", "utstyr", "middels", f"{k}/{src.name}: CRC-feil",
                             f"{100 * src.framer.crc_err / fr:.1f} % øydelagde rammer frå kjelda.",
                             "Sjekk kabel, baudrate og at ingen andre program les same port."))
    # maskiner (gjennom casteren og hjarteslag)
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
    for r in base.store.machines():
        if r["versjon"] and vtuple(r["versjon"]) < vtuple(SNOWMAN_MIN):
            out.append(S(f"maskin:{r['id']}:gammal", "snowman", "høg", f"{r['namn']}: SNOWMAN {r['versjon']} er for gammal",
                         f"Base krev minst SNOWMAN {SNOWMAN_MIN} for delinga og anleggspakka.",
                         "Oppdater SNOWMAN på maskina (Innst. › System › Hent siste versjon)."))
        if r["fixdel"] is not None and r["age"] is not None and r["age"] < 86400 and r["fixdel"] < 0.6:
            out.append(S(f"maskin:{r['id']}:fix", "utstyr", "middels",
                         f"{r['namn']}: berre {100 * r['fixdel']:.0f} % RTK FIX",
                         "Låg FIX-del gir hol i snødjupna. Vanlege årsaker: antenna er skjerma (vinsj, lys), "
                         "kabelen er dårleg, eller basen er langt unna.",
                         "Sjekk antenneplasseringa og kabelen. Samanlikn med andre maskiner i same bakke."))
        pk = base.store.package()
        if pk and r["pakke"] and str(r["pakke"]) != str(pk["versjon"]) and r["age"] is not None and r["age"] < 3600:
            out.append(S(f"maskin:{r['id']}:pakke", "drift", "låg", f"{r['namn']}: gammal anleggspakke",
                         f"Maskina har v{r['pakke']}, aktiv er v{pk['versjon']}.",
                         "Maskina hentar ny pakke når ho har dekning. Står det lenge, sjekk samband og nøkkel."))
    # Base sjølv
    free = base.disk_free()
    if free is not None and free < 5:
        out.append(S("disk", "base", "høg", f"Lite diskplass ({free} GB ledig)",
                     "Rådataloggen og anleggspakkane kan fylle disken.",
                     "Set ned «logg.dagar» eller «logg.maks_mb», eller flytt data/ til ein større disk."))
    up = base.updates.info
    if up.get("ny"):
        out.append(S("oppdatering", "base", "låg", f"Ny versjon av SNOWMAN Base: {up['ny']}",
                     f"Du har {VERSION}.", "Trykk «Oppdater» på statussida, eller køyr «snowman-base oppdater»."))
    if cfg["web"].get("status_open") and cfg["caster"].get("krev_innlogging") is False:
        out.append(S("open-caster", "base", "middels", "Casteren er open utan innlogging",
                     "Kven som helst som når porten, kan bruke korreksjonane.",
                     "Set «caster.krev_innlogging» til true (standard)."))
    if not base.ai.enabled():
        out.append(S("ai-av", "base", "låg", "AI-analysen er av",
                     "Reglane finn kjende problem. AI kan i tillegg sjå mønster og foreslå forbetringar i programma.",
                     "Slå på AI på kontorsida (lokal modell via Ollama, eller Claude med eigen API-nøkkel). Berre eit "
                     "anonymisert samandrag blir sendt."))
    return out


def day_summary(base):
    """Samandrag av døgnet så langt – lagra i dagstal (trendar) og brukt av AI."""
    mounts = {}
    for m in base.mounts.values():
        s = m.out.summary()
        d = m.day
        mounts[m.name] = {"oppetid": round(d["ok"] / d["tot"], 4) if d["tot"] else None, "bytte": d["bytte"],
                          "system": s["systems"], "satellittar": s["satsTotal"], "baner": s["eph"],
                          "bitrate": m.out.bitrate(), "typar": [t["type"] for t in s["types"] if t["aktiv"]],
                          "basekontroll": (m.base_check() or {}).get("avvik_m")}
    machines = []
    for r in base.store.machines():
        if r["age"] is not None and r["age"] < 86400:
            machines.append({"versjon": r["versjon"], "fixdel": r["fixdel"], "pakke": r["pakke"]})
    conns = sum(1 for h in base.caster.history if h[4] == "inn")
    return {"base": VERSION, "mountpoints": mounts, "maskiner": machines, "tilkoplingar": conns,
            "forslag_frå_maskiner": len(base.store.proposals("ny")), "disk_gb": base.disk_free()}


def run(base):
    """Køyr reglane, lagre forslaga og dagens samandrag. Returnerer forslaga."""
    found = rules(base)
    for s in found:
        base.store.upsert_improvement(s)
    base.store.save_day(time.strftime("%Y-%m-%d"), day_summary(base))
    return found


def export_markdown(store, include_done=False):
    """Forslaga som Markdown – kan givast til utviklaren (eller ein AI-assistent) som oppgåveliste."""
    rows = store.improvements(include_done)
    lines = [f"# Forbetringsforslag frå SNOWMAN Base {VERSION}",
             f"Laga {time.strftime('%Y-%m-%d %H:%M')}. Kjelde: reglar og ev. AI. Alvor: høg / middels / låg.", ""]
    for cat, title in CATEGORIES.items():
        part = [r for r in rows if r["kategori"] == cat]
        if not part:
            continue
        lines.append(f"## {title}")
        for r in part:
            lines.append(f"- **[{r['alvor']}] {r['tittel']}** ({r['kjelde']}, status: {r['status']}, sett {r['tal']} gonger)")
            lines.append(f"  - Kvifor: {r['grunn']}")
            lines.append(f"  - Tiltak: {r['tiltak']}")
            if r.get("merknad"):
                lines.append(f"  - Merknad: {r['merknad']}")
        lines.append("")
    props = [p for p in store.proposals() if p["type"] == "program" and p["status"] in ("ny", "godkjent")]
    if props:
        lines.append("## Ønske frå førarane (SNOWMAN snødjupne)")
        for p in props:
            lines.append(f"- {p['tekst']} (maskin {p['maskin']}, {time.strftime('%Y-%m-%d', time.localtime(p['dato']))})")
        lines.append("")
    return "\n".join(lines)
