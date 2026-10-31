#!/usr/bin/env bash
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
# Installerer SNOWMAN Base som systemteneste på Linux (Debian/Ubuntu/Raspberry Pi OS).
#   bash installasjon/installer-linux.sh        (køyr frå base/v1.0, med sudo-rett)
# Etterpå: «snowman-base» for kommandoar, «sudo systemctl status snowman-base» for status.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
DATA="${SNOWMAN_BASE_DATA:-$DIR/data}"
echo "SNOWMAN Base blir installert frå $DIR (data i $DATA) for brukaren $USER_NAME"
command -v python3 >/dev/null || { echo "Manglar python3: sudo apt install python3 python3-venv"; exit 1; }
python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --disable-pip-version-check -r "$DIR/requirements.txt"
mkdir -p "$DATA"
# tilgang til USB-mottakaren
sudo usermod -aG dialout "$USER_NAME" || true
sed -e "s#__MAPPE__#$DIR#g" -e "s#__DATA__#$DATA#g" -e "s#__BRUKAR__#$USER_NAME#g" \
  "$DIR/installasjon/snowman-base.service" | sudo tee /etc/systemd/system/snowman-base.service >/dev/null
cat <<CMD | sudo tee /usr/local/bin/snowman-base >/dev/null
#!/usr/bin/env bash
export SNOWMAN_BASE_DATA="$DATA"
exec "$DIR/.venv/bin/python" "$DIR/snowman_base.py" "\$@"
CMD
sudo chmod +x /usr/local/bin/snowman-base
sudo systemctl daemon-reload
sudo systemctl enable --now snowman-base
sleep 3
echo
echo "SNOWMAN Base køyrer. Statusside: http://$(hostname -I | awk '{print $1}'):8780/"
echo "Første gong: opne http://$(hostname -I | awk '{print $1}'):8780/kontor/ frå ein PC på same nett og lag administrator."
echo "Mountpoint og brukarar: kontorsida, eller «snowman-base brukar legg-til NAMN --rolle kontor»."
