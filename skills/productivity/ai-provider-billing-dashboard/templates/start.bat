@echo off
REM ============================================================
REM   AI Provider Billing Dashboard - launcher (template)
REM   1) Kills any old process on the port (PowerShell - reliable)
REM   2) Starts the server
REM   3) Auto-opens the browser
REM   NOTE: ASCII-ONLY on purpose. Cyrillic/non-ASCII in a .bat
REM         breaks cmd.exe ('indstr is not recognized' cascade).
REM ============================================================
cd /d "%~dp0"

set PORT=8765

echo [1/3] Checking port %PORT% for an old process...
REM PowerShell Get-NetTCPConnection is reliable; netstat^|findstr
REM silently failed in some locales and left zombies holding the port.
powershell -NoProfile -Command "$p=(Get-NetTCPConnection -LocalPort %PORT% -State Listen -ErrorAction SilentlyContinue).OwningProcess; if ($p) { Write-Host ('    Killing old process PID ' + $p); Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }"

echo [2/3] Browser will open in 3 seconds...
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:%PORT%"

echo [3/3] Starting server (do NOT close this window)...
echo     Dashboard: http://localhost:%PORT%
echo     Stop: close this window or press Ctrl+C
echo.
python server.py

pause
