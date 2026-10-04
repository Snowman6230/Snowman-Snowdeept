# Endringslogg – SNOWMAN by Alpindata

Alle endringar i SNOWMAN blir førte her, med den nyaste øvst.
Kvar oppføring seier **kva** som vart endra og **kvifor**. Detaljane står i git-historikken.

Merke: **Nytt** · **Endra** · **Retta** · **Fjerna** · **Avgjerd** (val som styrer vidare utvikling)

---

## 2026-10-04

### Spesifikasjon: Terrain Engine
- **Nytt:** `docs/TERRAIN-ENGINE.md` – terrengbibliotek (legg til, erstatt, av/på, prioritet), typar flater (barmark, målflate, snøflate), opplastingsveivisar med formatkrav, fallgruver (UTM 32/33, NN2000 vs. ellipsoidisk høgd), trasear og anleggsobjekt, og rekkjefølgje v1.6–v1.8.
- **Avgjerd:** Terreng blir lagt inn som eit bibliotek med fleire lag og prioritet, ikkje som éi fil.
- **Avgjerd:** GeoTIFF er tilrådd format. LAS/LAZ og XYZ blir gjort om til rutenett ved import.
- **Avgjerd:** Snødjupne blir berre vist når RTK FIX, terrengdekning og kalibrering er på plass.
- **Avgjerd:** Trasear (ytterpunkt/omriss) og anleggsobjekt skal kunne registrerast – køyre og registrere, teikne på kart, eller importere fil.

### PC-prototype v1.5.2 – førarperspektiv og HUD
- **Nytt:** Førarperspektiv (knappen «Førarvising»): kartet blir vippa 50° og vist frå bak og over maskina, med horisont. Alltid køyreretning opp, zoomar nært maskina. Sporflate, piler og snødjupnefargar følgjer med i 3D.
- **Nytt:** HUD-versjon for frontruta (`hud.html`, opnast på `/hud`). Eiga side som kan køyre på eigen skjerm eller mobil på dashbordet: store tal for snødjupne og avvik frå måldjupne (✓ på mål / ▼ under / ▲ over), fart, kurs, RTK-status, prepareringstid. Spegling for HUD-film, nattmodus i dempa raudt, lysstyrke, fullskjerm, skjermen held seg vaken.
- **Nytt:** Førarskjermen sender tilstanden til den lokale tenesta (`/api/hud`), og HUD-en les derifrå. `--lan` / `LAN=1` gjer HUD tilgjengeleg for andre einingar i same nett.
- **Avgjerd:** HUD er skild ut som eigen versjon/side, så førarskjermen og HUD kan utviklast og testast kvar for seg.
- **Avgjerd:** HUD viser same reglar som førarskjermen: snødjupne berre som tal i demo (merka DEMO) til Terrain Engine finst. Nattmodus er dempa raud for å skåne nattsynet.
- **Avgjerd:** Ekte 3D-terreng (bakkar og kantar) kjem saman med Terrain Engine når LiDAR-modellen finst.

### PC-prototype v1.5.1 – spor som følgjer zoom
- **Retta:** Sporet etter maskina hadde fast breidd i pikslar og vart altfor breitt når ein zooma ut. No blir sporet teikna som ei flate i meter (fresbreidd), så det har rett storleik på alle zoomnivå og er like breitt som maskinteikninga.
- **Retta:** Overlappande spor vart mørkare. No blir all preparert flate vist med jamn farge, så opne felt synest tydeleg.
- **Retta:** Demoen la lanane med litt for stor avstand, slik at det vart smale opne felt. No ligg lanane med 0,2 m overlapp.
- **Endra:** Piler for køyreretning blir skjulte og senterlinja tynnare når ein zoomar langt ut.
- **Avgjerd:** Opne felt mellom spor skal berre visast når fres/utstyr faktisk ikkje har dekt flata.

### PC-prototype v1.5 – Linux-testpakke
- **Nytt:** `simuler-leica.py` – virtuell Leica (NMEA GGA, RTK FIX) for testing utan mottakar.
- **Endra:** `start-snowman.sh` har testmodus (`./start-snowman.sh sim`), sjekkar at pyserial finst, opnar vanleg vindauge som standard og fullskjerm med `KIOSK=1`, og stoppar tenesta når skriptet blir avslutta.

### PC-prototype v1.5 – kartkjelder og anleggsprofil
- **Nytt:** Val av kartkjelde per anlegg (Innstillingar › Kart): Kartverket topo/gråtone, lokale offline-kartfliser (`data/tiles`), eiga XYZ/WMTS- eller WMS-kjelde, OpenStreetMap (berre test) eller berre rutenett.
- **Nytt:** Anleggsprofil – eksporter alle innstillingar til ei fil og importer på dei andre maskinene på anlegget.
- **Avgjerd:** SNOWMAN skal kunne seljast til ulike anlegg og trakkemaskiner. Kart og maskinoppsett må difor kunne konfigurerast utan kodeendring.
- **Avgjerd:** OpenStreetMap sine kartfliser skal ikkje brukast i produktet (vilkåra tillèt ikkje kommersiell bruk).

### Lisens
- **Nytt:** `LICENSE` – alle rettar reserverte, bruk berre etter skriftleg lisensavtale. Copyright-linje i hovudfilene.
- **Avgjerd:** Repoet bør gjerast privat. Lisensnøkkel per maskin (signert, verkar offline) kjem seinare.

### PC-prototype v1.5 – v24-grensesnitt kopla til Leica/GNSS
- **Endra:** PC-versjonen bruker no same førargrensesnitt som Driver v24 (krav: «Alle funksjoner som virka i html varianten skal også virke i prototype. Husk å bruke samme layout»). Éi samla fil, hentar ikkje lenger kode frå GitHub ved oppstart.
- **Nytt:** Maskina følgjer GNSS-posisjonen frå den lokale tenesta. Spor, distanse, areal, fart og kurs blir rekna frå ekte posisjonar.
- **Nytt:** Fix, satellittar og HDOP frå mottakaren. Gult/raudt varsel utan RTK FIX. Varsel når GNSS-data stoppar.
- **Nytt:** Kalibrering (maskinnamn, antenne X/Y/Z, høgdeoffset) og LiDAR/terreng-registrering frå v1.4 som faner i innstillingane.
- **Nytt:** Arbeidsøkter blir lagra som filer på PC-en (`data/sessions`). Innstillingar (seriellport, NTRIP) blir hugsa mellom omstartar.
- **Nytt:** Areal-felt, kartretning nord opp / køyreretning opp, wake lock (skjermen sovnar ikkje), oppstart på Linux i Chromium kioskmodus (`start-snowman.sh`).
- **Nytt:** Leaflet ligg lokalt – appen startar utan nett.
- **Retta:** Maskinteikninga er i målestokk (fresbreidd = sporbreidd).
- **Retta:** Innstillingar frå v22/v23 gjekk tapt (feil lagringsnøkkel).
- **Retta:** Historikken kunne fylle nettlesarlageret og stoppe loggføringa.
- **Retta:** Distansen auka når maskina stod i ro (GPS-støy). No filter på minste flytting og dårleg nøyaktigheit.
- **Retta:** Kompass og GPS-kurs kjempa om kartrotasjonen. No styrer GNSS-kursen under køyring.
- **Retta:** «Start prep» under demo, og melding om lagring når ingenting vart lagra.
- **Endra:** Snødjupne blir vist som **IKKJE MÅLT** under ekte køyring, og sporet er nøytralt blått. Fargar og tal berre i demo, merka «DEMO – SIMULERTE DATA».
- **Avgjerd:** Simulert snødjupne skal aldri sjå ut som ekte måling.

### Opprydding
- **Nytt:** PC-prototype v1.2–v1.4 og SNOWMAN NTRIP Service v1.1 lagt inn i repoet (låg tidlegare berre som nedlastingar frå utviklinga i ChatGPT).
- **Avgjerd:** GitHub er staden for kode. Google Drive blir brukt til dokument (forretningsplan, investorpresentasjon).

---

## 2026-09-30

### PC-prototype v1.1 – v1.4 (utvikla i ChatGPT, lagt inn i repoet 2026-10-04)
- **v1.1:** PC-panel oppå v24 med Leica/NMEA via Web Serial, test-NMEA, NTRIP-test og terrengfil.
- **v1.2:** Éin samla oppstart (`START-SNOWMAN.bat`) med lokal Python-teneste. Grensesnittet vart for forenkla.
- **v1.3:** Forsøk på v24-layout + lokal GNSS/NTRIP-teneste.
- **v1.4:** Offline-kartidé, LiDAR-filval (LAS/LAZ/PLY/XYZ/CSV) med koordinat- og høgdesystem, maskinkalibrering. Kartet var eit rutenett, sporet og distansen var simulerte, og v24-layouten var ikkje med.
- **Nytt:** SNOWMAN NTRIP Service v1.1 – Python-bru mellom COM/Leica (NMEA GGA) og CPOS/NTRIP (RTCM).
- **Avgjerd:** Leica GS07 via RS232/NMEA skal støttast, men SNOWMAN skal vere leverandøruavhengig.
- **Avgjerd:** Mobil/HTML er demo og utviklingsverktøy. Sluttproduktet køyrer på PC i trakkemaskina (første kandidat: Surface Pro 1796 med lett Linux).

### Driver v20 – v24 (mobil/HTML)
- **v24:** Kartet roterer etter køyreretninga. Start/Stopp preparering – spor blir berre logga under aktiv preparering. Reset spor. Satellittstatus-panel. Samanhengande spor i fresbreidd i staden for boblar.
- **v23:** Satellittstatus og samanhengande dekningsspor.
- **v22:** Tidsbruk, piler for køyreretning, trakkemaskin-ikon.
- **v21:** Demo-område 300 × 50 m og avspeling av spor sortert på dato.
- **v20:** Retta av/på for snødjupne.

## 2026-09-29

### Snowman v2 – v19 (mobil/HTML)
- **v16–v19:** Fullskjerm førar-cockpit, innstillingsfaner, kart med køyreretning opp, vis/skjul maskin, klikkbar GPS-status.
- **v12–v15:** Gjennomsiktig trakkemaskin, justerbar maskinbreidd (5,5 m), skjer- og fresbreidd, snødjupneskala i seks nivå, utviklarnamn flytta til innstillingar.
- **v9–v11:** Mobil investorprototype, førarvisning med synleg trakkemaskin, kart med køyreretning opp.
- **v4–v8:** Terrenghøgd frå Kartverket Høydedata, terrengproxy (Cloudflare Worker), betre feilhandtering og 20 s timeout.
- **Avgjerd:** Geonorge/Kartverket-oppslag feila med timeout. Terrenget skal i staden kome frå eigen LiDAR-modell lagra lokalt.
- **v2:** Første versjon av Snowman by Alpindata.

---

## Planlagt

- **v1.6 Terrain Engine:** sjå `docs/TERRAIN-ENGINE.md`. Testast med syntetisk terreng, deretter Kartverket DTM 1 m for Fjellsætra.
- **v1.8 Trasear og anleggsobjekt.**
- Ekte 3D-terreng i førarperspektivet (frå LiDAR).
- HUD-test i maskina: lesbarheit natt/dag, dobbeltbilete i buet frontrute.
- Fleire maskinprofilar per anlegg.
- Lisensnøkkel per maskin.
- Felttest: RTK + LiDAR mot manuelt målt snødjupne.
