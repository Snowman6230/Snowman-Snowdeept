# Endringslogg – SNOWMAN by Alpindata

Alle endringar i SNOWMAN blir førte her, med den nyaste øvst.
Kvar oppføring seier **kva** som vart endra og **kvifor**. Detaljane står i git-historikken.

Merke: **Nytt** · **Endra** · **Retta** · **Fjerna** · **Avgjerd** (val som styrer vidare utvikling)

---

## 2026-10-06

### PC-prototype v1.6.31 – hellingskorreksjon (antenna står ikkje rett over beltet i bakke)
- **Nytt:** `helling.py`. Antenna sit 2,8 m over beltet; når maskina står på skrå, er ho ikkje rett over beltet. Utan korreksjon blir snødjupna for høg (4 cm ved 10°, 18 cm ved 20°, 43 cm ved 30°), og punktet blir målt opptil 1,4 m ved sida av der maskina står. SNOWMAN rettar no både høgda (h·cos θ) og punktet (flytt h·sin θ opp i bakken). Berre høgdekorreksjon utan å flytte punktet ville gjort feilen større, så begge blir alltid gjorde saman.
- **Nytt:** Kjelde for hellinga, Innst. › Kalibrering › Helling:
  - **Auto (standard):** hellingsmålaren i antenna om ho sender han (NMEA `HPR`/`PSAT,HPR`, `PASHR` eller `PTNL,AVR` – t.d. Leica GS18 T / iCON gps 70 T om dei er sette opp til det), elles utrekna. Antenna blir oppdaga av seg sjølv.
  - **Utrekna:** helling langs køyreretninga frå GNSS-høgda dei siste 4–10 m, sidehelling frå terrengmodellen der maskina står.
  - **Av:** som før.
  - «Snu forteikn» for stamp og krenging om antenna er montert annleis. Skjermen viser helling, stamp, krenging, kjelde, kor langt målepunktet er flytt og kor mykje høgda er retta.
- **Nytt:** Feltloggen (CSV) har kolonnar for hellingskjelde, helling, stamp, krenging og flytting av målepunktet.
- **Endra:** Simulatoren set antenna vinkelrett ut frå snøflata (som i ei ekte maskin på skrå), og kan sende helling som ei antenne med hellingsmålar (`--helling`, `$PASHR`). Det tynne snøfeltet har no 4 m skrå overgang i staden for loddrett kant.
- **Endra:** `docs/FELTPROVE.md`: sjekk forteikn på hellinga i bakke, og ta kontrollmålingar der det er flatt.
- **Avgjerd (eigar):** Programmet skal automatisk bruke hellingsmålaren i antenna om ho har det, og elles rekne ut hellinga sjølv.
- **Merknad:** Leica GS07 og GS16 har ikkje hellingsmålar etter det Leica oppgir; GS18 T/I og iCON gps 70 T har. Om antenna sender hellinga ut til andre program, må sjekkast i feltloggen.
- **Testa (snødjupne mot fasit):**
  - Testterreng (jamn bakke, 14°): snittfeil 9,2 cm utan korreksjon → 0,7 cm utrekna (maks 2,4 cm).
  - Familietrekk (Topocad, opptil 23°): snitt |feil| 5,4 cm (maks 33 cm) utan → 1,0 cm utrekna (maks 7 cm) → 0,7 cm med hellingsmålar i antenna (maks 2,8 cm).
  - Utan simulert tidsforskyving (rekna direkte langs heile ruta, 3 800 punkt): 7,6 cm → 0,4 cm, ingen over 10 cm.

### Plan – vegplan v1.7 til v2.0
- **Avgjerd (eigar):** v1.9 = presisjon og klar for sal (maskingeometri, lisens, driftsportal, snøvolum); v2.0 = første salsversjon. Sjå tabellen «Vegplan» i `docs/VEGEN-VIDARE.md`.

### Plan – fleire maskiner deler snødjupne
- **Avgjerd (eigar):** Maskiner med SNOWMAN skal dele målingane sine, slik at snødjupne og preparert areal frå dei siste 12 timane er kjent for alle maskinene. Det er mobildekning i heile anlegget; utan dekning blir målingane sende automatisk når dekninga kjem att.
- **Avgjerd:** Løysinga blir ein felles SNOWMAN-server for anlegget med «lagre og send vidare» (maskinene kan ikkje nå kvarandre direkte over mobilnettet). Nyaste måling gjeld, GNSS-tid på kvar måling, berre RTK FIX frå kalibrerte maskiner, aldri demo. Planlagt som v1.8, etter anleggspakka (v1.7). Sjå `docs/VEGEN-VIDARE.md` kap. 6.
- **Avgjerd (eigar):** Same server skal òg sende anleggsdata (terreng, trasear, hindringar, kontrollpunkt, kartfliser) ut til alle maskinene. Endringar blir gjorde éin stad; nytt terreng blir berre teke i bruk når prep er stoppa.
- **Avgjerd (eigar):** Vel den beste og billigaste serverløysinga når dette blir innført. Alternativ: NAS på anlegget (med Tailscale), kontor-PC eller leigd server (ca. 75–80 kr/mnd hos Hetzner, august 2026).

### PC-prototype v1.6.30 – varsel om hindringar, og rapportar lagra automatisk
- **Nytt:** **Hindringar** under Innst. › Trasear: hydrant, snøkanon, heismast, stein, kum, bygg, gjerde/stolpe eller anna, med namn, radius og merknad. Leggjast inn ved å trykke på kartet, eller «framfor skjeret» når maskina står inntil hindringa. Vist på kartet som raudt merke med symbol og ring i rett storleik.
- **Nytt:** **Varsel berre for hindringar maskina kan treffe:** når ei hindring ligg i køyrebana (breidda til frontskjeret + radius + 0,5 m), kjem eit stort raudt varsel **10 m før skjeret** når ho, med nedteljing i meter («⚠ HYDRANT 7 · 8 m» … «STOPP!»). Blinkar dei siste 3 m. Kort pip når varselet kjem og for kvar meter dei siste 5 m. Hindringar ved sida av køyrebana gir ikkje varsel.
- **Nytt:** Varselet kjem **både på førarskjermen og på HUD** (stor raud tekst, blinkar nær). Er det inga hindring, viser HUD varsel om forbode område.
- **Nytt:** **Rapportar blir lagra automatisk** til ei mappe (standard: `Dokument/SNOWMAN-rapportar`) kvart 5. minutt og med éin gong prep blir stoppa – også utan nett. Éi CSV-fil per prepareringsdøgn og maskin. Ligg mappa i OneDrive, Google Drive eller Dropbox på PC-en, lastar synkroniseringsprogrammet opp filene når PC-en har nett (wifi eller mobildata). Mappa og av/på blir valde i Innst. › Rapport, med «Lagre rapportane no».
- **Nytt:** `trasear.py` `Objekt`, `data/objekt.json`, `GET /api/objekt`, `POST /api/objekt/save`, `/delete`; `GET/POST /api/report/export`. HUD får `warn` og `warnLevel`.
- **Avgjerd (eigar):** Varsel om hindringar skal kome på både HUD og skjerm, berre for hindringar maskina er i fare for å treffe, 10 m før, med nedteljing.
- **Avgjerd:** Opplasting skjer via synkroniseringsprogrammet på PC-en (OneDrive o.l.), ikkje frå SNOWMAN sjølv. Då treng SNOWMAN ingen passord eller nett, og fungerer offline.
- **Testa:** simanlegg over Familietrekk: hindring lagt inn frå kartet, hydrant lagd 14–16 m framfor maskina gir nedteljing 8 → 5 → 1 m → STOPP!, same tekst på HUD, varselet forsvinn når hindringa er passert. Rapportmappe valt i nettlesaren: CSV-fil skriven med maskinnamn. Ingen JS-feil. (Testmaskina oppdaterer posisjonen sjeldnare enn ein ekte mottakar, så nedteljinga hoppa fleire meter om gongen i testen.)

### PC-prototype v1.6.29 – frontskjeret ser ut som eit skjer
- **Endra:** Frontskjeret i 3D-terreng og frontrute var ein kloss (eigaren: «ser ikkje ut som eit frontskjer»). No er det ei tynn, bøygd skjærplate (1,15 m høg, krummar fram i toppen) med svart kant øvst, to sidevengjer vinkla fram og to skyvearmar. Plata er halvgjennomsiktig, så føraren ser snødjupnefargane framfor skjeret gjennom ho i frontrutevisinga. Breidda følgjer framleis innstillinga for frontskjer (full / innkøyrd).
- **Testa:** simanlegg over Familietrekk, frontrute og 3D-terreng, ingen JS-feil.

### PC-prototype v1.6.28 – store terrengfiler (Kartverket DTM1) blir klipte til anlegget
- **Nytt:** GeoTIFF-filer over 40 millionar ruter (t.d. Kartverket DTM1 «som kildedata», 1,1 GB per fil) blir ikkje lesne heilt inn. SNOWMAN viser kva fila dekkjer, og føraren vel eit utsnitt (2×2, 3×3, 4×4 eller 6×6 km) rundt kartmidten i Innst. › Terreng. Berre rutene/stripene i fila som ligg i utsnittet blir pakka ut, så minnebruken held seg låg.
- **Nytt:** Utsnitt av ei stor fil blir lagt **under** dei andre laga (grunnlag), så Topocad-modellar for bakkane blir brukte først der dei finst. Ligg anlegget over to filer, blir kvar fil eit eige lag – biblioteket brukar dei saman.
- **Nytt:** Manglar fila koordinatsystem, blir det henta frå Kartverket-filnamnet (t.d. `dtm1_33_…` → EUREF89 UTM 33), med åtvaring.
- **Nytt:** `POST /api/terrain/crop` (bigToken, lat, lon, half). Store opplastingar ligg i `data/upload/stor-*` i inntil 3 timar og blir sletta ved oppstart.
- **Bakgrunn:** Eigaren har lasta ned Kartverket-bestilling 1763175: to filer, `dtm1_33_111_133.tif` og `dtm1_33_111_134.tif`, 1,1 GB kvar (+ `.tfw` og metadata).
- **Testa:** Syntetisk 7×7 km GeoTIFF (LZW, flyttal-prediktor, både ruter og striper): utsnitt på 2×2 km lese på 0,15–0,4 s, høgdene identiske med fila, rett plassering. Heile flyten i nettlesaren: stor fil → utsnitt → import nedst i biblioteket → rett høgd ved oppslag.

### PC-prototype v1.6.27 – retta frys når det berre finst forbodne område
- **Retta:** SNOWMAN fraus (ingen knappar verka, kartet vart blankt eller svart) når anlegget hadde eit forbode område men ingen trasé. Teikninga av traseane bad om ny prosent, og når det ikkje fanst nokon trasé å rekne prosent for, teikna ho kartet på nytt – som igjen bad om ny prosent, i ring. Nettlesaren gav opp med «Maximum call stack size exceeded» mange gonger i sekundet. Funne frå skjermbilete av konsollen hos eigaren.
- **Endra:** Ny prosent blir no berre henta frå den vanlege oppdateringa (kvart 8./15. sekund), aldri frå sjølve teikninga, og berre når det finst minst éin trasé.
- **Testa:** Berre eitt forbode område + demo + Innst. › Trasear + bakgrunn av/på: før rettinga fraus sida (som hos eigaren), etter rettinga ingen feil.
- **Merknad:** Retting i v1.6.26 (namn på traseane) var ikkje årsaka, men er behalden fordi ho gjer visinga lettare.

### PC-prototype v1.6.26 – retting av treg vising
- **Retta:** Eigaren melde at v1.6.25 var tydeleg tregare enn før i alle startval (1–4). Frå v1.6.23 sette førarskjermen ein CSS-variabel på heile kartet for kvar posisjon (for at trasénamna skulle stå rett opp). Då måtte nettlesaren rekne om stilen til alle element i kartet fleire gonger i sekundet. No blir berre namne-elementa snudde, og berre når kartvinkelen er endra med minst 2°.
- **Testa:** 90 s demo i nettlesar: tid til stilutrekning ned ca. 30 %. Treigleiken kunne ikkje framkallast fullt ut her (testmaskina har ikkje skjermkort), så eigaren må stadfeste på eigen PC.

## 2026-10-05

### PC-prototype v1.6.25 – uprepart areal og måldjupne per trasé
- **Nytt:** **Uprepart areal** blir vist oransje inne i kvar trasé – areal fresen ikkje har gått over i prepareringsdøgnet. Blir oppdatert kvart 8. sekund under prep (frå øktene som blir lagra kvart 5. sekund). Kan slåast av i Innst. › Trasear. I test blir demo/simulator rekna med.
- **Nytt:** **Måldjupne per trasé:** når maskina er i ein trasé med eiga måldjupne, viser snødjupnetalet øvst avviket («✓ PÅ MÅL», «▼ 0,40 UNDER MÅL», «▲ 0,50 OVER MÅL») og blir raudt under og blått over mål. Toleransen kjem frå Målprofil. HUD brukar same måldjupne og viser namnet på traseen.
- **Endra:** `GET /api/trasear/status?map=1` gir òg kart over uprepart areal (bitmap per trasé).
- **Avgjerd:** Fargane på sporet i kartet følgjer framleis forklaringa (snøintervall), så forklaringa alltid stemmer. Måldjupna blir vist i talet øvst og på HUD.
- **Testa:** simanlegg over Familietrekk med måldjupne 0,90 m: køyrt stripe blir borte frå det oransje, avvik og farge rett under/på/over mål, HUD får måldjupne og trasénamn, ingen JS-feil.

### PC-prototype v1.6.24 – drivstoff og rapport
- **Nytt:** Innst. › **Drivstoff**: registrer fylling (liter, timeteljar på motoren, merknad, «fylt heilt opp»). SNOWMAN reknar **liter per time** og **liter per daa** med full tank-metoden: literane ved ei fylling er det maskina har brukt sidan førre fulle fylling. Med timeteljar blir det rekna mot motortimar, elles mot tida med prep på (frå øktene). Ei fylling som ikkje er full blir lagt saman med neste fulle. Viser snitt for dei siste 30 dagane.
- **Nytt:** Innst. › **Rapport** for eitt prepareringsdøgn: samla tid med prep, køyrd lengd, areal køyrt, drivstoff og målt snødjupne; per trasé prosent preparert, sist preparert og snødjupne (med måldjupne); kvar økt; og fyllingane. **Last ned som CSV** (semikolon og desimalkomma, opnar rett i norsk Excel).
- **Nytt:** `drivstoff.py`, `data/drivstoff.json`, `GET /api/fuel`, `POST /api/fuel/add`, `/api/fuel/delete`, `GET /api/report?date=`, `/api/report/days`, `/api/report/csv?date=`.
- **Avgjerd:** Drivstoff blir registrert for hand no (alternativ A). Automatisk forbruk (CAN-bus, straummålar) står i `docs/VEGEN-VIDARE.md`.
- **Avgjerd:** Demo og simulator er med i rapporten, merka TEST, men ikkje i summane.
- **Testa:** To fyllingar med timeteljar over ei 1-times økt (43,9 daa) gir 29,6 l/time og 0,81 l/daa; lågare timeteljar enn førre fylling blir avvist; registrering og sletting i Innst. › Drivstoff; rapport og CSV-nedlasting i nettlesaren, ingen JS-feil.

### PC-prototype v1.6.23 – trasear (yttergrense for preparering) og forbodne område
- **Nytt:** Innst. › **Trasear**. Kvar trasé er eit omriss med namn, vanskegrad/farge (grøn, blå, raud, svart, langrenn, anna) og valfri måldjupne. **Forbodne område** (veg, bygg, bekk, parkering) blir lagra på same måte.
- **Nytt:** Tre måtar å lage omrisset på:
  - **Teikne på kartet:** trykk for kvart hjørne, dra hjørna for å flytte, trykk på eit hjørne for å fjerne det, ANGRE / FERDIG / AVBRYT.
  - **Hente frå terrengmodellen:** SNOWMAN finn yttergrensa av cellene med høgd i laget (største samanhengande område, forenkla til få hjørne). Føraren justerer før lagring. Testa på Familietrekk (Topocad): 11 hjørne, 35,2 daa, 96 % av modellen innanfor.
  - **Endre** eit lagra omriss: nye hjørne blir sette inn på næraste kant.
- **Nytt:** Prosent preparert per trasé, rekna i SNOWMAN-tenesta frå øktene: kvar strekning maskina har køyrt med prep på, med fresbreidda, blir merkt i eit rutenett (1 m) over traseen. Hopp over 30 m eller pausar over 60 s blir ikkje rekna som køyrt. Viser òg sist preparert og snitt/minste målte snødjupne i traseen.
- **Nytt:** Traseane blir viste på kartet med namn og prosent (namnet står rett opp sjølv når kartet er snudd). Øvst i tal-kolonnen til venstre står gjeldande trasé og prosent.
- **Nytt:** Varsel under preparering: **UTANFOR TRASÉ**, **KANTEN AV TRASEEN** (fresen når over kanten), og raudt blinkande **FORBODE OMRÅDE** / **NÆR FORBODE OMRÅDE**.
- **Nytt:** `trasear.py`, `data/trasear.json`, `GET /api/trasear`, `GET /api/trasear/status` (`?date=ÅÅÅÅ-MM-DD` for eit anna døgn), `POST /api/trasear/save`, `/delete`, `/from-terrain`.
- **Avgjerd:** **Prepareringsdøgnet går frå kl. 12 til kl. 12**, slik at ei natt med preparering (t.d. 17–03) blir rekna som éin dag.
- **Avgjerd:** Teikning er berre mogleg når prep er stoppa, og skjer alltid med kartet ovanfrå og nord opp (elles treffer trykka feil stad). Visinga blir sett tilbake etterpå.
- **Avgjerd:** Demo og simulator tel ikkje i prosent preparert. I test blir prosenten med demo/simulator vist med **TEST** etter.
- **Testa:** simanlegg over Familietrekk: hente omriss, flytte/legge til/angre hjørne, lagre trasé og forbode område, preparering med prosent og varsel, ingen JS-feil. Syntetisk sveip over heile traseen gir 100 %.

### PC-prototype v1.6.22 – fri vising når prepareringa er stoppa
- **Nytt:** Når prep er stoppa, kan føraren sjå på arbeidet frå ulike vinklar:
  - **3D-terreng og frontrute:** dra for å snu kameraet rundt maskina (og vippe opp/ned), rull/knip for zoom, to fingrar, høgre museknapp eller Shift + dra for å flytte.
  - **Kart, førar og horisont:** knappane ⟲ ⟳ snur kartet 15° om gongen, og kartet kan dragast utan at det hoppar tilbake til maskina.
  - **⌖ Følg maskina** (eller Sentrer) går tilbake til vanleg vising.
- **Endra:** Når prep startar, går visinga automatisk tilbake til å følgje maskina, og snu-knappane blir skjulte – føraren kan ikkje kome i fri vising ved eit uhell under køyring.
- **Testa:** Knappane er skjulte under prep og synlege etter stopp; dra og zoom i 3D gir fri kamera; Følg maskina nullstiller; ⟲ ⟳ og dra i kartvising.

### Dokumentasjon – vegen vidare
- **Nytt:** `docs/VEGEN-VIDARE.md` – moglege framtidige løysingar: maskingeometri (snødjupne ved fres og skjer ut frå antenneplassering og mål), IMU og to antenner (rygging, bratt terreng), følar for skjerhøgd, anleggspakke, opplasting av fleire terrengfiler, trasear og anleggsobjekt, fleire maskiner.
- **Avgjerd (eigar):** Maskingeometri for fres og skjer blir ikkje laga no, men står som framtidig løysing. Antenna skal sitje midt på taket mellom førar og passasjer, om ho ikkje er i vegen for vinsjen.

### PC-prototype v1.6.21 – feltlogg for prøving i maskina
- **Nytt:** `feltlogg.py` – lagrar alt mottakaren sender (alle NMEA-linjer, med PC-tid) og hendingar (mottakar/NTRIP tilkopla, feil) i `data/logg/<namn>.nmea`, og éi CSV-linje per posisjon med det SNOWMAN rekna ut: fix, satellittar, HDOP, posisjon, høgd, geoidehøgd, terrenghøgd og lag, snødjupne (rå og vist), status, fart, kurs, antennehøgd og høgdeoffset.
- **Nytt:** Innst. › System › FELTLOGG: start/stopp, «Logg alltid når SNOWMAN startar», liste over loggar med **Last ned (zip)**, og slett alle. Loggen inneheld ingen passord. Mappa blir halden under 500 MB (eldste loggar blir sletta).
- **Nytt:** `GET /api/log`, `POST /api/log` (start/stopp/slett/alltid), `GET /api/log/download?name=` (berre loggfiler kan lastast ned).
- **Nytt:** `docs/FELTPROVE.md` – sjekkliste for første prøvetur med Leica i trakkemaskina.
- **Testa:** 5 s logg med simulert mottakar: NMEA- og CSV-fil med rett innhald, nedlasting som zip, forsøk på å laste ned andre filer blir avvist.

### PC-prototype v1.6.20 – eigen logo (trakkemaskin)
- **Nytt:** SNOWMAN-ikon: raud trakkemaskin på preparert snø med fjell, i eit avrunda blått felt. Eiga teikning (`pc/v1.6/ikon/snowman.svg`), med PNG og Windows-ikon (`snowman.ico`, 16–256 px).
- **Nytt:** Ikonet blir brukt på snarvegen på skrivebordet (Windows), i autostart, i programmenyen (Linux) og som ikon for SNOWMAN-vindauget, HUD-sida og nettlesarfana.
- **Kvifor:** Eigaren ville at filene og snarvegane skal vise at dette er hans program.

### PC-prototype v1.6.19 – installasjon som Maskin-PC, autostart og oppdatering frå skjermen (kiosk, steg 3–4)
- **Nytt:** Installasjonen spør om **Kontor-PC** (du startar SNOWMAN sjølv) eller **Maskin-PC** (startar av seg sjølv i kioskmodus). Både `INSTALLER-WINDOWS.bat` og `installer-linux.sh`. Kan endrast seinare under Innst. › System.
- **Nytt:** `oppstart.py` – autostart utan administratorrettar. Windows: snarveg i Oppstart-mappa som startar utan svart vindauge (`pythonw`). Linux: merkt `exec-once`-linje i Hyprland-oppsettet (Omarchy) eller `~/.config/autostart/snowman.desktop` (GNOME, KDE, XFCE). Autostart brukar `--auto`: kiosk eller vanleg etter innstillinga.
- **Nytt:** Maskin-PC på Windows: dvale og skjermsparar blir slått av på straum (`powercfg`). I kioskmodus held SNOWMAN skjermen vaken sjølv (Wake Lock) – også på Linux.
- **Nytt:** Innst. › System: «Start SNOWMAN automatisk når PC-en startar», «Start i kioskmodus», PIN-kode, og **Hent siste versjon** med **Start SNOWMAN på nytt** – så kiosk-PC-en kan oppdaterast utan meny og terminal (`POST /api/update`, `POST /api/restart`; oppstartsprogrammet startar teneste og vindauge på nytt ved kode 3).
- **Endra:** Økta blir lagra kvart 5. sekund (før kvart 30. punkt). Innstillingane i tenesta blir skrivne trygt (mellombels fil + byte), som økter og kontrolldata alt var.
- **Retta:** Overskrifta i Innstillingar med «Avslutt SNOWMAN» skuva fanene saman.
- **Testa (Linux):** installasjon som Maskin-PC med og utan Hyprland-oppsett, autostart av/på, oppdatering og omstart frå skjermen. Windows-delen (snarveg, pythonw, powercfg) er ikkje testa på ein ekte Windows-PC enno.

### PC-prototype v1.6.18 – kioskmodus med byte begge vegar, PIN og vakthund (kiosk, steg 2)
- **Nytt:** Kioskmodus: berre SNOWMAN på skjermen (Edge/Chromium `--kiosk`). Knappen nede heiter **«Vanleg skjerm»** i kiosk og **«Kioskmodus»** i vanleg vindauge. Oppstartsprogrammet lukkar det eine vindauget, ventar til det er heilt lukka, og opnar det andre. Kontrollerer at vindauget kom opp, og prøver ein gong til om ikkje.
- **Nytt:** Eigne nettlesarprofilar for kiosk og vanleg vindauge (`data/nettlesar-kiosk`, `data/nettlesar`), så det nye vindauget alltid blir ein eigen prosess. Innstillingane er like i begge (ligg i tenesta sidan v1.6.17).
- **Nytt:** Valfri **PIN-kode** for å gå ut av kiosk (Innst. › System). 4–8 siffer, lagra som SHA-256-hash. Av når SNOWMAN blir levert.
- **Nytt:** Fana **System** i Innstillingar: PIN-kode og «Start i kioskmodus (autostart)» (`data/system.json`, brukt av `--auto`).
- **Nytt:** Vakthund i oppstartsprogrammet: blir kioskvindauget lukka (t.d. Alt + F4), kjem det opp att etter 1,5 s. Krasjar tenesta, blir ho starta på nytt (maks 5 gonger på 2 min). «Avslutt SNOWMAN» stoppar alt som før.
- **Endra:** Ei preparering som pågår, blir stoppa og lagra før skjermen blir bytt (med spørsmål). Utan oppstartsprogrammet slår knappen nettlesaren sin fullskjerm av/på som før.
- **Endra:** `stopp` (meny, `snowman stopp`) stoppar oppstartsprogrammet først, så vakthunden ikkje startar tenesta på nytt.
- **Endra:** Menyval 4 heiter «Start i kioskmodus».
- **Testa:** Ekte Chromium (virtuell skjerm): kiosk → feil PIN avvist → rett PIN → vanleg skjerm → kioskmodus att; kioskvindauget drepe → opna att; tenesta drepen → starta att; stopp → alle prosessar borte.

### PC-prototype v1.6.17 – førarinnstillingane ligg i SNOWMAN-tenesta (kiosk, steg 1)
- **Endra:** Innstillingane i førarskjermen (perspektiv, bakgrunn, maskinmål, kartkjelde, snøintervall osv.) blir lagra i tenesta (`data/ui-config.json`) i staden for berre i nettlesaren. Same innstillingar i kioskvindauge, vanleg vindauge og alle nettlesarprofilar. Nettlesaren er reserve når tenesta manglar. Første gong blir innstillingane frå nettlesaren sende til tenesta.
- **Nytt:** `GET/POST /api/ui-config`, og `write_atomic()` i tenesta: skriv til mellombels fil og byter ut, så straumbrot aldri gir halvskrivne filer.
- **Nytt:** `docs/KIOSKMODUS.md` – analyse og plan for kioskmodus, autostart og installasjon som Maskin-PC. Avgjerder: valfri PIN for å gå ut av kiosk; automatisk innlogging blir ikkje sett opp automatisk.
- **Testa:** Innstillingar endra i éin nettlesarprofil blir viste i ein annan profil.

### PC-prototype v1.6.16 – «Avslutt SNOWMAN» i skjermbiletet
- **Nytt:** Knappen **⏻ AVSLUTT SNOWMAN** øvst i Innstillingar. Etter stadfesting: pågåande preparering blir stoppa og lagra (SNOWMAN ventar til økta er lagra i tenesta), innstillingane blir lagra, tenesta stoppar, simulatoren og vindauget blir lukka. Står vindauget att (t.d. starta utan oppstartsprogrammet), viser det «SNOWMAN er avslutta. Alt er lagra.»
- **Nytt:** `POST /api/shutdown` (berre på denne PC-en, ikkje på mobil-porten). Tenesta lagrar innstillingane og frigjer COM-porten til Leica når ho stoppar.
- **Endra:** `saveCurrentSession` returnerer når lagringa er ferdig; feilar lagringa i tenesta, blir økta lagra i nettlesaren i staden.
- **Testa:** Ekte Chromium: preparering med 23 punkt → Avslutt → økta lagra med 24 punkt, alle prosessar stoppa, vindauget lukka.
- **Avgjerd:** Knappen ligg i Innstillingar (ikkje i verktøylinja), så han ikkje blir trykt på ved eit uhell under køyring.

### PC-prototype v1.6.15 – HUD utan venting
- **Retta:** I demo (Demo-knappen) og når førarskjermen sender prepareringsstatus, venta HUD-straumen på neste GNSS-posisjon – utan mottakar berre éin gong i sekundet. No blir HUD-en varsla med éin gong førarskjermen sender noko (5 gonger i sekundet).
- **Endra:** Straumen sender kvar melding med éin gong (TCP_NODELAY), utan at operativsystemet samlar små pakkar.
- **Nytt:** HUD-menyen viser kor ofte HUD-en får nye tal («Oppdatering: 5,0 gonger/s (straum)»), så ein kan sjå om det er nettverket som er tregt.
- **Retta:** Knappen FULLSKJERM i HUD-menyen gjorde ingenting (same namnefelle som før: `fullscreen` er ein eigenskap på document).
- **Testa:** HUD med simulert mottakar: 10 oppdateringar/s. Demo utan mottakar: 5/s (før 1/s).

### PC-prototype v1.6.14 – oppdatering frå menyen også på Windows
- **Nytt:** Menyval 5 «Hent siste versjon» fungerer no utan git: SNOWMAN lastar ned siste versjon frå GitHub (zip), skriv berre filer som er endra inn i pc-mappa og oppdaterer bibliotek ved behov. Mappene `data` (terreng, kalibrering, kontroll) og `.venv` blir aldri rørte, og gamle prototypar (v1.2–v1.5) blir ikkje lasta ned. Med git (Linux-maskina) blir `git pull` brukt som før.
- **Testa:** Utpakka Windows-pakke v1.6.10 → menyval 5 → v1.6.13, 9 filer oppdaterte, data-mappa uendra.
- **Kvifor:** Eigaren ville oppdatere frå terminalvindauget på Windows-PC-en i staden for å laste ned og pakke ut zip-fila kvar gong.

### PC-prototype v1.6.13 – menyen nedst blir verande i 3D-terreng og frontrute
- **Retta:** Verktøylinja nedst forsvann hos eigaren når han bytte til 3D-terreng eller frontrute. Truleg årsak: på somme skjermkort/nettlesarar blir ei WebGL-flate som dekkjer heile vindauget teikna over resten av sida. Feilen kom ikkje fram i testmiljøet her.
- **Endra:** 3D-flata ligg no berre mellom topplinja og verktøylinja (aldri under dei), og topplinja og verktøylinja får eigne teiknelag (`translateZ(0)`).
- **Testa:** 3D-terreng og frontrute teiknar som før, og verktøylinja er øvst på 1024–1440 px breie skjermar.

### PC-prototype v1.6.12 – raskare HUD på mobil
- **Endra:** HUD-en hentar ikkje lenger data ved å spørje PC-en kvart 0,3 sekund (ny nettverkstilkopling kvar gong). I staden held han éi tilkopling open, og PC-en sender ny verdi med éin gong ein ny GNSS-posisjon kjem – 5 gonger i sekundet (Server-Sent Events, `GET /api/hud/stream`). Også tilgjengeleg på mobil-porten 8766; alt anna er framleis stengt der.
- **Nytt:** Vakthund i HUD-en: kjem det ikkje data på 4 sekund (t.d. mobilen har sove), koplar han til på nytt. Fell tilbake til spørjing om nettlesaren ikkje støttar straum.
- **Testa:** 5–6 meldingar i sekundet på begge portane, data under 0,01 s gamle når dei blir sende. HUD-sida opnar éi straumtilkopling og oppdaterer fart og snødjupne fortløpande.
- **Kvifor:** Eigaren opplevde at HUD på mobil låg etter førarskjermen.

### PC-prototype v1.6.11 – fullskjerm av og på medan SNOWMAN køyrer
- **Retta:** «Avslutt fullskjerm» på Windows lukka fullskjermvindauget, men det nye vanlege vindauget kom ikkje opp – føraren hamna i terminalvindauget. Årsak: SNOWMAN lukka og starta Edge på nytt.
- **Endra:** Fullskjerm blir no slått av og på inne i SNOWMAN (nettlesaren sin fullskjerm), utan å lukke eller opne vindauge. Knappen **Fullskjerm / Avslutt fullskjerm** står alltid i verktøylinja og under Innst. › Kart, og verkar i alle visingar (kart, førar, horisont, 3D-terreng, frontrute). Esc går også ut.
- **Nytt:** Valet blir hugsa. Var SNOWMAN i fullskjerm sist, går han i fullskjerm att ved første trykk på skjermen (nettlesaren tillèt ikkje fullskjerm utan eit trykk). Menyval 4 / `--kiosk` gjer det same.
- **Fjerna:** Kiosk-oppstart av nettlesaren og `POST /api/kiosk`.
- **Avgjerd:** Vanleg fullskjerm i staden for kiosk. Føraren kan alltid kome ut med knappen eller Esc, og vindauget blir aldri borte.
- **Testa:** Ekte Chromium (virtuell skjerm): første trykk → fullskjerm, byte av vising i fullskjerm, Avslutt fullskjerm → vanleg vindauge (same vindauge, ope), Fullskjerm igjen.

## 2026-10-04

### PC-prototype v1.6.10 – knapp for å avslutte fullskjerm
- **Nytt:** Knappen **Avslutt fullskjerm** i verktøylinja (og under Innst. › Kart) – berre synleg i fullskjerm. Etter stadfesting blir fullskjermvindauget lukka og SNOWMAN opna i eit vanleg vindauge. Tenesta køyrer vidare utan avbrot. Fungerer utan tastatur (Surface i trakkemaskina).
- **Nytt:** `POST /api/kiosk` – oppstartsprogrammet (`start_snowman.py`) får beskjed, lukkar fullskjermvindauget og opnar vanleg vindauge. Startar ein SNOWMAN utan oppstartsprogrammet, prøver knappen å lukke vindauget sjølv, og elles står det «trykk Alt + F4».
- **Endra:** SNOWMAN opnar nettlesaren med eigen profil (`data/nettlesar`), så vindauga kan lukkast av SNOWMAN og innstillingane i førarskjermen er dei same i fullskjerm og vanleg vindauge. **Merk:** innstillingar som berre låg i nettlesaren (t.d. vald perspektiv, maskinmål) må setjast éin gong til. Kalibrering, terreng og kontroll ligg i tenesta og er uendra.
- **Endra:** `start-snowman.sh` (Linux) brukar no same oppstartsprogram som Windows (`start_snowman.py`). Simulatoren går over TCP på begge.
- **Retta:** Knappen kalla først ein funksjon med same namn som nettlesaren sin `document.exitFullscreen`, og gjorde ingenting. Fanga i testen.
- **Testa:** Ekte Chromium i fullskjerm (virtuell skjerm): knappen er synleg berre i fullskjerm, stadfesting → vanleg vindauge, tenesta køyrer vidare.

### PC-prototype v1.6.9 – Windows-versjon
- **Nytt:** `pc/INSTALLER-WINDOWS.bat` – sjekkar Python (tilbyr installasjon med winget om det manglar), lagar eige Python-miljø (`v1.6\.venv`), installerer bibliotek og lagar snarvegen «SNOWMAN» på skrivebordet.
- **Nytt:** `pc/SNOWMAN.bat` – same meny som `snowman` på Linux: start, demo, test over terrengmodellane, fullskjerm, oppdater og stopp. Førarskjermen opnar i Edge eller Chrome som eige vindauge (fullskjerm med `--kiosk`).
- **Nytt:** `start_snowman.py` – felles oppstart for alle system i Python (simulator, teneste, nettlesar, stopp, meny, versjon). Batch-filene er berre ein tynn inngang.
- **Nytt:** Simulatoren kan sende NMEA over TCP (`--tcp 7777`), og tenesta les `socket://127.0.0.1:7777` som seriellport (pyserial `serial_for_url`). Windows har ikkje virtuelle seriellportar, så demo og test brukar dette der. Ekte Leica brukar COM-porten som før.
- **Retta:** Simulatorporten blir ikkje lenger lagra i innstillingane. Før vart ein seinare vanleg start ståande og vente på simulatoren.
- **Endra:** `v1.6\INSTALL.bat` og `v1.6\START-SNOWMAN.bat` viser vidare til dei nye filene i `pc\`.
- **Nytt:** `pc/LES-MEG-WINDOWS.txt` med installasjon, start, COM-port og oppdatering.
- **Testa:** Oppstart, demo over TCP, stopp, meny og oppdateringstekst frå utpakka zip (på Linux). Batch-filene er ikkje testa på ein ekte Windows-PC enno.
- **Avgjerd:** Krev Python 3.10+ på PC-en (installert av installasjonen). Ei ferdig .exe krev bygging på Windows og kan kome seinare.

### PC-prototype v1.6.8 – ryddigare verktøylinje og versjonsnummer
- **Endra:** Knappen for kartperspektiv viser no perspektivet som er i bruk (t.d. «Kart», «Horisont»). Trykk opnar ein meny med alle fem: Kart, Førar, Horisont, 3D-terreng og Frontrute.
- **Nytt:** Eigen knapp **Bakgrunn** rett ved sida av perspektivknappen – slår bakgrunnskartet (og høgdekurvene i 3D) av og på.
- **Fjerna:** Historikk-knappen i verktøylinja. Historikk ligg under Innst. › Historikk.
- **Endra:** Zoom ut har no eit reint minusteikn utan sirkel, likt plussteiknet på Zoom inn.
- **Nytt:** Versjonsnummeret som er i bruk står rett under «SNOWMAN by Alpindata», i vindaugstittelen, under Innst. › Maskin, i terminalen og i `snowman`-menyen. Éin stad i koden: `APP_VERSION` i driver.html og `VERSION` i snowman_pc.py.
- **Retta:** Tenesta ber nettlesaren alltid hente sida på nytt (`Cache-Control: no-cache`), så ein ny versjon synest med éin gong etter oppdatering.
- **Kvifor:** Ønske frå eigaren etter testing.

### PC-prototype v1.6.7 – kontroll av snødjupne og terrengmodell
- **Nytt:** Fana **Kontroll** (Innst.) med to typar kontroll:
  - **Kontrollmåling her:** maskina står med RTK FIX, føraren skriv inn kjend snødjupne (snøsonde rett under antenna, eller 0 på barmark). SNOWMAN lagrar si eiga utrekning ved sida av og viser avviket (grøn ≤ 5 cm, gul ≤ 15 cm, raud over).
  - **Kontrollpunkt:** kjend koordinat (EUREF89 UTM 32/33/35) og terrenghøgd NN2000 frå landmålar. Terrengmodellen blir samanlikna med punktet utan GNSS. Punkta blir viste på kartet (lilla) med avvik og avstand frå maskina.
- **Nytt:** Statistikk over kontrollmålingane: snittavvik, spreiing og største avvik. Med minst 3 målingar og eit systematisk avvik (≥ 3 cm og større enn spreiinga) kan SNOWMAN justere høgdeoffset med eitt trykk (med stadfesting).
- **Nytt:** Avvika blir alltid rekna mot gjeldande antennehøgd og høgdeoffset, så gamle kontrollmålingar framleis gjeld etter ei justering.
- **Nytt:** `kontroll.py`, API `GET /api/control` og `POST /api/control/check | check/delete | point | point/delete | apply-offset`. Data i `data/kontroll.json` (høyrer til anlegget, skal med i anleggspakka).
- **Nytt:** I testmodus skriv simulatoren den simulerte snødjupna til `data/sim-fasit.json`, og fana viser ho merka «TEST» – så kontrollmåling kan prøvast heime.
- **Testa:** 4 kontrollmålingar med 5 cm kjend feil → snittavvik +4,9 cm, spreiing ±0,5 cm → justering gav høgdeoffset 0,049 m og snittavvik 0. Kontrollpunkt 12 cm under modellen → avvik +12 cm. Ugyldige koordinatar og snødjupner blir avviste.
- **Avgjerd:** SNOWMAN justerer aldri kalibreringa av seg sjølv – berre når føraren stadfestar, og berre når avviket er systematisk.
- **Kvifor:** Utan kontroll mot kjende verdiar veit ein ikkje om snødjupna er til å stole på (t.d. WGS84-forskyving i lysmaster-modellen, ulike modellar som overlappar).

### Oppstart frå terminalen – kommandoen `snowman`
- **Nytt:** `pc/installer-linux.sh` – køyr éin gong. Installerer kommandoen `snowman` (lenkje i `~/.local/bin`) og ein snarveg «SNOWMAN» i programmenyen. Legg `~/.local/bin` til i PATH i `~/.bashrc` om det manglar. Endrar ikkje noko utanfor heimemappa.
- **Nytt:** `pc/snowman` – meny med start (Leica), demo, test over terrengmodellane, fullskjerm, oppdatering frå GitHub og stopp. Kan også brukast direkte: `snowman start | demo | test | oppdater | stopp | hjelp`.
- **Nytt:** Køyrer SNOWMAN alt (t.d. frå eit anna vindauge), blir den gamle stoppa før ny start – elles er porten oppteken.
- **Avgjerd:** Kommandoen ligg i `pc/` og vel den nyaste versjonsmappa (`pc/v1.6`, seinare `pc/v1.7` …), så han treng ikkje installerast på nytt ved ny versjon. `snowman oppdater` brukar `git pull --ff-only`, så lokale endringar aldri blir overskrivne.
- **Kvifor:** Eigaren ville kunne opne SNOWMAN direkte frå terminalen utan å hugse mapper og kommandoar.

### PC-prototype v1.6.6 – frontrute, bakgrunn av og snødjupne framfor maskina
- **Nytt:** Visinga **Frontrute** – 3D frå augehøgd i førarhuset (ca. 2,9 m), fast i køyreretninga, hallar med maskina i sidehelling og bakke. Zoom inn/ut endrar synsfeltet. Utan terrengmodell blir horisont vist.
- **Nytt:** **Bakgrunn av/på** (Innst. › Kart): skjuler bakgrunnskartet, og i 3D blir terrenget mørkt utan høgdekurver. Då synest berre spor og snødjupne.
- **Nytt:** **Snødjupne framfor maskina (estimat)**: vekta snitt (IDW) av målingar SNOWMAN alt har gjort innanfor 10 m (nabolanar og sporet bak). Krev minst 3 målingar og ei innanfor 6 m – elles blir det ikkje vist noko. Vist i 2 × 2 m ruter 4–40 m framfor maskina, blekare enn målt spor på kartet og skravert i 3D. Eigen boks øvst med stipla ramme: «FRAMFOR · ESTIMERT ≈0,62 m, minst 0,25 m · 6–30 m». Kan slåast av under Innst. › Kart.
- **Avgjerd:** Estimatet byggjer berre på eigne målingar i nærleiken – SNOWMAN kan ikkje måle snø der maskina ikkje har vore. Det er alltid merka ESTIMERT og blir aldri lagra som måling.
- **Kvifor:** Eigaren ville kunne skru av bakgrunnen, sjå snødjupna framfor maskina og ha ein førarmodus som er som å sjå ut gjennom frontruta.

### PC-prototype v1.6.5 – fleire visingar og 3D-terreng
- **Nytt:** Fire visingar. Knappen «Førarvising» blar gjennom dei, og under Innst. › Kart kan du velje direkte:
  - **Kart** – ovanfrå (som før).
  - **Førar** – kartet vippa 50° (som før).
  - **Horisont** – vippa 68° med dis-himmel og nærare zoom, så ein ser langt framover.
  - **3D-terreng** – ekte relieff frå terrengmodellen (WebGL). Snøkvitt terreng med lys og skugge og høgdekurver kvar meter (tjukkare kvar 5. m). Sporet blir måla på terrenget i snødjupnefargar. Trakkemaskina er teikna i målestokk (beltebreidd, skjær og fres frå maskininnstillingane) og vippar etter terrenget. Kameraet følgjer bak maskina. Zoom inn/ut flyttar kameraet nærare eller lenger unna.
- **Nytt:** `GET /api/terrain/patch` – terrengutsnitt (300 × 300 m, 1 m rute) rundt maskina frå det høgast prioriterte laget. Testa mot punktoppslag: maks avvik 0,5 mm. Nytt utsnitt blir henta når maskina har køyrt 60 m.
- **Nytt:** `vendor/three.snowman.min.js` – three.js r186 (MIT-lisens), berre dei delane SNOWMAN brukar (540 kB). Lisens i `vendor/THREE-LICENSE`.
- **Avgjerd:** 3D-terreng blir berre teikna der det finst terrengmodell. Utanfor modellen, eller utan terreng (t.d. i demo), blir horisontvisinga brukt automatisk – SNOWMAN dikter ikkje opp terreng.
- **Avgjerd:** Blir verande i mappa `pc/v1.6` (v1.6.5). Terrengbiblioteket ligg i `pc/v1.6/data`, og ei ny mappe ville gjort at det måtte leggjast inn på nytt.
- **Kvifor:** Eigaren ville ha fleire førarmodusar, meir vippa mot horisonten, så ein ser terrenget betre.

### Dokumentasjon – HUD på mobil stadfesta
- **Endra:** LES-MEG: skriv HUD-adressa med `http://` først. Testa av eigaren: HUD virkar på mobil etter `sudo ufw allow 8766/tcp` på Omarchy.

### PC-prototype v1.6.4 – test over ekte terrengmodell (simanlegg)
- **Nytt:** `./start-snowman.sh simanlegg` – den simulerte Leica-mottakaren køyrer over det øvste aktive terrenglaget i biblioteket (t.d. Topocad-modellane frå Fjellsætra). Høgda er ekte terreng + simulert snø (ca. 0,4–1,2 m og eit tynt felt) + antennehøgd. Lanane følgjer lengderetninga til modellen og held seg innanfor han. Når du legg inn eller endrar prioritet på eit lag, flyttar maskina seg dit innan nokre sekund.
- **Nytt:** Tenesta veit når mottakaren er simulatoren (`--simulert`, set automatisk av `sim`, `simterreng` og `simanlegg`). Førarskjermen viser då «TEST – SIMULERT MOTTAKAR OG SNØ», snødjupna heiter «SNØDJUPNE (TEST)» med «SIMULERT SNØ», HUD viser «DEMO – SIMULERT», og øktene blir lagra som demo.
- **Kvifor:** Eigaren ville teste terrengmodellane i demomodus. Før køyrde simulatoren berre over testterrenget, og simulert mottakar vart vist som ekte måling – det bryt regelen om at simulert snødjupne aldri skal sjå ut som ekte.
- **Testa:** Familietrekk, parkeringsplass og lysmaster: 100 % av ruta innanfor modellen. Snødjupne i tenesta lik simulert snø (0,78–0,84 m), FLOAT-perioden gir «IKKJE MÅLT – KREV RTK FIX».

### PC-prototype v1.6.3 – stadfesta høgdesystem blir lagra
- **Endra:** Når føraren hakar av «Eg har sjekka at høgdene er NN2000» ved import, blir laget lagra som «NN2000 (stadfesta)» i staden for «ukjent». Det synest i terrenglista og i oppslaga.
- **Avgjerd (eigar):** Topocad-filene frå Fjellsætra er i NN2000. Parkeringsmodellen er EUREF89 UTM 32N. Lysmaster-modellen er verkeleg WGS84 UTM 32N. Med 37 % median helling gir ei forskyving på ca. 0,9 m om lag 30 cm høgdefeil der, så modellen blir berre brukt til oversikt. Ingen automatisk WGS84→EUREF89-omrekning no: ho krev kva år punkta vart målte. Kontrollpunkt (v1.7) skal avdekkje slike skilnader.

### PC-prototype v1.6.3 – import av Topocad DTM
- **Nytt:** Terrengbiblioteket les Topocad-terrengmodellar (`.dtm`, trekantmodell/TIN). Trekantane blir gjorde om til eit 0,5 m rutenett ved import, berre innanfor modellen (ingen gjetting utanfor kanten). Bruddlinjer er med i trekantane.
- **Nytt:** Koordinatsystemet blir lese frå fila (EPSG). Manglar EPSG-koden, blir sona tolka frå namnet (t.d. «EUREF UTM 32») og føraren får ei åtvaring.
- **Nytt:** Åtvaringar ved import: Topocad oppgir ikkje høgdesystem (stadfest NN2000), fil merkt WGS84 kan liggje ca. 0,9 m forskyvd, og modellar med under 200 punkt er for grove til snødjupnemåling.
- **Endra:** Fana «Terreng» viser Topocad DTM som godteke format.
- **Testa:** Dei to filene frå Drive (Fjellsætra). «Terrängmodell parkeringsplass»: 9 265 punkt, 17 591 trekantar, 338–366 m, 0,15 km². Oppslag i tenesta mot modellen: maks avvik 1,4 cm (200 punkt). «Terreng fra lysmaster»: berre 36 punkt – berre til oversikt. GeoTIFF-import uendra.
- **Avgjerd:** Topocad-formatet er lese ut frå sjølve fila (ingen tredjepartskode). Formatet er ikkje offentleg dokumentert, så nye Topocad-versjonar må testast.

### PC-prototype v1.6.2 – HUD utan avbrot, HUD-knapp og HUD på mobil
- **Retta:** HUD viste av og til «VENTAR PÅ SNOWMAN». Årsak: nettlesaren bremsar førarskjermen når han ligg i bakgrunnen, og HUD fekk data derifrå. No set tenesta saman HUD-dataa sjølv – GNSS, fart, kurs og snødjupne kjem direkte frå mottakaren. Førarskjermen leverer berre prepareringsstatus. Ventemeldinga viser no årsaka.
- **Nytt:** Knappen «HUD» i verktøylinja: opne HUD på same PC (eigen skjerm), eller slå på «HUD på mobil» med QR-kode og adresse.
- **Nytt:** HUD på mobil/nettbrett går via ein eigen port (8766) på lokalnettet som **berre** viser HUD-sida og HUD-data. Styring og innstillingar er framleis berre tilgjengelege på PC-en (testa: 403 på alt anna). Valet blir hugsa.
- **Endra:** Hovudtenesta lyttar no alltid berre på PC-en sjølv (127.0.0.1). `--lan` / `LAN=1` slår på mobil-HUD-porten.
- **Nytt:** QR-kodebibliotek `vendor/qrcode.js` (MIT-lisens, Kazuhiko Arase).
- **Endra:** Rettleiing om brannmur i HUD-vindauget og LES-MEG (Omarchy har brannmur på som standard: `sudo ufw allow 8766/tcp`).
- **Avgjerd:** Mobil under HUD-film er tilrådd første HUD-løysing. Mobilen er berre skjerm – han kan ikkje styre SNOWMAN.

### PC-prototype v1.6.1 – lås kartrotasjonen
- **Nytt:** Kompassknapp øvst til høgre på kartet: trykk for å låse kartet med nord opp, eller la det rotere etter køyreretninga. Nålen viser alltid kvar nord er. Valet blir hugsa.
- **Endra:** Når kartet er låst, snur maskinteikninga seg etter køyreretninga i staden. Fungerer òg i førarperspektivet.
- **Retta:** Kartet snurra ein heil runde når kursen passerte nord (t.d. 359° → 1°). No blir vinkelen halden samanhengande, så kartet tek alltid den korte vegen.
- **Endra:** Mjukare rotasjon (0,4 s).

### PC-prototype v1.6 – Terrain Engine (ekte snødjupne)
- **Nytt:** `terrain.py` – terrengbibliotek med fleire lag: legg til, erstatt (eldre versjon blir teken vare på), slå av/på, prioritet og slett. Oppslag med interpolasjon frå det høgast prioriterte laget som har data.
- **Nytt:** Snødjupne = (GNSS-høgd − antennehøgd − høgdeoffset) − terrenghøgd, rekna i den lokale tenesta for kvar GNSS-posisjon. Vist i spor (fargar), førarskjerm og HUD, og lagra i arbeidsøktene.
- **Nytt:** Opplasting med analyse i fana «Terreng»: format, koordinatsystem (EUREF89/WGS84 UTM 32/33/35), høgdesystem (NN2000/NN54/ukjent), oppløysing, nodata, dekning av maskinposisjonen. Krev stadfesting når høgdesystemet er ukjent. Omriss av laga på kartet.
- **Nytt:** Kalibrering lagra i tenesta: antennehøgd, høgdeoffset, høgdekjelde (NN2000 eller ellipsoidisk + geoidehøgd).
- **Nytt:** `testterreng.py` (syntetisk bakke ved Fjellsætra) og `simuler-leica.py --terreng` med fasit-snødjupne. `./start-snowman.sh simterreng`.
- **Nytt:** `start-snowman.sh` lagar eige python-miljø (.venv) og installerer bibliotek automatisk.
- **Testa:** Snittavvik −0,1 cm, maks 2,1 cm mot fasit (simulert RTK-støy ca. 1 cm). Same resultat med lag i UTM-sone 33. Koordinatomrekning kontrollert mot pyproj: under 1 mm avvik.
- **Avgjerd:** Snødjupne blir berre vist når RTK FIX, terrengdekning og lagra kalibrering er på plass – elles blir årsaka vist.
- **Avgjerd:** Bibliotek: numpy, tifffile og imagecodecs (BSD-lisens). LAS/LAZ og XYZ kjem i v1.7.
- **Kjent avgrensing:** Horisontal antenneoffset og pitch/roll er ikkje med enno.

### Spesifikasjon: Terrain Engine
- **Nytt:** `docs/TERRAIN-ENGINE.md` – terrengbibliotek (legg til, erstatt, av/på, prioritet), typar flater (barmark, målflate, snøflate), opplastingsveivisar med formatkrav, fallgruver (UTM 32/33, NN2000 vs. ellipsoidisk høgd), trasear og anleggsobjekt, og rekkjefølgje v1.6–v1.8.
- **Avgjerd:** Terreng blir lagt inn som eit bibliotek med fleire lag og prioritet, ikkje som éi fil.
- **Avgjerd:** GeoTIFF er tilrådd format. LAS/LAZ og XYZ blir gjort om til rutenett ved import.
- **Avgjerd:** Snødjupne blir berre vist når RTK FIX, terrengdekning og kalibrering er på plass.
- **Avgjerd:** Trasear (ytterpunkt/omriss) og anleggsobjekt skal kunne registrerast – køyre og registrere, teikne på kart, eller importere fil.

### PC-prototype v1.5.2 – førarperspektiv og HUD
- **Nytt:** Førarperspektiv (knappen «Førarvising»): kartet blir vippa 50° og vist frå bak og over maskina, med horisont. Alltid køyreretning opp, zoomar nært maskina. Sporflate, piler og snødjupnefargar følgjer med i 3D.
- **Nytt:** HUD-versjon for frontruta (`hud.html`, opnast på `/hud`). Eiga side som kan køyre på eigen skjerm eller mobil på dashbordet: store tal for snødjupne og avvik frå måldjupne (✓ på mål / ▼ under / ▲ over), fart, kurs, RTK-status, prepareringstid. Spegling for HUD-film, nattmodus i dempa raudt, lysstyrke, fullskjerm, skjermen held seg vaken.
- **Nytt:** Førarskjermen sender tilstanden til den lokale tenesta (`/api/hud`), og HUD-en les derifrå. `--lan` / `LAN=1` gjer HUD tilgjengeleg for andre einingar i same nett.
- **Avgjerd:** HUD er skild ut som eigen versjon/side, så førarskjermen og HUD kan utviklast og testast kvar for seg.
- **Avgjerd:** HUD viser same reglar som førarskjermen: snødjupne berre som tal i demo (merka DEMO) til Terrain Engine finst. Nattmodus er dempa raud for å skåne nattsynet.
- **Avgjerd:** Ekte 3D-terreng (bakkar og kantar) kjem saman med Terrain Engine når LiDAR-modellen finst.

### PC-prototype v1.5.1 – spor som følgjer zoom
- **Retta:** Sporet etter maskina hadde fast breidd i pikslar og vart altfor breitt når ein zooma ut. No blir sporet teikna som ei flate i meter (fresbreidd), så det har rett storleik på alle zoomnivå og er like breitt som maskinteikninga.
- **Retta:** Overlappande spor vart mørkare. No blir all preparert flate vist med jamn farge, så opne felt synest tydeleg.
- **Retta:** Demoen la lanane med litt for stor avstand, slik at det vart smale opne felt. No ligg lanane med 0,2 m overlapp.
- **Endra:** Piler for køyreretning blir skjulte og senterlinja tynnare når ein zoomar langt ut.
- **Avgjerd:** Opne felt mellom spor skal berre visast når fres/utstyr faktisk ikkje har dekt flata.

### PC-prototype v1.5 – Linux-testpakke
- **Nytt:** `simuler-leica.py` – virtuell Leica (NMEA GGA, RTK FIX) for testing utan mottakar.
- **Endra:** `start-snowman.sh` har testmodus (`./start-snowman.sh sim`), sjekkar at pyserial finst, opnar vanleg vindauge som standard og fullskjerm med `KIOSK=1`, og stoppar tenesta når skriptet blir avslutta.

### PC-prototype v1.5 – kartkjelder og anleggsprofil
- **Nytt:** Val av kartkjelde per anlegg (Innstillingar › Kart): Kartverket topo/gråtone, lokale offline-kartfliser (`data/tiles`), eiga XYZ/WMTS- eller WMS-kjelde, OpenStreetMap (berre test) eller berre rutenett.
- **Nytt:** Anleggsprofil – eksporter alle innstillingar til ei fil og importer på dei andre maskinene på anlegget.
- **Avgjerd:** SNOWMAN skal kunne seljast til ulike anlegg og trakkemaskiner. Kart og maskinoppsett må difor kunne konfigurerast utan kodeendring.
- **Avgjerd:** OpenStreetMap sine kartfliser skal ikkje brukast i produktet (vilkåra tillèt ikkje kommersiell bruk).

### Lisens
- **Nytt:** `LICENSE` – alle rettar reserverte, bruk berre etter skriftleg lisensavtale. Copyright-linje i hovudfilene.
- **Avgjerd:** Repoet bør gjerast privat. Lisensnøkkel per maskin (signert, verkar offline) kjem seinare.

### PC-prototype v1.5 – v24-grensesnitt kopla til Leica/GNSS
- **Endra:** PC-versjonen bruker no same førargrensesnitt som Driver v24 (krav: «Alle funksjoner som virka i html varianten skal også virke i prototype. Husk å bruke samme layout»). Éi samla fil, hentar ikkje lenger kode frå GitHub ved oppstart.
- **Nytt:** Maskina følgjer GNSS-posisjonen frå den lokale tenesta. Spor, distanse, areal, fart og kurs blir rekna frå ekte posisjonar.
- **Nytt:** Fix, satellittar og HDOP frå mottakaren. Gult/raudt varsel utan RTK FIX. Varsel når GNSS-data stoppar.
- **Nytt:** Kalibrering (maskinnamn, antenne X/Y/Z, høgdeoffset) og LiDAR/terreng-registrering frå v1.4 som faner i innstillingane.
- **Nytt:** Arbeidsøkter blir lagra som filer på PC-en (`data/sessions`). Innstillingar (seriellport, NTRIP) blir hugsa mellom omstartar.
- **Nytt:** Areal-felt, kartretning nord opp / køyreretning opp, wake lock (skjermen sovnar ikkje), oppstart på Linux i Chromium kioskmodus (`start-snowman.sh`).
- **Nytt:** Leaflet ligg lokalt – appen startar utan nett.
- **Retta:** Maskinteikninga er i målestokk (fresbreidd = sporbreidd).
- **Retta:** Innstillingar frå v22/v23 gjekk tapt (feil lagringsnøkkel).
- **Retta:** Historikken kunne fylle nettlesarlageret og stoppe loggføringa.
- **Retta:** Distansen auka når maskina stod i ro (GPS-støy). No filter på minste flytting og dårleg nøyaktigheit.
- **Retta:** Kompass og GPS-kurs kjempa om kartrotasjonen. No styrer GNSS-kursen under køyring.
- **Retta:** «Start prep» under demo, og melding om lagring når ingenting vart lagra.
- **Endra:** Snødjupne blir vist som **IKKJE MÅLT** under ekte køyring, og sporet er nøytralt blått. Fargar og tal berre i demo, merka «DEMO – SIMULERTE DATA».
- **Avgjerd:** Simulert snødjupne skal aldri sjå ut som ekte måling.

### Opprydding
- **Nytt:** PC-prototype v1.2–v1.4 og SNOWMAN NTRIP Service v1.1 lagt inn i repoet (låg tidlegare berre som nedlastingar frå utviklinga i ChatGPT).
- **Avgjerd:** GitHub er staden for kode. Google Drive blir brukt til dokument (forretningsplan, investorpresentasjon).

---

## 2026-09-30

### PC-prototype v1.1 – v1.4 (utvikla i ChatGPT, lagt inn i repoet 2026-10-04)
- **v1.1:** PC-panel oppå v24 med Leica/NMEA via Web Serial, test-NMEA, NTRIP-test og terrengfil.
- **v1.2:** Éin samla oppstart (`START-SNOWMAN.bat`) med lokal Python-teneste. Grensesnittet vart for forenkla.
- **v1.3:** Forsøk på v24-layout + lokal GNSS/NTRIP-teneste.
- **v1.4:** Offline-kartidé, LiDAR-filval (LAS/LAZ/PLY/XYZ/CSV) med koordinat- og høgdesystem, maskinkalibrering. Kartet var eit rutenett, sporet og distansen var simulerte, og v24-layouten var ikkje med.
- **Nytt:** SNOWMAN NTRIP Service v1.1 – Python-bru mellom COM/Leica (NMEA GGA) og CPOS/NTRIP (RTCM).
- **Avgjerd:** Leica GS07 via RS232/NMEA skal støttast, men SNOWMAN skal vere leverandøruavhengig.
- **Avgjerd:** Mobil/HTML er demo og utviklingsverktøy. Sluttproduktet køyrer på PC i trakkemaskina (første kandidat: Surface Pro 1796 med lett Linux).

### Driver v20 – v24 (mobil/HTML)
- **v24:** Kartet roterer etter køyreretninga. Start/Stopp preparering – spor blir berre logga under aktiv preparering. Reset spor. Satellittstatus-panel. Samanhengande spor i fresbreidd i staden for boblar.
- **v23:** Satellittstatus og samanhengande dekningsspor.
- **v22:** Tidsbruk, piler for køyreretning, trakkemaskin-ikon.
- **v21:** Demo-område 300 × 50 m og avspeling av spor sortert på dato.
- **v20:** Retta av/på for snødjupne.

## 2026-09-29

### Snowman v2 – v19 (mobil/HTML)
- **v16–v19:** Fullskjerm førar-cockpit, innstillingsfaner, kart med køyreretning opp, vis/skjul maskin, klikkbar GPS-status.
- **v12–v15:** Gjennomsiktig trakkemaskin, justerbar maskinbreidd (5,5 m), skjer- og fresbreidd, snødjupneskala i seks nivå, utviklarnamn flytta til innstillingar.
- **v9–v11:** Mobil investorprototype, førarvisning med synleg trakkemaskin, kart med køyreretning opp.
- **v4–v8:** Terrenghøgd frå Kartverket Høydedata, terrengproxy (Cloudflare Worker), betre feilhandtering og 20 s timeout.
- **Avgjerd:** Geonorge/Kartverket-oppslag feila med timeout. Terrenget skal i staden kome frå eigen LiDAR-modell lagra lokalt.
- **v2:** Første versjon av Snowman by Alpindata.

---

## Planlagt

- **v1.6.2:** Kartverket DTM 1 m for Fjellsætra (frå hoydedata.no).
- **v1.7:** LAS/LAZ- og XYZ-import, kontrollpunkt, anleggspakke, horisontal antenneoffset.
- **v1.8 Trasear og anleggsobjekt.**
- Ekte 3D-terreng i førarperspektivet (frå LiDAR).
- HUD-test i maskina: lesbarheit natt/dag, dobbeltbilete i buet frontrute.
- Fleire maskinprofilar per anlegg.
- Lisensnøkkel per maskin.
- Felttest: RTK + LiDAR mot manuelt målt snødjupne.
