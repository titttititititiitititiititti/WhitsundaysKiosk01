@echo off
REM ============================================
REM Filtour Kiosk Startup Script (Windows)
REM ============================================
REM This script starts the kiosk in auto-update mode.
REM Add this to Windows Task Scheduler to run at startup.

title Filtour Kiosk

REM Set the path to your project folder
cd /d "%~dp0.."

echo ============================================
echo Starting Filtour Kiosk...
echo ============================================
echo.

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found! Please install Python 3.9+
    pause
    exit /b 1
)

REM Install/update dependencies
echo Installing dependencies...
python -m pip install -r requirements.txt -q

REM Start the auto-update daemon
echo Starting kiosk with auto-updates...
python scripts/auto_update.py --daemon

pause

