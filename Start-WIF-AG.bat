@echo off
setlocal
cd /d "%~dp0"

echo Starting WIF AG Tool...
echo.

set PYTHONPATH=src

REM Open the browser shortly after the server boots
start "" /B cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000/"

py -m wif_ag_tool serve

echo.
echo Server stopped. Press any key to close this window.
pause >nul
