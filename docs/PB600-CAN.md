# PistenBully 600 SCR – maskindata frå CAN til SNOWMAN (forundersøking)

Status 2026-10-08: **forundersøking – ingen kode, inga tilkopling.** Første mål er å finne rett CAN-/diagnosedokumentasjon
for PB600 SCR og avgjere kva maskindata SNOWMAN kan hente utan ekstra sensorar.

**Merking i dette dokumentet** (vi gjettar aldri pinout, CAN-ID-ar eller signaldefinisjonar):

| Merke | Tyder |
|---|---|
| **[D]** | Dokumentert i ei kjelde (lenkje oppgitt) |
| **[S]** | Standard SAE J1939 – gjeld *om* motorstyringa sender meldinga; må stadfestast i CAN-logg frå maskina |
| **[O]** | Må observerast i CAN-logg frå maskina |
| **[H]** | Hypotese – ikkje stadfesta |
| **[E]** | Eigaren sine funn (ikkje kontrollert her) |

---

## 1. Maskina: kva generasjon er «PB600 SCR»?

| Opplysning | Merke | Kjelde |
|---|---|---|
| PB600 Polar SCR (katalog 3/2013): motor **Mercedes-Benz OM 460 LA**, 6 syl., 12,8 l, 375 kW (510 PS), **Tier 4i**, SCR-katalysator, AdBlue-tank 40 l | [D] | [Brosjyre 600 Polar SCR (DE)](https://static1.squarespace.com/static/592c1631c534a5adf88fa047/t/5c896fa3f4e1fc8e31044866/1552510902783/broschuere_600_Polar_SCR_de.pdf) |
| 24 V-anlegg, 24 V/140 A generator, 2 × 12 V/135 Ah batteri | [D] | same |
| «**PSX-Leitrechner**» for sentral styring og diagnose om bord; 10,4" touchskjerm og **TerminalControlCenter (TCC)** | [D] | same |
| Maskina er fjerndiagnostiserbar; **Com-Box** (standard) for driftsdata, telemetri og servicekommunikasjon | [D] | same |
| SNOWsat (snødjupne og flåtestyring) som tilleggsutstyr | [D] | same, og [datablad PB600](https://www.pistenbully.com/_Resources/Persistent/a/8/9/7/a89723a64173f56b81bc6583094a1aa75e5ff8ab/Datenblatt_PistenBully_600_EN_AWB.pdf) |
| Dagens PB600 (Stage V) har **Cummins X12** – altså ein annan motor/annan generasjon enn 2012–2018-maskina | [D] | [datablad PB600](https://www.pistenbully.com/_Resources/Persistent/a/8/9/7/a89723a64173f56b81bc6583094a1aa75e5ff8ab/Datenblatt_PistenBully_600_EN_AWB.pdf) |

**Konsekvens:** Kva motorstyring (ECU) OM 460 LA Tier 4i har, og kva J1939-meldingar ho sender, er **[H]** til vi har
chassisnummer/årsmodell og ein CAN-logg. Eksakt WKU/chassisnummer trengst for å bestille rett *Planbuch/Schaltplan*.

## 2. Kva veit vi om CAN og sensorar på PB600 (eldre generasjon)?

Frå [instruksjonsboka PB600/600 Polar «From WKU 5 826 MA A L 011021»](https://telemet.com/_manuals/Pistenbully/PB600/600-ab-011021_en.pdf)
(OM 460 LA, EUROMOT III – **eldre enn SCR-generasjonen**, men same familie):

| Opplysning | Merke |
|---|---|
| Feilkode-undergruppe «7 = **CAN monitoring**», og feil «7,2,043 **No engine data available on CAN**» → motordata går over CAN til styresystemet | [D] (eldre gen.) |
| «3,2,002 **Length measuring system, tiller-depth cylinder**» → fresedjupna har **lengdemåling i sylinderen** | [D] (eldre gen.) |
| «3,2,001 **Length measuring system, lifting cylinder**» → løftesylinderen for bakre ramme har **lengdemåling** | [D] (eldre gen.) |
| «3,2,005/006 Tiller-depth sensor for lifting/lowering defective» | [D] (eldre gen.) |
| Fresedjupna blir vist på terminalen | [D] (eldre gen.) |
| Frontskjeret (løft, tilt, sving, venger) blir styrt med joystick; **inga posisjonsgivarar for skjeret er nemnde**, berre «Front-equipment detection» (16,3,037) | [D] (eldre gen.) |
| Bussfart, ID-ar, kva buss motor og fres ligg på, diagnosekontakt og pinout: **ikkje skildra** i instruksjonsboka | – |

**Vurdering:** Fresedjupn og løft av bakre ramme er truleg målte verdiar (sylinder med lengdemåling) som styresystemet
kjenner – og dermed **truleg** finst på ein CAN-buss **[H]**. Om dei ligg på ein buss vi kan lytte på (og ikkje berre
internt i PSX-styringa), må **[O]** observerast. Sideposisjon, fresturtal, kontakttrykk og flytestilling: **[H]/[E]**.
«0–1000»-verdiane (0 = venstre, 500 = midten, 1000 = høgre) er **[E]** – kjelda bør leggjast ved her.

Frontskjeret: ingen dokumentasjon på absolutte posisjonsgivarar → planlegg med at det **ikkje** finst **[H]**; eventuelt
eigne vinkel-/lengdegivarar seinare.

## 3. Diagnosekontakt, pinout og bussfart

| Punkt | Status |
|---|---|
| Diagnosekontakt, plassering og type på PB600 SCR | **Ukjend** – må finnast i Planbuch/servicehandbok (826 11720) eller sjåast på maskina **[O]** |
| *Om* maskina har ein standard J1939-kontakt (Deutsch HD10-9-1939, 9-pinnar): A = batteri −, B = batteri +, C = CAN_H, D = CAN_L, E = skjerm, F/G = J1708, H/J = OEM-/reiskaps-CAN | **[S]** – [Copperhill: J1939/13](https://copperhilltech.com/blog/sae-j193913-offboard-diagnostic-connector-deutsch-hd1091939-/). **Ikkje bruk før kontakten er stadfesta på maskina.** |
| Bussfart: J1939 er normalt 250 kbit/s (J1939-11) eller 500 kbit/s (J1939-14) | **[S]**; PB600 sin faktiske fart **[O]** (adapter i lyttemodus kan prøve 250/500 utan å forstyrre) |
| Kva buss motoren og fresa/bakre utstyr ligg på (CAN 1/CAN 2) | **[O]** / Planbuch |

## 4. Standard J1939-meldingar som truleg er nyttige [S]

Gjeld berre om motorstyringa/maskina sender dei – **[O]** stadfest i logg. PGN/SPN frå
[Woodward easYgen J1939-protokoll](https://support.woodward.com/file.php/8090PAZXYXHXGT8089993AB4A0F/easYgen-3000XT-Series-1939-Protocol.pdf);
skalering etter SAE J1939-71 må kontrollerast mot DBC før bruk.

| Variabel i SNOWMAN | J1939 | PGN (des / hex) | SPN |
|---|---|---|---|
| `engineRPM` | EEC1 | 61444 / 0xF004 | 190 |
| `engineLoad` (moment %) | EEC1 / EEC2 | 61444 / 61443 | 513 / 92 |
| `coolantTemperature` | ET1 | 65262 / 0xFEEE | 110 |
| oljetrykk | EFL/P1 | 65263 / 0xFEEF | 100 |
| `operatingHours` | HOURS | 65253 / 0xFEE5 | 247 |
| `fuelConsumption` (l/t) | LFE | 65266 / 0xFEF2 | 183 |
| totalt drivstoff brukt | LFC | 65257 / 0xFEE9 | 250 |
| `fuelLevel` | DD | 65276 / 0xFEFC | 96 |
| `adBlueLevel` | AdBlue-tank | 65110 / 0xFE56 | 1761 |
| feilkodar (SPN/FMI) | DM1 | 65226 / 0xFECA (fleirpakke via BAM) | – |
| `vehicleSpeed` | CCVS1 | 65265 / 0xFEF1 | 84 – **[H]**: hydrostatisk beltemaskin sender truleg ikkje hjulbasert fart; kan vere proprietær. GNSS gir fart uansett. |
| køyreretning | – | – | **[H]** proprietær; GNSS gir retning når maskina køyrer |

## 5. Proprietære PB600-signal (fres, bakre ramme, skjer) [O]

Kan ikkje gjettast. Metode når vi har logg-oppsett:
1. Logg rå CAN (alle ID-ar, tidsstempel) i lyttemodus med maskina i ro, motor på.
2. Utfør **éin** funksjon om gongen med kjende steg: fresedjupn +/−, løft/senk bakre ramme, sideflytt venstre → midt → høgre,
   fres på/av, flytestilling – og noter tid og kva TCC-terminalen viser.
3. Finn ID-ar/byte som endrar seg berre med den funksjonen; samanlikn med verdien på terminalen (fresedjupna blir vist der).
4. Skriv kvar funnen definisjon inn her med merket **[O]**, ID, byte, skalering og korleis han vart stadfesta.

Det kan vere enklare å be **Kässbohrer** om grensesnittdokumentasjon: maskina har Com-Box og SNOWsat-grensesnitt, så
produsenten har truleg ei definert dataflate **[H]**. Kontakt via
[PistenBully kundeservice / kontaktpersonar](https://pistenbully.com/en/services/pistenbully-customer-service).

## 6. USB-CAN-adapter til Windows-PC-en

Krav: galvanisk isolert, **lyttemodus (listen-only)**, Windows 10/11, støtta av `python-can`, 250/500 kbit/s.

| Adapter | Isolasjon | Lyttemodus | Merknad |
|---|---|---|---|
| **PEAK PCAN-USB opto-decoupled (IPEH-002022)** | Ja, opptil 500 V [D] | `python-can`: `state=BusState.PASSIVE` [D] | D-Sub 9 (CiA 106), 5 kbit/s–1 Mbit/s, drivarar for Windows 10/11 [D]. **Tilrådd.** [PEAK](https://www.peak-system.com/products/hardware/external-pc-interfaces/pcan-usb/?&L=1), [python-can PCAN](https://python-can.readthedocs.io/en/v4.3.1/interfaces/pcan.html) |
| Kvaser Leaf Light HS v2 | Ja [D] | **Nei** i følgje databladet [D] | Utelukka på grunn av manglande lyttemodus. [Datablad](https://www.farnell.com/datasheets/1885452.pdf) |
| ELM327 / Bluetooth OBD2 | – | – | Ikkje eigna (eigaren vil heller ikkje bruke det) |

Treng i tillegg: overgang frå maskinkontakten (når han er kjend) til D-Sub 9, **utan** termineringsmotstand (bussen er
allereie terminert), og sikring på eventuell straumforsyning.

## 7. Tryggleik og reglar

- **Berre lytting.** Adapteren i lyttemodus og ingen sendekode i SNOWMAN. Lyttemodus hindrar òg at adapteren sender
  kvittering (ACK) – han er usynleg på bussen.
- Ingen ekstra termineringsmotstand; kople til med tenninga av; galvanisk isolasjon mellom maskin og PC.
- Avklar garanti/serviceavtale med Kässbohrer før fysisk tilkopling.
- CAN-loggar kan innehalde maskin- og føraråtferd → same personvernreglar som feltloggen (sjå VEGEN-VIDARE kap. 10).

## 8. Plan for SNOWMAN (når 1–3 er avklart)

Eige lag `maskindata` (ny modul) som:
1. Opnar adapteren i lyttemodus (`python-can`), og **loggar rå CAN** til fil i feltloggen (for analyse og seinare funn).
2. Dekodar standard J1939 (kap. 4) → `engineRPM`, `engineLoad`, `coolantTemperature`, `fuelLevel`, `fuelConsumption`,
   `adBlueLevel`, `operatingHours`, feilkodar (DM1).
3. Dekodar stadfesta PB600-signal (kap. 5) → `tillerDepth`, `tillerLiftPosition`, `tillerSidePosition`, `tillerRPM`,
   `tillerActive`; og berre om dei finst: `bladeLiftPosition`, `bladeTilt`, `bladeAngle`.
4. Koplar dataa til resten av SNOWMAN: **fres aktiv** avgjer preparert areal (betre enn fartsgrensa på 40 km/t),
   **målt drivstoff** erstattar estimatet i rapporten, fresedjupn/sideposisjon gir rett plassering av fresa i kartet,
   feilkodar og temperaturar i feltloggen.

## 9. Opne punkt – å finne (eigaren si liste)

| # | Punkt | Status |
|---|---|---|
| 1 | Planbuch/Schaltplan PB600 SCR 2012–2018 | Trengst chassisnummer; be Kässbohrer/forhandlar |
| 2–4 | Diagnosekontakt, plassering, kontakttype, pinout, CAN-H/CAN-L/jord | Ukjend – Planbuch eller sjå på maskina |
| 5 | Bussfart | [O] – lyttemodus 250/500 |
| 6–7 | Kva buss motor og fres ligg på | Planbuch / [O] |
| 8 | Standard J1939 PGN/SPN | Liste i kap. 4 [S] – stadfest i logg |
| 9–13 | Proprietære meldingar: fresedjupn, løft, sideposisjon, turtal/aktiv | [O] metode i kap. 5 (eller Kässbohrer) |
| 14 | Absolutte posisjonsgivarar på frontskjer | Ikkje funne i dokumentasjon – truleg nei [H] |
| 15 | USB-CAN-adapter | PEAK PCAN-USB opto-decoupled tilrådd [D] |
