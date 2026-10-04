@echo off
title SNOWMAN PC Prototype v1.4
cd /d "%~dp0"
start "" http://127.0.0.1:8765
py snowman_pc.py
pause
