@echo off
title Filtour Kiosk
echo ================================================
echo           FILTOUR KIOSK STARTING
echo ================================================
echo.

cd /d "%~dp0"

REM Check if Python is available (support both python and py launcher)
set PYCMD=
python --version >nul 2>&1
if not errorlevel 1 (
    set PYCMD=python
) else (
    py --version >nul 2>&1
    if not errorlevel 1 (
        set PYCMD=py
    )
)

if "%PYCMD%"=="" (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from python.org
    pause
    exit /b 1
)

REM Install dependencies (self-heal if setup was incomplete)
echo Checking dependencies...
"%PYCMD%" -m pip install --upgrade pip -q
"%PYCMD%" -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo WARNING: Could not fully install dependencies from requirements.txt
    echo Trying minimal fallback install...
    "%PYCMD%" -m pip install waitress flask -q
)

echo.
echo Starting Kiosk Runner...
echo (This window will keep the app running. Don't close it!)
echo.

"%PYCMD%" run_kiosk.py

echo.
echo Kiosk has stopped.
pause
