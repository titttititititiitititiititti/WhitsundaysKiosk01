"""
Tour Kiosk Launcher
Starts the Flask server and opens the browser automatically.
Can be compiled to .exe with: pyinstaller --onefile --noconsole launcher.py
"""

import subprocess
import webbrowser
import time
import sys
import os

def main():
    # Get the directory where the launcher is located
    if getattr(sys, 'frozen', False):
        # Running as compiled .exe
        app_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    os.chdir(app_dir)
    
    # Start Flask server
    print("Starting Tour Kiosk...")
    
    # Use pythonw for no console, python for console
    python_exe = sys.executable
    if 'pythonw' not in python_exe.lower():
        # Try to find pythonw in same directory
        pythonw = python_exe.replace('python.exe', 'pythonw.exe')
        if os.path.exists(pythonw):
            python_exe = pythonw
    
    app_path = os.path.join(app_dir, 'app.py')
    
    # Start Flask in subprocess
    process = subprocess.Popen(
        [python_exe, app_path],
        cwd=app_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
    
    # Wait for server to start
    time.sleep(2)
    
    # Open browser
    webbrowser.open('http://localhost:5000')
    
    print("Tour Kiosk is running!")
    print("Close this window to stop the server.")
    
    # Keep running until process ends
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()

if __name__ == '__main__':
    main()

