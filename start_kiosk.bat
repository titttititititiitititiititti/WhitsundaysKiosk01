@echo off
title Filtour Kiosk (Auto-Updating)
color 0A
cd /d C:\filtour

echo ===============================================================================
echo                    FILTOUR KIOSK - AUTO-UPDATING MODE
echo ===============================================================================
echo.
echo The kiosk will automatically check for updates every 60 seconds.
echo When changes are pushed from the main computer, this kiosk will restart.
echo.
echo Press Ctrl+C to stop the kiosk.
echo.
echo ===============================================================================
echo.

:: Check if Python auto-updater exists
if exist "scripts\auto_update.py" (
    echo Starting auto-update daemon...
    echo.
    python scripts\auto_update.py --daemon
) else (
    echo Auto-updater not found - using simple mode
    echo.
    goto simple_loop
)

goto end

:simple_loop
:: Simple loop that checks for updates on each restart
echo Checking for updates...
git fetch origin main >nul 2>&1
git diff --quiet HEAD origin/main 2>nul
if errorlevel 1 (
    echo Updates found! Pulling changes...
    git pull origin main
    echo.
)

echo Starting kiosk...
python app.py

echo.
echo Kiosk stopped. Restarting in 5 seconds...
echo (Press Ctrl+C now to exit)
timeout /t 5 >nul
goto simple_loop

:end
echo.
echo Kiosk shutdown complete.
pause
