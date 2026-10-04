#!/bin/sh
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
# SNOWMAN PC v1.5 – oppstart på Linux (t.d. Surface Pro med Xubuntu/Mint/Debian XFCE).
# Startar den lokale tenesta og opnar førarskjermen i Chromium kioskmodus.
# Bruk: ./start-snowman.sh [seriellport]   t.d. ./start-snowman.sh /dev/ttyUSB0
cd "$(dirname "$0")"
if [ -n "$1" ]; then python3 snowman_pc.py --serial "$1" & else python3 snowman_pc.py & fi
sleep 2
BROWSER=$(command -v chromium || command -v chromium-browser || command -v google-chrome)
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars --check-for-update-interval=31536000 http://127.0.0.1:8765
