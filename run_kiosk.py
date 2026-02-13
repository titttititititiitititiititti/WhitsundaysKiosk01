#!/usr/bin/env python3
"""
Kiosk Runner - Keeps the Flask app running continuously with auto-restart support.
Run this instead of app.py directly for production kiosk deployments.

Usage:
    python run_kiosk.py

Features:
- Automatically restarts the app if it crashes
- Checks for updates BEFORE starting the app (handles broken code!)
- Auto-pulls fixes when crash loops are detected
- Handles graceful restarts for updates
- Logs crashes and restarts
- Works reliably on Windows
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
UPDATE_CHECK_INTERVAL = 60  # Seconds between update checks
LOG_FILE = 'logs/kiosk_runner.log'

# Track restart history and last update check
restart_times = []
last_update_check = 0

def log(message):
    """Log with timestamp to console and file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[KIOSK {timestamp}] {message}"
    print(log_line, flush=True)
    
    # Also write to log file
    try:
        os.makedirs('logs', exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
    except:
        pass

def check_for_updates():
    """Check if there are new commits on origin/main. Returns True if updates available."""
    global last_update_check
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check if we're in a git repo
        if not os.path.exists(os.path.join(script_dir, '.git')):
            return False
        
        # Fetch latest from origin
        fetch_result = subprocess.run(
            ['git', 'fetch', 'origin', 'main'],
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if fetch_result.returncode != 0:
            log(f"[UPDATE] Fetch failed: {fetch_result.stderr}")
            return False
        
        # Check how many commits behind we are
        result = subprocess.run(
            ['git', 'rev-list', 'HEAD..origin/main', '--count'],
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            commits_behind = int(result.stdout.strip() or '0')
            if commits_behind > 0:
                log(f"[UPDATE] ✨ {commits_behind} new commit(s) available!")
                return True
        
        last_update_check = time.time()
        return False
        
    except subprocess.TimeoutExpired:
        log("[UPDATE] Timeout checking for updates")
        return False
    except Exception as e:
        log(f"[UPDATE] Error checking: {e}")
        return False

def pull_updates():
    """Pull latest code from origin. Returns True if successful."""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        log("[UPDATE] 📥 Pulling latest code...")
        
        # Save local files that shouldn't be overwritten
        instance_file = os.path.join(script_dir, 'config', 'instance.json')
        instance_backup = None
        if os.path.exists(instance_file):
            with open(instance_file, 'r', encoding='utf-8') as f:
                instance_backup = f.read()
        
        # Force reset to match origin exactly
        result = subprocess.run(
            ['git', 'reset', '--hard', 'origin/main'],
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            log(f"[UPDATE] Reset failed: {result.stderr}")
            return False
        
        # Restore instance.json
        if instance_backup:
            os.makedirs(os.path.dirname(instance_file), exist_ok=True)
            with open(instance_file, 'w', encoding='utf-8') as f:
                f.write(instance_backup)
            log("[UPDATE] Restored instance.json")
        
        log("[UPDATE] ✅ Code updated successfully!")
        return True
        
    except subprocess.TimeoutExpired:
        log("[UPDATE] Timeout pulling updates")
        return False
    except Exception as e:
        log(f"[UPDATE] Error pulling: {e}")
        return False

def check_rapid_restarts():
    """Check if we're in a crash loop. Returns True if crash loop detected."""
    global restart_times
    now = time.time()
    
    # Remove old restart times outside the window
    restart_times = [t for t in restart_times if now - t < RAPID_RESTART_WINDOW]
    
    if len(restart_times) >= MAX_RAPID_RESTARTS:
        log(f"⚠️ CRASH LOOP DETECTED: {len(restart_times)} restarts in {RAPID_RESTART_WINDOW}s")
        return True
    
    restart_times.append(now)
    return False

def run_flask_app():
    """Run the Flask app and return the exit code"""
    log("🚀 Starting Flask app...")
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Simple approach: just run app.py directly
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
    global restart_times
    
    os.makedirs('logs', exist_ok=True)
    
    log("=" * 60)
    log("KIOSK RUNNER STARTED")
    log(f"Directory: {os.getcwd()}")
    log(f"Python: {sys.executable}")
    log("The app will automatically restart if it crashes")
    log("Updates are checked BEFORE each start")
    log("Press Ctrl+C to stop")
    log("=" * 60)
    
    while True:
        # ALWAYS check for updates BEFORE starting the app
        # This way, even if app.py has a syntax error, we can pull the fix
        log("[UPDATE] Checking for updates before start...")
        if check_for_updates():
            if pull_updates():
                log("[UPDATE] Restarting with new code...")
                restart_times = []  # Reset crash counter after update
        
        # Check for crash loop
        if check_rapid_restarts():
            log("[CRASH LOOP] Attempting to pull fixes from GitHub...")
            if pull_updates():
                log("[CRASH LOOP] Updates pulled, retrying...")
                restart_times = []  # Reset crash counter after update
            else:
                log("[CRASH LOOP] No updates available, waiting 60s...")
                time.sleep(60)
                restart_times = []
                continue
        
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
