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
| **`pc/v1.5/`** | **PC-prototype v1.5 – v24-grensesnittet kopla til Leica/GNSS. Gjeldande PC-versjon.** |
| `ntrip-service/v1.1/` | SNOWMAN NTRIP Service v1.1 – Python-bru mellom COM/Leica og CPOS |
| `worker.js` | Cloudflare Worker – terrengproxy mot Kartverket (eldre test) |

## Viktig

- Snødjupna i alle versjonar er **simulert**. Ingen versjon bereknar enno ekte snødjupne frå LiDAR.
- NTRIP/CPOS-brukarnamn og passord skal aldri leggjast inn i dette repoet.
- PC v1.5 viser snødjupne som IKKJE MÅLT under ekte køyring. Fargar/tal finst berre i demo, merka SIMULERT.
- Neste planlagde steg: PC-prototype v1.6 – Terrain Engine (XYZ/CSV → terrenghøgd → snødjupne).
