#!/usr/bin/env python3
"""
Kiosk Runner - Keeps the Flask app running continuously with auto-restart support.
Run this instead of app.py directly for production kiosk deployments.

Usage:
    python run_kiosk.py

Features:
- Automatically restarts the app if it crashes
- Handles graceful restarts for updates
- Logs crashes and restarts
- Works reliably on Windows
- Prevents crash loops
"""

import subprocess
import sys
import os
import time
from datetime import datetime

# Configuration
RESTART_DELAY = 3  # Seconds to wait before restarting
MAX_RAPID_RESTARTS = 5  # Max restarts within RAPID_RESTART_WINDOW
RAPID_RESTART_WINDOW = 60  # Seconds - if 5 restarts in 60s, wait longer
LOG_FILE = 'logs/kiosk_runner.log'

# Track restart history
restart_times = []

def log(message):
    """Log with timestamp to console and file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[KIOSK {timestamp}] {message}"
    print(log_line)
    
    # Also write to log file
    try:
        os.makedirs('logs', exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
    except:
        pass

def check_rapid_restarts():
    """Check if we're in a crash loop and wait if needed"""
    global restart_times
    now = time.time()
    
    # Remove old restart times outside the window
    restart_times = [t for t in restart_times if now - t < RAPID_RESTART_WINDOW]
    
    if len(restart_times) >= MAX_RAPID_RESTARTS:
        log(f"⚠️ CRASH LOOP DETECTED: {len(restart_times)} restarts in {RAPID_RESTART_WINDOW}s")
        log("Waiting 60 seconds before next attempt...")
        time.sleep(60)
        restart_times = []
    
    restart_times.append(now)

def run_flask_app():
    """Run the Flask app and return the exit code"""
    log("🚀 Starting Flask app...")
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Simple approach: just run app.py directly
    # Flask's dev server is reliable for kiosk use
    cmd = [sys.executable, 'app.py']
    log(f"Running: {' '.join(cmd)}")
    
    # Set up environment
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    env['FLASK_ENV'] = 'production'
    
    # Start Flask
    process = None
    try:
        process = subprocess.Popen(
            cmd,
            cwd=script_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        log(f"App started (PID: {process.pid})")
        
        # Stream output - print each line as it comes
        while True:
            if process.stdout:
                line = process.stdout.readline()
                if line:
                    # Print without extra newline
                    print(line, end='', flush=True)
                elif process.poll() is not None:
                    break
            else:
                if process.poll() is not None:
                    break
                time.sleep(0.1)
        
        exit_code = process.returncode
        log(f"App exited with code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        log("⌨️ Keyboard interrupt - shutting down...")
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        return 'stop'
    except Exception as e:
        log(f"❌ Error running app: {e}")
        import traceback
        traceback.print_exc()
        if process:
            try:
                process.terminate()
            except:
                pass
        return 1

def main():
    """Main loop - keeps the app running forever"""
    os.makedirs('logs', exist_ok=True)
    
    log("=" * 60)
    log("KIOSK RUNNER STARTED")
    log(f"Directory: {os.getcwd()}")
    log(f"Python: {sys.executable}")
    log("The app will automatically restart if it crashes")
    log("Press Ctrl+C to stop")
    log("=" * 60)
    
    while True:
        check_rapid_restarts()
        
        result = run_flask_app()
        
        if result == 'stop':
            log("🛑 Clean shutdown requested")
            break
        elif result == 0:
            # Clean exit - likely an update restart
            log(f"🔄 App exited cleanly, restarting in {RESTART_DELAY}s...")
        else:
            # Crash
            log(f"💥 App crashed (code {result}), restarting in {RESTART_DELAY}s...")
        
        time.sleep(RESTART_DELAY)
    
    log("KIOSK RUNNER STOPPED")

if __name__ == '__main__':
    main()
