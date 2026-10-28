# SNOWMAN Base v1.0

RTK-base, NTRIP-caster og anleggsserver for SNOWMAN snødjupne. Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata).

```
GNSS-mottakar (base) ──USB / nett / opplasting──►  SNOWMAN Base  ──NTRIP──►  SNOWMAN på tråkkemaskinene
reserve: TH / CPOS ─────────────relé─────────────►  (PC, NAS, Pi)  ◄─API───  deling, anleggspakke, forslag
                                                       │
                                     statusside :8780 · kontor :8780/kontor · AI (valfri)
```

## Kva Base gjer

| Funksjon | Kort |
|---|---|
| **NTRIP-caster** (port 2101) | NTRIP 1 og 2, same protokoll som TH og CPOS. Testa mot NTRIP-klienten i SNOWMAN snødjupne. |
| **Kjelder** | Mottakar på USB/seriell, mottakar på nettet (TCP), eining som sender inn (TCP-tenar eller NTRIP-opplasting frå t.d. ein Raspberry Pi ved antenna), relé frå annan caster, avspeling (test). |
| **Reserve** | Kjeldene står i prioritert rekkjefølgje. Stoppar eigen base, går Base over til reserven (t.d. TH eller CPOS) og tilbake når eigen base er oppe att. |
| **Tillegg** | Utvalde meldingar (standard: satellittbaner 1019/1020/1042/1045/1046) frå ei anna kjelde blir lagde inn i straumen. RTK-motoren i SNOWMAN treng baner. |
| **Basekontroll** | Posisjonen basen sender (1005/1006) blir samanlikna med innmålt koordinat. Avvik over 5 cm gir åtvaring. |
| **Rådatalogg** | Alt mottakaren sender, éi fil per time (grunnlag for PPP-innmåling av basen og feilsøking). Blir sletta etter 30 dagar. |
| **Satellittbaner (BRDC)** | Valfritt: Base hentar dagleg banefil frå BKG/IGS og deler henne med maskinene. |
| **Deling (API v1)** | Snødjupne frå maskinene siste 12 t (berre RTK FIX frå kalibrerte maskiner), hjarteslag og maskinliste. For SNOWMAN v1.8. |
| **Anleggspakke** | Kontoret lastar opp ny versjon, maskinene hentar henne. Alle versjonar blir tekne vare på, og ein kan rulle tilbake. |
| **Forslag** | Førarane kan melde ny hindring, merknad eller ønske til programmet. Kontoret godkjenner. |
| **Forbetringar** | Reglar (alltid på) og AI (valfri) foreslår forbetringar i oppsett, utstyr, drift og i SNOWMAN-programma. Kan eksporterast som oppgåveliste til utviklaren. |
| **Oppdatering** | Same som SNOWMAN snødjupne: git pull eller zip frå GitHub. Éin knapp på kontorsida. `data/` blir aldri rørt. |

## Kom i gang

Krev Python 3.10 eller nyare. `pyserial` trengst berre for mottakar på USB.

### Linux, Raspberry Pi eller liten server (tilrådd)

```bash
git clone https://github.com/Snowman6230/Snowman-Snowdeept.git
cd Snowman-Snowdeept/base/v1.0
bash installasjon/installer-linux.sh          # systemteneste + kommandoen «snowman-base»
snowman-base mountpoint ny FJELL --seriell /dev/ttyACM0 --reserve gpsbase.dyndns.org:2101/TH
sudo systemctl restart snowman-base
```

### Windows

Last ned repoet (git eller zip), opne `base\v1.0` og dobbeltklikk `START-SNOWMAN-BASE.bat`. Første gong blir Python-pakkane installerte. Kommandoar: `START-SNOWMAN-BASE.bat mountpoint ny FJELL --seriell COM5`.

### NAS (Synology, QNAP) eller server med Docker

```bash
cd Snowman-Snowdeept/base/v1.0/installasjon
docker compose up -d --build
```

Programmet ligg i ei mappe som blir montert inn i containeren, så «Oppdater» på kontorsida fungerer også her. Mottakar på USB: fjern `#` under `devices` i `docker-compose.yml`. Er mottakaren ved antenna og NAS-en i kjellaren, er det betre med ein Raspberry Pi ved antenna som sender inn (sjå «Opplasting»).

### Første oppstart

Base lagar ein NTRIP-brukar, ein **anleggsnøkkel** (maskinene) og ein **kontornøkkel** (kontorsida), og skriv dei éin gong til `data/NOKLAR.txt`. Ta vare på dei og slett fila. Nøklane blir berre lagra som hash.

| Kommando | Kva |
|---|---|
| `snowman-base brukar legg-til PB1` | Eigen NTRIP-brukar per maskin (passordet blir vist) |
| `snowman-base brukar liste` / `fjern PB1` | |
| `snowman-base nokkel kontor` | Ny kontornøkkel (den gamle sluttar å virke) |
| `snowman-base mountpoint ny NAMN …` | `--seriell PORT [--baud]`, `--tcp-tenar PORT`, `--opplasting`, `--rele caster:port/MP`, `--reserve caster:port/MP`, `--brukar`, `--passord` |
| `snowman-base oppdater` | Hent siste versjon |
| `snowman-base versjon` | |

## I SNOWMAN snødjupne (maskina)

NTRIP-innstillingane: caster = adressa til Base (t.d. `192.168.1.20`, eller Tailscale-namnet), port **2101**, mountpoint = namnet du valde (t.d. `FJELL`), brukar og passord frå `NOKLAR.txt`. «HENT MOUNTPOINTS» viser lista frå Base.

Maskinene må nå Base. På anlegget: same nett. Over mobilnettet: opne port 2101 i ruteren (berre 2101, ikkje 8780), eller bruk **Tailscale** (gratis for små oppsett, ingen opne portar).

## Basemottakaren

Base sender vidare det mottakaren sender, uendra. Mottakaren må stå i **basemodus med fast, innmålt koordinat** og sende:

| Melding | Kvifor |
|---|---|
| 1005 eller 1006 | Baseposisjonen (kvart 5.–10. sekund) |
| MSM4 eller MSM7 for GPS, GLONASS, Galileo, BeiDou (1074/1084/1094/1124 eller 1077/1087/1097/1127) | Observasjonane. **Ikkje MSM3** – RTKLIB i SNOWMAN les ikkje MSM3. |
| 1230 | GLONASS-bias |
| 1019, 1020, 1042, 1046 (om mottakaren kan) | Satellittbaner til RTK-motoren i SNOWMAN. ZED-F9P kan ikkje sende baner som RTCM – då bør du leggje til eit tillegg med baner, eller slå på `baner.hent`. |

- **u-blox ZED-F9P:** u-center › CFG-TMODE3 = Fixed (ECEF eller LLH frå innmålinga), og RTCM-meldingane over ut på USB.
- **Unicore UM980/UM981:** baseposisjon med fast koordinat, og RTCM-meldingane over (sjå handboka til mottakaren for kommandoane). UM980 kan også sende baner.

Legg inn den innmålte posisjonen (ARP, EUREF89, ellipsoidisk høgd) i `data/base.json` under mountpointet:

```json
"innmalt": {"lat": 62.380200, "lon": 6.781100, "h": 702.35}
```

## Døme på mountpoint i data/base.json

```json
{
  "namn": "FJELL",
  "skildring": "Fjellsætra – eigen base",
  "kjelder": [
    {"type": "seriell", "namn": "mottakar", "port": "/dev/ttyACM0", "baud": 115200},
    {"type": "ntrip", "namn": "reserve-TH", "caster": "gpsbase.dyndns.org", "port": 2101, "mountpoint": "TH",
     "brukar": "", "passord": ""}
  ],
  "tillegg": [
    {"type": "ntrip", "namn": "baner", "caster": "…", "port": 2101, "mountpoint": "…", "typar": [1019, 1020, 1042, 1046]}
  ],
  "byte_etter_s": 10,
  "innmalt": {"lat": 62.3802, "lon": 6.7811, "h": 702.35}
}
```

Andre kjeldetypar: `{"type": "tcp", "vert": "192.168.1.50", "port": 5016}`, `{"type": "tcp-tenar", "port": 5016}`,
`{"type": "opplasting", "hash": "…"}` (lag med `mountpoint ny … --opplasting`), `{"type": "fil", "sti": "opptak.rtcm3"}` (test).
Ei relékjelde til nettverks-RTK (CPOS) sender GGA med posisjonen frå `innmalt` (eller `"gga": {"lat", "lon", "h"}` på kjelda).

### Opplasting frå ein Raspberry Pi ved antenna

```bash
# på Pi-en (RTKLIB str2str), mottakaren på /dev/ttyACM0:
str2str -in serial://ttyACM0:115200 -out ntrips://:PASSORD@ADRESSE-TIL-BASE:2101/FJELL
```

## Forbetringar og AI

Forbetringsmotoren køyrer kvart 15. minutt og finn mellom anna: MSM3, manglande baner, berre GPS+GLONASS, ikkje innmålt eller avvikande baseposisjon, reserve i bruk, mange byte, låg oppetid, CRC-feil, ustabilt samband til ei maskin, gammal SNOWMAN-versjon, låg FIX-del, gammal anleggspakke, lite diskplass og ny versjon av Base. Dagstal blir lagra for trendar.

**AI** (kontorsida › AI) er av som standard. Vel:
- **Lokal modell (Ollama)** på same PC eller NAS: ingenting forlèt anlegget.
- **Claude (Anthropic API)** med eigen API-nøkkel (lagra berre i `data/base.json`).

AI får eit anonymisert samandrag (ingen namn, IP-adresser, posisjonar eller nøklar). Ønske frå førarane blir sende som tekst. «Førehandsvis» viser nøyaktig kva som blir sendt. AI foreslår, men styrer aldri noko. Forslaga kan lastast ned som Markdown og givast til utviklaren som oppgåveliste.

## Samspel med SNOWMAN snødjupne

- Casteren fungerer med alle SNOWMAN-versjonar.
- API v1 (deling, anleggspakke, forslag) er klart for SNOWMAN v1.8. `/api/v1/info` viser versjon, API-versjon, funksjonar og minste SNOWMAN-versjon. Maskiner som er for gamle, blir viste på kontorsida.
- Endrar du casteren eller API-et: køyr testane (under). Kompatibilitetstesten brukar NTRIP-klienten frå `pc/v1.6`. Eit brot i API-et gir ny API-versjon (`/api/v2/`), og v1 blir verande.

## Testar

```bash
cd base/v1.0 && python -m unittest discover -s test -v
```

## Tryggleik og drift

- Opne berre port **2101** mot internett, aldri 8780 (statusside og kontor). Bruk Tailscale eller VPN for kontoret utanfrå.
- `web.status_open: false` krev kontornøkkel også for statussida.
- Ta kopi av `data/` (innstillingar, anleggspakkar, delte målingar). Rådataloggen kan utelatast.
- Hendingane står òg i `data/hendingar.log`.
