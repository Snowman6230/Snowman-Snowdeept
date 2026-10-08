# Terrain Engine – spesifikasjon

SNOWMAN by Alpindata · Analyse 2026-10-04 · Status: **v1.6 ferdig** (bibliotek, GeoTIFF, Topocad DTM, barmark, snødjupne) · v1.7 planlagt

Terrain Engine reknar ut ekte snødjupne ved å samanlikne den kalibrerte høgda til maskina (RTK-GNSS)
med ein terrengmodell av barmark. Dokumentet skildrar korleis terreng blir lagt inn, bytt ut og brukt.

---

## 1. Terrengbibliotek

Kvart anlegg har eit **terrengbibliotek** med fleire lag. Kvart lag har:
namn · type · kjelde · dato · oppløysing · koordinatsystem · høgdesystem · dekningsområde · prioritet · aktiv/inaktiv.

| Funksjon | Føremål |
|---|---|
| **Legg til** | T.d. Kartverket DTM 1 m som grunnlag for heile anlegget + eigen LiDAR som detalj for bakkane |
| **Erstatt** | Ny skanning etter grave-/planeringsarbeid. Gammal versjon blir teken vare på (kan rullast tilbake) |
| **Slå av/på** | Teste med/utan eit lag |
| **Prioritet** | Der lag overlappar, vinn det beste (eigen LiDAR 0,25 m før Kartverket 1 m) |
| **Slett** | Med stadfesting |

**Oppslag:** For kvar GNSS-posisjon blir det høgast prioriterte aktive laget med gyldig høgd brukt.
Hol/nodata → neste lag. Føraren ser kjelda, t.d. «Terreng: Eigen LiDAR 09/2026 · 0,25 m».

## 2. Typar flater

| Type | Innhald | Gir |
|---|---|---|
| **Barmark (DTM)** | Bakken utan snø – **påkravd** | Snødjupne |
| **Målflate** | Ønskt snøoverflate (prosjektert, eller barmark + måldjupne) | Kor mykje snø som skal fjernast/tilførast (gir «Målprofil» ekte innhald) |
| **Snøflate (oppmåling)** | Skanning med snø, t.d. drone | Kontroll av snødjupne, snøvolum for heile bakken |

v1.6 tek berre **barmark**, men biblioteket blir bygd slik at dei andre typane kan leggjast til utan omskriving.

## 3. Opplasting – veivisar i fana «Terreng»

1. **Vel type** (barmark / målflate / snøflate) – kort forklaring per type.
2. **Vel fil** – appen viser tilrådd og godtekne format (tabell under).
3. **Automatisk analyse** frå filhovudet: koordinatsystem, høgdesystem, dekning, oppløysing, nodata.
4. **Kontroll** med tydelege varsel, t.d.:
   - ⛔ «Fila manglar koordinatsystem – kan ikkje brukast»
   - ⚠️ «Høgdesystem ukjent – stadfest at det er NN2000»
   - ⚠️ «Fila dekkjer ikkje posisjonen til maskina»
5. **Førehandsvising** på kartet (skuggerelieff + omriss).
6. **Kontrollpunkt** (valfritt): køyr til kjent punkt med RTK FIX og sjå avviket.
7. **Lagre** med namn og prioritet.

### Format (blir vist i appen)

| | Format | Krav |
|---|---|---|
| ✅ **Tilrådd** | **GeoTIFF (.tif)** – terrengmodell | Barmark, 0,25–1 m rute, EUREF89 UTM 32 eller 33, NN2000 |
| ✅ Godteke | **Topocad DTM (.dtm)** – trekantmodell (v1.6.3) | Blir gjort om til 0,5 m rutenett. EPSG frå fila (eller tolka frå namnet). Høgdesystem står ikkje i fila – stadfest NN2000 |
| ✅ Godteke | **LAS/LAZ** – punktsky | Bakkepunkt (klasse 2) blir brukte; blir gjort om til rutenett ved import |
| ✅ Godteke | **XYZ/CSV** | Kolonnar austing, nording, høgd i same koordinatsystem |
| ⛔ Ikkje godteke | OBJ, PLY, bilete | Manglar koordinatar / ikkje høgdedata |

Kjelde utan eiga skanning: Kartverket DTM 1 m frå hoydedata.no (GeoTIFF, EUREF89 UTM 33, NN2000).
Merk: hoydedata.no er stengt fredag kl. 16 – måndag kl. 07.

## 4. Kritiske fallgruver

- **UTM-sone 32 eller 33.** Sunnmøre ligg i sone 32, men Kartverket leverer ofte nasjonale produkt i sone 33.
  Motoren må rekne GNSS-posisjonen om til sona kvart lag er lagra i.
- **Høgdesystem.** Terreng er i NN2000. Leica kan levere NN2000 *eller* ellipsoidisk høgd – skilnad ca. 40 m på
  Sunnmøre. Eiga innstilling under Kalibrering: «GNSS-høgd: NN2000 / ellipsoidisk». Tilrådd: still inn Leica til NN2000.

## 5. Ytelse, utrekning og vising

- **Minne (Surface 4 GB):** Alle filer blir gjorde om til eit internt, oppdelt rutenett ved import. Berre ruter nær maskina
  blir lasta. Store LiDAR-filer går fint.
- **Utrekning i lokal teneste (Python):**
  `snødjupne = (GNSS-høgd − antennehøgd over referansepunkt − fast høgdeoffset) − terrenghøgd`
  Pitch/roll (IMU) kjem seinare. Resultatet blir sendt med status, kjelde og kvalitet til førarskjerm og HUD.
- **Ærleg vising:** Snødjupne blir berre vist når RTK FIX + terreng dekkjer posisjonen + kalibrering er sett.
  Elles: «UTANFOR TERRENGMODELL», «IKKJE MÅLT – RTK FLOAT», osv.
- **Anleggspakke:** Terrengbiblioteket kan eksporterast saman med anleggsprofilen (zip), så alle maskiner får same terreng.

## 6. Trasear og anleggsobjekt

> **Status (v1.6.23):** trasear og forbodne område er laga – teikning, omriss frå terrengmodell, prosent preparert i
> prepareringsdøgnet, gjeldande trasé på førarskjermen og varsel. Rapport per trasé (v1.6.24), uprepart areal på kartet og
> måldjupne per trasé (v1.6.25) er òg laga. Anleggsobjekt (punkt) står att. Sjå `pc/v1.6/trasear.py`.

Anlegget kan registrere **ytterpunkt (omriss) for kvar trasé** og **punkt for faste objekt**.

### Trasear (polygon)
Namn, type (nedfart / løype / park / transportveg), farge, eventuell eiga måldjupne.

**Gir:**
- **Dekningsgrad per trasé:** «Familiebakken: 87 % preparert i dag», og uprepart areal synleg på kartet.
- **Varsel når maskina er utanfor trasé** eller nær kant (stup, skog, gjerde).
- **Rapport per trasé:** tid, areal, snødjupne-statistikk (min/snitt), snøvolum når målflate finst.
- **Eiga måldjupne per trasé** (t.d. 0,8 m i nedfart, 0,4 m i langrennsløype).
- Viser kva trasé maskina er i, på førarskjerm og HUD.
- Kontroll av at terrengmodellen dekkjer heile traséen.

### Anleggsobjekt (punkt)
Snøkanon, hydrant, heismast, bygg, kum, kabel, steinar og andre hindringar.

**Gir:** varsel når maskina nærmar seg (t.d. 15 m), symbol på kartet, og kopling mot Snowman Hydrantstyring (hydrantar).

### Registrering – tre måtar
1. **Køyr og registrer:** trykk «Registrer ytterpunkt» ved kvart hjørne, eller «Følg kant» som loggar kanten kontinuerleg med RTK.
   Mest nøyaktig og krev ingen kartkunnskap.
2. **Teikn på kartet:** klikk hjørna på skjermen. Raskt, men berre så nøyaktig som bakgrunnskartet.
3. **Importer fil:** GeoJSON, KML, GPX eller SOSI frå kommune/anleggsplan.

Trasear og objekt blir lagra i anleggsprofilen og følgjer med til alle maskiner.

## 6b. Snøflateminne – estimat framfor maskina frå tidlegare trakka overflate (v1.6.58)

Barmarka endrar seg ikkje når maskina planerer – det gjer snøoverflata. Målinga under maskina er difor alltid
rett. Estimatet framfor maskina kan derimot bruke at ei planert overflate er jamn:

- **Lagring** (`snoflate.py`, `data/snoflate.json`): kvar gyldige snødjupne (RTK FIX, kalibrert, i terrengmodellen)
  lagrar snøoverflata (NN2000) i ei rute på 1 × 1 m med tid, i 7 døgn. Testmodus blir lagra merka som test.
- **Modell:** overflata følgjer den store forma på terrenget, ikkje bekkar/groper/kular.
  `Tg` = glatta terreng (snitt ±6 m), `r = overflate − Tg` (jamn), estimert djupne = `r(x) + Tg(x) − terreng(x)`.
- **Estimat:** same rutemønster som før (2 × 2 m, 4–40 m framfor), berre overflate under 72 t, minst 3 målingar
  innanfor 8 m og den næraste innanfor 6 m. Alltid merka «ESTIMERT · TIDL. FLATE» med alder.
- **Timar og av/på (v1.6.59):** knappen «≋ Flate» nedst opnar ein meny: AV · 3 · 5 · 10 · 15 · 24 · 48 · 72 t (standard
  24 t), same val i Innst. › Kart. Fungerer før og under «Start prep». AV = estimatet byggjer berre på snødjupna målt i
  denne økta. «Gløym tidlegare overflate» slettar minnet (t.d. etter mykje nysnø).
- **Førre besøk (v1.6.59):** kvar rute hugsar også overflata frå førre preparering (målingar med over 2 t mellomrom =
  nytt besøk). HUD-en viser då «OVERFLATE SIDAN SIST ±x cm» når snødjupna blir målt, og «SIST MÅLT HER ≈x m»
  (estimat, stipla) når målinga manglar, t.d. utan RTK FIX. Hovudtalet i HUD-en er alltid dagens målte snødjupne.
- **Testa** (`testsnoflate.py`): planert overflate over bekkefar – snittavvik 0,5 cm (enkel djupne-interpolasjon:
  5 cm, opptil 66 cm feil midt i bekken). Når snøen ligg jamt oppå terrenget (ikkje planert) er det omvendt –
  difor av/på-knappen. Direkte interpolasjon av overflata vart prøvd og forkasta (store feil i bratt bakke).

## 6c. Snøkart – estimat av snøendring frå vêrvarselet (prototype v1.6.72, steg 1–2)

**Grunnregel (eigaren 2026-10-09):** alle funksjonar i Vêr byggjer på **den gjeldande terrengmodellen** i SNOWMAN –
dei aktive barmark-laga, høgast prioritet vinn (same som snødjupnemålinga). Høgda til varselet, «ved maskina» for
stasjonane og snøkartet blir alle henta derifrå. Står maskina utanfor terrengmodellen, blir snøkartet lagt midt på
det høgast prioriterte laget.

Kode: `pc/v1.6/snokart.py` (modell), `/api/snowmap` i `snowman_pc.py`, overlay `SNK` i `driver.html`.

**Rutenett:** `TerrainLibrary.patch` rundt maskina, ±300 / ±600 / ±1200 m, 301 × 301 ruter (2–8 m). Midten blir festa
til eit 50 m-rutenett så lé-tala kan gjenbrukast medan maskina køyrer. Rekning: ca. 0,2–0,4 s for 24–48 t.

**Steg 1 – nysnø:** temperatur −0,65 °C/100 m, nedbør +7 %/100 m (0,5–2 ×), snødel frå våttemperatur
(−0,5…+1,5 °C), nysnøtettleik etter Hedstrom & Pomeroy (tyngre i vind), smelting 0,15 mm/°C/t av snøen i perioden.

**Steg 2 – vindflytting:**
- Lé-tal Sx (Winstral m.fl. 2002) per rute og 16 vindretningar, inntil 100 m i lo. Relativt lé-tal
  Sxr = Sx − 0,7 · snitt(Sx innan 100 m) styrer erosjon, avsetjing og lokal vind (ryggar/kantar/søkk skil seg ut).
- Terskel 5 m/s (kald laus snø), 7 m/s (−2…0 °C), 10 m/s (over 0 °C). Erosjon ∝ (U − Ut)³, avgrensa av laus snø.
- Transport 40 m medvinds, spreidd over ca. 50 m, lagd att etter skjerming. Masse halden (15 % fordampar),
  fokksnø 250 kg/m³. «Laus snø frå før» (0–20 cm, 90 kg/m³) er eit val føraren gjer.

**Vising:** eigne fargar (blå skala for snøendring, oransje ↔ blå for vindeffekt) – med vilje ulike dei for målt
snødjupne – skravur, «ESTIMAT»-vassmerke og banner «ESTIMAT – VÊRMODELL, IKKJE MÅLING». Terrengskugge (overdriven i
slakt terreng) og høgdekurver for orientering.

**Ikkje med enno (steg 3–5):** setjing, smelting av eldre snø, totaldjupne frå snøflate-minnet, nedbør og vind
bakover i tid frå Frost, kalibrering mot RTK med treffsikkerheit, tidsglidar, snøproduksjon frå Hydrantstyring.
Parameterane over er litteraturverdiar og må kalibrerast mot målingar på anlegget.

## 7. Rekkjefølgje

| Versjon | Innhald |
|---|---|
| **v1.6** | Terrengbibliotek (legg til, erstatt, av/på, prioritet), GeoTIFF, barmark. Ekte snødjupne i spor, førarskjerm og HUD. Testa med syntetisk terreng med kjend fasit |
| **v1.6.2** | HUD på mobil, HUD-knapp |
| **v1.6.3** | Topocad DTM-import. Testa med parkeringsplass og lysmaster, Fjellsætra |
| **v1.6.4–6** | Test over ekte terrengmodell (simanlegg). Visingar: kart, førar, horisont, 3D-terreng og frontrute. Estimert snødjupne framfor maskina |
| **v1.6.7** | Kontrollmålingar (kjend snødjupne) og kontrollpunkt (kjend terrenghøgd), justering av høgdeoffset |
| **v1.6.23** | Trasear og forbodne område: teikne, omriss frå terrengmodell, prosent preparert, varsel |
| Neste | Kartverket DTM 1 m for Fjellsætra. Test av UTM 32/33 og NN2000 |
| **v1.7** | Anleggspakke, LAS/LAZ- og XYZ-import |
| **v1.8** | Trasear og anleggsobjekt (registrering, dekningsgrad, varsel, rapport per trasé) |
| Seinare | Sjå `docs/VEGEN-VIDARE.md`: maskingeometri (fres/skjer), IMU, to antenner, målflate og snøflate |
