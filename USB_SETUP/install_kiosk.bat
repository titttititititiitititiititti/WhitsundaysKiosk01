@echo off
title Filtour Kiosk Installer

:: ============================================
:: AUTO-ELEVATE TO ADMINISTRATOR
:: ============================================
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

:: ============================================
:: ACTUAL INSTALLER STARTS HERE
:: ============================================
setlocal EnableDelayedExpansion
color 0A

echo.
echo ===============================================================================
echo                      FILTOUR KIOSK AUTOMATED INSTALLER
echo ===============================================================================
echo.
echo Script location: %~dp0
echo Working directory: %CD%
echo.
echo [OK] Running as Administrator
echo.

:: ===== PYTHON CHECK =====
echo [1/6] Looking for Python...

python --version >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Found: python
    python --version
    set PYCMD=python
    goto :found_python
)

py --version >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Found: py launcher
    py --version
    set PYCMD=py
    goto :found_python
)

:: Manual search in common locations
if exist "C:\Python312\python.exe" (
    echo [OK] Found: C:\Python312\python.exe
    set "PYCMD=C:\Python312\python.exe"
    goto :found_python
)
if exist "C:\Python311\python.exe" (
    echo [OK] Found: C:\Python311\python.exe
    set "PYCMD=C:\Python311\python.exe"
    goto :found_python
)
if exist "C:\Python310\python.exe" (
    echo [OK] Found: C:\Python310\python.exe
    set "PYCMD=C:\Python310\python.exe"
    goto :found_python
)
if exist "C:\Program Files\Python312\python.exe" (
    echo [OK] Found: C:\Program Files\Python312\python.exe
    set "PYCMD=C:\Program Files\Python312\python.exe"
    goto :found_python
)
if exist "C:\Program Files\Python311\python.exe" (
    echo [OK] Found: C:\Program Files\Python311\python.exe
    set "PYCMD=C:\Program Files\Python311\python.exe"
    goto :found_python
)
if exist "C:\Program Files\Python310\python.exe" (
    echo [OK] Found: C:\Program Files\Python310\python.exe
    set "PYCMD=C:\Program Files\Python310\python.exe"
    goto :found_python
)

echo.
echo ************************************************************
echo *  ERROR: Python not found!                                *
echo ************************************************************
echo.
echo Please install Python first:
echo   1. Run the Python installer from this USB
echo   2. IMPORTANT: Check "Add Python to PATH"
echo   3. IMPORTANT: Select "Install for all users"
echo   4. Close this window and run installer again
echo.
pause
exit /b 1

:found_python
echo.

:: ===== GIT CHECK =====
echo [2/6] Looking for Git...

git --version >nul 2>&1
if %errorLevel% equ 0 (
    echo [OK] Found: git
    git --version
    set GITCMD=git
    goto :found_git
)

if exist "C:\Program Files\Git\bin\git.exe" (
    echo [OK] Found: C:\Program Files\Git\bin\git.exe
    set "GITCMD=C:\Program Files\Git\bin\git.exe"
    goto :found_git
)

echo.
echo ************************************************************
echo *  ERROR: Git not found!                                   *
echo ************************************************************
echo.
echo Please install Git first:
echo   1. Run the Git installer from this USB
echo   2. Use all default settings
echo   3. Close this window and run installer again
echo.
pause
exit /b 1

:found_git
echo.

:: ===== CLONE OR UPDATE REPO =====
echo [3/6] Setting up C:\filtour...

if exist "C:\filtour" (
    echo    Folder exists - updating...
    cd /d "C:\filtour"
    "%GITCMD%" pull origin main
) else (
    echo    Cloning from GitHub (may take a few minutes)...
    cd /d C:\
    "%GITCMD%" clone https://github.com/titttititititiitititiititti/tourismwhitsundaysfiltour.git filtour
    if !errorLevel! neq 0 (
        echo.
        echo ERROR: Clone failed! Check your internet connection.
        echo.
        pause
        exit /b 1
    )
)
echo [OK] Repository ready
echo.

:: ===== INSTALL PACKAGES =====
echo [4/6] Installing Python packages (this takes a few minutes)...
cd /d "C:\filtour"

"%PYCMD%" -m pip install --upgrade pip >nul 2>&1
"%PYCMD%" -m pip install -r requirements.txt

if !errorLevel! neq 0 (
    echo [!] Warning: Some packages may have issues
) else (
    echo [OK] Packages installed
)
echo.

:: ===== CREATE FOLDERS =====
echo [5/6] Creating directories...
if not exist "C:\filtour\logs" mkdir "C:\filtour\logs"
if not exist "C:\filtour\config" mkdir "C:\filtour\config"
echo [OK] Directories ready
echo.

:: ===== TEST =====
echo [6/6] Testing installation...
cd /d "C:\filtour"
"%PYCMD%" -c "import flask; print('[OK] Flask working')"
echo.

:: ===== COMPLETE =====
echo ===============================================================================
echo                         INSTALLATION COMPLETE!
echo ===============================================================================
echo.
echo   Kiosk installed at: C:\filtour
echo.
echo   TO START THE KIOSK:
echo     1. Open Command Prompt
echo     2. Type: cd C:\filtour
echo     3. Type: python app.py
echo     4. Open browser: http://localhost:5000
echo.
echo   ADMIN LOGIN: http://localhost:5000/admin/login
echo.
echo ===============================================================================
echo.

set /p STARTNOW="Start the kiosk now? (y/n): "
if /i "!STARTNOW!"=="y" (
    echo.
    echo Starting kiosk...
    echo Open browser to: http://localhost:5000
    echo Press Ctrl+C to stop the server
    echo.
    cd /d "C:\filtour"
    "%PYCMD%" app.py
)

echo.
echo Press any key to close...
pause >nul
