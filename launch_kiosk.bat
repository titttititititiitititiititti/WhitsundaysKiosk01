@echo off
title Tour Kiosk - Starting...
echo.
echo  ========================================
echo    TOUR KIOSK - Starting Application
echo  ========================================
echo.

:: Change to the script directory
cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

:: Install requirements if needed (first run)
if not exist "venv" (
    echo [SETUP] First run detected - installing dependencies...
    python -m pip install -r requirements.txt --quiet
)

:: Start Flask in background and open browser
echo [START] Starting Tour Kiosk server...
echo [INFO] Opening browser in 3 seconds...
echo.
echo  Press Ctrl+C to stop the server
echo  ========================================
echo.

:: Start the browser after a delay (in background)
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000"

:: Run Flask (this will show logs)
python app.py

