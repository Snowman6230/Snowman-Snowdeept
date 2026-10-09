# Lokal AI i SNOWMAN (prototype v1.6.74–75)

AI-knappen (✦ AI) i verktøylinja opnar eit overlay med fem preparéringsråd. Råda kan visast som eigne lag på
hovudkartet («Vis på kartet»). Laga blir verande når overlayet er lukka, så føraren ser dei medan han køyrer, og
kan slåast av med knappane nede til venstre på kartet. Alt anna i SNOWMAN går vidare i bakgrunnen. Vêr og AI deler
plass på skjermen – det eine lukkar det andre.

Kode: `pc/v1.6/ai.py` (modell og læring), `/api/ai` i `snowman_pc.py`, `AIP` i `driver.html`.

## Kva «lokal AI» er her

Ikkje ein språkmodell og ingen skyteneste. Det er ein lærande modell som køyrer på PC-en i maskina, utan nett, og
som kombinerer det SNOWMAN veit om akkurat dette området:

- den gjeldande terrengmodellen og snøkartet (TERRAIN-ENGINE kap. 6c)
- RTK-målingane (snøflate-minnet), trasear med måldjupne og anleggsobjekt (snøkanon/hydrant)
- vêret frå stasjonane nær GPS-posisjonen (MET Frost) og varselet (MET Locationforecast)

## Automatisk tilpassa staden (krav frå eigaren)

Ingenting er sett opp for Fjellsætra spesielt. Alt blir henta og lært frå GPS-posisjonen:

| Kva | Korleis |
|---|---|
| Områdeprofil | Blir laga automatisk første gong SNOWMAN er meir enn 5 km frå ein kjend stad (`data/ai-profil.json`). Høgder frå terrengmodellen, stasjonar valde etter GPS. |
| Lokalt klima | Profilen lærer vindrosa (timar over 3 m/s) og nattetemperaturen frå vêret bakover. Viser t.d. «mest vind frå vest – fokksnø samlar seg typisk i heng som vender mot aust». |
| Nedbørsnivå | Nedbørsfaktor frå RTK-kalibreringa (snøkartet). |
| Kvar snøen kjem | Læringa i faste 10 × 10 m UTM-ruter (snøkartet) – gjeld berre der ho er lært. |
| Stasjonar og varsel | Næraste stasjonar og varsel for staden og høgda. |

Test og ekte data blir haldne kvar for seg (eigne profilar og læringsfiler).

## Dei fem råda

1. **Tidspunkt å preparere.** Kvar time i varselet får ein score (0–100): nedbør, vind, våt snø og svært kaldt trekkjer
   ned; kuldegrader etter preparering og «snøfallet er over» trekkjer opp; «meir snø kjem straks» trekkjer ned.
   Per trasé: tidsbruk = areal / (2,5 m/s · 5,5 m · 60 %), beste start slik at traseen er ferdig før opning
   (`aiOpen`, standard kl. 09). Behov (høg/middels/låg) etter tid sidan sist preparert og dekning.
2. **Snøflytting med skjeret.** Overskot og underskot mot måldjupna (± toleranse) i totaldjupna frå snøkartet,
   delte i 60 m-rutar. Par i same trasé innan 120 m (oppover maks 40 m), helst nedover. Flyttingar under 20 m³ blir
   ikkje viste. Kart: gul stipla pil med «SKYV x m³».
3. **Hol i spora.** Uprepart areal inne i traseane dette prepareringsdøgnet (trasé-statusen). Avgrensa flekkar
   frå 8 m² til 25 % av traseen; smale kantstripar (under 2,5 m breie) blir ikkje rekna. Traseer under 50 %
   preparert blir ikkje leita gjennom. Kart: oransje ring med «HOL x m²».
4. **Kvalitetsscore per trasé.** Dekning 40 %, del av traseen innan måldjupna 30 %, jamnleik 15 %, hol 15 % (vekta
   om når djupne manglar). Karakter god / brukbar / svak og det svakaste punktet.
5. **Snøproduksjon – for lite snø.** Område der totaldjupna **etter venta nysnø dei neste 24 t** er minst 5 cm under
   måldjupna minus toleransen. Delte i 80 m-rutar. For kvart område: manglande djupne, areal, volum snø, vatn
   (× 0,45), timar med éin kanon (`aiGunRate`, standard 25 m³/t – grovt), næraste snøkanon/hydrant og første
   produksjonsvindauge for høgda der. Kart: **raudt skravert** (lys: 5–20 cm, raud: 20–40 cm, mørk: over 40 cm for
   lite), raud etikett «❄ MANGLAR x cm» og stipla linje til næraste kanon/hydrant.

## Visuelt for føraren

- Eigne farger og skravur – aldri same uttrykk som målt snødjupne.
- Etikettar står alltid rett opp, også når kartet roterer med maskina (CSS-variabelen `--aiDeg`).
- Alt er merkt «AI-FORSLAG · ESTIMAT» (og TEST/DEMO når det gjeld).

## Opningstider (v1.6.75, `opningstid.py`)

Tidspunkt-rådet reknar mot **neste opning** frå opningstidene (data/opningstid.json, AI › Opningstider › Endre):

| Standard | |
|---|---|
| Laurdag og søndag | 10–16 |
| Kveldskøyring | tysdag, onsdag og fredag 18–21 (varierer mellom anlegg – endre manuelt) |
| Skoleferiar og heilagdagar | 10–16 (i tillegg til kveldskøyring): juleferie 21.12–1.1, vinterferie veke 8 og 9, påskeferie (laurdag før palmesøndag – 2. påskedag), heilagdagar |
| Stengt | 24.12 og 25.12, og utanfor sesongen (standard 1.12–30.4) |
| Manuelle unntak | per dato: ekstra opning, andre tider eller stengt – går framfor alt anna |

Heilagdagane blir rekna ut i programmet (påskeformelen) – fungerer utan nett i heile landet. Skoleruta varierer
mellom fylke og kommunar (t.d. har Vestland både veke 8 og 9), så standarden tek med begge vekene; sjekk skoleruta
for fylket/kommunen og endre om det trengst. Utanfor opningstidene brukar tidspunkt-rådet kl. 10 (`aiOpen`).

## Tale (v1.6.75)

Av/på i AI-overlayet («🔊 Tale PÅ / 🔇 Tale AV»), standard AV. Når tale er på:
- **AI-en snakkar:** korte varsel medan maskina køyrer – inn i område med for lite snø, hol i sporet innan 40 m,
  snøfall eller sterk vind innan ein time. Kvar melding høgst kvart 3. min (vêr éin gong i timen).
- **Føraren snakkar:** 🎤 «Spør AI» nede til høgre. Forstår spørsmål om snø som manglar, tidspunkt, vêr, hol,
  kvalitet, snøflytting, opningstid og snødjupna her («hjelp» gir lista).
- Opplesing: talemotoren i Windows/nettlesaren (norsk stemme om ho er installert) – utan nett.
  Talegjenkjenning i nettlesaren krev oftast nett; utan blir det skrivefelt med skjermtastatur.
- Spørsmåla blir lagra som tekst i den lokale læringsloggen (ikkje lyd), så AI-en ser kva førarane vil spørje om.

## Opplæring og nye funn (v1.6.75)

- **Lokal læringslogg** (`data/ai-laering.jsonl`, test for seg): kvar natt blir område med for lite snø (40 m-ruter),
  hol i spora (20 m-ruter) og treffsikkerheita mot RTK registrerte éin gong per prepareringsdøgn. I tillegg
  førarens 👍/👎 på kvart råd og talekommandoar (forstått eller ikkje).
- **Nye funn** (seksjon 6): hol som går igjen same stad, fast underskot same stad (≥ 3 døgn), snømodellen som bommar
  same vegen, råd som førarane meiner er (lite) nyttige, og spørsmål AI-en ikkje forstår – dei siste er forslag til
  korleis SNOWMAN kan utviklast vidare.
- **Opplæringspakke** (⬇ i seksjon 6): anonymisert zip for ein framtidig sentral SNOWMAN-AI – utan posisjonar,
  trasénamn, talt tekst, førarnamn, lyd og GNSS-spor. Blir **ikkje** sendt automatisk; «Del sentralt» er AV og ikkje
  bygd. Først skal kvart anlegg lære lokalt.

## Ikkje med enno

Språkmodell-assistent (fritt språk), kamera, CAN-data (fresdjupne, slitasje), læring av kva forhold som
gir god kvalitet, og produksjonsdata frå Hydrantstyring. Sjå VEGEN-VIDARE kap. 14.
