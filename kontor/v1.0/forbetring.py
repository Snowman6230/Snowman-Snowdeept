# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""Forbetringsmotoren i SNOWMAN Office: finn forbetringar i oppsett, utstyr og program ut frå drifta.

To lag:
  1. Reglar (alltid på, lokalt): maskinene, anleggspakka og Office sjølv – og åtvaringane frå SNOWMAN Base om
     korreksjonane (henta frå statussida til Base, berre lesing).
  2. AI (valfritt, ai.py): les eit anonymisert samandrag og foreslår meir – også forbetringar i SNOWMAN-programma.

Kvart forslag har ein fast nøkkel, så same funn blir oppdatert (ikkje dobla). Status: ny → godteke/avvist → gjort.
Forslag som kjem att etter «gjort», blir opna på nytt. Kontoret kan eksportere lista som Markdown til utviklaren.

Kategoriar:  base (SNOWMAN Base) · kontor (SNOWMAN Office) · snowman (SNOWMAN Snowdeep) · utstyr · drift
"""
import time

from konfig import SNOWMAN_MIN, VERSION

CATEGORIES = {"base": "SNOWMAN Base", "kontor": "SNOWMAN Office", "snowman": "SNOWMAN Snowdeep",
              "utstyr": "Mottakar og antenne", "drift": "Drift av anlegget"}


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


def rules(k):
    """Alle reglane. k = SnowmanKontor (snowman_kontor.py). Returnerer liste med forslag."""
    out = []
    now = time.time()
    # SNOWMAN Base (korreksjonane) – åtvaringane Base sjølv finn, henta frå statussida
    bs = k.basestatus.last
    if not k.basestatus.configured():
        out.append(S("base-ukjend", "kontor", "låg", "Office ser ikkje statusen til SNOWMAN Base",
                     "Med adressa til Base kan Office vise korreksjonsstraumane og ta med åtvaringane frå Base her.",
                     "Skriv adressa til Base under System › SNOWMAN Base (t.d. http://snowman-base.local:8780)."))
    elif bs.get("ok") is False and bs.get("t") and now - bs["t"] < 600:
        out.append(S("base-borte", "drift", "høg", "Office får ikkje kontakt med SNOWMAN Base",
                     bs.get("feil") or "Ingen svar.",
                     "Sjekk straum og nett til Pi-en ved antenna. Korreksjonane til maskinene kan vere borte."))
    for f in ((bs.get("status") or {}).get("forslag") or []) if bs.get("ok") else []:
        if isinstance(f, dict) and f.get("nokkel") and f.get("tittel"):
            out.append({"nokkel": "base:" + str(f["nokkel"])[:80], "kategori": f.get("kategori") if f.get("kategori")
                        in CATEGORIES else "base", "alvor": f.get("alvor") if f.get("alvor") in ("høg", "middels", "låg")
                        else "låg", "tittel": str(f["tittel"])[:150], "grunn": str(f.get("grunn") or "")[:800],
                        "tiltak": str(f.get("tiltak") or "")[:800], "kjelde": "Base"})
    # maskinene (hjarteslag)
    pk = k.store.package()
    for r in k.store.machines():
        if r["versjon"] and vtuple(r["versjon"]) < vtuple(SNOWMAN_MIN):
            out.append(S(f"maskin:{r['id']}:gammal", "snowman", "høg", f"{r['namn']}: SNOWMAN {r['versjon']} er for gammal",
                         f"Office krev minst SNOWMAN {SNOWMAN_MIN} for anleggspakka.",
                         "Oppdater SNOWMAN på maskina (Innst. › System › Hent siste versjon)."))
        if r["fixdel"] is not None and r["age"] is not None and r["age"] < 86400 and r["fixdel"] < 0.6:
            out.append(S(f"maskin:{r['id']}:fix", "utstyr", "middels",
                         f"{r['namn']}: berre {100 * r['fixdel']:.0f} % RTK FIX",
                         "Låg FIX-del gir hol i snødjupna. Vanlege årsaker: antenna er skjerma (vinsj, lys), "
                         "kabelen er dårleg, eller basen er langt unna.",
                         "Sjekk antenneplasseringa og kabelen. Samanlikn med andre maskiner i same bakke."))
        if pk and r["pakke"] and str(r["pakke"]) != str(pk["versjon"]) and r["age"] is not None and r["age"] > 86400:
            out.append(S(f"maskin:{r['id']}:pakke", "drift", "låg", f"{r['namn']}: gammal anleggspakke",
                         f"Maskina har v{r['pakke']}, aktiv er v{pk['versjon']}, og ho har ikkje meldt seg på eit døgn.",
                         "Maskina hentar ny pakke når ho er på wifi på anlegget (HENT FRÅ OFFICE). Sjekk wifi i garasjen."))
    # Office sjølv
    free = k.disk_free()
    if free is not None and free < 5:
        out.append(S("disk", "kontor", "høg", f"Lite diskplass ({free} GB ledig)",
                     "Anleggspakkane og databasen kan fylle disken.", "Rydd på PC-en, eller flytt data/ til ein større disk."))
    up = k.updates.info
    if up.get("tilgjengeleg"):
        import oppdatering
        out.append(S("oppdatering", "kontor", "låg", f"Ny versjon tilgjengeleg: {oppdatering.tekst(up)}",
                     f"Du har Office {VERSION} og kart {up.get('kart') or '–'}.", "Trykk «Oppdater no» øvst på kontorsida."))
    if not k.ai.enabled():
        out.append(S("ai-av", "kontor", "låg", "AI-analysen er av",
                     "Reglane finn kjende problem. AI kan i tillegg sjå mønster og foreslå forbetringar i programma.",
                     "Slå på AI på kontorsida (lokal modell via Ollama, eller Claude med eigen API-nøkkel). Berre eit "
                     "anonymisert samandrag blir sendt."))
    return out


def day_summary(k):
    """Samandrag av døgnet så langt – lagra i dagstal (trendar) og brukt av AI."""
    mounts = {}
    s = k.basestatus.last.get("status") if k.basestatus.last.get("ok") else None
    for m in (s or {}).get("mountpoints") or []:
        d, sm = m.get("dag") or {}, m
        mounts[str(m.get("namn"))] = {"oppetid": round(d["ok"] / d["tot"], 4) if d.get("tot") else None,
                                      "bytte": d.get("bytte"), "system": sm.get("systems"),
                                      "satellittar": sm.get("satsTotal"), "baner": sm.get("eph")}
    machines = []
    for r in k.store.machines():
        if r["age"] is not None and r["age"] < 86400:
            machines.append({"versjon": r["versjon"], "fixdel": r["fixdel"], "pakke": r["pakke"]})
    return {"kontor": VERSION, "base": (s or {}).get("versjon"), "mountpoints": mounts, "maskiner": machines,
            "tilkoplingar": (s or {}).get("tilkoplingar_i_dag"),
            "forslag_frå_maskiner": len(k.store.proposals("ny")), "disk_gb": k.disk_free()}


def run(k):
    """Køyr reglane, lagre forslaga og dagens samandrag. Returnerer forslaga."""
    found = rules(k)
    for s in found:
        k.store.upsert_improvement(s)
    keys = {s["nokkel"] for s in found}
    for r in k.store.improvements():           # løyst av seg sjølv: regelen slår ikkje til lenger
        if r["kjelde"] in ("regel", "Base") and r["status"] == "ny" and r["nokkel"] not in keys:
            k.store.set_improvement(r["nokkel"], "gjort", "Løyst – regelen slår ikkje til lenger")
    k.store.save_day(time.strftime("%Y-%m-%d"), day_summary(k))
    return found


def export_markdown(store, include_done=False):
    """Forslaga som Markdown – kan givast til utviklaren (eller ein AI-assistent) som oppgåveliste."""
    rows = store.improvements(include_done)
    lines = [f"# Forbetringsforslag frå SNOWMAN Office {VERSION}",
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
        lines.append("## Ønske frå førarane (SNOWMAN Snowdeep)")
        for p in props:
            lines.append(f"- {p['tekst']} (maskin {p['maskin']}, {time.strftime('%Y-%m-%d', time.localtime(p['dato']))})")
        lines.append("")
    return "\n".join(lines)
