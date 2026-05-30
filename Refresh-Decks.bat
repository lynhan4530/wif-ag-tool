@echo off
setlocal
cd /d "%~dp0"

set PYTHONPATH=src

echo Re-parsing vanilla StrategicDecks.ndf...
py -m wif_ag_tool refresh

echo.
pause
