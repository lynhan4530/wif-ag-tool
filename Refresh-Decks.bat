@echo off
setlocal
cd /d "%~dp0"

echo Re-parsing vanilla StrategicDecks.ndf...
py -m wif_ag_tool refresh

echo.
pause
