@echo off
title Filtour Kiosk (Compatibility Launcher)
echo ============================================
echo Filtour Kiosk Launcher
echo ============================================
echo.
echo Detected legacy scripts\start_kiosk.bat path.
echo Redirecting to the main launcher...
echo.

cd /d "%~dp0.."

if exist "start_kiosk.bat" (
    call "start_kiosk.bat"
) else (
    echo ERROR: Main launcher not found at %CD%\start_kiosk.bat
    echo Run: python run_kiosk.py
    pause
    exit /b 1
)

