# Terrain Engine – spesifikasjon

SNOWMAN by Alpindata · Analyse 2026-10-04 · Status: **planlagt (v1.6–v1.7)**

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

## 7. Rekkjefølgje

| Versjon | Innhald |
|---|---|
| **v1.6** | Terrengbibliotek (legg til, erstatt, av/på, prioritet), GeoTIFF, barmark. Ekte snødjupne i spor, førarskjerm og HUD. Testa med syntetisk terreng med kjend fasit |
| **v1.6.1** | Kartverket DTM 1 m for Fjellsætra. Test av UTM 32/33 og NN2000 |
| **v1.7** | LAS/LAZ- og XYZ-import, kontrollpunkt, anleggspakke |
| **v1.8** | Trasear og anleggsobjekt (registrering, dekningsgrad, varsel, rapport per trasé) |
| Seinare | Målflate og snøflate, IMU (pitch/roll), ekte 3D-terreng i førarperspektivet |
