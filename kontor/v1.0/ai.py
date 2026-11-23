# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""AI i SNOWMAN Office – valfri, berre Claude (Anthropic). Avgjerd 2026-11-23: lokal AI (Ollama) er fjerna fordi
mange PC-ar på anlegga er eldre, og andre leverandørar er fjerna for å halde SNOWMAN enkel.

Innstillinga «ai.leverandor» i data/kontor.json (eller Office › AI):
    av          ingen AI (standard). Reglane i forbetring.py er alltid på, og AI-råda i maskina (reknereglar i
                SNOWMAN Snowdeep) er alltid lokale og blir ikkje rørte av dette.
    anthropic   Claude via API – krev eigen API-nøkkel (lagra berre i data/kontor.json på kontor-PC-en).

Bruk: forbetringsanalyse (éin gong i døgnet), spørsmål frå kontoret, og «Spør SNOWMAN AI» frå maskinene
(POST /api/v1/ai/maskin – maskinene har ingen nøkkel, dei spør Office). Éitt spørsmål om gongen.
Månadstak: «ai.maks_per_manad» kall (standard 500) – så ein feil ikkje kan gi ei stor rekning.

Personvern: AI får berre eit ANONYMISERT samandrag – ingen namn, ingen IP-adresser, ingen posisjonar, ingen nøklar.
Kontorsida kan vise nøyaktig kva som blir sendt (forehandsvising) før AI blir slått på.
AI les og foreslår – han styrer aldri Office, Base, mottakaren eller maskinene.
"""
import json
import threading
import time
import urllib.error
import urllib.request

from forbetring import day_summary, CATEGORIES
from konfig import VERSION, SNOWMAN_MIN
import nett

SYSTEM = """Du er forbetringsassistenten i SNOWMAN Office (Alpindata), anleggsserveren for eit skianlegg som brukar
SNOWMAN Snowdeep: tråkkemaskiner måler snødjupne med RTK-GNSS (RTK rekna i SNOWMAN med RTKLIB) mot ein
terrengmodell. SNOWMAN Base (eigen Raspberry Pi) er RTK-base og NTRIP-caster og har berre med korreksjonane å gjere.
SNOWMAN Office (PC på anlegget) sender ut anleggspakka frå kontoret, tek imot forslag og deler målingar.

Svar alltid på nynorsk. Ver konkret og nøktern. Ikkje gjenta forslag som alt står i lista frå reglane.
Foreslå forbetringar i fem kategoriar: base (SNOWMAN Base), kontor (SNOWMAN Office), snowman (SNOWMAN Snowdeep),
utstyr (mottakar/antenne) og drift (anlegget). Forbetringar i programma skal vere så konkrete at ein utviklar kan
lage dei. Grunngje kvart forslag med tal frå samandraget. Finn ikkje på data som ikkje står der."""

ASK_JSON = """Gi svaret som JSON: {"forslag": [{"kategori": "base|kontor|snowman|utstyr|drift", "alvor": "høg|middels|låg",
"tittel": "...", "grunn": "...", "tiltak": "..."}]}. Maks 8 forslag. Berre JSON, ingen anna tekst."""


DRIVER = """Du er SNOWMAN AI i førarhuset på ei tråkkemaskin (SNOWMAN Snowdeep, Alpindata). Føraren spør medan han
arbeider. Svar på nynorsk, kort og konkret: 1–4 setningar, utan overskrifter og lister med mindre føraren ber om det.
Bygg på samandraget av skjermen (snødjupne, mål, GNSS, trasear, AI-råda frå reknereglane i maskina og vêret).
Finn ikkje på tal som ikkje står der – sei heller at du ikkje veit. Alt er råd: føraren avgjer. Gi aldri råd som går
ut over tryggleiken (bratt terreng, vinsj, folk i bakken, skred) – vis då til rutinane på anlegget."""


MODELL = "claude-haiku-5-5"     # rask og billeg – nok til korte svar og den daglege analysen
MAKS_PER_MANAD = 500            # kall i månaden før AI stoppar av seg sjølv (kan endrast i data/kontor.json)


class AI:
    def __init__(self, cfg, store, events):
        self.cfg = cfg
        self.store = store
        self.events = events
        self.last = None               # {"t", "ok", "tal", "feil"}
        self.lock = threading.Lock()   # éitt spørsmål om gongen frå maskinene
        self._fix_gamal_leverandor()

    def _fix_gamal_leverandor(self):
        """Før 1.4.0 kunne leverandøren vere «ollama» (lokal AI). Han er fjerna – AI blir slått av, med melding."""
        if self.cfg["ai"].get("leverandor") not in ("av", "anthropic"):
            gamal = self.cfg["ai"].get("leverandor")
            self.cfg.update(lambda d: d["ai"].update(leverandor="av"))
            self.events.add(f"AI: «{gamal}» (lokal AI) er fjerna frå SNOWMAN Office. AI er slått av – vel Claude under "
                            "Office › AI om du vil bruke AI.", "info")

    def bruk(self):
        """Kall denne månaden og taket."""
        m = time.strftime("%Y-%m")
        b = self.cfg["ai"].get("bruk") or {}
        return {"manad": m, "kall": int(b.get("kall", 0)) if b.get("manad") == m else 0,
                "maks": int(self.cfg["ai"].get("maks_per_manad") or MAKS_PER_MANAD)}

    def _tel(self):
        b = self.bruk()
        if b["kall"] >= b["maks"]:
            raise RuntimeError(f"Månadstaket for AI er nådd ({b['maks']} kall i {b['manad']}). AI er på pause til neste "
                               "månad – eller auk «maks_per_manad» under ai i data/kontor.json.")
        self.cfg.update(lambda d: d["ai"].update(bruk={"manad": b["manad"], "kall": b["kall"] + 1}))

    def test(self):
        """Prøv nøkkelen med eit lite kall. Returnerer svaret."""
        return self._ask("Svar med eitt ord.", "Svar «OK» på nynorsk.").strip()[:80]

    def enabled(self):
        return self.cfg["ai"].get("leverandor", "av") == "anthropic"

    # ---------- kva som blir sendt ----------
    def context(self, base):
        """Anonymisert samandrag: tal og typar – ingen namn, IP, posisjonar eller nøklar."""
        days = self.store.days(14)
        names = ([m["namn"] for m in self.store.machines() if m.get("namn")] + [m["id"] for m in self.store.machines()]
                 + [u.get("namn", "") for u in self.cfg["brukarar"]])          # også brukarnamn (maskin/kontor)
        rules = [{"kategori": r["kategori"], "alvor": r["alvor"], "tittel": _anon(r["tittel"], names), "status": r["status"],
                  "tal": r["tal"]} for r in self.store.improvements(include_done=True)[:40]]
        wishes = [p["tekst"][:300] for p in self.store.proposals() if p["type"] == "program"][:20]
        return {"kontor_versjon": VERSION, "snowman_min": SNOWMAN_MIN, "i_dag": _anon_day(day_summary(base)),
                "siste_dagar": [_anon_day(d) for d in days[1:]], "forslag_frå_reglane": rules,
                "ønske_frå_førarane": wishes}

    def preview(self, base):
        return {"leverandor": self.cfg["ai"].get("leverandor", "av"), "system": SYSTEM,
                "melding": json.dumps(self.context(base), ensure_ascii=False, indent=1) + "\n\n" + ASK_JSON}

    # ---------- køyring ----------
    def analyse(self, base):
        """Be AI om forbetringsforslag og lagre dei (kjelde «ai»). Returnerer forslaga."""
        if not self.enabled():
            raise RuntimeError("AI er av. Vel Claude under Office › AI.")
        msg = json.dumps(self.context(base), ensure_ascii=False) + "\n\n" + ASK_JSON
        try:
            text = self._ask(SYSTEM, msg)
            items = _parse(text)
            for i, s in enumerate(items):
                s["nokkel"] = "ai:" + _key(s["tittel"])
                s["kjelde"] = "ai"
                self.store.upsert_improvement(s)
            self.last = {"t": time.time(), "ok": True, "tal": len(items), "feil": ""}
            self.events.add(f"AI-analyse: {len(items)} forslag", "info")
            return items
        except Exception as e:
            self.last = {"t": time.time(), "ok": False, "tal": 0, "feil": str(e)[:300]}
            self.events.add(f"AI-analyse feila: {e}", "feil")
            raise

    def ask(self, base, question):
        """«Spør SNOWMAN Office»: fritt spørsmål med samandraget som bakgrunn."""
        if not self.enabled():
            raise RuntimeError("AI er av. Vel Claude under Office › AI.")
        msg = ("Samandrag av drifta (anonymisert):\n" + json.dumps(self.context(base), ensure_ascii=False)
               + "\n\nSpørsmål frå driftsleiaren: " + str(question)[:2000])
        return self._ask(SYSTEM, msg)

    # ---------- SNOWMAN AI for maskinene ----------
    def driver(self, maskin, tekst, kontekst=None):
        """Spørsmål frå føraren (SNOWMAN Snowdeep). Returnerer svaret."""
        if not self.enabled():
            raise RuntimeError("AI er ikkje slått på i SNOWMAN Office (Office › AI).")
        tekst = str(tekst or "").strip()[:1000]
        if not tekst:
            raise ValueError("Spørsmålet er tomt")
        ktx = json.dumps(kontekst or {}, ensure_ascii=False)[:8000]
        if not self.lock.acquire(timeout=90):
            raise RuntimeError("SNOWMAN AI svarar ei anna maskin – prøv igjen om litt.")
        try:
            t0 = time.time()
            svar = self._ask(DRIVER, "Samandrag av skjermen i maskina:\n" + ktx + "\n\nFøraren spør: " + tekst)
            self.events.add(f"SNOWMAN AI svara {maskin} ({time.time() - t0:.0f} s)", "info")
            return svar.strip()
        finally:
            self.lock.release()

    def _ask(self, system, msg):
        c = self.cfg["ai"]
        if c.get("leverandor") != "anthropic":
            raise RuntimeError("AI er av. Vel Claude under Office › AI.")
        if not c.get("api_nokkel"):
            raise RuntimeError("API-nøkkel manglar (Office › AI).")
        self._tel()
        body = {"model": c.get("modell") or MODELL, "max_tokens": 2000, "system": system,
                "messages": [{"role": "user", "content": msg}]}
        try:
            r = _post("https://api.anthropic.com/v1/messages", body,
                      {"x-api-key": c["api_nokkel"], "anthropic-version": "2023-06-01"}, 120)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError("Claude godtok ikkje API-nøkkelen. Sjekk nøkkelen på console.anthropic.com og lim han "
                                   "inn på nytt under Office › AI.") from None
            if e.code == 429:
                raise RuntimeError("Claude har for mykje å gjere akkurat no, eller kontoen har nådd grensa si. Prøv igjen "
                                   "om litt.") from None
            if e.code == 400 and b"credit" in (e.read(4000) or b"").lower():
                raise RuntimeError("Kontoen hos Anthropic er tom. Fyll på under Billing på console.anthropic.com.") from None
            raise RuntimeError(f"Claude svarte med feil {e.code}.") from None
        except OSError as e:
            raise RuntimeError("Får ikkje kontakt med Claude – har kontor-PC-en internett? (" + nett.forklar(e) + ")") from None
        return "".join(b.get("text", "") for b in r.get("content", []))


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"content-type": "application/json", "user-agent": f"SNOWMAN Office/{VERSION}",
                                          **headers})
    with nett.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _parse(text):
    """Hent forslaga ut av svaret (JSON, gjerne med tekst rundt)."""
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        raise ValueError("AI svarte ikkje med JSON")
    data = json.loads(text[a:b + 1])
    out = []
    for s in data.get("forslag", [])[:8]:
        cat = s.get("kategori") if s.get("kategori") in CATEGORIES else "kontor"
        lvl = s.get("alvor") if s.get("alvor") in ("høg", "middels", "låg") else "låg"
        title = str(s.get("tittel") or "").strip()[:150]
        if title:
            out.append({"kategori": cat, "alvor": lvl, "tittel": title, "grunn": str(s.get("grunn") or "")[:800],
                        "tiltak": str(s.get("tiltak") or "")[:800]})
    return out


def _key(title):
    return "".join(c for c in title.lower() if c.isalnum())[:60]


def _anon(text, names=()):
    """Fjern maskinnamn, brukarnamn og IP-adresser frå titlar."""
    import re
    text = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "[ip]", str(text))
    for n in sorted(set(names), key=len, reverse=True):
        if n and len(n) > 1:
            text = text.replace(n, "[maskin]")
    return re.sub(r"^Maskin \S+", "Maskin [x]", text)


def _anon_day(d):
    d = dict(d)
    d.pop("disk_gb", None)
    return d
