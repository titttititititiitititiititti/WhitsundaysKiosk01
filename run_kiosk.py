#!/usr/bin/env python3
"""
Kiosk Runner - Keeps the Flask app running continuously with auto-restart support.
Run this instead of app.py directly for production kiosk deployments.

Usage:
    python run_kiosk.py

Features:
- Automatically restarts the app if it crashes
- Handles graceful restarts for updates (via flag file)
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
RESTART_DELAY = 2  # Seconds to wait before restarting
MAX_RAPID_RESTARTS = 5  # Max restarts within RAPID_RESTART_WINDOW
RAPID_RESTART_WINDOW = 60  # Seconds - if 5 restarts in 60s, wait longer
RESTART_FLAG_FILE = 'config/.restart_requested'
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
        log(f"⚠️ CRASH LOOP: {len(restart_times)} restarts in {RAPID_RESTART_WINDOW}s")
        log("Waiting 60 seconds before next attempt...")
        time.sleep(60)
        restart_times = []
    
    restart_times.append(now)

def check_restart_flag():
    """Check if the app requested a restart"""
    if os.path.exists(RESTART_FLAG_FILE):
        try:
            os.remove(RESTART_FLAG_FILE)
            return True
        except:
            pass
    return False

def run_flask_app():
    """Run the Flask app and return the exit code"""
    log("🚀 Starting Flask app...")
    
    # Determine which server to use
    try:
        import waitress
        log("✅ Using Waitress production server")
        # Run with waitress
        cmd = [
            sys.executable, '-c',
            'from app import app; import waitress; waitress.serve(app, host="0.0.0.0", port=5000, threads=4)'
        ]
    except ImportError:
        log("⚠️ Using Flask dev server (install waitress for better stability)")
        cmd = [sys.executable, 'app.py']
    
    # Set up environment
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    
    # Start Flask
    try:
        process = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)) or '.',
            env=env
        )
        
        log(f"App started (PID: {process.pid})")
        
        # Wait for the process, checking for restart flag periodically
        while process.poll() is None:
            # Check if restart was requested
            if check_restart_flag():
                log("🔄 Restart requested, stopping app...")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                return 'restart'
            
            time.sleep(1)
        
        exit_code = process.returncode
        log(f"App exited with code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        log("Keyboard interrupt - shutting down...")
        if process:
            process.terminate()
        return 'stop'
    except Exception as e:
        log(f"Error running app: {e}")
        return 1

def main():
    """Main loop - keeps the app running forever"""
    os.makedirs('config', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    log("=" * 50)
    log("KIOSK RUNNER STARTED")
    log(f"Directory: {os.getcwd()}")
    log(f"Python: {sys.executable}")
    log("Press Ctrl+C to stop")
    log("=" * 50)
    
    while True:
        check_rapid_restarts()
        
        result = run_flask_app()
        
        if result == 'stop':
            log("Clean shutdown")
            break
        elif result == 'restart':
            log(f"Restarting in {RESTART_DELAY}s...")
        elif result == 0:
            log(f"App exited normally, restarting in {RESTART_DELAY}s...")
        else:
            log(f"💥 App crashed (code {result}), restarting in {RESTART_DELAY}s...")
        
        time.sleep(RESTART_DELAY)
    
    log("KIOSK RUNNER STOPPED")

if __name__ == '__main__':
    main()
