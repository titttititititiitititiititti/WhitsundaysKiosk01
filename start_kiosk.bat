@echo off
title Filtour Kiosk (Auto-Updating)
color 0A
cd /d C:\filtour

echo ===============================================================================
echo                    FILTOUR KIOSK - AUTO-UPDATING MODE
echo ===============================================================================
echo.
echo The kiosk will automatically check for updates and restart when needed.
echo.
echo Press Ctrl+C to stop the kiosk.
echo.
echo ===============================================================================
echo.

:: Check if Python auto-updater exists
if exist "scripts\auto_updater.py" (
    echo Using Python auto-updater (checks every 5 minutes)
    echo.
    python scripts\auto_updater.py
) else (
    echo Using simple restart loop
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

