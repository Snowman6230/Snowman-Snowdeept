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

## 10. Førarar, innlogging, personvern og oppsummering (planlagt v1.9.1 eller v2.0.1)

Analysert 2026-10-07. Eigaren bestemte å leggje dette i ein seinare versjon – mest aktuelt som oppfølgingsversjon
**v1.9.1 eller v2.0.1**, etter hovudversjonen.

**Førarinnlogging og roller**
- Startskjerm med store namneknappar; føraren trykkjer på namnet sitt eller skriv inn eit nytt, og skriv PIN.
  Standard førar-PIN første gong er 1234, og han **må** endrast ved første innlogging. «Byt førar» midt i vakta.
  Førarnamnet blir vist øvst og på HUD.
- Roller: **førar** (prep, visingar, HUD, drivstoff, eigne økter/rapportar) og **administrator** (kalibrering, terreng,
  trasear, NTRIP, kiosk, førarar, nullstille PIN, slette loggar, alle rapportar). Kiosk-PIN går inn i administratortilgangen.
- PIN-kodar blir lagra **hasha** berre på PC-en (data/), aldri i repoet.
- **Avgjerd/tilråding:** administrator-PIN skal **ikkje** stå i koden (repoet er offentleg, og alle kundar ville fått same
  kode). Han blir laga ved første oppstart på kvar maskin; nullstilling krev ei eiga fil lagt inn lokalt på PC-en.
- **Avgjerd (eigaren 2026-10-07):** begge delar – førarar kan leggje seg til sjølv på startskjermen (med 1234 som må
  endrast), og administrator kan leggje til, endre og fjerne førarar.

**Førar knytt til økter, loggar og rapportar**
- Kvar økt, feltlogg og drivstoffylling får førarnamn. Rapport kan filtrerast per førar og per maskin.
- Seinare (v1.8-serveren): førarlista blir delt mellom maskinene.

**Personvern** (ikkje juridisk råd – sjekk før sal)
- Posisjonslogg knytt til namngitt tilsett er personopplysningar og ofte eit kontrolltiltak etter arbeidsmiljølova kap. 9:
  klart formål (dokumentasjon av preparering/sikkerheit), drøfting med tillitsvalde, informasjon til førarane på førehand,
  og slettefrist.
- Innstillingar: slettefrist for namn i loggar (t.d. 90 dagar) og modus utan namn for anlegg som ikkje vil ha det.

**Oppsummering av preparering** (per økt, døgn eller førar, kan lagrast som PDF)
- Kart: trakka område i fresbreidd (finst frå v1.6.43), farga etter tid eller snødjupne, med trasear og prosent preparert.
- Nøkkeltal: prep-tid, km, unikt areal (daa), transport-km, snødjupne snitt/minst; per trasé: prosent, sist preparert,
  snødjupne mot måldjupne.
- Drivstoff per økt og per daa – **estimert** frå fyllingar og timar (l/t), tydeleg merka. Målt forbruk krev CAN-bus (seinare).
- Førar og maskin.

**Feltlogg-lista** – A–D er laga i v1.6.51 (utan førarnamn); førarnamn på kvar logg kjem med førarinnlogginga
- A: kompakte linjer (`07.10 21:30 · førar · 1,2 MB ⬇`), B: samanfalda liste («Loggar: 23 stk · 145 MB ▸»), C: gruppert
  per dag med nedlasting av heile dagen, D: skjul og slett nesten tomme loggar (< ca. 10 kB) etter 7 dagar.
- Moglegheit: automatisk opprydding (behald 30 dagar / maks 500 MB).

## 11. Meir i feltloggen (arkivert 2026-10-07)

Punkt 1–6 vart laga i v1.6.52 (snødjupnestatus, korreksjonsalder/base, endra innstillingar, programfeil, handlingar,
oppstartsblokk). Desse står att til seinare:
- Terreng: inn i/ut av terrenglag, byte av lag.
- Nett: internett borte/tilbake, feil ved eksport av rapportar.
- Klokke: skilnad mellom PC-klokka og GNSS-tida.
- Yting kvart minutt: minne og CPU i tenesta, biletfart i 3D, ledig diskplass.
- Kan vente: HUD tilkopla/fråkopla, batteri/straum på Surface-en.

## 12. Maskindata frå PistenBully 600 via CAN/J1939 (forundersøking 2026-10-08, ikkje plassert)

Full dokumentasjon: [`PB600-CAN.md`](PB600-CAN.md). Ingen kode før punkta under er avklarte.

**Kvar vi står**
- Maskina er ein PB600 med AdBlue, **truleg frå ca. 2020** (eigaren). Då er ho truleg av generasjonen med
  **Cummins X12 / Stage V** og iTerminal (lansert oktober 2018), ikkje Mercedes OM 460-generasjonen. Må stadfestast.
- SNOWMAN skal **berre lytte** på CAN (lyttemodus, ingen sendekode). Galvanisk isolert USB-CAN til Windows-PC-en.
- Tilrådd adapter: **PEAK PCAN-USB opto-decoupled (IPEH-002022)**. Ikkje ELM327. Kvaser Leaf Light HS v2 er utelukka
  (manglar lyttemodus).
- Alt blir merkt **[D]** dokumentert / **[S]** standard J1939 / **[O]** observert i logg / **[H]** hypotese / **[E]** eigaren.
  Pinout, CAN-ID-ar og signal blir aldri gjetta.

**Truleg tilgjengeleg utan ekstra sensorar** (standard J1939 – må stadfestast i logg): motorturtal, last/moment,
kjølevasstemperatur, oljetrykk, driftstimar, forbruk (l/t), drivstoffnivå, AdBlue-nivå, feilkodar (DM1), og truleg
data frå partikkelfilteret. Fres-, ramme- og skjerdata er proprietære: må finnast i logg eller fåast frå Kässbohrer.
Frontskjeret har truleg ikkje absolutte posisjonsgivarar.

**Neste steg (eigaren)**
1. Sjå på maskina: Cummins eller Mercedes på motoren, iTerminal eller eldre skjerm, chassisnummer (WKU) og byggjeår.
2. Be Kässbohrer/forhandlar om Planbuch/Schaltplan og diagnosekontakt for det chassisnummeret, og spør om dei har
   eit grensesnitt for maskindata (dei leverer SNOWsat).
3. Avklar garanti/serviceavtale før fysisk tilkopling.
4. Skaff adapteren og ta første CAN-logg i lyttemodus (metoden i PB600-CAN.md kap. 5).

**Når det er avklart:** ny modul `maskindata` (rå CAN-logg i feltloggen → J1939-dekoding → stadfesta PB600-signal),
og koplingar i SNOWMAN: fres aktiv avgjer preparert areal, målt drivstoff i rapporten, fresposisjon i kartet,
feilkodar og temperaturar i feltloggen.

## 13. Vêr, snøproduksjon, snøanslag og webkamera (analyse 2026-10-08, prototype 2026-10-09)

**Prototype i v1.6.68:** Vêr-knappen med overlay for snøproduksjon (MET Locationforecast, våttemperatur, vindauge,
48 t-graf, dag for dag, innstillbare grenser, offline-lagring, DEMO-merking). Skjermbilete: `prototypar/ver/`.

**Neste steg (ikkje plassert i vegplanen)**
1. **Observasjonar frå næraste stasjon (MET Frost):** prototype i v1.6.70 («MÅLT NO»). Klient-ID ligg i koden etter
   avgjerd frå eigaren (berre opne data); eige anlegg kan setje `frost_client_id` lokalt. SNOWMAN vel stasjonar etter GPS (avstand og høgdeskilnad) og lagrar valet i stadprofilen. For Fjellsætra
   (funne 2026-10-09; yr-id «5-NNNNN» svarar til MET-stasjon SNNNNNN – stadfest i Frost med klient-ID):
   - **Roaldshornet (truleg SN60190)**, ca. 1050 moh., 62,3065 N 6,8490 Ø (ca. 17 km frå Fjellsætra): temperatur og vind
     (også kast). Best for høgfjellstemperatur og vind.
   - **Fv60 Strandafjellet (truleg SN60225)**, 504 moh.: temperatur, nedbør og vind. Truleg vegvêrstasjon.
   - **Fv650 Liabygda** (id ikkje funnen): temperatur, nedbør og vind.
   - Ingen av dei viser luftfukt eller snødjupne på yr – våttemperaturen må framleis kome frå varselet.
   - github.com/metno har ikkje vêrdata. `weathericons` (MIT) er teke inn i v1.6.69 (`vendor/vaersymbol/`).
     YR-merket skal ikkje brukast i SNOWMAN (MET sine vilkår).
2. **Vegvêr frå Statens vegvesen (DATEX II, NLOD):** krev søkt brukarkonto. Berre aktuelt der Frost ikkje har stasjonen.
3. **Webkamera per anlegg:** liste i stadprofilen (namn, plassering, bilete-adresse), val etter GPS, ikon på kartet og
   bilete i eit panel. Valfritt eitt bilete i timen til dagsrapporten.
4. **Snøanslag (steg 1–4 som prototype i v1.6.72–73: Vêr › Snøkart, sjå TERRAIN-ENGINE 6c – att står snøproduksjon frå Hydrantstyring):** høgdejustert temperatur, snø/regn etter våttemperatur, nedbør × snøtettleik, smelting (graddøgn) og
   vindflytting (le/lo frå terrengmodellen). Kopla til snøflate-minnet: «venta nysnø sidan sist preparering», kalibrert
   mot RTK-målingar. Alltid merkt **ESTIMAT – vêrmodell**, aldri blanda med målt snødjupne.
5. Kopling til Snowman Hydrantstyring (produksjonsvindauge per hydrant/kanon og høgd).

## 14. AI i SNOWMAN (analyse og prototype 2026-10-09)

**Prototype i v1.6.74–75:** AI-knappen med fem råd frå lokal AI, opningstider, tale (av/på), læringslogg og nye funn – tidspunkt, snøflytting, hol i spora, kvalitet og
snøproduksjon – og kartlag på hovudkartet. Alt blir tilpassa staden automatisk etter GPS. Sjå `AI.md`.

**Vidare (ikkje plassert):**
1. «Spør SNOWMAN»: språkmodell med lese-verktøy mot SNOWMAN-tenesta (aldri styring), sterk modell over nett og
   ein mindre lokal modell utan nett. Utskiftbar modul, nøkkel lagra lokalt, berre samandrag ut.
2. Nattplan og morgonrapport som faste funksjonar (bygd på dei fem råda).
3. Røyst i førarhuset (norsk talegjenkjenning, også lokalt).
4. Fleire lærande modellar: snødjupne framfor maskina, kalibrering per maskin, drivstoff og slitasje (CAN),
   kva forhold som gir god kvalitet, produksjon mot resultat per kanon (Hydrantstyring).
5. Seinare: kamera/LiDAR for overflate og hindringar – krev mykje testing.
6. **Sentral SNOWMAN-AI (når prosjektet er modent – avgjerd frå eigaren 2026-10-09):** først lærer kvar installasjon
   lokalt. Seinare kan anlegga (etter avtale, av/på) sende anonymiserte opplæringspakker (frå v1.6.75) til ein
   sentral AI-motor som finn mønster på tvers av anlegg og foreslår forbetringar i SNOWMAN (modellparametrar,
   nye råd, nye talekommandoar). Krev: databehandlaravtale, samtykke per anlegg, sikker overføring, versjonering
   av modellar, og at oppdateringar alltid blir testa før dei blir sende ut. Lokale data og lokal drift skal
   aldri avhenge av den sentrale motoren.

## 15. RTK i SNOWMAN (avgjerd 2026-10-09, ventar)

Eigaren: «RTK skal vere i SNOWMAN». I dag reknar mottakaren RTK sjølv. SNOWMAN hentar korreksjonane (NTRIP) og les
resultatet (GGA, kvalitet 4 = FIX).

- **Mål:** SNOWMAN reknar RTK sjølv frå rådata (kode og bølgjefase) frå mottakaren og basedata frå NTRIP.
- **Mottakaruavhengig (eigaren sitt val):**
  - Rådata blir lesne som RTCM 3 MSM (1074/1084/1094/1124 o.l.), som mange mottakarar kan sende.
  - Andre format (u-blox, NovAtel, Septentrio) kan kome seinare.
- **RTK-motor:** RTKLIB, demo5-utgåva (BSD-2-lisens, kan brukast i proprietær kode med lisenstekst). Han køyrer
  lokalt og utan nett.
- **Versjon:** byggjast i `pc/v1.7`. «RTK i mottakaren» blir verande som val. Snødjupne krev framleis FIX.
- **Krav til mottakaren:** han må kunne sende rådata ut. Zenith35 Pro viser berre NMEA i oppsettet, så det må sjekkast.
- **Status:** eigaren valde først å vente til Zenith-en fungerte med dagens løysing (sjå
  `claude/felttest-zenith35-2026-10-09.md` i prosjektet).
- **Avgjerd 2026-10-09 kl. 22.32 (eigaren):** «Ikkje bruk RTK på Zenith, den skal berre sende. RTK og NTRIP skal
  kun vere i SNOWMAN.»
  - Merknad: GGA åleine er ein ferdig rekna posisjon og kan ikkje gi RTK. Mottakaren må sende **rådata**
    (kode og fase), helst som RTCM 3 MSM eller 1004/1012.
  - Spor å teste: Zenith35 Pro sender eigne rådata som RTCM 3 i «RTK Base»-modus, men berre over UHF, GSM eller
    External (kabel). Med kabel kan han truleg vere rådatakjelde for SNOWMAN.
  - Alternativ mottakar: u-blox ZED-F9P.

## Vegplan (bestemt av eigaren 2026-10-06)

| Versjon | Innhald |
|---|---|
| **v1.6.x** | Feltprøve med Leica i maskina og rettingar etter ho. |
| **v1.7** | Anleggspakke, fleire terrengfiler på ein gong, LAS/LAZ/XYZ, trasear og hindringar i 3D/frontrute, rettleiingslinjer. |
| **v1.8** | Deling mellom maskiner (snødjupne siste 12 t, felles preparert areal) og utsending av anleggsdata frå server (kap. 6). |
| **v1.9** | Presisjon og klar for sal: maskingeometri (snødjupne ved fres og skjer, IMU), lisens og aktivering per maskin, driftsportal for driftsleiar (kart over flåten, rapportar, historikk, drivstoff, trasear, beskjedar), snøvolum mot målflate, skjermkorttest per maskin (kap. 9), førarinnlogging med roller, førar på økter/loggar/rapportar, personvern-innstillingar, oppsummering med kart og PDF, kompakt loggliste (kap. 10 – som v1.9.1 eller v2.0.1). |
| **v2.0** | Første salsversjon til andre anlegg: installasjonsrettleiing, brukarmanual, support. |
| Moglege (ikkje plasserte) | 3D: trakka område, bakgrunnskart og større område (kap. 8) – testa 2026-10-07, ventar på avgjerd. |
| Seinare | CAN-bus (drivstoff, motordata, vinsj – ulikt for PistenBully og Prinoth) – forundersøking for PB600 i kap. 12 og `PB600-CAN.md`. LiDAR for snødjupne framfor maskina. |

Maskingeometrien blir flytt fram til v1.7 om feltprøva viser at målinga ved antenna er for upresis.

## 7. Anna

- LAS/LAZ-import (punktsky) om terrengdata kjem i det formatet.
- Målflate og snøflate (kor mykje snø som skal flyttast, snøvolum).
