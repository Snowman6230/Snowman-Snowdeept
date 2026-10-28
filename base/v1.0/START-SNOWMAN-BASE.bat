@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title SNOWMAN Base
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Startar SNOWMAN Base. Første gong: installerer Python-pakkane i .venv. Startar på nytt etter oppdatering (kode 3).
if not exist ".venv\Scripts\python.exe" (
  echo Installerer SNOWMAN Base første gong ...
  py -3 -m venv .venv || python -m venv .venv || (echo Fann ikkje Python 3.10+. Installer frå python.org. & pause & exit /b)
  ".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
)
set SNOWMAN_BASE_TENESTE=1
:start
".venv\Scripts\python.exe" snowman_base.py %*
if %errorlevel%==3 goto start
pause
