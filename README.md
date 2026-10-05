# SNOWMAN by Alpindata

Førar- og snødjupnesystem for trakkemaskiner (RTK-GNSS + LiDAR-terrengmodell).

## Innhald

| Mappe / fil | Kva det er |
|---|---|
| `index.html` | Startside – vidaresender til Driver v24 |
| `v24.html`, `v23.html` | Mobil/HTML-førarversjonar (demo og UI-utvikling) |
| `v1.1.html` | PC-prototype v1.1 – Leica/NMEA og NTRIP-test i nettlesaren |
| `pc/v1.2/` | PC-prototype v1.2 – éin samla oppstart (Windows) |
| `pc/v1.3/` | PC-prototype v1.3 – v24-layout + lokal GNSS/NTRIP-teneste |
| `pc/v1.4/` | PC-prototype v1.4 – offline-kart, LiDAR-filval, maskinkalibrering |
| `pc/v1.5/` | PC-prototype v1.5 – v24-grensesnittet kopla til Leica/GNSS, førarperspektiv, HUD |
| **`pc/v1.6/`** | **PC-prototype v1.6 – Terrain Engine: ekte snødjupne frå terrengmodell. Gjeldande PC-versjon.** |
| `pc/snowman`, `pc/installer-linux.sh` | Linux: kommandoen `snowman` (meny) og installasjon |
| `pc/SNOWMAN.bat`, `pc/INSTALLER-WINDOWS.bat` | Windows: meny og installasjon – sjå `pc/LES-MEG-WINDOWS.txt` |
| `ntrip-service/v1.1/` | SNOWMAN NTRIP Service v1.1 – Python-bru mellom COM/Leica og CPOS |
| `worker.js` | Cloudflare Worker – terrengproxy mot Kartverket (eldre test) |

Sjå [docs/VEGEN-VIDARE.md](docs/VEGEN-VIDARE.md) for moglege framtidige løysingar, [ENDRINGSLOGG.md](ENDRINGSLOGG.md) for alle endringar og avgjerder, og [docs/TERRAIN-ENGINE.md](docs/TERRAIN-ENGINE.md) for spesifikasjonen av Terrain Engine.

## Viktig

- Snødjupna i v1.5 og eldre er **simulert**.
- NTRIP/CPOS-brukarnamn og passord skal aldri leggjast inn i dette repoet.
- PC v1.6 viser ekte snødjupne når terrengmodell, kalibrering og RTK FIX er på plass. Demo er merka SIMULERT.
- Køyrer på Linux og Windows 10/11 (Python 3.10+). Neste: anleggspakke (v1.7).
- PC v1.6.23–24: trasear (yttergrense, prosent preparert, varsel), drivstoff og rapport per prepareringsdøgn (Innst. › Trasear, Drivstoff, Rapport).

## Lisens

Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå [LICENSE](LICENSE).
