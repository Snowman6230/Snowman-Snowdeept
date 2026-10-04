# Arbeidsreglar for SNOWMAN by Alpindata

- Skriv på nynorsk – i grensesnitt, kommentarar, commit-meldingar og dokumentasjon.
- **Oppdater ENDRINGSLOGG.md ved kvar endring** (nyaste øvst, med dato, kva og kvifor). Ta med avgjerder.
- Gjeldande PC-versjon: `pc/v1.6/`. Ny versjon = ny mappe (`pc/v1.7/`), eldre versjonar blir ikkje endra.
- Behald førargrensesnittet frå Driver v24. Ikkje lag nytt grensesnitt utan at eigaren ber om det.
- Simulert snødjupne skal aldri sjå ut som ekte måling. Demo skal vere tydeleg merka.
- Systemet skal fungere offline og vere leverandøruavhengig (Leica støtta, ikkje kravd).
- Aldri legg CPOS/NTRIP-innloggingar eller andre hemmelegheiter i repoet.
- Proprietær kode – sjå LICENSE. Ikkje legg til tredjepartskode utan å sjekke lisensen.
- Test med simulert GNSS før push: `simuler-leica.py` (og `--terreng` + `testterreng.py` for snødjupne mot fasit).
- Spesifikasjon for terreng: `docs/TERRAIN-ENGINE.md`.
