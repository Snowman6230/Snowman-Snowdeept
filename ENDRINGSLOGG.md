# Endringslogg – SNOWMAN by Alpindata

Alle endringar i SNOWMAN blir førte her, med den nyaste øvst.
Kvar oppføring seier **kva** som vart endra og **kvifor**. Detaljane står i git-historikken.

Merke: **Nytt** · **Endra** · **Retta** · **Fjerna** · **Avgjerd** (val som styrer vidare utvikling)

---

## 2026-10-09

### Avgjerd – RTK i SNOWMAN (ingen kodeendring)
- **Avgjerd:** eigaren vil at SNOWMAN skal rekne RTK sjølv, og at det skal vere mottakaruavhengig (rådata som RTCM 3
  MSM). Planen er RTKLIB demo5 (BSD-2) i `pc/v1.7`, med «RTK i mottakaren» som val.
- Arbeidet ventar til Zenith35 Pro fungerer med dagens løysing. Sjå docs/VEGEN-VIDARE.md kap. 15.

### PC-prototype v1.6.88 – hald tilbake antennemeldingar som mottakaren ikkje godtek
- **Funn:** Zenith35 Pro svarte `@GNSS,ADVNULLANTENNA,ERROR` på korreksjonane. «ADVNULLANTENNA» er antennenamnet til
  basen i RTCM 1008/1033. Det tyder at mottakaren faktisk les korreksjonane frå SNOWMAN over Bluetooth, men ikkje
  godtek antennenamnet. Det tidlegare «LANTENNA» var same feilen, avkorta. Konklusjonen i v1.6.87, at Zenith-en ikkje
  tek imot korreksjonar over Bluetooth, er difor truleg feil.
- **Nytt:** feltet «Ikkje send desse RTCM-typane til mottakaren» på NTRIP-sida (`rtcm_drop`, t.d. «1008,1033»).
  Rammene blir haldne tilbake i `RtcmMonitor.feed(drop=…)`. Statusen viser kva som er halde tilbake.
  Korreksjonane (1004/1012, 1006, 1230) blir sende som før.
- **Nytt:** `rtk_hint` kjenner att `…ANTENNA,ERROR` og føreslår «1008,1033».
- **Endra:** hjelpeteksten om Zenith35 Pro er oppdatert.
- **Avgjerd:** feltet er tomt som standard. Andre mottakarar treng antenneinformasjonen.
- Testa:
  - einingstest: 1008/1033 blir haldne tilbake, 1004/1006/1012 går vidare
  - feltet blir lagra og lese inn att
  - `simuler-leica.py --anlegg` gav RTK FIX
  - Playwright utan JS-feil

### PC-prototype v1.6.87 – funn frå felttest: Zenith35 Pro og korreksjonar over Bluetooth
- **Funn (felttest 9.10.2026, Surface + GeoMax Zenith35 Pro):**
  - Posisjon (GGA) kjem stabilt over Bluetooth (utgåande COM4), opp til 26 satellittar.
  - Korreksjonane frå casteren er feilfrie (basen TH, RTCM 3, GPS+GLONASS), og SNOWMAN sender dei som reine RTCM-rammer.
  - Zenith-en brukar dei likevel ikkje. Han står i GPS/SBAS, Status Info viser «Datalink Status: Disconnected» med
    «Datalink: Bluetooth», og mottakaren svarar `@GNSS,…,ERROR` på korreksjonsdataa.
  - Den innkommande porten (COM3) blir ikkje brukt av mottakaren.
  - Landnova X på Mesa2 gav RTK FIX med same base, men mot ein Xsite ROVER V2, ikkje mot Zenith-en.
- **Avgjerd:** for Zenith35 Pro tilrår SNOWMAN no RTK Data Source = GSM/GPRS (SIM-kort og NTRIP-oppsett i mottakaren)
  eller External (kabel). SNOWMAN les då berre posisjonen. Working Mode skal vere RTK Rover, aldri RTK Base på maskina.
  Kjem det fram ein GeoMax-kommando som opnar Bluetooth-datalinken, kan han leggjast i «Oppstartskommandoar».
- **Endra:** hjelpeteksten på NTRIP-sida og diagnosen (`rtk_hint`) seier dette, i staden for at Zenith-en «treng
  ingen kommandoar».
- Testa med `simuler-leica.py --anlegg` (RTK FIX, inga åtvaring). Playwright gav ingen JS-feil.

### PC-prototype v1.6.86 – retting: SNOWMAN koplar til mottakaren på nytt av seg sjølv
- **Retta (feil i SNOWMAN):** Etter at Zenith35 Pro vart starta på nytt, kom det aldri posisjon igjen. Det stod
  «NO DATA, SAT 0» og «Write timeout» heilt til SNOWMAN sjølv vart starta på nytt. Årsaka: når mottakaren startar på
  nytt, døyr Bluetooth-sambandet utan at Windows lukkar porten. SNOWMAN las difor ingenting frå ein «open» port i det
  uendelege. NTRIP-delen var i orden, men fekk ikkje skrive korreksjonane til den døde porten.
- **Nytt:** vakthund på mottakarporten. Kjem det ingen data på 15 s, blir porten lukka og opna på nytt. Mottakarar
  sender minst éin gong i sekundet, så 15 s stille tyder at sambandet er dødt. Er mottakaren framleis av, prøver
  SNOWMAN igjen kvart 2. sekund med forklaringa frå v1.6.81.
- **Nytt:** tre feil på rad når NTRIP skriv korreksjonar til mottakaren, opnar òg porten på nytt.
- **Retta:** «LAGRE / KOPLE TIL» koplar no alltid til mottakaren på nytt. Før skjedde det berre når port, baud eller
  oppstartskommandoar var endra.
- **Nytt:** statusen på NTRIP-sida viser kor mange gonger porten er opna på nytt, og når det skjedde sist.
- Testa med `simuler-leica.py --anlegg`:
  - simulatoren fryst i 19 s: porten vart opna på nytt etter 15 s, og RTK FIX kom tilbake då data kom att
  - «LAGRE / KOPLE TIL» med same port koplar til på nytt
  - Playwright gav ingen JS-feil

### PC-prototype v1.6.85 – forklaring for MANUELL og nøytrale namn
- **Bakgrunn:** Etter omstart av Zenith35 Pro viste SNOWMAN «MANUELL» (GGA-kvalitet 7). Diagnosen sa då at mottakaren
  «får korreksjonar men brukar dei ikkje». Det var misvisande, for kvalitet 7 er ein fast eller innlagd posisjon og
  ikkje ei måling.
- **Nytt:** `rtk_hint` har eiga forklaring for MANUELL. Ho ber føraren sjekke at Working Mode = RTK Rover (ikkje Base
  eller Static), og at RTK Data Source er den vegen korreksjonane kjem: Bluetooth frå SNOWMAN, eller GSM/GPRS med
  eige SIM-kort og NTRIP-oppsett i mottakaren.
- **Endra:** «Leica/GNSS» i fix-boksen og i meldingane er bytt til «GNSS» eller «GNSS + NTRIP», fordi SNOWMAN er
  leverandøruavhengig.
- Testa med `simuler-leica.py --anlegg` (RTK FIX, inga åtvaring). Playwright gav ingen JS-feil.

### PC-prototype v1.6.84 – skarpare diagnose: mottakaren les ikkje korreksjonane
- **Bakgrunn:** Med v1.6.83 kom berre reine RTCM-rammer fram til Zenith35 Pro. Teksten frå casteren (`Ntrip-Version`,
  `Server: NTRIP Caster 1.0`, `Date`, `Content-Type`) vart halden tilbake. Mottakaren stod likevel i SBAS, med
  base-ID 0121 (EGNOS).
- **Nytt:** `rtk_hint` kjenner att ein base-ID mellom 120 og 158, som er ein SBAS-satellitt. Då seier SNOWMAN rett ut
  at mottakaren ikkje les korreksjonane i det heile, og at feilen ligg i korreksjonsinngangen på mottakaren, ikkje i
  sikta. Ein mottakar som les RTCM frå basen, brukar basen (DGPS/FLOAT) sjølv med dårleg sikt.
- **Nytt:** «Svar frå mottakar» viser kor gammalt svaret er. Eit gammalt `@GNSS,…,ERROR` blir ikkje lenger forveksla
  med eit nytt.
- Testa med `simuler-leica.py --anlegg` (RTK FIX, inga åtvaring) og `rtk_hint` med base-ID 0121 og 0000.

### PC-prototype v1.6.83 – berre reine RTCM-rammer til mottakaren
- **Bakgrunn:** I felttest (basen var 0,82 km unna, korreksjonane gyldige) stod Zenith35 Pro framleis i SBAS. GGA viste
  base-ID 0121, som er EGNOS-satellitten, ikkje basen. Mottakaren svarte `@GNSS,DN,ERROR`. SNOWMAN sende rådataa frå
  casteren uendra vidare, og då kom òg 110 byte som ikkje var RTCM. Det kan vere tekstlinjer etter «ICY 200 OK»
  (t.d. `Server:` og `Date:`). Mottakaren tolka dette som kommandoar.
- **Endra:** `RtcmMonitor.feed()` returnerer no berre heile RTCM 3-rammer med rett CRC. Det er berre desse som blir
  sende til mottakaren. Tekst, øydelagde rammer og andre byte blir haldne tilbake.
- **Nytt:** NTRIP-sida viser tekst frå casteren som ikkje blir send vidare («Tekst frå casteren: …»), til diagnose.
- **Avgjerd:** mottakaren skal aldri få anna enn kontrollerte korreksjonar frå SNOWMAN. Ei øydelagd ramme er verre
  enn ei som manglar.
- Det er ikkje stadfesta at dette åleine gir RTK FIX. Antenna låg inne i bilen, og innstillinga for
  korreksjonsinngang i mottakaren er ikkje kontrollert.
- Testa:
  - einingstest av filteret med casterhovud, øydelagd ramme og oppdelte bitar (berre gyldige rammer går vidare)
  - `simuler-leica.py --anlegg` (RTK FIX som før)
  - Playwright utan JS-feil

### PC-prototype v1.6.82 – kvifor manglar RTK FIX? Diagnose av heile kjeda
- **Bakgrunn:** Etter at Bluetooth fungerte, viste Zenith35 Pro «SBAS» (GGA-kvalitet 9) med 10 satellittar. NTRIP var
  tilkopla med gyldige RTCM-korreksjonar, men det kom ingen snødjupne, sidan snødjupne krev RTK FIX. Sjølve
  avgrensinga er rett og blir ikkje endra: utan RTK FIX blir det ingen snødjupne.
- **Nytt:** `rtk_hint()` vurderer heile kjeda når det ikkje er RTK FIX. Vurderinga blir vist i GNSS-panelet og på
  NTRIP-sida, og skil mellom:
  - mottakaren er ikkje tilkopla
  - ingen NTRIP
  - korreksjonane er ikkje i orden
  - korreksjonane blir ikkje sende vidare til mottakaren
  - mottakaren får korreksjonar men brukar dei ikkje (antenna utan fri sikt, eller feil innstilling i mottakaren)
  - RTK FLOAT: vent med fri sikt
- **Nytt:** NTRIP-sida viser byte sende til mottakaren. Ho viser òg om mottakaren sjølv brukar korreksjonar
  (korreksjonsalder og base-ID frå GGA-felt 13–14, som SNOWMAN alt las). SBAS kan òg fylle feltet, og då står det.
- **Endra:** Kjelde i GNSS-panelet viser «GNSS + NTRIP» i staden for «Leica + CPOS». SNOWMAN er leverandøruavhengig,
  og korreksjonane kan kome frå andre enn CPOS.
- Testa med `simuler-leica.py --anlegg` (RTK FIX, ingen åtvaring) og `rtk_hint` mot tilstandane over. Playwright
  gav ingen JS-feil.

### PC-prototype v1.6.81 – forklaring når mottakarporten ikkje opnar
- **Bakgrunn:** På Surface med GeoMax Zenith35 Pro over Bluetooth fekk SNOWMAN berre feilen
  `could not open port 'COM4': FileNotFoundError(2, 'Systemet finner ikke angitt fil.')`. Porten (UTGÅANDE COM4)
  var likevel rett. Med ein Bluetooth-port tyder feilen at Windows ikkje får samband med mottakaren.
- **Nytt:** `serial_explain()` legg ei forklaring på norsk til feilen, med kva føraren kan gjere. Forklaringa er
  vist både under «Feil» og i Innst. › GNSS. Ho dekkjer:
  - Windows får ikkje opna porten: mottakaren er av eller langt unna, er kopla til ei anna eining (han tek berre éi
    Bluetooth-tilkopling om gongen), eller må parast på nytt
  - porten er oppteken av eit anna program
  - tidsavbrot på Bluetooth (feil 121)
  - feil på nettverksport (socket)
- **Endra:** same mottakarfeil blir no skriven i feltloggen berre når han endrar seg, eller kvart 5. minutt. Før
  vart han skriven kvart 2. sekund, sidan SNOWMAN prøver å kople til igjen så ofte.
- Testa med `simuler-leica.py --anlegg` (RTK FIX som før) og forklaringane mot feiltekstane frå Windows.

### PC-prototype v1.6.80 – Vêr: vel stad sjølv
- **Nytt:** knappen «📍» i hovudet på Vêr opnar eit stadpanel. Eigaren ønskte å kunne velje staden vêret gjeld for.
  Desse vala finst:
  - **Maskina (automatisk)** – som før: GNSS, så sist kjende posisjon, så midten av terrengmodellen.
  - **Lagra stader** – dei siste 20 vala, nyaste først. Kvar stad kan fjernast med ✕.
  - **Terrengmodellar** – midten av kvart aktive barmark-lag i biblioteket.
  - **Søk i stadnamn** – Sentralt stadnamnregister hos Kartverket (CC BY 4.0, kjelda er vist). Søket krev nett. Utan
    nett får føraren forklaring på norsk og blir vist vidare til vala under.
  - **Midten av kartet** og **koordinatar** («62.28, 6.60» eller «62,28; 6,60», valfritt «, 900» for moh.). Begge
    fungerer utan nett.
- Den valde staden blir hugsa i `data/ver-stad.json` (høyrer til anlegget, ikkje i git) til føraren vel «Maskina»
  igjen. Han gjeld varselet og «Målt no». Hovudet viser «📍 namn», og «ved maskina» blir «ved staden».
- **Avgjerd:** høgda for ein vald stad kjem frå terrengmodellen når staden ligg inne i han. Elles kjem ho frå den som
  er oppgitt, eller frå høgdemodellen til MET. GNSS-høgda til maskina blir aldri brukt for ein stad ein annan plass.
- **Avgjerd:** snøkartet og AI følgjer framleis alltid terrengmodellen og maskina (jf. avgjerda om at terrengmodellen
  er knytt til alle funksjonane i Vêr). Stadvalet gjeld berre varselet og stasjonsmålingane.
- **Retta:** stadfunksjonen frå v1.6.78 heitte `where()`, same namn som hjelpefunksjonen som skriv fil og linje i
  feilloggen, og skugga han. Feilloggen ville då ha fått rot i staden for kodestad. Han heiter no `stad()`.
- Testa i isolert kopi utan GNSS og med `simuler-leica.py --anlegg`:
  - alle vala, lagring, sletting, ugyldig innhald og attende til automatisk
  - Playwright utan JS-feil
- Ikkje testa mot ekte teneste: stadnamnsøket er testa mot eit lokalt testsvar i Kartverket-formatet, fordi nettet
  er stengt her.

### PC-prototype v1.6.79 – retting: sertifikatfeil mot MET på Windows
- **Retta:** «Test samband» på Surface viste `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`
  mot både api.met.no og frost.met.no. DNS var OK, det var ingen proxy, og klokka var rett. Årsaka er at Python på
  Windows berre ser rotsertifikata som alt ligg i Windows-lageret. Windows hentar manglande rotsertifikat først når
  ein nettlesar treng dei. Difor kan Edge opne sida medan SNOWMAN blir avvist.
- **Nytt:** `nett.context()` og `nett.urlopen()`. Alle HTTPS-kall (MET-varsel, Frost, «Test samband» og nedlasting
  av oppdatering i `start_snowman.py`) lèt no Windows sjølv kontrollere sertifikatet, same som nettlesaren. Dette
  skjer via biblioteket truststore. Testen viser kva sertifikatlager som er i bruk.
- **Avgjerd:** Sertifikatkontrollen blir aldri slått av. Vi brukar sertifikatlageret i systemet i staden for å
  leggje ved ein eigen sertifikatbunt, slik at det òg fungerer bak brannmurar og antivirus som har eigne sertifikat.
- **Tredjepart:** truststore 0.10.1 (MIT, Seth Michael Larson), lagt urørt i `vendor/truststore/` med lisensen i
  `vendor/TRUSTSTORE-LICENSE`. Han ligg i mappa sjølv, for oppdateringa køyrer ikkje `pip` på nytt. Han krev
  Python 3.10 eller nyare, same krav som installasjonen. Manglar han, blir standard Python brukt som før.
- Testa i isolert kopi med `simuler-leica.py --anlegg`. TLS mot pypi.org fungerer gjennom den nye konteksten.
  Windows-lageret kan ikkje testast her og må stadfestast på Surface.

### PC-prototype v1.6.78 – retting: Vêr hentar data sjølv utan GNSS, og test av samband
- **Retta:** Vêr-knappen opna overlayet, men henta ingen data på Surface. Den sannsynlege årsaka var at GNSS var av:
  `/api/weather` svarte «Ingen posisjon frå GNSS endå» og spurde aldri MET. No blir staden vald i denne rekkjefølgja
  (ny funksjon `where()` i `snowman_pc.py`): oppgitt stad → GNSS → sist kjende posisjon (`data/sist-posisjon.json`, lagra
  kvart 5. min når GNSS er på) → midten av terrengmodellen. Det same gjeld stasjonsmålingar, snøkart og AI.
  Vêr-hovudet viser kvar staden kjem frå når GNSS er av.
- **Nytt:** `nett.py` forklarar nettverksfeil på norsk (ikkje nett/DNS, sertifikat/klokke, proxy/brannmur, avvist av
  tenesta, tidsavbrot). Feilmeldingane frå MET-varsel og Frost brukar denne forklaringa.
- **Nytt:** knappen «🔌 Test samband» i Vêr når det ikkje er kontakt. Han testar api.met.no og frost.met.no
  (`/api/nettest`) og viser resultat, DNS, proxy og stad. Er alt OK, blir vêret henta på nytt.
- **Avgjerd:** Vêr skal fungere utan GNSS. Terrengmodellen er god nok som stad for varsel og stasjonar.
- Testa i isolert kopi utan GNSS (midten av terrengmodellen), med `simuler-leica.py --anlegg` (GNSS) og etter at
  simulatoren vart stoppa (sist kjende posisjon). Ekte kall mot MET kan ikkje testast her (nettet er stengt), men
  feilforklaringa og knappen er testa mot den stengde proxyen.

### PC-prototype v1.6.77 – retting: maskina står der ho er når kartet er flytt
- **Retta:** når føraren hadde flytt kartet («Følg maskina» synest), stod maskinteikninga fast midt på skjermen medan
  sporet gjekk vidare. Teikninga ligg utanpå kartet og var alltid midtstilt. No blir ho plassert der maskina faktisk
  er på kartet når kartet ikkje følgjer maskina, også når kartet er rotert. Når kartet følgjer maskina, står ho midt
  på som før. Gjeld kartvisinga ovanfrå (førar- og horisontvisinga følgjer alltid maskina).
- **Kvifor:** eigaren melde frå med skjermbilete (v1.6.75): maskina stod på same stad medan sporet flytta seg.
- **Testa:** demo, kartet dradd bort: maskina følgjer enden av sporet i tre bilete på rad, både med nord opp og med
  kartet snudd 35°. Ingen JavaScript-feil.

### PC-prototype v1.6.76 – rettingar: Tal og 3D/frontrute utan GNSS
- **Retta:** **Tal** (fart, kurs, spor, areal, tid) forsvann i førar-/horisontvisinga og når 3D-terreng eller
  frontrute fall tilbake til horisont (t.d. utan GNSS): det vippa kartet vart teikna over boksane. Tal (og AI-lag,
  mikrofon og snakkeboble) har no eige teiknelag, slik verktøylinja har. Feilen fanst også i v1.6.67.
- **Retta:** **3D-terreng og frontrute utan GNSS** viste berre eit tomt rutenett/himmel, fordi 3D-visinga treng ein
  posisjon. No blir midten av den gjeldande terrengmodellen vist (utan maskin), merkt «INGEN GNSS – VISER MIDTEN AV
  TERRENGMODELLEN». Kartet blir også flytt dit éin gong ved oppstart når GNSS manglar, så **Demo** køyrer på
  terrengmodellen (før: der kartet tilfeldigvis stod, ofte utanfor modellen – då mangla terrenget i 3D).
  Nytt endepunkt `/api/terrain/centre`.
- **Kvifor:** eigaren melde frå med skjermbilete frå maskin-PC-en: 3D-modell og frontrute mangla, og Tal mangla.
- **Testa:** utan GNSS (ingen mottakar): kart, horisont, 3D-terreng og frontrute – terrengmodellen synest og Tal
  synest; Demo i 3D køyrer på terrengmodellen. Med `simuler-leica.py --anlegg`: 3D og frontrute som før, samanlikna
  med v1.6.67. Ingen JavaScript-feil.

### PC-prototype v1.6.75 – AI: opningstider, tale med føraren, læringslogg og nye funn
- **Nytt:** **opningstider** (`opningstid.py`, AI › Opningstider): standard laurdag og søndag 10–16, kveldskøyring
  tysdag, onsdag og fredag 18–21, og 10–16 i juleferie (21.12–1.1), vinterferie (veke 8 og 9), påskeferie og på
  heilagdagar (norsk kalender, rekna ut lokalt med påskeformelen). 24. og 25.12 stengt, sesong 1.12–30.4. Alt kan
  endrast: vekeplan, ferietider, veker, sesong, stengde datoar og **manuelle unntak per dato**. Visast som 14-dagars
  oversikt. Tidspunkt-rådet reknar no mot neste opning.
- **Nytt:** **tale** (av/på i AI-overlayet, standard AV): AI-en seier korte varsel medan maskina køyrer (for lite snø,
  hol like ved, snøfall/sterk vind innan ein time), og føraren kan spørje med 🎤 «Spør AI» (snø som manglar,
  tidspunkt, vêr, hol, kvalitet, snøflytting, opningstid, snødjupne). Opplesing utan nett; talegjenkjenning krev
  oftast nett, elles skrivefelt.
- **Nytt:** **lokal læringslogg** og **nye funn** (seksjon 6): kva som går igjen (hol, underskot same stad), kva
  modellen bommar på, kva førarane meiner om råda (👍/👎 på kvart råd), og kva dei spør om som AI-en ikkje forstår.
- **Nytt:** **opplæringspakke** (anonymisert zip) for ein framtidig sentral SNOWMAN-AI. Ingenting blir sendt;
  «Del sentralt» er AV og ikkje bygd.
- **Endra:** standard opningstid i tidspunkt-rådet er kl. 10 (før: 9) når det ikkje finst opning i kalenderen.
- **Avgjerd (eigaren):** standard opningstider som over; kveldskøyring varierer og må kunne endrast manuelt.
  Tale skal ha av/på. Kvar SNOWMAN-installasjon lærer først lokalt; ein sentral AI-motor kjem når prosjektet er
  modent (VEGEN-VIDARE kap. 14 punkt 6).
- **Avgjerd:** vinterferie standard veke 8 og 9, fordi fylke og kommunar har ulike veker (Vestland har begge) og
  anlegga får gjester frå begge – sjekk skoleruta lokalt. Skolerutene blir ikkje henta automatisk (formata
  varierer mellom fylka).
- **Testa:** `python3 opningstid.py` (helg, kveld, vinterferie veke 8/9, skjærtorsdag, julaftan, utanfor sesong),
  `python3 ai.py`, og i isolert kopi med demo og TEST-data: redigering og lagring av unntak, 👍, åtte
  talespørsmål (sju forstått), mikrofon og snakkeboble, opplæringspakke utan posisjonar/namn/tekst.
  Ingen JavaScript-feil. Skjermbilete 7–10 i `docs/prototypar/ai/`. Norsk stemme og talegjenkjenning må testast
  på maskin-PC-en (testmaskina har ingen stemmer og ikkje nett).

### PC-prototype v1.6.74 – AI-knapp: lokal AI med fem preparéringsråd
- **Nytt:** knappen **«✦ AI»** i verktøylinja (etter Vêr) opnar eit overlay med fem råd: **5 snøproduksjon** (øvst),
  **1 tidspunkt å preparere**, **2 snøflytting med skjeret**, **3 hol i spora** og **4 kvalitetsscore per trasé**.
  Kvart råd har «Vis» (flyttar kartet dit) og «Vis på kartet».
- **Nytt:** råda blir **lag på hovudkartet** som blir verande når overlayet er lukka: område med for lite snø er
  **raudt skravert** (tre nivå) med etikett «❄ MANGLAR x cm · y m³ snø · næraste kanon/hydrant» og stipla linje
  til han; snøflytting som gul pil «SKYV x m³»; hol som oransje ring; kvalitet som «xx %» ved traseen. Etikettane
  står alltid rett opp når kartet roterer. Laga blir slått av med knappane nede til venstre.
- **Nytt:** alt anna går vidare i bakgrunnen (testa: sporet voks medan AI var ope). Vêr og AI deler plass – det
  eine lukkar det andre. Nye råd kvar 10. min så lenge overlayet eller eit AI-lag er på.
- **Nytt:** `ai.py` – lokal, lærande modell på PC-en (ikkje språkmodell, ingen skyteneste). **Områdeprofil blir laga
  automatisk** når SNOWMAN er på ein ny stad (> 5 km frå kjende), og lærer vindrose og nattetemperatur. Saman med
  nedbørsfaktoren og læringa i snøkartet blir alt tilpassa staden etter GPS – utan oppsett per anlegg.
  Nytt endepunkt `/api/ai`. Spesifikasjon i `docs/AI.md`.
- **Nytt:** innstillingar `aiOpen` (opningstid, standard 9) og `aiGunRate` (m³ snø per time per kanon, standard 25 –
  grovt anslag) i førarskjerm-innstillingane, loggførte ved endring.
- **Endra:** snøkartet kan halde inntil tre utrekningar samstundes (snøkart og AI kan ha ulike utsnitt).
- **Endra:** verktøylinja: knappane er litt smalare (70 px) og rada blir aldri kutta i kantane.
- **Avgjerd (eigaren):** ein lokal AI i SNOWMAN skal lære området han er i, og alt skal tilpassast automatisk når
  SNOWMAN blir selt til andre delar av Noreg.
- **Kvifor:** eigaren ville teste AI i SNOWMAN med eigen knapp, dei fem råda, og særleg sjå område med for lite snø
  mot oppgitt måldjupne på ein måte føraren forstår.
- **Testa:** `python3 ai.py` (tidspunkt etter snøfall, flytting nedover, hol, kvalitet), og i isolert kopi med
  DTM1-utsnitt, `simuler-leica.py --anlegg`, TEST-målingar, to TEST-trasear (mål 0,8 og 1,0 m), ei TEST-økt med hol,
  snøkanon og hydrant, demo-vêr – og utan trasear. Ingen JavaScript-feil. Skjermbilete i `docs/prototypar/ai/`.
  Kanon-kapasiteten og scorane er ikkje kalibrerte mot verkelegheita.

### PC-prototype v1.6.73 – Snøkart steg 3–4: totaldjupne, vêr bakover, treffsikkerheit og læring
- **Nytt (steg 3):** setjing av laus snø, smelting av både ny og eldre snø (graddøgn og regn), og **totaldjupne** =
  sist målt med RTK (snøflate-minnet, fylt mellom spor innan 12 m) + modellendringa sidan. Bleikare farge jo eldre
  målinga er. Same fargeintervall som målt snødjupne, men skravert og merkt ESTIMAT.
- **Nytt (steg 4):** **vêr bakover 72 t frå MET Frost** (temperatur og vind frå stasjonen nærast i høgd, nedbør frå
  næraste stasjon, omrekna til høgda) – så endringa sidan sist målt kan reknast. **Tidsglidar:** «No (sidan sist
  målt)», +6, +12, +24, +48 t. Nye visingar: «Total djupne», «Endring», «Utan vind», «Vindeffekt» og «Lært».
- **Nytt:** **treffsikkerheit mot RTK** – ruter køyrde to gonger blir samanlikna med modellen (snittfeil, skeivheit),
  og ein **nedbørsfaktor** blir rekna ut. «Juster etter RTK: På/Av».
- **Nytt:** **SNOWMAN lærer kvar det kjem meir eller mindre snø** enn modellen ventar, i faste 10 × 10 m-ruter over
  sesongen (data/snokart-laering.json, ikkje i git). Visinga «Lært» viser mønsteret, «Bruk lært: På/Av» brukar det.
  **Snøproduksjon blir halden utanfor:** ruter innan 60 m frå snøkanon eller hydrant (anleggsobjekt, stipla sirkel
  i kartet) og hendingar som ser ut som produksjon eller skjerarbeid blir ikkje lærte.
- **Endra:** snø som blir flytt av vinden blir **pakka** – tettleiken på fokksnø følgjer vindstyrken (200–400 kg/m³),
  og eldre, tettare laus snø krev meir vind før han flyttar seg.
- **Avgjerd:** kalibreringa samanliknar med snø pakka under beltet (450 kg/m³), fordi maskina måler overflata ho
  står på. Læringa viser mønsteret (delt på medianen); nivået blir teke av nedbørsfaktoren.
- **Kvifor:** eigaren bad om steg 3 og 4, og påpeika at flytt snø blir meir kompakt og at SNOWMAN bør lære kvar det
  kjem mest snø – med atterhald om snøproduksjon.
- **Testa:** `python3 snokart.py` (vind, setjing 14,8 → 13,1 cm på 24 t, smelting, kalibrering ×1,3, læring aust/vest),
  `testsnoflate.py`, og i ein isolert kopi med DTM1-utsnitt, `simuler-leica.py --anlegg`, oppdikta TEST-målingar
  (to besøk, 101 645 ruter) og TEST-læring, demo-vêr bakover og framover, og utan vêrhistorikk. Treffsikkerheit i
  testen ±0,9 cm, faktor ×1,2. Ingen JavaScript-feil. Skjermbilete i `docs/prototypar/snokart/`. Frost-historikken
  er testa med demo og ved feil, ikkje mot ekte Frost (ikkje nåbar frå testmaskina).

### PC-prototype v1.6.72 – Snøkart: estimert snøendring i terrengmodellen (Vêr › Snøkart, steg 1–2)
- **Nytt:** knappen **«🗺 Snøkart (estimat)»** i Vêr opnar eit nytt overlay over Vêr med eit kart over estimert
  snøendring i den gjeldande terrengmodellen: periode 6 / 12 / 24 / 48 t frå varselet, visingane «Med vind»,
  «Utan vind» og «Berre vindeffekt», område ±300 / ±600 / ±1200 m og «Laus snø frå før» 0–20 cm. Trykk i kartet for
  å lese av ein stad. Sidepanel med periode, nedbør, snitt nysnø med og utan vind, vind (himmelretning), del av
  arealet som blir blåst bort / fylt på, og fargeskala. Maskina, nordpil, vindpil og målestokk står i kartet.
- **Nytt:** ✕ i snøkartet går tilbake til Vêr. Vêr-knappen i verktøylinja lukkar begge. Alt anna går vidare under
  (testa: sporet voks frå 44 til 94 punkt medan snøkartet var ope).
- **Nytt:** `snokart.py` – steg 1: nysnø frå nedbør, høgd og våttemperatur (−0,65 °C og +7 % nedbør per 100 m,
  nysnøtettleik etter temperatur og vind, smelting av snøen i perioden). Steg 2: vindflytting med lé-tal (Winstral Sx)
  frå terrengmodellen for 16 vindretningar, vind over terskel, transport medvinds og avsetjing i le – massen blir
  halden. Nytt endepunkt `/api/snowmap`. Detaljar i TERRAIN-ENGINE kap. 6c.
- **Nytt:** Vêr viser kvar høgda kjem frå («høgd frå terrengmodell «…»»).
- **Avgjerd (eigaren):** **den gjeldande terrengmodellen i SNOWMAN blir alltid brukt i alle funksjonane i Vêr**
  (varsel-høgd, «ved maskina» for stasjonane, snøkartet). Står maskina utanfor, blir snøkartet lagt midt på det
  høgast prioriterte aktive laget.
- **Avgjerd:** snøkartet har eigne fargar (blå for snøendring, oransje ↔ blå for vindeffekt), skravur,
  «ESTIMAT»-vassmerke og banner – så det aldri kan forvekslast med målt snødjupne.
- **Endra:** demo-varselet har fått ei snøbye med vestaversvind dei første timane, så snøkartet har noko å vise i demo.
- **Kvifor:** eigaren ville ha eit estimert snøkart som tek omsyn til vindretning, vindstyrke og nedbør.
- **Testa:** `python3 snokart.py` (kunstig rygg: vestavind blæs ryggen rein og fyller austsida), og i ein isolert kopi
  med eit ekte DTM1-utsnitt (Kartverket, ca. 870–1040 moh.) og `simuler-leica.py --anlegg`. Retta under testinga:
  for sterk erosjon på jamne lo-bakkar (no relativt lé-tal) og opphoping ved kanten av terrengmodellen. Ingen
  JavaScript-feil. Skjermbilete i `docs/prototypar/snokart/`. Parametrane er ikkje kalibrerte mot målingar enno.

### PC-prototype v1.6.71 – Vêr: vind som himmelretning, «kl.» på klokkeslett
- **Endra:** vindretning blir vist som **himmelretning** (nord, nordaust, aust, søraust, sør, sørvest, vest, nordvest –
  der vinden kjem frå) med ei **pil** som viser kvar vinden blæs, i staden for grader. Gjeld vindboksen, «Målt no» og
  avlesinga i grafen.
- **Endra:** klokkeslett står med **«kl.»**: tidsaksen i 48-timarsgrafen (kl. 06, kl. 12, kl. 18, og «Lau kl. 00» ved
  midnatt), produksjonsvindauge, «vindauge no / neste vindauge» og avlesinga. Vindauge over midnatt får begge dagane,
  t.d. «Fre kl. 18 – Lau kl. 09» (før: «Fre 18–09»).
- **Kvifor:** eigaren: grader er vanskeleg å tolke for ein maskinførar, og grafen mangla klokkeslett.
- **Testa:** med `simuler-leica.py` (isolert kopi) og demo (varierande vindretning). Ingen JavaScript-feil.

### PC-prototype v1.6.70 – «MÅLT NO» i Vêr: målingar frå næraste vêrstasjonar (MET Frost)
- **Nytt:** `frost.py` hentar siste målingar frå dei næraste stasjonane (Frost «nearest» frå GPS-posisjonen, maks 3 med
  ferske data): temperatur, vind og kast, luftfukt, nedbør siste time og snødjupne der stasjonen måler det. Nytt
  endepunkt `/api/weather/obs`.
- **Nytt:** vêr-overlayet har fått delen **«MÅLT NO – NÆRASTE STASJONAR»** med namn, høgd, avstand, målingar og alder.
  Temperaturen blir også omrekna til høgda til maskina (0,65 °C/100 m, merkt som anslag), og våttemperatur blir rekna ut
  der stasjonen måler luftfukt. Målingane blir viste også når varselet manglar.
- **Nytt:** offline først – stasjonslista blir lagra i 7 dagar og siste målingar i `data/frost-cache.json`, vist med
  merknad når nettet manglar. Nye målingar blir henta høgst kvar 10. min.
- **Nytt:** `snowman-config.local.json` kan ha `frost_client_id` (eige anlegg sin ID) og `frost_stations`
  (fast liste, t.d. `SN60190,SN60225`). Tomt = innebygd ID og næraste stasjonar.
- **Avgjerd (eigaren):** SNOWMAN sin Frost **klient-ID ligg i koden** (`frost.py`). Eigaren: «Det er ingen fare med det» –
  ID-en gir berre tilgang til opne data. **Client secret blir ikkje brukt og ligg ikkje i repoet.** Andre anlegg bør få
  eigen ID seinare, så ikkje alle deler éin.
- **Kvifor:** eigaren registrerte ein Frost-ID og ville ha han brukt i SNOWMAN.
- **Testa:** mot ei lokal testteneste som svarar som Frost (stasjonsoppslag, siste målingar, færre element ved feil 400,
  lagring og offline), i demo og med `simuler-leica.py`. Frost er ikkje nåbar frå testmaskina, så første test mot ekte
  Frost blir på maskin-PC-en. Ingen JavaScript-feil.

### PC-prototype v1.6.69 – vêrsymbol i vêr-overlayet
- **Nytt:** vêrsymbola til MET (same `symbol_code` som i varselet) blir viste kvar 3. time over 48-timarsgrafen, i
  boksen «Luft · fukt» for timen no, ved kvar dag i «Dag for dag» og i avlesinga når ein trykkjer i grafen – med nynorsk
  tekst frå `legend.csv` (t.d. «Klårvêr», «Kraftig snø»). Demo-data har fått passande symbol.
- **Nytt:** symbola ligg i `vendor/vaersymbol/` (83 SVG, uendra) og blir levert av SNOWMAN-tenesta, så dei verkar utan
  nett. Kjelde og lisens står i `vendor/vaersymbol/LES-MEG.txt` og `LICENSE`. Kreditering i overlayet og i Om-feltet.
- **Avgjerd (lisens sjekka):** `github.com/metno/weathericons` er **MIT-lisensiert (Copyright (c) 2015-2017 Yr)**, ikkje
  CC BY – CC BY 4.0 gjeld vêrdataa frå api.met.no. MIT tillèt bruk i proprietær programvare når lisensteksten følgjer
  med. Namnet og merket Yr blir ikkje brukt som merke i SNOWMAN, berre i den påkravde opphavsmerknaden.
- **Kvifor:** eigaren ville ha vêrsymbola inn i overlayet.
- **Testa:** med `simuler-leica.py` (isolert kopi) og demo: symbol blir viste, `/vendor/vaersymbol/…` slepp berre gjennom
  gyldige filnamn (stigar som `..` gir 404). Ingen JavaScript-feil. Nye skjermbilete i `docs/prototypar/ver/`.

### Dokumentasjon – målestasjonar nær Fjellsætra (VEGEN-VIDARE kap. 13)
- **Nytt:** Roaldshornet (ca. 1050 moh., temperatur og vind), Fv60 Strandafjellet (504 moh., temperatur, nedbør, vind)
  og Fv650 Liabygda er dei næraste stasjonane yr viser. Truleg MET-id SN60190 og SN60225 – må stadfestast i Frost.
- **Avgjerd:** github.com/metno har ingen eigne vêrdata eller offisiell Python-klient; SNOWMAN brukar eigen klient
  (`ver.py`). YR-merket blir ikkje brukt. MET sine vêrsymbol (`weathericons`) kan vurderast etter lisenssjekk.
- **Kvifor:** eigaren bad om å finne informasjon på github.com/metno.

### PC-prototype v1.6.68 – Vêr og snøproduksjon (Vêr-knappen, prototype)
- **Nytt:** knappen **«❄ Vêr»** i verktøylinja (etter HUD) opnar eit **overlay** over kartet med varsel for staden og
  høgda til maskina: snøproduksjon no (GODT / MARGINALT / FOR MYKJE VIND / IKKJE MOGLEG), våttemperatur, luft og fukt,
  vind, **produksjonsvindauge** (samanhengande timar, minst 2 t), graf for dei neste 48 timane (våttemperatur og
  lufttemperatur med grenselinjer, bakgrunn etter status, eigen liten nedbørsgraf) og **dag for dag**-oversikt.
  Trykk eller dra i grafen for å lese av kvar time. Trykk **Vêr** igjen (eller ✕) for å lukke.
- **Nytt:** overlayet stoppar ingenting – GNSS, måling, spor, økt og verktøylinja går vidare under (testa: sporet voks
  frå 36 til 65 punkt medan overlayet var ope, og Zoom ut fungerte). DEMO-/TEST-merket blir flytt så det alltid synest.
- **Nytt:** `ver.py` hentar **MET Norway Locationforecast 2.0** (gratis, CC BY 4.0) via SNOWMAN-tenesta
  (`/api/weather`), reknar ut **våttemperatur etter Stull (2011)** og klassifiserer kvar time. MET sine vilkår blir følgde:
  eigen User-Agent, maks 4 desimalar, nytt oppslag først når «Expires» er passert, og If-Modified-Since.
- **Nytt:** **offline først** – siste varsel blir lagra i `data/ver-cache.json` og vist med alder når nettet manglar.
  Utan lagra varsel står det tydeleg at SNOWMAN ikkje får kontakt med api.met.no; resten av SNOWMAN er urørt.
- **Nytt:** grensene kan stillast inn nedst i overlayet (standard godt ≤ −5 °C, marginalt ≤ −2 °C våttemperatur,
  maks vind 12 m/s). Lagra i førarskjerm-innstillingane (`wxGood`, `wxMarg`, `wxWind`) og loggførte ved endring.
- **Nytt:** i **Demo** blir oppdikta vêrdata viste, merkte «DEMO – OPPDIKTA VÊRDATA, IKKJE VARSEL». Dei blir aldri
  lagra som ekte varsel.
- **Avgjerd:** prototypen brukar berre Locationforecast (ingen registrering eller nøklar). Observasjonar frå
  stasjonar (Frost, Strandafjellet), vegvêr frå Statens vegvesen, webkamera og snøanslag med vind er neste steg
  (VEGEN-VIDARE kap. 13).
- **Kvifor:** eigaren ville ha forhold for snøproduksjon i SNOWMAN, som eit overlay som kan opnast og lukkast med éin
  knapp utan at noko anna stoppar.
- **Testa:** med `simuler-leica.py` (isolert kopi), demo og utan nett (MET ikkje nåbar frå testmaskina), og mot ein lokal
  testteneste som svarar som MET: rett tolking, mellomlagring til «Expires», If-Modified-Since, og lagra varsel når nettet
  forsvinn. Ingen JavaScript-feil. Skjermbilete i `docs/prototypar/ver/`.

## 2026-10-08

### Dokumentasjon – eksempel på alle rapportane (`docs/eksempel-rapportar/`)
- **Nytt:** eksempel på dagsrapport som PDF med trasear og utan trasear, CSV til Excel og ein feltlogg (zip),
  med `README.md` som forklarer kvar fil og kvar ein finn ho i SNOWMAN. Alle er laga med oppdikta eller simulerte data
  og tydeleg merkte («EKSEMPEL – oppdikta data, ikkje ekte målingar» øvst og nedst i PDF-ane; feltloggen er frå
  simulatoren og merkt simulert).
- **Nytt:** `pc/v1.6/lag-eksempel.py` lagar eksempelrapportane på nytt i ei eiga mappe (data/ til SNOWMAN blir ikkje
  rørt). `pdfrapport.build` har fått valfri merknad (`note`) for slike eksempel.
- **Kvifor:** eigaren ville sjå eksempel på alle rapportane ein kan ta ut av SNOWMAN.

### PC-prototype v1.6.67 – snødjupne i farger på karta i rapporten, «Tal» først i knapperekkja
- **Nytt:** karta i rapporten (i SNOWMAN og i PDF-en) er farga etter **målt snødjupne** i fresbreidda – same fargar og
  intervall som på kartet (Innst. › Snøintervall) – med **fargeskala** under kartet. Trakka utan måling er lyseblått,
  ikkje trakka del av ein trasé er grått. Siste køyring gjeld der spor overlappar. Finst det berre simulert snø, står
  det «SIMULERT SNØ (TEST) – ikkje ekte måling».
- **Endra:** knappen **«⏱ Tal»** står no lengst til venstre, før «Snødjupne».
- **Kvifor:** eigaren: utan fargeskala er det vanskeleg å vite djupna på snøen i rapporten.
- **Testa:** rapport og PDF med og utan testtrasé (simulert snø, 1199 målte ruter, snitt 0,78 m), fargeskala under
  kvart kart. Ingen JavaScript-feil.

### PC-prototype v1.6.66 – rapporten som PDF (kart, trasear, økter, drivstoff)
- **Nytt:** knappen **⬇ RAPPORT SOM PDF** i Innst. › Rapport (ved sida av ⬇ CSV / EXCEL). PDF-en (A4) har samandrag,
  trasear med tid i traseen, kart per trasé (trakka grønt, ikkje trakka grått, berre TEST oransje, målestokk og nord) –
  eller kart over heile området om ingen trasear er lagde inn – økter og drivstoff. TEST/demo er merka i oransje.
  Skriven med eigen kode (`pdfrapport.py`, berre numpy), så det fungerer offline utan nye pakkar.
- **Nytt:** automatisk lagring skriv no både CSV og PDF til mappa (t.d. OneDrive).
- **Retta:** kartet over trakka område vart nesten tomt når det var køyrt på stader langt frå kvarandre (t.d.
  Fjellsætra og Sykkylven sentrum). No blir det delt i opptil 4 kart («Område 1 av 2»), kvart skore til det som er
  køyrt – både i SNOWMAN og i PDF-en.
- **Kvifor:** eigaren ville kunne laste ned kart, drivstoff og økter som PDF, i tillegg til CSV.
- **Testa:** PDF frå testdata (1 side; med testtrasé 2 sider), med drivstoff og økter (testdata), nedlasting frå
  knappen, automatisk lagring (CSV + PDF), deling av område (to område langt frå kvarandre → to kart). Ingen
  JavaScript-feil.

### PC-prototype v1.6.65 – breiare innstillingar ved å dra, og knapp for å skjule fart/kurs/spor/areal/tid
- **Nytt:** eit blått handtak på venstre kant av innstillingane. Hald og dra mot venstre, så blir panelet så breitt
  som der du slepp – høgst 50 % av skjermen. Dra heilt tilbake for fast plass (vanleg breidd). Kvar gong
  innstillingane blir opna, startar dei med vanleg breidd igjen. Fungerer med mus og finger.
- **Nytt:** knappen **«⏱ Tal»** nede slår av og på boksane FART, KURS, SPOR, AREAL og TID nede til venstre
  (trasé-ruta blir ståande når ein er i ein trasé). Valet blir hugsa.
- **Kvifor:** eigaren ville kunne gjere innstillingane breiare ved behov og ha meir kart synleg.
- **Testa:** 390 px → dra til x = 700 gir 668 px, dra langt til venstre stoppar på 684 px (50 % av 1368),
  dra tilbake gir vanleg breidd, lukk og opne gir vanleg breidd. «Tal» skjuler og viser boksane. Ingen JavaScript-feil.

### PC-prototype v1.6.64 – loggen hoppar ikkje til toppen medan ein les
- **Retta:** feltlogg-lista (Innst. › System) vart teikna på nytt kvart 2. sekund, så hendingsboksen hoppa tilbake
  til toppen medan ein las. No blir ingenting teikna på nytt om innhaldet er likt, og rulleposisjonen i boksen blir
  halden når nye linjer kjem. Står ein heilt nedst, følgjer boksen med nye linjer.
- **Retta:** hendingane i loggen som pågår blir no henta på nytt kvart 2. sekund, så nye feilmeldingar kjem fram
  medan boksen er open (før var lista frosen frå då ein opna ho).
- **Retta (same feil andre stader):** Kontroll-panelet (status, kontrollmålingar, kontrollpunkt) vart òg teikna på
  nytt kvart 2. sekund – no berre når noko er endra, og markørane på kartet blir ikkje teikna på nytt utan grunn.
  Då blir heller ikkje knappar bytte ut midt i eit trykk på berøringsskjermen. Andre panel har ikkje slik oppdatering.
- **Kvifor:** eigaren fekk ikkje lese feilmeldingane i loggen fordi teksten hoppa til toppen.
- **Testa:** hendingsboksen midt i (pos. 200) held seg etter 7 s og nye linjer kjem til (58 → 61); nedst følgjer
  boksen nye linjer (61 → 64). Ingen JavaScript-feil.

### Nytt app-ikon for SNOWMAN (skrivebord, oppgåvelinje og nettlesarfane)
- **Nytt:** moderne ikon med SNOWMAN-fjelltoppane (snøline, same form som logoen) som går ned i ei snøflate, og den
  nye tråkkemaskina sett ovanfrå (skjer med venger, belte, raudt førarhus, fres og gul finisher) med preparert spor
  bak. Dei små storleikane (16–32 px) er forenkla, så ikonet er tydeleg på skrivebordet.
- **Nytt:** `ikon/lag-ikon.py` lagar alle ikonfilene og logoen frå éi kjelde (`snowman.svg`, `snowman-enkel.svg`,
  `snowman-logo.svg`, `snowman.ico`, `snowman-256/512.png`, `vendor/snowman-icon.png`). `docs/LOGO.md` har filer,
  fargar og skrift, så ikon og logo kan følgje med vidare i utviklinga.
- **Merk:** Windows kan vise det gamle ikonet på snarvegen til ikon-mellomlageret blir oppdatert (omstart, eller køyr
  INSTALLER-WINDOWS.bat på nytt for å lage snarvegen på nytt).
- **Kvifor:** eigaren ønskte eit meir moderne ikon med den nye maskina og logoen med snø i fjella.

### PC-prototype v1.6.63 – skjermtastaturet kjem att etter bruk av ekte tastatur
- **Retta:** etter eit trykk på ein ekte tast (Surface-tastaturet) kom ikkje skjermtastaturet opp att når ein trykte
  på skjermen – det var sperra i 10 minutt. No opnar **kvart trykk med fingeren** i eit skrivefelt tastaturet igjen,
  også i feltet som alt har fokus. Ekte tastetrykk skjuler det framleis. Museklikk opnar det ikkje (AUTO).
- **Kvifor:** tastaturet til Surface kan vere kopla til og frå; då må skjermtastaturet kome att.
- **Testa:** trykk → synleg, ekte tast → skjult, trykk i same felt → synleg, ekte tast + trykk i anna felt → synleg,
  museklikk → ikkje synleg. Ingen JavaScript-feil.

### PC-prototype v1.6.62 – snu kartet med to fingrar, tastatur på skjermen, passord berre som stjerner
- **Nytt:** **vri med to fingrar** for å snu kartet (2D og førar-/horisontvising); knip zoomar som før. Rotasjonen
  startar først etter 12° vriing, så kartet ikkje snur seg når ein berre zoomar. **Under prep** går kartet tilbake til
  køyreretninga 12 s etter siste vriing («Kartet følgjer køyreretninga igjen»); utan prep blir det ståande til FØLG.
- **Retta:** å dra på eit snudd kart flytta kartet i feil retning (Leaflet reknar i skjermretning, kartet er rotert
  og skalert med CSS). No går kartet same vegen som fingeren (testa: 200 px til høgre → 201 px til høgre ved 45°).
- **Nytt:** **tastatur på skjermen** (`tastatur.js`, brukt i førarskjermen og på NTRIP-sida): norsk med æøå for
  tekst, talpanel for tal (komma blir punktum), eige siffer-panel for PIN. Kjem opp når ein trykkjer i eit skrivefelt
  med fingeren (AUTO), forsvinn ved ekte tastetrykk. Legg seg på motsett side av feltet, viser feltnamn og det som er
  skrive (prikkar for passord), er halvgjennomsiktig og kan dragast. Windows sitt eige tastatur blir halde unna.
  Innstilling i Innst. › System: AUTO / ALLTID / AV.
- **Endra:** PIN-spørsmåla for kioskmodus brukte nettlesaren sin `prompt()`, som ikkje kan brukast utan tastatur.
  No er det ein eigen boks med siffer-panel.
- **Endra (NTRIP-sida):** passordet er skjult medan ein skriv; **VIS PASSORD** viser det berre før ein har lagra.
  Etter LAGRE står det berre `********` – passordet er hugsa i SNOWMAN, men blir aldri sendt tilbake til skjermen.
  Trykkjer ein i feltet, kan ein skrive eit nytt; lèt ein det stå tomt, gjeld det gamle. Tenesta ignorerer felt som
  berre er stjerner.
- **Avgjerd:** eige tastatur i SNOWMAN i staden for Windows sitt berøringstastatur (fungerer i kioskmodus, dekkjer
  ikkje feltet, store tastar for hanskar, utan nett). Rotasjon også under prep med automatisk retur (val B).
- **Testa:** Chromium med simulert touch: vriing (8° = ingen rotasjon, 60° → 45° etter terskel), retur etter 12 s
  under prep, dra på snudd kart, talpanel (1,25 → måldjupne 1.25 lagra), tekst «Pb600 æøå» (tastaturet dekkjer ikkje
  feltet), ekte tast skjuler tastaturet, PIN-boks (1234), NTRIP-passord (skjult → VIS → lagra som stjerner).
  Ingen JavaScript-feil. Lokale testinnstillingar er sette tilbake.
- **Kvifor:** PC-en i maskina har berre berøringsskjerm; eigaren ville snu kartet med fingrane og kunne skrive inn
  verdiar utan tastatur, og at passordet berre skal synast som stjerner etter lagring.

### PC-prototype v1.6.61 – SNOWMAN-logoen slik eigaren har han
- **Endra:** logoen i toppfeltet er no eigaren sin: kvite fjelltoppar over «SNOWMAN» (rett, feit skrift) og
  «by Alpindata» i lyseblått under, teikna som SVG (skarp i alle storleikar). App-ikonet frå v1.6.60 er teke ut av
  toppfeltet igjen. Versjonen står etter «by Alpindata». Logoen er 72 px høg som før og blir mindre på smal skjerm.
- **Kvifor:** eigaren viste logoen slik han skal vere, og bad om å justere storleiken om han tok for mykje plass.

### PC-prototype v1.6.60 – SNOWMAN-logoen i toppen og meir luft til snødjupna
- **Endra:** toppfeltet på førarskjermen viser SNOWMAN-ikonet (tråkkemaskina framfor fjella, same som app-ikonet i
  `ikon/`) til venstre for «SNOWMAN by Alpindata», og det er meir luft (30 px) mellom namnet og snødjupneboksen.
  På smal skjerm blir ikonet mindre.
- **Kvifor:** eigaren ønskte meir luft mellom SNOWMAN og snødjupna, og logoen inn i toppen.
- **Testa:** nettlesar i 1368, 1920 og 680 px breidd.

### PC-prototype v1.6.59 – timeval for tidlegare flate, kart og tid per trasé i rapporten, sidetal på HUD
- **Nytt:** knappen «≋ Flate» nedst opnar ein meny: **AV · 3 · 5 · 10 · 15 · 24 · 48 · 72 t** – kor gammal flata som
  blir brukt til estimatet framfor maskina kan vere. Knappen viser valet («Flate 24 t»). Same val i Innst. › Kart.
  Standard er 24 t (før: fast 72 t). Valet kan endrast før og under «Start prep»; sporet du køyrer no er òg med.
- **Nytt (rapport):** ny kolonne **Tid** per trasé (tid med maskina inne i traseen, utan transport over 40 km/t og
  hopp i sporet), også i CSV-fila. Ny boks **«Kart per trasé»** med kart over kvar det er trakka (grønt), ikkje trakka
  (grått) og berre TEST (oransje), med målestokk og nord opp. Er ingen trasear lagde inn, viser **«Kart – trakka
  område»** heile området som er køyrt i prepareringsdøgnet (i fresbreidda; berre test blir vist oransje og merka TEST).
- **Nytt (HUD):** hovudtalet er framleis dagens målte snødjupne. På sidene:
  - venstre: **OVERFLATE SIDAN SIST ±x cm** (målt overflate no mot førre preparering same stad – nysnø, setning,
    snø flytt av skjeret), med alderen på førre preparering;
  - høgre: **SIST MÅLT HER ≈x m** (estimat, stipla ramme) når den direkte målinga manglar, t.d. utan RTK FIX;
  - nede: estimatet framfor maskina blir no vist også før «Start prep» når det kjem frå tidlegare flate.
- **Endra:** snøflateminnet hugsar overflata frå førre besøk i kvar rute (over 2 t mellomrom = ny preparering).
- **Avgjerd:** «soner» i rapporten = trasear lagde inn på kartet. Innkøyring i forbodne område blir ikkje vist i
  rapporten (eigaren). Ordet er «spor», ikkje «lane».
- **Testa:** `testsnoflate.py` (OK), einingstest av førre besøk (+12 cm etter 20 t) og «sist målt her» (0,80 m, 20 t);
  simulert GNSS over testterrenget: menyen (3 t → AV → 24 t under prep), estimat på HUD etter prep, rapport med og
  utan testtrasé, HUD-sidetala med testdata. Ingen JavaScript-feil. Testlag, testtrasé og testminne er sletta.
- **Kvifor:** eigaren ønskte timeval for estimatet, kart over kvar det er trakka per trasé i rapporten, og estimert
  snødjupne frå førre preparering på HUD-en – med dagens målte snødjupne som hovudtal.

### PC-prototype v1.6.58 – estimat framfor maskina frå tidlegare trakka overflate (snøflateminne)
- **Nytt:** SNOWMAN hugsar snøoverflata der maskina har køyrt (`snoflate.py`, `data/snoflate.json`, ruter på 1 × 1 m,
  7 døgn). Ved neste preparering blir snødjupna framfor maskina estimert frå denne overflata: overflata følgjer den
  store forma på bakken, men bekkar, groper og kular frå terrengmodellen blir rekna med under ei planert flate.
  Eit gjenfylt bekkefar blir då estimert djupt sjølv om ein berre har køyrt på kvar side av det.
- **Nytt:** knappen **«≋ Tidl. flate»** nedst slår dette av og på (også i Innst. › Kart, med status, forklaring og
  «Gløym tidlegare overflate» t.d. etter mykje nysnø). Av = som før: estimatet byggjer berre på målingane i økta.
- **Nytt:** estimatboksen viser «FRAMFOR · ESTIMERT · TIDL. FLATE» og alderen på flata («flate 18 t gammal»), også på
  HUD-en. Det er alltid merka som estimat. Berre flate under 72 t blir brukt. Demo brukar det ikkje; simulert
  mottakar lagrar og brukar berre test-flate (blandar aldri test og ekte).
- **Avgjerd (modell):** `djupne = r(x) + Tg(x) − terreng(x)`, der `Tg` er glatta terreng (±6 m) og `r = overflate − Tg`
  for kvar lagra måling. Direkte interpolasjon av overflata vart prøvd først og forkasta: i 14° helling gav ho opptil
  0,7 m feil framfor maskina.
- **Testa:** `testsnoflate.py` (syntetisk bakke med bekkefar og kul): planert overflate – snittavvik 0,5 cm, midt i
  bekken 1,91 m mot fasit 1,92 m (gamle metoden 1,25 m). Ikkje planert snø (snøen følgjer terrenget) – den nye metoden
  bommar med opptil 0,65 m, den gamle treffer; difor av/på-knappen. Simulert GNSS over testterrenget
  (`simuler-leica.py --terreng`, `--simulert`): minnet blir fylt, estimatet kjem på 0,07 s, knappen byter mellom
  metodane, ingen JavaScript-feil. Testlag og testminne er sletta etterpå.
- **Kvifor:** eigaren påpeikte at terrenget ser annleis ut etter planering (slettare, bekkar og kular forsvinn) og
  ville teste i v1.6 korleis SNOWMAN skal tolke overflata, med ein knapp for å slå det av og på.

### PC-prototype v1.6.57 – all tekst synest i vallistene i Rapport og Historikk
- **Retta:** tekstane i vallistene vart kutta. Rapport: feltet heiter no «Prepareringsdøgn (12–12)», og lista viser
  berre datoen («08.10.2026») i staden for «08.10.2026 kl. 12 – neste dag kl. 12». Historikk: «Vel økt (dato, starttid
  og type)» står over ei vallist i full breidde, med tekst som «08.10.2026 kl. 17:20 – KØYRING» (24-timars klokke).
  Trakka område: «Periode» står over ei vallist i full breidde, og første valet heiter «Prepareringsdøgn (12–12)».
- **Kvifor:** eigaren såg at ikkje all tekst synest i rubrikkane, og ønskte «Prepareringsdøgn (12-12)».
- **Testa:** nettlesar med lagra økter – Rapport og Historikk, all tekst synest. Ingen JavaScript-feil.

### PC-prototype v1.6.56 – Målprofil forklart, Avslutt sist, eigen knapp for kontroll på barmark
- **Endra:** Innst. › Målprofil har ei kort forklaring øvst («✓ PÅ MÅL», raudt under, blått over), tydelege namn på
  felta (Måldjupne, Toleranse ±, Demo-snødjupne – «berre for DEMO-knappen, aldri ei ekte måling») og ein boks
  «ℹ Kvar målprofilen blir brukt» (HUD-en alltid; førarskjermen i trasé; traseen si eiga måldjupne gjeld føre).
  Demo-snødjupna blir vist med to desimalar.
- **Endra:** «⏻ AVSLUTT SNOWMAN» er flytt frå overskrifta til sist i knapperekkja, etter System.
- **Nytt:** Innst. › Kontroll har knappen **KONTROLL PÅ BARMARK (0 m SNØ)**. Han lagrar ei kontrollmåling med 0 m snø
  (etter stadfesting) og merknaden «Barmark». «Kjend snødjupne her» heiter no «Snødjupne målt med snøsonde rett under
  antenna (m)», og knappen LAGRE MED SNØSONDE. Ei kort forklaring øvst seier kva ein gjer på barmark og på snø.
- **Kvifor:** eigaren syntest Målprofil ikkje var forklart, at «Kjend snødjupne» var uklart, og ønskte Avslutt sist og
  ein eigen knapp for kontroll på barmark.
- **Testa:** nettlesar – begge panela, og at barmark-knappen sender 0 m med merknad og snøsonde-knappen sender den
  innskrivne djupna. Ingen JavaScript-feil.

### PC-prototype v1.6.55 – same tråkkemaskin i 3D-terreng og frontrute
- **Endra:** 3D-modellen av maskina har same utsjånad og mål som 2D-teikninga frå v1.6.54: belte med slitebane og
  runde endar, raudt karosseri, førarhus med frontrute, sidevindauge, tak og varsellys, motorlokk med rister, fresbom,
  raud fres, gul finisher og gule sideflapsar, og grått skjer med venger, ribber og skyvearmar. GPS-antenna (grøn) og
  eventuell antenne 2 (blå) står på taket.
- **Endra:** modellen står no med **GPS-antenna i posisjonen** (etter «Antenne framfor midten av beltet» og «til sida»),
  slik som på kartet. Før stod han med eit fast punkt i posisjonen.
- **Endra:** i frontrutevisinga er skjeret grått som på maskina (før gult). Det er framleis halvgjennomsiktig, så
  snøfargane framfor skjeret synest gjennom plata. Berre skjeret og skyvearmane er synlege der, som før.
- **Kvifor:** eigaren ønskte same tydelege maskin i 3D-modellen og frontruta som i 2D.
- **Testa:** simulert GNSS over testterrenget (`simuler-leica.py --terreng`, testlag lagt inn og sletta etterpå):
  3D-terreng bak maskina og frontrute. Ingen JavaScript-feil.

### PC-prototype v1.6.54 – tydeleg tråkkemaskin på kartet, i Maskin og i Kalibrering
- **Endra:** maskinteikninga på kartet er ny og tydelegare (ovanfrå, front opp): frontskjer med venger, belte med
  slitebane, raudt førarhus med frontrute og tak, motorlokk, fresbom, fres og gul finisher. Ho er teikna i meter etter
  maskinmåla (frontskjer, maskinbreidde og fres), så breiddene stemmer med kartet. Målpilene (t.d. «5,5 m») ligg i
  teikninga. Teikninga er meir dekkjande enn før (92 % mot 58 %), og ho er aldri mindre enn 90 px.
- **Endra:** **GPS-antenna står no midt i posisjonen** på kartet, og maskina blir teikna rundt ho etter «Antenne framfor
  midten av beltet» og «til sida». Før stod midten av teikninga i posisjonen.
- **Nytt:** Innst. › Maskin viser maskina med mål (Frontskjer, Maskin, Fres). Teikninga følgjer med medan ein skriv, og
  viser full breidde eller innkøyrd etter ARBEIDSSTILLING.
- **Nytt:** Innst. › Kalibrering viser maskina med GPS-antenna (grøn) og eventuelt antenne 2 (blå), og eit kryss for
  midten av beltet (nullpunktet). Nytt val «Tal på GPS-antenner» (1 eller 2) med plassering av antenne 2.
- **Avgjerd:** antenne 2 er førebels **berre til informasjon** (teikninga). SNOWMAN brukar framleis éin posisjon frå
  mottakaren. Lengdene i teikninga er skjematiske (PB600-klasse); berre breiddene er eigarens mål.
- **Kvifor:** eigaren ønskte maskina tydeleg som på førebiletet hans, med måla synlege i innstillingane og plasseringa
  av GPS-antenna(ne) synleg under kalibrering.
- **Testa:** simulert GNSS (`simuler-leica.py --terreng`): kart ved zoom 19/20, 3D-vising, Maskin- og Kalibrering-panelet
  med 1 og 2 antenner. Ingen JavaScript-feil.

### Dokumentasjon – PB600-sporet lagra i vegplanen
- **Nytt:** `docs/VEGEN-VIDARE.md` kap. 12 samlar CAN/J1939-sporet for PB600: kvar vi står, kva data som truleg finst
  utan ekstra sensorar, neste steg for eigaren og plan for `maskindata`-modulen. Vegplan-lina «Seinare – CAN-bus»
  peikar no hit. Detaljane står framleis i `docs/PB600-CAN.md`.
- **Avgjerd:** sporet er ikkje plassert i nokon versjon enno – det ventar på generasjon, chassisnummer og Planbuch.
- **Kvifor:** eigaren bad om at sporet blir lagra i dokumentasjonen.

### Dokumentasjon – PB600: maskina er truleg frå ca. 2020
- **Endra:** `docs/PB600-CAN.md` fekk kap. 1b. Eigaren meiner maskina er frå rundt 2020. Den nye PB600 med
  **Cummins X12 / Stage V** og iTerminal kom i oktober 2018, så maskina er truleg av den generasjonen og ikkje
  OM 460-generasjonen som instruksjonsboka i kap. 2 gjeld. Nytt open punkt 0: stadfest generasjonen (motor, skjerm,
  typeskilt).
- **Kvifor:** generasjonen avgjer kva Planbuch, motorstyring og J1939-meldingar som gjeld.

### Dokumentasjon – forundersøking PB600 SCR CAN/J1939 (ingen kode)
- **Nytt:** `docs/PB600-CAN.md` – kva som er kjent om maskindata frå PistenBully 600 SCR (ca. 2012–2018): motor
  (OM 460 LA Tier 4i), CAN-overvaking og lengdemåling i fresedjupn- og løftesylinder (frå eldre instruksjonsbok),
  standard J1939-meldingar som truleg kan brukast, metode for å finne proprietære signal, val av USB-CAN-adapter,
  tryggleiksreglar og plan for ein `maskindata`-modul. Eigaren si liste med 15 punkt står som open-punkt-tabell.
- **Avgjerd:** alt blir merkt **[D]** dokumentert / **[S]** standard J1939 / **[O]** må observerast / **[H]** hypotese /
  **[E]** eigaren sine funn. Pinout, CAN-ID-ar og signal blir aldri gjetta.
- **Avgjerd:** SNOWMAN skal berre lytte på CAN (lyttemodus, ingen sendekode). Tilrådd adapter: PEAK PCAN-USB
  opto-decoupled (IPEH-002022). Kvaser Leaf Light HS v2 er utelukka (manglar lyttemodus); ELM327 blir ikkje brukt.
- **Avgjerd:** ingen programmering før Planbuch/diagnosekontakt for rett chassisnummer er funne.
- **Kvifor:** eigaren vil ha maskindata (fres, drivstoff, motor) inn i SNOWMAN utan ekstra sensorar, og første
  prioritet var å finne rett dokumentasjon.

## 2026-10-07

### PC-prototype v1.6.53 – Rapport, Drivstoff, Kontroll og Historikk tek mindre plass
- **Endra:** same prinsipp som feltlogg-lista (v1.6.51) i resten av innstillingane – lister og lange forklaringar ligg i
  samanfaldbare boksar med ei kort samandragslinje, og blir opna ved behov (opne/lukka blir hugsa medan SNOWMAN er open):
  - **Rapport:** «Samla» står framme; **Trasear** (tal · snitt % preparert), **Økter** (tal · tid · daa) og **Drivstoff**
    (tal fyllingar · liter) er samanfalda. **Automatisk lagring** er ein boks med status i overskrifta («PÅ · sist …»),
    og dei to forklaringane er samla i «ℹ Om rapporten og automatisk lagring».
  - **Drivstoff:** «Fyllingar (N)» med éi linje per fylling (`07.10 21:30 · 180 l · 16,7 l/t · 0,85 l/daa · ✕`);
    forklaringa i «ℹ Slik blir forbruket rekna».
  - **Kontroll:** «Kontrollmålingar (N)» og «Kontrollpunkt (N)» med éi linje kvar (avvik i farge, ✕ slett, ⌖ vis på kart);
    skjemaet for nytt kontrollpunkt ligg i «＋ Legg til kontrollpunkt»; forklaringa i «ℹ Slik gjer du ei kontrollmåling».
  - **Historikk:** økta på to linjer, knappane SPEL AV / SAMLA / STOPP og VIS TRAKKA OMRÅDE / SKJUL side om side,
    forklaringa i «ℹ Om trakka område».
- **Kvifor:** eigaren ønskte at rapportar og lister ikkje skal ta for stor plass. Panela er no 40–55 % lågare
  (Rapport 1068 → 453 px, Drivstoff 817 → 467, Kontroll 979 → 439, Historikk 776 → 482 med testdata).
- **Testa:** testdata (3 økter, 3 fyllingar) – alle fire panela før/etter i nettlesar, ingen JavaScript-feil.

### PC-prototype v1.6.52 – meir i feltloggen for feilsøking
- **Nytt (1) – snødjupnestatus:** kvar gong statusen endrar seg (t.d. «OK → NEGATIVE – sjekk høgdesystem», «OK →
  Utanfor terrengmodell») blir det skrive i loggen med høgd, overflate, terrenghøgd, råverdi og terrenglag i augneblinken.
  Statusar som tyder på feil oppsett blir merkte FEIL.
- **Nytt (2) – korreksjonane i mottakaren:** CSV-fila har tre nye kolonnar: `korr_alder_s` og `base_id` frå GGA (viser om
  mottakaren faktisk brukar korreksjonane, og frå kva base) og `ntrip` (tilkopla 1/0).
- **Nytt (3) – endra innstillingar:** «Innstilling endra (kalibrering): antZ 2.8 → 10.0», tilsvarande for NTRIP/mottakar
  og førarskjermen (breidder, mål, visingar, 3D-detalj …). **Passord og brukarnamn blir aldri skrivne** – berre «endra».
- **Nytt (4) – programfeil:** JavaScript-feil i førarskjermen (med fil, linje og dei første linjene av kallstakken, maks
  10 per minutt) og ubehandla feil i trådane i tenesta, med kvar i koden feilen oppstod.
- **Nytt (5) – handlingar:** Start/Stopp prep (med distanse og tid), Demo starta/stoppa, Reset spor (knappen),
  kontrollmåling med avvik, justert høgdekorreksjon, drivstoff registrert, og når skjermkortvernet set ned 3D-detaljen.
- **Nytt (6) – oppstartsblokk** når loggen startar: versjon, operativsystem, Python, heile kalibreringa, helling,
  mottakarport, NTRIP-oppsett **utan passord**, aktive terrenglag med oppløysing, maskin- og fresbreidder, og skjerm/
  skjermkort/nettlesar frå førarskjermen.
- **Avgjerd (eigaren):** punkt 7–10 vart arkiverte til seinare (sjå under).
- **Arkivert til seinare (ikkje laga):**
  7. Terreng: maskina køyrer inn i/ut av eit terrenglag, eller byter lag.
  8. Nett: internett borte/tilbake, feil ved eksport av rapportar.
  9. Klokke: skilnad mellom PC-klokka og GNSS-tida (feil klokke gir feil prepareringsdøgn).
  10. Yting kvart minutt: minne og CPU i tenesta, biletfart i 3D, ledig diskplass.
  Òg ført opp som «kan vente»: HUD tilkopla/fråkopla, batteri/straum på Surface-en.
- **Testa:** simulator med testterreng: oppstartsblokka, antZ 2,8 → 10 → 2,8 gav NEGATIVE og tilbake til OK med tal,
  NTRIP-endring utan passord i loggen (sjekka at passordet ikkje finst i nokon loggfil), Start/Stopp prep frå skjermen,
  JavaScript-feil og ubehandla feil kom i loggen, CSV med korreksjonsalder 1.0 og base 0001.

### PC-prototype v1.6.51 – feltloggane: kompakt liste, feil og hendingar
- **Endra – lista i Innst. › System › Feltlogg** tek mykje mindre plass:
  - **Samanfalda (B):** éi linje «Loggar: N stk · X MB · ⚠ N feil ▸ Vis» til ho blir opna.
  - **Per dag (C):** «07.10.2026 · 3 loggar · 12 MB · ⚠ 3» – nyaste dagen open, dei tre siste dagane synlege, «Vis alle»
    for resten, og **⬇ dag** lastar ned alle loggane frå dagen i éi zip.
  - **Éi tynn linje per logg (A):** `21:30–22:05 · 35 min · 1,2 MB · 97 % FIX · ⚠ 3 · Hendingar · ⬇`.
  - **Nesten tomme loggar (D)** (under 10 kB, t.d. oppstart utan mottakar) blir skjulte og sletta etter 7 dagar –
    men aldri om dei har feil.
- **Nytt – Hendingar:** knappen viser hendingar og feil i loggen rett i SNOWMAN (feil i raudt), utan å laste ned.
- **Nytt – fleire hendingar i loggen:** endring i fix-type (t.d. «RTK FIX → RTK FLOAT», feil når FIX blir mista),
  «Mottakaren har slutta å sende posisjon» og «Posisjon er tilbake», NMEA med feil sjekksum (maks éi linje per minutt),
  GGA som ikkje kunne tolkast. Feil blir merkte «FEIL:» og talde (NTRIP-feil, mottakarfeil, avviste endringar m.m.).
- **Nytt – samandrag per logg** (`.json` ved sida av loggen, òg med i zip-fila): start, slutt, linjer, posisjonar,
  hendingar, feil og del av tida med kvar fix-type.
- **Testa:** falsk mottakar (FIX → FLOAT → FIX, feil sjekksum, 6,5 s utan GGA): alle hendingane kom i loggen med rett
  merking; gammal tom logg sletta, ny tom skjult; dag-zip; lista i nettlesar (lukka/open, hendingar) utan JavaScript-feil.

### Dokumentasjon – førarinnlogging, personvern, oppsummering og loggliste ført inn i vegplanen
- **Nytt:** `docs/VEGEN-VIDARE.md` kap. 10: førarinnlogging (namneknappar, førar-PIN 1234 som må endrast første gong,
  roller førar/administrator), førar knytt til økter/loggar/rapportar, personvern (arbeidsmiljølova kap. 9, slettefrist,
  modus utan namn), oppsummering av preparering med kart og PDF (drivstoff tydeleg merka estimert), og kompakt
  feltlogg-liste (A–D).
- **Avgjerd (eigaren):** blir lagt i ein seinare versjon, mest aktuelt v1.9.1 eller v2.0.1 – ikkje no. Førarar kan både
  leggje seg til sjølv på startskjermen og bli lagde til av administrator.
- **Avgjerd/tilråding:** administrator-PIN blir ikkje skriven i koden eller dokumentasjonen (repoet er offentleg); han
  blir laga ved første oppstart på kvar maskin.

### PC-prototype v1.6.50 – «Framfor · estimert» på HUD
- **Nytt:** HUD-en viser no snødjupna framfor maskina (6–30 m) saman med målt snødjupne: «FRAMFOR · ESTIMERT ≈0,51 m,
  minst 0,47 m» i stipla gul ramme nedst, mellom fart og kurs. I demo står det «(DEMO)». Same estimat som på
  førarskjermen; blir berre vist når maskina preparerer (eller demo går) og det finst målingar i nærleiken, og forsvinn
  når «Snødjupne framfor» er slått av.
- **Avgjerd:** estimatet er tydeleg mindre enn den målte snødjupna og alltid merka ESTIMERT med ≈ og stipla ramme, så det
  aldri kan forvekslast med måling (CLAUDE.md).
- **Testa:** demo i 25 s: HUD fekk estimatet (≈1,00 m, minst 0,91) og viste det merka; borte etter stopp; ingen
  JavaScript-feil. Skjermbilete av HUD (spegla) kontrollert.

### PC-prototype v1.6.49 – låst kart (nord opp) øydela 3D og frontrute
- **Retta:** Når kartet vart låst (kompasset «LÅST» / Kartretning nord opp) i 3D-terreng eller frontrute, vart 2D-kartet
  og 2D-sporet teikna **oppå** 3D-biletet: grøne strekar/felt framfor maskina i 3D, og i frontrute kunne heile
  biletet bli eit flatt 2D-kart der maskina ikkje synest. Årsak: låst kart har `transform: none`, og då mista
  kartflata sitt eige teiknelag, så kartlaga til Leaflet (z-index 200–700) kom over 3D-flata. Kartflata har no alltid
  eige teiknelag (`isolation: isolate`). Feilen har truleg vore der sidan 3D kom; han synte seg no med detaljflata.
- **Testa:** demo på testterreng, 3D og frontrute med låst kart før/etter (skjermbilete): ingen 2D-lag over 3D etter
  rettinga. Kart- og førarvising med låst kart som før. Ingen JavaScript-feil.

### PC-prototype v1.6.48 – sju feil i GNSS/NTRIP-delen retta (frå kodegjennomgang)
Eigaren fekk ein kodegjennomgang av `snowman_pc.py`, `ntripklient.py` og `rtcm.py` i ei anna Claude-økt. Alle sju
funna vart kontrollerte mot koden, stadfesta og retta her. Ingen endring i førargrensesnittet.
- **Retta (1) – HUD viste gamle GNSS-data som ferske:** alderen vart rekna frå siste oppdatering av *noko* i statusen
  (også NTRIP kvart sekund). Sluttar mottakaren å sende medan Bluetooth-porten står open, viste HUD «RTK FIX» og siste
  snødjupne utan stans. No blir alderen rekna frå siste tolka GGA (`gga_time`); etter 5 s går HUD bort frå GNSS med
  årsaka «Mottakaren har slutta å sende posisjon». Førarskjermen tømmer òg snødjupna («GNSS HAR STOPPA»), og NTRIP-sida
  viser «INGEN NY POSISJON PÅ N s».
- **Retta (2) – NMEA-sjekksum:** linjer med feil sjekksum blir forkasta før dei går inn i snødjupna eller blir sende til
  casteren, og blir talde på NTRIP-sida. **Avgjerd:** linjer *utan* sjekksum blir godtekne (nokre eldre mottakarar sender
  ingen) men talde, så SNOWMAN ikkje sluttar å verke med slike mottakarar.
- **Retta (3) – skriving til mottakaren kunne henge NTRIP:** `write_timeout=1` på porten, eigen feilhandtering for
  skrivinga, og feilen blir meld som mottakarfeil («Serial: …») utan at NTRIP-sambandet blir rive ned.
- **Retta (4) – «Serial: TILKOPLA» vart ståande** etter at porten var lukka eller sett til tom.
- **Retta (5) – falske FEIL i RTCM-vurderinga:** «Ventar på posisjonen til basen» dei første 30 s før 1005/1006 (FEIL
  først etter det), og byte blir talde per oppkopling, så «ikkje RTCM 3» ikkje blinkar etter kvar ny oppkopling.
  (Feilane kom med v1.6.39.)
- **Retta (6) – NTRIP Auto:** prøver no NTRIP 2 også når casteren tek imot sambandet men aldri svarar på NTRIP 1, og
  lukkar sambandet ved feil.
- **Retta (8) – tryggleik:** endringar (POST) blir berre godtekne frå SNOWMAN sine eigne sider (127.0.0.1/localhost på
  same port). Før kunne ei anna nettside i nettlesaren på PC-en byte caster medan passordet stod lagra, slik at
  innlogginga vart send til ein annan server. Avviste forsøk blir loggførte.
- **Testa:** einingstestar (sjekksum rett/feil/utan, RTCM-vurdering før/etter 1005 og etter nullstilling); falsk caster
  og falsk mottakar: feil NMEA forkasta, ingen FEIL over fleire ned-/oppkoplingar, HUD går frå GNSS 6 s etter at GGA
  stoppar og tilbake når ho kjem att, mottakar som ikkje les → «Serial: … Write timeout» medan NTRIP held fram,
  POST frå framand side 403 / frå SNOWMAN 200, tom port → AV, stille NTRIP 1 → tilkopla med NTRIP 2 etter 11 s;
  førarskjerm og NTRIP-side lagrar som før (både 127.0.0.1 og localhost); `simuler-leica.py --terreng` mot fasit med
  alle tre høgdeval (snitt innan ±1 cm).

### PC-prototype v1.6.47 – simulatoren viser snødjupne også med Kartverket-geoiden
- **Retta:** Testmodus (oppstartsval 3, simulert mottakar) viste ikkje snødjupne, berre «FEIL – SJEKK HØGDESYSTEM/
  KALIBRERING». Simulatoren sende NN2000-høgd med fast geoidehøgd 40,0 m. Med høgdevalet «Rå GPS-høgd → Kartverket-modellen»
  (som er rett for Zenith-en og var lagra frå feltprøva) vart høgda då ca. 5 m for låg, og SNOWMAN meinte maskina stod
  under terrenget. No sender simulatoren geoidehøgda frå Kartverket-modellen der maskina er, som ein ekte mottakar.
- **Kvifor:** testmodus skal fungere med same kalibrering som feltoppsettet, så ein slepp å endre innstillingar for å teste.
- **Testa:** `simuler-leica.py --terreng` mot fasit med alle tre høgdevala: NN2000 −0,2 cm, Kartverket-modellen +0,1 cm,
  fast tal (44,77) −1,0 cm i snitt (maks 3 cm).

### PC-prototype v1.6.46 – automatisk vern for svake skjermkort i 3D
- **Nytt:** Dei første 10 sekunda i 3D/frontrute (etter 2 s oppvarming) måler SNOWMAN tida per bilete. Klarer skjermkortet
  under ca. 15 bilete i sekundet, blir **3D-detalj nær maskina sett eitt steg ned** (HØG → NORMAL → AV), og føraren får
  melding: «3D-detalj sett ned til … – skjermkortet klarte berre ca. N bilete i sekundet. Kan endrast i Innst. › Kart.»
  Etter nedtrapping blir det målt på nytt, til farta held eller detaljen er AV.
- **Avgjerd:** vernet går berre ned, aldri opp. Vel føraren nivå sjølv med knappen, gjeld valet resten av økta (ingen
  automatikk overstyrer føraren). Held farta, blir det ikkje målt meir den økta.
- **Avgjerd (eigaren):** full skjermkorttest per maskin blir lagd i v1.9/v2.0 saman med installasjonsrettleiinga
  (docs/VEGEN-VIDARE.md kap. 9).
- **Testa:** treg programvare-GPU (ca. 1 bilete/s): NORMAL → AV med melding etter ca. 14 s; når føraren har valt sjølv,
  blir nivået verande. Ingen JavaScript-feil.

### PC-prototype v1.6.45 – skarpare spor og terreng i 3D og frontrute
- **Endra (steg 1):** teksturane i 3D blir filtrerte med det høgaste skjermkortet klarer (anisotropi, vanlegvis 16 i staden
  for 4), så spor og kurver held seg skarpe når ein ser langs bakken. «Snødjupne framfor»-estimatet blir teikna i full
  oppløysing (25 cm i staden for 50 cm) – **skraveringa er uendra**, så estimatet ser framleis aldri ut som måling.
- **Nytt (steg 2):** eiga **detaljflate ±40 m rundt maskina** med skarp tekstur (12 eller 16 pikslar per meter mot 4 elles):
  sporkantar og høgdekurver framfor skjeret er knivskarpe i 3D og frontrute. Flata følgjer maskina og blir teikna på nytt
  kvar ca. 14 m (ca. 5 ms). Teksturen blir sendt til skjermkortet maks 5 gonger i sekundet.
- **Nytt:** knapp i Innst. › Kart: **3D-DETALJ NÆR MASKINA: HØG / NORMAL / AV** (standard NORMAL). Blir 3D tregt på
  maskina, vel NORMAL eller AV.
- **Avgjerd (eigaren):** steg 1 + 2 med moglegheit for å justere/slå av. Testa i testkopi først (bilete før/etter vist og
  godkjent).
- **Testa:** simulert GNSS (`simuler-leica.py --terreng`) med testterreng, prep i gang, 3D og frontrute, alle tre nivå
  vekselvis utan JavaScript-feil; skjermbilete samanlikna. Biletfrekvens på Surface-en er ikkje målt (testmaskina har
  ikkje skjermkort).

### Dokumentasjon – 3D-test lagra som mogleg framtidig versjon (ingen endring i SNOWMAN)
- **Nytt:** `docs/VEGEN-VIDARE.md` kap. 8 med testresultat for trakka område i 3D, bakgrunnskart drapert på 3D-terrenget
  og større 3D-område. Prototypen er lagra i `docs/prototypar/3d-trakka-og-kart.py` (blir ikkje brukt av SNOWMAN).
- **Avgjerd (eigaren):** test først, så spørsmål – og etter testen: *ikkje gjer endringar no*, ta vare på det som mogleg
  framtidig versjon. PC-versjonen er framleis v1.6.44.

### PC-prototype v1.6.44 – fartsgrensa for preparering er 40 km/t
- **Endra:** Grensa for kva som blir rekna som transport, er heva frå 25 til **40 km/t** (trakka område, prosent per trasé,
  areal og prep-tid i rapporten, og avspeling i fresbreidd).
- **Avgjerd (eigaren):** Ei trakkemaskin kan av og til gå fort, så 25 km/t kunne ta bort ekte preparering. 40 km/t held
  framleis bilkøyring (som feltprøva 2026-10-06, 50–60 km/t) utanfor.
- **Testa:** syntetiske økter – biltur i 54 km/t er framleis ikkje med, arealet er uendra.

### PC-prototype v1.6.43 – trakka område i Historikk, avspeling i fresbreidd, transport blir ikkje preparert areal
- **Nytt – TRAKKA OMRÅDE (Innst. › Historikk):** vel periode (dette prepareringsdøgnet, siste 24 t, 3, 7 eller 30 døgn,
  eller alt) og trykk VIS TRAKKA OMRÅDE. Alt som er køyrt blir vist som flate i **den fresbreidda kvar økt vart køyrd med**,
  farga etter kor lenge sidan det sist vart køyrt (under 6 t, 6–24 t, 1–3 døgn, eldre), med forklaring. Under står trakka
  areal i daa (overlapp tel éin gong), tal på økter og tidsrommet. Demo/test er berre med når ein kryssar av for det, og blir
  då merka TEST. Rekna ut i SNOWMAN-tenesta som eitt bilete, så kartet ikkje blir tregt sjølv med mange økter.
- **Nytt – VIS VALD ØKT SAMLA:** heile den valde økta på ein gong, i fresbreidd.
- **Endra – avspeling:** sporet blir teikna i fresbreidda (meter, følgjer zoomen), ikkje som ei tynn strek. Overlapp blir
  ikkje mørkare. Transport og hopp i sporet blir vist som tynn stipla linje. Avspelinga startar nær nok til å sjå breidda.
- **Endra – transport:** strekningar køyrde fortare enn 25 km/t blir ikkje rekna som preparert – verken i trakka område,
  prosent preparert per trasé eller areal og prep-tid i rapporten. Køyrde km tek framleis med alt.
  (Avgjerd frå feltprøva 2026-10-06, der ein biltur gav 93,9 daa «preparert».)
- **Testa:** syntetiske økter (fire økter med ulik alder og breidd, ei med 1,8 km biltur): areal innanfor 4 % av fasit,
  biltur ikkje med, rett tal på økter per periode, demo berre med når valt; Historikk-fana i nettlesar utan JavaScript-feil,
  skjermbilete av trakka område og avspeling i fresbreidd kontrollert.

### PC-prototype v1.6.42 – NTRIP-sida viser at det er lagra
- **Endra:** Når ein trykkjer LAGRE / KOPLE TIL, skiftar knappen til «LAGRAR …» og så grøn «✓ LAGRA», og under knappen
  står «✓ Lagra kl. 11:38. Koplar til …». SNOWMAN følgjer så med på oppkoplinga i inntil 20 s og skriv anten
  «NTRIP tilkopla (NTRIP 1)» eller feilen (t.d. feil passord) i raudt. Lagring som feilar, blir vist som «LAGRING FEILA».
- **Endra:** Knappen er sperra i 2,5 s etter trykk, så fleire trykk ikkje sender fleire lagringar. Passordfeltet blir tømt
  etter lagring (passordet er lagra og står som «(uendra)»).
- **Kvifor:** Før kom det inga tilbakemelding, så det var lett å trykke fleire gonger utan å vite om det var lagra.
- **Testa:** i nettlesar mot simulert caster: tekst rett etter trykk, melding om tilkopla etter 3,5 s, ingen JavaScript-feil.

### PC-prototype v1.6.41 – NTRIP: vakthund, NTRIP 2 og liste over mountpoints
- **Nytt – vakthund:** kjem det ingen korreksjonar på 20 sekund (justerbart på NTRIP-sida, minst 5), koplar SNOWMAN opp på
  nytt av seg sjølv. Før kunne SNOWMAN vise «TILKOPLA» i det uendelege når mobilnettet hang utan at sambandet vart lukka,
  og maskina mista RTK FIX utan forklaring. Statusen viser «ingen korreksjonar på N s» medan det står på.
- **Nytt – NTRIP 2:** val av NTRIP-versjon (Auto / 1 / 2). **Auto** prøver NTRIP 1 først, akkurat som før, og NTRIP 2 berre
  når casteren avviser NTRIP 1. Feil passord og ukjent mountpoint blir ikkje prøvde på nytt med NTRIP 2. NTRIP 2-straumar
  med «chunked» overføring blir pakka ut før korreksjonane går til mottakaren. Statusen viser kva versjon som er i bruk.
- **Nytt – HENT MOUNTPOINTS:** hentar kjeldetabellen frå casteren og viser mountpoints med stad, format, satellittsystem,
  avstand frå maskina og type (enkeltbase/nettverk, «krev posisjon»). Klikk for å velje. Nærmaste base øvst.
  Brukarnamn/passord blir berre sende med til casteren dei er lagra for.
- **Endra:** NTRIP-koden er flytta til eigen modul (`ntripklient.py`). Ventetid før ny oppkopling er 10 s ved feil passord
  eller mountpoint (3 s elles), så kontoen ikkje blir sperra av mange forsøk. Caster kan no skrivast som «adresse:port».
- **Avgjerd:** NTRIP 1 er framleis standard (Auto) – gpsbase/TH og CPOS verkar som før. Kryptert samband (TLS) og
  reservecaster ventar til seriepakka (v2.0).
- **Testa:** einingstestar (chunked-utpakking med tilfeldige oppdelingar, kjeldetabell med avstand), falsk caster i tre
  modusar: NTRIP 1, berre NTRIP 2 (Auto går over til 2) og «stille» straum (vakthunden koplar opp på nytt), kjeldetabell
  over NTRIP 1 og 2, val av mountpoint på NTRIP-sida i nettlesar, og at passordet aldri blir sendt til nettlesaren.

### PC-prototype v1.6.40 – klarare tekstar i Innst. › Kalibrering
- **Endra:** Alle felt og hjelpetekstar i Kalibrering er skrivne om så det går fram kva som skal målast og kvifor:
  - «Antennehøgd: frå botnen av antennefestet ned til underkanten av belta», med hjelpetekst om å måle loddrett på flat mark og
    at antennehøgda i sjølve mottakaren (t.d. Zenith) då skal vere 0.
  - «Fast høgdeoffset» heiter no **«Høgdekorreksjon frå kontrollmåling – normalt 0»**, med forklaring på forteiknet. Same ord i
    Kontroll-fana (knappen JUSTER HØGDEKORREKSJON, stadfesting og melding), i statuslinja og i LES-MEG/FELTPROVE.
  - Høgdeval: spørsmålet «Kva høgd sender mottakaren?» med vala «Høgd over havet (NN2000) frå mottakaren»,
    «Rå GPS-høgd → Kartverket-modellen (tilrådd)» og «Rå GPS-høgd → fast tal (berre om modellen manglar)».
  - Helling: «Auto (tilrådd) – hellingsmålar i antenna om ho har», «Berre utrekna frå GPS og terreng», «Av»; «stamp/krenging»
    heiter no «fram/bak» og «side», òg i visinga av hellinga. Kortare forklaring.
  - Kalibreringsrutinen er ei nummerert liste (flat barmark → mål antennehøgd → kontrollmåling 0 på 2–3 stader → juster).
  - Ordet «referansepunkt» er bytt ut med «underkanten av belta» / «midten av beltet».
- **Endra:** Felta for antenne fram/bak og til sida er merka **«førebels berre til informasjon»** – dei blir lagra, men er
  ikkje med i utrekninga av snødjupne enno.
- **Endra:** Nedtrekksmenyane for høgd og helling går over heile breidda, så heile valet er synleg.
- **Kvifor:** Eigaren opplevde tekstane som uklare under feltprøva. Ingen utrekningar er endra.
- **Testa:** Kalibrering-fana opna i nettlesar (ingen JavaScript-feil), skjermbilete kontrollert.

### PC-prototype v1.6.39 – kontroll av RTCM-korreksjonane, og to feil i NTRIP-tilkoplinga retta
- **Nytt:** NTRIP-sida viser no om korreksjonane faktisk er gyldige: tal på gyldige RTCM 3-rammer (CRC-24Q-kontroll), CRC-feil,
  meldingstypar, kva satellittsystem basen sender, basestasjonen (ID frå 1005/1006) og **avstanden til basen**, og ei kort
  vurdering («OK: gyldige korreksjonar … ligg feilen i mottakaren», «FEIL: ikkje RTCM 3», «basen sender ikkje posisjonen sin» o.l.).
  Ei samanfatning blir skriven i feltloggen kvart minutt. Dataa til mottakaren blir ikkje endra.
- **Retta:** «SOURCETABLE 200 OK» (casteren sender kjeldetabellen fordi mountpointet ikkje finst) vart godteke som tilkopla,
  og teksten vart send vidare til mottakaren som om det var korreksjonar. No: tydeleg feilmelding om at mountpointet ikkje finst.
- **Retta:** Etter «ICY 200 OK» las SNOWMAN fram til ei tom linje. Castarar som startar RTCM med éin gong, kunne då miste opptil
  16 kB korreksjonar ved kvar tilkopling. No blir berre statuslinja (og ei eventuell tom linje) lesen.
- **Endra:** Tipset om `INTERFACEMODE` (NovAtel) på NTRIP-sida er fjerna – Zenith35 Pro brukar @GNSS-kommandoar og treng ingen
  oppstartskommandoar. Sida forklarer no innstillingane på Zenith-en i staden.
- **Kvifor:** Feltprøva 2026-10-06 gav ikkje RTK FIX sjølv om RTCM kom fram. Med kontrollen kan neste feltprøve avgjere med éin
  gong om feilen ligg i basen/mountpointet eller i mottakaren.
- **Testa:** einingstest (rammer delte over fleire pakkar, søppel, CRC-feil, 1005-posisjon → avstand), falsk caster med og utan tom
  linje etter ICY, feil mountpoint (kjeldetabell), og simulert GNSS (`simuler-leica.py --terreng`).
- **Står att:** fartsgrense for preparering (transport skal ikkje gi areal) – kjem i ein seinare versjon.

### Dokumentasjon – resultat frå første feltprøve (Zenith35 Pro, bil til Fjellsætra)
- **Nytt:** `docs/FELTPROVE.md` har fått resultatet frå feltprøva 2026-10-06: kva som fungerte (Bluetooth, NTRIP, NN2000-høgd,
  rapportar, tunnel), kvifor det ikkje vart RTK FIX (Base-modus, Extra Safe RTK, berre GPS, dårleg sikt), rette Zenith-innstillingar
  og ei sjekkliste til neste forsøk, med GSM-testen som skil mellom feil i Bluetooth-korreksjonar og feil i basen.
- **Avgjerd:** til v1.6.39 – fartsgrense (ca. 25 km/t) så transport ikkje blir rekna som preparert areal, og retta tipstekst på
  NTRIP-sida (Zenith35 Pro brukar @GNSS-kommandoar, ikkje NovAtel `INTERFACEMODE`).
- **Avgjerd:** tilrådd mottakar til seriepakka (v2.0) er u-blox ZED-F9P/X20P med to antenner; Leica/GeoMax framleis støtta.
- **Kvifor:** så resultatet og neste steg ligg klart til neste feltprøve.

## 2026-10-06

### PC-prototype v1.6.38 – oppstartskommandoar til mottakaren, og ny tilkopling når oppsettet blir endra
- **Nytt:** «Oppstartskommandoar til mottakaren» i NTRIP-oppsettet: tekstlinjer som blir sende kvar gong porten blir opna. For GeoMax Zenith35 Pro (NovAtel OEM7) kan `INTERFACEMODE THISPORT AUTO NOVATEL ON` få mottakaren til å ta imot RTCM-korreksjonane på Bluetooth-porten. Svaret frå mottakaren (t.d. «<OK») blir vist som «Svar frå mottakar» og lagra i feltloggen.
- **Retta:** Endra COM-port, baud eller oppstartskommandoar vart ikkje tekne i bruk før SNOWMAN vart starta på nytt; no blir porten opna på nytt med éin gong. Same for NTRIP: ny caster, mountpoint, brukar eller passord gir ny tilkopling.
- **Bakgrunn:** Zenith35 Pro får korreksjonane (NTRIP tilkopla, RTCM mottatt) men står på SBAS (kvalitet 9). GeoMax tek normalt berre imot korreksjonar via eige modem, UHF eller «nettverk via kontroller», så RTCM på Bluetooth må slåast på.
- **Testa:** test-mottakar over TCP: kommandoen blir send når oppsettet blir lagra, porten blir opna på nytt, svaret «<OK» blir vist.

### PC-prototype v1.6.37 – «FIX 9» blir vist som SBAS
- **Endra:** GGA-kvalitet 9 (SBAS/EGNOS – brukt av NovAtel-baserte mottakarar som GeoMax Zenith) blir vist som **SBAS**, ikkje «FIX 9». Også 3 (PPS), 7 (manuell) og 8 (simulert) har namn. Snødjupne krev framleis RTK FIX.

### PC-prototype v1.6.36 – NTRIP-oppsettet viser og tek vare på det som er lagra
- **Retta (alvorleg):** Skjemaet i LEICA / CPOS / NTRIP-OPPSETT vart aldri fylt med det som var lagra. COM-port stod alltid «COM3», og mountpoint/passord var tomme. Trykte ein LAGRE, vart den fungerande porten (COM4) og mountpointet skrivne over – og mottakaren kopla frå. No blir skjemaet fylt med det som er lagra; passordet blir aldri sendt til nettlesaren, og eit tomt passordfelt endrar ikkje passordet.
- **Nytt:** Lista over seriellportar på PC-en (USB, Bluetooth) med skildring, som forslag i COM-port-feltet, og påminning om å bruke den **utgåande** Bluetooth-porten. `GET /api/config`, `GET /api/ports`.
- **Funne av:** eigaren, som mista koplinga til Zenith35 Pro etter å ha lagra på nytt (COM3 og tomt mountpoint).
- **Testa:** skjemaet viser lagra port, caster, mountpoint og brukar; lagring endrar ingenting som ikkje er endra; passordet er uendra.

### PC-prototype v1.6.35 – retta: SNOWMAN fann ikkje att posisjonen etter tunnel
- **Retta (alvorleg):** Når mottakaren mista posisjonen (tunnel: GGA utan breidd/lengd), lagra fart/kurs-utrekninga eit tomt punkt. Alle GGA-meldingar etterpå feila då med «GGA parse: unsupported operand type(s) for -: 'float' and 'NoneType'», og SNOWMAN stod fast på NO FIX til han vart starta på nytt – sjølv om mottakaren hadde fått posisjon att. No blir tomme punkt hoppa over, og posisjonen kjem att med éin gong.
- **Funne av:** eigaren, som køyrde gjennom ein tunnel med GeoMax Zenith35 Pro via Bluetooth.
- **Testa:** GPS → tunnel (2 meldingar utan posisjon) → GPS att: gammal kode feila på kvar melding etterpå, ny kode viser posisjonen att utan feil.

### PC-prototype v1.6.34 – Kartverket sin geoidemodell for NN2000
- **Nytt:** Geoidemodellen HREF2018B (NN2000 over EUREF89) frå Kartverket ligg i `pc/v1.6/geoide/` (270 kB, frå PROJ-data). Lisens CC BY 4.0, kreditert i `geoide/LES-MEG.txt` og under Innst. «© Kartverket».
- **Nytt:** «GNSS-høgd frå mottakaren» har valet **Ellipsoidisk – Kartverket geoidemodell (tilrådd)**: NN2000-høgd = (høgd + geoidehøgd i GGA) − N frå modellen der maskina er. Rett anten mottakaren sender ellipsoidisk høgd (geoidehøgd 0) eller høgd over sin eigen geoide.
- **Nytt:** NTRIP-oppsettet viser høgda frå mottakaren, geoidehøgda i meldinga, ellipsoidisk høgd, N frå Kartverket-modellen og **NN2000-høgd** – så høgda kan kontrollerast mot kartet.
- **Retta:** Hjelpeteksten sa «geoidehøgd ca. 40 på Sunnmøre»; rett er ca. 45 m (HREF2018B: 44,8 m i Sykkylven, 45,1 m på Fjellsætra).
- **Bakgrunn:** Eigaren såg at høgda frå GeoMax Zenith35 Pro var feil (55,6 m i Sykkylven sentrum). Det passar med ellipsoidisk høgd; med modellen blir NN2000-høgda ca. 10,9 m.
- **Testa:** N = 39,1 m i Oslo (som venta), 44,76 m i Sykkylven; same NN2000-høgd med geoidehøgd 0 og med geoidehøgd i meldinga; utanfor Noreg gir «manglar geoide».

### PC-prototype v1.6.33 – NTRIP: rett User-Agent og betre feilmelding
- **Retta:** NTRIP-førespurnaden hadde User-Agent «SNOWMAN-NTRIP/1.1». NTRIP 1.0 krev at han byrjar med «NTRIP », og nokre castarar avviser elles. No: `NTRIP SNOWMAN/<versjon>`, og `Host`-felt.
- **Endra:** Mellomrom før/etter brukarnamn, passord og mountpoint blir fjerna (lett å få med ved inntasting).
- **Endra:** Feilmeldinga forklarer 401 (feil brukarnamn/passord, ingen tilgang til mountpointet eller kontoen i bruk på ei anna eining) og 404 (mountpointet finst ikkje).
- **Bakgrunn:** Eigaren fekk «HTTP/1.1 401 Unauthorized» mot gpsbase.dyndns.org:2101, mountpoint TH. Porten er rett (casteren svarte).
- **Testa:** mot ein lokal test-caster: rett førespurnad og feilmelding.

### PC-prototype v1.6.32 – tilbakeknapp på NTRIP-oppsettet, Zenith35 Pro tilkopla
- **Retta:** NTRIP/GNSS-oppsettet (Innst. › Kart › LEICA / CPOS / NTRIP-OPPSETT) hadde ingen veg tilbake i kiosk og app-vindauge. No er det knappen **← TILBAKE TIL SNOWMAN** øvst og nedst.
- **Testa av eigaren:** GeoMax Zenith35 Pro via Bluetooth (COM4) sender NMEA rett til SNOWMAN utan ekstra oppsett: «Serial: TILKOPLA COM4», GPS, 16 satellittar, HDOP 0,9, posisjon og høgd. Første ekte mottakar kopla til SNOWMAN.

### Utstyr – GeoMax Zenith35 Pro via Bluetooth
- **Fakta:** GeoMax Zenith35 Pro GSM-UHF-TAG (2018) er tilgjengeleg: smartantenne med mottakar, Bluetooth, GSM-modem, UHF og hellingsmålar (Tilt&Go).
- **Avgjerd (eigar):** Han skal koplast til SNOWMAN via Bluetooth. Det krev ingen ny kode: Bluetooth gir ein COM-port (Windows) eller `/dev/rfcomm0` (Linux), som SNOWMAN les som ein vanleg seriellport. Framgangsmåte i `docs/FELTPROVE.md`.

### Utstyr – antenna er ei Leica MNA1202 GG
- **Fakta:** Antenna som er tilgjengeleg, er Leica MNA1202 GG (art. 753221, 2007): maskinantenne til Leica MNS1200-systemet, GPS + GLONASS L1/L2, TNC-kontakt, 4,5–18 V DC. Ho er berre ei antenne utan eigen mottakar og utan hellingsmålar. Tidlegare antaking om GS07 med Lemo-kontakt var feil.
- **Avgjerd:** Det trengst ein GNSS-mottakar mellom antenna og PC-en (Leica-mottakaren som høyrde til, eller ein rimeleg RTK-mottakar med bias-tee). Hellingskorreksjonen brukar utrekna helling. Sjå `docs/FELTPROVE.md`.

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
