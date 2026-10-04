@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title SNOWMAN by Alpindata
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Meny: start, demo, test, fullskjerm, oppdater, stopp. Eller direkte: SNOWMAN.bat demo / test / start / stopp / COM3

set "APP="
for /f "delims=" %%d in ('dir /b /ad /on v*') do if exist "%%d\start_snowman.py" set "APP=%%d"
if not defined APP goto ingenapp
if not exist "%APP%\.venv\Scripts\python.exe" goto ikkjeinstallert

if "%~1"=="" (
  "%APP%\.venv\Scripts\python.exe" "%APP%\start_snowman.py" meny
) else (
  "%APP%\.venv\Scripts\python.exe" "%APP%\start_snowman.py" %*
)
echo.
pause
exit /b

:ikkjeinstallert
echo.
echo   SNOWMAN er ikkje installert enno. Køyr INSTALLER-WINDOWS.bat først.
echo.
pause
exit /b

:ingenapp
echo   Fann ikkje SNOWMAN-filene (mappa v1.6) ved sida av denne fila.
pause
exit /b
