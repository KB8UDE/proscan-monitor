@echo off
set "PY=python"
set "APP=%~dp0p25_radio_dashboard_v2.py"

if not exist "%PY%" (
  echo Bundled Codex Python was not found:
  echo %PY%
  pause
  exit /b 1
)

"%PY%" "%APP%" --mock
pause
