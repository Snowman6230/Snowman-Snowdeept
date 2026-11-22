@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title SNOWMAN Kontor
rem SNOWMAN by Alpindata - Copyright 2026 Hans Petter Brunstad Sorensen (Alpindata). Alle rettar reserverte. Sjaa LICENSE.
rem Startar SNOWMAN Kontor i dette vindauget. Forste gong: lagar Python-miljoet i .venv.
rem Fila MAA ha Windows-linjeskift (CRLF) - sjaa .gitattributes.
rem Alt etter :start staar i EI blokk ( ... ), saa oppdateringa kan byte ut denne fila medan Kontor koyrer.
rem Kode 3 = start paa nytt etter oppdatering.
if exist ".venv\Scripts\python.exe" goto start
echo Installerer SNOWMAN Kontor første gong ...
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
:start
(
  set SNOWMAN_KONTOR_TENESTE=1
  ".venv\Scripts\python.exe" snowman_kontor.py %*
  if errorlevel 3 if not errorlevel 4 goto start
  pause
  exit /b
)
