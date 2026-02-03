@echo off
title Filtour - Account Setup
color 0A

:: Auto-elevate to admin
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting administrator privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"

setlocal EnableDelayedExpansion

echo.
echo ===============================================================================
echo                    FILTOUR - ACCOUNT SETUP
echo ===============================================================================
echo.

:: Check if kiosk is installed
if not exist "C:\filtour\app.py" (
    echo ERROR: Kiosk not installed!
    echo.
    echo Please run install_kiosk.bat first.
    echo.
    pause
    exit /b 1
)

echo [OK] Kiosk found at C:\filtour
echo.

:: ===== ACCOUNT SETUP =====
echo ===============================================================================
echo                      LINK DEVICE TO ACCOUNT
echo ===============================================================================
echo.
echo If you haven't created an account yet:
echo   1. Start the kiosk (type 'y' at the end)
echo   2. Go to: http://localhost:5000/admin/register
echo   3. Create your account
echo   4. Run this setup again
echo.
echo If you already have an account, enter the username below.
echo.

set /p USERNAME="Account username (or press Enter to skip): "

if "%USERNAME%"=="" (
    echo.
    echo Skipping account setup - you can run this again later.
    goto :setup_autostart
)

echo.
echo Linking this device to account: %USERNAME%
echo.

:: Create config folder if needed
if not exist "C:\filtour\config" mkdir "C:\filtour\config"

:: Create instance.json
(
echo {
echo   "active_account": "%USERNAME%",
echo   "device_name": "Kiosk",
echo   "weather_widget_enabled": true,
echo   "default_language": "en",
echo   "available_languages": ["en", "zh", "ja", "de", "fr", "es", "hi"],
echo   "currency": "AUD",
echo   "setup_date": "%date% %time%"
echo }
) > "C:\filtour\config\instance.json"

echo [OK] Device linked to account: %USERNAME%
echo.

:setup_autostart
:: ===== AUTO-START SETUP =====
echo ===============================================================================
echo                      AUTO-START ON BOOT
echo ===============================================================================
echo.

set /p AUTOSTART="Start kiosk automatically when computer turns on? (y/n): "

if /i "%AUTOSTART%"=="y" (
    echo.
    echo Creating startup shortcut...
    
    echo Set oWS = WScript.CreateObject^("WScript.Shell"^) > "%temp%\shortcut.vbs"
    echo sLinkFile = oWS.SpecialFolders^("Startup"^) ^& "\Filtour Kiosk.lnk" >> "%temp%\shortcut.vbs"
    echo Set oLink = oWS.CreateShortcut^(sLinkFile^) >> "%temp%\shortcut.vbs"
    echo oLink.TargetPath = "C:\filtour\start_kiosk.bat" >> "%temp%\shortcut.vbs"
    echo oLink.WorkingDirectory = "C:\filtour" >> "%temp%\shortcut.vbs"
    echo oLink.Save >> "%temp%\shortcut.vbs"
    
    cscript //nologo "%temp%\shortcut.vbs"
    del "%temp%\shortcut.vbs"
    
    echo [OK] Kiosk will start automatically on boot
    echo.
)

:: ===== COMPLETE =====
echo ===============================================================================
echo                         SETUP COMPLETE!
echo ===============================================================================
echo.
echo To start the kiosk:
echo   - Double-click: C:\filtour\start_kiosk.bat
echo   - Or type 'y' below
echo.
echo Admin dashboard: http://localhost:5000/admin/login
echo.
echo ===============================================================================
echo.

set /p STARTNOW="Start the kiosk now? (y/n): "
if /i "%STARTNOW%"=="y" (
    echo.
    echo Starting kiosk...
    echo Open browser to: http://localhost:5000
    echo.
    cd /d "C:\filtour"
    
    if exist "start_kiosk.bat" (
        call start_kiosk.bat
    ) else (
        python app.py
    )
)

echo.
pause
