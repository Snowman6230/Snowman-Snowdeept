SNOWMAN NTRIP Service v1.1

TEST PÅ WINDOWS
1. Pakk ut mappa.
2. Køyr INSTALL.bat éin gong. Dette installerer pyserial.
3. Køyr START-SNOWMAN-NTRIP.bat.
4. Nettlesaren opnar http://127.0.0.1:8765
5. Vel COM-porten Leica/RTK-mottakaren brukar (t.d. COM3) og baudrate.
6. Legg inn NTRIP/CPOS caster, port, mountpoint, brukarnamn og passord.
7. Trykk LAGRE / KOPLE TIL.

LEICA
Leica må vere konfigurert til å sende NMEA (særleg GGA) på den valde serieporten,
og same port må kunne ta imot RTCM-korreksjonar dersom mottakaren skal bruke NTRIP
gjennom SNOWMAN.

VIKTIG
Dette er prototype/testprogramvare. Test mot kjent punkt før snødjupnedata blir
brukt operativt. Ikkje legg CPOS-passord i GitHub eller offentlege filer.

API FOR SNOWMAN HTML
GET http://127.0.0.1:8765/api/status
POST http://127.0.0.1:8765/api/config

GitHub Pages er HTTPS, og moderne nettlesarar kan blokkere kall frå HTTPS-side til
lokal HTTP. For første test bruker du statusvindauget lokalt. Neste steg er å
pakke SNOWMAN-PC-grensesnittet lokalt saman med denne tenesta eller gi tenesta
lokal HTTPS/WebSocket.
