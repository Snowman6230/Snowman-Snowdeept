# Lokal AI i SNOWMAN (prototype v1.6.74)

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

## Ikkje med enno

Språkmodell-assistent («Spør SNOWMAN»), røyst, kamera, CAN-data (fresdjupne, slitasje), læring av kva forhold som
gir god kvalitet, og produksjonsdata frå Hydrantstyring. Sjå VEGEN-VIDARE kap. 14.
