# SNOWMAN – logo og ikon

Kjelda til alt er `pc/v1.6/ikon/lag-ikon.py`. Endre der, køyr `python3 lag-ikon.py` (krev Playwright/Chromium og
Pillow, berre ved utvikling), så blir alle filene laga på nytt og er like. Ny PC-versjon (`pc/v1.7/`) tek med
`ikon/`-mappa.

| Fil | Bruk |
|---|---|
| `ikon/snowman.svg` | Hovudikonet (512 × 512) – kjeldefil |
| `ikon/snowman-enkel.svg` | Forenkla ikon for små storleikar (16–32 px) |
| `ikon/snowman-logo.svg` | Logo med tekst: fjelltoppar, SNOWMAN, by Alpindata (dokument, nettside, rapportar) |
| `ikon/snowman.ico` | Skrivebordssnarvegen på Windows (16–256 px; dei små er den forenkla utgåva) |
| `ikon/snowman-256.png`, `snowman-512.png` | Snarveg på Linux, sal/presentasjon |
| `vendor/snowman-icon.png` | Ikonet i nettlesarfana (64 px) |

**Innhald:** kvite fjelltoppar med snøline (same form som logoen i førarskjermen) som går ned i ei snøflate,
og tråkkemaskina sett ovanfrå (same teikning som på kartet) med preparert spor bak.

**Fargar**

| | |
|---|---|
| Natthimmel | `#0b2a44` → `#15507c` |
| Snø | `#ffffff` → `#dcecf7`, spor `#cfe3f2` |
| Maskin | raud `#d42c2c`, skjer `#8d9ba5`, belte `#1a252d`, finisher `#f2c230`, GPS `#19e07a` |
| Logo-tekst | `#ffffff`, «by Alpindata» `#8cc8f0` |
| Skrift | Arial/Helvetica, feit (900) for SNOWMAN, 700 for «by Alpindata» |

Logoen i toppfeltet på førarskjermen er teikna direkte i `driver.html` med same fjell-form (`PEAKS` i lag-ikon.py).
