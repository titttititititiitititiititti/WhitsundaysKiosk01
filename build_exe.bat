@echo off
echo.
echo  ========================================
echo    Building Tour Kiosk Launcher .exe
echo  ========================================
echo.

:: Install PyInstaller if not present
pip install pyinstaller --quiet

:: Build the exe
echo [BUILD] Creating TourKiosk.exe...
pyinstaller --onefile --noconsole --name "TourKiosk" --icon "static/favicon.ico" launcher.py 2>nul

if exist "dist\TourKiosk.exe" (
    echo.
    echo [SUCCESS] TourKiosk.exe created in dist\ folder!
    echo.
    echo Copy TourKiosk.exe to your project folder and double-click to launch.
    copy "dist\TourKiosk.exe" "TourKiosk.exe" >nul
    echo.
    echo [DONE] TourKiosk.exe is ready in the project root!
) else (
    echo [ERROR] Build failed. Check if PyInstaller is installed correctly.
)

echo.
pause

