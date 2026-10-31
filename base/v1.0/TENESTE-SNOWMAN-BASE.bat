@echo off
setlocal EnableExtensions
cd /d "%~dp0"
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Koyrer SNOWMAN Base utan vindauge, som oppgaave ved oppstart av Windows (laga av INSTALLER-WINDOWS.bat).
rem Startar paa nytt: med ein gong etter oppdatering (kode 3), etter 30 s ved feil. Stopp: Oppgaaveplanleggaren
rem eller «schtasks /end /tn "SNOWMAN Base"». Utskrift: data\teneste.log.
rem Fila MAA ha Windows-linjeskift (CRLF). Alt etter :start staar i EI blokk (sjaa START-SNOWMAN-BASE.bat).
if not exist "data" mkdir "data"
if not exist ".venv\Scripts\python.exe" (
  echo %date% %time% Fann ikkje .venv - koyr INSTALLER-WINDOWS.bat >> "data\teneste.log"
  exit /b 1
)
:start
(
  set SNOWMAN_BASE_TENESTE=1
  echo %date% %time% SNOWMAN Base startar >> "data\teneste.log"
  ".venv\Scripts\python.exe" snowman_base.py >> "data\teneste.log" 2>&1
  if errorlevel 3 if not errorlevel 4 goto start
  if errorlevel 1 (
    echo %date% %time% SNOWMAN Base stoppa med feil - ny start om 30 s >> "data\teneste.log"
    ping -n 31 127.0.0.1 >nul
    goto start
  )
  exit /b 0
)
