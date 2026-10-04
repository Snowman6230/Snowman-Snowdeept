#!/bin/sh
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
# SNOWMAN PC v1.6 – oppstart på Linux.
#
#   ./start-snowman.sh              brukar seriellporten som er lagra i innstillingane
#   ./start-snowman.sh /dev/ttyUSB0 brukar denne seriellporten (Leica via USB-RS232)
#   ./start-snowman.sh sim          test utan mottakar: startar ein simulert Leica
#   ./start-snowman.sh simterreng   simulert Leica over testterreng med kjend snødjupne (test av Terrain Engine)
#
# KIOSK=1 ./start-snowman.sh ...    opnar førarskjermen i fullskjerm (for trakkemaskina). Avslutt med Alt+F4.
# HUD=1   ./start-snowman.sh ...    opnar òg HUD-visinga (frontruta) i eit eige vindauge.
# LAN=1   ./start-snowman.sh ...    HUD kan opnast frå mobil/nettbrett i same nett (adressa blir skriven ut).
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

PORT="$1"
if [ "$1" = "sim" ] || [ "$1" = "simterreng" ]; then
  rm -f /tmp/snowman-sim-port
  if [ "$1" = "simterreng" ]; then
    [ -f testterreng.tif ] || $PY testterreng.py testterreng.tif
    echo "Testterreng: last opp testterreng.tif under Innst. › Terreng, og lagre kalibrering (antenne 2,8 m) under Innst. › Kalibrering."
    $PY simuler-leica.py /tmp/snowman-sim-port --terreng &
  else
    $PY simuler-leica.py /tmp/snowman-sim-port &
  fi
  SIM=$!
  i=0; while [ ! -s /tmp/snowman-sim-port ] && [ $i -lt 20 ]; do sleep 0.2; i=$((i+1)); done
  PORT=$(cat /tmp/snowman-sim-port)
fi

EXTRA=""; [ "$LAN" = "1" ] && EXTRA="--lan"
if [ -n "$PORT" ]; then $PY snowman_pc.py $EXTRA --serial "$PORT" & else $PY snowman_pc.py $EXTRA & fi
SRV=$!
trap 'kill $SRV ${SIM:-} 2>/dev/null' EXIT INT TERM
sleep 2

URL=http://127.0.0.1:8765
B=$(command -v chromium || command -v chromium-browser || command -v google-chrome || command -v google-chrome-stable)
if [ "$HUD" = "1" ]; then
  if [ -n "$B" ]; then "$B" --new-window "$URL/hud" & else xdg-open "$URL/hud" 2>/dev/null & fi
fi
if [ -n "$B" ] && [ "$KIOSK" = "1" ]; then
  "$B" --kiosk --noerrdialogs --disable-infobars "$URL"
elif [ -n "$B" ]; then
  "$B" --new-window "$URL"
else
  xdg-open "$URL" 2>/dev/null || echo "Opne $URL i nettlesaren."
fi
echo "SNOWMAN køyrer på $URL – trykk Ctrl+C her for å stoppe."
wait $SRV
