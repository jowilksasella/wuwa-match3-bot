@echo off
rem The game runs elevated, so mouse input must come from an elevated process.
net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
set PY=python
if exist "C:\ProgramData\miniconda3\python.exe" set PY="C:\ProgramData\miniconda3\python.exe"
%PY% bot.py
pause
