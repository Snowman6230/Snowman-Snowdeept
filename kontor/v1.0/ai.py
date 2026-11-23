# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
"""AI i SNOWMAN Office – utskiftbar modul (same prinsipp som VEGEN-VIDARE kap. 14).

Leverandørar (innstillinga «ai.leverandor» i data/kontor.json, eller kontorsida):
    av          ingen AI (standard). Reglane i forbetring.py er alltid på.
    ollama      lokal språkmodell (Ollama på same maskin eller NAS) – ingenting forlèt anlegget. Tilrådd: LOKAL_MODELL.
                Office kan sjå om Ollama køyrer, hente modellen og ta han i bruk (Office › AI › Lokal AI).

SNOWMAN AI for maskinene (frå 1.3.0): førarane spør i SNOWMAN Snowdeep (AI-panelet), maskina sender spørsmålet og
eit kort samandrag av det skjermen viser til Office (POST /api/v1/ai/maskin, rolla maskin – også på maskinporten),
og Office svarar med AI-en som er sett opp her. Éin om gongen, så ein svak PC ikkje blir overlasta.
    anthropic   Claude via API – krev eigen API-nøkkel (lagra berre i data/kontor.json)

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


LOKAL_MODELL = "gemma3:4b"      # lokal standardmodell: god på norsk, går på ein vanleg PC (ca. 3 GB, 8 GB minne)
OLLAMA = "http://localhost:11434"

DRIVER = """Du er SNOWMAN AI i førarhuset på ei tråkkemaskin (SNOWMAN Snowdeep, Alpindata). Føraren spør medan han
arbeider. Svar på nynorsk, kort og konkret: 1–4 setningar, utan overskrifter og lister med mindre føraren ber om det.
Bygg på samandraget av skjermen (snødjupne, mål, GNSS, trasear, AI-råda frå den lokale modellen i maskina og vêret).
Finn ikkje på tal som ikkje står der – sei heller at du ikkje veit. Alt er råd: føraren avgjer. Gi aldri råd som går
ut over tryggleiken (bratt terreng, vinsj, folk i bakken, skred) – vis då til rutinane på anlegget."""


def ollama_url(adresse):
    """Adressa til Ollama som full URL. Tomt, «ollama» eller «localhost» → http://localhost:11434.
    «192.168.1.20» → http://192.168.1.20:11434. Ein feilskriven verdi (t.d. «ollama» i feltet) gir ikkje lenger
    «unknown url type»."""
    a = str(adresse or "").strip().rstrip("/")
    if not a or a.lower() in ("ollama", "localhost", "127.0.0.1", "lokal", "local"):
        return OLLAMA
    if "://" not in a:
        a = "http://" + a
    scheme, rest = a.split("://", 1)
    host = rest.split("/", 1)[0]
    if ":" not in host.split("]")[-1] and scheme.lower() == "http":
        host += ":11434"
    return f"{scheme.lower()}://{host}"


def lokal_modell(modell):
    """Modellnamnet til Ollama. Tomt eller «ollama» (programnamnet, ikkje ein modell) → LOKAL_MODELL."""
    m = str(modell or "").strip()
    return LOKAL_MODELL if not m or m.lower() in ("ollama", "lokal", "local") else m


class AI:
    def __init__(self, cfg, store, events):
        self.cfg = cfg
        self.store = store
        self.events = events
        self.last = None               # {"t", "ok", "tal", "feil"}
        self.lock = threading.Lock()   # éitt spørsmål om gongen frå maskinene
        self.pull_st = {}              # henting av lokal modell: {"modell", "status", "del", "ferdig", "feil", "t"}

    def enabled(self):
        return self.cfg["ai"].get("leverandor", "av") in ("ollama", "anthropic")

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
        """«Spør SNOWMAN Office»: fritt spørsmål med samandraget som bakgrunn."""
        if not self.enabled():
            raise RuntimeError("AI er av. Vel leverandør på kontorsida.")
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

    # ---------- lokal AI (Ollama) ----------
    def lokal(self):
        """Køyrer Ollama, og kva modellar har han? Ingenting blir endra."""
        adr = ollama_url(self.cfg["ai"].get("adresse"))
        r = {"adresse": adr, "koyrer": False, "versjon": None, "modellar": [], "tilradd": LOKAL_MODELL,
             "i_bruk": self.cfg["ai"].get("leverandor") == "ollama", "modell": lokal_modell(self.cfg["ai"].get("modell")),
             "henting": dict(self.pull_st), "feil": ""}
        try:
            with nett.urlopen(urllib.request.Request(adr + "/api/version"), timeout=3) as h:
                r["versjon"] = json.loads(h.read().decode("utf-8")).get("version")
            with nett.urlopen(urllib.request.Request(adr + "/api/tags"), timeout=5) as h:
                r["modellar"] = [m.get("name") for m in json.loads(h.read().decode("utf-8")).get("models", [])]
            r["koyrer"] = True
        except Exception as e:
            r["feil"] = ("Ollama er ikkje installert eller ikkje starta på denne PC-en." if "10061" in str(e) or
                         "refused" in str(e).lower() else nett.forklar(e))
        return r

    def hent_modell(self, modell=None):
        """Hentar ein modell i Ollama (bakgrunn). Framgangen står i lokal()["henting"]."""
        modell = (str(modell or "").strip() or LOKAL_MODELL)[:80]
        if self.pull_st.get("modell") and not self.pull_st.get("ferdig") and time.time() - self.pull_st.get("t", 0) < 120:
            raise RuntimeError(f"Hentar alt {self.pull_st['modell']} – vent til det er ferdig.")
        adr = ollama_url(self.cfg["ai"].get("adresse"))
        self.pull_st = {"modell": modell, "status": "startar", "del": 0.0, "ferdig": False, "feil": "", "t": time.time()}

        def run():
            try:
                req = urllib.request.Request(adr + "/api/pull", data=json.dumps({"model": modell, "stream": True}).encode(),
                                             method="POST", headers={"content-type": "application/json"})
                with nett.urlopen(req, timeout=3600) as h:
                    for line in h:
                        try:
                            d = json.loads(line)
                        except ValueError:
                            continue
                        if d.get("error"):
                            raise RuntimeError(d["error"])
                        self.pull_st.update({"status": d.get("status", ""), "t": time.time()})
                        if d.get("total") and d.get("completed"):
                            self.pull_st["del"] = d["completed"] / d["total"]
                self.pull_st.update({"ferdig": True, "status": "ferdig", "del": 1.0, "t": time.time()})
                self.events.add(f"Lokal AI: modellen {modell} er henta", "ok")
            except Exception as e:
                msg = str(e)
                if "10061" in msg or "refused" in msg.lower():
                    msg = "Ollama er ikkje installert eller ikkje starta på denne PC-en."
                self.pull_st.update(ferdig=True, feil=msg[:300], status="feila", t=time.time())
                self.events.add(f"Lokal AI: henting av {modell} feila: {msg[:200]}", "feil")
        threading.Thread(target=run, daemon=True, name="ollama-pull").start()
        return dict(self.pull_st)

    def _ask(self, system, msg):
        c = self.cfg["ai"]
        kind = c.get("leverandor")
        if kind == "ollama":
            url = ollama_url(c.get("adresse")) + "/api/chat"
            body = {"model": lokal_modell(c.get("modell")), "stream": False,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": msg}]}
            try:
                r = _post(url, body, {}, 300)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise RuntimeError(f"Ollama kjenner ikkje modellen «{body['model']}». Hent han først: "
                                       "trykk HENT MODELL under Office › AI › Lokal AI, eller skriv namnet på ein modell du "
                                       f"har i feltet Modell (tilrådd: {LOKAL_MODELL}).") from None
                raise
            except OSError as e:
                if "10061" in str(e) or "refused" in str(e).lower():
                    raise RuntimeError(f"Får ikkje kontakt med Ollama på {url.rsplit('/api/', 1)[0]}. Ollama er ikkje "
                                       "installert eller ikkje starta på denne PC-en. Installer frå ollama.com (eller køyr "
                                       "INSTALLER-WINDOWS.bat på nytt og svar J på lokal AI), og trykk HENT MODELL – eller vel "
                                       "«Claude (Anthropic API)» eller «Av».") from None
                raise RuntimeError(nett.forklar(e)) from None
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
