# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""AI i SNOWMAN Base – utskiftbar modul (same prinsipp som VEGEN-VIDARE kap. 14).

Leverandørar (innstillinga «ai.leverandor» i data/base.json, eller kontorsida):
    av          ingen AI (standard). Reglane i forbetring.py er alltid på.
    ollama      lokal språkmodell (Ollama på same maskin eller NAS) – ingenting forlèt anlegget
    anthropic   Claude via API – krev eigen API-nøkkel (lagra berre i data/base.json)

Personvern: AI får berre eit ANONYMISERT samandrag – ingen namn, ingen IP-adresser, ingen posisjonar, ingen nøklar.
Kontorsida kan vise nøyaktig kva som blir sendt (forehandsvising) før AI blir slått på.
AI les og foreslår – han styrer aldri Base, mottakaren eller maskinene.
"""
import json
import time
import urllib.request

from forbetring import day_summary, CATEGORIES
from konfig import VERSION, SNOWMAN_MIN
import nett

SYSTEM = """Du er forbetringsassistenten i SNOWMAN Base (Alpindata), serveren for eit skianlegg som brukar SNOWMAN
snødjupne: tråkkemaskiner måler snødjupne med RTK-GNSS (RTK rekna i SNOWMAN med RTKLIB) mot ein terrengmodell.
Base er RTK-base og NTRIP-caster, deler målingar mellom maskinene og sender ut anleggspakka frå kontoret.

Svar alltid på nynorsk. Ver konkret og nøktern. Ikkje gjenta forslag som alt står i lista frå reglane.
Foreslå forbetringar i fire kategoriar: base (programmet SNOWMAN Base), snowman (programmet SNOWMAN snødjupne),
utstyr (mottakar/antenne) og drift (anlegget). Forbetringar i programma skal vere så konkrete at ein utviklar kan
lage dei. Grunngje kvart forslag med tal frå samandraget. Finn ikkje på data som ikkje står der."""

ASK_JSON = """Gi svaret som JSON: {"forslag": [{"kategori": "base|snowman|utstyr|drift", "alvor": "høg|middels|låg",
"tittel": "...", "grunn": "...", "tiltak": "..."}]}. Maks 8 forslag. Berre JSON, ingen anna tekst."""


class AI:
    def __init__(self, cfg, store, events):
        self.cfg = cfg
        self.store = store
        self.events = events
        self.last = None               # {"t", "ok", "tal", "feil"}

    def enabled(self):
        return self.cfg["ai"].get("leverandor", "av") in ("ollama", "anthropic")

    # ---------- kva som blir sendt ----------
    def context(self, base):
        """Anonymisert samandrag: tal og typar – ingen namn, IP, posisjonar eller nøklar."""
        days = self.store.days(14)
        names = [m["namn"] for m in self.store.machines() if m.get("namn")] + [m["id"] for m in self.store.machines()]
        rules = [{"kategori": r["kategori"], "alvor": r["alvor"], "tittel": _anon(r["tittel"], names), "status": r["status"],
                  "tal": r["tal"]} for r in self.store.improvements(include_done=True)[:40]]
        wishes = [p["tekst"][:300] for p in self.store.proposals() if p["type"] == "program"][:20]
        return {"base_versjon": VERSION, "snowman_min": SNOWMAN_MIN, "i_dag": _anon_day(day_summary(base)),
                "siste_dagar": [_anon_day(d) for d in days[1:]], "forslag_frå_reglane": rules,
                "ønske_frå_førarane": wishes}

    def preview(self, base):
        return {"leverandor": self.cfg["ai"].get("leverandor", "av"), "system": SYSTEM,
                "melding": json.dumps(self.context(base), ensure_ascii=False, indent=1) + "\n\n" + ASK_JSON}

    # ---------- køyring ----------
    def analyse(self, base):
        """Be AI om forbetringsforslag og lagre dei (kjelde «ai»). Returnerer forslaga."""
        if not self.enabled():
            raise RuntimeError("AI er av. Vel leverandør på kontorsida.")
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
        """«Spør SNOWMAN Base»: fritt spørsmål med samandraget som bakgrunn."""
        if not self.enabled():
            raise RuntimeError("AI er av. Vel leverandør på kontorsida.")
        msg = ("Samandrag av drifta (anonymisert):\n" + json.dumps(self.context(base), ensure_ascii=False)
               + "\n\nSpørsmål frå driftsleiaren: " + str(question)[:2000])
        return self._ask(SYSTEM, msg)

    def _ask(self, system, msg):
        c = self.cfg["ai"]
        kind = c.get("leverandor")
        if kind == "ollama":
            url = (c.get("adresse") or "http://localhost:11434").rstrip("/") + "/api/chat"
            body = {"model": c.get("modell") or "llama3.1", "stream": False,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": msg}]}
            r = _post(url, body, {}, 300)
            return r["message"]["content"]
        if kind == "anthropic":
            if not c.get("api_nokkel"):
                raise RuntimeError("API-nøkkel manglar (kontorsida › AI).")
            body = {"model": c.get("modell") or "claude-sonnet-5-5", "max_tokens": 2000, "system": system,
                    "messages": [{"role": "user", "content": msg}]}
            r = _post("https://api.anthropic.com/v1/messages", body,
                      {"x-api-key": c["api_nokkel"], "anthropic-version": "2023-06-01"}, 120)
            return "".join(b.get("text", "") for b in r.get("content", []))
        raise RuntimeError(f"Ukjend AI-leverandør «{kind}»")


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"content-type": "application/json", "user-agent": f"SNOWMAN Base/{VERSION}",
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
        cat = s.get("kategori") if s.get("kategori") in CATEGORIES else "base"
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
