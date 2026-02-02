@echo off
setlocal EnableDelayedExpansion

echo ===============================================================================
echo                      FILTOUR KIOSK AUTOMATED INSTALLER
echo ===============================================================================
echo.

:: Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] This installer needs Administrator privileges.
    echo     Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

:: Check if Python is installed
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [X] Python not found!
    echo     Please install Python first from this USB drive.
    echo     IMPORTANT: Check "Add Python to PATH" during installation!
    pause
    exit /b 1
)
echo [OK] Python found
for /f "tokens=2" %%i in ('python --version 2^>^&1') do echo      Version: %%i

:: Check if Git is installed
echo.
echo [2/6] Checking Git installation...
git --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [X] Git not found!
    echo     Please install Git first from this USB drive.
    pause
    exit /b 1
)
echo [OK] Git found
for /f "tokens=3" %%i in ('git --version 2^>^&1') do echo      Version: %%i

:: Clone the repository
echo.
echo [3/6] Cloning repository to C:\filtour...
if exist "C:\filtour" (
    echo [!] C:\filtour already exists.
    set /p OVERWRITE="    Delete and reinstall? (y/n): "
    if /i "!OVERWRITE!"=="y" (
        rmdir /s /q "C:\filtour"
    ) else (
        echo     Skipping clone, using existing folder.
        goto :install_deps
    )
)

cd C:\
git clone https://github.com/titttititititiitititiititti/tourismwhitsundaysfiltour.git filtour
if %errorLevel% neq 0 (
    echo [X] Failed to clone repository!
    echo     Check your internet connection and GitHub credentials.
    pause
    exit /b 1
)
echo [OK] Repository cloned successfully

:install_deps
:: Install Python dependencies
echo.
echo [4/6] Installing Python dependencies...
cd C:\filtour
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if %errorLevel% neq 0 (
    echo [X] Failed to install dependencies!
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: Create logs directory
echo.
echo [5/6] Setting up directories...
if not exist "C:\filtour\logs" mkdir "C:\filtour\logs"
echo [OK] Directories created

:: Test the installation
echo.
echo [6/6] Testing installation...
cd C:\filtour
python -c "import flask; print('Flask OK')" >nul 2>&1
if %errorLevel% neq 0 (
    echo [X] Flask import failed!
    pause
    exit /b 1
)
echo [OK] Installation verified

echo.
echo ===============================================================================
echo                         INSTALLATION COMPLETE!
echo ===============================================================================
echo.
echo Next steps:
echo   1. To test the kiosk now, run:
echo      cd C:\filtour
echo      python app.py
echo.
echo   2. Open browser to: http://localhost:5000
echo.
echo   3. To set up auto-start, see SETUP_INSTRUCTIONS.txt
echo.
echo   4. Admin login: http://localhost:5000/admin/login
echo      Account: airliebeachtourism
echo.
echo ===============================================================================
echo.

set /p RUNNOW="Would you like to start the kiosk now? (y/n): "
if /i "%RUNNOW%"=="y" (
    echo.
    echo Starting kiosk... (Press Ctrl+C to stop)
    echo Open browser to: http://localhost:5000
    echo.
    cd C:\filtour
    python app.py
)

pause

