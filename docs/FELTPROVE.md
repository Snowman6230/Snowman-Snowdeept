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
- [ ] SNOWMAN er oppdatert (Innst. › System › HENT SISTE VERSJON).
- [ ] Terrengmodell for området er lagt inn (Innst. › Terreng), med NN2000 stadfesta.
- [ ] Leica er sett opp til å sende **NMEA GGA** (gjerne 5 Hz) på seriellporten, og høgd i **NN2000** (ikkje ellipsoidisk).
- [ ] CPOS-brukar og mountpoint er klare (Innst. › Kart › LEICA / CPOS / NTRIP-OPPSETT).
- [ ] Mål antennehøgda over referansepunktet på maskina (bakkenivå under belta), og kor langt fram/bak og til sida antenna sit.
- [ ] Ta med snøsonde og meterstokk.

## I maskina
1. Kople til Leica (USB-RS232). Start SNOWMAN med val 1 (eller kiosk).
2. **Innst. › System › START LOGG** – eller slå på «Logg alltid».
3. Sjekk øvst til høgre: **RTK FIX**, satellittar, HDOP. Noter kor lang tid det tek frå start til RTK FIX.
4. **Innst. › Kalibrering:** antennehøgd, høgdeoffset 0, «NN2000». LAGRE KALIBRERING.
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
