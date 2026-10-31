@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title SNOWMAN Base
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Startar SNOWMAN Base i dette vindauget. Forste gong: installerer Python-pakkane i .venv.
rem Fila MAA ha Windows-linjeskift (CRLF) - sjaa .gitattributes.
rem Alt etter :start staar i EI blokk ( ... ). Windows les heile blokka for ho blir koyrd, saa oppdateringa kan byte
rem ut denne fila medan Base koyrer utan at Windows les rot etterpaa. Kode 3 = start paa nytt etter oppdatering.
if exist ".venv\Scripts\python.exe" goto start
echo Installerer SNOWMAN Base første gong ...
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Fann ikkje Python 3.10 eller nyare. Last ned frå https://www.python.org/downloads/windows/
  echo Hak av for «Add python.exe to PATH» under installasjonen, og start denne fila på nytt.
  pause
  exit /b 1
)
%PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo Klarte ikkje å lage Python-miljøet ^(.venv^). Sjekk at Python er 3.10 eller nyare.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
:start
(
  set SNOWMAN_BASE_TENESTE=1
  ".venv\Scripts\python.exe" snowman_base.py %*
  if errorlevel 3 if not errorlevel 4 goto start
  pause
  exit /b
)
