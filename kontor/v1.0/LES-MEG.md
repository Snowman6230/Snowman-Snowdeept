# SNOWMAN Kontor

Kontorsida og anleggsserveren for SNOWMAN snødjupne. Køyrer på **ein PC på anlegget** (Windows).

**Frå 1.1.2** gjer du alt i **Kart og anlegg** – same skjermbilete som i maskinene. Knappen **▤ Kontor** i verktøylinja
(eller Innst. › Kontor) har publisering, maskinene, forslag, pakkar, brukarar, forbetringar, AI og system. Kontorsida på
8790 er ein reserve.

**Frå 1.1.0** har kontoret **same kart, 3D, terreng, trasear, hindringar og kontrollpunkt som i maskinene**: Kontor
startar SNOWMAN snødjupne i **kontormodus** (utan GNSS) på **http://localhost:8765/**. Der lastar du inn terrengmodellane
(dei same `.pxy`-filene som i dag), lagar trasear og hindringar og trykkjer **PUBLISER TIL MASKINENE**. Maskinene ute i
bakken blir viste på kartet i sanntid.

```
SNOWMAN Base (Raspberry Pi ved antenna) ──NTRIP 2101──► tråkkemaskinene (SNOWMAN snødjupne)
        ▲ statusen (berre lesing)                              │  anleggspakke med terreng (wifi, port 8790)
        │                                                      │  sanntid: posisjon og snødjupne
        │                                                      ▼  (wifi 8790, eller mobilnett 8791)
SNOWMAN Kontor (kontor-PC) ◄───────────────────────────────────┘
   ├ kontorsida  http://localhost:8790/   forslag, brukarar, system, Base-status
   └ kart og anlegg http://localhost:8765/ SNOWMAN snødjupne i kontormodus
```

**Avgjerd 2026-11-22:** SNOWMAN Base har berre med satellittar og NTRIP å gjere. Alt anna – kontorsida, anleggspakkar,
forslag, maskinoversikt, deling og AI – ligg i SNOWMAN Kontor. Ei oppdatering eller ein feil i Kontor kan difor aldri
stoppe korreksjonane til maskinene.

## Kva Kontor gjer

| Funksjon | |
|---|---|
| **Kart og anlegg (kontormodus)** | SNOWMAN snødjupne utan GNSS på http://localhost:8765/: terrengbibliotek, 3D, trasear, hindringar, kontrollpunkt – same skjermbilete som i maskina. Fana **Kontor** publiserer og viser maskinene. |
| **Sanntid** | Maskinene sender posisjon, snødjupne, fix og «preparerer» kvart 10. s og RTK FIX-målingar. Kartet i kontormodus viser maskinene og målingane (farga etter snødjupne) dei siste 12 timane. |
| **Anleggspakke** | Trasear, forbodne område, hindringar, kontrollpunkt **og terrengmodellane** ut til alle maskinene. Kontor kontrollerer pakka (formatversjon 1, sjå under). Alle versjonar blir tekne vare på, og ein kan rulle tilbake. |
| **Forslag** | Førarane sender forslag (ny hindring, trasé, merknad) frå maskina. Kontoret godkjenner, avviser eller merkjer som gjort. |
| **Maskinoversikt** | Kva SNOWMAN-versjon og anleggspakke kvar maskin har, og når ho sist melde seg. |
| **SNOWMAN Base (berre lesing)** | Korreksjonsstraumane og åtvaringane frå Base blir viste på oversikta og i forbetringslista. Kontor endrar aldri noko i Base. |
| **Forbetringar og AI** | Reglar (alltid på) og valfri AI (lokal Ollama eller Claude med eigen nøkkel, berre anonymisert samandrag). Eksport som Markdown til utviklaren. |
| **Deling (v1.8)** | API-et for delt snødjupne mellom maskinene er klart. SNOWMAN snødjupne brukar det frå v1.8. |

## Kom i gang (Windows)

1. Installer **Python 3.10 eller nyare** frå python.org. Vel «Install for all users» og hak av for «Add python.exe to PATH».
2. Pakk ut `SNOWMAN-Kontor.zip` **utanfor OneDrive**, t.d. til `C:\`. Du får `C:\SNOWMAN-Kontor\kontor\v1.0` (Kontor)
   og `C:\SNOWMAN-Kontor\pc\v1.6` (SNOWMAN snødjupne til kontormodus). Begge må liggje der – flytt ikkje på dei.
3. Opne `kontor\v1.0` og dobbeltklikk **INSTALLER-WINDOWS.bat** (godta administratorløyve). Han:
   - lagar Python-miljøet,
   - lagar oppgåva «SNOWMAN Kontor», som startar Kontor ved kvar oppstart av Windows,
   - opnar port **8790** i brannmuren **berre frå privat nett** (wifi og nettverk på anlegget),
   - opnar port **8791** (berre maskin-API-et) for sanntid ute i bakken.
4. Opne **http://localhost:8790/** og lag **administrator** og ein **brukar for maskinene** (rolla «maskin»).
5. Under **System › SNOWMAN Base**: skriv adressa til statussida på Pi-en, t.d. `http://snowman-base.local:8780`.
6. Opne **http://localhost:8765/** (lenkja «Kart og anlegg» på kontorsida). Last inn terrengmodellane i
   Terrengbiblioteket, lag trasear og hindringar, og publiser under fana **Kontor**.

Berre prøve, utan installasjon: dobbeltklikk `START-SNOWMAN-KONTOR.bat`.
Avinstallere: `INSTALLER-WINDOWS.bat fjern` (data blir ikkje sletta).

**PC-en:**
- Gi PC-en **fast IP-adresse** på nettet på anlegget (reservasjon i ruteren). Maskinene treng adressa.
- Nettverket må vere sett til **Privat** i Windows, elles stengjer brannmuren for maskinene.
- **Opne aldri port 8790 i ruteren mot internett.** Maskinene hentar anleggspakka når dei er på wifi på anlegget
  (t.d. i garasjen). Ute i bakken brukar dei siste pakke.
- **Sanntid ute i bakken (mobilnett):** send **berre port 8791** vidare i ruteren til kontor-PC-en, og gi anlegget eit
  namn som DuckDNS (t.d. `fjellsetra.duckdns.org`). På port 8791 svarar berre maskin-API-et, og berre for brukarar med
  rolla «maskin» – kontorsida og innlogginga finst ikkje der. Pakker over 50 MB (terreng) blir berre henta på wifi.
  Utan vidaresending fungerer alt anna som før; kartet viser då maskinene når dei er på wifi.
- PC-en treng ikkje stå på heile tida. Maskinene brukar siste pakke, og forslag ligg i kø i maskina til Kontor svarar.
- Kart og anlegg (8765) er berre for denne PC-en og blir ikkje opna i brannmuren.

## Nytt terreng ut til maskinene

1. Last inn eller byt terrengmodellen i Terrengbiblioteket på http://localhost:8765/ (kontormodus).
2. Fana **Kontor** › hak av for «Ta med terrengmodellane» › **PUBLISER TIL MASKINENE**. Alle *aktive* lag blir med.
3. Maskina lastar ned pakka på wifi. Terrenget blir **ikkje** teke i bruk av seg sjølv: føraren får knappen
   **⛰ TA I BRUK NYTT TERRENG** (Innst. › Trasear) og trykkjer når prepareringa er stoppa. Lokale lag i maskina blir slått
   av (ikkje sletta), og det gamle terrenget blir teke vare på (dei tre siste).
4. Gjer ei kontrollmåling etterpå. Kontorsida viser kva terrengversjon kvar maskin har.

## I SNOWMAN snødjupne (maskina)

Innst. › Trasear › **«Kopling til SNOWMAN Kontor»** (SNOWMAN 1.6.139 eller nyare):

| Felt | Verdi |
|---|---|
| Adresse til PC-en med Kontor | den faste IP-adressa til kontor-PC-en, t.d. `192.168.1.20` |
| Port | `8790` |
| Brukarnamn / passord | ein brukar med rolla **maskin** (Kontor › Brukarar) – ikkje NTRIP-brukaren |
| Adresse ute (valfritt) | DuckDNS-namnet til anlegget, t.d. `fjellsetra.duckdns.org` – berre når port 8791 er send vidare |
| Port ute | `8791` |
| Sanntid til kontoret | på (standard) – posisjon og snødjupne kvart 10. s |

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
| `terreng/<id>/meta.json` + `grid.npy` | terrenglag (aktive lag på kontoret) | terrengbiblioteket |

```json
{"format": "snowman-anleggspakke", "formatversjon": 1, "anlegg": "Fjellsætra",
 "laga": "2026-11-20T09:00:00+0100", "laga_av": "admin", "snowman_min": "1.7.0",
 "filer": {"trasear.json": "<sha256>", "objekt.json": "<sha256>"}}
```

Alle innhaldsfilene er valfrie, men pakka må ha minst éi. Ei fil som manglar, betyr at maskina held på det ho har.
Kontor avviser pakka med forklaring om manifestet manglar, sha256 ikkje stemmer, ei fil er ukjend, eller trasear,
hindringar eller kontrollpunkt har ugyldige verdiar. `anleggspakke.py` – `lag()` lagar ei gyldig pakke.
Pakka blir laga av kontormodus (`/api/kontormodus/publiser`) og send til Kontor. Maks 4 GB.

## Oppdatering

Du treng **aldri** laste ned zip-fila på nytt. Kontor ser sjølv etter ny versjon på GitHub ved oppstart og kvar 3. time –
både av **SNOWMAN Kontor** og av **kartet** (SNOWMAN snødjupne i `pc/`). Er det noko nytt, kjem det eit **gult varsel øvst
på kontorsida og i kartet** med knappen **Oppdater no**:

- **Berre kartet er nytt** (vanlegast – ny versjon av SNOWMAN snødjupne): berre kartet startar på nytt. Kontorsida,
  maskinporten og maskinene merkar ingenting. Kartet på kontoret er dermed alltid same versjon som i maskinene.
- **Kontor er nytt:** heile Kontor startar på nytt (nokre sekund).
- Kjem det ei ny versjonsmappe av snødjupne (t.d. `pc/v1.7`), blir ho henta og teken i bruk av seg sjølv, med pakkane ho treng.

«Seinare» gøymer varselet til neste versjon. Det same finst under **System › Oppdatering**. Automatisk oppdatering om
natta (03–05) kan slåast på (`oppdatering.auto` i `data/kontor.json`). `data/` blir aldri rørt, og korreksjonane
(SNOWMAN Base) blir ikkje påverka.

## Data

`v1.0/data/`: `kontor.json` (innstillingar og brukarar, passord som hash), `kontor.db` (maskiner, forslag,
forbetringar, dagstal, delte målingar), `anleggspakke/` (versjonane), `hendingar.log`, `teneste.log`.
Ta med `data/` i vanleg kopi av PC-en.

## Testar

```bash
cd kontor/v1.0 && python -m unittest discover -s test -v
cd pc/v1.6 && python3 test/testkontorkopling.py      # maskina mot Kontor (pakke, terreng, sanntid)
```
