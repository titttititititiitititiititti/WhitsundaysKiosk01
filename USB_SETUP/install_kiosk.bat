@echo off
title Filtour Kiosk Installer
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
echo                      FILTOUR KIOSK INSTALLER
echo ===============================================================================
echo.
echo This installer will:
echo   1. Copy the kiosk from USB to C:\filtour
echo   2. Install Python packages
echo   3. Set up auto-updates from GitHub
echo.

set USB=%~dp0

:: ===== CHECK FOR KIOSK FOLDER ON USB =====
echo [1/5] Checking USB contents...

if not exist "%USB%..\app.py" (
    echo.
    echo ERROR: Cannot find the kiosk project on USB!
    echo.
    echo Make sure the USB has this structure:
    echo   USB\
    echo     tour kiosk project\
    echo       app.py
    echo       templates\
    echo       static\
    echo       USB_SETUP\          ^<-- You are here
    echo         install_kiosk.bat
    echo.
    pause
    exit /b 1
)

echo [OK] Found kiosk project on USB
echo.

:: ===== CHECK PYTHON =====
echo [2/5] Checking for Python...

set PYCMD=

python --version >nul 2>&1
if %errorLevel% equ 0 (
    set PYCMD=python
    echo [OK] Found: python
    python --version
    goto :found_python
)

py --version >nul 2>&1
if %errorLevel% equ 0 (
    set PYCMD=py
    echo [OK] Found: py launcher
    py --version
    goto :found_python
)

:: Check common locations
for %%P in (
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python310\python.exe"
) do (
    if exist %%P (
        set "PYCMD=%%~P"
        echo [OK] Found: %%P
        goto :found_python
    )
)

echo.
echo ERROR: Python not found!
echo.
echo Please install Python first:
echo   1. Run python-3.12.x-amd64.exe from this USB
echo   2. CHECK "Add Python to PATH"
echo   3. CHECK "Install for all users"
echo   4. Run this installer again
echo.
pause
exit /b 1

:found_python
echo.

:: ===== COPY PROJECT TO C:\filtour =====
echo [3/5] Copying kiosk to C:\filtour...
echo      (This may take several minutes)
echo.

if exist "C:\filtour" (
    echo      C:\filtour already exists.
    set /p OVERWRITE="      Delete and reinstall? (y/n): "
    if /i "!OVERWRITE!"=="y" (
        echo      Removing old installation...
        rmdir /s /q "C:\filtour" 2>nul
        timeout /t 2 >nul
    ) else (
        echo      Keeping existing installation.
        goto :skip_copy
    )
)

:: Copy the entire project folder
xcopy "%USB%..\*" "C:\filtour\" /E /I /H /Y /Q

if !errorlevel! neq 0 (
    echo.
    echo ERROR: Failed to copy files!
    pause
    exit /b 1
)

echo [OK] Kiosk copied to C:\filtour
echo.

:skip_copy

:: ===== INSTALL PACKAGES =====
echo [4/5] Installing Python packages...
echo      (This may take a few minutes)
echo.

cd /d "C:\filtour"

"%PYCMD%" -m pip install --upgrade pip >nul 2>&1
"%PYCMD%" -m pip install -r requirements.txt

if !errorlevel! neq 0 (
    echo [!] Warning: Some packages may have had issues
) else (
    echo [OK] Packages installed
)
echo.

:: ===== SET UP GIT FOR AUTO-UPDATES =====
echo [5/5] Setting up auto-updates...

git --version >nul 2>&1
if %errorLevel% equ 0 (
    cd /d "C:\filtour"
    
    :: Initialize git if needed
    if not exist "C:\filtour\.git" (
        git init >nul 2>&1
    )
    
    :: Set remote for updates
    git remote remove origin >nul 2>&1
    git remote add origin https://github.com/titttititititiitititiititti/tourismwhitsundaysfiltour.git >nul 2>&1
    
    echo [OK] Auto-updates configured
    echo      The kiosk will check for updates from GitHub
) else (
    echo [!] Git not installed - auto-updates disabled
    echo      Install Git if you want automatic updates
)
echo.

:: ===== CREATE DIRECTORIES =====
if not exist "C:\filtour\logs" mkdir "C:\filtour\logs"
if not exist "C:\filtour\config" mkdir "C:\filtour\config"

:: ===== DONE =====
echo ===============================================================================
echo                      INSTALLATION COMPLETE!
echo ===============================================================================
echo.
echo Kiosk installed at: C:\filtour
echo.
echo NEXT STEPS:
echo   1. Run FIRST_TIME_SETUP.bat to create your account
echo   2. Or start the kiosk now and register at:
echo      http://localhost:5000/admin/register
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
    "%PYCMD%" app.py
)

echo.
echo Press any key to close...
pause >nul
