# Kioskmodus og autostart – spesifikasjon

SNOWMAN by Alpindata · Analyse 2026-10-05 · Status: **ferdig** (v1.6.17–1.6.19) – Windows-delen må testast på ekte PC

I trakkemaskina skal SNOWMAN berre vere der når PC-en startar – utan terminal, meny eller val. Føraren skal likevel
kunne gå ut til vanleg skjerm og tilbake til kiosk.

---

## 1. Ønske frå eigaren

| Behov | Løysing |
|---|---|
| Startar av seg sjølv | SNOWMAN blir lagt i oppstarten til brukaren på PC-en |
| Kioskmodus | Berre SNOWMAN på skjermen – ingen oppgåvelinje, ingen nettlesarmeny |
| Ut av kiosk | Knapp **«Gå til vanleg skjerm»** → SNOWMAN i vanleg vindauge, skrivebordet tilgjengeleg |
| Tilbake til kiosk | Knapp **«Kioskmodus»** i vanleg vindauge |
| Val ved installasjon | **Kontor-PC** (startast manuelt) eller **Maskin-PC** (kiosk + autostart) |
| PIN (valfri) | PIN-kode for å gå ut av kiosk. Av ved levering, kan slåast på per anlegg |

## 2. Tekniske val

**Autostart (utan administratorrettar):**
- Windows: snarveg i brukaren si Oppstart-mappe, utan svart konsollvindauge.
- Linux: `~/.config/autostart/snowman.desktop` (GNOME, KDE, XFCE …) og `exec-once` i Hyprland-oppsettet (Omarchy).

**Kiosk og byte mellom modusane:**
- Kiosk = nettlesaren i `--kiosk` (Edge på Windows, Chromium/Chrome på Linux).
- Byte gjer oppstartsprogrammet (`start_snowman.py`): lukkar det eine vindauget, **ventar til det er heilt lukka**, opnar det andre.
- Eigen nettlesarprofil for kiosk og for vanleg vindauge, så det nye vindauget alltid startar som eigen prosess (i v1.6.10 kom ikkje
  Edge-vindauget opp att fordi den gamle prosessen framleis heldt profilen).
- **Førkrav:** innstillingane i førarskjermen (perspektiv, maskinmål, kartkjelde osv.) ligg i SNOWMAN-tenesta, ikkje i nettlesaren.
  Då er alt likt same kva vindauge/profil som er ope. Trengst òg til anleggspakka.

**Vakthund:** I kioskmodus blir vindauget opna att om det blir lukka (t.d. Alt + F4 ved eit uhell), og tenesta starta att om ho krasjar.

## 3. Driftstryggleik i maskina

- **Ingen dvale/skjermsparar** på Maskin-PC (Windows: `powercfg`; Linux: hypridle/xset).
- **Straumbrot:** PC-en blir ofte kutta når maskina blir slått av. Økta blir lagra kvart 5. sekund (før: kvart 30. punkt), og filer blir
  skrivne trygt (først til mellombels fil, så bytt ut), så ei fil aldri blir halvskriven.
- **Innst. › System:** «Start automatisk ved oppstart», «Start i kioskmodus», «PIN for å gå ut av kiosk», «Oppdater SNOWMAN».

## 4. Ikkje tilrådd

- **Windows Assigned Access (innebygd kiosk):** låser PC-en så hardt at ein ikkje kjem ut til vanleg skjerm.
- **Automatisk innlogging blir ikkje sett opp automatisk.** Det krev lagra passord eller brukar utan passord – eit tryggleiksval
  eigaren tek sjølv. Rettleiing blir laga.

## 5. Rekkjefølgje

| Steg | Innhald | Status |
|---|---|---|
| 1 | Førarinnstillingane flytta til tenesta (`data/ui-config.json`) | v1.6.17 |
| 2 | Kioskmodus med byte begge vegar, valfri PIN, vakthund | v1.6.18 |
| 3 | Installasjon: Kontor-PC / Maskin-PC, autostart, ingen dvale (Windows og Linux) | v1.6.19 |
| 4 | Innst. › System, oppdatering frå skjermen, tryggare lagring | v1.6.19 |

Windows-delen av steg 3 kan berre testast fullt ut på ein ekte Windows-PC.

## 6. Rettleiing: automatisk innlogging (valfritt)

Autostart startar SNOWMAN når brukaren loggar inn. For at alt skal starte utan at nokon rører PC-en, må PC-en logge inn av seg
sjølv. Det er eit tryggleiksval: alle som slår på PC-en, kjem inn. Bruk helst ein eigen brukar berre for SNOWMAN på Maskin-PC-en.

**Windows 10/11**
1. Innstillingar › Kontoar › Påloggingsalternativ: slå av «Krev Windows Hello-pålogging for Microsoft-kontoar» (Windows 11).
2. Trykk Windows-tasten + R, skriv `netplwiz` og trykk Enter.
3. Fjern haken ved «Brukarar må skrive inn brukarnamn og passord …», trykk OK og skriv passordet to gonger.
4. Start PC-en på nytt for å teste.

**Linux**
- GNOME: Innstillingar › Brukarar › Automatisk innlogging.
- KDE: Systeminnstillingar › Innloggingsskjerm (SDDM) › Behaviour › Automatisk innlogging.
- Omarchy/Hyprland: avheng av oppsettet (krypteringspassord ved oppstart kan ikkje hoppast over). Sjå Omarchy-dokumentasjonen.
