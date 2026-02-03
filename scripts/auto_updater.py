"""
Filtour Kiosk Auto-Updater
Runs in the background and checks for updates every 5 minutes.
When updates are found, restarts the Flask app.
"""

import subprocess
import time
import os
import sys
import signal

# Configuration
CHECK_INTERVAL = 300  # Check every 5 minutes (300 seconds)
KIOSK_DIR = r"C:\filtour"
FLASK_PROCESS = None

def log(message):
    """Print timestamped log message"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_command(cmd, cwd=None):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd or KIOSK_DIR,
            capture_output=True, 
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def check_for_updates():
    """Check if there are new commits on origin/main"""
    # Fetch latest from remote
    success, _, _ = run_command("git fetch origin main")
    if not success:
        log("Warning: Could not fetch from remote")
        return False
    
    # Check if local is behind remote
    success, output, _ = run_command("git rev-list HEAD..origin/main --count")
    if success and output.strip() != "0":
        return True
    return False

def pull_updates():
    """Pull the latest updates"""
    log("Pulling updates...")
    success, output, error = run_command("git pull origin main")
    if success:
        log("Updates pulled successfully")
        return True
    else:
        log(f"Pull failed: {error}")
        return False

def start_flask():
    """Start the Flask application"""
    global FLASK_PROCESS
    log("Starting Flask app...")
    
    # Find Python executable
    python_cmd = sys.executable
    
    FLASK_PROCESS = subprocess.Popen(
        [python_cmd, "app.py"],
        cwd=KIOSK_DIR,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    log(f"Flask started (PID: {FLASK_PROCESS.pid})")
    return FLASK_PROCESS

def stop_flask():
    """Stop the Flask application"""
    global FLASK_PROCESS
    if FLASK_PROCESS:
        log("Stopping Flask app...")
        try:
            if os.name == 'nt':
                # Windows
                FLASK_PROCESS.terminate()
                FLASK_PROCESS.wait(timeout=10)
            else:
                # Unix
                os.killpg(os.getpgid(FLASK_PROCESS.pid), signal.SIGTERM)
            log("Flask stopped")
        except Exception as e:
            log(f"Error stopping Flask: {e}")
            try:
                FLASK_PROCESS.kill()
            except:
                pass
        FLASK_PROCESS = None

def restart_flask():
    """Restart the Flask application"""
    stop_flask()
    time.sleep(2)
    return start_flask()

def main():
    log("=" * 60)
    log("Filtour Kiosk Auto-Updater Started")
    log(f"Checking for updates every {CHECK_INTERVAL} seconds")
    log("=" * 60)
    
    # Change to kiosk directory
    os.chdir(KIOSK_DIR)
    
    # Start Flask initially
    start_flask()
    
    last_check = 0
    
    try:
        while True:
            current_time = time.time()
            
            # Check if Flask is still running
            if FLASK_PROCESS and FLASK_PROCESS.poll() is not None:
                log("Flask process died! Restarting...")
                start_flask()
            
            # Check for updates periodically
            if current_time - last_check >= CHECK_INTERVAL:
                last_check = current_time
                log("Checking for updates...")
                
                if check_for_updates():
                    log("Updates available!")
                    if pull_updates():
                        log("Restarting Flask with new code...")
                        restart_flask()
                else:
                    log("No updates available")
            
            time.sleep(10)  # Sleep 10 seconds between checks
            
    except KeyboardInterrupt:
        log("Shutting down...")
        stop_flask()
        log("Goodbye!")

if __name__ == "__main__":
    main()

