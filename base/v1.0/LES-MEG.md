# SNOWMAN Base (versjon 1.2 – mappa v1.0)

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
| **Reserve** | Kjeldene står i prioritert rekkjefølgje. Stoppar eigen base, går Base over til reserven (t.d. TH eller CPOS) med éin gong, og tilbake når eigen base har sendt stabilt i 60 s (ingen byte fram og tilbake). |
| **Innlogging** | Brukarnamn og passord – ingen nøklar. Rolla **ntrip** for maskinene (korreksjonar og API), **kontor** for administrator. |
| **Tilgang** | Fana «Tilgang» viser kva maskinene skal skrive i SNOWMAN, offentleg IP og CGNAT-sjekk, og held eit fast namn (dynamisk DNS) oppdatert. |
| **Vern** | Sperre i 10 min etter 10 feil passord frå same IP-adresse, grense for samtidige tilkoplingar, roterande hendingslogg. |
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
```

Opne deretter `http://<ip-til-pi>:8780/kontor/` frå ein PC på same nett og lag administrator.

### Windows

1. Last ned [SNOWMAN-Base.zip](https://github.com/Snowman6230/snowman-snowdeept/releases/download/siste/SNOWMAN-Base.zip)
   og pakk ut til ei mappe **utanfor OneDrive**, t.d. `C:\SNOWMAN-Base`.
2. **Fast drift (tilrådd):** dobbeltklikk `v1.0\INSTALLER-WINDOWS.bat` og godta spørsmålet om administratorløyve.
   Installasjonen
   - lagar Python-miljøet,
   - lagar oppgåva «SNOWMAN Base», som startar Base ved kvar oppstart av Windows (også utan innlogging, og etter
     straumbrot og Windows Update),
   - opnar brannmuren for port 2101 (og 8780 berre frå privat nett),
   - slår av dvale når PC-en står i straumen, og USB-straumsparing (mottakaren blir ikkje kopla frå).
   Logg: `v1.0\data\teneste.log`. Fjerne igjen: `INSTALLER-WINDOWS.bat fjern`.
3. **Prøve i eit vindauge:** dobbeltklikk `START-SNOWMAN-BASE.bat`. Ikkje bruk begge samstundes – då seier den andre
   at porten er i bruk.
4. Opne `http://localhost:8780/kontor/` og lag administrator (brukarnamn og passord).

### NAS (Synology, QNAP) eller server med Docker

Kort om NAS-vegen og når han passar: sjå kapitlet [«SNOWMAN Base på NAS»](#snowman-base-på-nas) under.

```bash
cd Snowman-Snowdeept/base/v1.0/installasjon
docker compose up -d --build
```

### Første oppstart: administrator og brukarar

Innlogging er **brukarnamn og passord**. Det finst ingen nøklar å ta vare på.

1. Opne kontorsida (`http://localhost:8780/kontor/`). Første gong ber ho deg lage ein **administrator** (rolla
   kontor). Det går berre frå det lokale nettet. Lag gjerne samstundes brukaren maskinene skal bruke (rolla ntrip).
2. Fana **Brukarar**: lag, endre og slett brukarar, og byt passord. Kvar maskin kan ha sin eigen brukar, eller alle
   kan bruke same. Nytt passord gjeld med éin gong.

| Rolle | Kven | Brukt til |
|---|---|---|
| `ntrip` | Tråkkemaskinene | Brukarnamn og passord i SNOWMAN snødjupne under NTRIP. Same innlogging gjeld for deling og anleggspakke (API). |
| `kontor` | Administrator | Kontorsida. |

**Gløymt passord** – på maskina Base køyrer på (fungerer også medan Base køyrer):

| Windows | Linux / Pi |
|---|---|
| `START-SNOWMAN-BASE.bat brukar passord NAMN` | `snowman-base brukar passord NAMN` |

| Kommando | Kva |
|---|---|
| `brukar legg-til NAMN [--rolle ntrip\|kontor\|begge] [--mountpoints FJELL]` | Ny brukar (spør etter passord) |
| `brukar passord NAMN` | Nytt passord |
| `brukar liste` / `brukar fjern NAMN` | |
| `mountpoint ny NAMN …` | `--seriell PORT [--baud]`, `--tcp-tenar PORT`, `--opplasting`, `--rele caster:port/MP`, `--reserve caster:port/MP`, `--brukar`, `--passord` |
| `oppdater` / `versjon` | Hent siste versjon / vis versjon |

Kommandoane gjeld med éin gong også når Base køyrer (Base les innstillingane på nytt innan to sekund). Frå versjon 1.2
blir dei gamle nøklane (`NOKLAR.txt`) ikkje brukte. NTRIP-brukarar frå før held fram som før.

### Mountpoint: legg inn manuelt på kontorsida

Det enklaste er å setje opp mountpointa på kontorsida, utan kommandoar:

1. Opne **http://localhost:8780/kontor/** og logg inn med brukarnamn og passord (administrator).
2. Fana **Mountpoints** › **+ Nytt mountpoint**. Skriv **Namn** (det maskinene skriv i «Mountpoint», t.d. `FJELL`).
3. Legg til kjelder i prioritert rekkjefølgje (øvst = første val, resten er reserve):
   - **Relé frå annan caster (NTRIP):** caster, port, brukarnamn, passord og mountpoint – same verdiar som du har
     brukt i SNOWMAN mot Norman sin caster (t.d. `gpsbase.dyndns.org`, `2101`, `TH`). «Hent mountpoints frå
     casteren» viser lista, men du kan òg skrive mountpointet sjølv.
   - **Mottakar på USB / COM-port:** t.d. `COM5`, 115200 baud. «Finn portar» viser portane på PC-en.
   - **Opplasting til Base:** for ein NTRIP-server (t.d. str2str på ein Raspberry Pi). Passordet blir vist éin gong.
   - **Mottakar sender inn på ein TCP-port** eller **mottakar på nettet**.
4. **Lagre og ta i bruk.** Endringa gjeld med éin gong – Base treng ikkje startast på nytt. Maskiner som er kopla
   til, koplar seg til på nytt av seg sjølv.

Passord blir aldri viste på kontorsida. Når du endrar eit mountpoint, står passordet att om du lèt feltet vere tomt.
«Tilbake til første kjelde» (standard 60 s): kor lenge eigen base må ha sendt utan opphald før Base byter tilbake frå
reserven. Hindrar at maskinene får byte av base fram og tilbake når eigen base er ustabil.

## SNOWMAN Base på NAS

Ein NAS står uansett på heile døgnet, har straumvern og kopi av data – ein god stad for Base når anlegget har ein.
Base køyrer i **Docker**: ein «container» med Python og det Base treng, avgrensa frå resten av NAS-en.
Programfilene og `data/` ligg i vanlege mapper på NAS-en, så «Oppdater» på kontorsida fungerer, og ingenting går
tapt om containeren blir bygd på nytt.

### Krav

| | |
|---|---|
| NAS | Synology med DSM 7.2 eller nyare (**Container Manager**), eller QNAP med **Container Station**. Både Intel/AMD- og ARM-modellar fungerer. |
| Minne og disk | Base brukar lite: under 200 MB minne. Rekn 5 GB disk til rådatalogg (30 dagar) og anleggspakkar. |
| Nett | Fast IP-adresse for NAS-en på det lokale nettet (reservert i ruteren). |

### Mottakaren: helst ikkje på USB i NAS-en

NAS-en står sjeldan der antenna kan stå, og **Synology DSM 7 har avgrensa støtte for USB-seriell-einingar** (GNSS-mottakarar
blir ofte ikkje kjende att utan ekstra drivarar). Tilrådd oppsett:

```
antenne ── mottakar ── Raspberry Pi (ved antenna) ──nett──► NAS med SNOWMAN Base ──► maskinene
                       str2str sender inn (opplasting)
```

1. På NAS-en: `mountpoint ny FJELL --opplasting --reserve gpsbase.dyndns.org:2101/TH` (sjå «Første oppstart»).
2. På Pi-en: `str2str -in serial://ttyACM0:115200 -out ntrips://:PASSORD@NAS-ADRESSE:2101/FJELL` som teneste.

Har NAS-en mottakaren på USB likevel (QNAP, eller Synology der eininga finst som `/dev/ttyACM0`): fjern `#` under
`devices` i `docker-compose.yml` og bruk `--seriell /dev/ttyACM0`.

### Installasjon på Synology (Container Manager)

1. **Pakkesenter** › installer **Container Manager** (og **Git Server** eller last ned repoet som zip).
2. Pakk ut `SNOWMAN-Base.zip` i ei delt mappe, t.d. `/volume1/docker/snowman-base`, slik at `v1.0` ligg der
   (eller legg heile repoet der, så `base/v1.0` ligg der). Bruk den mappa i stiane under.
3. **Container Manager** › **Prosjekt** › **Opprett**: namn `snowman-base`, sti `/volume1/docker/snowman-base/v1.0/installasjon`,
   kjelde «Bruk eksisterande docker-compose.yml». Byggjer og startar.
4. Opne `http://NAS-ADRESSE:8780/kontor/` og lag administrator (brukarnamn og passord).
5. Kommandoar (mountpoint, brukarar, nøklar): Container Manager › Container › `snowman-base` › **Terminal** ›
   `python /app/snowman_base.py mountpoint ny FJELL --opplasting`, og start containeren på nytt.

### Installasjon på QNAP (Container Station)

Container Station › **Applikasjonar** › **Opprett** › lim inn `docker-compose.yml` (rett stiane til mappa der repoet
ligg), eller køyr `docker compose up -d --build` over SSH i `base/v1.0/installasjon`.

### Nå Base utanfrå (som Norman sin base på gpsbase.dyndns.org)

Maskinene brukar mobilnett og må nå NAS-en frå internett. To måtar:

| | Dynamisk DNS + port 2101 | Tailscale |
|---|---|---|
| Korleis | Eit fast namn (t.d. `fjellsatra.synology.me`) peikar alltid til den offentlege IP-adressa til anlegget. Ruteren sender port 2101 vidare til NAS-en. | Kryptert privat nett mellom NAS og maskiner. Ingen opne portar. |
| Oppsett | Synology: Kontrollpanel › Ekstern tilgang › **DDNS** (gratis `synology.me`). Eller DDNS i ruteren. Ruteren: vidaresend **TCP 2101** → NAS. | Tailscale-pakken på NAS-en og Tailscale på kvar maskin-PC. |
| I SNOWMAN | caster `fjellsatra.synology.me`, port 2101 | caster = Tailscale-namnet til NAS-en, port 2101 |
| Passar | Akkurat som TH i dag. Også for andre (t.d. Norman) som vil bruke basen. | Sikrast, men kvar eining må ha Tailscale. |

Opne **berre port 2101** mot internett, aldri 8780 (status og kontor) – bruk Tailscale eller VPN til kontorsida utanfrå.
Port-vidaresending krev at internettsambandet på anlegget har ei offentleg IP-adresse (ikkje CGNAT). Sjekk det hos
internettleverandøren; har sambandet ikkje det, er Tailscale løysinga.

### Kopi og oppdatering

- Ta med `base/v1.0/data/` i NAS-en sin vanlege kopi (Hyper Backup / HBS). Rådataloggen kan utelatast.
- Oppdatering: kontorsida › System › **Oppdater**. Containeren startar på nytt av seg sjølv (kode 3, `restart: unless-stopped`).
- Ny Python-versjon i containeren (sjeldan): Container Manager › Prosjekt › `snowman-base` › **Bygg** på nytt.

## I SNOWMAN snødjupne (maskina) – som mot Norman sin base

Same felt som mot `gpsbase.dyndns.org:2101/TH`:

| Felt i SNOWMAN | Ute i bakken (mobilnett) | På anlegget (same nett) |
|---|---|---|
| Caster | det faste namnet (dynamisk DNS), t.d. `fjellsatra.duckdns.org` | IP-adressa til Base, t.d. `192.168.1.20` |
| Port | 2101 | 2101 |
| Mountpoint | namnet i Base, t.d. `FJELL` («HENT MOUNTPOINTS» viser lista) | same |
| Brukarnamn / passord | ein brukar med rolla ntrip | same |

Fana **Tilgang** på kontorsida viser desse verdiane for ditt anlegg.

**Slik blir Base nådd utanfrå (fiber med offentleg IP – som Norman):**
1. Fast lokal IP-adresse til maskina med Base (reservasjon i ruteren).
2. Port-vidaresending i ruteren: **TCP 2101** → maskina med Base. **Aldri 8780.**
3. Fast namn: ei gratis DDNS-teneste (t.d. DuckDNS). Lim inn oppdaterings-adressa i **Tilgang › Dynamisk DNS**, så
   held Base namnet oppdatert og viser om det peikar rett. Har ruteren innebygd DDNS, kan den brukast i staden.
4. Test: SNOWMAN-PC-en på mobilnett (deling frå telefonen, Wi-Fi av på telefonen) → «HENT MOUNTPOINTS».

Er den offentlege adressa delt (CGNAT – vanleg på mobilt breiband), fungerer ikkje port-vidaresending. Då: **Tailscale**
på maskina med Base og på kvar maskin-PC, eller send straumen vidare til ein caster på internett med RTKLIB:
`str2str -in ntrip://BRUKAR:PASSORD@localhost:2101/FJELL -out ntrips://:PASSORD2@rtk2go.com:2101/FJELLSATRA`.

## Basemottakaren

Base sender vidare det mottakaren sender, uendra. Mottakaren må stå i **basemodus med fast, innmålt koordinat** og sende:

| Melding | Kvifor |
|---|---|
| 1005 eller 1006 | Baseposisjonen (kvart 5.–10. sekund) |
| MSM4 eller MSM7 for GPS, GLONASS, Galileo, BeiDou (1074/1084/1094/1124 eller 1077/1087/1097/1127) | Observasjonane. **Ikkje MSM3** – RTKLIB i SNOWMAN les ikkje MSM3. |
| 1230 | GLONASS-bias |
| 1019, 1020, 1042, 1046 (om mottakaren kan) | Satellittbaner til RTK-motoren i SNOWMAN. ZED-F9P kan ikkje sende baner som RTCM – då bør du leggje til eit tillegg med baner, eller slå på `baner.hent`. |

- **u-blox ZED-F9P:** u-center › CFG-TMODE3 = Fixed (ECEF eller LLH frå innmålinga), og RTCM-meldingane over ut på USB.
  Gi basen ein **eigen stasjons-ID** (ikkje 0, og ikkje same som reserven) – Base åtvarar om to kjelder har same ID.
  Lagre konfigurasjonen i mottakaren: Base sender aldri noko til mottakaren.
- **Unicore UM980/UM981:** baseposisjon med fast koordinat, og RTCM-meldingane over (sjå handboka til mottakaren for kommandoane). UM980 kan også sende baner.

Legg inn den innmålte posisjonen (ARP, EUREF89, ellipsoidisk høgd) på kontorsida › Mountpoints › Endre › «Innmålt
basepunkt» (eller i `data/base.json` under mountpointet). Er TH reserve, bør basepunktet vere målt inn mot TH (t.d. med
R12i), så snødjupna ikkje hoppar når Base byter:

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
- Bruk sterke passord (minst 8 teikn). Etter 10 feil passord frå same IP-adresse blir adressa sperra i 10 minutt
  (`vern` i `data/base.json`). Maks 20 samtidige tilkoplingar per adresse og 200 i alt.
- NTRIP sender brukarnamn og passord ukryptert (som alle NTRIP 1/2-castarar, også TH og CPOS). Bruk difor ein eigen
  NTRIP-brukar for maskinene, ikkje same passord som administratoren.
- `web.status_open: false` krev innlogging også for statussida.
- Ta kopi av `data/` (innstillingar, anleggspakkar, delte målingar). Rådataloggen kan utelatast.
- Hendingane står òg i `data/hendingar.log` (blir rotert til `hendingar.log.1` ved 5 MB).
