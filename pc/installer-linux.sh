#!/bin/sh
# SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
# Installerer kommandoen «snowman» og ein snarveg i programmenyen (Linux). Køyr éin gong:
#
#   sh ~/snowman/pc/installer-linux.sh
#
# Endrar ikkje systemet: alt blir lagt i heimemappa di (~/.local/bin og ~/.local/share/applications).
# Kommandoen peikar på mappa SNOWMAN ligg i, så «snowman oppdater» (git pull) held han oppdatert.

PCDIR=$(dirname "$(readlink -f "$0")")
BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"

chmod +x "$PCDIR/snowman" "$PCDIR"/v*/start-snowman.sh 2>/dev/null
mkdir -p "$BIN" "$APPS"
ln -sf "$PCDIR/snowman" "$BIN/snowman"
echo "✔ Kommandoen «snowman» er installert ($BIN/snowman)."

# Snarveg i programmenyen (Omarchy: Super + Space, skriv «snowman»)
cat > "$APPS/snowman.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SNOWMAN
GenericName=Snødjupne for trakkemaskin
Comment=SNOWMAN by Alpindata – meny for start, demo og test
Exec=$BIN/snowman
Icon=$(ls -d "$PCDIR"/v*/ikon/snowman-256.png 2>/dev/null | sort -V | tail -n 1)
Terminal=true
Categories=Utility;
Keywords=snowman;snødjupne;trakkemaskin;alpindata;
EOF
echo "✔ Snarveg i programmenyen: søk etter «SNOWMAN»."

# ~/.local/bin må vere i PATH for at terminalen skal finne kommandoen
case ":$PATH:" in
  *":$BIN:"*) ;;
  *)
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
      if [ -f "$rc" ] && ! grep -q 'SNOWMAN: ~/.local/bin' "$rc"; then
        printf '\n# SNOWMAN: ~/.local/bin i PATH\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
        echo "✔ La til ~/.local/bin i $rc."
      fi
    done
    echo "  Lukk terminalen og opne han igjen (eller skriv: source ~/.bashrc)."
    ;;
esac

# Kontor-PC eller Maskin-PC (kiosk + autostart)
APP=$(ls -d "$PCDIR"/v*/ 2>/dev/null | sort -V | while read d; do [ -f "$d/start_snowman.py" ] && echo "$d"; done | tail -n 1)
echo ""
echo "Kva type PC er dette?"
echo "  K = Kontor-PC: du startar SNOWMAN sjølv (snowman i terminalen)"
echo "  M = Maskin-PC: SNOWMAN startar av seg sjølv i kioskmodus når PC-en startar"
printf "Vel K eller M og trykk Enter: "
read TYPE
case "$TYPE" in
  [Mm]*) sh "${APP}start-snowman.sh" installer maskin ;;
  *)     sh "${APP}start-snowman.sh" installer kontor ;;
esac
echo "Valet kan endrast seinare under Innst. › System i SNOWMAN."

echo ""
echo "Ferdig! Skriv  snowman  i terminalen for å starte."
