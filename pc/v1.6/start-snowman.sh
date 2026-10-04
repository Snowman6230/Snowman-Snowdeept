#!/bin/sh
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
# SNOWMAN PC v1.6 – oppstart på Linux.
#
#   ./start-snowman.sh              brukar seriellporten som er lagra i innstillingane
#   ./start-snowman.sh /dev/ttyUSB0 brukar denne seriellporten (Leica via USB-RS232)
#   ./start-snowman.sh sim          test utan mottakar: startar ein simulert Leica
#   ./start-snowman.sh simterreng   simulert Leica over testterreng med kjend snødjupne (test av Terrain Engine)
#   ./start-snowman.sh simanlegg    simulert Leica over terrengmodellane du har lagt inn (t.d. Topocad frå Fjellsætra), med simulert snø
#
# KIOSK=1 ./start-snowman.sh ...    opnar førarskjermen i fullskjerm (for trakkemaskina). Avslutt med Alt+F4.
# HUD=1   ./start-snowman.sh ...    opnar òg HUD-visinga (frontruta) i eit eige vindauge.
# LAN=1   ./start-snowman.sh ...    slår på HUD for mobil/nettbrett i same nett (port 8766, berre HUD). Kan også slåast på med HUD-knappen.
cd "$(dirname "$0")" || exit 1

# Bibliotek: brukar eige python-miljø (.venv) i denne mappa, slik at systemet ikkje blir endra.
PY=python3
if ! $PY -c "import serial, numpy, tifffile" 2>/dev/null; then
  if [ ! -x .venv/bin/python ]; then
    echo "Første oppstart: lagar python-miljø og installerer bibliotek (krev nett) …"
    python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || { echo "Installasjon feila."; exit 1; }
  fi
  PY=.venv/bin/python
fi

# Resten (simulator, teneste, nettlesar, «Avslutt fullskjerm») gjer start_snowman.py – same på Linux og Windows.
FLAGS=""
[ "$KIOSK" = "1" ] && FLAGS="$FLAGS --kiosk"
[ "$HUD" = "1" ] && FLAGS="$FLAGS --hud"
[ "$LAN" = "1" ] && FLAGS="$FLAGS --lan"
exec $PY start_snowman.py "$@" $FLAGS
