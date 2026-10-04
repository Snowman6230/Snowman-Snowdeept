@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title SNOWMAN - installasjon
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Installerer SNOWMAN paa Windows 10/11: Python-miljo, bibliotek og snarveg paa skrivebordet. Koyr ein gong.

echo.
echo   SNOWMAN by Alpindata – installasjon for Windows
echo   ================================================
echo.

rem --- 1. Python 3.10 eller nyare ---
set "PYEXE="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYEXE=py -3"
if defined PYEXE goto harpython
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PYEXE=python"
if defined PYEXE goto harpython

echo   Python manglar. SNOWMAN treng Python 3.10 eller nyare.
echo.
where winget >nul 2>&1 || goto manuellpython
choice /c JN /m "  Vil du installere Python no"
if errorlevel 2 goto manuellpython
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
echo.
echo   Python er installert. Lukk dette vindauget og køyr INSTALLER-WINDOWS.bat på nytt.
pause
exit /b

:manuellpython
echo   Last ned Python frå https://www.python.org/downloads/windows/
echo   Hak av for «Add python.exe to PATH» under installasjonen.
echo   Køyr så INSTALLER-WINDOWS.bat på nytt.
pause
exit /b

:harpython
for /f "delims=" %%v in ('%PYEXE% --version') do echo   %%v funnen.

rem --- 2. Nyaste versjonsmappe (v1.6, v1.7 ...) ---
set "APP="
for /f "delims=" %%d in ('dir /b /ad /on v*') do if exist "%%d\start_snowman.py" set "APP=%%d"
if not defined APP goto ingenapp
echo   SNOWMAN-mappe: %CD%\%APP%

rem --- 3. Eige Python-miljo med bibliotek (endrar ikkje resten av PC-en) ---
echo.
echo   Lagar Python-miljø og installerer bibliotek. Dette krev nett og tek nokre minutt ...
if not exist "%APP%\.venv\Scripts\python.exe" %PYEXE% -m venv "%APP%\.venv" || goto feil
"%APP%\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%APP%\.venv\Scripts\python.exe" -m pip install -r "%APP%\requirements.txt" --quiet --disable-pip-version-check || goto feil
"%APP%\.venv\Scripts\python.exe" -c "import serial, numpy, tifffile; print('  Bibliotek installert.')" || goto feil

rem --- 4. Snarveg paa skrivebordet ---
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'SNOWMAN.lnk')); $s.TargetPath='%~dp0SNOWMAN.bat'; $s.WorkingDirectory='%~dp0'; $s.Description='SNOWMAN by Alpindata'; $s.Save()" && echo   Snarveg «SNOWMAN» lagd på skrivebordet.

echo.
echo   Ferdig! Start SNOWMAN med snarvegen på skrivebordet, eller SNOWMAN.bat i denne mappa.
echo   Første gong kan Windows spørje om Python får bruke nettverket: vel «Privat nettverk» og Tillat
echo   (trengst berre for HUD på mobil).
echo.
pause
exit /b

:ingenapp
echo   Fann ikkje SNOWMAN-filene (mappa v1.6 med start_snowman.py) ved sida av denne fila.
pause
exit /b

:feil
echo.
echo   Installasjonen feila. Sjekk at PC-en er på nett, og prøv igjen.
echo   Ta bilete av meldinga over og send til Alpindata om det ikkje går.
pause
exit /b 1
