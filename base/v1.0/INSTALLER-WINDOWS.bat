@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title SNOWMAN Base - installasjon
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Installerer SNOWMAN Base slik at han koyrer heile tida paa denne PC-en:
rem   1. Python-miljoet (.venv)
rem   2. oppgaave «SNOWMAN Base» som startar ved oppstart av Windows (ogsaa utan innlogging)
rem   3. brannmur: port 2101 (NTRIP) inn, port 8780 (kontor) berre fraa privat nett
rem   4. straum: aldri dvale naar PC-en staar i straumen, og USB-straumsparing av (mottakaren blir ikkje kopla fraa)
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
echo   SNOWMAN Base - installasjon på denne PC-en
echo   Mappe: %~dp0
echo.
echo %~dp0 | find /i "OneDrive" >nul && (
  echo   ÅTVARING: mappa ligg i OneDrive. Flytt SNOWMAN Base til t.d. C:\SNOWMAN-Base først.
  echo   OneDrive kan låse filer medan Base skriv, og lastar opp rådata heile tida.
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
echo   [1/4] Python-miljøet er klart.
rem --- 2. Oppgaave ved oppstart ---
schtasks /end /tn "SNOWMAN Base" >nul 2>&1
schtasks /create /tn "SNOWMAN Base" /tr "\"%~dp0TENESTE-SNOWMAN-BASE.bat\"" /sc onstart /ru SYSTEM /rl HIGHEST /f >nul
if errorlevel 1 (
  echo   Klarte ikkje å lage oppgåva «SNOWMAN Base».
  pause
  exit /b 1
)
echo   [2/4] Oppgåva «SNOWMAN Base» startar Base ved kvar oppstart av Windows.
rem --- 3. Brannmur ---
netsh advfirewall firewall delete rule name="SNOWMAN Base NTRIP" >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Base kontor" >nul 2>&1
netsh advfirewall firewall add rule name="SNOWMAN Base NTRIP" dir=in action=allow protocol=TCP localport=2101 profile=any >nul
netsh advfirewall firewall add rule name="SNOWMAN Base kontor" dir=in action=allow protocol=TCP localport=8780 profile=private,domain >nul
echo   [3/4] Brannmur: port 2101 open, port 8780 berre frå privat nett.
rem --- 4. Straum ---
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setactive SCHEME_CURRENT
echo   [4/4] Straum: aldri dvale i straumen, USB-straumsparing av.
schtasks /run /tn "SNOWMAN Base" >nul
echo.
echo   SNOWMAN Base køyrer no i bakgrunnen og startar sjølv etter omstart og straumbrot.
echo   Kontor: http://localhost:8780/kontor/   (første gong: lag administrator)
echo   Logg:   %~dp0data\teneste.log
echo   Bruk IKKJE START-SNOWMAN-BASE.bat i tillegg - då køyrer to Base. Kommandoar (t.d. «brukar passord NAMN»)
echo   går fint:  START-SNOWMAN-BASE.bat brukar passord NAMN
echo   Hugs: Nettverkskortet bør ha fast IP-adresse (reservert i ruteren), og ruteren må sende port 2101 hit.
echo.
pause
exit /b 0
:fjern
schtasks /end /tn "SNOWMAN Base" >nul 2>&1
schtasks /delete /tn "SNOWMAN Base" /f >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Base NTRIP" >nul 2>&1
netsh advfirewall firewall delete rule name="SNOWMAN Base kontor" >nul 2>&1
echo   Oppgåva og brannmurreglane er fjerna. Mappa og data er ikkje sletta. Straum-innstillingane er uendra.
pause
exit /b 0
