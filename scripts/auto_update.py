#!/usr/bin/env python3
"""
Filtour Auto-Update Script
==========================
This script automatically pulls updates from GitHub and restarts the Flask app.
Run this on the shop's kiosk computer to keep the app up to date.

Usage:
    python auto_update.py           # Run once
    python auto_update.py --daemon  # Run continuously (check every 5 minutes)
"""

import subprocess
import sys
import os
import time
import argparse
import signal
import logging
from datetime import datetime

# Configuration
CHECK_INTERVAL = 300  # 5 minutes between checks
FLASK_PORT = 5000
REPO_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(REPO_PATH, 'logs', 'auto_update.log'))
    ]
)
logger = logging.getLogger(__name__)

# Ensure logs directory exists
os.makedirs(os.path.join(REPO_PATH, 'logs'), exist_ok=True)

flask_process = None


def check_for_updates():
    """Check if there are updates available on the remote repository"""
    try:
        os.chdir(REPO_PATH)
        
        # Fetch latest from remote
        subprocess.run(['git', 'fetch'], capture_output=True, check=True)
        
        # Check if local is behind remote
        result = subprocess.run(
            ['git', 'status', '-uno'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if 'Your branch is behind' in result.stdout:
            logger.info("Updates available!")
            return True
        elif 'Your branch is up to date' in result.stdout:
            logger.debug("No updates available")
            return False
        else:
            logger.debug("Branch status unclear, assuming no updates")
            return False
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Git error checking for updates: {e}")
        return False


def pull_updates():
    """Pull the latest updates from the remote repository"""
    try:
        os.chdir(REPO_PATH)
        
        # Stash any local changes
        subprocess.run(['git', 'stash'], capture_output=True)
        
        # Pull latest changes
        result = subprocess.run(
            ['git', 'pull', '--rebase'],
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"Pull successful: {result.stdout.strip()}")
        
        # Install any new dependencies
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'],
            capture_output=True
        )
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Git error pulling updates: {e}")
        return False


def start_flask():
    """Start the Flask application"""
    global flask_process
    
    try:
        os.chdir(REPO_PATH)
        
        # Kill any existing Flask process on the port
        if sys.platform == 'win32':
            subprocess.run(
                f'for /f "tokens=5" %a in (\'netstat -aon ^| find ":{FLASK_PORT}"\') do taskkill /F /PID %a',
                shell=True,
                capture_output=True
            )
        else:
            subprocess.run(f'fuser -k {FLASK_PORT}/tcp', shell=True, capture_output=True)
        
        time.sleep(2)  # Wait for port to be released
        
        # Start Flask
        flask_process = subprocess.Popen(
            [sys.executable, 'app.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=REPO_PATH
        )
        
        logger.info(f"Flask started with PID: {flask_process.pid}")
        return True
        
    except Exception as e:
        logger.error(f"Error starting Flask: {e}")
        return False


def stop_flask():
    """Stop the Flask application"""
    global flask_process
    
    if flask_process:
        flask_process.terminate()
        flask_process.wait(timeout=10)
        logger.info("Flask stopped")
        flask_process = None


def update_and_restart():
    """Pull updates and restart the Flask app"""
    logger.info("=" * 50)
    logger.info("Starting update process...")
    
    if check_for_updates():
        logger.info("Pulling updates...")
        if pull_updates():
            logger.info("Restarting Flask app...")
            stop_flask()
            time.sleep(2)
            start_flask()
            logger.info("Update complete!")
        else:
            logger.error("Failed to pull updates")
    else:
        logger.info("No updates available")


def daemon_mode():
    """Run continuously, checking for updates periodically"""
    logger.info(f"Starting daemon mode (checking every {CHECK_INTERVAL}s)")
    
    # Start Flask initially
    start_flask()
    
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        stop_flask()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            update_and_restart()
        except Exception as e:
            logger.error(f"Error in daemon loop: {e}")
            time.sleep(60)  # Wait a minute before retrying


def main():
    parser = argparse.ArgumentParser(description='Filtour Auto-Update Script')
    parser.add_argument('--daemon', action='store_true', help='Run continuously')
    parser.add_argument('--check', action='store_true', help='Just check for updates')
    parser.add_argument('--pull', action='store_true', help='Just pull updates')
    args = parser.parse_args()
    
    if args.check:
        has_updates = check_for_updates()
        print(f"Updates available: {has_updates}")
    elif args.pull:
        pull_updates()
    elif args.daemon:
        daemon_mode()
    else:
        update_and_restart()


if __name__ == '__main__':
    main()

