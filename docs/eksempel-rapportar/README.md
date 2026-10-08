# Eksempel på rapportar frå SNOWMAN

Alle filene her er **eksempel med oppdikta eller simulerte data** – ikkje ekte målingar. Dei viser kva SNOWMAN kan
levere. Rapportane 1–3 er laga med `pc/v1.6/lag-eksempel.py` (køyr han på nytt etter endringar i rapportane).

| Fil | Kva | Kvar i SNOWMAN |
|---|---|---|
| `1-dagsrapport-med-trasear.pdf` | Dagsrapport for eitt prepareringsdøgn (kl. 12–12): samandrag, trasear (areal, % preparert, tid i traseen, sist preparert, snødjupne, måldjupne), **kart per trasé i snødjupnefargar** med fargeskala, økter og drivstoff (l/time, l/daa) | Innst. › Rapport › ⬇ RAPPORT SOM PDF |
| `2-dagsrapport-utan-trasear.pdf` | Same rapport når ingen trasear er lagde inn: **kart over heile området som er køyrt**, delt i område om det er køyrt fleire stader | Innst. › Rapport › ⬇ RAPPORT SOM PDF |
| `3-dagsrapport.csv` | Same tal som tabellar (semikolon og desimalkomma – opnar rett i norsk Excel): samla, trasear, økter, drivstoff | Innst. › Rapport › ⬇ CSV / EXCEL |
| `4-feltlogg-simulert.zip` | Feltlogg for feilsøking (frå simulatoren, merkt simulert): `.nmea` (alt mottakaren sende + hendingar og feil med `#`), `.csv` (posisjon, fix, høgd, terreng, snødjupne, helling, korreksjonsalder, NTRIP – éi linje per posisjon), `.json` (samandrag: tid, linjer, feil, % RTK FIX) | Innst. › System › Feltlogg › ⬇ (éin logg) eller ⬇ dag (alle loggane frå dagen) |

**Automatisk lagring:** SNOWMAN lagrar PDF og CSV for dei to siste prepareringsdøgna i ei mappe (t.d. OneDrive) kvart
5. minutt og når prep blir stoppa (Innst. › Rapport › Automatisk lagring).

**Merk:** økter frå demo og testmodus (simulert mottakar) er alltid merkte TEST i oransje og er ikkje med i summane.
Simulert snø er aldri vist som ekte måling.
