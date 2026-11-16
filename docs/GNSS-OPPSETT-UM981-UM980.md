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
Kortet stivt fast, X-pila framover (IMU).
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
SAVECONFIG
```
SNOWMAN: same COM-port og baud (venta 115200), «Kvar blir RTK rekna?» = I SNOWMAN.

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
