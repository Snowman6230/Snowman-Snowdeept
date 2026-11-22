# SNOWMAN Kontor

Kontorsida og anleggsserveren for SNOWMAN snødjupne. Køyrer på **ein PC på anlegget** (Windows).

```
SNOWMAN Base (Raspberry Pi ved antenna) ──NTRIP 2101──► tråkkemaskinene (SNOWMAN snødjupne)
        ▲ statusen (berre lesing)                              │  anleggspakke, forslag, hjarteslag
        │                                                      ▼  (wifi på anlegget, port 8790)
SNOWMAN Kontor (kontor-PC) ◄───────────────────────────────────┘
        ▲ nettlesar
     driftsleiaren
```

**Avgjerd 2026-11-22:** SNOWMAN Base har berre med satellittar og NTRIP å gjere. Alt anna – kontorsida, anleggspakkar,
forslag, maskinoversikt, deling og AI – ligg i SNOWMAN Kontor. Ei oppdatering eller ein feil i Kontor kan difor aldri
stoppe korreksjonane til maskinene.

## Kva Kontor gjer

| Funksjon | |
|---|---|
| **Anleggspakke** | Trasear, forbodne område, hindringar og kontrollpunkt ut til alle maskinene. Kontor kontrollerer pakka (formatversjon 1, sjå under). Alle versjonar blir tekne vare på, og ein kan rulle tilbake. |
| **Forslag** | Førarane sender forslag (ny hindring, trasé, merknad) frå maskina. Kontoret godkjenner, avviser eller merkjer som gjort. |
| **Maskinoversikt** | Kva SNOWMAN-versjon og anleggspakke kvar maskin har, og når ho sist melde seg. |
| **SNOWMAN Base (berre lesing)** | Korreksjonsstraumane og åtvaringane frå Base blir viste på oversikta og i forbetringslista. Kontor endrar aldri noko i Base. |
| **Forbetringar og AI** | Reglar (alltid på) og valfri AI (lokal Ollama eller Claude med eigen nøkkel, berre anonymisert samandrag). Eksport som Markdown til utviklaren. |
| **Deling (v1.8)** | API-et for delt snødjupne mellom maskinene er klart. SNOWMAN snødjupne brukar det frå v1.8. |

## Kom i gang (Windows)

1. Installer **Python 3.10 eller nyare** frå python.org. Vel «Install for all users» og hak av for «Add python.exe to PATH».
2. Pakk ut `SNOWMAN-Kontor.zip` **utanfor OneDrive**, t.d. til `C:\SNOWMAN-Kontor`.
3. Opne `v1.0` og dobbeltklikk **INSTALLER-WINDOWS.bat** (godta administratorløyve). Han:
   - lagar Python-miljøet,
   - lagar oppgåva «SNOWMAN Kontor», som startar Kontor ved kvar oppstart av Windows,
   - opnar port **8790** i brannmuren **berre frå privat nett** (wifi og nettverk på anlegget).
4. Opne **http://localhost:8790/** og lag **administrator** og ein **brukar for maskinene** (rolla «maskin»).
5. Under **System › SNOWMAN Base**: skriv adressa til statussida på Pi-en, t.d. `http://snowman-base.local:8780`.

Berre prøve, utan installasjon: dobbeltklikk `START-SNOWMAN-KONTOR.bat`.
Avinstallere: `INSTALLER-WINDOWS.bat fjern` (data blir ikkje sletta).

**PC-en:**
- Gi PC-en **fast IP-adresse** på nettet på anlegget (reservasjon i ruteren). Maskinene treng adressa.
- Nettverket må vere sett til **Privat** i Windows, elles stengjer brannmuren for maskinene.
- **Opne aldri port 8790 i ruteren mot internett.** Maskinene hentar anleggspakka når dei er på wifi på anlegget
  (t.d. i garasjen). Ute i bakken brukar dei siste pakke.
- PC-en treng ikkje stå på heile tida. Maskinene brukar siste pakke, og forslag ligg i kø i maskina til Kontor svarar.

## I SNOWMAN snødjupne (maskina)

Innst. › Trasear › **«Kopling til SNOWMAN Kontor»** (SNOWMAN 1.6.137 eller nyare):

| Felt | Verdi |
|---|---|
| Adresse til PC-en med Kontor | den faste IP-adressa til kontor-PC-en, t.d. `192.168.1.20` |
| Port | `8790` |
| Brukarnamn / passord | ein brukar med rolla **maskin** (Kontor › Brukarar) – ikkje NTRIP-brukaren |

Slå på koplinga og trykk **HENT FRÅ KONTOR**. Når ei pakke er henta, er trasear, forbodne område og kontrollpunkt
styrte frå kontoret. Ei ny hindring i maskina gir varsel med éin gong og blir sendt hit som forslag.

## Brukarar

| Rolle | Kven | |
|---|---|---|
| `maskin` | Tråkkemaskinene | Anleggspakke, forslag, hjarteslag, deling |
| `kontor` | Administrator | Kontorsida |

Kommandoar (i `v1.0`, også medan Kontor køyrer):

```
START-SNOWMAN-KONTOR.bat brukar liste
START-SNOWMAN-KONTOR.bat brukar legg-til NAMN [--rolle maskin|kontor|begge]
START-SNOWMAN-KONTOR.bat brukar passord NAMN        (gløymt passord)
START-SNOWMAN-KONTOR.bat brukar fjern NAMN
```

## Anleggspakke – format (formatversjon 1)

Ei zip-fil med dei **same filene som SNOWMAN snødjupne lagrar** i `data/`, pluss eit manifest:

| Fil | Innhald | Frå maskina |
|---|---|---|
| `manifest.json` | påkravd – sjå under | – |
| `trasear.json` | `{"trasear": [...]}` – trasear og forbodne område | `data/trasear.json` |
| `objekt.json` | `{"objekt": [...]}` – hindringar | `data/objekt.json` |
| `kontrollpunkt.json` | `{"points": [...]}` – kontrollpunkt (ikkje kontrollmålingane) | `points` i `data/kontroll.json` |
| `terreng/…` | terrenglag – plass i formatet, blir ikkje sendt enno | – |

```json
{"format": "snowman-anleggspakke", "formatversjon": 1, "anlegg": "Fjellsætra",
 "laga": "2026-11-20T09:00:00+0100", "laga_av": "admin", "snowman_min": "1.7.0",
 "filer": {"trasear.json": "<sha256>", "objekt.json": "<sha256>"}}
```

Alle innhaldsfilene er valfrie, men pakka må ha minst éi. Ei fil som manglar, betyr at maskina held på det ho har.
Kontor avviser pakka med forklaring om manifestet manglar, sha256 ikkje stemmer, ei fil er ukjend, eller trasear,
hindringar eller kontrollpunkt har ugyldige verdiar. `anleggspakke.py` – `lag()` lagar ei gyldig pakke.
Kartfana der kontoret kan hente frå ei maskin, redigere og publisere, er neste steg (VEGEN-VIDARE kap. 16, steg 3).

## Oppdatering

Kontorsida › **System › Oppdatering**: «Sjekk etter ny versjon» og «Oppdater og start på nytt». Kontor sjekkar sjølv
éin gong i døgnet. Automatisk oppdatering om natta kan slåast på (`oppdatering.auto` i `data/kontor.json`).
`data/` blir aldri rørt. Korreksjonane (SNOWMAN Base) blir ikkje påverka.

## Data

`v1.0/data/`: `kontor.json` (innstillingar og brukarar, passord som hash), `kontor.db` (maskiner, forslag,
forbetringar, dagstal, delte målingar), `anleggspakke/` (versjonane), `hendingar.log`, `teneste.log`.
Ta med `data/` i vanleg kopi av PC-en.

## Testar

```bash
cd kontor/v1.0 && python -m unittest discover -s test -v
cd pc/v1.6 && python3 test/testkontorkopling.py      # maskina mot Kontor
```
