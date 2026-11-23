@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title SNOWMAN Office - installasjon
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Installerer SNOWMAN Office slik at han startar sjolv paa denne PC-en:
rem   1. Python-miljoet (.venv)
rem   2. oppgaave «SNOWMAN Office» som startar ved oppstart av Windows (ogsaa utan innlogging)
rem   3. brannmur: port 8790 (kontorsida og maskinene) berre fraa privat nett - aldri ope mot internett
rem   4. snarveg paa skrivebordet med eige ikon   5. lokal AI (Ollama), valfri
rem Avinstallere: INSTALLER-WINDOWS.bat fjern
rem Fila MAA ha Windows-linjeskift (CRLF).
net session >nul 2>&1
if errorlevel 1 (
  echo Installasjonen treng administratorløyve. Godta spørsmålet frå Windows.
  if "%~1"=="" (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs") else (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%~1' -Verb RunAs")
  exit /b
)
if /i "%~1"=="fjern" goto fjern
echo.
echo   SNOWMAN Office - installasjon på denne PC-en
echo   Mappe: %~dp0
echo.
echo %~dp0 | find /i "OneDrive" >nul && (
  echo   ÅTVARING: mappa ligg i OneDrive. Flytt SNOWMAN Office til t.d. C:\SNOWMAN-Office først.
  echo   OneDrive kan låse databasen medan Office skriv.
  pause
  exit /b 1
)
rem --- 1. Python ---
if not exist ".venv\Scripts\python.exe" (
  set "PY="
  where py >nul 2>nul && set "PY=py -3"
  if not defined PY (where python >nul 2>nul && set "PY=python")
)
if not exist ".venv\Scripts\python.exe" (
  if not defined PY (
    echo   Fann ikkje Python 3.10 eller nyare. Last ned frå https://www.python.org/downloads/windows/
    echo   Vel «Install for all users» og hak av for «Add python.exe to PATH».
    pause
    exit /b 1
  )
)
if not exist ".venv\Scripts\python.exe" call %PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo   Klarte ikkje å lage Python-miljøet ^(.venv^).
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
echo   [1/5] Python-miljøet er klart.
rem --- 2. Oppgaave ved oppstart ---
rem Gamle namn (SNOWMAN Kontor, før 1.2.0) blir fjerna – oppgåva og brannmuren heiter no SNOWMAN Office
schtasks /end /tn "SNOWMAN Kontor" >nul 2>&1
schtasks /delete /tn "SNOWMAN Kontor" /f >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Kontor" >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Kontor maskinport" >nul 2>&1
schtasks /end /tn "SNOWMAN Office" >nul 2>&1
schtasks /create /tn "SNOWMAN Office" /tr "\"%~dp0TENESTE-SNOWMAN-KONTOR.bat\"" /sc onstart /ru SYSTEM /rl HIGHEST /f >nul
if errorlevel 1 (
  echo   Klarte ikkje å lage oppgåva «SNOWMAN Office».
  pause
  exit /b 1
)
echo   [2/5] Oppgåva «SNOWMAN Office» startar Office ved kvar oppstart av Windows.
rem --- 3. Brannmur ---
netsh advfirewall firewall delete rule name="SNOWMAN Office" >nul 2>&1
netsh advfirewall firewall add rule name="SNOWMAN Office" dir=in action=allow protocol=TCP localport=8790 profile=private,domain >nul
netsh advfirewall firewall delete rule name="SNOWMAN Office maskinport" >nul 2>&1
netsh advfirewall firewall add rule name="SNOWMAN Office maskinport" dir=in action=allow protocol=TCP localport=8791 profile=any >nul
echo   [3/5] Brannmur: port 8790 open berre frå privat nett (wifi og nettverk på anlegget).
echo         Port 8791 (berre maskin-API, berre rolla maskin) er open for sanntid ute i bakken.
rem --- 4. Snarveg paa skrivebordet (eige ikon) ---
".venv\Scripts\python.exe" snowman_kontor.py snarveg
echo   [4/5] Snarvegen «SNOWMAN Office» på skrivebordet opnar kart og anlegg (og startar Office om han står).
rem --- 5. Lokal AI (valfri) ---
echo.
echo   [5/5] Lokal AI (valfri): Ollama køyrer ein språkmodell på denne PC-en. SNOWMAN Office og maskinene
echo         (SNOWMAN Snowdeep) kan då spørje AI utan at noko forlèt anlegget. Treng ca. 4 GB plass og 8 GB minne.
choice /c JN /n /m "         Installere Ollama no? [J/N] "
if errorlevel 2 goto utanai
where winget >nul 2>nul || (
  echo         Fann ikkje winget. Last ned Ollama frå https://ollama.com/download og installer han.
  goto utanai
)
winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
echo         Ollama er installert. Hent modellen i SNOWMAN Office: Office › AI › Lokal AI › HENT MODELL.
:utanai
schtasks /run /tn "SNOWMAN Office" >nul
echo.
echo   SNOWMAN Office køyrer no i bakgrunnen og startar sjølv etter omstart.
echo   Kontorsida: http://localhost:8790/   (første gong: lag administrator og ein brukar for maskinene)
echo   Kart og anlegg: snarvegen «SNOWMAN Office» på skrivebordet, eller http://localhost:8765/
echo   Maskinene:  IP-adressa til denne PC-en, port 8790 (gi PC-en fast IP-adresse i ruteren)
echo   Logg:       %~dp0data\teneste.log
echo   Bruk IKKJE START-SNOWMAN-OFFICE.bat i tillegg - då køyrer to Office. Kommandoar går fint:
echo               START-SNOWMAN-OFFICE.bat brukar passord NAMN
echo   Nettverket på PC-en må vere sett til «Privat» i Windows, elles når ikkje maskinene Office.
echo   Opne ALDRI port 8790 i ruteren mot internett.
echo   Sanntid ute i bakken (mobilnett): send BERRE port 8791 vidare i ruteren til denne PC-en.
echo.
pause
exit /b 0
:fjern
schtasks /end /tn "SNOWMAN Kontor" >nul 2>&1
schtasks /delete /tn "SNOWMAN Kontor" /f >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Kontor" >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Kontor maskinport" >nul 2>&1
schtasks /end /tn "SNOWMAN Office" >nul 2>&1
schtasks /delete /tn "SNOWMAN Office" /f >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Office" >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Office maskinport" >nul 2>&1
echo   Oppgåva og brannmurregelen er fjerna. Mappa og data er ikkje sletta.
pause
exit /b 0
