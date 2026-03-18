"""
Analytics Protection Module
Provides automatic backups and recovery for analytics data
"""
import json
import os
import shutil
import glob
from datetime import datetime

def create_analytics_backup(repo_path=None):
    """Create a timestamped backup of all analytics files before any dangerous operation"""
    if not repo_path:
        repo_path = os.path.dirname(os.path.abspath(__file__))
    
    backup_dir = os.path.join(repo_path, 'data', 'analytics_backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_subdir = os.path.join(backup_dir, timestamp)
    os.makedirs(backup_subdir, exist_ok=True)
    
    analytics_files = glob.glob(os.path.join(repo_path, 'data', 'analytics_*.json'))
    analytics_files = [f for f in analytics_files if '_backup' not in f and '_request' not in f]
    
    backed_up = []
    for af in analytics_files:
        try:
            backup_path = os.path.join(backup_subdir, os.path.basename(af))
            shutil.copy2(af, backup_path)
            backed_up.append(os.path.basename(af))
            
            # Also verify the backup is valid JSON
            with open(backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                session_count = len(data.get('sessions', []))
                print(f"[ANALYTICS BACKUP] Backed up {os.path.basename(af)} with {session_count} sessions to {timestamp}", flush=True)
        except Exception as e:
            print(f"[ANALYTICS BACKUP] ERROR backing up {os.path.basename(af)}: {e}", flush=True)
    
    # Keep only last 10 backups to avoid disk space issues
    cleanup_old_backups(backup_dir, keep=10)
    
    return backup_subdir, backed_up

def cleanup_old_backups(backup_dir, keep=10):
    """Remove old backups, keeping only the most recent ones"""
    try:
        backups = sorted([d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d))], reverse=True)
        if len(backups) > keep:
            for old_backup in backups[keep:]:
                old_path = os.path.join(backup_dir, old_backup)
                try:
                    shutil.rmtree(old_path)
                    print(f"[ANALYTICS BACKUP] Cleaned up old backup: {old_backup}", flush=True)
                except:
                    pass
    except:
        pass

def restore_from_backup(backup_path, repo_path=None):
    """Restore analytics files from a backup"""
    if not repo_path:
        repo_path = os.path.dirname(os.path.abspath(__file__))
    
    restored = []
    for backup_file in glob.glob(os.path.join(backup_path, 'analytics_*.json')):
        try:
            filename = os.path.basename(backup_file)
            target = os.path.join(repo_path, 'data', filename)
            
            # Verify backup is valid before restoring
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            shutil.copy2(backup_file, target)
            restored.append(filename)
            print(f"[ANALYTICS RESTORE] Restored {filename} with {len(data.get('sessions', []))} sessions", flush=True)
        except Exception as e:
            print(f"[ANALYTICS RESTORE] ERROR restoring {os.path.basename(backup_file)}: {e}", flush=True)
    
    return restored

def validate_analytics_file(file_path):
    """Validate an analytics file and return session count"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sessions = data.get('sessions', [])
        return len(sessions), True
    except Exception as e:
        return 0, False

def get_latest_backup(repo_path=None):
    """Get the path to the most recent backup"""
    if not repo_path:
        repo_path = os.path.dirname(os.path.abspath(__file__))
    
    backup_dir = os.path.join(repo_path, 'data', 'analytics_backups')
    if not os.path.exists(backup_dir):
        return None
    
    backups = sorted([d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d))], reverse=True)
    if backups:
        return os.path.join(backup_dir, backups[0])
    return None




