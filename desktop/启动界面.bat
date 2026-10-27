@echo off
cd /d "%~dp0"
set "PY=%~dp0..\python\pythonw.exe"
if not exist "%PY%" set "PY=%~dp0..\python\python.exe"
if not exist "%PY%" (
  echo missing portable python
  pause
  exit /b 1
)
start "" "%PY%" "%~dp0server.py"