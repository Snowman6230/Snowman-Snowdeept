# Feltprøve i trakkemaskina – sjekkliste

SNOWMAN by Alpindata · v1.6.21

## Før du dreg
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
5. **Kontrollmåling på barmark:** stå på brøyta veg/parkeringsplass innanfor terrengmodellen. Innst. › Kontroll, skriv 0, LAGRE.
   Gjenta på 2–3 stader. Avviket viser om kalibreringa og terrengmodellen stemmer.
6. **Kontrollmåling i snø:** stopp, stikk snøsonda ned rett under antenna, skriv inn djupna, LAGRE. 3–5 stader.
7. Køyr ein vanleg tur med **Start prep**. Prøv kart, førar, 3D-terreng og frontrute. Noter om Surface-en hakkar.
8. Prøv HUD på mobil.
9. **STOPP LOGG** til slutt.

## Etterpå
- Last ned loggen (Innst. › System › Last ned (zip)) og send han til Alpindata saman med notata dine.
- Noter: kva fungerte, kva var tregt, kva var feil. Bilete av skjermen er gull verdt.
