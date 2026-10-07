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
| Bratt terreng | 3 m høg antenne og 10° helling flyttar punktet ca. 0,5 m sidevegs → nokre cm høgdefeil i bratte bakkar | **Løyst i v1.6.31:** hellingskorreksjon frå antenna (om ho har hellingsmålar) eller utrekna frå GNSS + terrengmodell. Ein eigen IMU blir berre aktuelt for rygging. |
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

**Krav frå eigaren:** vel den **beste og billigaste** løysinga når dette blir innført. Serverprogrammet blir laga slik at det
køyrer likt på NAS, kontor-PC og leigd server, så valet kan takast seinare. Alternativ som skal samanliknast då
(prisar må sjekkast på det tidspunktet):
- **NAS på anlegget** (Synology/QNAP med Container Manager/Docker) – ingen månadskostnad, står alltid på. Maskinene når han
  via **Tailscale** (gratis for små oppsett, ingen opne portar). Truleg best for Fjellsætra om NAS-en kan køyre program.
- **Kontor-PC på anlegget** som server – ingen månadskostnad, men må stå på heile natta og vere nåbar utanfrå (fast adresse
  eller tunnel).
- **Liten leigd server på nett** (VPS) – låg månadskostnad (Hetzner ca. 6,50 €/mnd i august 2026), alltid på, enkel å nå frå
  alle maskiner. Éin server kan dekkje alle kundane til Alpindata – truleg best ved sal til andre anlegg.
- **Ein av maskin-PC-ane som server** – ingen ekstra maskin, men berre tilgjengeleg når den maskina køyrer. Truleg ikkje godt nok.

## 8. 3D: trakka område, bakgrunnskart og større område (testa, ikkje bestemt)

Eigaren ønskte å kunne «vri og vende» på trakka område i 3D etter preparering, med bakgrunnskart. Det vart **testa i ei
eiga testkopi 2026-10-07 (mot v1.6.44)** og lagt til side etter ønske frå eigaren: *ikkje gjer endringar no, men ta vare
på det som mogleg framtidig versjon.* Prototypen ligg i `docs/prototypar/3d-trakka-og-kart.py`.

| Funksjon | Testresultat | Før det kan takast i bruk |
|---|---|---|
| Trakka område frå Historikk i 3D | Fungerte. Låg nøyaktig der det skal (kontrollert mot ein «veg» i testkartet, same som 2D). Oppdatering 4–7 ms. | Mjukare kantar (i dag 1 m ruter), skjule når ein trykkjer SKJUL. |
| Bakgrunnskart drapert på 3D-terrenget | Fungerte med lokale kartfliser (data/tiles). | Prøve Kartverket-kartet på PC-en (kan bli stoppa av nettlesaren, CORS). Om det blir stoppa: SNOWMAN hentar og lagrar flisene sjølv – gir òg kart utan nett. |
| Større 3D-område | I dag 300 × 300 m, 1 m rute. Opptil ca. 800 × 800 m, 2 m rute, er lett å hente (0,9 MB, under 0,1 s). | Måle biletfrekvens på Surface-en (testmaskina hadde ikkje skjermkort). Grovare terreng og lågare teksturoppløysing. |

Ope spørsmål til eigaren: høgdekurver oppå kartet i 3D – svakare (forslag), som no, eller ingen når kartet er på.

## 9. Skjermkorttest per maskin (planlagt v1.9/v2.0)

Bestemt av eigaren 2026-10-07. Eit **automatisk vern** finst frå v1.6.46: dei første 10 s i 3D blir biletfarten målt, og
3D-detalj blir sett eitt steg ned (HØG → NORMAL → AV) om skjermkortet ikkje klarer ca. 15 bilete i sekundet.

Den fulle testen kjem saman med installasjonsrettleiinga, når SNOWMAN skal på mange ulike maskiner:
- Eigen test under Innst. › System (ca. 30 s, maskina i ro) som prøver detaljnivå (høg/normal/av), skjermoppløysing
  (1,5 × / 2 ×) og storleiken på 3D-området (300 m / 800 m, sjå kap. 8).
- Vel det beste oppsettet som held flyt (mål: minst 25 bilete i sekundet i frontrute), og lagrar det per maskin.
- Resultatet blir vist (skjermkort, bilete i sekundet per nivå) og kan sendast med i feltloggen/support.
- Grunnlag for å kunne slå på større 3D-område og bakgrunnskart i 3D (kap. 8) berre der skjermkortet taklar det.

## Vegplan (bestemt av eigaren 2026-10-06)

| Versjon | Innhald |
|---|---|
| **v1.6.x** | Feltprøve med Leica i maskina og rettingar etter ho. |
| **v1.7** | Anleggspakke, fleire terrengfiler på ein gong, LAS/LAZ/XYZ, trasear og hindringar i 3D/frontrute, rettleiingslinjer. |
| **v1.8** | Deling mellom maskiner (snødjupne siste 12 t, felles preparert areal) og utsending av anleggsdata frå server (kap. 6). |
| **v1.9** | Presisjon og klar for sal: maskingeometri (snødjupne ved fres og skjer, IMU), lisens og aktivering per maskin, driftsportal for driftsleiar (kart over flåten, rapportar, historikk, drivstoff, trasear, beskjedar), snøvolum mot målflate, skjermkorttest per maskin (kap. 9). |
| **v2.0** | Første salsversjon til andre anlegg: installasjonsrettleiing, brukarmanual, support. |
| Moglege (ikkje plasserte) | 3D: trakka område, bakgrunnskart og større område (kap. 8) – testa 2026-10-07, ventar på avgjerd. |
| Seinare | CAN-bus (drivstoff, motordata, vinsj – ulikt for PistenBully og Prinoth), LiDAR for snødjupne framfor maskina. |

Maskingeometrien blir flytt fram til v1.7 om feltprøva viser at målinga ved antenna er for upresis.

## 7. Anna

- LAS/LAZ-import (punktsky) om terrengdata kjem i det formatet.
- Målflate og snøflate (kor mykje snø som skal flyttast, snøvolum).
