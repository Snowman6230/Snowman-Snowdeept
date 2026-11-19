# GNSS-oppsett: UM981-02 (maskin) og UM980 (base)

Full steg-for-steg-rettleiing med avkryssing: [GNSS-OPPSETT-UM981-UM980.docx](GNSS-OPPSETT-UM981-UM980.docx).
Her er kortversjonen.

Kort: UM981-02 (gnss.store ELT0263-981.02) i maskina, UM980 (ELT0223) som base. Antenne L1/L2/L5 (TNC), kabel TNC–SMA.
Oppsettet blir gjort éin gong per kort i Unicore UPrecise og lagra med `SAVECONFIG`. SNOWMAN sender aldri noko til
mottakaren.

## Reglar
- Antennekabel på før USB. Ikkje kortslutt antennekontakten. Ikkje kortet på metall. SMA med fingrane.
- Ikkje USB-straum og 5 V-omformar samstundes.
- UPrecise og SNOWMAN kan ikkje ha COM-porten open samstundes.
- Éin kommando om gongen, Enter, vent på `$command,…,response: OK*xx`.
- Utan portnamn gjeld kommandoen porten ein er kopla til. Ved ERROR: prøv med portnamn, t.d. `RTCM1074 COM1 1`.

## Maskin – UM981-02
Kortet stivt fast og flatt. Aksemerket på UM981-modulen: **Y framover**, X mot høgre (IMU).
```
UNLOG
MODE ROVER
RTCM1074 1
RTCM1084 1
RTCM1094 1
RTCM1124 1
RTCM1019 10
RTCM1020 10
RTCM1042 10
RTCM1046 10
GPGGA 1
INSPVAXA 1
SAVECONFIG
```
SNOWMAN: same COM-port og baud (venta 115200), «Kvar blir RTK rekna?» = I SNOWMAN.

### IMU-helling (v1.6.117)
- Kort som alt er sette opp: `INSPVAXA 1` og `SAVECONFIG` i UPrecise (SNOWMAN lukka). Data Stream viser då
  `#INSPVAXA…` kvart sekund.
- SNOWMAN: Innst. › Antenne og helling › Helling › Hellingskorreksjon:
  - **IMU på** (tilrådd): hellinga frå IMU-en i UM981; når IMU-en ikkje er klar, reknar SNOWMAN sjølv.
  - **IMU av**: SNOWMAN reknar hellinga frå GPS-høgda og terrengmodellen.
  - **Av**: ingen hellingskorreksjon.
- Sjekk at kortet sender: lukk SNOWMAN og UPrecise og køyr `pc/SJEKK-IMU.bat` (éi linje i sekundet med
  tal på meldingar og hellinga frå IMU-en).
- INSPVAXA blir berre brukt med rett CRC og når INS-en har retta seg inn (ikkje INS_INACTIVE/INS_ALIGNING).
  Kursen frå INS-en blir brukt berre ved INS_SOLUTION_GOOD.
- Kontroll: rett opp ein bakke → fram/bak +. Høgre side ned → side +.
- Førarskjermen (v1.6.118): «HELLING · IMU» nede til venstre med fram/bak og side i grader og ein liten maskinfigur
  bakfrå som hallar med sidehellinga. Slå av/på: Innst. › Antenne og helling › Helling › «Vis hellinga på førarskjermen».

## Base – UM980
```
UNLOG
CONFIG UNDULATION 0.0
MODE BASE <breidd> <lengd> <ellipsoidehøgd>
RTCM1006 10
RTCM1033 10
RTCM1074 1
RTCM1084 1
RTCM1094 1
RTCM1124 1
RTCM1019 10
RTCM1020 10
RTCM1042 10
RTCM1046 10
SAVECONFIG
```
- Høgda skal vere **ellipsoidehøgd** (EUREF89), ikkje NN2000. RTCM 1006 sender jordsentrerte koordinatar.
  Utan `CONFIG UNDULATION 0.0` les kortet høgda som høgd over sin eigen globale geoide (feil med desimeter).
  SNOWMAN gjer høgda om til NN2000 med HREF2018B (sjå TERRAIN-ENGINE.md).
- Mål punktet med R12i mot TH/CPOS. Mellombels: `MODE BASE TIME 600` i staden for linje 2–3 (berre 1–2 m absolutt).
- Kontroll: GGA-kvalitet 7 = basemodus.
- SNOWMAN Base: kontorsida › Mountpoints › Nytt, kjelde «Mottakar på USB / COM-port».
