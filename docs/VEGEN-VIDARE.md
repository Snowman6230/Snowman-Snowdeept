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

## 6. Fleire maskiner deler snødjupne (planlagt v1.8)

**Status:** bestemt av eigaren 2026-10-06, kjem etter anleggspakka (v1.7).

To eller fleire maskiner med SNOWMAN deler målingane sine. Kjem ei maskin over eit område ei anna maskin har preparert dei
**siste 12 timane**, veit systemet snødjupna der, og prosent preparert / uprepart areal gjeld heile flåten.

**Korleis:** via mobildata til ein felles SNOWMAN-server for anlegget («lagre og send vidare»). Det er dekning i heile anlegget på
Fjellsætra. Utan dekning held maskina fram som før og legg målingane i kø; dei blir sende når dekninga kjem att, og maskina hentar
det dei andre har sendt. Maskinene kan ikkje nå kvarandre direkte over mobilnettet (operatørane blokkerer innkomande trafikk),
så serveren er naudsynt. Han kan vere kontor-PC-en på anlegget eller ein liten server på nett.

**Reglar:**
- Kvar måling har posisjon, snødjupne, maskin og **GNSS-tid** (ikkje PC-klokka, som kan gå feil).
- Nyaste måling på ein stad gjeld – snø blir flytt når ein preparerer. Eigne nye målingar går alltid framfor eldre frå andre.
- Målingar eldre enn 12 timar blir ikkje viste. Alder blir vist («målt av PB 2 for 3 t sidan»).
- Berre målingar med RTK FIX frå kalibrerte maskiner blir delte. Demo og simulator blir aldri delte.
- Kvar maskin må vere kontrollmålt (Innst. › Kontroll) – ein høgdefeil på éi maskin blir elles delt med alle.
- Dei andre maskinene blir viste på kartet (posisjon, sist sett).
- Eigen nøkkel per anlegg; ingen passord i koden.

**Datamengd:** om lag eitt punkt per meter køyrt – nokre få MB per maskin per natt.

**Utsending av anleggsdata til maskinene (bestemt av eigaren 2026-10-06):** same server sender anleggspakka (v1.7) ut til alle
maskinene. Endringar blir gjorde éin stad (kontor-PC eller nettside på serveren) og når alle maskinene.
- Innhald: terrengmodellar, trasear og forbodne område, hindringar, kontrollpunkt, kartfliser for offline drift – seinare
  beskjedar og oppgåver frå driftsleiar.
- Maskinene hentar sjølve når dei har dekning; ei maskin som har vore avslått, får alt nytt ved neste oppstart.
- Trasear og hindringar blir tekne i bruk med éin gong. Nytt terreng blir **ikkje** skifta under preparering (endrar
  snødjupna): føraren får «Nytt terreng tilgjengeleg – ta i bruk», og det skjer når prep er stoppa.
- Store filer (terreng, kartfliser) helst over wifi i garasjen; små endringar over mobildata. Berre endringar blir sende.
- Versjon på anleggsdataa: kontoret ser kva versjon kvar maskin har.

**Krav frå eigaren:** vel den **beste og billigaste** løysinga når dette blir innført. Alternativ som skal samanliknast då
(prisar må sjekkast på det tidspunktet):
- **Kontor-PC på anlegget** som server – ingen månadskostnad, men må stå på heile natta og vere nåbar utanfrå (fast adresse
  eller tunnel).
- **Liten leigd server på nett** (VPS) – låg månadskostnad, alltid på, enkel å nå frå alle maskiner. Kan dele på fleire anlegg.
- **Ein av maskin-PC-ane som server** – ingen ekstra maskin, men berre tilgjengeleg når den maskina køyrer. Truleg ikkje godt nok.

## 7. Anna

- LAS/LAZ-import (punktsky) om terrengdata kjem i det formatet.
- Målflate og snøflate (kor mykje snø som skal flyttast, snøvolum).
