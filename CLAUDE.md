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
- SNOWMAN Base: `base/v1.0/` (eiga versjonsmappe, same reglar). **Berre satellittar og NTRIP** (avgjerd 2026-11-22) –
  ikkje legg andre funksjonar inn i Base. Endringar i casteren skal testast med
  `cd base/v1.0 && python -m unittest discover -s test` – testen brukar NTRIP-klienten i `pc/v1.6`.
- **Namn (2026-11-23):** programma heiter **SNOWMAN Snowdeep** (`pc/`, maskinene), **SNOWMAN Base** (`base/`) og
  **SNOWMAN Office** (`kontor/`). Bruk desse namna i alt som blir vist. Ikkje endre mappenamna, API-adressene
  (`/api/kontor…`, `/api/v1/…`), innstillingsnøklane (`kontor_*`) eller `--kontor` – oppdateringa og maskinene er avhengige
  av dei. «kontoret» og «snødjupne» som vanlege ord er framleis nynorsk. `TENESTE-SNOWMAN-KONTOR.bat` skal ikkje endrast
  (oppgåva i Windows peikar på ho, og ho køyrer medan oppdateringa skriv filer).
- SNOWMAN Office: `kontor/v1.0/` (eiga versjonsmappe, same reglar). Kontorsida, anleggspakke, forslag, maskinoversikt,
  deling og AI. Køyrer på ein Windows-PC på anlegget (port 8790, berre lokalt nett; port 8791 berre maskin-API for
  sanntid ute). Kart og anlegg er SNOWMAN Snowdeep i Office-modus (`snowman_pc.py --kontor`, port 8766 – 8765 er Snowdeep i maskinene), starta av
  Office frå `pc/` i same zip – nye funksjonar i kartet blir laga i `pc/`, ikkje i Office. Test:
  `cd kontor/v1.0 && python -m unittest discover -s test` og `cd pc/v1.6 && python3 test/testkontorkopling.py`.
  Brot i API-et gir ny API-versjon; oppdater `SNOWMAN_MIN` i `kontor/v1.0/konfig.py` når SNOWMAN Snowdeep må oppdaterast.
  Ny versjon av SNOWMAN Snowdeep treng INGEN ny Office-versjon: Office følgjer VERSION i `pc/<nyaste>/snowman_pc.py`
  og varslar og oppdaterer kartet sjølv. Endrar du anleggspakka, maskin-API-et eller terrengformatet, auk både
  `SNOWMAN_MIN` og Office-versjonen (`kontor/v1.0/konfig.py`).
- SNOWMAN Snowdeep skal fungere fullt ut utan SNOWMAN Base og SNOWMAN Office. Begge er valfrie tilknytingar
  (Base: korreksjonar; Office: anleggsdata og deling). Det som kjem frå Office, blir lagra lokalt i maskina.
  Sjå VEGEN-VIDARE kap. 19.
