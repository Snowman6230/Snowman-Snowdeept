# Vegen vidare – moglege framtidige løysingar

SNOWMAN by Alpindata · Oppdatert 2026-10-05

Idear og analysar som er vurderte, men ikkje bestemte. Eigaren avgjer rekkjefølgja.

---

## 1. Maskingeometri: snødjupne ved fres og skjer

**Status:** analysert 2026-10-05, utsett av eigaren.

GNSS-antenna (midt på taket mellom førar og passasjer, om ho ikkje er i vegen for vinsjen) gir posisjon og høgd for eitt punkt.
Med måla til maskina og køyreretninga kan SNOWMAN rekne ut kvar fres og skjer er – utan eigne følarar.

```
          skjer          antenne (tak)            fres
            |<---- 3,4 m ---->|<------ 4,1 m ------>|
   ═════════╪═════════════════╪═════════════════════╪═══
                        (belte på snøen)
```

**Utan ekstra følarar:**

| | Korleis | Kor sikkert |
|---|---|---|
| Kvar fres og skjer er | Antenneposisjon + mål + køyreretning frå GNSS | God når maskina køyrer framover |
| Snødjupne ved fresen | Maskina står på snøoverflata; høgda under belta blir flytt bakover til fresen og samanlikna med terrenget der | God – blir den målte snødjupna |
| Sporet på kartet | Teikna der fresen faktisk gjekk, med rett breidd | God |
| Snø framfor skjeret | Estimat frå målingar i nærleiken (som «Framfor» i dag), rekna der skjeret er | Estimat, ikkje måling |

**Krev ekstra utstyr:**

| | Kvifor | Løysing |
|---|---|---|
| Rygging | GNSS gir retninga maskina flyttar seg, ikkje kva veg ho peikar | To GNSS-antenner (Leica har), hellings-/retningsfølar (IMU), eller gir-signal frå maskina |
| Bratt terreng | 3 m høg antenne og 10° helling flyttar punktet ca. 0,5 m sidevegs → nokre cm høgdefeil i bratte bakkar | IMU (rimeleg, USB) |
| Kor djupt skjeret skjer | Skjeret blir styrt med hydraulikk – GNSS ser det ikkje | Følar på skjer/hydraulikk |

**Mål som må takast i maskina:** høgd frå underkant belte til antenna; avstand frå antenna fram til skjerkanten; avstand bak til
midten av fresen og til enden av finisheren (og sidevegs, om antenna ikkje sit midt).

**Plan når det blir aktuelt:**
1. Maskingeometri i Innst. › Kalibrering (antenne, skjer, fres). Snødjupne og spor ved fresen, eige estimat ved skjeret.
   Ved rygging: hald opp med å registrere i staden for å teikne på feil stad.
2. IMU for helling (bratt terreng) og retning (rygging).
3. To antenner (retning også i ro og ved rygging).
4. Følar for skjerhøgd.

## 2. Anleggspakke

Terrengmodellar, kontrollpunkt, kartkjelder og innstillingar i éi fil, som blir lasta inn på neste maskin eller hos ny kunde.
Nødvendig før sal til andre anlegg.

## 3. Opplasting av fleire terrengfiler samstundes

Kartverket leverer ofte fleire GeoTIFF-ruter («Som kildedata»). **v1.6.28:** store filer blir klipte til eit utsnitt rundt
anlegget, éi fil om gongen (kvar fil blir eit lag). Står att: velje alle filene på ein gong og slå dei saman til eitt lag.

## 4. Trasear og anleggsobjekt

**Trasear er laga i v1.6.23** (teikne, omriss frå terrengmodell, prosent preparert, varsel ved kant og i forbodne område).
Uprepart areal på kartet og måldjupne per trasé (snødjupnetal og HUD) kom i v1.6.25. Hindringar (hydrantar, snøkanonar,
master, steinar …) med varsel og nedteljing på skjerm og HUD kom i v1.6.30. Står att: trasear, uprepart areal og hindringar
i 3D-terreng og frontrute, og rettleiingslinjer framfor skjeret. Sjå `docs/TERRAIN-ENGINE.md` kap. 6.

Moglege utvidingar: teikne traseen ved å køyre rundt han med maskina, og importere omriss frå GIS (GeoJSON/SOSI/DXF).

## 5. Drivstoff automatisk

Drivstoff blir no registrert for hand (v1.6.24, full tank-metoden). Seinare kan forbruket lesast automatisk:
- **CAN-bus / J1939** frå motoren (liter per time, timeteljar, tomgang) – krev CAN-adapter (USB) og tilgang til maskina sitt
  CAN-nett. Mest presist, men ulikt mellom PistenBully og Prinoth.
- **Straummålar på drivstoffleidninga** – produsentuavhengig, men krev montering.
- **Tal frå driftssystemet til maskina** (t.d. eksport frå produsenten) – avheng av leverandøren.

Rapporten kan òg få ei utskriftsvennleg side (PDF) i tillegg til CSV.

## 6. Fleire maskiner

To eller fleire trakkemaskiner ser kvarandre sine spor og snødjupner. Krev nett mellom maskinene (fungerer offline, synkroniserer
når det er dekning).

## 7. Anna

- LAS/LAZ-import (punktsky) om terrengdata kjem i det formatet.
- Målflate og snøflate (kor mykje snø som skal flyttast, snøvolum).
