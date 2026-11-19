@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title SNOWMAN - sjekk IMU
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Viser roleg (eitt sekund om gongen) kva mottakaren sender og hellinga fraa IMU-en. Lukk SNOWMAN og UPrecise foerst.
rem Bruk: SJEKK-IMU.bat  eller  SJEKK-IMU.bat COM3
set "APP="
for /f "delims=" %%d in ('dir /b /ad /on v*') do if exist "%%d\sjekk_imu.py" set "APP=%%d"
if not defined APP (
  echo   Fann ikkje sjekk_imu.py. Oppdater SNOWMAN foerst.
  pause
  exit /b
)
set "PY=%APP%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%APP%\sjekk_imu.py" %*
echo.
pause
