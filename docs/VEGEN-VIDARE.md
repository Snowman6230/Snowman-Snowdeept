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
1. Maskingeometri i Innst. › Antenne og helling (antenne, skjer, fres). Snødjupne og spor ved fresen, eige estimat ved skjeret.
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
- Kvar maskin må vere kontrollmålt (Innst. › Kontrollmåling) – ein høgdefeil på éi maskin blir elles delt med alle.
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

**Feilkodar og varsling (lagt til 2026-10-22, eigaren):** når SNOWMAN er kopla til CAN, skal han varsle om feil.
Detaljar i `PB600-CAN.md` kap. 8b.
- Aktive feilkodar frå motoren (J1939 DM1: SPN, FMI, kor mange gongar) og lampestatus (raud stopp, gul varsel,
  motorlampe). Raud stopplampe gir raudt varsel med éin gong på skjerm og HUD, anna gir gult varsel.
- Eigne grenseverdiar: kjølevatn, oljetrykk, lågt drivstoff og AdBlue, partikkelfilter som regenererer, og påminning
  om service etter driftstimar.
- Alt blir logga med tid og posisjon i feltloggen og rapporten, og går til driftsleiar (`/leiar` og serveren i v1.8).
- Avgrensingar: berre *aktive* feil (lagra feil, DM2, må etterspørjast, og SNOWMAN sender aldri). PistenBully sine
  eigne feilkodar er truleg ikkje standard J1939. Tekst og tiltak for Cummins-kodane krev feilkodelista frå Cummins.
- Maskina sin eigen skjerm er alltid primærvarslinga. SNOWMAN supplerer og dokumenterer.

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
- **Status v1.6.91:** RTK-motoren er bygd i v1.6 (`rtkmotor.py`, pyrtklib/RTKLIB) og er standard. Han er testa mot
  RTKLIB-testdata og heile vegen gjennom SNOWMAN. Det som står att, er ein ekte mottakar med rådata, og eventuelt
  ei eiga kjelde for satellittbaner i sanntid (t.d. eit NTRIP-mountpoint med 1019/1020).
- **v1.7-mappe:** krev at data, `.venv` og autostart blir flytta (SNOWMAN.bat, installer, oppstart.py). Det er eit
  eige steg.

## 16. Kontor og maskin (bestemt av eigaren 2026-10-22, avgjerder 2026-11-20 og 2026-11-22)

**Avgjerd 6 (2026-11-22) – tre program:** SNOWMAN Base på Raspberry Pi-en skal **berre** ha med satellittar og NTRIP
å gjere («ikkje noko anna som kan rote ting til»). Kontordelen blir eit eige program, **SNOWMAN Kontor**
(`kontor/v1.0`), på ein **Windows-PC** på anlegget. Maskinene når Kontor **berre på nettet på anlegget** (wifi i
garasjen) – ingen open port mot internett for Kontor. Grunnar: ei oppdatering av kontordelen starta heile Base på nytt
(maskinene mista korreksjonane), feil eller store filer i kontordelen kunne ramme casteren, og anlegg med CPOS (utan
eigen base) treng òg kontoret. *Laga 2026-11-22: Base 1.4.0, Kontor 1.0.0, SNOWMAN 1.6.137.*
Der det står «Base» om kontordelen, anleggspakka eller maskin-API-et under, gjeld det no SNOWMAN Kontor.
Avgjerd 4 (maskin-API på port 2101) er erstatta av avgjerd 6.

**Avgjerd 8 (2026-11-23) – nye namn:** Eigaren: «Kan du døype om namnet frå kontor til Snowman Office?» og «Du kan også
bytte frå SNOWMAN snødjupne til Snowman Snowdeep. Då forstår folk det også.» Dei tre programma heiter no
**SNOWMAN Snowdeep** (maskinene), **SNOWMAN Base** (Pi-en ved antenna) og **SNOWMAN Office** (kontor-PC-en). Berre namna
som blir viste er bytte; mappene (`pc/`, `base/`, `kontor/`), API-adressene, innstillingane i maskinene og `--kontor` er
uendra, elles ville oppdateringa og koplinga i maskinene gått tapt. Nedlastingane heiter SNOWMAN-Snowdeep.zip og
SNOWMAN-Office.zip (dei gamle namna ligg ved sida av som kopi). Teksten elles er framleis nynorsk; «kontoret» og
«snødjupne» som vanlege ord står som før. Under i dette kapitlet står dei gamle namna slik dei var då avgjerdene vart
tekne. *Laga 2026-11-23: Office 1.2.0, Snowdeep 1.6.142.*

**Avgjerd 7 (2026-11-23) – kontoret er SNOWMAN snødjupne i kontormodus:** Eigaren: «Snowman Kontor bør ha meir eller
mindre same funksjonar som Snowman Snødjupne … Det bør også kunne lastast inn karta som eg brukar i dag. Eg må kunne
legge inn nye kart og desse pushest ut til maskinene.» Val (eigaren):
- **Kontormodus:** Kontor startar SNOWMAN snødjupne frå `pc/` med `--kontor` (utan GNSS, NTRIP og motor) på
  http://localhost:8765/. Same kart, 3D, terrengbibliotek, trasear, hindringar og kontrollpunkt som i maskina.
  Fana **Kontor** publiserer til maskinene. Kontor-zip-en inneheld difor både `kontor/v1.0` og `pc/v1.6`.
- **Terreng i anleggspakka:** `terreng/<id>/meta.json` + `grid.npy` for aktive lag (maks 4 GB). Maskina lastar ned på
  wifi, men **føraren tek det i bruk** (knapp) når prepareringa er stoppa. Lokale lag blir slått av, ikkje sletta; dei
  tre siste terrenga blir tekne vare på.
- **Sanntid ute i bakken:** maskina sender posisjon, snødjupne, fix og «preparerer» kvart 10. s og RTK FIX-målingar.
  Wifi på anlegget først, så mobilnettet til **port 8791** (berre maskin-API, berre rolla maskin), som er den einaste
  porten som kan sendast vidare i ruteren (DuckDNS). Pakker over 50 MB blir berre henta på wifi.
*Laga 2026-11-23: Kontor 1.1.0, SNOWMAN 1.6.139.* Same dag (eigaren: «gjer 1 og 2»): kontormodus er rydda for det som
berre gjeld maskina, og alt frå kontorsida ligg under Innst. › Kontor i same layout (Kontor 1.1.2, SNOWMAN 1.6.141).
Kontorsida på 8790 er ein reserve.

**Avgjerd:** SNOWMAN skal skilje mellom **kontor** (planlegging og redigering) og **maskin** (førar). Kontoret legg inn
og plottar detaljar i kart og 3D-modell og sender oppdateringar ut til heile maskinparken. Byggjer vidare på kap. 2
(anleggspakke) og kap. 6 (server og utsending).

**Kvifor**
- Ulike oppgåver: kontoret planlegg med stor skjerm, mus og 3D; føraren skal sjå, måle og bli varsla – ikkje teikne.
- Éi sanning: anleggsdataa blir endra éin stad, ikkje ulikt på kvar maskin.
- Tryggleik: hindringar og forbodne område har éin ansvarleg, og endringar kan sporast og rullast tilbake.

**Rolledeling**

| | Kontor | Maskin |
|---|---|---|
| Teikne/redigere i 2D og 3D | Ja: trasear, hindringar, forbodne område, kontrollpunkt, rettleiingslinjer, snøkanonar, måldjupne, målflate | Nei |
| Importere | Ja: terreng (LAS/LAZ/GeoTIFF), GIS-omriss (GeoJSON/SOSI/DXF), kartfliser | Nei |
| Sjå snødjupne, spor og flåten | Heile anlegget og historikk | Eigen og delt (v1.8) |
| Melde frå | – | «Ny hindring her», merknad/bilete, sendt som **forslag** som kontoret godkjenner |
| Oppgåver og beskjedar | Sende ut | Ta imot og kvittere |
| Rapportar og drivstoff | Alle maskiner | Eigne økter |

**Presisering frå eigaren (2026-10-29):** kontordelen skal liggje i **SNOWMAN Base**. Derifrå skal kontoret kunne
sende ut kartgrenser (trasear/yttergrenser), hindringar m.m. til SNOWMAN snødjupne, og **alle innstillingar** til
dei ulike tråkkemaskinene – felles for heile flåten eller ulikt per maskin (t.d. kalibrering, fresbreidd, antenne,
NTRIP, varsel).

**Utsending til maskinparken** (reglane frå kap. 6 gjeld)
- Kontoret **publiserer** ein ny versjon av anleggspakka; serveren sender han ut. Maskinene hentar sjølve når dei har dekning.
- Trasear og hindringar blir tekne i bruk med éin gong. Nytt terreng blir ikkje bytt under preparering.
- Versjonsnummer på anleggspakka frå starten (v1.7). Kontoret ser kva versjon kvar maskin har, og kan rulle tilbake.
- Endringslogg: kven endra kva, og når.

**Teknisk**
- Eitt program, to roller – same kjerne, kart og 3D. Kontoret er ein rolle med redigeringsverktøy (administratorrolla i kap. 10).
- Kontordelen køyrer som nettside på serveren frå v1.8, så han kan brukast frå kva PC som helst på anlegget.
- Plotting i 3D: eit klikk i 3D-terrenget blir festa til terrenghøgda (krev eige arbeid).

**Plassering**
- v1.7: anleggspakke med versjonsnummer (formatet kontoret seinare redigerer).
- v1.8: publisering ut, forslag inn frå maskinene, enkel kontorside for 2D-redigering.
- v1.9: full kontordel i driftsportalen – 3D-redigering, import, oppgåver og rapportar for heile flåten.

### Analyse og avgjerder 2026-11-20 («SNOWMAN Kontor»)

**Funn:** det som mangla, var lenkja mellom kontor og maskin, ikkje teikneverktøy. Anleggspakka i Base var ei zip-fil
utan definert innhald, `pc/v1.6` hentar ingenting frå Base, og maskin-API-et fanst berre på port 8780 (som aldri
skal opnast mot internett). Trasear og hindringar for Fjellsætra er alt teikna i maskina.

**Rekkjefølgje (avgjerd):**
1. **Format for anleggspakka** – formatversjon 1, same filer som maskina alt har (`kontor/v1.0/anleggspakke.py`):
   `manifest.json` + `trasear.json`, `objekt.json`, `kontrollpunkt.json`; `terreng/` har plass i formatet.
   *Laga i Base v1.3.0, flytta til Kontor 1.0.0.*
2. **Maskina tek imot:** valfri bolk «Kopling til SNOWMAN Base» (av som standard), knappen «Hent frå Base»
   først, automatisk henting seinare. Lagrar lokalt; siste pakke gjeld om Base er borte.
   *Laga i PC v1.6.136 (2026-11-22), mot Kontor i v1.6.137 (`pc/v1.6/kontorkopling.py`):* Innst. › Trasear ›
   «Kopling til SNOWMAN Kontor», knappen «Hent frå Kontor».
   Står att: automatisk henting, administrator-PIN på av-brytaren (kap. 10 finst ikkje enno), fingeravtrykk av
   terrenget i hjarteslaget (avgjerd 2), og at kontoret ser lokale hindringar på kartet før dei er godkjende.
3. **Kartfane på kontoret i 2D (SNOWMAN Kontor):** «Hent frå maskin» (første versjon frå det som alt er teikna),
   redigere, «Publiser» (Kontor lagar pakka sjølv), forslag frå maskinene på kartet.
4. **Innstillingar til maskinene** (sjå avgjerd 3 under).
5. **3D-redigering og import** – v1.9 som før.

Kontordelen blir verande i SNOWMAN Base (avgjerda 2026-10-29) – ikkje eige program. «SNOWMAN Kontor» er namnet på
kontordelen av Base.

**Avgjerd 1 – lokal redigering når maskina er kopla til Base:**
- Trasear og forbodne område: føraren kan berre sende **forslag**.
- **Ny hindring** blir lagd inn lokalt med varsel med éin gong, merkt «lokal – ventar på kontoret», og sendt som
  forslag. Lokale hindringar ligg i eit eige lag som ein ny pakke aldri slettar.
- Godkjent → kjem med i neste pakke, og den lokale blir fjerna når pakka er komen. Avvist → føraren får beskjed med
  grunngjeving og fjernar ho sjølv. Ei hindring skal aldri forsvinne utan at føraren veit det.
- Er koplinga til Base av, kan maskina redigerast fritt (kap. 19). Brytaren krev administrator-PIN (kap. 10).

**Avgjerd 2 – terreng i anleggspakka:**
- Første versjon sender **ikkje** terreng. Maskina sender eit fingeravtrykk (sha256) av terrenglaga i hjarteslaget,
  og kontorsida åtvarar når maskinene har ulikt terreng (viktig før deling i v1.8).
- Seinare: terreng i pakka, berre lasta ned når fingeravtrykket er endra, helst over wifi. Teke i bruk når prep er
  stoppa, med kontrollmåling etterpå.

**Avgjerd 3 – innstillingar til maskinene, i tre grupper:**

| Gruppe | Døme | Korleis |
|---|---|---|
| Automatisk (påverkar ikkje målinga) | varselavstand, HUD og visning, vêrstad, opningstider, GGA-intervall | Teke i bruk med éin gong, lita melding til føraren |
| Føraren godtek (måling, areal, samband) | antennehøgd, fresbreidd, tilt, høgdemodus, NTRIP | Gammal → ny verdi, «Ta i bruk». Aldri under preparering |
| Berre ved maskina | seriell-/Bluetooth-port, kalibrering (zOff, «kalibrert»), RTK-modus | Blir aldri sende. Kontoret ser verdiane og kan be om ny kontrollmåling |

- NTRIP med automatisk angring: ingen korreksjonar innan om lag 2 min etter endring → tilbake til førre oppsett.
- Verdi per maskin går framfor felles verdi; kontorsida viser kvar verdien kjem frå.
- Maskina tek vare på førre innstillingar og kan gå tilbake med eitt trykk. Passord blir aldri viste på kontorsida.
- Før NTRIP-passord blir sende som innstillingar (eller seinast før sal): HTTPS mellom maskin og Base.

**Avgjerd 4 – maskinene når Base gjennom port 2101 (erstatta av avgjerd 6, 2026-11-22 – fjerna i Base 1.4):** maskindelen av API-et (anleggspakke, deling, forslag) svarar
òg på casterporten, så ruteren berre treng port 2101 open – same namn og port for korreksjonar og anleggsdata, som
Norman sin base (`gpsbase.dyndns.org:2101`). Kontoret er aldri tilgjengeleg på 2101. *Laga i Base v1.3.0.*
DuckDNS og port 2101 i ruteren er **ikkje** sette opp på Fjellsætra enno (2026-11-20).

**Avgjerd 5 – Base på eiga eining:** Base på ein **Raspberry Pi ved antenna** (Pi 4 bestilt 21.11), som berre køyrer
Base som systemteneste. Det er straum og nettverk der antenna skal stå. Ikkje på ein PC som blir brukt til anna.
For sal (v2.0): ferdig «Base-boks» frå Alpindata, med ein Alpindata-server på nett som val for anlegg utan
offentleg IP (Pi ved antenna lastar opp dit).

## 17. Lisens: éin lisens skal ikkje kunne brukast på fleire maskiner (analyse 2026-10-22, utsett)

**Status:** eigaren vurderer dette seinare (2026-10-22). Ingen avgjerd og ingen kode før eigaren har teke stilling til
dei tre opne punkta nedst i kapitlet.

**Spørsmål frå eigaren:** korleis unngå at eit anlegg kjøper éin lisens og brukar han på fleire maskiner?

**Viktig føresetnad – før sal:** repoet er i dag **offentleg**, og SNOWMAN er Python-kjeldekode. Då kan kven som helst
kopiere programmet og fjerne ein lisenskontroll. Før første sal (v2.0) bør:
- repoet gjerast **privat**,
- kundane få ein **ferdig bygd versjon** (t.d. PyInstaller/Nuitka), ikkje kjeldekode,
- lisenskontrollen ha ein del som ligg på Alpindata sin server, der kunden ikkje kan endre han.

Ingen lisenskontroll på kundens eigen PC er umogleg å omgå. Målet er at det skal vere **meir tungvint å jukse enn å
betale** – og at det viktigaste (deling, anleggsdata, oppdateringar, support) berre fungerer med gyldig lisens.

**Tiltak i lag (tilråding)**

| Lag | Tiltak | Kva det hindrar |
|---|---|---|
| 1. Aktivering per maskin | Lisensnøkkel blir aktivert mot Alpindata sin lisensteneste. Maskina får ei **signert lisensfil** (t.d. Ed25519) bunden til ein **maskin-ID** (PC-ID + GNSS-boksen). Signaturen kan ikkje forfalskast utan Alpindata sin private nøkkel. | Kopiering av lisensfila til ein annan PC |
| 2. Offline-frist | Maskina må sjekke inn med lisenstenesta minst kvar 30. dag (innstillbart). Utan kontakt: åtvaring, deretter avgrensa modus. | At ei deaktivert/flytta lisens held fram å virke |
| 3. Plassar på serveren (v1.8) | Anleggsserveren godtek berre så mange maskiner som lisensen gjeld for. Maskin utan gyldig lisens får ikkje anleggsdata, deling eller oppdateringar. | Fleire maskiner på same lisens i same flåte |
| 4. GNSS-boksen som «nøkkel» | Lisensen følgjer GNSS-boksen Alpindata leverer. ID-en til mottakaren (u-blox ZED-F9P har unik chip-ID) blir lagra i lisensen. Kan setjast opp ved levering slik at SNOWMAN berre les ID-en, utan å sende til mottakaren **[H] – må testast**. | Ny maskin utan å kjøpe boks og lisens |
| 5. Synleg i data | Kvar måling, økt og rapport er merkt med lisens-ID og maskin-ID. Same lisens frå to stader samstundes blir oppdaga på serveren. | Skjult dobbelbruk |
| 6. Avtale og pris | Lisensavtale med rett til kontroll. Pris per anlegg + per maskin, med rabatt for fleire maskiner – så det lønner seg å lisensiere alle. | Gjer juks lite lønnsamt |

**Flytting av lisens:** når ein PC eller GNSS-boks blir bytt, frigjer kontoret lisensen i portalen og aktiverer på ny
maskin. Avgrens til t.d. 2 flyttingar per år utan å kontakte Alpindata.

**Rettferdig og trygg handheving**
- Lisensen blir **aldri** stoppa midt i ei preparering. Åtvaring først; avgrensing tidlegast ved neste oppstart.
- **Tryggleiksfunksjonar** (posisjon, hindringsvarsel, forbodne område) blir aldri låste av lisensen.
- Avgrensa modus: kart og posisjon virkar; snødjupne, deling, rapportar og oppdateringar krev gyldig lisens.
- Demo/prøvelisens (t.d. 30 dagar) for nye kundar, tydeleg merkt.

**Ope til eigaren – avgjerast seinare**

| # | Spørsmål | Alternativ | Status |
|---|---|---|---|
| 1 | Lisensmodell | Per maskin · per anlegg med tal maskiner · abonnement per år | Ventar på eigaren |
| 2 | Lisensteneste | Alpindata sin eigen server (same som kap. 6, VPS) · ferdig teneste (t.d. Keygen, LemonSqueezy – prisar og vilkår må sjekkast) | Ventar på eigaren |
| 3 | Når repoet skal gjerast privat | Seinast før første sal (v2.0) – tilrådd tidlegare | Ventar på eigaren |

**Plassering:** lag 1, 2, 5 og 6 i v1.9 (står alt i vegplanen som «lisens og aktivering per maskin»), lag 3 når
serveren kjem i v1.8, lag 4 når GNSS-boksen er valt og testa.

## 18. SNOWMAN Base (laga 2026-10-29, v1.0)

**Avgjerd (eigaren 2026-10-29):** SNOWMAN skal ha eigen base, «SNOWMAN Base», som kan køyre på PC, server, NAS (med
operativsystem/Docker) eller Linux. Han skal innehalde alle funksjonane SNOWMAN snødjupne treng frå ein base og ein
server, vere framtidsretta, kunne køyre kontordelen, vere like enkel å oppdatere som SNOWMAN snødjupne, ta omsyn til
at endringar i Base kan påverke SNOWMAN snødjupne, og kunne foreslå forbetringar i programma – med innebygd AI.

**Laga i `base/v1.0/`** (sjå `base/v1.0/LES-MEG.md`):
- NTRIP-caster (NTRIP 1 og 2) med innlogging, kjeldetabell og GGA frå maskinene (posisjon på kartet).
- Kjelder: mottakar på USB/seriell, TCP, TCP-tenar, NTRIP-opplasting (t.d. Raspberry Pi ved antenna), relé frå
  TH/CPOS, avspeling (test). Reserve i prioritert rekkjefølgje, og tillegg (satellittbaner) inn i straumen.
- Kontroll av baseposisjonen (1005/1006) mot innmålt punkt, rådatalogg for PPP, BRDC-banefil til maskinene.
- API v1 for v1.8: hjarteslag, delte målingar (siste 12 t, berre FIX frå kalibrerte maskiner), anleggspakke med
  versjonar og tilbakerulling, forslag frå maskinene. Maskinplassar som førebuing til kap. 17 (av som standard).
- Statusside og kontorside (kart med basar og maskiner, anleggspakke, forslag, forbetringar, AI, oppdatering).
- v1.1.0: mountpoints blir lagde og endra manuelt på kontorsida (relé, USB/COM, opplasting, TCP), med
  prioritet/reserve, henting av mountpoints frå ein annan caster, og bruk med éin gong utan omstart.
- Forbetringsmotor: reglar (alltid på) + AI (av som standard: lokal Ollama eller Claude med eigen nøkkel, berre
  anonymisert samandrag). Kategoriar: SNOWMAN Base, SNOWMAN snødjupne, mottakar/antenne, drift. Eksport som
  Markdown-oppgåveliste til utviklaren. Dagstal for trendar.
- Oppdatering som i SNOWMAN snødjupne (git pull eller zip, `data/` blir aldri rørt), dagleg sjekk og valfri
  automatisk oppdatering om natta. Køyrer som systemteneste (Linux), Docker (NAS) eller .bat (Windows).
- Samspel: `/api/v1/info` med API-versjon og minste SNOWMAN-versjon. Testane køyrer casteren mot NTRIP-klienten i
  `pc/v1.6`. Brot i API-et gir ny API-versjon; v1 blir verande.

**Analyse 2026-10-31 (Base v1.1.1) – feil som skal rettast i Base v1.2:** *(retta i Base v1.2.0, 2026-10-31 – sjå
ENDRINGSLOGG. Står att frå lista: L5 reserve-relé alltid tilkopla, L6 tillegg på kontorsida)*
- **H1** Kommandoane `brukar`/`nokkel`/`mountpoint ny` verkar ikkje i Base som køyrer, og blir sletta når kontorsida
  lagrar (stadfesta). Til retta: stopp Base før slike kommandoar.
- **H2** Ingen ventetid før Base byter tilbake til eigen base → blafring mellom basar (stadfesta: 20 byte på 10 epokar).
  Saman med kap. 19 (SNOWMAN nullstiller ikkje RTK ved byte av base) gir det risiko for falsk FIX.
- **H3** `verdict()` krasjar når ingen kjelde er aktiv og eit tillegg sender baner → `/api/status` 500 (stadfesta).
- **M1** tcp-tenar: hengande tilkopling stengjer for ny (stadfesta). **M2** byte i `tick()` blir ikkje logga/talt
  (stadfesta). **M3** Windows: `SO_REUSEADDR` lèt to Base binde same port. **M4** port 2101: ingen grense per IP,
  hendingslogg utan rotasjon. **M5** oppdatering skriv over .bat-fila som køyrer. **M6** Windows: ingen autostart,
  dvale, USB-straumsparing.
- Nye funksjonar: side «Slik når maskinene Base» (IP, CGNAT-åtvaring), innebygd dynamisk DNS, «send vidare» til
  ekstern caster, åtvaring ved same stasjons-ID på eigen base og reserve.
- Tilrådd oppsett: Base på Raspberry Pi ved antenna (ZED-F9P på USB). Tilgang som Norman sin base krev offentleg IP,
  DDNS og port 2101; elles Tailscale eller vidaresending til ekstern caster.

**Base v1.2.0 (2026-10-31, eigaren):** innlogging med **brukarnamn og passord, ingen nøklar** («nøklar er lett å
miste»). Rolla ntrip (maskinene – same innlogging for NTRIP og API) og kontor (administrator). Anlegget har fiber →
tilgang som Norman sin base (DDNS + port 2101); Base held det faste namnet oppdatert (fana «Tilgang»).

**Base v1.3.0 (2026-11-20, kap. 16):** maskin-API-et på casterporten (2101) og format for anleggspakka
(formatversjon 1, kontrollert ved opplasting). Base skal stå på Raspberry Pi ved antenna.

**Base v1.4.0 (2026-11-22, kap. 16 avgjerd 6): berre satellittar og NTRIP.** Kontorsida, anleggspakke, forslag,
deling, forbetringslager og AI er flytta til SNOWMAN Kontor (`kontor/v1.0`). Maskin-API-et på 2101 er fjerna. Base har
ei lita oppsettside (`/oppsett/`: mountpoints, tilgang, brukarar, oppdatering) og viser åtvaringane om korreksjonane
på statussida. Kontor les statusen (berre lesing).

**Står att (neste steg):**
1. SNOWMAN snødjupne mot SNOWMAN Kontor: anleggspakke laga (v1.6.137), deling i v1.8.
2. ~~SNOWMAN Kontor: kartfane i 2D med «Hent frå maskin» og «Publiser», så 3D i v1.9~~ – løyst med kontormodus
   (avgjerd 7, Kontor 1.1.0): kart og 3D frå SNOWMAN snødjupne, publisering med terreng, maskinene i sanntid.
   Inkluderer utsending av innstillingar til maskinene, felles og per maskin (eigaren 2026-10-29). API v1 har i dag
   éi anleggspakke for heile flåten; innstillingar per maskin krev eit tillegg i API-et (t.d. `GET /api/v1/innstillingar`
   med maskin-ID frå hjarteslaget).
3. Baner frå BRDC-fila inn i straumen som RTCM 1019/1020 (for basemottakarar som ikkje sender baner, t.d. ZED-F9P).
4. Base kan vise SNOWMAN sin eigen FIX-status: SNOWMAN sender i dag GGA frå mottakaren til casteren. Når RTK blir
   rekna i SNOWMAN, er det SNOWMAN si løysing (frå hjarteslaget i v1.8) som viser den reelle FIX-delen.
5. Når repoet blir privat (kap. 17): tilgangsnøkkel for oppdateringa.

## 19. SNOWMAN snødjupne utan Base, reservecaster og byte av base (analyse 2026-10-29, ventar)

**Status:** analyse – ingen kode. Eigaren vil gjere SNOWMAN Base ferdig først og sjå på dette seinare.

**Avgjerd (eigaren 2026-10-29):** SNOWMAN snødjupne skal **ikkje** vere avhengig av SNOWMAN Base for å fungere. Base
er ei valfri tilknyting – ein NTRIP-caster blant fleire (TH, CPOS, rtk2go, eigen base), og eventuelt ein stad å hente
anleggsdata, innstillingar og delte målingar frå.

**Slik er det i dag (sjekka i `pc/v1.6`, v1.6.112):** ingen kode i SNOWMAN snødjupne viser til Base (ingen adresse,
ingen bruk av API-et). NTRIP-sida er ein vanleg NTRIP-klient. Base blir brukt ved å skrive adressa til Base i dei same
felta (caster, port, mountpoint, brukarnamn, passord) som i dag blir brukte mot TH.

**Reglar for det som kjem (kontordel v1.7–v1.8, deling v1.8, lisens kap. 17):**
- Alt maskina får frå Base (kartgrenser, hindringar, innstillingar), blir lagra lokalt og brukt derifrå. Er Base borte,
  gjeld det siste som kom.
- Maskina kan framleis setjast opp lokalt utan Base.
- Hindringar og forbodne område skal aldri forsvinne fordi sambandet med Base er brote.
- Utan Base viser maskina berre eigne målingar – delinga er eit tillegg.
- Lisensen kan avgrense det Base sender ut, men aldri stoppe sjølve SNOWMAN snødjupne.
- Den valfrie koplinga til Base (adresse og anleggsnøkkel for anleggsdata og deling) blir ein eigen bolk, av som
  standard. NTRIP-felta blir som i dag.

**Svakheit funnen (gjeld alt i dag):** RTK-motoren (`pc/v1.6/rtkmotor.py`, `base_bytes`, RTCM 1005/1006) tek inn ny
baseposisjon i `opt.rb`, men **nullstiller ikkje RTK-løysinga**. Heiltala frå den gamle basen kan bli verande, særleg
med fix-and-hold (v1.6.107) → mogleg **falsk FIX** like etter at basen er bytt. Det skjer òg utan reservecaster: når
Base sjølv går over til reserven (t.d. TH), får SNOWMAN ein annan base i same straum.
- **Tiltak (prioritet 1):** oppdag nytt basepunkt (posisjonen flyttar seg meir enn t.d. 1 m, eller ny stasjons-ID) →
  nullstill RTK-løysinga, logg hendinga, og vis kva base som er i bruk.

**Reservecaster i SNOWMAN (prioritet 2) – konsekvensar:**

| | Konsekvens | Tiltak |
|---|---|---|
| Fordel | Korreksjonar sjølv om hovudkjelda (t.d. Base) er nede. SNOWMAN blir verande uavhengig av Base. | – |
| Høgdereferanse | RTK måler relativt til basen. Feil i baseposisjonen går rett inn i snødjupna. Ulikt innmålte basar → hopp på cm til m ved byte. | Berre basar med innmålt koordinat (EUREF89/NN2000). Kontrollmål snødjupna mot kjent punkt med kvar base. |
| FIX-tap ved byte | Sekund til minutt i FLOAT medan heiltala blir funne på nytt – ingen ekte snødjupne i den tida. | Tiltaket i prioritet 1. |
| Sporbarheit | Målingar frå ulike basar kan avvike. | Feltlogg og rapport viser kva kjelde som var i bruk. Viktig for deling (v1.8). |
| Byte fram og tilbake | Kjelde som fell ut og kjem att → mange byte og FIX-tap. | Tilbake til hovudkjelda først når ho har vore stabil ei stund (t.d. 2 min), helst ikkje midt i preparering. |
| Innlogging | Ein konto til må lagrast. CPOS: same konto kan ofte ikkje vere innlogga to stader, og kostar per konto. | Eigen konto for reserven. |
| Arbeid | Felt for reserve på NTRIP-sida + logikk for byte. Bruker eksisterande «Ny oppkopling etter … sekund». | Om lag éin dag, i `pc/v1.6` (v1.6.x). |

**Rekkjefølgje:** 1) nullstilling av RTK ved byte av base og vising av aktiv base, 2) reservecaster med ventetid før
byte tilbake og logg av kjelde, 3) i drift: berre innmålte basar som hovudkjelde og reserve.

## 20. Språk: nynorsk, bokmål, engelsk og svensk (analyse 2026-11-20, ventar)

**Ønske frå eigaren:** ein språkmodul der ein kan velje språk, helst ved oppstart. Det må gjelde alle menyar og
tekstar.

**Omfang (målt i v1.6.124):** om lag 2 500–3 000 tekstar:
- førarskjermen (`driver.html`): om lag 840 tekstar i menyar og knappar og om lag 1 500 tekstar som blir laga medan
  programmet køyrer;
- leiarsida, HUD, NTRIP-oppsett og feilsøkaren: om lag 450 tekstar;
- meldingar frå tenesta: feilsøkaren, status, PDF-rapporten, startmenyen og AI;
- SNOWMAN Base (status og kontor): om lag 200 tekstar.

**Tre måtar som er vurderte:**
- **A. Nøkkelsystem** (`t("btn.start")` og éi fil per språk). Standardmåten, men alle om lag 3 000 stadene i koden
  må endrast, og kvar ny funksjon krev nøklar i alle språkfilene.
- **B. Nynorsk som nøkkel (tilrådd).** Koden blir ståande med nynorsk tekst, og kvart språk får ei ordliste frå
  nynorsk. Førarskjermen omset tekst og knappar automatisk, også når innhaldet endrar seg. Tekstar som blir laga i
  JavaScript og Python, går gjennom `T()`. Manglar ei omsetjing, blir nynorsken ståande, så ingenting blir tomt. Ein
  test listar tekstar utan omsetjing. Kan byggjast steg for steg.
- **C. Omsetjing i nettlesaren.** Dårlege fagord, verkar ikkje offline og rører ikkje meldingane frå tenesta.
  Forkasta.

**Val av språk:** første gong i startmenyen og i installasjonsprogrammet, og seinare under Innst. › System › Språk
(gjeld med ein gong, utan omstart). Valet blir lagra per maskin. SNOWMAN Base får sitt eige språkval på kontorsida.

**Fagord:** det blir laga ei ordliste før omsetjinga, t.d. svensk «pistmaskin, snödjup, preparering» og engelsk
«groomer, snow depth, tiller». Ein svensk og ein engelsk fagperson bør lese gjennom før sal.

**Plan i fire steg:**
1. Grunnmur: språkmodul, språkval, test for tekstar utan omsetjing og ordliste.
2. Førarskjermen og HUD. Etter dette steget kan ein svensk eller engelsk førar bruke SNOWMAN.
3. Feilsøkaren, NTRIP-sida og meldingane frå tenesta.
4. Leiarsida, PDF-rapporten og SNOWMAN Base. Rettleiingane (LES-MEG og Word) blir omsette for seg.

**Avgjerder (eigaren 2026-11-20):**
- Språkvala blir **nynorsk, bokmål, engelsk og svensk**.
- Feltloggen og hendingane blir skrivne på **same språk som føraren har valt**. Konsekvens for feilsøking: ein logg
  frå ei svensk maskin er på svensk. Kvar hending bør difor òg få ei fast kode (t.d. `NTRIP_FEIL`), så loggar på alle
  språk kan lesast og analyserast likt.
- **Ventar:** ingen endringar no. Plasserast i vegplanen seinare (truleg før v2.0, første salsversjon).

## 21. Ortofoto (flybilete) som lag i kart, 3D og Frontrute (analyse 2026-11-22, ventar)

Eigaren har eit ortofoto frå same droneflyging som terrengmodellen «Sykkylven Skisenter» (.pxy) og høgdekurvene
«Fjellseter terreng 0,25 Kootelinjer.dxf» (same omriss, 1192 × 1189 m). Ønske: ortofotoet som eit lag som kan slåast
av og på, og strekt over 3D-terrenget.

**Analyse:**
- **Kart (2D):** enkelt. Leaflet legg biletet over Kartverket-bakgrunnen med PÅ/AV og gjennomsikt. Snødjupnefargar og
  spor ligg oppå.
- **3D og Frontrute:** mogleg. Alt på 3D-flata er éin tekstur som ligg over terrengnettet (høgdekurver, snødjupne,
  spor, trasear – sjå kap. 8 og v1.6.133). Ortofotoet blir teikna inn som botnlag i teksturen og følgjer då terrenget
  av seg sjølv. Detaljnivået blir avgrensa av teksturen: 4 px/m for heile utsnittet, 12–16 px/m nær maskina (godt nok
  for stiar, steinar og tre). Kap. 8 testa allereie kartfliser drapert på 3D-terrenget, så dette byggjer vidare på det.
- **Krav til fila:** biletet må ha koordinatar. Skjermbiletet (JPG, ca. 960 × 820 px, ca. 1,5 m/px, utan koordinatar)
  kan ikkje brukast. Brukbart: **GeoTIFF** (best – SNOWMAN les alt GeoTIFF for terreng) eller **JPG/PNG med world-fil**
  (.jgw/.pgw), helst med .prj. **Ikkje** ECW, JPEG 2000 eller MrSID (krev GDAL) – be om GeoTIFF i staden.
- **Storleik:** 3–5 cm over 1,2 × 1,2 km = 500–1000 megapikslar – for stort for førarskjermen. Ved import lagar SNOWMAN
  kartfliser i fleire detaljnivå og lagrar dei lokalt: fungerer utan nett, raskt å vise, 3D hentar berre utsnittet
  rundt maskina. Ingen nye bibliotek: tifffile og imagecodecs les GeoTIFF og lagar JPEG-fliser.
- **Nytte utover utsjånaden:** sjå skogbelta når ein teiknar JAMN UT HEILT, VERN og trasear (v1.6.135); føraren
  kjenner att stiar, bekkar, steinar og bygg under snøen; kontroll av terrengmodellen (ein «haug» i 3D der fotoet viser
  eit tre = treet er ikkje fjerna).
- **Observasjon:** ortofotoet viser at .pxy-fila truleg er rekna ut frå flybileta (fotogrammetri), ikkje LiDAR. Då
  finst det ingen bakkepunkt under tett skog, og «FJERN TRE» må gjette der.

**Forslag til løysing:**
1. Terrengbiblioteket: ny lagtype «Ortofoto (flybilete)». Les GeoTIFF eller world-fil, lagar fliser med framdrift
   (som .pxy-importen).
2. Kart: eige val under **Bakgrunn**, med PÅ/AV og gjennomsikt.
3. 3D og Frontrute: ortofotoet som botnlag i terrengteksturen, med PÅ/AV. Høgdekurvene blir tynnare når det er på
   (jf. det opne spørsmålet i kap. 8).
4. Valfritt: biletet blir automatisk dempa eller vist i gråtonar når snødjupna er vist, så sumarfargane ikkje gjer
   snøfargane vanskelege å lese.

**Ventar:** eigaren sjekkar kva filer dronefirmaet leverte (.tif eller .jgw ved sida av biletet), storleik og filnamn.
Ingen endringar før eigaren seier frå. Ikkje plassert i vegplanen.

## Vegplan (bestemt av eigaren 2026-10-06)

| Versjon | Innhald |
|---|---|
| **v1.6.x** | Feltprøve med Leica i maskina og rettingar etter ho. |
| **v1.7** | Anleggspakke med versjonsnummer (kap. 16), fleire terrengfiler på ein gong (LAS/LAZ/XYZ kom i v1.6.95), trasear og hindringar i 3D/frontrute, rettleiingslinjer. |
| **Kontor v1.0** | SNOWMAN Kontor – kontorsida og anleggsserveren på ein Windows-PC (kap. 16, avgjerd 6, 2026-11-22). |
| **Kontor 1.1** | Kontormodus (SNOWMAN snødjupne utan GNSS), terreng i anleggspakka, sanntid frå maskinene (wifi eller port 8791) (kap. 16, avgjerd 7, 2026-11-23). |
| **Base v1.4** | Berre satellittar og NTRIP – kontordelen flytta til SNOWMAN Kontor (2026-11-22). |
| **Base v1.3** | Maskin-API på port 2101 og format for anleggspakka (kap. 16, 2026-11-20). |
| **Base v1.0** | SNOWMAN Base (kap. 18): eigen base, NTRIP-caster med reserve, API for deling og anleggspakke, kontorside, forbetringar med AI. Laga 2026-10-29. |
| **v1.8** | Deling mellom maskiner (snødjupne siste 12 t, felles preparert areal) og utsending av anleggsdata frå server (kap. 6). Kontor publiserer, maskiner sender forslag, enkel kontorside i 2D (kap. 16). Lisensplassar på serveren (kap. 17). |
| **v1.9** | Presisjon og klar for sal: maskingeometri (snødjupne ved fres og skjer, IMU), lisens og aktivering per maskin (kap. 17), full kontordel med 3D-redigering og import (kap. 16), driftsportal for driftsleiar (kart over flåten, rapportar, historikk, drivstoff, trasear, beskjedar), snøvolum mot målflate, skjermkorttest per maskin (kap. 9), førarinnlogging med roller, førar på økter/loggar/rapportar, personvern-innstillingar, oppsummering med kart og PDF, kompakt loggliste (kap. 10 – som v1.9.1 eller v2.0.1). |
| **v2.0** | Første salsversjon til andre anlegg: installasjonsrettleiing, brukarmanual, support. |
| Moglege (ikkje plasserte) | 3D: trakka område, bakgrunnskart og større område (kap. 8) – testa 2026-10-07, ventar på avgjerd. Ortofoto (flybilete) som lag i kart, 3D og Frontrute (kap. 21) – analysert 2026-11-22, ventar på fila. |
| Seinare | CAN-bus (drivstoff, motordata, feilkodar med varsling, vinsj – ulikt for PistenBully og Prinoth) – forundersøking for PB600 i kap. 12 og `PB600-CAN.md`. LiDAR for snødjupne framfor maskina. |

Maskingeometrien blir flytt fram til v1.7 om feltprøva viser at målinga ved antenna er for upresis.

## 7. Anna

- ~~LAS/LAZ-import (punktsky)~~ – ferdig i v1.6.95 (eigen LiDAR, val av høgdesystem).
- Målflate og snøflate (kor mykje snø som skal flyttast, snøvolum).
