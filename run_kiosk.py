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
import json
from datetime import datetime

# Configuration
RESTART_DELAY = 3  # Seconds to wait before restarting
MAX_RAPID_RESTARTS = 5  # Max restarts within RAPID_RESTART_WINDOW
RAPID_RESTART_WINDOW = 60  # Seconds - if 5 restarts in 60s, wait longer
UPDATE_CHECK_INTERVAL = 60  # Seconds between update checks
LOG_FILE = 'logs/kiosk_runner.log'
KIOSK_PORT = 5000

# Track restart history and last update check
restart_times = []
last_update_check = 0
chrome_process = None

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
        
        # Fetch latest from origin (with verbose output for debugging)
        fetch_result = subprocess.run(
            ['git', 'fetch', 'origin', 'main'],
            cwd=script_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        
        if fetch_result.returncode != 0:
            log(f"[UPDATE] ❌ Fetch failed: {fetch_result.stderr}")
            if fetch_result.stdout:
                log(f"[UPDATE] Fetch stdout: {fetch_result.stdout}")
            return False
        
        # Get current HEAD commit
        local_head = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=script_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=5
        )
        
        # Get remote HEAD commit
        remote_head = subprocess.run(
            ['git', 'rev-parse', 'origin/main'],
            cwd=script_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=5
        )
        
        if local_head.returncode != 0 or remote_head.returncode != 0:
            log(f"[UPDATE] ⚠️ Could not get commit hashes")
            return False
        
        local_commit = local_head.stdout.strip()
        remote_commit = remote_head.stdout.strip()
        
        # Check if they're different
        if local_commit != remote_commit:
            # Check how many commits behind we are
            result = subprocess.run(
                ['git', 'rev-list', 'HEAD..origin/main', '--count'],
                cwd=script_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=10
            )
            
            if result.returncode == 0:
                commits_behind = int(result.stdout.strip() or '0')
                if commits_behind > 0:
                    log(f"[UPDATE] ✨ {commits_behind} new commit(s) available!")
                    log(f"[UPDATE] Local: {local_commit[:8]}... Remote: {remote_commit[:8]}...")
                    return True
        
        last_update_check = time.time()
        return False
        
    except subprocess.TimeoutExpired:
        log("[UPDATE] ⚠️ Timeout checking for updates")
        return False
    except Exception as e:
        log(f"[UPDATE] ❌ Error checking: {e}")
        import traceback
        traceback.print_exc()
        return False

def pull_updates():
    """Pull latest code from origin. Returns True if successful."""
    try:
        import json
        import glob as globmod
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        log("[UPDATE] 📥 Pulling latest code...")
        
        # Save local files that shouldn't be overwritten
        instance_file = os.path.join(script_dir, 'config', 'instance.json')
        instance_backup = None
        if os.path.exists(instance_file):
            with open(instance_file, 'r', encoding='utf-8') as f:
                instance_backup = f.read()
        
        # Backup local analytics files before reset (critical for multi-kiosk setups)
        analytics_backup = {}
        for af in globmod.glob(os.path.join(script_dir, 'data', 'analytics_*.json')):
            try:
                with open(af, 'r', encoding='utf-8-sig') as f:
                    analytics_backup[af] = f.read()
                log(f"[UPDATE] Backed up {os.path.basename(af)}")
            except:
                pass
        
        # Force reset to match origin exactly
        result = subprocess.run(
            ['git', 'reset', '--hard', 'origin/main'],
            cwd=script_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60
        )
        
        if result.returncode != 0:
            log(f"[UPDATE] Reset failed: {result.stderr}")
            return False
        
        # Restore analytics files - MERGE local backup with remote data
        for af, backup_content in analytics_backup.items():
            try:
                # Strip BOM if present
                clean_content = backup_content.lstrip('\ufeff')
                local_data = json.loads(clean_content)
                local_sessions = local_data.get('sessions', [])
                local_ids = {s.get('session_id') for s in local_sessions if s.get('session_id')}
                
                # Read the remote version that git reset just brought in
                remote_sessions = []
                if os.path.exists(af):
                    try:
                        with open(af, 'r', encoding='utf-8-sig') as f:
                            remote_data = json.load(f)
                        remote_sessions = remote_data.get('sessions', [])
                    except:
                        pass
                
                # Merge: start with all local sessions, add remote-only sessions
                merged = local_sessions[:]
                added = 0
                for rs in remote_sessions:
                    if rs.get('session_id') and rs['session_id'] not in local_ids:
                        merged.append(rs)
                        added += 1
                
                # Sort by started_at and cap at 1000
                merged.sort(key=lambda s: s.get('started_at', ''))
                if len(merged) > 1000:
                    merged = merged[-1000:]
                
                local_data['sessions'] = merged
                with open(af, 'w', encoding='utf-8') as f:
                    json.dump(local_data, f, indent=2)
                
                log(f"[UPDATE] Merged analytics: {len(local_sessions)} local + {added} remote = {len(merged)} total")
            except Exception as e:
                log(f"[UPDATE] ⚠️ Analytics merge failed ({e}), restoring backup")
                try:
                    with open(af, 'w', encoding='utf-8') as f:
                        f.write(backup_content)
                except:
                    pass
        
        # Restore instance.json
        if instance_backup:
            os.makedirs(os.path.dirname(instance_file), exist_ok=True)
            with open(instance_file, 'w', encoding='utf-8') as f:
                f.write(instance_backup)
            log("[UPDATE] Restored instance.json")
        
        log("[UPDATE] ✅ Code updated successfully!")
        log("[UPDATE] ⚠️ NOTE: run_kiosk.py updates require a manual restart to take effect")
        log("[UPDATE] ⚠️ The current process is still running old code - please restart run_kiosk.py")
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

def find_chrome():
    """Find Chrome executable on Windows"""
    chrome_paths = [
        os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
        os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            return path
    return None

def launch_chrome_kiosk():
    """Launch Chrome in kiosk mode (fullscreen, no UI chrome, locked down)"""
    global chrome_process
    
    chrome_path = find_chrome()
    if not chrome_path:
        log("[KIOSK] ⚠️ Chrome not found - please open http://localhost:5000 manually")
        return
    
    # Kill any existing Chrome kiosk instances we launched
    if chrome_process and chrome_process.poll() is None:
        try:
            chrome_process.terminate()
            chrome_process.wait(timeout=5)
            time.sleep(2)  # Let Windows fully release file locks on profile
        except:
            pass
    
    kiosk_url = f'http://localhost:{KIOSK_PORT}'
    
    # Chrome kiosk flags - removes ALL browser UI
    chrome_args = [
        chrome_path,
        f'--kiosk',                              # True kiosk mode - fullscreen, no chrome
        f'--app={kiosk_url}',                     # App mode (no tabs/address bar)
        '--disable-pinch',                         # No pinch zoom
        '--overscroll-history-navigation=0',       # No swipe back/forward
        '--disable-session-crashed-bubble',        # No "restore pages" dialog
        '--noerrdialogs',                          # Suppress error dialogs
        '--disable-infobars',                      # No info bars
        '--disable-translate',                     # No translate bar
        '--disable-features=TranslateUI',          # Extra translate disable
        '--disable-extensions',                    # No extensions popup
        '--disable-component-update',              # No update prompts
        '--check-for-update-interval=31536000',    # Check updates once a year
        '--autoplay-policy=no-user-gesture-required',  # Allow autoplay
        '--disable-background-networking',         # Reduce background activity
        '--no-first-run',                          # Skip first-run experience
        '--no-default-browser-check',              # Skip default browser check
        '--disable-popup-blocking',                # Allow our QR popups
        '--disable-prompt-on-repost',              # No repost warnings
        '--high-dpi-support=1',                         # Enable high DPI support
        '--force-device-scale-factor=0.875',             # Tuned for shop touchscreens (profile auto-cleared on launch)
        '--user-data-dir=' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chrome_kiosk_profile'),
    ]
    
    # Always start with a fresh profile to avoid cached zoom/settings issues
    profile_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chrome_kiosk_profile')
    import shutil
    if os.path.exists(profile_dir):
        for attempt in range(3):
            try:
                shutil.rmtree(profile_dir)
                log("[KIOSK] Cleared old Chrome profile (fresh start)")
                break
            except Exception as e:
                if attempt < 2:
                    log(f"[KIOSK] Profile cleanup attempt {attempt+1} failed, retrying in 2s...")
                    time.sleep(2)
                else:
                    log(f"[KIOSK] ⚠️ Could not clear Chrome profile: {e} (using existing)")
    
    try:
        chrome_process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log(f"[KIOSK] ✅ Chrome launched in kiosk mode (PID: {chrome_process.pid})")
        log(f"[KIOSK] 🔒 To exit: press Alt+F4 or Ctrl+Alt+Delete")
    except Exception as e:
        log(f"[KIOSK] ❌ Failed to launch Chrome: {e}")

def should_launch_chrome():
    """Check if we should auto-launch Chrome in kiosk mode"""
    # Check instance config
    instance_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'instance.json')
    if os.path.exists(instance_file):
        try:
            with open(instance_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            # Default to True for kiosk deployments, can be disabled in config
            return config.get('chrome_kiosk_mode', True)
        except:
            pass
    return True  # Default: yes, launch in kiosk mode

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
    
    # Start Flask - read as bytes and decode manually for bulletproof encoding handling
    process = None
    stdout_wrapper = None
    try:
        import io
        process = subprocess.Popen(
            cmd,
            cwd=script_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0  # Unbuffered for immediate output
        )
        
        # Wrap stdout in TextIOWrapper with explicit UTF-8 encoding and error handling
        stdout_wrapper = io.TextIOWrapper(
            process.stdout,
            encoding='utf-8',
            errors='replace',  # Replace invalid bytes with replacement character
            line_buffering=True
        )
        
        log(f"App started (PID: {process.pid})")
        
        # Wait a moment and check if process is still alive
        time.sleep(2)
        if process.poll() is not None:
            # Process died immediately - read any error output
            log(f"⚠️ App process died immediately (exit code: {process.returncode})")
            try:
                # Try to read any remaining output
                remaining = stdout_wrapper.read()
                if remaining:
                    log("Error output:")
                    print(remaining, end='', flush=True)
            except Exception as e:
                log(f"Could not read error output: {e}")
        
        # Stream output - print each line as it comes
        startup_timeout = 30  # Give app 30 seconds to start
        startup_start = time.time()
        server_ready = False
        last_output_time = time.time()
        
        while True:
            # Check if process died
            if process.poll() is not None:
                break
            
            # Check for startup timeout
            if not server_ready and (time.time() - startup_start) > startup_timeout:
                log(f"⚠️ App hasn't shown 'Running on' message after {startup_timeout}s - may be stuck")
                log("⚠️ Check the output above for errors")
                server_ready = True  # Stop warning, but keep monitoring
            
            # Check for hung process (no output for 5 minutes)
            if (time.time() - last_output_time) > 300:
                log("⚠️ No output for 5 minutes - process may be hung")
                last_output_time = time.time()  # Reset timer
            
            try:
                # Read line with timeout using select/poll if available, otherwise just read
                line = stdout_wrapper.readline()
                if line:
                    last_output_time = time.time()
                    # Print without extra newline
                    print(line, end='', flush=True)
                    
                    # Check if Flask server is ready
                    if ('Running on' in line or ' * Running on' in line) and not server_ready:
                        server_ready = True
                        log("✅ Flask server is ready!")
                        
                        # Verify server is actually responding (health check)
                        import urllib.request
                        import socket
                        try:
                            # Quick connection test to verify server is listening
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(2)
                            result = sock.connect_ex(('127.0.0.1', KIOSK_PORT))
                            sock.close()
                            if result == 0:
                                log(f"✅ Server is listening on port {KIOSK_PORT} - ready to accept connections!")
                                
                                # Auto-launch Chrome in kiosk mode (only on first start)
                                # On restarts (auto-updates), the existing Chrome auto-reconnects
                                if should_launch_chrome() and (chrome_process is None or chrome_process.poll() is not None):
                                    time.sleep(1)  # Brief pause for server to fully initialize
                                    launch_chrome_kiosk()
                                elif chrome_process and chrome_process.poll() is None:
                                    log("[KIOSK] Chrome already running — it will auto-reconnect")
                            else:
                                log(f"⚠️ Server message printed but port {KIOSK_PORT} not accessible")
                        except Exception as e:
                            log(f"⚠️ Could not verify server connection: {e}")
                elif process.poll() is not None:
                    # Process ended and no more output
                    break
                else:
                    # No line available yet, small sleep to avoid busy-waiting
                    time.sleep(0.01)
            except (UnicodeDecodeError, UnicodeError) as e:
                # This should never happen with errors='replace', but just in case
                log(f"⚠️ Encoding error (unexpected): {e}, continuing...")
                if process.poll() is not None:
                    break
                time.sleep(0.1)
            except BrokenPipeError:
                # Process closed stdout
                break
            except Exception as e:
                # Catch any other unexpected errors
                log(f"⚠️ Unexpected error reading output: {e}, continuing...")
                if process.poll() is not None:
                    break
                time.sleep(0.1)
        
        # Clean up the wrapper
        try:
            stdout_wrapper.close()
        except:
            pass
        
        exit_code = process.returncode
        if exit_code is None:
            exit_code = 1  # Process was terminated
        log(f"App exited with code: {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        log("⌨️ Keyboard interrupt - shutting down...")
        if stdout_wrapper:
            try:
                stdout_wrapper.close()
            except:
                pass
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        # Also close Chrome kiosk
        if chrome_process and chrome_process.poll() is None:
            try:
                chrome_process.terminate()
                log("[KIOSK] Chrome kiosk closed")
            except:
                pass
        return 'stop'
    except Exception as e:
        log(f"❌ Error running app: {e}")
        import traceback
        traceback.print_exc()
        if stdout_wrapper:
            try:
                stdout_wrapper.close()
            except:
                pass
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
