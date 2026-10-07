# Feltprøve i trakkemaskina – sjekkliste

SNOWMAN by Alpindata · v1.6.21

## Før du dreg

**Utstyr (2026-10-06):** antenna som er tilgjengeleg er **Leica MNA1202 GG** (maskinantenne frå 2007, GPS + GLONASS L1/L2,
TNC-kontakt, 4,5–18 V DC frå mottakaren via kabelen). Ho er **berre ei antenne** – ho sender ingen posisjon sjølv og har ingen
hellingsmålar. Ho må koplast til ein GNSS-mottakar som gir NMEA til PC-en:
- Leica-mottakaren som høyrde til (t.d. MNS1200 / GX1200-serien) om han finst – sjekk at han tek imot RTCM frå CPOS.
- eller ein rimeleg RTK-mottakar (t.d. u-blox ZED-F9P-kort over USB). Desse gir berre 3,3 V til antenna, så det trengst ein
  **bias-tee** (straummatar) med 5–12 V mellom mottakar og antenne, og overgang TNC → SMA.
SNOWMAN er uavhengig av mottakar, så begge vegar fungerer. Hellinga blir då rekna ut (Innst. › Kalibrering › Helling: Auto).

**GeoMax Zenith35 Pro (GSM-UHF-TAG, 2018)** er òg tilgjengeleg: komplett smartantenne med mottakar (GPS, GLONASS, Galileo,
BeiDou), Bluetooth, GSM-modem, UHF-radio og Tilt&Go (hellingsmålar, opptil 15–30°). Straum 9–18 V. Kopling via **Bluetooth**:
1. Windows: Innstillingar › Bluetooth › Legg til eining › «Zenith35 …» (PIN 0000 om han spør). Deretter «Fleire
   Bluetooth-innstillingar» › fana **COM-portar** › noter **utgåande** COM-port (t.d. COM5).
   Linux: `bluetoothctl` (pair/trust), så `sudo rfcomm bind 0 <adresse>` → `/dev/rfcomm0`.
2. SNOWMAN › Innst. › Kart › LEICA / CPOS / NTRIP-OPPSETT: vel COM-porten, lagre. Start feltlogg (Innst. › System).
3. Kjem det **$GNGGA**-linjer i loggen, er alt klart. Kjem det ingenting, må NMEA GGA (5 Hz) slåast på for Bluetooth-porten
   i GeoMax sitt oppsettprogram (X-PAD) – send loggen til Alpindata.
4. RTK: CPOS via SNOWMAN (RTCM over same Bluetooth-kopling) eller via SIM-kortet i Zenith-en sjølv (set opp i X-PAD).
5. Sender Zenith-en helling i NMEA, tek SNOWMAN han i bruk automatisk; kjelda står i Innst. › Kalibrering › Helling.
Bluetooth Class II rekk om lag 10 m – nok frå taket til førarhuset. Til fast bruk i maskina er kabel tryggare.
- [ ] SNOWMAN er oppdatert (Innst. › System › HENT SISTE VERSJON).
- [ ] Terrengmodell for området er lagt inn (Innst. › Terreng), med NN2000 stadfesta.
- [ ] Leica er sett opp til å sende **NMEA GGA** (gjerne 5 Hz) på seriellporten, og høgd i **NN2000** (ikkje ellipsoidisk).
- [ ] CPOS-brukar og mountpoint er klare (Innst. › Kart › LEICA / CPOS / NTRIP-OPPSETT).
- [ ] Mål antennehøgda frå botnen av antennefestet ned til underkanten av belta, og kor langt fram/bak og til sida antenna sit.
- [ ] Ta med snøsonde og meterstokk.

## I maskina
1. Kople til Leica (USB-RS232). Start SNOWMAN med val 1 (eller kiosk).
2. **Innst. › System › START LOGG** – eller slå på «Logg alltid».
3. Sjekk øvst til høgre: **RTK FIX**, satellittar, HDOP. Noter kor lang tid det tek frå start til RTK FIX.
4. **Innst. › Kalibrering:** antennehøgd, høgdekorreksjon 0, og kva høgd mottakaren sender (Zenith: «rå GPS-høgd – Kartverket-modellen»). LAGRE KALIBRERING.
   **Helling:** la stå på «Auto». Sjå kva «Kjelde» seier – «antenne (…)» betyr at antenna sender helling, «utrekna» at ho ikkje gjer det.
   Køyr rett opp ein bakke: **stamp skal vere positiv**. Stå med høgre side ned i ein sidebakke: **krenging skal vere positiv**.
   Er forteiknet feil når kjelda er antenna, kryss av for «Snu forteikn». Noter antennemodellen (står på etiketten).
5. **Kontrollmåling på barmark:** stå på brøyta veg/parkeringsplass innanfor terrengmodellen. Innst. › Kontroll, skriv 0, LAGRE.
   Gjenta på 2–3 stader. Avviket viser om kalibreringa og terrengmodellen stemmer.
6. **Kontrollmåling i snø:** stopp der det er **flatt** (helling under 3° i Innst. › Kalibrering – i bakke blir målepunktet flytt
   mot midten av maskina), stikk snøsonda ned rett ved sida av maskina på høgd med antenna, skriv inn djupna, LAGRE. 3–5 stader.
7. Køyr ein vanleg tur med **Start prep**. Prøv kart, førar, 3D-terreng og frontrute. Noter om Surface-en hakkar.
8. Prøv HUD på mobil.
9. **STOPP LOGG** til slutt.

## Etterpå
- Last ned loggen (Innst. › System › Last ned (zip)) og send han til Alpindata saman med notata dine.
- Noter: kva fungerte, kva var tregt, kva var feil. Bilete av skjermen er gull verdt.

---

## Resultat: første feltprøve 2026-10-06 (bil, Sykkylven → Fjellsætra)

Utstyr: GeoMax Zenith35 Pro (Z35180902059) over Bluetooth (COM4, utgåande), NTRIP gpsbase.dyndns.org:2101, mountpoint TH
(basen står om lag 4 km frå heimen). SNOWMAN PC v1.6.38. Testen vart køyrd i **bil**, ikkje trakkemaskin.

**Fungerte**
- Bluetooth-sambandet heldt, også i fart (50–60 km/t) og gjennom tunnel (etter rettinga i v1.6.35).
- NTRIP tilkopla, RTCM vidaresendt til mottakaren (239 116 byte på éi økt).
- NN2000-høgd med Kartverket-geoiden rett: ellipsoidisk 416,28 m − N 45,13 m = 371,15 m.
- Spor, økter og rapport lagra automatisk; demo-økter haldne utanfor summen.
- Snødjupne vart ikkje vist utan RTK FIX («IKKJE MÅLT – KREV RTK FIX»), slik det skal vere.

**Fungerte ikkje: RTK FIX** – mottakaren stod på SBAS (GGA-kvalitet 9) heile kvelden. Truleg årsaker:
1. Zenith-en stod i **RTK Base**-modus i starten (retta til RTK Rover). Ikkje trykk «Start» på Working Mode – det startar basestasjon.
2. **RTK Quality Mode = Extra Safe RTK** – ventar lenge før FIX blir godteke.
3. Berre **GPS**-satellittar (9–12) blei følgde, sjølv om alle system skulle vere på.
4. Truleg dårleg sikt mot himmelen (innandørs/vindauge), og PC-en var tidvis utan internett (globus-ikon i Windows).
5. Mottakaren svarte `@GNSS,LANTENNA,ERROR,1*61`: Zenith-en brukar eige **@GNSS**-kommandospråk (ikkje NovAtel),
   og tolka innkomande data på Bluetooth som kommandoar medan han stod i feil modus. `INTERFACEMODE`-tipset gjeld ikkje.

**Rette Zenith-innstillingar** (nettsida 192.168.10.1 via Zenith-wifien › Settings › Sensor Settings):
Working Mode **RTK Rover** · RTK Data Source **Bluetooth** · Antenna Height to ARP **0** (SNOWMAN brukar antZ) ·
RTK Quality Mode **Normal** under testing · Satellite Settings: **GPS, GLONASS, Galileo, BeiDou** på · Save Settings.
PC-en kan ikkje vere på Zenith-wifien og internett samstundes – bruk mobilen til Zenith-sida, eller **USB-deling** frå mobilen.

### Sjekkliste til neste forsøk (dagslys, open himmel)
1. Zenith-en **ute** med fri sikt rundt (biltak/stolpe). Bluetooth rekk 10–20 m.
2. Kontroller innstillingane over (Rover, Bluetooth, Normal, alle fire satellittsystem).
3. PC-en på internett (ikkje Zenith-wifien).
4. SNOWMAN › NTRIP-sida (v1.6.39 eller nyare): NTRIP **TILKOPLA**, «RTCM mottatt» aukar, **ingen** `@GNSS…ERROR`.
   Les **«Vurdering»**: «OK: gyldige RTCM-korreksjonar» betyr at basen er i orden. Noter meldingstypar, satellittsystem og
   avstand til basen. Står det FEIL, ligg problemet i basen/mountpointet, ikkje i Zenith-en.
5. Vent 3–5 min → FLOAT → **FIX**. Noter tida.
6. **Står han framleis på SBAS:** set RTK Data Source = **GSM/GPRS** og legg same NTRIP-konto inn i Zenith-en sjølv (eige SIM).
   - FIX då → basen og kontoen er i orden; feilen er at Zenith-en ikkje tek imot RTCM over Bluetooth. SNOWMAN berre les posisjon.
   - Ikkje FIX → feilen ligg i basen eller mountpointen TH.
7. Ved FIX: kontrollmåling på barmark (venta 0,00 m) – antennehøgd = målt frå antennefestet (ARP) til underkanten av belta, høgdekorreksjon 0, «rå GPS-høgd – Kartverket-modellen».

### Notert til v1.6.39
- ~~Fartsgrense for preparering~~ – gjort i v1.6.43 (25 km/t).
  prep-tid eller trasédekning. Økter under 50 m køyring utan areal. (Biltesten gav 93,9 daa «preparert».)
- ~~Retta tipstekst på NTRIP-sida~~ – gjort i v1.6.39, saman med kontroll av RTCM-korreksjonane.

### Antenne til seriepakke (v2.0) – vurdering 2026-10-06
Zenith35 Pro er god nok til RTK FIX; problemet i kveld var oppsett, ikkje antenne. Tilråding til seriepakke:
u-blox ZED-F9P / ZED-X20P (t.d. ArduSimple simpleRTK3B/4) med **to antenner** (retning ved stillstand), fleirbandsantenne
på hyttetaket med jordplan ≥ 15 cm. Septentrio mosaic-X5 som robust mellomval; Leica/Trimble/GeoMax framleis støtta.
