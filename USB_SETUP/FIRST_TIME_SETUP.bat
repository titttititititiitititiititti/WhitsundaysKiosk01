@echo off
title Filtour - First Time Device Setup
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
echo                    FILTOUR KIOSK - FIRST TIME SETUP
echo ===============================================================================
echo.
echo This will:
echo   1. Copy tour images from USB to kiosk
echo   2. Copy background video from USB to kiosk  
echo   3. Link this device to your account
echo   4. Set up automatic updates
echo.

:: Check if kiosk is installed
if not exist "C:\filtour\app.py" (
    echo ERROR: Kiosk not installed at C:\filtour
    echo Please run install_kiosk.bat first!
    echo.
    pause
    exit /b 1
)

echo [OK] Kiosk installation found
echo.

set USB=%~dp0

:: ===== COPY TOUR IMAGES =====
echo ===============================================================================
echo                      COPYING TOUR IMAGES
echo ===============================================================================
echo.

if exist "%USB%tour_images" (
    echo Found tour_images folder on USB...
    echo Copying to C:\filtour\static\tour_images\
    echo This may take several minutes for large image libraries...
    echo.
    
    if not exist "C:\filtour\static\tour_images" mkdir "C:\filtour\static\tour_images"
    
    xcopy "%USB%tour_images\*" "C:\filtour\static\tour_images\" /E /I /Y /Q
    
    if !errorlevel! equ 0 (
        echo.
        echo [OK] Tour images copied successfully!
    ) else (
        echo.
        echo [!] Warning: Some images may not have copied
    )
) else (
    echo [!] No tour_images folder found on USB
    echo     Put your tour_images folder on the USB stick to copy them
)
echo.

:: ===== COPY BACKGROUND VIDEO =====
echo ===============================================================================
echo                      COPYING BACKGROUND VIDEO
echo ===============================================================================
echo.

if exist "%USB%b_roll\0124.mp4" (
    echo Found background video on USB...
    
    if not exist "C:\filtour\static\b_roll" mkdir "C:\filtour\static\b_roll"
    
    copy "%USB%b_roll\0124.mp4" "C:\filtour\static\b_roll\0124.mp4" /Y >nul
    
    echo [OK] Background video copied!
) else if exist "%USB%b_roll" (
    echo Found b_roll folder, copying all videos...
    
    if not exist "C:\filtour\static\b_roll" mkdir "C:\filtour\static\b_roll"
    
    xcopy "%USB%b_roll\*" "C:\filtour\static\b_roll\" /E /I /Y /Q
    
    echo [OK] Video files copied!
) else (
    echo [!] No b_roll folder found on USB
    echo     The kiosk will use a solid color background instead
)
echo.

:: ===== COPY LOGOS =====
echo ===============================================================================
echo                      COPYING LOGOS
echo ===============================================================================
echo.

if exist "%USB%logos" (
    echo Found logos folder on USB...
    
    xcopy "%USB%logos\*" "C:\filtour\static\logos\" /E /I /Y /Q
    
    echo [OK] Logos copied!
) else (
    echo [!] No logos folder found on USB (optional)
)
echo.

:: ===== ACCOUNT SETUP =====
echo ===============================================================================
echo                      ACCOUNT SETUP
echo ===============================================================================
echo.
echo Enter the username of the account you created for this kiosk.
echo (You should have registered at http://localhost:5000/admin/register)
echo.

set /p USERNAME="Account username: "

if "%USERNAME%"=="" (
    echo ERROR: Username cannot be empty!
    pause
    exit /b 1
)

echo.
echo Linking this device to account: %USERNAME%
echo.

:: Create instance.json
(
echo {
echo   "active_account": "%USERNAME%",
echo   "device_name": "Kiosk",
echo   "weather_widget_enabled": true,
echo   "default_language": "en",
echo   "available_languages": ["en", "zh", "ja", "de", "fr", "es", "hi"],
echo   "currency": "AUD",
echo   "setup_date": "%date% %time%",
echo   "setup_note": "This kiosk is linked to the %USERNAME% account"
echo }
) > "C:\filtour\config\instance.json"

echo [OK] Device linked to account: %USERNAME%
echo.

:: ===== CREATE AUTO-UPDATE STARTUP =====
echo ===============================================================================
echo                      SETTING UP AUTO-UPDATES
echo ===============================================================================
echo.

:: Create the auto-start batch file
(
echo @echo off
echo title Filtour Kiosk
echo cd /d C:\filtour
echo :loop
echo echo Checking for updates...
echo git fetch origin main ^>nul 2^>^&1
echo git diff --quiet HEAD origin/main
echo if errorlevel 1 ^(
echo     echo Updates found! Pulling changes...
echo     git pull origin main
echo     echo Restarting kiosk...
echo     timeout /t 3 ^>nul
echo ^)
echo echo Starting kiosk...
echo python app.py
echo echo.
echo echo Kiosk stopped. Restarting in 5 seconds...
echo timeout /t 5
echo goto loop
) > "C:\filtour\start_kiosk.bat"

echo [OK] Created C:\filtour\start_kiosk.bat
echo.

:: Ask about auto-start on boot
echo Would you like the kiosk to start automatically when the computer turns on?
set /p AUTOSTART="Set up auto-start? (y/n): "

if /i "%AUTOSTART%"=="y" (
    echo.
    echo Creating startup shortcut...
    
    :: Create VBS script to make shortcut
    echo Set oWS = WScript.CreateObject^("WScript.Shell"^) > "%temp%\createshortcut.vbs"
    echo sLinkFile = oWS.SpecialFolders^("Startup"^) ^& "\Filtour Kiosk.lnk" >> "%temp%\createshortcut.vbs"
    echo Set oLink = oWS.CreateShortcut^(sLinkFile^) >> "%temp%\createshortcut.vbs"
    echo oLink.TargetPath = "C:\filtour\start_kiosk.bat" >> "%temp%\createshortcut.vbs"
    echo oLink.WorkingDirectory = "C:\filtour" >> "%temp%\createshortcut.vbs"
    echo oLink.Save >> "%temp%\createshortcut.vbs"
    
    cscript //nologo "%temp%\createshortcut.vbs"
    del "%temp%\createshortcut.vbs"
    
    echo [OK] Kiosk will start automatically on boot!
)

echo.
echo ===============================================================================
echo                         SETUP COMPLETE!
echo ===============================================================================
echo.
echo Summary:
echo   - Tour images: Copied to C:\filtour\static\tour_images\
echo   - Background:  Copied to C:\filtour\static\b_roll\
echo   - Account:     Linked to "%USERNAME%"
echo   - Auto-update: Enabled (checks on each restart)
echo   - Auto-start:  %AUTOSTART%
echo.
echo To start the kiosk manually:
echo   Double-click: C:\filtour\start_kiosk.bat
echo.
echo To push updates from your main computer:
echo   git add -A
echo   git commit -m "your changes"
echo   git push shop main
echo.
echo The kiosk will automatically pull updates when it restarts!
echo.
echo ===============================================================================
echo.

set /p STARTNOW="Start the kiosk now? (y/n): "
if /i "%STARTNOW%"=="y" (
    echo.
    echo Starting kiosk...
    echo Open browser to: http://localhost:5000
    echo.
    start "" "C:\filtour\start_kiosk.bat"
)

echo.
echo Press any key to close...
pause >nul
