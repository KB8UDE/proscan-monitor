@echo off
setlocal
set "APP=%~dp0p25_radio_dashboard_v2.py"

rem Uses PY if already set, otherwise the Windows py launcher, otherwise python on PATH.
if not defined PY (
where py >nul 2>nul && set "PY=py -3" || set "PY=python"
)

%PY% "%APP%" --port COM1 --baud 19200 --interval 2
pause
