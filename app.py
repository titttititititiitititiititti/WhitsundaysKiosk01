import os
import sys

# Fix Windows console encoding for non-ASCII characters (Japanese, Chinese, Hindi, etc.)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass  # Older Python versions may not support reconfigure

print("Current working directory:", os.getcwd())
print("Templates folder exists:", os.path.isdir('templates'))
print("index.html exists:", os.path.isfile('templates/index.html'))
import csv
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, make_response
from functools import wraps
import openai
from dotenv import load_dotenv
import random
import glob
import re
import json
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import qrcode
from io import BytesIO
import uuid
import time
import subprocess
import threading
from werkzeug.security import generate_password_hash, check_password_hash

# RAG/Semantic Search imports
try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("[RAG] ChromaDB not available - semantic search disabled")

# [CHAT-001] Initial Flask app serving chatbot UI and connecting tours.csv to GPT-4o.
# [CHAT-002] Load environment variables from .env using python-dotenv.

load_dotenv()

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'tour-kiosk-secret-key-2024')

# App version - update this when releasing new versions
APP_VERSION = "1.0.0"

# ============================================================================
# REFERRAL TRACKING - Track which kiosk/shop referred users
# ============================================================================

# Global variable to store pending referral (set in before_request, applied in after_request)
_pending_referral = {}

@app.before_request
def track_referral():
    """
    Check for referral parameter and store in cookie.
    When users scan a QR code from a kiosk, the URL includes ?ref=accountname
    We store this in a cookie so it persists as they browse.
    """
    global _pending_referral
    
    # Check for referral parameter in URL
    ref = request.args.get('ref')
    if ref and ref != 'qr':  # 'qr' was old generic tracking, ignore it
        # Validate that this is a real account
        settings_file = f'config/accounts/{ref}/settings.json'
        if os.path.exists(settings_file):
            # Store for after_request to set cookie
            _pending_referral[id(request)] = ref
            print(f"[REFERRAL] User arrived from kiosk: {ref}")

@app.after_request
def set_referral_cookie(response):
    """Set the referral cookie after the request is processed"""
    global _pending_referral
    
    req_id = id(request)
    if req_id in _pending_referral:
        ref = _pending_referral.pop(req_id)
        # Set cookie that lasts 30 days
        response.set_cookie(
            'filtour_ref',
            ref,
            max_age=30*24*60*60,  # 30 days
            httponly=True,
            samesite='Lax'
        )
        print(f"[REFERRAL] Set cookie for: {ref}")
    
    return response

def get_referral_account():
    """
    Get the referral account from cookie or URL parameter.
    Returns the account username or None if no referral.
    """
    def account_exists(username):
        """Check if account exists in accounts or defaults folder"""
        return (os.path.exists(f'config/accounts/{username}/settings.json') or 
                os.path.exists(f'config/defaults/{username}/settings.json'))
    
    # First check URL parameter (takes precedence)
    ref = request.args.get('ref')
    if ref and ref != 'qr':
        if account_exists(ref):
            return ref
    
    # Then check cookie
    ref = request.cookies.get('filtour_ref')
    if ref:
        if account_exists(ref):
            return ref
    
    return None

# ============================================================================
# GIT SYNC - AUTO-PUSH CHANGES TO CONNECTED DEVICES
# ============================================================================

_git_sync_lock = threading.Lock()
_last_git_sync = 0
GIT_SYNC_COOLDOWN = 5  # Minimum seconds between git syncs

# GitHub token for authenticated push from Render/cloud deployments
# Set GITHUB_TOKEN environment variable with a Personal Access Token
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

def get_authenticated_remote_url():
    """Get the remote URL with authentication token embedded (for Render/cloud)"""
    if not GITHUB_TOKEN:
        return None
    
    try:
        # Get current origin URL
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=os.getcwd(), timeout=10
        )
        origin_url = result.stdout.strip()
        
        # Convert https://github.com/user/repo.git to https://token@github.com/user/repo.git
        if origin_url.startswith('https://github.com/'):
            # Remove any existing credentials
            url_without_auth = origin_url.replace('https://', '')
            if '@' in url_without_auth:
                url_without_auth = url_without_auth.split('@', 1)[1]
            return f'https://{GITHUB_TOKEN}@{url_without_auth}'
        
        return None
    except:
        return None

def git_sync_changes(commit_message="Update tour data"):
    """
    Commit and push changes to git repository.
    This allows connected shop devices to pull updates automatically.
    Runs in a background thread to avoid blocking the response.
    
    On Render/cloud: Uses GITHUB_TOKEN env var for authenticated push.
    On local: Uses stored git credentials.
    """
    def _do_git_sync():
        global _last_git_sync
        
        with _git_sync_lock:
            # Cooldown to prevent rapid-fire commits
            now = time.time()
            if now - _last_git_sync < GIT_SYNC_COOLDOWN:
                print(f"[GIT SYNC] Skipping - cooldown active ({GIT_SYNC_COOLDOWN}s)")
                return
            _last_git_sync = now
        
        try:
            # Check if we're in a git repo
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=os.getcwd()
            )
            
            if result.returncode != 0:
                print("[GIT SYNC] Not a git repository - skipping sync")
                return
            
            # Check if there are changes
            if not result.stdout.strip():
                print("[GIT SYNC] No changes to commit")
                return
            
            # Show what files are being changed
            changed_files = result.stdout.strip().split('\n')
            print(f"[GIT SYNC] Staging {len(changed_files)} changed file(s):")
            for line in changed_files[:10]:  # Show first 10
                if line.strip():
                    print(f"  - {line.strip()}")
            if len(changed_files) > 10:
                print(f"  ... and {len(changed_files) - 10} more")
            
            # Stage all changes
            add_result = subprocess.run(
                ['git', 'add', '-A'], 
                cwd=os.getcwd(), 
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True
            )
            
            # Commit
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            full_message = f"{commit_message} [{timestamp}]"
            commit_result = subprocess.run(
                ['git', 'commit', '-m', full_message],
                cwd=os.getcwd(), 
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            if commit_result.returncode != 0:
                if 'nothing to commit' in commit_result.stdout:
                    print("[GIT SYNC] No changes to commit (already committed?)")
                else:
                    print(f"[GIT SYNC] ❌ Commit failed: {commit_result.stderr}")
                    if commit_result.stdout:
                        print(f"[GIT SYNC] Commit stdout: {commit_result.stdout}")
                return
            else:
                print(f"[GIT SYNC] ✅ Committed: {full_message}")
            
            # Push changes
            # On Render/cloud: use authenticated URL with token
            # On local: use regular git push with stored credentials
            auth_url = get_authenticated_remote_url()
            
            if auth_url:
                # Use authenticated URL for Render/cloud deployment
                print("[GIT SYNC] Using authenticated push (GITHUB_TOKEN)")
                try:
                    push_result = subprocess.run(
                        ['git', 'push', auth_url, 'main'],
                        cwd=os.getcwd(), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60
                    )
                    if push_result.returncode == 0:
                        print("[GIT SYNC] ✅ Successfully pushed to origin (authenticated)")
                    else:
                        print(f"[GIT SYNC] ❌ Push failed: {push_result.stderr}")
                        print(f"[GIT SYNC] ❌ Push stdout: {push_result.stdout}")
                        return  # Don't continue if push failed
                except subprocess.TimeoutExpired:
                    print("[GIT SYNC] Authenticated push timed out")
            else:
                # Local development - push to all remotes with stored credentials
                remotes_result = subprocess.run(
                    ['git', 'remote'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=os.getcwd()
                )
                remotes = remotes_result.stdout.strip().split('\n')
                
                push_success = False
                for remote in remotes:
                    if remote:
                        try:
                            push_result = subprocess.run(
                                ['git', 'push', remote, 'main'],
                                cwd=os.getcwd(), 
                                capture_output=True, 
                                text=True,
                                encoding='utf-8',
                                errors='replace',
                                timeout=60
                            )
                            if push_result.returncode == 0:
                                print(f"[GIT SYNC] ✅ Successfully pushed to {remote}")
                                push_success = True
                            else:
                                print(f"[GIT SYNC] ❌ Push to {remote} failed: {push_result.stderr}")
                        except subprocess.TimeoutExpired:
                            print(f"[GIT SYNC] ❌ Push to {remote} timed out")
                        except Exception as e:
                            print(f"[GIT SYNC] ❌ Push to {remote} failed: {e}")
                
                if not push_success and remotes:
                    print(f"[GIT SYNC] ⚠️ WARNING: Push failed to all remotes!")
                    return
            
            print(f"[GIT SYNC] ✅ Changes synced: {commit_message}")
            
        except Exception as e:
            print(f"[GIT SYNC] Error: {e}")
    
    # Run in background thread
    thread = threading.Thread(target=_do_git_sync, daemon=True)
    thread.start()

# ============================================================================
# AUTHENTICATION & USER MANAGEMENT
# ============================================================================

def load_users():
    """Load user accounts from config file"""
    users_file = 'config/users.json'
    if os.path.exists(users_file):
        with open(users_file, 'r', encoding='utf-8') as f:
            return json.load(f).get('users', {})
    return {}

def save_users(users):
    """Save user accounts to config file"""
    users_file = 'config/users.json'
    os.makedirs('config', exist_ok=True)
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump({'users': users}, f, indent=2)

# ============================================================================
# PER-ACCOUNT CONFIG SYSTEM
# ============================================================================

def get_account_config_dir(username):
    """Get the config directory for a specific account"""
    return f'config/accounts/{username}'

def load_account_settings(username):
    """Load settings for a specific account"""
    config_dir = get_account_config_dir(username)
    settings_file = os.path.join(config_dir, 'settings.json')
    
    # First, check if account-specific settings exist
    if os.path.exists(settings_file):
        with open(settings_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Second, check for default settings (for demo accounts on Render/cloud)
    defaults_file = f'config/defaults/{username}/settings.json'
    if os.path.exists(defaults_file):
        # Only log once per session to reduce spam
        log_key = f'_logged_settings_{username}'
        if not getattr(load_account_settings, log_key, False):
            print(f"[CONFIG] Using default settings for '{username}'")
            setattr(load_account_settings, log_key, True)
        with open(defaults_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Return default settings for new accounts
    return {
        'onboarding_complete': False,
        'enabled_tours': [],  # List of tour keys that are enabled
        'enabled_companies': [],  # List of company names that are enabled
        'tour_overrides': {},  # Per-tour settings (booking URLs, prices, widgets)
        'promoted_tours': {'popular': [], 'featured': [], 'best_value': []},
        'kiosk_settings': {
            'ai_microphone_enabled': True,
            'session_timeout_minutes': 5,
            'shop_open_time': '09:00',
            'shop_close_time': '17:00',
            'auto_sleep_enabled': False,
            'default_language': 'en',
            'available_languages': ['en'],
            'weather_widget_enabled': True,
            'currency': 'AUD'
        },
        'created_at': datetime.now().isoformat()
    }

def save_account_settings(username, settings, sync_to_git=True):
    """Save settings for a specific account
    
    Saves to both:
    - config/accounts/{username}/ (local, gitignored) - for local state
    - config/defaults/{username}/ (tracked in git) - for syncing to other devices
    """
    settings['last_updated'] = datetime.now().isoformat()
    
    # Save to local (gitignored) directory
    config_dir = get_account_config_dir(username)
    os.makedirs(config_dir, exist_ok=True)
    settings_file = os.path.join(config_dir, 'settings.json')
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    
    # ALSO save to defaults directory (tracked in git) for syncing
    if sync_to_git:
        defaults_dir = f'config/defaults/{username}'
        os.makedirs(defaults_dir, exist_ok=True)
        defaults_file = os.path.join(defaults_dir, 'settings.json')
        with open(defaults_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        print(f"[CONFIG SYNC] Saved {username} settings to git-tracked location")

# ============================================================================
# CHANGE REQUEST SYSTEM - Agents request changes, admin approves/denies
# ============================================================================

PENDING_CHANGES_FILE = 'config/pending_changes.json'
ADMIN_USERS = ['bailey']  # Users who can approve/deny requests

def load_pending_changes():
    """Load all pending change requests"""
    if os.path.exists(PENDING_CHANGES_FILE):
        try:
            with open(PENDING_CHANGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'requests': []}
    return {'requests': []}

def save_pending_changes(data):
    """Save pending change requests"""
    os.makedirs(os.path.dirname(PENDING_CHANGES_FILE), exist_ok=True)
    with open(PENDING_CHANGES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def create_change_request(requested_by, change_type, description, changes_data, tour_key=None):
    """Create a new change request for admin approval"""
    data = load_pending_changes()
    
    request_id = f"req_{uuid.uuid4().hex[:8]}_{int(time.time())}"
    
    new_request = {
        'id': request_id,
        'requested_by': requested_by,
        'requested_at': datetime.now().isoformat(),
        'type': change_type,  # 'tour_update', 'tour_toggle', 'settings_change', etc.
        'description': description,
        'tour_key': tour_key,
        'changes': changes_data,  # The actual changes to apply
        'status': 'pending',  # pending, approved, denied
        'reviewed_by': None,
        'reviewed_at': None,
        'review_note': None
    }
    
    data['requests'].append(new_request)
    save_pending_changes(data)
    
    print(f"[CHANGE REQUEST] New request {request_id} from {requested_by}: {description}")
    return request_id

def get_pending_requests(status='pending'):
    """Get all requests with a specific status"""
    data = load_pending_changes()
    if status == 'all':
        return data['requests']
    return [r for r in data['requests'] if r.get('status') == status]

def get_request_by_id(request_id):
    """Get a specific request by ID"""
    data = load_pending_changes()
    for req in data['requests']:
        if req['id'] == request_id:
            return req
    return None

def approve_change_request(request_id, reviewed_by, note=None):
    """Approve a change request and apply the changes"""
    data = load_pending_changes()
    
    for req in data['requests']:
        if req['id'] == request_id and req['status'] == 'pending':
            # Apply the changes based on type
            success = apply_approved_changes(req)
            
            if success:
                req['status'] = 'approved'
                req['reviewed_by'] = reviewed_by
                req['reviewed_at'] = datetime.now().isoformat()
                req['review_note'] = note
                save_pending_changes(data)
                
                # Sync to git so kiosks get the update
                git_sync_changes(f"Approved change: {req['description']}")
                
                print(f"[CHANGE REQUEST] Approved {request_id} by {reviewed_by}")
                return True, "Changes approved and applied"
            else:
                return False, "Failed to apply changes"
    
    return False, "Request not found or already processed"

def deny_change_request(request_id, reviewed_by, note=None):
    """Deny a change request"""
    data = load_pending_changes()
    
    for req in data['requests']:
        if req['id'] == request_id and req['status'] == 'pending':
            req['status'] = 'denied'
            req['reviewed_by'] = reviewed_by
            req['reviewed_at'] = datetime.now().isoformat()
            req['review_note'] = note
            save_pending_changes(data)
            
            print(f"[CHANGE REQUEST] Denied {request_id} by {reviewed_by}")
            return True, "Request denied"
    
    return False, "Request not found or already processed"

def apply_approved_changes(request):
    """Apply the changes from an approved request"""
    try:
        change_type = request['type']
        changes = request['changes']
        username = request['requested_by']
        tour_key = request.get('tour_key')
        
        if change_type == 'tour_toggle':
            # Enable/disable a tour
            settings = load_account_settings(username)
            enabled_tours = settings.get('enabled_tours', [])
            
            if changes.get('enabled'):
                if tour_key not in enabled_tours:
                    enabled_tours.append(tour_key)
            else:
                if tour_key in enabled_tours:
                    enabled_tours.remove(tour_key)
            
            settings['enabled_tours'] = enabled_tours
            save_account_settings(username, settings)
            
        elif change_type == 'tour_update':
            # Update tour settings (booking URL, name override, etc.)
            settings = load_account_settings(username)
            if 'tour_overrides' not in settings:
                settings['tour_overrides'] = {}
            
            if tour_key not in settings['tour_overrides']:
                settings['tour_overrides'][tour_key] = {}
            
            # Apply each change
            for key, value in changes.items():
                if value:  # Only apply non-empty values
                    settings['tour_overrides'][tour_key][key] = value
                elif key in settings['tour_overrides'][tour_key]:
                    del settings['tour_overrides'][tour_key][key]
            
            save_account_settings(username, settings)
            
        elif change_type == 'tour_promotion':
            # Change tour promotion status
            settings = load_account_settings(username)
            promoted = settings.get('promoted_tours', {'popular': [], 'featured': [], 'best_value': []})
            
            new_level = changes.get('level', '')
            
            # Remove from all promotion levels first
            for level in ['popular', 'featured', 'best_value']:
                if tour_key in promoted.get(level, []):
                    promoted[level].remove(tour_key)
            
            # Add to new level if specified
            if new_level and new_level in promoted:
                promoted[new_level].append(tour_key)
            
            settings['promoted_tours'] = promoted
            save_account_settings(username, settings)
            
        elif change_type == 'kiosk_settings':
            # Update kiosk settings
            settings = load_account_settings(username)
            kiosk = settings.get('kiosk_settings', {})
            
            for key, value in changes.items():
                kiosk[key] = value
            
            settings['kiosk_settings'] = kiosk
            save_account_settings(username, settings)
        
        elif change_type == 'tour_content_edit':
            # Apply tour content changes (name, description, images, etc.) to CSV
            # This edits the actual tour data, not just account overrides
            new_data = changes.get('new_data', {})
            
            if not tour_key or not new_data:
                print("[CHANGE REQUEST] Missing tour_key or new_data")
                return False
            
            try:
                company, tid = tour_key.split('__', 1)
            except ValueError:
                print(f"[CHANGE REQUEST] Invalid tour key: {tour_key}")
                return False
            
            csv_file = find_company_csv(company)
            if not csv_file:
                print(f"[CHANGE REQUEST] Company CSV not found: {company}")
                return False
            
            # Read, update, and write back to CSV
            rows = []
            fieldnames = None
            
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)
            
            # Add any new fields
            new_fields = [f for f in new_data.keys() if f not in fieldnames]
            if new_fields:
                fieldnames = list(fieldnames) + new_fields
            
            # Find and update the tour
            tour_found = False
            for i, row in enumerate(rows):
                if row.get('id') == tid:
                    for field, value in new_data.items():
                        row[field] = value
                    rows[i] = row
                    tour_found = True
                    break
            
            if not tour_found:
                print(f"[CHANGE REQUEST] Tour not found: {tour_key}")
                return False
            
            # Write back
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"[CHANGE REQUEST] Applied tour content edit for {tour_key}")
        
        elif change_type == 'company_name_edit':
            # Update company display name
            global COMPANY_DISPLAY_NAMES
            company_key = changes.get('company_key')
            new_name = changes.get('after')
            
            if company_key and new_name:
                COMPANY_DISPLAY_NAMES[company_key] = new_name
                save_company_display_names(COMPANY_DISPLAY_NAMES)
                print(f"[CHANGE REQUEST] Applied company name edit: {company_key} -> {new_name}")
            else:
                print(f"[CHANGE REQUEST] Missing company_key or new name")
                return False
        
        else:
            print(f"[CHANGE REQUEST] Unknown change type: {change_type}")
            return False
        
        return True
        
    except Exception as e:
        print(f"[CHANGE REQUEST] Error applying changes: {e}")
        return False

def is_admin_user(username):
    """Check if user is an admin who can approve changes"""
    return username in ADMIN_USERS

def requires_approval(username):
    """Check if a user's changes require approval (non-admin agents)"""
    return username not in ADMIN_USERS

def is_tour_enabled_for_account(username, tour_key):
    """Check if a tour is enabled for a specific account"""
    settings = load_account_settings(username)
    enabled_tours = settings.get('enabled_tours', [])
    # Special case: "__ALL__" means all tours are enabled (for demo accounts)
    if enabled_tours == "__ALL__":
        return True
    return tour_key in enabled_tours

def get_enabled_tours_for_account(username):
    """Get list of enabled tour keys for an account"""
    settings = load_account_settings(username)
    return settings.get('enabled_tours', [])

def get_account_tour_override(username, tour_key):
    """Get tour-specific overrides for an account"""
    settings = load_account_settings(username)
    return settings.get('tour_overrides', {}).get(tour_key, {})

def load_agent_settings():
    """Load agent settings (promotions, disabled tours)"""
    settings_file = 'config/agent_settings.json'
    if os.path.exists(settings_file):
        with open(settings_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'disabled_tours': [],
        'promoted_tours': {'popular': [], 'featured': [], 'best_value': []},
        'promotion_levels': {},
        'ai_promotion_hints': {},
        'hero_booking_platform': {'enabled': False, 'availability_widget_url': '', 'pricing_widget_url': ''}
    }

def get_hero_booking_settings(preview_account=None):
    """Get Hero booking platform settings for frontend (uses active kiosk account or preview)"""
    # Get tour overrides from the active kiosk account or preview account
    if preview_account:
        settings = load_account_settings(preview_account)
        tour_overrides = settings.get('tour_overrides', {})
    else:
        tour_overrides = get_kiosk_tour_overrides()
    
    # Global Hero settings (rarely used now - per-tour overrides preferred)
    settings = load_agent_settings()
    hero = settings.get('hero_booking_platform', {})
    
    return {
        'enabled': hero.get('default_enabled', False),
        'availability_widget_url': hero.get('availability_widget_url', ''),
        'pricing_widget_url': hero.get('pricing_widget_url', ''),
        'tour_overrides': tour_overrides  # Per-tour settings from active account
    }

def save_agent_settings(settings):
    """Save agent settings to config file"""
    settings_file = 'config/agent_settings.json'
    os.makedirs('config', exist_ok=True)
    settings['last_updated'] = datetime.now().isoformat()
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

def get_kiosk_custom_logo(preview_account=None):
    """Get the custom logo for this kiosk instance or preview account"""
    # Use preview account if specified
    account_to_use = preview_account or get_active_account()
    if account_to_use:
        settings = load_account_settings(account_to_use)
        return settings.get('kiosk_settings', {}).get('custom_logo', '')
    
    # Fallback to instance config
    instance_config_file = 'config/instance.json'
    if os.path.exists(instance_config_file):
        with open(instance_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('custom_logo', '')
    return ''

def get_kiosk_settings(preview_account=None):
    """Get the kiosk settings for this instance or preview account"""
    account_to_use = preview_account or get_active_account()
    if account_to_use:
        settings = load_account_settings(account_to_use)
        return settings.get('kiosk_settings', {
            'ai_microphone_enabled': True,
            'session_timeout_minutes': 5
        })
    # Default settings
    return {
        'ai_microphone_enabled': True,
        'session_timeout_minutes': 5
    }

def update_instance_config(kiosk_settings, username=None):
    """Update the instance config file with kiosk settings (makes changes live)"""
    instance_config_file = 'config/instance.json'
    os.makedirs('config', exist_ok=True)
    
    # Load existing config or create new
    if os.path.exists(instance_config_file):
        with open(instance_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {}
    
    # CRITICAL: Link this kiosk instance to the account
    if username:
        config['active_account'] = username
    
    # Update relevant fields
    config['custom_logo'] = kiosk_settings.get('custom_logo', '')
    config['weather_widget_enabled'] = kiosk_settings.get('weather_widget_enabled', True)
    config['default_language'] = kiosk_settings.get('default_language', 'en')
    config['available_languages'] = kiosk_settings.get('available_languages', ['en'])
    config['currency'] = kiosk_settings.get('currency', 'AUD')
    config['last_updated'] = datetime.now().isoformat()
    
    with open(instance_config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"[INSTANCE] Updated instance config for account '{username}': logo={config.get('custom_logo', 'none')}")

def get_active_account():
    """Get the active account for this kiosk instance"""
    instance_config_file = 'config/instance.json'
    if os.path.exists(instance_config_file):
        with open(instance_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('active_account')
    return None

def get_kiosk_enabled_tours():
    """Get the list of enabled tours for this kiosk instance"""
    active_account = get_active_account()
    if active_account:
        settings = load_account_settings(active_account)
        return settings.get('enabled_tours', [])
    return []  # No account = no tours

def get_kiosk_tour_overrides():
    """Get tour overrides for this kiosk instance"""
    active_account = get_active_account()
    if active_account:
        settings = load_account_settings(active_account)
        return settings.get('tour_overrides', {})
    return {}

def get_kiosk_promotions():
    """Get promoted tours for this kiosk instance"""
    active_account = get_active_account()
    if active_account:
        settings = load_account_settings(active_account)
        return settings.get('promoted_tours', {'popular': [], 'featured': [], 'best_value': []})
    return {'popular': [], 'featured': [], 'best_value': []}

def load_shop_config(company=None):
    """Load shop-specific configuration based on company/account"""
    shops_dir = 'config/shops'
    
    # If company is specified, try to load that config
    if company:
        company_config = os.path.join(shops_dir, f'{company}.json')
        if os.path.exists(company_config):
            with open(company_config, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    # Fall back to default config
    default_config = os.path.join(shops_dir, 'default.json')
    if os.path.exists(default_config):
        with open(default_config, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # If no config files exist, return a minimal default
    return {
        'shop_id': 'default',
        'shop_name': 'Tour Kiosk',
        'modes': {
            'ai_assistant': {'enabled': True},
            'browse_tours': {'enabled': True},
            'quick_decision': {'enabled': True}
        },
        'features': {
            'weather_widget': True,
            'currency_selector': True,
            'language_selector': True,
            'available_languages': ['en', 'zh', 'ja', 'hi', 'de', 'fr', 'es']
        }
    }

def login_required(f):
    """Decorator to require login for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def agent_required(f):
    """Decorator to require agent role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        if session.get('role') != 'agent':
            return render_template('access_denied.html', message="Agent access required"), 403
        return f(*args, **kwargs)
    return decorated_function

def operator_required(f):
    """Decorator to require operator role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        if session.get('role') not in ['operator', 'agent']:
            return render_template('access_denied.html', message="Operator access required"), 403
        return f(*args, **kwargs)
    return decorated_function

def get_tour_promotion_status(tour_key, preview_account=None):
    """Get the promotion status for a tour (uses active kiosk account or preview)"""
    # Use preview account if specified, otherwise get kiosk's active account
    if preview_account:
        settings = load_account_settings(preview_account)
        promotions = settings.get('promoted_tours', {'popular': [], 'featured': [], 'best_value': []})
    else:
        promotions = get_kiosk_promotions()
    
    for level, tours in promotions.items():
        if tour_key in tours:
            return level
    return None

def is_tour_enabled(tour_key, preview_account=None):
    """Check if a tour is enabled for the active kiosk account or preview account"""
    # Use preview account if specified, otherwise get kiosk's active account
    if preview_account:
        settings = load_account_settings(preview_account)
        enabled_tours = settings.get('enabled_tours', [])
    else:
        enabled_tours = get_kiosk_enabled_tours()
    
    # Special case: "__ALL__" means all tours are enabled (for demo accounts)
    if enabled_tours == "__ALL__":
        return True
    
    # If no account is linked or account has no tours, show nothing
    if not enabled_tours:
        return False
    
    return tour_key in enabled_tours

def are_company_images_enabled(company_name):
    """Check if images are enabled for a company (for legal purposes)"""
    settings = load_agent_settings()
    return company_name not in settings.get('disabled_images_companies', [])

def get_placeholder_images():
    """Get list of placeholder images from the placeholder_images folder"""
    placeholder_dir = 'static/placeholder_images'
    if not os.path.exists(placeholder_dir):
        return ['/static/placeholder.jpg']
    
    images = []
    for ext in ['jpg', 'jpeg', 'png', 'webp']:
        images.extend(glob.glob(f'{placeholder_dir}/*.{ext}'))
    
    if not images:
        return ['/static/placeholder.jpg']
    
    # Convert to web paths
    return ['/' + img.replace('\\', '/') for img in images]


def get_newcomer_images():
    """Get list of all images from the newcomer_images folder for map view gallery"""
    newcomer_dir = 'static/newcomer_images'
    if not os.path.exists(newcomer_dir):
        return []
    
    images = []
    for ext in ['jpg', 'jpeg', 'png', 'webp']:
        images.extend(glob.glob(f'{newcomer_dir}/*.{ext}'))
    
    # Convert to relative paths (newcomer_images/filename) for url_for
    result = []
    for img in sorted(images):
        filename = os.path.basename(img)
        result.append({
            'path': f'newcomer_images/{filename}',
            'alt': os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ')
        })
    return result

def get_random_placeholder_image():
    """Get a random placeholder image"""
    images = get_placeholder_images()
    return random.choice(images)

def get_random_placeholder_gallery(count=3):
    """Get a gallery of random placeholder images (tries to avoid duplicates)"""
    images = get_placeholder_images()
    if len(images) <= count:
        return images * ((count // len(images)) + 1)[:count]
    return random.sample(images, count)

def normalize_image_url(img_url):
    """
    Normalize an image URL - handles both local paths and remote URLs.
    Local paths get a leading slash, remote URLs (http/https) are preserved as-is.
    """
    if not img_url:
        return ''
    img_url = img_url.strip()
    # Remote URLs (Cloudflare, etc.) - keep as-is
    if img_url.startswith('http://') or img_url.startswith('https://'):
        return img_url
    # Local paths - ensure leading slash
    if not img_url.startswith('/'):
        return '/' + img_url
    return img_url

def filter_hidden_images(gallery, tour_key, username=None):
    """Filter out images that are hidden for the specified account"""
    if not username or not gallery:
        return gallery
    
    settings = load_account_settings(username)
    hidden_images = settings.get('hidden_images', {}).get(tour_key, [])
    
    if not hidden_images:
        return gallery
    
    # Filter out hidden images (check both with and without leading slash)
    filtered = []
    for img in gallery:
        normalized = img.lstrip('/') if img else ''
        img_with_slash = '/' + normalized if normalized else ''
        
        if normalized not in hidden_images and img_with_slash not in hidden_images and img not in hidden_images:
            filtered.append(img)
    
    return filtered

def load_tour_images(tour, max_images=5, account_username=None):
    """
    Load images for a specific tour on demand.
    Returns (thumbnail, gallery, uses_placeholder) tuple.
    Called only when we're about to display a tour card.
    
    Supports HYBRID images:
    - Local paths: static/tour_images/company/id/image.jpg
    - Remote URLs: https://example.com/image.jpg (Cloudflare R2, etc.)
    """
    company = tour.get('company', '')
    key = tour.get('key', '')
    name = tour.get('name', '')
    
    # Extract tour ID from key (format: company__id)
    tid = key.split('__')[1] if '__' in key else ''
    
    # Check if images are enabled for this company
    images_enabled = are_company_images_enabled(company)
    
    if not images_enabled:
        # Use placeholder images
        thumb_path = get_random_placeholder_image()
        gallery = get_random_placeholder_gallery(max_images)
        # print(f"[LAZY-IMAGES] {name}: using {len(gallery)} placeholder images")  # Disabled for cleaner logs
        return thumb_path, gallery, True  # True = uses_placeholder_images
    
    # Images enabled - FIRST check if tour already has image_urls from CSV
    csv_images = tour.get('image_urls', '')
    if csv_images and isinstance(csv_images, str):
        # Parse comma-separated image URLs from CSV
        image_list = [img.strip() for img in csv_images.split(',') if img.strip()]
        if image_list:
            # Normalize URLs - handles both local paths AND remote URLs (http/https)
            gallery = []
            for img in image_list[:max_images]:
                normalized = normalize_image_url(img)
                if normalized:
                    gallery.append(normalized)
            
            # Get thumbnail from image_url field or first gallery image
            thumb_path = normalize_image_url(tour.get('image_url', ''))
            if not thumb_path and gallery:
                thumb_path = gallery[0]
            
            # Filter out hidden images for this account
            if account_username:
                gallery = filter_hidden_images(gallery, key, account_username)
                # Update thumbnail if it was filtered out
                if thumb_path and thumb_path not in gallery and gallery:
                    thumb_path = gallery[0]
                elif thumb_path and thumb_path not in gallery:
                    thumb_path = None
            
            # print(f"[LAZY-IMAGES] {name}: loaded {len(gallery)} images from CSV image_urls")  # Disabled for cleaner logs
            return thumb_path, gallery, False
    
    # Fallback: find images by scanning folder
    thumb_path = find_thumbnail(company, tid, name)
    gallery = [thumb_path] if thumb_path else []
    
    # Look for more images in the tour's image folder
    image_folder = f"static/tour_images/{company}/{tid}"
    if os.path.isdir(image_folder):
        extensions = ['.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG', '.WEBP']
        try:
            for filename in sorted(os.listdir(image_folder)):  # Sort for consistent order
                if len(gallery) >= max_images:
                    break
                # Skip thumbnail since we already have it
                if 'thumbnail' in filename.lower():
                    continue
                # Check if it's an image file
                if any(filename.endswith(ext) for ext in extensions):
                    img_url = '/' + os.path.join(image_folder, filename).replace('\\', '/')
                    if img_url not in gallery:
                        gallery.append(img_url)
        except Exception as e:
            # print(f"[LAZY-IMAGES] Error reading {image_folder}: {e}")  # Disabled for cleaner logs
            pass  # Silently ignore errors reading image folder
    
    # If we still don't have enough images, just use what we have
    if not gallery and thumb_path:
        gallery = [thumb_path]
    
    # Filter out hidden images for this account
    if account_username:
        gallery = filter_hidden_images(gallery, key, account_username)
        # Update thumbnail if it was filtered out
        if thumb_path and thumb_path not in gallery and gallery:
            thumb_path = gallery[0]
        elif thumb_path and thumb_path not in gallery:
            thumb_path = None
    
    # print(f"[LAZY-IMAGES] {name}: loaded {len(gallery)} real images from folder {image_folder}")  # Disabled for cleaner logs
    return thumb_path, gallery, False  # False = uses real images

# ============================================================================
# RAG SEMANTIC SEARCH - Find tours by meaning, not just keywords
# ============================================================================

# Global ChromaDB collection (lazy loaded)
_chroma_collection = None
_chroma_client = None
_openai_client = None

CHROMA_DB_PATH = "data/tour_embeddings"
CHROMA_COLLECTION_NAME = "tours"
EMBEDDING_MODEL = "text-embedding-3-small"

def get_chroma_collection(force_reload=False):
    """Get or initialize the ChromaDB collection for semantic search"""
    global _chroma_collection, _chroma_client
    
    if not CHROMA_AVAILABLE:
        return None
    
    if _chroma_collection is not None and not force_reload:
        return _chroma_collection
    
    try:
        db_path = os.path.join(os.path.dirname(__file__), CHROMA_DB_PATH)
        if not os.path.exists(db_path):
            print(f"[RAG] Embeddings database not found at {db_path}")
            print("[RAG] Run 'python scripts/index_tours_rag.py' to create embeddings")
            return None
        
        # Always create a fresh client to pick up any database changes
        _chroma_client = chromadb.PersistentClient(path=db_path)
        _chroma_collection = _chroma_client.get_collection(CHROMA_COLLECTION_NAME)
        print(f"[RAG] Loaded {_chroma_collection.count()} tour embeddings")
        return _chroma_collection
    except Exception as e:
        print(f"[RAG] Error loading ChromaDB: {e}")
        _chroma_collection = None
        return None

def get_query_embedding(text):
    """Get embedding for a query text using OpenAI"""
    global _openai_client
    
    if _openai_client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return None
        _openai_client = openai.OpenAI(api_key=api_key)
    
    try:
        response = _openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[text]
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"[RAG] Error creating query embedding: {e}")
        return None

def semantic_search_tours(query, n_results=10, min_similarity=0.10):
    """
    Search tours using semantic similarity.
    
    Args:
        query: Natural language search query
        n_results: Max number of results to return
        min_similarity: Minimum similarity score (0-1) to include
    
    Returns:
        List of (tour_key, similarity_score, metadata) tuples, sorted by similarity
    """
    collection = get_chroma_collection()
    if collection is None:
        print("[RAG] Semantic search unavailable - collection not loaded")
        return []
    
    # Get query embedding
    query_embedding = get_query_embedding(query)
    if query_embedding is None:
        print("[RAG] Could not create query embedding")
        return []
    
    try:
        # Query ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=['metadatas', 'distances']
        )
        
        if not results or not results['ids'] or not results['ids'][0]:
            return []
        
        # Convert distances to similarities and filter
        matches = []
        for tour_key, distance, metadata in zip(
            results['ids'][0],
            results['distances'][0],
            results['metadatas'][0]
        ):
            # ChromaDB L2 distance - convert to similarity score
            # Lower distance = more similar
            # Normalize roughly to 0-1 range
            similarity = max(0, 1 - (distance / 2))
            
            if similarity >= min_similarity:
                matches.append({
                    'key': tour_key,
                    'similarity': similarity,
                    'name': metadata.get('name', ''),
                    'company': metadata.get('company', ''),
                    'company_name': metadata.get('company_name', ''),
                    'duration_category': metadata.get('duration_category', ''),
                    'price_adult': metadata.get('price_adult', ''),
                    'promotion': metadata.get('promotion', ''),
                })
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        print(f"[RAG] Query: '{query[:50]}...' -> {len(matches)} matches")
        for i, m in enumerate(matches[:3]):
            print(f"  {i+1}. {m['name'][:40]} ({m['similarity']:.1%})")
        
        return matches
    
    except Exception as e:
        print(f"[RAG] Search error: {e}")
        return []

def get_tours_by_semantic_search(query, all_tours, max_results=8, min_similarity=0.15):
    """
    Get full tour objects matching a semantic search query.
    
    Combines RAG search with full tour data for a hybrid approach.
    
    Args:
        query: Natural language search query
        all_tours: List of all tour dictionaries (from load_all_tours)
        max_results: Maximum tours to return
        min_similarity: Minimum similarity threshold
    
    Returns:
        List of tour dictionaries with added 'similarity_score' field
    """
    # Get semantic matches
    semantic_matches = semantic_search_tours(query, n_results=max_results * 2, min_similarity=min_similarity)
    
    if not semantic_matches:
        print("[RAG] No semantic matches - falling back to keyword search")
        return []
    
    # Build key lookup for tours
    tour_by_key = {t.get('key'): t for t in all_tours if t.get('key')}
    
    # Match semantic results to full tour data
    matched_tours = []
    for match in semantic_matches:
        tour_key = match['key']
        tour = tour_by_key.get(tour_key)
        
        if tour:
            # Add similarity score to tour
            tour_with_score = tour.copy()
            tour_with_score['similarity_score'] = match['similarity']
            tour_with_score['match_type'] = 'semantic'
            matched_tours.append(tour_with_score)
        else:
            print(f"[RAG] Warning: Tour key '{tour_key}' from embeddings not found in loaded tours")
    
    # Limit results
    matched_tours = matched_tours[:max_results]
    
    print(f"[RAG] Returning {len(matched_tours)} tours for query: '{query[:30]}...'")
    return matched_tours

# ============================================================================
# ANALYTICS SYSTEM - Local logging for kiosk usage tracking (per-account)
# ============================================================================

# Default account for analytics (can be overridden per kiosk)
DEFAULT_ANALYTICS_ACCOUNT = 'bailey'

def get_analytics_file(account=None):
    """Get the analytics file path for an account"""
    account = account or DEFAULT_ANALYTICS_ACCOUNT
    return f'data/analytics_{account}.json'

def load_analytics(account=None):
    """Load analytics data from account-specific file"""
    analytics_file = get_analytics_file(account)
    if os.path.exists(analytics_file):
        try:
            with open(analytics_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error loading analytics for {account}: {e}")
            return {'sessions': [], 'summary': {}, 'account': account}
    return {'sessions': [], 'summary': {}, 'account': account or DEFAULT_ANALYTICS_ACCOUNT}

def save_analytics(data, account=None):
    """Save analytics data to account-specific file"""
    os.makedirs('data', exist_ok=True)
    analytics_file = get_analytics_file(account)
    data['account'] = account or DEFAULT_ANALYTICS_ACCOUNT
    data['last_updated'] = datetime.now().isoformat()
    with open(analytics_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def log_analytics_event(session_id, event_type, event_data=None, account=None):
    """Log an analytics event for a session (to account-specific file)"""
    account = account or DEFAULT_ANALYTICS_ACCOUNT
    analytics = load_analytics(account)
    
    # Find or create session
    session = None
    for s in analytics['sessions']:
        if s['session_id'] == session_id:
            session = s
            break
    
    if not session:
        # Don't create a new session just for a session_end event (prevents ghost sessions)
        if event_type == 'session_end':
            return None
        session = {
            'session_id': session_id,
            'account': account,
            'started_at': datetime.now().isoformat(),
            'events': [],
            'language': None,
            'mode': None,
            'tours_viewed': [],
            'tours_booked': [],
            'chat_messages': []
        }
        analytics['sessions'].append(session)
    
    # Create event
    event = {
        'type': event_type,
        'timestamp': datetime.now().isoformat(),
        'data': event_data or {}
    }
    session['events'].append(event)
    
    # Update session-level data based on event type
    if event_type == 'language_selected':
        session['language'] = event_data.get('language')
    elif event_type == 'mode_selected':
        session['mode'] = event_data.get('mode')
    elif event_type == 'tour_clicked':
        tour_name = event_data.get('tour_name')
        if tour_name and tour_name not in session['tours_viewed']:
            session['tours_viewed'].append(tour_name)
    elif event_type == 'book_now_clicked':
        tour_name = event_data.get('tour_name')
        if tour_name and tour_name not in session['tours_booked']:
            session['tours_booked'].append(tour_name)
        # Track QR code conversions
        if event_data.get('from_qr_code'):
            if 'qr_conversions' not in session:
                session['qr_conversions'] = []
            session['qr_conversions'].append({
                'tracking_id': event_data.get('qr_tracking_id'),
                'tour_name': tour_name,
                'timestamp': datetime.now().isoformat()
            })
    elif event_type == 'chat_message':
        session['chat_messages'].append({
            'role': event_data.get('role', 'user'),
            'message': event_data.get('message', '')[:500],  # Limit message length
            'timestamp': datetime.now().isoformat()
        })
    elif event_type == 'session_end':
        session['ended_at'] = datetime.now().isoformat()
        # Calculate duration
        try:
            start = datetime.fromisoformat(session['started_at'])
            end = datetime.fromisoformat(session['ended_at'])
            session['duration_seconds'] = (end - start).total_seconds()
        except:
            pass
    
    # Keep only last 1000 sessions to prevent file bloat
    if len(analytics['sessions']) > 1000:
        analytics['sessions'] = analytics['sessions'][-1000:]
    
    save_analytics(analytics, account)
    
    # Analytics are stored locally and only pushed when manually requested
    # from the agent dashboard analytics page (no more auto-push commits)
    
    return session

def is_meaningful_session(session):
    """Check if a session has meaningful user activity (not just idle timeout)"""
    # Check for any meaningful events (not just session_start/session_end)
    meaningful_event_types = {
        'tour_view', 'tour_viewed', 'tour_click', 'tour_detail',
        'mode_select', 'mode_selected', 'browse_all', 'quick_decision', 'ai_mode',
        'chat_message', 'chat_sent',
        'qr_code_generated', 'qr_tour_visit',
        'book_now_clicked', 'booking_click', 'send_to_phone', 'send_to_phone_clicked',
        'language_select', 'language_selected',
        'swipe', 'card_swipe', 'like', 'dislike'
    }
    
    events = session.get('events', [])
    for event in events:
        event_type = event.get('type', '')
        if event_type in meaningful_event_types:
            return True
    
    # Also check if tours were viewed or chat messages sent
    if len(session.get('tours_viewed', [])) > 0:
        return True
    if len(session.get('chat_messages', [])) > 0:
        return True
    
    return False

def get_analytics_summary(account=None):
    """Get summary statistics from analytics data for an account"""
    account = account or DEFAULT_ANALYTICS_ACCOUNT
    analytics = load_analytics(account)
    all_sessions = analytics.get('sessions', [])
    
    # Filter out meaningless sessions - must have REAL user activity
    # Not just session_start + session_end from idle timeout
    sessions = [s for s in all_sessions if is_meaningful_session(s)]
    
    if not sessions:
        return {
            'total_sessions': 0,
            'avg_duration_seconds': 0,
            'language_breakdown': {},
            'mode_breakdown': {},
            'top_tours_viewed': [],
            'top_tours_booked': [],
            'total_chats': 0
        }
    
    # Calculate stats (only meaningful sessions)
    total_sessions = len(sessions)
    
    # Average duration (only for ended sessions)
    durations = [s.get('duration_seconds', 0) for s in sessions if s.get('duration_seconds')]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    # Language breakdown
    languages = {}
    for s in sessions:
        lang = s.get('language', 'unknown')
        languages[lang] = languages.get(lang, 0) + 1
    
    # Mode breakdown
    modes = {}
    for s in sessions:
        mode = s.get('mode', 'unknown')
        modes[mode] = modes.get(mode, 0) + 1
    
    # Tour views
    tour_views = {}
    for s in sessions:
        for tour in s.get('tours_viewed', []):
            tour_views[tour] = tour_views.get(tour, 0) + 1
    top_tours_viewed = sorted(tour_views.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Tour bookings
    tour_bookings = {}
    for s in sessions:
        for tour in s.get('tours_booked', []):
            tour_bookings[tour] = tour_bookings.get(tour, 0) + 1
    top_tours_booked = sorted(tour_bookings.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Total chat messages
    total_chats = sum(len(s.get('chat_messages', [])) for s in sessions)
    
    # QR code tracking stats
    qr_codes_generated = 0
    qr_tour_visits = 0
    qr_book_now_clicks = 0
    qr_conversions = []
    send_to_phone_clicks = 0
    book_now_clicks = 0
    send_to_phone_by_source = {}
    book_now_by_source = {}
    
    for s in sessions:
        for event in s.get('events', []):
            if event.get('type') == 'qr_code_generated':
                qr_codes_generated += 1
            elif event.get('type') == 'qr_tour_visit':
                qr_tour_visits += 1
            elif event.get('type') == 'book_now_clicked':
                book_now_clicks += 1
                src = event.get('data', {}).get('source', 'unknown')
                book_now_by_source[src] = book_now_by_source.get(src, 0) + 1
                if event.get('data', {}).get('from_qr_code'):
                    qr_book_now_clicks += 1
            elif event.get('type') == 'send_to_phone_clicked':
                send_to_phone_clicks += 1
                src = event.get('data', {}).get('source', 'unknown')
                send_to_phone_by_source[src] = send_to_phone_by_source.get(src, 0) + 1
        
        # Collect QR conversions
        for conversion in s.get('qr_conversions', []):
            qr_conversions.append(conversion)
    
    # Calculate QR conversion rate
    qr_conversion_rate = 0
    if qr_tour_visits > 0:
        qr_conversion_rate = round((qr_book_now_clicks / qr_tour_visits) * 100, 1)
    
    return {
        'total_sessions': total_sessions,
        'avg_duration_seconds': round(avg_duration, 1),
        'avg_duration_formatted': f"{int(avg_duration // 60)}m {int(avg_duration % 60)}s",
        'language_breakdown': languages,
        'mode_breakdown': modes,
        'top_tours_viewed': top_tours_viewed,
        'top_tours_booked': top_tours_booked,
        'total_chats': total_chats,
        'recent_sessions': sessions[-20:][::-1],  # Last 20 meaningful sessions, newest first
        'account': account,
        'qr_stats': {
            'codes_generated': qr_codes_generated,
            'tour_visits': qr_tour_visits,
            'book_now_clicks': qr_book_now_clicks,
            'conversion_rate': qr_conversion_rate,
            'total_conversions': len(qr_conversions),
            'recent_conversions': sorted(qr_conversions, key=lambda x: x.get('timestamp', ''), reverse=True)[:20]
        },
        'send_to_phone_clicks': send_to_phone_clicks,
        'send_to_phone_by_source': send_to_phone_by_source,
        'book_now_clicks': book_now_clicks,
        'book_now_by_source': book_now_by_source
    }

# Company name mapping for prettier display - load from config or use defaults
def load_company_display_names():
    """Load company display names from config file, with defaults as fallback"""
    config_file = 'config/company_names.json'
    defaults = {
        'redcatadventures': 'Red Cat Adventures',
        'cruisewhitsundays': 'Cruise Whitsundays',
        'helireef': 'HeliReef',
        'sundownercruises': 'Sundowner Cruises',
        'iconicwhitsunday': 'Iconic Whitsunday',
        'oceanrafting': 'Ocean Rafting',
        'zigzagwhitsundays': 'Zigzag Whitsundays',
        'truebluesailing': 'True Blue Sailing',
        'airliebeachdiving': 'Airlie Beach Diving',
        'crocodilesafari': 'Crocodile Safari',
        'exploregroup': 'Explore Group',
        'explorewhitsundays': 'Explore Whitsundays',
        'oceandynamics': 'Ocean Dynamics',
        'ozsail': 'OzSail',
        'pioneeradventures': 'Pioneer Adventures',
        'prosail': 'ProSail'
    }
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                # Merge saved with defaults (saved takes priority)
                return {**defaults, **saved}
    except Exception as e:
        print(f"Error loading company names: {e}")
    return defaults

def save_company_display_names(names):
    """Save company display names to config file"""
    config_file = 'config/company_names.json'
    try:
        os.makedirs('config', exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(names, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving company names: {e}")
        return False

def get_company_display_names_for_account(username=None):
    """Get company display names with account-specific overrides applied"""
    # Start with global names
    names = dict(COMPANY_DISPLAY_NAMES)
    
    # Apply account-specific overrides if username provided
    if username:
        settings = load_account_settings(username)
        overrides = settings.get('company_name_overrides', {})
        names.update(overrides)
    
    return names

def get_company_display_name(company_key, username=None):
    """Get a single company's display name with optional account override"""
    names = get_company_display_names_for_account(username)
    return names.get(company_key, company_key.title())

# Load on startup
COMPANY_DISPLAY_NAMES = load_company_display_names()

def get_english_tour_name(company, tid):
    """Get the English tour name for a tour (for image matching purposes)"""
    en_folder = f"data/{company}/en"
    if not os.path.isdir(en_folder):
        return None
    
    csv_files = glob.glob(f"{en_folder}/*.csv")
    for csv_file in csv_files:
        try:
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id') == tid:
                        return row.get('name', '')
        except Exception:
            pass
    return None

def find_thumbnail(company, tid, tour_name=None):
    """Find thumbnail for a tour - always looks in static/tour_images/{company}/{tour_id}/"""
    extensions = [".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"]
    
    # Primary location: static/tour_images/{company}/{tour_id}/
    base = f"static/tour_images/{company}/{tid}/thumbnail"
    for ext in extensions:
        path = f"{base}{ext}"
        if os.path.exists(path):
            return "/" + path.replace("\\", "/")
    
    # Fallback: pick largest image from hash-based folder
    folder = f"static/tour_images/{company}/{tid}"
    if os.path.isdir(folder):
        try:
            candidates = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if os.path.splitext(f)[1].lower() in [e.lower() for e in extensions] and os.path.isfile(os.path.join(folder, f))
            ]
            if candidates:
                largest_path = max(candidates, key=lambda p: os.path.getsize(p))
                return "/" + largest_path.replace("\\", "/")
        except Exception:
            pass
    
    # Legacy fallback: try name-based folder (for old downloaded images)
    # Look for folder that contains the tour name keywords
    # IMPORTANT: Always use English tour name for matching (image folders use English names)
    english_name = tour_name
    if tour_name:
        en_name = get_english_tour_name(company, tid)
        if en_name:
            english_name = en_name
    
    if english_name:
        import re
        # Extract key words from tour name (lowercase, alphanumeric only)
        keywords = set(re.findall(r'[a-z0-9]+', english_name.lower()))
        
        company_dir = f"static/tour_images/{company}"
        if os.path.isdir(company_dir):
            try:
                # Check all folders and find best match
                best_match = None
                best_score = 0
                
                for folder_name in os.listdir(company_dir):
                    folder_path = os.path.join(company_dir, folder_name)
                    if os.path.isdir(folder_path):
                        # Score based on how many keywords match
                        folder_keywords = set(re.findall(r'[a-z0-9]+', folder_name.lower()))
                        matching_keywords = keywords & folder_keywords
                        score = len(matching_keywords)
                        
                        # Need at least 2 matching keywords to consider it
                        if score >= 2 and score > best_score:
                            best_score = score
                            best_match = folder_path
                
                # If we found a good match, look for thumbnail
                if best_match:
                    # Try thumbnail
                    for ext in extensions:
                        thumb_path = os.path.join(best_match, f"thumbnail{ext}")
                        if os.path.exists(thumb_path):
                            return "/" + thumb_path.replace("\\", "/")
                    # Try largest image
                    try:
                        candidates = [
                            os.path.join(best_match, f)
                            for f in os.listdir(best_match)
                            if os.path.splitext(f)[1].lower() in [e.lower() for e in extensions] and os.path.isfile(os.path.join(best_match, f))
                        ]
                        if candidates:
                            largest_path = max(candidates, key=lambda p: os.path.getsize(p))
                            return "/" + largest_path.replace("\\", "/")
                    except Exception:
                        pass
            except Exception:
                pass
    
    # Ultimate fallback: return a placeholder image path
    return "/static/placeholder.jpg"

# Helper functions for filtering
def parse_duration(duration_str):
    """Parse duration string into categories"""
    if not duration_str:
        return "unknown"
    duration_lower = duration_str.lower()
    
    # Check for multi-day first (most specific) - including patterns like "6 days", "2 nights", etc.
    if any(word in duration_lower for word in ["overnight", "multi", "night"]):
        return "multi_day"
    
    # Check for X day/days patterns (2+ days = multi_day, 1 day = full_day)
    days_match = re.search(r'(\d+)\s*days?', duration_lower)
    if days_match:
        num_days = int(days_match.group(1))
        if num_days >= 2:
            return "multi_day"
        elif num_days == 1:
            return "full_day"
    
    # Check for evening/sunset tours (these are half day)
    if any(word in duration_lower for word in ["evening", "sunset"]):
        return "half_day"
    
    # Check for half day variations including "half hour"
    if any(word in duration_lower for word in ["half day", "half-day", "half hour", "half-hour", "morning", "afternoon"]):
        return "half_day"
    
    # Check for minutes (anything under 4 hours in minutes is half_day)
    minutes_match = re.search(r'(\d+)\s*(?:minute|min)', duration_lower)
    if minutes_match:
        minutes = int(minutes_match.group(1))
        if minutes <= 240:  # 4 hours or less
            return "half_day"
        else:
            return "full_day"
    
    # Check for hours to determine half vs full day
    hours_match = re.search(r'(\d+)\s*(?:-\s*(\d+))?\s*hour', duration_lower)
    if hours_match:
        max_hours = int(hours_match.group(2)) if hours_match.group(2) else int(hours_match.group(1))
        if max_hours <= 4:
            return "half_day"
        else:
            return "full_day"
    
    # Check for "full day" or just "day" (but not "X days")
    if "full day" in duration_lower or "full-day" in duration_lower:
        return "full_day"
    
    # Check for standalone "day" 
    if " day" in duration_lower:
        return "full_day"
    
    return "unknown"

def parse_price(price_str):
    """Parse price string into ranges"""
    if not price_str:
        return "unknown"
    # Extract numbers from price string - handle different currency symbols and formats
    numbers = re.findall(r'[0-9]+', str(price_str))
    if numbers:
        price = int(numbers[0])
        if price < 100:
            return "budget"
        elif price < 250:
            return "mid_range"
        elif price < 500:
            return "premium"
        else:
            return "luxury"
    return "unknown"

def parse_activity_type(highlights, description, name):
    """Parse activity types from text content - returns a list to support multiple activities"""
    text = f"{highlights} {description} {name}".lower()
    
    activities = []
    
    # 1. Whitehaven Beach (very specific - highest priority)
    if "whitehaven" in text:
        activities.append("whitehaven_beach")
    
    # 2. Great Barrier Reef (must have BOTH reef-related AND water activity keywords)
    # This prevents false positives like "Crocodile Safari" 
    has_reef = any(word in text for word in ["great barrier reef", "outer reef", "inner reef", "reef world", "coral reef", "reef site"])
    has_water_activity = any(word in text for word in ["snorkel", "snorkeling", "snorkelling", "dive", "diving", "underwater", "coral", "marine life", "reef fish"])
    
    # Or check if it explicitly mentions reef AND snorkel/dive together
    if has_reef or (has_water_activity and "reef" in text):
        activities.append("great_barrier_reef")
    
    # 3. Scenic/Adventure (helicopter, flights, aerial, high-speed)
    if any(word in text for word in ["helicopter", "heli", "scenic flight", "flight", "aerial", "plane", "aircraft", "fly"]):
        activities.append("scenic_adventure")
    # Note: Include "jetski" and "jetskiing" as one word since tour data often uses that form
    if any(word in text for word in ["jet boat", "jet ski", "jetski", "jetskiing", "speed boat", "thundercat", "fast boat", "adrenaline", "thrill"]):
        if "scenic_adventure" not in activities:  # Avoid duplicates
            activities.append("scenic_adventure")
    
    # 4. Island Tours (generic island hopping, cruises, sailing)
    # ONLY tag as island_tours if NOT already tagged as Whitehaven or primarily reef-focused
    # This prevents Whitehaven tours and reef tours from being lumped into generic island tours
    if "whitehaven_beach" not in activities:  # Don't double-tag Whitehaven tours
        # Look for island-specific keywords
        has_island_keywords = any(word in text for word in ["island hop", "island tour", "island cruise", "multi-island", "hamilton island", "daydream island", "hayman island"])
        has_sailing_keywords = any(word in text for word in ["sailing", "sail", "catamaran", "yacht", "overnight sail", "multi-day sail"])
        
        # Tag as island tour if it has island keywords OR if it's a sailing/cruise tour without strong reef focus
        if has_island_keywords:
            activities.append("island_tours")
        elif has_sailing_keywords and "great_barrier_reef" not in activities:
            # Only add island_tours for sailing if it's NOT primarily a reef tour
            activities.append("island_tours")
    
    # Return list of activities, or ["other"] if none matched
    return activities if activities else ["other"]

def is_family_friendly(price_child, includes, description):
    """Determine if tour is family-friendly"""
    if price_child and price_child.strip() and "n/a" not in price_child.lower():
        return True
    
    text = f"{includes} {description}".lower()
    if any(word in text for word in ["family", "children", "kids", "child"]):
        return True
    
    return False

def has_meals_included(includes):
    """Check if meals are included"""
    if not includes:
        return False
    text = includes.lower()
    return any(word in text for word in ["lunch", "breakfast", "dinner", "meal", "food", "tea", "coffee"])

def has_equipment_included(includes):
    """Check if equipment is included"""
    if not includes:
        return False
    text = includes.lower()
    return any(word in text for word in ["equipment", "gear", "snorkel", "mask", "fins", "wetsuit"])

def load_reviews(company, tour_id):
    """Load review data for a specific tour"""
    review_file = os.path.join('tour_reviews', company, f"{tour_id}.json")
    
    if os.path.exists(review_file):
        try:
            with open(review_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading reviews for {company}/{tour_id}: {e}")
            return None
    return None

# Helper to load all tours from all *_with_media.csv files
def load_all_tours(language='en', preview_account=None):
    """Load tours from language-specific CSV folders with fallback to English and root directory
    
    Args:
        language: Language code for translations
        preview_account: If specified, use this account's settings instead of the kiosk's active account
    """
    tours = []
    csv_files = []
    loaded_companies = set()
    loaded_tour_keys = set()  # Track loaded tours to prevent duplicates
    
    # First, load from organized data/{company}/{language}/ structure
    company_dirs = glob.glob('data/*/')
    
    for company_dir in company_dirs:
        # Normalize path separators for Windows compatibility
        company_name = os.path.basename(company_dir.rstrip('/\\'))
        loaded_companies.add(company_name)
        
        # Try language-specific CSV first
        lang_csv = glob.glob(f'{company_dir}{language}/*_with_media.csv')
        
        if lang_csv:
            csv_files.extend(lang_csv)
        else:
            # Fallback to English if translation doesn't exist
            en_csv = glob.glob(f'{company_dir}en/*_with_media.csv')
            if en_csv:
                csv_files.extend(en_csv)
    
    # Also load from root directory (legacy CSVs) for companies not in data/ structure
    root_csvs = glob.glob('*_with_media.csv')
    for root_csv in root_csvs:
        # Extract company name from filename: tours_{company}_cleaned_with_media.csv
        filename = os.path.basename(root_csv)
        if filename.startswith('tours_') and filename.endswith('_cleaned_with_media.csv'):
            company_name = filename.replace('tours_', '').replace('_cleaned_with_media.csv', '')
            # Only add if not already loaded from data/ structure
            if company_name not in loaded_companies:
                csv_files.append(root_csv)
                loaded_companies.add(company_name)  # Prevent loading same company twice
    
    for csvfile in csv_files:
        try:
            # Check if file still exists before trying to open it
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tid = row['id']
                        name = row['name']
                        company = row['company_name']
                        key = f"{company}__{tid}"
                        
                        # Skip if already loaded (prevent duplicates)
                        if key in loaded_tour_keys:
                            continue
                        loaded_tour_keys.add(key)
                        
                        # Check if images are enabled for this company (legal toggle)
                        images_enabled = are_company_images_enabled(company)
                        
                        # DON'T load images here - they'll be loaded lazily when tours are displayed
                        # Just mark whether this tour uses placeholders or real images
                        thumb_path = None  # Will be loaded later
                        gallery = []  # Will be loaded later
                        
                        # Load review data
                        review_data = load_reviews(company, tid)
                        
                        # Check if tour is disabled by agent (use preview account if specified)
                        if not is_tour_enabled(key, preview_account=preview_account):
                            continue  # Skip disabled tours
                        
                        # Get promotion status (use preview account if specified)
                        promotion = get_tour_promotion_status(key, preview_account=preview_account)
                        
                        # Add parsed filter data
                        tour_data = {
                            'name': name, 
                            'thumbnail': thumb_path, 
                            'key': key,
                            'company': company,
                            'company_name': COMPANY_DISPLAY_NAMES.get(company, company.title()),
                            'price_adult': row.get('price_adult', ''),
                            'price_child': row.get('price_child', ''),
                            'price_tiers': row.get('price_tiers', ''),
                            'duration': row.get('duration', ''),
                            'includes': row.get('includes', ''),
                            'highlights': row.get('highlights', ''),
                            'description': row.get('description', ''),
                            'itinerary': row.get('itinerary', ''),
                            'menu': row.get('menu', ''),
                            'ideal_for': row.get('ideal_for', ''),
                            'age_requirements': row.get('age_requirements', ''),
                            'departure_location': row.get('departure_location', ''),
                            'gallery': gallery,  # Gallery images for slideshow
                            'uses_placeholder_images': not images_enabled,  # Flag for placeholder image indicator
                            # Parsed filter fields
                            'duration_category': parse_duration(row.get('duration', '')),
                            'price_category': parse_price(row.get('price_adult', '')),
                            'activity_type': parse_activity_type(
                                row.get('highlights', ''), 
                                row.get('description', ''), 
                                row.get('name', '')
                            ),
                            'family_friendly': is_family_friendly(
                                row.get('price_child', ''), 
                                row.get('includes', ''), 
                                row.get('description', '')
                            ),
                            'meals_included': has_meals_included(row.get('includes', '')),
                            'equipment_included': has_equipment_included(row.get('includes', '')),
                            # Review data
                            'review_rating': review_data.get('overall_rating', 0) if review_data else 0,
                            'review_count': review_data.get('review_count', 0) if review_data else 0,
                            # Booking connection flag
                            'booking_connected': row.get('booking_connected', '0'),
                            # Promotion status (for AI recommendations and sorting)
                            'promotion': promotion,
                            'is_promoted': promotion is not None,
                        }
                        tours.append(tour_data)
        except (FileNotFoundError, IOError) as e:
            print(f"Warning: Could not load {csvfile}: {e}")
            continue
        except Exception as e:
            print(f"Error processing {csvfile}: {e}")
            continue
    
    return tours

# Set your OpenAI API key here or via environment variable
openai.api_key = os.getenv('OPENAI_API_KEY')

# SendGrid Configuration
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'bookings@whitsundayskiosk.com')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')  # Fallback admin email

# Company email mapping - Real operator contact emails based on their domains
COMPANY_EMAILS = {
    # Main operators with verified domains
    'airliebeachdiving': 'bookings@airliebeachdiving.com',
    'crocodilesafari': 'bookings@crocodilesafari.com.au',
    'cruisewhitsundays': 'bailey.amouyal@gmail.com',
    'exploregroup': 'bookings@exploregroup.com.au',
    'explorewhitsundays': 'bookings@explorewhitsundays.com',
    'helireef': 'bookings@helireef.com.au',
    'iconicwhitsunday': 'bookings@iconicwhitsunday.com',
    'oceandynamics': 'bookings@oceandynamics.com.au',
    'ozsail': 'bookings@ozsail.com.au',
    'pioneeradventures': 'bookings@pioneeradventures.com.au',
    'prosail': 'bookings@prosail.com.au',
    'redcatadventures': 'bookings@redcatadventures.com.au',
    'saltydog': 'bookings@saltydog.com.au',
    'sundownercruises': 'bookings@sundownercruises.com.au',
    'truebluesailing': 'bookings@truebluesailing.com.au',
    'whitsunday-catamarans': 'bookings@whitsundaycatamarans.com.au',
    'whitsundaydiveadventures': 'bookings@whitsundaydiveadventures.com',
    'whitsundaystanduppaddle': 'bookings@whitsundaystanduppaddle.com.au',
    'zigzagwhitsundays': 'bookings@zigzagwhitsundays.com'
}

SYSTEM_PROMPT = (
    "You are a helpful tour assistant for Airlie Beach and the Whitsundays. "
    "You have access to a database of local tours. Answer questions and recommend tours based on the following data:"
)

def get_tour_context():
    # Summarize all tours for context (could be improved with RAG later)
    context = "\n".join([
        f"{t['name']} by {t['company_name']}: {t['summary']} (Price: {t['price_adult']} AUD, Departs: {t['departure_location']})"
        for t in tours_data
    ])
    return context

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    """Login page for agent and operator modes"""
    error = None
    last_username = session.get('last_login_username', '')
    
    if request.method == 'POST':
        login_id = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        
        # Remember the login identifier for next attempt
        session['last_login_username'] = login_id
        
        users = load_users()
        
        # Check if login_id is a username OR an email
        username = None
        if login_id in users:
            # Direct username match
            username = login_id
        else:
            # Try to find user by email
            for uname, udata in users.items():
                user_email = (udata.get('email') or '').lower()
                if user_email == login_id:
                    username = uname
                    break
        
        if username and username in users:
            stored_password = users[username].get('password', '')
            # Check if password is hashed (starts with pbkdf2: or scrypt:) or plain text
            password_valid = False
            if stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:'):
                # Hashed password
                password_valid = check_password_hash(stored_password, password)
            else:
                # Plain text password (backward compatibility)
                password_valid = (stored_password == password)
                # Auto-upgrade to hashed password on successful login
                if password_valid:
                    users[username]['password'] = generate_password_hash(password)
                    save_users(users)
            
            if password_valid:
                # Clear the remembered username on successful login
                session.pop('last_login_username', None)
                
                session['user'] = username
                session['role'] = users[username]['role']
                session['name'] = users[username]['name']
                company = users[username].get('company')
                session['company'] = company
                
                # Load and store shop-specific config
                shop_config = load_shop_config(company)
                session['shop_config'] = shop_config
                print(f"[LOGIN] User '{username}' logged in with shop config: {shop_config.get('shop_id', 'default')}")
                
                # Check if onboarding is complete
                account_settings = load_account_settings(username)
                if not account_settings.get('onboarding_complete', False):
                    return redirect(url_for('account_onboarding'))
                
                # Redirect based on role
                next_url = request.args.get('next')
                if next_url:
                    return redirect(next_url)
                
                if users[username]['role'] == 'agent':
                    return redirect(url_for('agent_dashboard'))
                else:
                    return redirect(url_for('operator_dashboard'))
            else:
                error = 'Invalid email/username or password'
        else:
            error = 'Invalid email/username or password'
    
    return render_template('admin_login.html', error=error, last_username=last_username)

@app.route('/admin/register', methods=['GET', 'POST'])
def register():
    """Registration page for new users"""
    error = None
    success = None
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        
        # Validation
        if not email:
            error = 'Email is required'
        elif not email.count('@') == 1 or '.' not in email.split('@')[1]:
            error = 'Please enter a valid email address'
        elif not password:
            error = 'Password is required'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters'
        elif password != confirm_password:
            error = 'Passwords do not match'
        elif not full_name:
            error = 'Full name is required'
        else:
            users = load_users()
            # Use email as username (before @), sanitize it
            base_username = email.split('@')[0].lower()
            # Remove any non-alphanumeric characters except underscores
            base_username = re.sub(r'[^a-z0-9_]', '', base_username)
            
            # Check if email already exists in any account (handle None values)
            email_exists = any((user.get('email') or '').lower() == email for user in users.values())
            if email_exists:
                error = 'An account with this email already exists'
            else:
                # Generate unique username if base username is taken
                username = base_username
                counter = 1
                while username in users:
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Create new user with agent role by default
                users[username] = {
                    'password': generate_password_hash(password),
                    'role': 'agent',
                    'name': full_name,
                    'email': email,
                    'company': None
                }
                save_users(users)
                success = 'Account created successfully! You can now log in.'
                print(f"[OK] New account created: {username} ({email})")
    
    return render_template('register.html', error=error, success=success)

# ============================================================================
# ACCOUNT ONBOARDING & SETTINGS
# ============================================================================

@app.route('/admin/onboarding', methods=['GET', 'POST'])
@login_required
def account_onboarding():
    """Onboarding wizard for new accounts - select tours to sell"""
    username = session.get('user')
    
    if request.method == 'POST':
        # Save selected tours
        selected_tours = request.form.getlist('tours')
        selected_companies = request.form.getlist('companies')
        
        settings = load_account_settings(username)
        settings['enabled_tours'] = selected_tours
        settings['enabled_companies'] = selected_companies
        settings['onboarding_complete'] = True
        save_account_settings(username, settings)
        
        # Note: Don't auto-link to kiosk here - use setup_kiosk.py for that
        # Each shop's repo should have instance.json pre-configured
        
        print(f"[ONBOARDING] User {username} completed onboarding with {len(selected_tours)} tours")
        return redirect(url_for('agent_dashboard'))
    
    # Load all available tours grouped by company
    companies = {}
    csv_files = get_all_tour_csvs()
    
    for csvfile in csv_files:
        try:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        company = row.get('company_name', 'unknown')
                        company_display = COMPANY_DISPLAY_NAMES.get(company, company)
                        
                        if company not in companies:
                            companies[company] = {
                                'display_name': company_display,
                                'tours': []
                            }
                        
                        tour_key = f"{company}__{row.get('id', '')}"
                        companies[company]['tours'].append({
                            'key': tour_key,
                            'name': row.get('name', 'Unnamed Tour'),
                            'price': row.get('price_adult', ''),
                            'duration': row.get('duration', '')
                        })
        except Exception as e:
            print(f"Error loading {csvfile}: {e}")
    
    return render_template('account_onboarding.html', 
                          companies=companies,
                          username=username)

@app.route('/admin/kiosk-settings', methods=['GET', 'POST'])
@login_required
def kiosk_settings():
    """Kiosk settings page - kiosk configuration"""
    username = session.get('user')
    settings = load_account_settings(username)
    
    if request.method == 'POST':
        # Update kiosk settings
        kiosk = settings.get('kiosk_settings', {})
        
        # Handle logo upload
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                # Create account's logo directory
                logo_dir = f'static/logos/{username}'
                os.makedirs(logo_dir, exist_ok=True)
                
                # Save the logo with a safe filename
                from werkzeug.utils import secure_filename
                filename = secure_filename(logo_file.filename)
                # Add timestamp to prevent caching issues
                import time
                timestamp = int(time.time())
                ext = os.path.splitext(filename)[1]
                new_filename = f'logo_{timestamp}{ext}'
                logo_path = os.path.join(logo_dir, new_filename)
                
                logo_file.save(logo_path)
                kiosk['custom_logo'] = '/' + logo_path.replace('\\', '/')
                print(f"[LOGO] Saved logo for {username}: {kiosk['custom_logo']}")
        
        # Handle logo removal
        if request.form.get('remove_logo') == 'true':
            if kiosk.get('custom_logo'):
                # Delete old logo file
                old_logo_path = kiosk['custom_logo'].lstrip('/')
                if os.path.exists(old_logo_path):
                    os.remove(old_logo_path)
                    print(f"[LOGO] Removed logo for {username}")
            kiosk['custom_logo'] = ''
        
        kiosk['ai_microphone_enabled'] = request.form.get('ai_microphone') == 'on'
        kiosk['session_timeout_minutes'] = int(request.form.get('session_timeout', 5))
        kiosk['shop_open_time'] = request.form.get('shop_open_time', '09:00')
        kiosk['shop_close_time'] = request.form.get('shop_close_time', '17:00')
        kiosk['auto_sleep_enabled'] = request.form.get('auto_sleep') == 'on'
        kiosk['default_language'] = request.form.get('default_language', 'en')
        kiosk['weather_widget_enabled'] = request.form.get('weather_widget') == 'on'
        kiosk['currency'] = request.form.get('currency', 'AUD')
        
        # Mode toggles
        kiosk['mode_ai_enabled'] = request.form.get('mode_ai_enabled') == 'on'
        kiosk['mode_quick_enabled'] = request.form.get('mode_quick_enabled') == 'on'
        kiosk['mode_browse_enabled'] = request.form.get('mode_browse_enabled') == 'on'
        
        print(f"[KIOSK] Mode settings for {username}: AI={kiosk['mode_ai_enabled']}, Quick={kiosk['mode_quick_enabled']}, Browse={kiosk['mode_browse_enabled']}")
        
        # Get selected languages
        selected_languages = request.form.getlist('languages')
        if not selected_languages:
            selected_languages = ['en']
        kiosk['available_languages'] = selected_languages
        
        settings['kiosk_settings'] = kiosk
        save_account_settings(username, settings)
        
        # Sync kiosk settings to connected devices
        git_sync_changes(f"Updated kiosk settings for {username}")
        
        return redirect(url_for('kiosk_settings') + '?saved=1')
    
    return render_template('kiosk_settings.html', 
                          settings=settings,
                          saved=request.args.get('saved'),
                          gallery_images=get_newcomer_images())


@app.route('/admin/api/gallery/upload', methods=['POST'])
@login_required
def gallery_upload_images():
    """Upload images to the map view presentation gallery"""
    files = request.files.getlist('gallery_images')
    if not files:
        return jsonify({'error': 'No images provided'}), 400
    
    gallery_dir = 'static/newcomer_images'
    os.makedirs(gallery_dir, exist_ok=True)
    
    uploaded = []
    for f in files:
        if f and f.filename:
            from werkzeug.utils import secure_filename
            filename = secure_filename(f.filename)
            # Keep original name but make safe
            if not filename:
                continue
            filepath = os.path.join(gallery_dir, filename)
            # If file already exists, add a number suffix
            if os.path.exists(filepath):
                name, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(filepath):
                    filename = f"{name}_{counter}{ext}"
                    filepath = os.path.join(gallery_dir, filename)
                    counter += 1
            f.save(filepath)
            uploaded.append(filename)
    
    if uploaded:
        username = session.get('user', 'unknown')
        git_sync_changes(f"Gallery: {username} added {len(uploaded)} image(s)")
    
    return jsonify({'success': True, 'uploaded': uploaded, 'count': len(uploaded)})


@app.route('/admin/api/gallery/delete', methods=['POST'])
@login_required
def gallery_delete_image():
    """Delete an image from the map view presentation gallery"""
    data = request.get_json()
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'Filename required'}), 400
    
    # Security: only allow deleting from newcomer_images dir
    safe_path = os.path.join('static', 'newcomer_images', os.path.basename(filename))
    
    if os.path.exists(safe_path):
        os.remove(safe_path)
        username = session.get('user', 'unknown')
        git_sync_changes(f"Gallery: {username} removed {os.path.basename(filename)}")
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'File not found'}), 404


@app.route('/admin/api/account/tours', methods=['POST'])
@login_required
def update_account_tours():
    """API to enable/disable tours for an account"""
    username = session.get('user')
    data = request.get_json()
    
    action = data.get('action')
    tour_key = data.get('tour_key')
    
    # Apply directly - toggles don't require approval
    settings = load_account_settings(username)
    enabled_tours = settings.get('enabled_tours', [])
    
    if action == 'enable' and tour_key not in enabled_tours:
        enabled_tours.append(tour_key)
    elif action == 'disable' and tour_key in enabled_tours:
        enabled_tours.remove(tour_key)
    
    settings['enabled_tours'] = enabled_tours
    save_account_settings(username, settings)
    
    # Sync to connected kiosks
    git_sync_changes(f"Updated enabled tours for {username}")
    
    return jsonify({'success': True, 'enabled_count': len(enabled_tours)})

@app.route('/admin/api/account/tour-override', methods=['POST'])
@login_required
def save_account_tour_override():
    """API to save tour-specific overrides for an account"""
    username = session.get('user')
    data = request.get_json()
    
    tour_key = data.get('tour_key')
    tour_name = data.get('tour_name', tour_key)
    if not tour_key:
        return jsonify({'error': 'No tour key provided'}), 400
    
    changes = {
        'booking_url': data.get('booking_url', ''),
        'widget_html': data.get('widget_html', ''),
        'price_override': data.get('price_override', ''),
        'notes': data.get('notes', ''),
    }
    
    # Check if user requires approval for changes
    if requires_approval(username):
        # Create a change request instead of applying directly
        # Build description of what's changing
        change_parts = []
        if changes['booking_url']:
            change_parts.append('booking URL')
        if changes['widget_html']:
            change_parts.append('widget HTML')
        if changes['price_override']:
            change_parts.append(f'price to {changes["price_override"]}')
        
        description = f"Update {tour_name}: {', '.join(change_parts) if change_parts else 'settings'}"
        
        request_id = create_change_request(
            requested_by=username,
            change_type='tour_update',
            description=description,
            changes_data=changes,
            tour_key=tour_key
        )
        return jsonify({
            'success': True,
            'pending_approval': True,
            'request_id': request_id,
            'message': 'Change request submitted for approval'
        })
    
    # Admin user - apply directly
    settings = load_account_settings(username)
    
    if 'tour_overrides' not in settings:
        settings['tour_overrides'] = {}
    
    settings['tour_overrides'][tour_key] = {
        **changes,
        'last_updated': datetime.now().isoformat()
    }
    
    save_account_settings(username, settings)
    
    # Sync to connected kiosks
    git_sync_changes(f"Updated tour override: {tour_key}")
    
    return jsonify({'success': True})

# ============================================================================
# CHANGE REQUEST ADMIN API - Review, approve, deny requests
# ============================================================================

@app.route('/admin/change-requests')
@login_required
def change_requests_page():
    """Admin page to review pending change requests"""
    username = session.get('user')
    
    if not is_admin_user(username):
        return "Access denied - admin only", 403
    
    pending = get_pending_requests('pending')
    recent_reviewed = [r for r in get_pending_requests('all') 
                       if r['status'] in ['approved', 'denied']][-20:]  # Last 20
    
    return render_template('change_requests.html',
                          pending_requests=pending,
                          recent_requests=recent_reviewed[::-1])  # Newest first

@app.route('/admin/api/change-requests')
@login_required
def api_get_change_requests():
    """API to get pending change requests"""
    username = session.get('user')
    
    if not is_admin_user(username):
        return jsonify({'error': 'Admin access required'}), 403
    
    status = request.args.get('status', 'pending')
    requests = get_pending_requests(status)
    
    return jsonify({
        'success': True,
        'requests': requests,
        'count': len(requests)
    })

@app.route('/admin/api/change-requests/<request_id>/approve', methods=['POST'])
@login_required
def api_approve_request(request_id):
    """API to approve a change request"""
    username = session.get('user')
    
    if not is_admin_user(username):
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json() or {}
    note = data.get('note', '')
    
    success, message = approve_change_request(request_id, username, note)
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/admin/api/change-requests/<request_id>/deny', methods=['POST'])
@login_required
def api_deny_request(request_id):
    """API to deny a change request"""
    username = session.get('user')
    
    if not is_admin_user(username):
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json() or {}
    note = data.get('note', '')
    
    success, message = deny_change_request(request_id, username, note)
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/admin/api/change-requests/pending-count')
@login_required  
def api_pending_count():
    """Get count of pending requests (for notification badge)"""
    username = session.get('user')
    
    if not is_admin_user(username):
        return jsonify({'count': 0})
    
    pending = get_pending_requests('pending')
    return jsonify({'count': len(pending)})

# Store password reset tokens in memory (with expiration)
password_reset_tokens = {}  # {username: {'code': '123456', 'expires': datetime}}

@app.route('/admin/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Send password reset code to user's email"""
    message = None
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        users = load_users()
        
        if username not in users:
            error = 'Username not found'
        else:
            user = users[username]
            email = user.get('email')
            
            if not email:
                error = 'No email address associated with this account. Please contact the administrator.'
            else:
                # Generate 6-digit code
                import random
                code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                
                # Store with 15-minute expiration
                password_reset_tokens[username] = {
                    'code': code,
                    'expires': datetime.now() + timedelta(minutes=15)
                }
                
                # Send email via SendGrid
                if SENDGRID_API_KEY:
                    try:
                        sg = SendGridAPIClient(SENDGRID_API_KEY)
                        from_email = Email(FROM_EMAIL)
                        to_email = To(email)
                        subject = "Tour Kiosk - Password Reset Code"
                        content = Content("text/html", f"""
                            <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
                                <h2 style="color: #0077b6;">Password Reset Request</h2>
                                <p>Hi {user.get('name', username)},</p>
                                <p>Your password reset code is:</p>
                                <div style="background: #f0f0f0; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; margin: 20px 0; border-radius: 10px;">
                                    {code}
                                </div>
                                <p>This code expires in 15 minutes.</p>
                                <p>If you didn't request this, please ignore this email.</p>
                                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                                <p style="color: #888; font-size: 12px;">Tour Kiosk Admin System</p>
                            </div>
                        """)
                        mail = Mail(from_email, to_email, subject, content)
                        sg.send(mail)
                        print(f"[MAIL] Password reset email sent to {email} for user {username}")
                        message = f'Reset code sent to {email[:3]}***{email[email.index("@"):]}'
                    except Exception as e:
                        print(f"Error sending reset email: {e}")
                        error = 'Failed to send email. Please try again.'
                else:
                    # For testing without SendGrid
                    print(f"[!] SENDGRID not configured. Reset code for {username}: {code}")
                    message = f'Reset code sent (check server logs if testing)'
    
    return render_template('forgot_password.html', message=message, error=error)

@app.route('/admin/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Reset password using the code sent via email"""
    message = None
    error = None
    username = request.args.get('username', request.form.get('username', '')).strip().lower()
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate
        if not username:
            error = 'Username is required'
        elif username not in password_reset_tokens:
            error = 'No reset code found. Please request a new one.'
        elif password_reset_tokens[username]['expires'] < datetime.now():
            error = 'Reset code has expired. Please request a new one.'
            del password_reset_tokens[username]
        elif password_reset_tokens[username]['code'] != code:
            error = 'Invalid reset code'
        elif len(new_password) < 6:
            error = 'Password must be at least 6 characters'
        elif new_password != confirm_password:
            error = 'Passwords do not match'
        else:
            # Update password (hash it)
            users = load_users()
            if username in users:
                users[username]['password'] = generate_password_hash(new_password)
                save_users(users)
                del password_reset_tokens[username]
                print(f"ðŸ”‘ Password reset successful for {username}")
                return redirect(url_for('login') + '?reset=success')
            else:
                error = 'User not found'
    
    return render_template('reset_password.html', username=username, error=error, message=message)

@app.route('/admin/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/account-settings', methods=['GET', 'POST'])
@login_required
def account_settings():
    """Account settings page - update name, email, and password"""
    error = None
    success = None
    
    if 'user' not in session:
        return redirect(url_for('login'))
    
    username = session['user']
    users = load_users()
    
    if username not in users:
        session.clear()
        return redirect(url_for('login'))
    
    user = users[username]
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_profile':
            # Update name and/or email
            new_name = request.form.get('full_name', '').strip()
            new_email = request.form.get('email', '').strip().lower()
            
            if not new_name:
                error = 'Full name is required'
            elif not new_email:
                error = 'Email is required'
            elif not (new_email.count('@') == 1 and '.' in new_email.split('@')[1]):
                error = 'Please enter a valid email address'
            else:
                # Check if email is already taken by another user
                email_taken = any(
                    (u.get('email') or '').lower() == new_email and ukey != username 
                    for ukey, u in users.items()
                )
                if email_taken:
                    error = 'This email is already associated with another account'
                else:
                    user['name'] = new_name
                    user['email'] = new_email
                    save_users(users)
                    # Update session
                    session['name'] = new_name
                    success = 'Profile updated successfully!'
                    print(f"[OK] Profile updated for {username}")
        
        elif action == 'change_password':
            # Change password
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not current_password:
                error = 'Current password is required'
            elif not new_password:
                error = 'New password is required'
            elif len(new_password) < 6:
                error = 'New password must be at least 6 characters'
            elif new_password != confirm_password:
                error = 'New passwords do not match'
            else:
                # Verify current password
                stored_password = user.get('password', '')
                password_valid = False
                
                if stored_password.startswith('pbkdf2:'):
                    # Hashed password
                    password_valid = check_password_hash(stored_password, current_password)
                else:
                    # Plain text password (backward compatibility)
                    password_valid = (stored_password == current_password)
                
                if not password_valid:
                    error = 'Current password is incorrect'
                else:
                    # Update password
                    user['password'] = generate_password_hash(new_password)
                    save_users(users)
                    success = 'Password changed successfully!'
                    print(f"ðŸ”‘ Password changed for {username}")
    
    return render_template('account_settings.html', 
                          user=user, 
                          username=username,
                          error=error, 
                          success=success)

# ============================================================================
# AGENT MODE ROUTES
# ============================================================================

@app.route('/admin/agent')
# @agent_required  # Disabled for testing
def agent_dashboard():
    """Agent dashboard - manage tour visibility and promotions"""
    # Use account-specific settings if user is logged in
    username = session.get('user')
    print(f"[DASHBOARD DEBUG] Session user: {username}")
    print(f"[DASHBOARD DEBUG] Session name: {session.get('name')}")
    if username:
        account_settings = load_account_settings(username)
        enabled_tours_for_account = account_settings.get('enabled_tours', [])
        account_tour_overrides = account_settings.get('tour_overrides', {})
        account_promotions = account_settings.get('promoted_tours', {})
        print(f"[DASHBOARD DEBUG] Loaded {len(enabled_tours_for_account)} enabled tours for '{username}'")
        print(f"[DASHBOARD DEBUG] Settings file: config/accounts/{username}/settings.json")
    else:
        enabled_tours_for_account = []
        account_tour_overrides = {}
        account_promotions = {}
        print(f"[DASHBOARD DEBUG] No user in session!")
    
    # Also load global settings for fallback
    global_settings = load_agent_settings()
    
    # Load all tours grouped by company
    all_tours = []
    loaded_keys = set()  # Prevent duplicates
    csv_files = get_all_tour_csvs()
    
    for csvfile in csv_files:
        try:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        company = row.get('company_name', 'unknown')
                        tour_key = f"{company}__{row.get('id', '')}"
                        
                        # Skip duplicates
                        if tour_key in loaded_keys:
                            continue
                        loaded_keys.add(tour_key)
                        
                        # Check if tour has a booking link configured (use account override first)
                        tour_overrides = account_tour_overrides.get(tour_key, {})
                        has_booking_link = bool(
                            tour_overrides.get('booking_button_url') or 
                            tour_overrides.get('hero_widget_html') or
                            row.get('booking_url')  # Check CSV for default booking URL
                        )
                        
                        # Check if tour is enabled for this account
                        # For new accounts with no enabled_tours, all tours are disabled
                        is_enabled = tour_key in enabled_tours_for_account if enabled_tours_for_account else False
                        
                        # Check promotion status from account settings
                        promotion = None
                        for promo_type in ['popular', 'featured', 'best_value']:
                            if tour_key in account_promotions.get(promo_type, []):
                                promotion = promo_type
                                break
                        
                        # Use account-specific company name override if available
                        company_display = get_company_display_name(company, username)
                        
                        all_tours.append({
                            'key': tour_key,
                            'id': row.get('id', ''),
                            'name': row.get('name', 'Unnamed Tour'),
                            'company': company,
                            'company_display': company_display,
                            'price': row.get('price_adult', ''),
                            'enabled': is_enabled,
                            'promotion': promotion,
                            'has_booking_link': has_booking_link
                        })
        except Exception as e:
            print(f"Error loading {csvfile}: {e}")
    
    # Group by company
    companies = {}
    disabled_images_companies = global_settings.get('disabled_images_companies', [])
    for tour in all_tours:
        if tour['company'] not in companies:
            companies[tour['company']] = {
                'name': tour['company_display'],
                'tours': [],
                'images_enabled': tour['company'] not in disabled_images_companies
            }
        companies[tour['company']]['tours'].append(tour)
    
    # Get promotion stats from account settings
    promoted_counts = {
        'popular': len(account_promotions.get('popular', [])),
        'featured': len(account_promotions.get('featured', [])),
        'best_value': len(account_promotions.get('best_value', []))
    }
    
    # Separate companies into: those with enabled tours, and those without
    active_companies = {}  # Companies with at least one enabled tour
    inactive_companies = {}  # Companies with ALL tours disabled
    
    for company_id, company_data in companies.items():
        enabled_tours = [t for t in company_data['tours'] if t['enabled']]
        disabled_tours = [t for t in company_data['tours'] if not t['enabled']]
        
        if enabled_tours:
            # Company has at least one enabled tour - show ALL tours (enabled & disabled)
            active_companies[company_id] = {
                'name': company_data['name'],
                'tours': company_data['tours'],  # ALL tours, not just enabled
                'images_enabled': company_data['images_enabled'],
                'enabled_count': len(enabled_tours),
                'disabled_count': len(disabled_tours)
            }
        else:
            # Company has NO enabled tours - goes to inactive section
            inactive_companies[company_id] = {
                'name': company_data['name'],
                'tours': disabled_tours,
                'images_enabled': company_data['images_enabled'],
                'enabled_count': 0,
                'disabled_count': len(disabled_tours)
            }
    
    # Get the active kiosk account (what's actually displayed on the kiosk)
    kiosk_account = get_active_account()
    is_kiosk_account = (username == kiosk_account) if username else False
    
    # Count total disabled tours for display
    total_disabled = sum(c['disabled_count'] for c in active_companies.values()) + sum(c['disabled_count'] for c in inactive_companies.values())
    
    return render_template('agent_dashboard.html',
                          companies=active_companies,
                          inactive_companies=inactive_companies,
                          settings=account_settings if username else global_settings,
                          tour_overrides=account_tour_overrides,
                          promoted_counts=promoted_counts,
                          disabled_count=total_disabled,
                          total_tours=len(all_tours),
                          company_names=get_company_display_names_for_account(username),
                          version=APP_VERSION,
                          kiosk_account=kiosk_account,
                          is_kiosk_account=is_kiosk_account)

@app.route('/admin/agent/api/toggle-tour', methods=['POST'])
# @agent_required  # Disabled for testing
def toggle_tour_visibility():
    """Toggle a tour's visibility (enabled/disabled) - saves to account settings"""
    data = request.get_json()
    tour_key = data.get('tour_key')
    enabled = data.get('enabled', True)
    
    if not tour_key:
        return jsonify({'error': 'Tour key required'}), 400
    
    # Use account-specific settings
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Apply directly - toggles don't require approval
    account_settings = load_account_settings(username)
    enabled_tours = account_settings.get('enabled_tours', [])
    
    if enabled and tour_key not in enabled_tours:
        enabled_tours.append(tour_key)
    elif not enabled and tour_key in enabled_tours:
        enabled_tours.remove(tour_key)
    
    account_settings['enabled_tours'] = enabled_tours
    save_account_settings(username, account_settings)
    
    # Sync to connected kiosks
    git_sync_changes(f"Toggled tour status: {tour_key}")
    
    return jsonify({'success': True, 'enabled': enabled})

@app.route('/admin/agent/api/set-promotion', methods=['POST'])
# @agent_required  # Disabled for testing
def set_tour_promotion():
    """Set or remove a tour's promotion level - saves to account settings"""
    data = request.get_json()
    tour_key = data.get('tour_key')
    level = data.get('level')  # 'popular', 'featured', 'best_value', or None to remove
    
    if not tour_key:
        return jsonify({'error': 'Tour key required'}), 400
    
    # Use account-specific settings
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Apply directly - promotions don't require approval
    account_settings = load_account_settings(username)
    promoted = account_settings.get('promoted_tours', {'popular': [], 'featured': [], 'best_value': []})
    
    # Ensure all promotion levels exist
    for promo_type in ['popular', 'featured', 'best_value']:
        if promo_type not in promoted:
            promoted[promo_type] = []
    
    # Remove from all promotion levels first
    for promo_level in promoted:
        if tour_key in promoted[promo_level]:
            promoted[promo_level].remove(tour_key)
    
    # Add to new level if specified
    if level and level in promoted:
        promoted[level].append(tour_key)
    
    account_settings['promoted_tours'] = promoted
    save_account_settings(username, account_settings)
    
    # Sync to connected kiosks
    git_sync_changes(f"Updated tour promotion: {tour_key}")
    
    return jsonify({'success': True, 'level': level})

@app.route('/admin/agent/api/bulk-update', methods=['POST'])
# @agent_required  # Disabled for testing
def bulk_update_tours():
    """Bulk enable/disable or promote tours - saves to account settings"""
    data = request.get_json()
    action = data.get('action')  # 'enable_all', 'disable_all', 'clear_promotions'
    company = data.get('company')  # Optional: limit to company
    
    # Use account-specific settings
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    account_settings = load_account_settings(username)
    enabled_tours = account_settings.get('enabled_tours', [])
    
    if action == 'enable_all':
        # Get all tour keys for the company (or all)
        csv_files = get_all_tour_csvs()
        for csvfile in csv_files:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        comp = row.get('company_name', '')
                        if not company or comp == company:
                            tour_key = f"{comp}__{row.get('id', '')}"
                            if tour_key not in enabled_tours:
                                enabled_tours.append(tour_key)
    
    elif action == 'disable_all':
        if company:
            enabled_tours = [t for t in enabled_tours if not t.startswith(company + '__')]
        else:
            enabled_tours = []
    
    elif action == 'clear_promotions':
        promoted = account_settings.get('promoted_tours', {'popular': [], 'featured': [], 'best_value': []})
        if company:
            for level in promoted:
                promoted[level] = [
                    t for t in promoted[level] 
                    if not t.startswith(company + '__')
                ]
        else:
            promoted = {'popular': [], 'featured': [], 'best_value': []}
        account_settings['promoted_tours'] = promoted
    
    account_settings['enabled_tours'] = enabled_tours
    save_account_settings(username, account_settings)
    
    # Sync to connected kiosks
    git_sync_changes(f"Bulk tour update: {action}")
    
    return jsonify({'success': True})

@app.route('/admin/agent/api/toggle-company-images', methods=['POST'])
# @agent_required  # Disabled for testing
def toggle_company_images():
    """Toggle images on/off for a company (legal compliance)"""
    data = request.get_json()
    company = data.get('company')
    enabled = data.get('enabled', True)
    
    if not company:
        return jsonify({'success': False, 'error': 'Company required'}), 400
    
    settings = load_agent_settings()
    disabled_images = settings.get('disabled_images_companies', [])
    
    if enabled:
        # Remove from disabled list
        disabled_images = [c for c in disabled_images if c != company]
    else:
        # Add to disabled list
        if company not in disabled_images:
            disabled_images.append(company)
    
    settings['disabled_images_companies'] = disabled_images
    save_agent_settings(settings)
    
    return jsonify({'success': True, 'images_enabled': enabled})

@app.route('/admin/agent/api/overlay-presets', methods=['GET'])
def get_overlay_presets():
    """Get saved overlay presets for the account"""
    username = session.get('user')
    if not username:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    account_settings = load_account_settings(username)
    presets = account_settings.get('overlay_presets', {})
    
    return jsonify({'success': True, 'presets': presets})

@app.route('/admin/agent/api/overlay-presets', methods=['POST'])
def manage_overlay_presets():
    """Save or delete overlay presets"""
    username = session.get('user')
    if not username:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    action = data.get('action')
    name = data.get('name')
    
    account_settings = load_account_settings(username)
    if 'overlay_presets' not in account_settings:
        account_settings['overlay_presets'] = {}
    
    if action == 'save':
        config = data.get('config', {})
        account_settings['overlay_presets'][name] = config
        save_account_settings(username, account_settings)
        git_sync_changes(f"Saved overlay preset: {name}")
        return jsonify({'success': True, 'message': f'Preset "{name}" saved'})
    
    elif action == 'delete':
        if name in account_settings['overlay_presets']:
            del account_settings['overlay_presets'][name]
            save_account_settings(username, account_settings)
            git_sync_changes(f"Deleted overlay preset: {name}")
            return jsonify({'success': True, 'message': f'Preset "{name}" deleted'})
        else:
            return jsonify({'success': False, 'error': 'Preset not found'})
    
    return jsonify({'success': False, 'error': 'Invalid action'})

@app.route('/admin/agent/api/bulk-apply-overlay-preset', methods=['POST'])
def bulk_apply_overlay_preset():
    """Apply an overlay preset to tours from a specific company that have widgets configured"""
    username = session.get('user')
    if not username:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    preset_name = data.get('preset_name')
    config = data.get('config')
    company = data.get('company')  # Optional - filter by company
    
    if not config:
        return jsonify({'success': False, 'error': 'No preset config provided'})
    
    account_settings = load_account_settings(username)
    tour_overrides = account_settings.get('tour_overrides', {})
    
    updated_count = 0
    
    # Find tours with widgets and apply the preset (optionally filtered by company)
    for tour_key, tour_settings in tour_overrides.items():
        # Check company filter if provided
        if company:
            tour_company = tour_key.split('__')[0] if '__' in tour_key else ''
            if tour_company != company:
                continue
        
        hero_widget = tour_settings.get('hero_widget_html', '')
        if hero_widget and hero_widget.strip():
            # This tour has a widget - apply the preset
            tour_settings['button_overlay'] = {
                'top': config.get('top'),
                'left': config.get('left'),
                'width': config.get('width'),
                'height': config.get('height')
            }
            updated_count += 1
    
    # Save the updated settings
    account_settings['tour_overrides'] = tour_overrides
    save_account_settings(username, account_settings)
    
    # Sync to connected kiosks
    git_sync_changes(f"Bulk applied overlay preset to {updated_count} tours")
    
    company_msg = f' from {company}' if company else ''
    return jsonify({
        'success': True, 
        'message': f'Applied preset to {updated_count} tours{company_msg}',
        'updated_count': updated_count
    })

@app.route('/admin/agent/api/tour-settings/<tour_key>', methods=['GET'])
def get_tour_settings(tour_key):
    """Get per-tour agent settings (booking URLs, price overrides, etc.) - uses account settings"""
    # Use account-specific settings
    username = session.get('user')
    if username:
        account_settings = load_account_settings(username)
        tour_overrides = account_settings.get('tour_overrides', {})
    else:
        # Fallback to global settings if not logged in
        settings = load_agent_settings()
        tour_overrides = settings.get('tour_overrides', {})
    tour_settings = tour_overrides.get(tour_key, {})
    
    # Also get basic tour info
    tours = load_all_tours()
    tour_data = None
    for tour in tours:
        if tour.get('key') == tour_key:
            tour_data = {
                'name': tour.get('name', ''),
                'price': tour.get('price', ''),
                'price_adult': tour.get('price_adult', ''),
                'price_child': tour.get('price_child', ''),
                'price_tiers': tour.get('price_tiers', ''),
                'company': tour.get('company', '')
            }
            break
    
    return jsonify({
        'success': True,
        'tour_key': tour_key,
        'tour_data': tour_data,
        'settings': {
            'booking_button_url': tour_settings.get('booking_button_url', ''),
            'hero_widget_html': tour_settings.get('hero_widget_html', ''),
            'notes': tour_settings.get('notes', ''),
            'button_overlay': tour_settings.get('button_overlay', None)
        }
    })

@app.route('/admin/agent/api/tour-settings/<tour_key>', methods=['POST'])
def save_tour_settings(tour_key):
    """Save per-tour agent settings - saves to account settings (booking URLs, widgets)"""
    data = request.get_json()
    
    # Use account-specific settings
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Apply directly - booking settings don't require approval
    account_settings = load_account_settings(username)
    if 'tour_overrides' not in account_settings:
        account_settings['tour_overrides'] = {}
    
    # Get existing or create new
    tour_settings = account_settings['tour_overrides'].get(tour_key, {})
    
    # Update fields (only if provided)
    if 'booking_button_url' in data:
        tour_settings['booking_button_url'] = data['booking_button_url'].strip()
    if 'hero_widget_html' in data:
        tour_settings['hero_widget_html'] = data['hero_widget_html'].strip()
    if 'notes' in data:
        tour_settings['notes'] = data['notes'].strip()
    if 'button_overlay' in data:
        overlay = data['button_overlay']
        # Validate overlay data
        if overlay and overlay.get('width') and float(overlay.get('width', 0)) > 0:
            tour_settings['button_overlay'] = {
                'top': str(overlay.get('top', 0)),
                'left': str(overlay.get('left', 0)),
                'width': str(overlay.get('width', 0)),
                'height': str(overlay.get('height', 0))
            }
            print(f"[OVERLAY] Saved button overlay for {tour_key}: {tour_settings['button_overlay']}")
        else:
            # Clear overlay if empty/invalid
            if 'button_overlay' in tour_settings:
                del tour_settings['button_overlay']
    
    # Clean up empty settings
    tour_settings = {k: v for k, v in tour_settings.items() if v}
    
    if tour_settings:
        account_settings['tour_overrides'][tour_key] = tour_settings
    elif tour_key in account_settings['tour_overrides']:
        del account_settings['tour_overrides'][tour_key]
    
    save_account_settings(username, account_settings)
    
    # Sync to connected kiosks via git push
    git_sync_changes(f"Updated tour settings: {tour_key}")
    
    return jsonify({'success': True, 'settings': tour_settings})

# ============================================================================
# DESK NOTIFICATION SYSTEM - Alert agents when customers need help booking
# ============================================================================

# Store recent desk booking requests (in-memory, clears on restart)
_desk_notifications = []
_desk_notification_id = 0

@app.route('/api/desk-notification', methods=['POST'])
def create_desk_notification():
    """Called when a customer clicks 'Book' on a tour without a booking link"""
    global _desk_notification_id
    
    data = request.get_json() or {}
    tour_name = data.get('tour_name', 'Unknown Tour')
    tour_key = data.get('tour_key', '')
    
    _desk_notification_id += 1
    notification = {
        'id': _desk_notification_id,
        'tour_name': tour_name,
        'tour_key': tour_key,
        'timestamp': datetime.now().isoformat(),
        'acknowledged': False
    }
    
    _desk_notifications.append(notification)
    
    # Keep only last 50 notifications
    if len(_desk_notifications) > 50:
        _desk_notifications.pop(0)
    
    print(f"🔔 DESK NOTIFICATION: Customer wants to book '{tour_name}'")
    
    return jsonify({'success': True, 'notification_id': _desk_notification_id})

@app.route('/api/desk-notifications', methods=['GET'])
def get_desk_notifications():
    """Get unacknowledged desk notifications for the agent dashboard"""
    # Get last_id parameter to only return new notifications
    last_id = request.args.get('last_id', 0, type=int)
    
    new_notifications = [n for n in _desk_notifications if n['id'] > last_id and not n['acknowledged']]
    
    return jsonify({
        'notifications': new_notifications,
        'count': len(new_notifications)
    })

@app.route('/api/desk-notification/<int:notification_id>/acknowledge', methods=['POST'])
def acknowledge_desk_notification(notification_id):
    """Mark a notification as acknowledged"""
    for n in _desk_notifications:
        if n['id'] == notification_id:
            n['acknowledged'] = True
            break
    
    return jsonify({'success': True})

# ============================================================================
# REMOTE UPDATE SYSTEM
# ============================================================================

import subprocess

@app.route('/health')
def health_check():
    """Simple health check endpoint for monitoring and update restart detection"""
    return jsonify({'status': 'ok', 'version': APP_VERSION})

@app.route('/admin/agent/api/set-device-account', methods=['POST'])
def set_device_account():
    """Set this device to use the logged-in user's account for the kiosk display
    
    This updates instance.json which is gitignored, so it persists through code updates.
    """
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    # Load the user's account settings to get their kiosk settings
    account_settings = load_account_settings(username)
    kiosk_settings = account_settings.get('kiosk_settings', {})
    
    # Update instance.json with this account
    instance_config_file = 'config/instance.json'
    os.makedirs('config', exist_ok=True)
    
    # Load existing config or create new
    if os.path.exists(instance_config_file):
        with open(instance_config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {}
    
    # Update the active account
    old_account = config.get('active_account', 'none')
    config['active_account'] = username
    config['custom_logo'] = kiosk_settings.get('custom_logo', '')
    config['weather_widget_enabled'] = kiosk_settings.get('weather_widget_enabled', True)
    config['default_language'] = kiosk_settings.get('default_language', 'en')
    config['available_languages'] = kiosk_settings.get('available_languages', ['en'])
    config['currency'] = kiosk_settings.get('currency', 'AUD')
    config['last_updated'] = datetime.now().isoformat()
    config['switched_by'] = username
    config['switch_note'] = f'Device switched from {old_account} to {username}'
    
    with open(instance_config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"[DEVICE] Account switched from '{old_account}' to '{username}'")
    
    return jsonify({
        'success': True, 
        'message': f'This device now uses {username}\'s tours',
        'previous_account': old_account,
        'new_account': username
    })

@app.route('/admin/agent/api/check-updates')
def check_for_updates():
    """Check if there are updates available from GitHub"""
    try:
        # Fetch latest from remote
        result = subprocess.run(
            ['git', 'fetch', 'origin'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=os.path.dirname(os.path.abspath(__file__)),
            timeout=30
        )
        
        # Check if we're behind origin/main
        result = subprocess.run(
            ['git', 'rev-list', 'HEAD..origin/main', '--count'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=os.path.dirname(os.path.abspath(__file__)),
            timeout=10
        )
        
        commits_behind = int(result.stdout.strip() or '0')
        
        if commits_behind > 0:
            # Get the list of changes
            changes_result = subprocess.run(
                ['git', 'log', 'HEAD..origin/main', '--oneline', '--no-decorate'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=os.path.dirname(os.path.abspath(__file__)),
                timeout=10
            )
            changes = changes_result.stdout.strip()
            
            return jsonify({
                'updates_available': True,
                'commits_behind': commits_behind,
                'changes': changes
            })
        else:
            return jsonify({
                'updates_available': False,
                'message': 'Already up to date'
            })
            
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout checking for updates'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/agent/api/apply-update', methods=['POST'])
def apply_update():
    """Signal restart for updates - run_kiosk.py wrapper handles the actual restart"""
    try:
        import threading
        
        def do_restart():
            time.sleep(2)  # Give time for response to be sent
            print("[MANUAL-UPDATE] Exiting for restart...")
            os._exit(42)  # Special exit code for "update and restart"
        
        # Start restart in background thread
        threading.Thread(target=do_restart, daemon=True).start()
        
        return jsonify({
            'success': True,
            'message': 'Restarting for update... The kiosk will reload automatically.',
            'note': 'Make sure run_kiosk.py is running as the wrapper'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/agent/api/force-sync', methods=['POST'])
@agent_required
def force_git_sync():
    """Manually trigger git sync and return the result (for debugging)"""
    try:
        username = session.get('user')
        if not username:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        # Check git status
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=os.getcwd(),
            timeout=10
        )
        
        if status_result.returncode != 0:
            return jsonify({
                'success': False,
                'error': 'Not a git repository',
                'details': status_result.stderr
            })
        
        changed_files = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
        
        if not changed_files:
            return jsonify({
                'success': True,
                'message': 'No changes to commit',
                'changed_files': []
            })
        
        # Stage and commit
        subprocess.run(['git', 'add', '-A'], cwd=os.getcwd(), check=True, timeout=10)
        
        commit_msg = f"Manual sync for {username} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        commit_result = subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        
        if commit_result.returncode != 0:
            return jsonify({
                'success': False,
                'error': 'Commit failed',
                'details': commit_result.stderr,
                'stdout': commit_result.stdout
            })
        
        # Push
        auth_url = get_authenticated_remote_url()
        if auth_url:
            push_result = subprocess.run(
                ['git', 'push', auth_url, 'main'],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
        else:
            push_result = subprocess.run(
                ['git', 'push', 'origin', 'main'],
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=60
            )
        
        if push_result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Successfully synced to GitHub',
                'changed_files': [f.strip() for f in changed_files if f.strip()],
                'commit': commit_msg
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Push failed',
                'details': push_result.stderr,
                'stdout': push_result.stdout
            })
            
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

# ============================================================================
# OPERATOR MODE ROUTES
# ============================================================================

@app.route('/admin/operator')
# @operator_required  # Disabled for testing
def operator_dashboard():
    """Operator dashboard - view and edit own company's tours"""
    user_company = session.get('company')
    is_agent = session.get('role') == 'agent'
    
    # For testing without login - treat as agent
    if not session.get('user'):
        is_agent = True
    
    # If agent (or testing mode), show company selector
    if is_agent or not user_company:
        selected_company = request.args.get('company')
        if not selected_company:
            # Show company list
            companies = list(COMPANY_DISPLAY_NAMES.items())
            return render_template('operator_select_company.html', companies=companies)
        user_company = selected_company
    
    # Load tours for this company
    csv_file = find_company_csv(user_company)
    tours = []
    
    if csv_file and os.path.exists(csv_file):
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                tour_key = f"{user_company}__{row.get('id', '')}"
                tours.append({
                    'key': tour_key,
                    'id': row.get('id', ''),
                    'name': row.get('name', 'Unnamed Tour'),
                    'price': row.get('price_adult', ''),
                    'duration': row.get('duration', ''),
                    'description': row.get('description', '')[:150] + '...' if row.get('description', '') else '',
                    'has_images': bool(row.get('image_url')),
                    'csv_file': csv_file
                })
    
    return render_template('operator_dashboard.html',
                          company=user_company,
                          company_display=COMPANY_DISPLAY_NAMES.get(user_company, user_company),
                          tours=tours,
                          is_agent=is_agent)

@app.route('/admin/operator/edit/<tour_key>')
# @operator_required  # Disabled for testing
def operator_edit_tour(tour_key):
    """Edit a specific tour (operator can only edit their own)"""
    try:
        company, tid = tour_key.split('__', 1)
    except ValueError:
        return render_template('access_denied.html', message="Invalid tour"), 404
    
    # Check permissions (disabled for testing)
    # user_company = session.get('company')
    # is_agent = session.get('role') == 'agent'
    # if not is_agent and user_company != company:
    #     return render_template('access_denied.html', message="You can only edit your own company's tours"), 403
    
    # Redirect to the existing tour editor with this tour pre-selected
    return redirect(url_for('tour_editor') + f'?select={tour_key}')

@app.route('/')
def index():
    # Check for referral from QR code scan (allows public access)
    referral_account = get_referral_account()
    
    # Check for preview mode (for logged-in admins testing)
    preview_account = request.args.get('preview')
    
    # Get the kiosk instance account (from instance.json - persists through restarts)
    kiosk_account = get_active_account()
    
    # Determine which account to use for filtering tours
    # Priority: 1) preview mode, 2) referral from QR, 3) kiosk instance, 4) demo mode
    is_demo_mode = False
    if preview_account:
        active_account = preview_account
    elif referral_account:
        active_account = referral_account
    elif kiosk_account:
        # Kiosk has an account set in instance.json - use it!
        active_account = kiosk_account
        print(f"[INDEX] Using kiosk account from instance.json: {kiosk_account}")
    elif 'user' in session:
        # Logged in user viewing the kiosk
        active_account = session.get('user')
    else:
        # No account set anywhere - use demo mode for public visitors
        active_account = 'awda'
        is_demo_mode = True
        print(f"[INDEX] Demo mode - no kiosk account set, using 'awda' for public access")
    
    if preview_account:
        session['preview_account'] = preview_account
    else:
        session.pop('preview_account', None)
    
    # Track where the user came from
    is_web_visitor = referral_account is not None
    if is_web_visitor:
        print(f"[INDEX] Web visitor from referral: {referral_account}")
    
    # Get language from query parameter or session (default: 'en')
    language = request.args.get('lang', 'en')
    tours = load_all_tours(language, preview_account=active_account)
    random.shuffle(tours)
    initial_tours = tours[:12]
    
    # Load images lazily for initial tours only (with account-specific hidden images filtered)
    print(f"[INDEX] Loading images for {len(initial_tours)} initial tours (account: {active_account})")
    for tour in initial_tours:
        thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=5, account_username=active_account)
        tour['thumbnail'] = thumb
        tour['gallery'] = gallery
        tour['uses_placeholder_images'] = uses_placeholder
    
    shown_keys = [t['key'] for t in initial_tours]
    
    # Load shop config - from session if logged in, otherwise default
    shop_config = session.get('shop_config') or load_shop_config(session.get('company'))
    
    # Load Hero booking platform settings (use active account)
    hero_booking = get_hero_booking_settings(preview_account=active_account)
    
    # Get custom logo from the account being viewed
    custom_logo = get_kiosk_custom_logo(preview_account=active_account)
    
    # Get kiosk settings (microphone enabled, etc.)
    kiosk_settings = get_kiosk_settings(preview_account=active_account)
    
    # Pass mode indicators to template
    preview_mode = preview_account is not None
    
    return render_template('index.html', 
                           tours=initial_tours, 
                           shown_keys=shown_keys, 
                           current_language=language,
                           shop_config=shop_config,
                           hero_booking=hero_booking,
                           custom_logo=custom_logo,
                           kiosk_settings=kiosk_settings,
                           preview_mode=preview_mode,
                           preview_account=preview_account,
                           referral_account=referral_account,
                           active_account=active_account,
                           is_web_visitor=is_web_visitor,
                           is_demo_mode=is_demo_mode,
                           newcomer_images=get_newcomer_images())

@app.route('/api/semantic-search')
def api_semantic_search():
    """API endpoint to test semantic search directly
    
    Usage: /api/semantic-search?q=family+snorkeling+adventure&n=5
    """
    query = request.args.get('q', '')
    n_results = int(request.args.get('n', '5'))
    min_sim = float(request.args.get('min_sim', '0.10'))
    language = request.args.get('lang', 'en')
    
    if not query:
        return jsonify({
            'error': 'Missing query parameter ?q=',
            'usage': '/api/semantic-search?q=family+snorkeling&n=5&min_sim=0.10'
        })
    
    if not CHROMA_AVAILABLE:
        return jsonify({
            'error': 'ChromaDB not available',
            'message': 'Run: pip install chromadb && python scripts/index_tours_rag.py'
        })
    
    # Get semantic matches
    matches = semantic_search_tours(query, n_results=n_results, min_similarity=min_sim)
    
    # Optionally get full tour data
    all_tours = load_all_tours(language)
    full_results = get_tours_by_semantic_search(query, all_tours, max_results=n_results, min_similarity=min_sim)
    
    return jsonify({
        'query': query,
        'n_results': len(matches),
        'matches': [
            {
                'key': m['key'],
                'name': m['name'],
                'company': m['company_name'],
                'similarity': f"{m['similarity']:.1%}",
                'similarity_raw': round(m['similarity'], 4),
                'duration': m.get('duration_category', ''),
                'price': m.get('price_adult', ''),
            }
            for m in matches
        ],
        'full_tours': [
            {
                'key': t.get('key', ''),
                'name': t.get('name', ''),
                'company': t.get('company_name', ''),
                'similarity': f"{t.get('similarity_score', 0):.1%}",
                'description': t.get('description', '')[:200] + '...',
            }
            for t in full_results[:3]
        ]
    })

@app.route('/api/tours')
def api_tours():
    """API endpoint to fetch filtered tours for video question flow"""
    language = request.args.get('lang', 'en')
    
    # Get the active account for filtering hidden images
    active_account = get_active_account()
    
    # Get filter parameters
    duration = request.args.get('duration', '')
    family_friendly = request.args.get('family_friendly', '')
    activities = request.args.getlist('activities')
    
    print(f"[API] ========== TOUR FILTERING ==========")
    print(f"[API] Duration filter: '{duration}'")
    print(f"[API] Family friendly filter: '{family_friendly}'")
    print(f"[API] Activities filter: {activities}")
    print(f"[API] Active account: {active_account}")
    
    # Load all tours
    tours = load_all_tours(language, preview_account=active_account)
    print(f"[API] Total tours loaded: {len(tours)}")
    
    filtered_tours = []
    duration_filtered = 0
    family_filtered = 0
    activities_filtered = 0
    
    for tour in tours:
        # Duration filter
        if duration:
            tour_duration = tour.get('duration_category', '').lower()
            tour_name = tour.get('name', '').lower()
            
            if duration == 'half_day' and tour_duration not in ['half_day', 'half day']:
                duration_filtered += 1
                continue
            elif duration == 'full_day':
                # Include full_day tours, OR unknown duration tours with "day tour" in name
                is_full_day = tour_duration in ['full_day', 'full day']
                is_likely_full_day = tour_duration in ['unknown', ''] and 'day tour' in tour_name
                if not is_full_day and not is_likely_full_day:
                    duration_filtered += 1
                    continue
            elif duration == 'multi_day' and tour_duration not in ['multi_day', 'multi day', 'multiday']:
                duration_filtered += 1
                continue
        
        # Family friendly filter
        # Only filter if "Family with Kids" is selected (true)
        # "Adults Only" (adults_only) doesn't filter anything
        if family_friendly and family_friendly == 'true':
            is_family = str(tour.get('family_friendly', '')).lower() in ['true', 'yes', '1']
            if not is_family:
                family_filtered += 1
                continue
        
        # Activities filter - more lenient matching with expanded keywords
        if activities and len(activities) > 0:
            tour_activities = tour.get('activities', '').lower()
            tour_keywords = tour.get('keywords', '').lower()
            tour_name = tour.get('name', '').lower()
            tour_description = tour.get('description', '').lower()
            
            # Combine all searchable fields
            searchable_text = f"{tour_activities} {tour_keywords} {tour_name} {tour_description}"
            
            has_match = False
            for activity in activities:
                if not activity:
                    continue
                    
                # Convert underscore to space for matching
                activity_search = activity.lower().replace('_', ' ')
                
                # Expanded keywords for swimming category
                if activity == 'swimming':
                    swimming_keywords = [
                        'swimming', 'swim', 'snorkeling', 'snorkel', 'diving', 'dive', 
                        'scuba', 'freedive', 'underwater', 'water activities', 
                        'overnight sailing', 'liveaboard', 'sea', 'ocean', 'reef',
                        'marine', 'coral', 'beach', 'lagoon', 'bay', 'sailing overnight'
                    ]
                    if any(keyword in searchable_text for keyword in swimming_keywords):
                        has_match = True
                        break
                
                # Try various matching strategies for other activities
                if (activity_search in searchable_text or
                    activity.replace('_', '') in searchable_text or
                    any(word in searchable_text for word in activity_search.split())):
                    has_match = True
                    break
            
            if not has_match:
                activities_filtered += 1
                continue
        
        filtered_tours.append(tour)
    
    print(f"[API] ========== FILTERING RESULTS ==========")
    print(f"[API] Filtered by duration: {duration_filtered}")
    print(f"[API] Filtered by family: {family_filtered}")
    print(f"[API] Filtered by activities: {activities_filtered}")
    print(f"[API] Final matching tours: {len(filtered_tours)}")
    print(f"[API] ========================================")
    
    # Randomize tours first, then sort by promotion level
    # This ensures promoted tours stay at top but non-promoted tours are randomized
    random.shuffle(filtered_tours)
    
    # Sort filtered tours: promoted tours first, then by promotion level
    # Using stable sort preserves random order within same promotion level
    promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
    filtered_tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
    
    # Add gallery, includes, and company_name to each tour
    # Load images lazily only for tours we're returning (with account-specific hidden images filtered)
    result_tours = []
    print(f"[API] Loading images for {len(filtered_tours)} filtered tours...")
    for tour in filtered_tours:
        # Load images lazily for this tour
        thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=5, account_username=active_account)
        
        # Parse video URLs if present
        video_urls = tour.get('video_urls', '')
        if video_urls and isinstance(video_urls, str):
            video_urls = [v.strip() for v in video_urls.split(',') if v.strip()]
        else:
            video_urls = []
        
        tour_data = {
            'key': tour['key'],
            'name': tour['name'],
            'company': tour.get('company', ''),
            'company_name': tour.get('company_name', tour.get('company', '')),
            'image': tour.get('image', ''),
            'thumbnail_url': thumb or '',
            'thumbnail': thumb or '',
            'duration': tour.get('duration', ''),
            'price': tour.get('price', 0),
            'price_adult': tour.get('price_adult', ''),
            'rating': tour.get('rating', 0),
            'includes': tour.get('includes', ''),
            'highlights': tour.get('highlights', ''),
            'gallery': gallery,
            'video_urls': video_urls,  # Video URLs for embedded playback
            'promotion': tour.get('promotion'),  # Include promotion status
            'is_promoted': tour.get('is_promoted', False),
            'review_rating': tour.get('review_rating', 0),
            'review_count': tour.get('review_count', 0),
            'uses_placeholder_images': uses_placeholder,
            'departure_location': tour.get('departure_location', '')
        }
        result_tours.append(tour_data)
    
    return jsonify({'tours': result_tours})

@app.route('/tour/<key>')
def tour_page(key):
    """Load home page but with tour parameter - JavaScript will auto-open tour in modal"""
    language = request.args.get('lang', 'en')
    mode = request.args.get('mode', 'browse')  # Default to browse all tours mode
    
    # Check for referral from QR code (allows public access)
    referral_account = get_referral_account()
    ref = request.args.get('ref')
    tracking_id = request.args.get('tid')
    timestamp = request.args.get('t')
    
    # Determine which account to use for filtering tours
    # Fall back to 'awda' demo account if nothing else works
    active_account = referral_account or get_active_account() or 'awda'
    
    # If ref was provided but account doesn't exist, still use it for tracking but load awda tours
    if ref and not referral_account:
        print(f"[TOUR] Referral '{ref}' not found, using 'awda' as fallback")
    
    # Log QR code visit if tracking parameters are present
    if ref and ref != 'qr' and tracking_id:
        try:
            session_id = request.cookies.get('analytics_session_id') or str(uuid.uuid4())
            
            tours = load_all_tours(language, preview_account=active_account)
            tour_data = next((t for t in tours if t.get('key') == key), None)
            tour_name = tour_data.get('name', key) if tour_data else key
            
            log_analytics_event(session_id, 'qr_tour_visit', {
                'tour_key': key,
                'tour_name': tour_name,
                'tracking_id': tracking_id,
                'timestamp': timestamp,
                'language': language,
                'referrer': ref,  # Now contains the shop/account name
                'referral_account': referral_account
            })
            print(f"📱 QR visit tracked: {tracking_id} → {key} (ref: {ref})")
        except Exception as e:
            print(f"[!] Failed to log QR visit: {e}")
    
    # Load tours filtered by the referral account
    tours = load_all_tours(language, preview_account=active_account)
    random.shuffle(tours)
    initial_tours = tours[:12]
    
    # Load images lazily for initial tours only (with account-specific hidden images filtered)
    for tour in initial_tours:
        thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=5, account_username=active_account)
        tour['thumbnail'] = thumb
        tour['gallery'] = gallery
        tour['uses_placeholder_images'] = uses_placeholder
    
    shown_keys = [t['key'] for t in initial_tours]
    
    # Pass tracking info to frontend
    qr_tracking = {
        'ref': ref,
        'tracking_id': tracking_id,
        'timestamp': timestamp,
        'referral_account': referral_account
    } if tracking_id else None
    
    # Get shop branding from the referral account
    custom_logo = get_kiosk_custom_logo(preview_account=active_account)
    hero_booking = get_hero_booking_settings(preview_account=active_account)
    kiosk_settings = get_kiosk_settings(preview_account=active_account)
    shop_config = load_shop_config(None)  # Load default shop config
    
    # Track if this is a web visitor from QR
    is_web_visitor = referral_account is not None
    
    response = make_response(render_template('index.html', 
                          tours=initial_tours, 
                          shown_keys=shown_keys, 
                          current_language=language, 
                          tour_to_open=key,
                          tour_open_mode=mode,  # Pass mode to frontend
                          qr_tracking=qr_tracking,
                          custom_logo=custom_logo,
                          hero_booking=hero_booking,
                          kiosk_settings=kiosk_settings,
                          shop_config=shop_config,
                          referral_account=referral_account,
                          active_account=active_account,
                          is_web_visitor=is_web_visitor,
                          newcomer_images=get_newcomer_images()))
    
    # Set referral cookie so subsequent page loads use the same account
    if ref and ref != 'qr':
        response.set_cookie('filtour_ref', ref, max_age=7*24*60*60, httponly=False, samesite='Lax')  # 7 days
    
    return response
    
    # Old standalone page code removed
    company, tid = key.split('__', 1)
    csv_pattern = f'data/{company}/{language}/*_with_media.csv'
    csv_files = glob.glob(csv_pattern)
    
    # Fallback to root directory if language-specific file doesn't exist
    if not csv_files:
        csv_files = glob.glob(f'tours_{company}_cleaned_with_media.csv')
    
    tour_data = None
    for csvfile in csv_files:
        try:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['company_name'] == company and row['id'] == tid:
                            # Build gallery from image_urls
                            image_urls = []
                            thumb = find_thumbnail(company, tid, row.get('name', ''))
                            if row.get('image_urls'):
                                for img in row['image_urls'].split(','):
                                    img_path = img.strip()
                                    if not img_path:
                                        continue
                                    if os.path.exists(img_path):
                                        img_url = '/' + img_path
                                        if img_url != thumb:
                                            image_urls.append(img_url)
                            gallery = [thumb] + image_urls if thumb else image_urls
                            
                            # Load review data
                            review_data = load_reviews(company, tid)
                            
                            tour_data = {
                                'key': key,
                                'name': row.get('name', ''),
                                'company': COMPANY_DISPLAY_NAMES.get(row.get('company_name', ''), row.get('company_name', '').title()),
                                'company_name': row.get('company_name', ''),
                                'summary': row.get('summary', ''),
                                'description': row.get('description', ''),
                                'price_adult': row.get('price_adult', ''),
                                'price_child': row.get('price_child', ''),
                                'duration': row.get('duration', ''),
                                'departure_location': row.get('departure_location', ''),
                                'departure_times': row.get('departure_times', ''),
                                'includes': row.get('includes', ''),
                                'highlights': row.get('highlights', ''),
                                'itinerary': row.get('itinerary', ''),
                                'menu': row.get('menu', ''),
                                'ideal_for': row.get('ideal_for', ''),
                                'age_requirements': row.get('age_requirements', ''),
                                'price_tiers': row.get('price_tiers', ''),
                                'keywords': row.get('keywords', ''),
                                'duration_hours': row.get('duration_hours', ''),
                                'link_booking': row.get('link_booking', ''),
                                'link_more_info': row.get('link_more_info', ''),
                                'gallery': gallery,
                                'thumbnail': thumb or '/static/placeholder.jpg',
                                'important_information': row.get('important_information', ''),
                                'what_to_bring': row.get('what_to_bring', ''),
                                'whats_extra': row.get('whats_extra', ''),
                                'cancellation_policy': row.get('cancellation_policy', ''),
                                'reviews': review_data if review_data else {
                                    'reviews': [],
                                    'overall_rating': 0,
                                    'review_count': 0,
                                    'source': None,
                                    'source_url': None
                                }
                            }
                            break
        except Exception as e:
            print(f"Error processing {csvfile}: {e}")
            continue
        
        if tour_data:
            break
    
    if not tour_data:
        return "Tour not found", 404
    
    # Get the base URL for QR code and sharing - use production domain
    if 'localhost' in request.host or '127.0.0.1' in request.host:
        base_url = request.url_root.rstrip('/')
    else:
        base_url = 'https://www.filtour.com'
    
    tour_url = f"{base_url}/tour/{key}?lang={language}"
    
    return render_template('tour_detail.html', tour=tour_data, tour_url=tour_url, current_language=language)

@app.route('/api/generate-tour-qr/<key>')
def generate_tour_qr(key):
    """Generate QR code for a specific tour with tracking and referral"""
    try:
        # ALWAYS use production domain for QR codes - users scan with phones
        base_url = 'https://filtour.com'
        
        language = request.args.get('lang', 'en')
        
        # Get the kiosk's account for referral tracking
        kiosk_account = get_active_account()
        
        # Generate unique tracking ID for this QR code scan
        tracking_id = str(uuid.uuid4())[:8]  # Short unique ID
        timestamp = int(time.time())
        
        # Add tracking parameters to URL including the shop referral
        # mode=browse ensures the tour opens in Browse All Tours mode
        tour_url = f"{base_url}/tour/{key}?lang={language}&ref={kiosk_account}&mode=browse&tid={tracking_id}&t={timestamp}"
        print(f"[QR] Generated tour QR with referral: {kiosk_account}")
        
        # Log QR code generation for analytics
        try:
            # Get session ID if available
            session_id = request.headers.get('X-Session-ID') or request.args.get('session_id')
            if session_id:
                log_analytics_event(session_id, 'qr_code_generated', {
                    'tour_key': key,
                    'tracking_id': tracking_id,
                    'language': language,
                    'timestamp': timestamp
                })
        except Exception as e:
            print(f"[!] Failed to log QR generation: {e}")
        
        print(f"ðŸ“± Generating QR code for: {tour_url} (tracking: {tracking_id})")
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(tour_url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
        
    except Exception as e:
        print(f"[ERR] Error generating tour QR code: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/voice-test')
def voice_test():
    """Voice chat test page"""
    return render_template('voice_test.html')

@app.route('/voice-selector')
def voice_selector():
    """Voice selector - choose from available voices"""
    return render_template('voice_selector.html')

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    """ElevenLabs Text-to-Speech API endpoint"""
    try:
        from elevenlabs_tts import synthesize_speech, is_configured
        
        # Check if ElevenLabs is configured
        if not is_configured():
            return jsonify({
                'success': False,
                'error': 'ElevenLabs not configured'
            }), 500
        
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'en')
        gender = data.get('gender', 'default')
        
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'}), 400
        
        # Synthesize speech
        audio_data = synthesize_speech(text, language, gender)
        
        if audio_data:
            # Return audio as MP3
            from flask import send_file
            from io import BytesIO
            
            audio_io = BytesIO(audio_data)
            audio_io.seek(0)
            
            return send_file(
                audio_io,
                mimetype='audio/mpeg',
                as_attachment=False,
                download_name='speech.mp3'
            )
        else:
            return jsonify({
                'success': False,
                'error': 'Speech synthesis failed'
            }), 500
            
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'ElevenLabs module not found'
        }), 500
    except Exception as e:
        print(f"TTS Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def apply_filters(tours, criteria, user_message_context=None, conversation_history=None):
    """Helper function to apply filter criteria to a list of tours"""
    filtered_tours = tours
    # Build user message context from current message + conversation history
    user_msg_lower = (user_message_context or '').lower() if user_message_context else ''
    
    # Also check conversation history for context
    if conversation_history:
        for msg in conversation_history[-5:]:  # Check last 5 messages
            if msg.get('role') == 'user':
                msg_text = msg.get('content', '').lower()
                # Preserve any specific request context from history
                if any(word in msg_text for word in ['jet ski', 'jetski', 'helicopter', 'scenic flight', 'speed boat']):
                    user_msg_lower = msg_text
                    break
    
    # Apply filters based on criteria dict
    if criteria.get('company'):
        filtered_tours = [t for t in filtered_tours if t['company'] == criteria['company']]
    
    if criteria.get('duration'):
        filtered_tours = [t for t in filtered_tours if t['duration_category'] == criteria['duration']]
    
    if criteria.get('price'):
        # Price filter now works as maximum price limit (not exact category match)
        # Budget = up to $100, Mid-range = up to $250, Premium = up to $500, Luxury = any price
        price_category = criteria['price']
        price_maximums = {
            'budget': 100,
            'mid_range': 250,
            'premium': 500,
            'luxury': float('inf')  # No limit for luxury
        }
        
        max_price = price_maximums.get(price_category, float('inf'))
        
        def get_tour_price(tour):
            """Extract numeric price from tour's price_adult field"""
            price_str = tour.get('price_adult', '')
            if not price_str or price_str == 'N/A' or price_str == 'Contact for price':
                return float('inf')  # If no price, treat as expensive (don't show in budget filters)
            
            # Remove currency symbols and common prefixes
            price_str = str(price_str).replace('A$', '').replace('$', '').replace(',', '').strip()
            
            # Handle "From XXX" or "From: XXX" format
            if 'from' in price_str.lower():
                price_str = price_str.lower().replace('from', '').replace(':', '').strip()
            
            # Extract first number (the starting/minimum price)
            numbers = re.findall(r'\d+', price_str)
            if numbers:
                return int(numbers[0])
            
            return float('inf')  # If can't parse, treat as expensive
        
        filtered_tours = [t for t in filtered_tours if get_tour_price(t) <= max_price]
    
    if criteria.get('activity'):
        selected_activities = criteria['activity']
        
        # Handle both single value and list (for multi-select with OR logic)
        if isinstance(selected_activities, str):
            selected_activities = [selected_activities]
        
            print(f"   Filtering by activities: {selected_activities}")
        
        # Get keywords if this is a direct keyword search
        search_keywords = criteria.get('keywords', [])
        
        # OR logic: Show tours that match ANY of the selected activities
        def tour_matches_any_activity(tour):
            # Build searchable text for text-based matching (includes translated names)
            search_text = f"{tour.get('name', '')} {tour.get('description', '')} {tour.get('highlights', '')} {tour.get('includes', '')}".lower()
            
            for selected_activity in selected_activities:
                # SIMPLE KEYWORD SEARCH: If user asked for something specific, find it directly
                if selected_activity == 'keyword_search' and search_keywords:
                    # Just search for the keywords in tour text - simple and direct
                    return any(keyword in search_text for keyword in search_keywords)
                
                # For other activities, check activity_type array first
                if selected_activity in tour.get('activity_type', []):
                    return True
                
                # Handle activity filtering with hierarchical relationships and text matching
                if selected_activity == 'island_tours':
                    # Island Tours is broad - include island_tours AND whitehaven_beach
                    if 'island_tours' in tour['activity_type'] or 'whitehaven_beach' in tour['activity_type']:
                        return True
                
                # Additional text-based matching for activities not in activity_type
                # MULTI-LANGUAGE KEYWORDS for each activity type
                if selected_activity == 'diving':
                    # ONLY true scuba diving tours - multi-language
                    diving_words = ['scuba', 'dive', 'diving', 'certified dive', 'intro dive', 
                                    'ãƒ€ã‚¤ãƒ“ãƒ³ã‚°', 'ã‚¹ã‚­ãƒ¥ãƒ¼ãƒ',  # Japanese
                                    'æ½œæ°´', 'æ°´è‚º',  # Chinese
                                    'tauchen', 'plongÃ©e', 'buceo']  # German, French, Spanish
                    if any(word in search_text for word in diving_words):
                        return True
                elif selected_activity == 'snorkeling':
                    # Tours focused on snorkeling (not diving)
                    snorkel_words = ['snorkel', 'ã‚·ãƒ¥ãƒŽãƒ¼ã‚±ãƒ«', 'ã‚·ãƒ¥ãƒŽãƒ¼ã‚±ãƒªãƒ³ã‚°', 'æµ®æ½œ', 'schnorcheln', 'esnÃ³rquel']
                    dive_words_check = ['dive', 'diving', 'ãƒ€ã‚¤ãƒ“ãƒ³ã‚°', 'æ½œæ°´']
                    name_lower = tour.get('name', '').lower()
                    if any(word in search_text for word in snorkel_words):
                        if not any(word in name_lower for word in dive_words_check):
                            return True
                elif selected_activity == 'sailing':
                    sailing_words = ['sail', 'sailing', 'cruise', 'yacht', 'catamaran',
                                     'ãƒ¨ãƒƒãƒˆ', 'ã‚¯ãƒ«ãƒ¼ã‚º', 'ã‚»ãƒ¼ãƒªãƒ³ã‚°',  # Japanese
                                     'å¸†èˆ¹', 'æ¸¸èˆ¹', 'æ¸¸è½®',  # Chinese
                                     'segeln', 'voile', 'vela']  # German, French, Spanish
                    if any(word in search_text for word in sailing_words):
                        return True
                elif selected_activity == 'swimming':
                    swim_words = ['swim', 'beach', 'whitehaven', 'water', 'ãƒ“ãƒ¼ãƒ', 'æµ·æ»©', 'strand', 'plage', 'playa']
                    if any(word in search_text for word in swim_words):
                        return True
                elif selected_activity == 'scenic_views':
                    scenic_words = ['scenic', 'view', 'helicopter', 'flight', 'aerial',
                                    'éŠè¦§', 'æ™¯è‰²', 'ãƒ˜ãƒªã‚³ãƒ—ã‚¿ãƒ¼',  # Japanese
                                    'ç›´å‡æœº', 'é£Žæ™¯',  # Chinese
                                    'rundflug', 'panoramique', 'escÃ©nico']  # German, French, Spanish
                    if any(word in search_text for word in scenic_words):
                        return True
                elif selected_activity == 'great_barrier_reef':
                    # General reef tours (includes snorkeling and diving)
                    reef_words = ['reef', 'ãƒªãƒ¼ãƒ•', 'ã‚µãƒ³ã‚´', 'ã‚°ãƒ¬ãƒ¼ãƒˆãƒãƒªã‚¢', 'çŠç‘š', 'å¤§å ¡ç¤', 'riff', 'rÃ©cif', 'arrecife']
                    if any(word in search_text for word in reef_words):
                        return True
                elif selected_activity == 'whitehaven_beach':
                    whitehaven_words = ['whitehaven', 'ãƒ›ãƒ¯ã‚¤ãƒˆãƒ˜ãƒ–ãƒ³', 'ç™½å¤©å ‚', 'ç™½æ²™']
                    if any(word in search_text for word in whitehaven_words):
                        return True
                # keyword_search is handled at the top of this function
                        
            return False
        
        filtered_tours = [t for t in filtered_tours if tour_matches_any_activity(t)]
        print(f"   After activity filter: {len(filtered_tours)} tours")
    
    # Family filter logic:
    # - "Family with Kids" (family=True) â†’ Only show family-friendly tours
    # - "Adults Only" (family=False/'adults_only') â†’ Show ALL tours (adults can go anywhere)
    if criteria.get('family') == True:
        filtered_tours = [t for t in filtered_tours if t['family_friendly']]
    # Note: When family=False or 'adults_only', we don't filter - adults can go on any tour
    
    if criteria.get('meals') == True:
        filtered_tours = [t for t in filtered_tours if t['meals_included']]
    
    if criteria.get('equipment') == True:
        filtered_tours = [t for t in filtered_tours if t['equipment_included']]
    
    return filtered_tours

@app.route('/filter-tours')
def filter_tours():
    """New endpoint for filtering tours"""
    # Get filter parameters
    language = request.args.get('lang', 'en')
    duration = request.args.get('duration', '')
    price = request.args.get('price', '')
    activities = request.args.getlist('activity')  # [OK] Get ALL selected activities
    family = request.args.get('family', '')
    meals = request.args.get('meals', '')
    equipment = request.args.get('equipment', '')
    company = request.args.get('company', '')
    
    print(f"Filter request: activities={activities}, duration={duration}, price={price}, family={family}, meals={meals}, equipment={equipment}")
    
    # Get referral account for filtering (if user came from QR code)
    referral_account = get_referral_account()
    active_account = referral_account or get_active_account()
    
    # Load all tours in the specified language (filtered by account)
    tours = load_all_tours(language, preview_account=active_account)
    
    # Build criteria dict
    criteria = {}
    if company: criteria['company'] = company
    if duration: criteria['duration'] = duration
    if price: criteria['price'] = price
    if activities: criteria['activity'] = activities  # Pass as list for OR logic
    # Family filter: only apply when "Family with Kids" (true) is selected
    # "Adults Only" means show all tours - adults can go anywhere
    if family and family == 'true': 
        criteria['family'] = True
    if meals: criteria['meals'] = (meals == 'true')
    if equipment: criteria['equipment'] = (equipment == 'true')
    
    # Apply filters using helper function
    filtered_tours = apply_filters(tours, criteria)
    
    # Sort: promoted tours first, then by promotion level
    promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
    filtered_tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
    
    # Check if this is for the map (needs all tours, no limit)
    for_map = request.args.get('for_map', '')
    
    # Sort results (no random shuffle - causes pagination issues!)
    if for_map == 'true':
        # Return all tours for map view (no limit)
        limited_tours = filtered_tours
    else:
        # Sort non-promoted tours alphabetically for consistency
        promoted = [t for t in filtered_tours if t.get('promotion')]
        non_promoted = [t for t in filtered_tours if not t.get('promotion')]
        non_promoted.sort(key=lambda t: t.get('name', '').lower())  # Stable alphabetical sort
        limited_tours = promoted + non_promoted
    
    # Load images for each tour (lazy loading, with account-specific hidden images filtered)
    for tour in limited_tours:
        if not tour.get('thumbnail'):
            thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=1, account_username=active_account)
            tour['thumbnail'] = thumb
            tour['gallery'] = gallery
            tour['uses_placeholder_images'] = uses_placeholder
    
    return jsonify({
        'tours': limited_tours,
        'total_found': len(filtered_tours)
    })

# Old basic chat removed - replaced with improved AI chat below (line 785)

@app.route('/more-tours')
def more_tours():
    language = request.args.get('lang', 'en')
    count = int(request.args.get('count', 12))
    exclude_raw = request.args.get('exclude', '')
    exclude_keys = set(exclude_raw.split(',')) if exclude_raw else set()
    # Remove empty string from exclude set if present
    exclude_keys.discard('')
    
    # Get referral account for filtering (if user came from QR code)
    referral_account = get_referral_account()
    active_account = referral_account or get_active_account()
    
    tours = load_all_tours(language, preview_account=active_account)
    total_count = len(tours)  # Total available tours
    
    # Sort ALL tours first (before exclusion) for consistent ordering
    promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
    promoted = [t for t in tours if t.get('promotion')]
    non_promoted = [t for t in tours if not t.get('promotion')]
    
    promoted.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
    non_promoted.sort(key=lambda t: t.get('name', '').lower())
    sorted_tours = promoted + non_promoted
    
    # Select tours that aren't already loaded (use exclude list, not offset)
    # This is simpler and more reliable than offset-based pagination
    selected = []
    for tour in sorted_tours:
        if tour['key'] in exclude_keys:
            continue  # Skip already-loaded tours
        if len(selected) >= count:
            break
        selected.append(tour)
    
    print(f"[MORE-TOURS] Total: {total_count}, Excluded: {len(exclude_keys)}, Selected: {len(selected)}")
    
    # Load images for each selected tour (lazy loading, with account-specific hidden images filtered)
    for tour in selected:
        if not tour.get('thumbnail'):
            thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=1, account_username=active_account)
            tour['thumbnail'] = thumb
            tour['gallery'] = gallery
            tour['uses_placeholder_images'] = uses_placeholder
    
    return jsonify(selected)

@app.route('/tour-detail/<key>')
def tour_detail(key):
    # key is company__id
    language = request.args.get('lang', 'en')
    company, tid = key.split('__', 1)
    # Load from language-specific CSV
    csv_pattern = f'data/{company}/{language}/*_with_media.csv'
    csv_files = glob.glob(csv_pattern)
    
    # Fallback to root directory if language-specific file doesn't exist
    if not csv_files:
        csv_files = glob.glob(f'tours_{company}_cleaned_with_media.csv')
    
    for csvfile in csv_files:
        try:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['company_name'] == company and row['id'] == tid:
                            # Check if images are enabled for this company
                            images_enabled = are_company_images_enabled(company)
                            
                            if images_enabled:
                                # Build gallery from image_urls, put thumbnail first if present
                                # Supports HYBRID: local paths AND remote URLs (http/https)
                                image_urls = []
                                thumb = find_thumbnail(company, tid, row.get('name', ''))
                                if row.get('image_urls'):
                                    for img in row['image_urls'].split(','):
                                        img_path = img.strip()
                                        if not img_path:
                                            continue
                                        # Normalize URL - supports both local and remote
                                        img_url = normalize_image_url(img_path)
                                        # For local paths, check if file exists
                                        if img_url.startswith('/') and not img_url.startswith('//'):
                                            local_path = img_url.lstrip('/')
                                            if os.path.exists(local_path) and img_url != thumb:
                                                image_urls.append(img_url)
                                        elif img_url.startswith('http'):
                                            # Remote URL - include without checking
                                            image_urls.append(img_url)
                                gallery = [thumb] + image_urls if thumb else image_urls
                            else:
                                # Images disabled - use random placeholders
                                gallery = get_random_placeholder_gallery(5)
                            
                            # Parse video URLs
                            video_urls_raw = row.get('video_urls', '')
                            video_urls = [v.strip() for v in video_urls_raw.split(',') if v.strip()] if video_urls_raw else []
                            
                            # Load full review data for detail page
                            review_data = load_reviews(company, tid)
                            
                            # Return all info needed for the detail page
                            return jsonify({
                                'key': key,  # Include the tour key for widget protection
                                'name': row.get('name', ''),
                                'company': COMPANY_DISPLAY_NAMES.get(row.get('company_name', ''), row.get('company_name', '').title()),
                                'summary': row.get('summary', ''),
                                'description': row.get('description', ''),
                                'price_adult': row.get('price_adult', ''),
                                'price_child': row.get('price_child', ''),
                                'duration': row.get('duration', ''),
                                'departure_location': row.get('departure_location', ''),
                                'departure_times': row.get('departure_times', ''),
                                'includes': row.get('includes', ''),
                                'highlights': row.get('highlights', ''),
                                'itinerary': row.get('itinerary', ''),
                                'menu': row.get('menu', ''),
                                'ideal_for': row.get('ideal_for', ''),
                                'age_requirements': row.get('age_requirements', ''),
                                'price_tiers': row.get('price_tiers', ''),
                                'keywords': row.get('keywords', ''),
                                'duration_hours': row.get('duration_hours', ''),
                                'link_booking': row.get('link_booking', ''),
                                'link_more_info': row.get('link_more_info', ''),
                                'booking_connected': row.get('booking_connected', '0'),
                                'gallery': gallery,
                                'video_urls': video_urls,  # Video URLs for embedded playback
                                'uses_placeholder_images': not images_enabled,
                                'important_information': row.get('important_information', ''),
                                'what_to_bring': row.get('what_to_bring', ''),
                                'whats_extra': row.get('whats_extra', ''),
                                'cancellation_policy': row.get('cancellation_policy', ''),
                                'reviews': review_data if review_data else {
                                    'reviews': [],
                                    'overall_rating': 0,
                                    'review_count': 0,
                                    'source': None,
                                    'source_url': None
                                }
                            })
        except (FileNotFoundError, IOError) as e:
            print(f"Warning: Could not load {csvfile}: {e}")
            continue
        except Exception as e:
            print(f"Error processing {csvfile}: {e}")
            continue
    return jsonify({'error': 'Tour not found'}), 404

@app.route('/api/similar-tours/<key>')
def get_similar_tours(key):
    """Get similar tours based on RAG embeddings"""
    language = request.args.get('lang', 'en')
    n_results = int(request.args.get('n', 3))
    active_account = get_active_account()
    
    print(f"[SIMILAR] Finding similar tours for: {key}")
    
    # Helper function to perform the actual search
    def do_search(collection):
        # Get the current tour's embedding from the collection
        result = collection.get(ids=[key], include=['embeddings'])
        
        embeddings = result.get('embeddings') if result else None
        if embeddings is None or len(embeddings) == 0:
            print(f"[SIMILAR] Tour {key} not found in embeddings")
            return {'tours': [], 'error': 'Tour not found in index'}
        
        tour_embedding = embeddings[0]
        
        # Query for similar tours (get extra to filter out the current tour)
        similar = collection.query(
            query_embeddings=[tour_embedding],
            n_results=n_results + 1,  # +1 to account for the tour itself
            include=['metadatas', 'distances']
        )
        
        if not similar or not similar['ids'] or not similar['ids'][0]:
            return {'tours': []}
        
        # Filter out the current tour and convert to tour data
        similar_tours = []
        all_tours = load_all_tours(language, preview_account=active_account)
        tours_by_key = {t['key']: t for t in all_tours}
        
        for i, (tour_key, metadata, distance) in enumerate(zip(
            similar['ids'][0],
            similar['metadatas'][0],
            similar['distances'][0]
        )):
            # Skip the current tour itself
            if tour_key == key:
                continue
            
            # Get full tour data
            tour_data = tours_by_key.get(tour_key)
            if tour_data:
                # Load thumbnail (with account-specific hidden images filtered)
                thumb, _, _ = load_tour_images(tour_data, max_images=1, account_username=active_account)
                
                similar_tours.append({
                    'key': tour_key,
                    'name': tour_data.get('name', metadata.get('name', '')),
                    'company_name': tour_data.get('company_name', metadata.get('company_name', '')),
                    'price_adult': tour_data.get('price_adult', metadata.get('price_adult', '')),
                    'duration': tour_data.get('duration', ''),
                    'thumbnail': thumb,
                    'similarity': round((1 - distance) * 100)  # Convert distance to similarity %
                })
            
            # Limit to requested number
            if len(similar_tours) >= n_results:
                break
        
        print(f"[SIMILAR] Found {len(similar_tours)} similar tours")
        return {'tours': similar_tours}
    
    # Try with cached collection first
    collection = get_chroma_collection()
    if collection is None:
        print("[SIMILAR] ChromaDB not available")
        return jsonify({'tours': [], 'error': 'Semantic search not available'})
    
    try:
        result = do_search(collection)
        return jsonify(result)
    except Exception as e:
        # If error mentions "does not exist", try reloading the collection
        error_msg = str(e)
        if "does not exist" in error_msg or "Collection" in error_msg:
            print(f"[SIMILAR] Collection error, reloading: {e}")
            collection = get_chroma_collection(force_reload=True)
            if collection is None:
                return jsonify({'tours': [], 'error': 'Could not reload ChromaDB'})
            try:
                result = do_search(collection)
                return jsonify(result)
            except Exception as e2:
                print(f"[SIMILAR] Error after reload: {e2}")
                import traceback
                traceback.print_exc()
                return jsonify({'tours': [], 'error': str(e2)})
        
        print(f"[SIMILAR] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'tours': [], 'error': str(e)})

def log_lead_to_csv(booking_data):
    """Log booking lead to CSV file for backup"""
    csv_file = 'leads_log.csv'
    file_exists = os.path.isfile(csv_file)
    
    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['timestamp', 'tour_name', 'tour_company', 'selected_pricing', 'guest_name', 'guest_email', 
                         'guest_phone', 'adults', 'children', 'preferred_date', 'message', 'email_sent']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerow({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tour_name': booking_data.get('tour_name', ''),
                'tour_company': booking_data.get('tour_company', ''),
                'selected_pricing': booking_data.get('selected_pricing', 'Not specified'),
                'guest_name': booking_data.get('guest_name', ''),
                'guest_email': booking_data.get('guest_email', ''),
                'guest_phone': booking_data.get('guest_phone', ''),
                'adults': booking_data.get('adults', ''),
                'children': booking_data.get('children', ''),
                'preferred_date': booking_data.get('preferred_date', ''),
                'message': booking_data.get('message', ''),
                'email_sent': booking_data.get('email_sent', False)
            })
        return True
    except Exception as e:
        print(f"Error logging lead to CSV: {e}")
        return False

def send_booking_email(booking_data):
    """Send booking inquiry email to tour operator"""
    if not SENDGRID_API_KEY:
        print("Warning: SENDGRID_API_KEY not set. Email not sent.")
        return False
    
    try:
        # Get tour operator email
        company = booking_data.get('tour_company', '').lower().replace(' ', '').replace('-', '')
        to_email = COMPANY_EMAILS.get(company, ADMIN_EMAIL)
        
        # Create email content
        subject = f"New Tour Inquiry - {booking_data.get('tour_name', 'Tour')}"
        
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #0077b6; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f9f9f9; padding: 30px; }}
                .section {{ margin-bottom: 20px; }}
                .label {{ font-weight: bold; color: #0077b6; }}
                .value {{ margin-left: 10px; }}
                .footer {{ background: #333; color: white; padding: 15px; text-align: center; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ðŸï¸ New Tour Inquiry</h1>
                </div>
                <div class="content">
                    <div class="section">
                        <p><span class="label">Tour:</span> <span class="value">{booking_data.get('tour_name', 'N/A')}</span></p>
                        <p><span class="label">Company:</span> <span class="value">{COMPANY_DISPLAY_NAMES.get(company, company.title())}</span></p>
                        <p><span class="label">Selected Pricing:</span> <span class="value">{booking_data.get('selected_pricing', 'Not specified')}</span></p>
                    </div>
                    
                    <div class="section">
                        <h3 style="color: #0077b6;">Guest Information</h3>
                        <p><span class="label">Name:</span> <span class="value">{booking_data.get('guest_name', 'N/A')}</span></p>
                        <p><span class="label">Email:</span> <span class="value">{booking_data.get('guest_email', 'N/A')}</span></p>
                        <p><span class="label">Phone:</span> <span class="value">{booking_data.get('guest_phone', 'N/A')}</span></p>
                    </div>
                    
                    <div class="section">
                        <h3 style="color: #0077b6;">Booking Details</h3>
                        <p><span class="label">Adults:</span> <span class="value">{booking_data.get('adults', 'N/A')}</span></p>
                        <p><span class="label">Children:</span> <span class="value">{booking_data.get('children', '0')}</span></p>
                        <p><span class="label">Preferred Date:</span> <span class="value">{booking_data.get('preferred_date', 'N/A')}</span></p>
                    </div>
                    
                    <div class="section">
                        <h3 style="color: #0077b6;">Message / Special Requests</h3>
                        <p>{booking_data.get('message', 'No special requests')}</p>
                    </div>
                </div>
                <div class="footer">
                    <p>Inquiry submitted via Filtour Kiosk</p>
                    <p><strong>Referral:</strong> {booking_data.get('referral', 'Unknown')} ({booking_data.get('source', 'kiosk')})</p>
                    <p>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        print(f"Email sent successfully to {to_email}. Status code: {response.status_code}")
        return True
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@app.route('/submit-booking', methods=['POST'])
def submit_booking():
    """Handle booking form submission"""
    try:
        booking_data = request.get_json()
        
        # Add referral tracking - which shop/kiosk referred this booking
        referral_account = get_referral_account()
        if referral_account:
            booking_data['referral'] = referral_account
            booking_data['source'] = 'web_qr'  # Came from QR code scan
            print(f"[BOOKING] Lead attributed to: {referral_account}")
        else:
            booking_data['referral'] = get_active_account()
            booking_data['source'] = 'kiosk'  # Direct from physical kiosk
        
        # Send email to tour operator
        email_sent = send_booking_email(booking_data)
        
        # Log to CSV (always log, even if email fails)
        booking_data['email_sent'] = email_sent
        log_lead_to_csv(booking_data)
        
        return jsonify({
            'success': True,
            'message': 'Booking inquiry submitted successfully'
        })
    except Exception as e:
        print(f"Error processing booking: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

def find_matching_tours_with_llm(user_message, conversation_history, all_tours, language='en', exclude_keys=None):
    """
    Use LLM to intelligently match user's request to available tours.
    Works with any language, any wording, and finds close matches.
    exclude_keys: Set of tour keys to exclude (for "show other options" requests)
    """
    if exclude_keys is None:
        exclude_keys = set()
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Build conversation context - separate USER messages from ASSISTANT messages
    # We need USER-ONLY context for intent detection (so assistant's welcome message doesn't pollute)
    context_messages = []
    user_messages_only = []
    for msg in conversation_history[-6:]:
        if msg.get('role') == 'user':
            user_content = msg.get('content', '')
            context_messages.append(f"User: {user_content}")
            user_messages_only.append(user_content.lower())
        elif msg.get('role') == 'assistant':
            context_messages.append(f"Assistant: {msg.get('content', '')[:200]}...")
    context = "\n".join(context_messages) if context_messages else "No previous context"
    
    # PRE-FILTER: Only send relevant tours to LLM (based on keywords in message AND context)
    msg_lower = user_message.lower()
    
    # TOPIC CHANGE DETECTION: If current message has a SPECIFIC activity, ignore historical context
    # This prevents "jet ski tours" from inheriting "whitehaven" from previous conversation
    specific_activities_in_msg = []
    activity_keywords = {
        'jetski': ['jetski', 'jet ski'],
        'oceanrafting': ['ocean rafting', 'oceanrafting'],  # Specific company/tour type
        'helicopter': ['helicopter', 'heli tour', 'scenic flight', 'seaplane'],
        'sailing': ['sailing tour', 'sail tour', 'yacht tour'],
        'diving': ['dive tour', 'diving tour', 'scuba'],
        'fishing': ['fishing tour', 'fishing charter'],
        'wildlife': ['wildlife tour', 'animal tour'],
        'reef': ['reef tour', 'great barrier', 'gbr tour'],
        'whitehaven': ['whitehaven tour', 'whitehaven beach'],
    }
    
    for activity, phrases in activity_keywords.items():
        if any(phrase in msg_lower for phrase in phrases):
            specific_activities_in_msg.append(activity)
    
    # If user is asking for a SPECIFIC activity in current message, DON'T inherit context
    # Example: User asked for "whitehaven" before, now asks for "jet ski" -> only search jet ski
    is_new_topic = len(specific_activities_in_msg) > 0
    
    if is_new_topic:
        # NEW TOPIC: Only use current message for intent
        user_text = msg_lower
        print(f"[LLM] TOPIC CHANGE detected: {specific_activities_in_msg} - ignoring historical context")
    else:
        # CONTINUATION: Use current + previous user messages
        user_text = msg_lower + " " + " ".join(user_messages_only)
    
    # Combined text for general keyword matching (includes assistant context for continuity)
    context_lower = context.lower() if context else ""
    combined_text = msg_lower + " " + context_lower
    
    keywords = ['snorkel', 'dive', 'reef', 'whitehaven', 'beach', 'sail', 'cruise', 'helicopter',
                'jet ski', 'jetski', 'kayak', 'fishing', 'whale', 'turtle', 'scenic', 'island', 'sunset',
                'half day', 'full day', 'overnight', 'family', 'romantic', 'adventure',
                'kangaroo', 'wildlife', 'animal', 'platypus', 'wallaby', 'nature', 'eco',
                'bird', 'crocodile', 'koala', 'dolphin', 'sunrise', 'rainforest', 'multi-day',
                'multi day', '2 day', '3 day', 'overnight', 'liveaboard', 'backpack']
    
    # Use appropriate text for keyword detection based on topic change
    active_keywords = [kw for kw in keywords if kw in user_text]
    
    # DESTINATION INTENT DETECTION - What does the USER actually want?
    # Check based on topic (current only if new topic, context if continuation)
    user_wants_whitehaven = 'whitehaven' in user_text
    user_wants_reef = ('reef' in user_text and 'whitehaven' not in user_text) or 'great barrier' in user_text or 'gbr' in user_text
    user_wants_sailing = any(kw in user_text for kw in ['sail', 'sailing', 'yacht'])
    user_wants_jetski = 'jetski' in user_text or 'jet ski' in user_text
    user_wants_oceanrafting = 'ocean rafting' in user_text or 'oceanrafting' in user_text
    wants_helicopter = any(kw in user_text for kw in ['helicopter', 'heli', 'scenic flight', 'aerial', 'fly over', 'seaplane'])
    
    # POPULAR TOURS REQUEST - user wants to see our most popular/recommended tours
    popular_keywords = ['popular', 'best tours', 'top tours', 'recommended', 'favorites', 'what\'s popular', 'show popular']
    user_wants_popular = any(kw in user_text for kw in popular_keywords)
    
    print(f"[LLM] User intent: whitehaven={user_wants_whitehaven}, reef={user_wants_reef}, sailing={user_wants_sailing}, jetski={user_wants_jetski}, oceanrafting={user_wants_oceanrafting}, helicopter={wants_helicopter}, popular={user_wants_popular}")
    
    # SPECIAL HANDLING: Only add GBR if user EXPLICITLY wants reef (not Whitehaven/sailing/etc)
    wants_coral_reef_only = 'coral reef' in user_text or 'fringing reef' in user_text
    
    if user_wants_reef and not wants_coral_reef_only and not user_wants_whitehaven:
        # User explicitly wants reef tours - add GBR filter
        active_keywords.append('great_barrier_reef')
        if 'reef' in active_keywords:
            active_keywords.remove('reef')
        print(f"[LLM] Reef request -> treating as Great Barrier Reef request")
    
    print(f"[LLM] Active keywords from message+context: {active_keywords}")
    
    # BUDGET DETECTION - if user mentions backpacker/budget keywords, filter out expensive tours
    budget_keywords = ['backpack', 'budget', 'cheap', 'affordable', 'student', 'hostel', 'low cost', 'inexpensive']
    luxury_keywords = ['luxury', 'private', 'charter', 'vip', 'exclusive', 'premium', 'honeymoon', 'couples only']
    
    is_budget_request = any(kw in combined_text for kw in budget_keywords)
    is_luxury_request = any(kw in combined_text for kw in luxury_keywords)
    
    if is_budget_request:
        print(f"[LLM] Budget request detected - will filter expensive tours (>$1000)")
    if is_luxury_request:
        print(f"[LLM] Luxury request detected - will prioritize premium tours")
    
    # Detect if user wants a specific mode of transport or NOT
    # If user asks for "beach tour" without mentioning helicopter/scenic flight, exclude those
    # NOTE: wants_helicopter is already defined above using user_text (for topic detection)
    # For exclusion, we use combined_text (includes history) to be more conservative
    wants_beach_boat = any(kw in combined_text for kw in ['beach', 'whitehaven', 'boat', 'cruise', 'sail'])
    exclude_helicopter = wants_beach_boat and not wants_helicopter
    
    if exclude_helicopter:
        print(f"[LLM] User wants beach/boat tour - excluding helicopter tours")
    
    # DIRECT NAME MATCHING: Check if user is asking for a specific tour by name
    # Extract potential tour name words from user message (3+ char words, excluding common words)
    common_words = {'the', 'and', 'for', 'can', 'you', 'have', 'any', 'tour', 'tours', 'about', 'tell', 'more', 
                    'what', 'like', 'want', 'show', 'looking', 'find', 'search', 'please', 'thanks', 'day', 'full', 'half'}
    user_words = [w for w in msg_lower.replace('?', '').replace('!', '').replace('.', '').split() 
                  if len(w) >= 3 and w not in common_words]
    
    # Check for direct tour name matches first
    direct_name_matches = []
    for t in all_tours:
        name_lower = t['name'].lower()
        # Check if any significant user word appears in tour name
        for word in user_words:
            if len(word) >= 4 and word in name_lower:
                direct_name_matches.append(t)
                break
    
    if direct_name_matches:
        print(f"[LLM] DIRECT NAME MATCH: Found {len(direct_name_matches)} tours matching user's specific request")
    
    # Filter tours to only those matching user's keywords (or all if no specific keywords)
    relevant_tours = []
    for t in all_tours:
        name_lower = t['name'].lower()
        
        # Include direct name matches first
        if t in direct_name_matches:
            relevant_tours.append(t)
            continue
        
        # Exclude helicopter/scenic flight tours if user wants beach tours
        if exclude_helicopter:
            if any(kw in name_lower for kw in ['helicopter', 'heli ', 'scenic flight', 'aerial']):
                continue  # Skip helicopter tours
        
        # JET SKI REQUEST: ONLY return jet ski tours!
        # Don't mix beach/reef tours with jet ski results
        # STRICT: Tour must be PRIMARILY about jet skiing, not just mention it as an add-on
        if user_wants_jetski:
            company_lower = (t.get('company', '') or t.get('company_name', '')).lower()
            # Strict check: jet ski must be in NAME or it's a jet ski company
            is_jetski_tour = (
                'jetski' in name_lower or 'jet ski' in name_lower or  # Name contains jet ski
                'jetskitour' in company_lower or                       # jetskitour company
                'oceandynamics' in company_lower                       # oceandynamics (jet ski operator)
            )
            if not is_jetski_tour:
                continue  # Skip non-jet-ski tours for jet ski requests
        
        # OCEAN RAFTING REQUEST: ONLY return Ocean Rafting company tours!
        if user_wants_oceanrafting:
            company_lower = (t.get('company', '') or t.get('company_name', '')).lower()
            is_oceanrafting_tour = 'oceanrafting' in company_lower or 'ocean rafting' in company_lower
            if not is_oceanrafting_tour:
                continue  # Skip non-Ocean-Rafting tours
        
        # SCENIC FLIGHT / HELICOPTER REQUEST: ONLY return aerial tours!
        # Prioritize PURE flights over combo packages
        if wants_helicopter and not user_wants_whitehaven and not user_wants_reef:
            tour_text = (name_lower + ' ' + (t.get('description', '') or '')).lower()
            company_lower = (t.get('company', '') or t.get('company_name', '')).lower()
            
            # Check if this is a PURE flight tour (main activity is flying)
            is_pure_flight = (
                'helicopter' in name_lower or
                'heli tour' in name_lower or
                'scenic flight' in name_lower or
                'seaplane' in name_lower or
                'gsl aviation' in company_lower or  # GSL Aviation = helicopter company
                'helireef' in company_lower or      # HeliReef = helicopter company
                'air whitsunday' in company_lower   # Air Whitsunday = seaplane company
            )
            
            # Check if this is a COMBO tour (flight + other activity)
            is_combo_tour = (
                'fly raft' in name_lower or
                'fly/raft' in name_lower or
                'heli' in name_lower and 'snorkel' in name_lower or
                'heli' in name_lower and 'reef' in name_lower or
                'flight' in name_lower and ('whitehaven' in name_lower or 'snorkel' in name_lower)
            )
            
            # For scenic flight requests: include pure flights, skip combos
            if is_combo_tour and not is_pure_flight:
                continue  # Skip combo tours - user wants actual flights
            
            # Must be a flight tour
            is_aerial_tour = is_pure_flight or (
                'aerial' in name_lower or
                ('flight' in name_lower and not is_combo_tour)
            )
            if not is_aerial_tour:
                continue  # Skip non-aerial tours for scenic flight requests
        
        # WHITEHAVEN BEACH REQUEST: Exclude reef-focused tours
        # These tours go to the GBR, not Whitehaven Beach!
        if user_wants_whitehaven and not user_wants_reef and not user_wants_jetski:
            tour_text_full = (name_lower + ' ' + (t.get('description', '') or '')).lower()
            is_reef_focused = (
                'reefworld' in name_lower or
                'great barrier reef' in name_lower or
                'reef adventure' in name_lower or
                'reef pontoon' in tour_text_full or
                'outer reef' in tour_text_full or
                ('reef' in name_lower and 'whitehaven' not in name_lower)
            )
            if is_reef_focused:
                continue  # Skip reef tours for Whitehaven requests
        
        # Budget filtering - skip expensive tours for backpackers
        if is_budget_request and not is_luxury_request:
            price_str = str(t.get('price_adult', '$0'))
            # Extract numeric price
            price_num = 0
            try:
                price_num = int(''.join(filter(str.isdigit, price_str.split('.')[0])))
            except:
                pass
            if price_num > 1000:
                continue  # Skip tours over $1000 for budget travelers
        
        if not active_keywords:
            relevant_tours.append(t)  # No keywords = include all
        else:
            tour_text = (name_lower + ' ' + (t.get('description', '') or '') + ' ' + (t.get('highlights', '') or '')).lower()
            tags = (t.get('tags', '') or '').lower()
            
            # Special handling for Great Barrier Reef - must actually go to the OUTER GBR
            if 'great_barrier_reef' in active_keywords:
                company_lower = (t.get('company', '') or t.get('company_name', '')).lower()
                
                # BLACKLIST: These companies do NOT go to the actual Great Barrier Reef
                # They do "coral reef snorkeling" at fringing reefs near islands - NOT the outer GBR
                is_blacklisted_company = any(c in company_lower for c in [
                    'oceanrafting', 'ocean rafting',  # Whitehaven Beach focused
                    'redcat', 'red cat',              # Island tours, not outer GBR  
                    'wings',                          # Langford Island, NOT outer GBR
                    'thundercat',                     # Island tours with fringing reef
                ])
                
                if is_blacklisted_company:
                    continue  # Skip this tour entirely for GBR searches
                
                # WHITELIST: Known actual GBR tour operators
                is_actual_gbr_operator = any(c in company_lower for c in [
                    'cruise whitsundays', 'cruisewhitsundays',  # Reefworld, Hardy Reef
                    'reefworld',
                ])
                
                # Tour must have ACTUAL outer GBR indicators (not just marketing text)
                has_real_gbr_indicators = (
                    'outer reef' in tour_text or 
                    'outer barrier' in tour_text or
                    'reefworld' in tour_text or 
                    'hardy reef' in tour_text or 
                    'knuckle reef' in tour_text or
                    'bait reef' in tour_text or
                    'hook reef' in tour_text or
                    'pontoon' in tour_text or  # GBR pontoons are on the outer reef
                    'reef sleep' in tour_text   # Sleeping on the reef = outer reef
                )
                
                # EXCLUDE if tour says "fringing reef" or "inner reef" - these are NOT the GBR
                is_fringing_only = (
                    'fringing reef' in tour_text or 
                    'inner reef' in tour_text or
                    'inner fringing' in tour_text or
                    ('coral reef' in tour_text and 'outer' not in tour_text and 'great barrier' not in tour_text)
                )
                
                # Include if: actual GBR operator OR has real GBR indicators AND not fringing only
                if is_actual_gbr_operator or (has_real_gbr_indicators and not is_fringing_only):
                    relevant_tours.append(t)
            else:
                # Special handling for jetski - match both "jet ski" and "jetski" variants
                if any(kw in ['jet ski', 'jetski'] for kw in active_keywords):
                    # Normalize tour text to find jetski tours
                    if 'jetski' in tour_text or 'jet ski' in tour_text or 'jetskitour' in t.get('company', '').lower():
                        relevant_tours.append(t)
                        continue
                
                # Standard keyword matching
                if any(kw in tour_text or kw in tags for kw in active_keywords):
                    relevant_tours.append(t)
    
    # Filter out excluded keys (for "other options" requests)
    if exclude_keys:
        before_exclude = len(relevant_tours)
        relevant_tours = [t for t in relevant_tours if t.get('key') not in exclude_keys]
        print(f"[LLM] Excluded {before_exclude - len(relevant_tours)} previously shown tours")
    
    # POPULAR TOURS REQUEST: Filter to ONLY promoted tours, then by rating
    if user_wants_popular:
        promoted_tours = [t for t in relevant_tours if t.get('is_promoted') or t.get('promotion')]
        if promoted_tours:
            print(f"[LLM] POPULAR REQUEST: Found {len(promoted_tours)} promoted tours - using ONLY these")
            relevant_tours = promoted_tours
        else:
            print(f"[LLM] POPULAR REQUEST: No promoted tours found - falling back to highest rated")
            # Sort by rating if no promoted tours
            relevant_tours.sort(key=lambda t: t.get('review_rating', 0) or 0, reverse=True)
    
    # PRE-SORT relevant tours by our scoring (promotion + rating) BEFORE sending to LLM
    # This way the LLM sees promoted/highly-rated tours FIRST in the catalog
    def pre_sort_score(tour):
        score = 0
        # Promoted tours get massive boost
        if tour.get('is_promoted') or tour.get('promotion'):
            score += 1000
        if tour.get('promotion') == 'popular':
            score += 500
        elif tour.get('promotion') == 'featured':
            score += 300
        elif tour.get('promotion') == 'best_value':
            score += 200
        # Rating score
        rating = tour.get('review_rating', 0) or 0
        score += rating * 100  # 5.0 = 500 points
        return score
    
    relevant_tours.sort(key=pre_sort_score, reverse=True)
    
    # Check if this is a specific activity request that should SKIP company diversity
    # For jetski, helicopter, scenic flight - return ALL matching tours from same company
    is_specific_activity = user_wants_jetski or wants_helicopter
    
    if not is_specific_activity:
        # Apply company diversity BEFORE sending to LLM - don't give LLM 10 tours from same company
        companies_seen = set()
        diverse_relevant = []
        remaining = []
        for tour in relevant_tours:
            company = tour.get('company', tour.get('company_name', ''))
            if company not in companies_seen:
                diverse_relevant.append(tour)
                companies_seen.add(company)
            else:
                remaining.append(tour)
        # Add remaining tours (duplicates) after diverse ones
        diverse_relevant.extend(remaining)
        relevant_tours = diverse_relevant
    else:
        print(f"[LLM] Specific activity request (jetski={user_wants_jetski}, helicopter={wants_helicopter}) - SKIPPING company diversity")
    
    # Limit to 50 most relevant tours to keep prompt manageable
    relevant_tours = relevant_tours[:50]
    print(f"[LLM] Pre-filtered to {len(relevant_tours)} relevant tours (from {len(all_tours)} total)")
    print(f"[LLM] Top 5 tours being sent to LLM (in this order):")
    for i, t in enumerate(relevant_tours[:5]):
        promo = "[PROMOTED]" if (t.get('is_promoted') or t.get('promotion')) else ""
        rating = t.get('review_rating', 0) or 0
        company = t.get('company', t.get('company_name', ''))
        print(f"   {i+1}. {t['name']} ({company}) - Rating: {rating} {promo}")
    
    # Build tour catalog (compact format for LLM)
    tour_catalog = []
    for t in relevant_tours:
        # Build a tags string from various fields to help matching
        tags = []
        name_lower = t['name'].lower()
        desc_lower = (t.get('description', '') or '').lower()
        
        # Auto-tag based on content
        if 'reef' in name_lower or 'reef' in desc_lower:
            tags.append('reef')
        if 'snorkel' in name_lower or 'snorkel' in desc_lower:
            tags.append('snorkeling')
        if 'dive' in name_lower or 'diving' in desc_lower:
            tags.append('diving')
        if 'whitehaven' in name_lower or 'whitehaven' in desc_lower:
            tags.append('whitehaven')
        if 'sail' in name_lower or 'sailing' in desc_lower:
            tags.append('sailing')
        if 'jet ski' in name_lower or 'jetski' in name_lower:
            tags.append('jetski')
        if 'helicopter' in name_lower or 'heli' in name_lower:
            tags.append('helicopter')
        if 'scenic flight' in name_lower:
            tags.append('scenic-flight')
        if 'kangaroo' in name_lower or 'kangaroo' in desc_lower:
            tags.append('wildlife')
            tags.append('kangaroo')
        if 'wildlife' in name_lower or 'wildlife' in desc_lower:
            tags.append('wildlife')
        if 'platypus' in name_lower or 'platypus' in desc_lower:
            tags.append('wildlife')
        if 'wallaby' in name_lower or 'wallaby' in desc_lower:
            tags.append('wildlife')
        if 'dolphin' in name_lower or 'dolphin' in desc_lower:
            tags.append('wildlife')
        if 'turtle' in name_lower or 'turtle' in desc_lower:
            tags.append('wildlife')
        if 'whale' in name_lower or 'whale' in desc_lower:
            tags.append('wildlife')
            tags.append('whale-watching')
        if 'eco' in name_lower or 'eco' in desc_lower:
            tags.append('eco')
        if 'sunrise' in name_lower or 'sunrise' in desc_lower:
            tags.append('sunrise')
        if 'rainforest' in name_lower or 'rainforest' in desc_lower:
            tags.append('nature')
        
        # Check family-friendly from CSV tags or audience field
        csv_tags = (t.get('tags', '') or '').lower()
        audience = (t.get('audience', '') or '').lower()
        ideal_for = (t.get('ideal_for', '') or '').lower()
        if 'family' in csv_tags or 'family' in audience or t.get('family_friendly'):
            tags.append('family-friendly')
        
        # Backpacker/social tags - for group sailing tours that attract young travelers
        if 'backpack' in ideal_for or 'young' in ideal_for or 'social' in ideal_for:
            tags.append('backpacker')
            tags.append('social')
        if 'clipper' in name_lower or 'matador' in name_lower or 'solway' in name_lower:
            tags.append('backpacker')  # Known backpacker boats
            tags.append('social')
        if 'overnight' in name_lower or 'liveaboard' in name_lower:
            # Multi-day group sailing = good for meeting people
            if 'private' not in name_lower and 'charter' not in name_lower:
                tags.append('social')
        
        # Get price for LLM context
        price_str = str(t.get('price_adult', ''))
        
        # Compact format - only essential info for matching
        tour_info = {
            'key': t['key'],
            'name': t['name'],
            'company': t.get('company', t.get('company_name', '')),
            'duration': t.get('duration_category', t.get('duration', '')),
            'price': price_str,
            'tags': tags,
            'rating': t.get('review_rating', 0) or 0,  # For ordering by quality
            'promoted': bool(t.get('is_promoted') or t.get('promotion'))
        }
        tour_catalog.append(tour_info)
    
    # Build budget context string for LLM
    budget_context = ""
    if is_budget_request:
        budget_context = "\nUSER IS A BUDGET TRAVELER (backpacker/student) - Prioritize tours under $500, prefer 'social' and 'backpacker' tagged tours. AVOID expensive luxury/private tours!"
    elif is_luxury_request:
        budget_context = "\nUSER WANTS LUXURY/PRIVATE - Prioritize premium, charter, and exclusive tours."
    
    # Build EXPLICIT promoted tours list for the prompt  
    promoted_tour_keys = [t['key'] for t in tour_catalog if t.get('promoted')]
    promoted_section = ""
    if promoted_tour_keys:
        promoted_section = f"""
⚠️ PROMOTED TOURS (marked "promoted: true" in the catalog) - Include FIRST if they match:
These {len(promoted_tour_keys)} tours are marked as popular/featured and MUST be prioritized:
{json.dumps(promoted_tour_keys, indent=1)}

RULE: If ANY of these promoted tours match the user's request (destination + duration), 
they MUST appear in your results BEFORE non-promoted tours from the same category!
"""
    
    # Create the LLM prompt
    prompt = f"""You are a tour matching assistant. Given a user's request and a catalog of available tours, 
select the most relevant tours to recommend.
{promoted_section}
CONVERSATION CONTEXT:
{context}

CURRENT USER REQUEST:
{user_message}
{budget_context}

AVAILABLE TOURS (JSON format):
{json.dumps(tour_catalog, indent=1)}

INSTRUCTIONS:
1. The tours are ALREADY SORTED by quality (promoted first, then by rating)
2. The tours are ALREADY DIVERSE (one per company first)
3. YOUR JOB: Just pick tours from the catalog that MATCH the user's destination request
4. PREFER TOURS NEAR THE TOP of the catalog - they are the best matches!
5. DO NOT skip over promoted tours (marked promoted: true) that match the destination!
6. If user wants "Whitehaven Beach" - pick tours where "whitehaven" is in the tags
7. If user wants "Great Barrier Reef" - pick tours where "reef" is in the tags
8. Return the FIRST 3-5 tours that match the destination from the catalog

IMPORTANT MATCHING RULES:
- DESTINATION MATCHING IS STRICT - tour must ACTUALLY GO to the destination:
  * "Whitehaven Beach" = tours that spend significant TIME at Whitehaven Beach
  * NOT tours that just FLY OVER or MENTION Whitehaven in passing!
  * Ocean Rafting (Northern Exposure, Southern Lights) = THE Whitehaven Beach tours!
  * Scenic flights ONLY for reef/Heart Reef requests, NOT beach requests
- DURATION IS STRICT - MUST MATCH EXACTLY:
  * "full day" = ONLY full_day tours (NOT multi-day or overnight!)
  * "half day" = ONLY half_day tours
  * "multi-day" or "overnight" = ONLY multi_day tours
  * DO NOT return 2-day tours for "full day" requests!
- USE THE TAGS FIELD to find related tours (e.g., "reef" tag means it's a reef tour)
- For family requests: ALWAYS include tours with "family-friendly" tag
- PRIORITIZE PROMOTED TOURS when they match!
- If no tours match, return empty and set needs_alternative=true
- Return 10-15 tours if available (we need variety for "show other" requests)

CRITICAL RULES:
1. DESTINATION MATCHING - Tour must ACTUALLY GO to the destination, not just mention it:
   - "Whitehaven Beach" = tours that spend TIME on Whitehaven Beach (not fly over it)
   - "Great Barrier Reef" = tours that visit the OUTER reef (pontoons, Reefworld) 
   - Scenic flights don't count as "visiting" - they see from the air only
   
2. COMPANY DIVERSITY - USUALLY prefer diverse companies, BUT with exceptions:
   - For GENERAL requests (beach, reef, sailing): spread across different operators
   - For SPECIFIC ACTIVITY requests (jetski, jet ski, helicopter, scenic flight): 
     IGNORE company diversity - return ALL matching tours even if from same company!
   - If user asks for "jetski" or "jet ski": return ALL jetski tours (likely same company)
   - If user asks for "helicopter" or "scenic flight": return ALL aerial tours

3. ORDERING (STRICT PRIORITY):
   a) PROMOTED TOURS FIRST - Tours with "promoted: true" that match the request go FIRST
   b) THEN BY RATING - Among matching tours, order by review rating (highest to lowest)
   - Look at the rating field in each tour
   - 5.0 rated tours before 4.5, before 4.0, etc.
   - If two tours have same rating, promoted one wins
   
4. MATCH THE REQUEST - Don't recommend reef tours for beach requests or vice versa!
   
   FOR WHITEHAVEN BEACH REQUESTS - DO NOT RECOMMEND:
   ❌ "Reefworld" tours (these go to the REEF, not Whitehaven Beach!)
   ❌ "Great Barrier Reef Adventure" (reef tour, not beach!)
   ❌ Any tour with "reef" in the name (unless it also has "whitehaven")
   ❌ Pontoon tours (these are reef pontoons, not beaches!)
   
   FOR WHITEHAVEN BEACH REQUESTS - PRIORITIZE:
   ✅ Ocean Rafting (Northern Exposure, Southern Lights) = #1 Whitehaven tours!
   ✅ Tours with "whitehaven" in the name
   ✅ Tours with "hill inlet" in the name
   ✅ Cruise Whitsundays Whitehaven tours (NOT their reef tours!)
   
   FOR GREAT BARRIER REEF REQUESTS - PRIORITIZE:
   ✅ Reefworld, Hardy Reef, outer reef pontoon tours
   ✅ Cruise Whitsundays reef tours
   ❌ NOT Ocean Rafting (they don't go to the actual GBR!)

CRITICAL: Use the EXACT "key" values from the catalog above. Keys contain hashes like "company__abc123def456".
Do NOT construct keys from tour names - copy the exact key string from the catalog.

Respond in this exact JSON format:
{{
  "matched_tour_keys": ["company__exacthashfromcatalog", "company__anotherhash"],
  "user_wants": "brief description of what user is looking for",
  "match_quality": "exact" | "close" | "alternative",
  "explanation": "why these tours were selected",
  "total_matching_tours": 3,
  "needs_alternative": false,
  "alternative_suggestion": null
}}

CRITICAL - DO NOT RETURN TOURS FOR THESE CASES:
- Questions about tours: "how many", "do you have", "what kind of", "are there any"
- General inquiries: "tell me about", "what tours", "which tours"
- Greetings or chat: "hello", "how are you", "thanks"

Only return tour matches when user explicitly wants RECOMMENDATIONS:
- "show me", "I want", "recommend", "find me", "book", "I'd like"
- Specific requests with preferences: "full day reef tour", "family snorkelling"

If the user is asking a QUESTION or just chatting, respond with EMPTY tours:
{{
  "matched_tour_keys": [],
  "user_wants": "asking about tours" or "chatting",
  "match_quality": "none",
  "explanation": "User is asking a question, not requesting recommendations",
  "needs_alternative": false,
  "alternative_suggestion": null
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap for this task
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        # Handle markdown code blocks if present
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()
        
        result = json.loads(result_text)
        
        print(f"[LLM] Tour Matching:")
        print(f"   User wants: {result.get('user_wants', 'unknown')}")
        print(f"   Match quality: {result.get('match_quality', 'unknown')}")
        print(f"   Matched tours: {result.get('matched_tour_keys', [])}")
        
        # Get full tour objects for matched keys (with fallback to name matching)
        matched_tours = []
        for key in result.get('matched_tour_keys', []):
            # Try exact key match first
            tour = next((t for t in all_tours if t['key'] == key), None)
            
            # If not found, try fuzzy matching by extracting tour name from the made-up key
            if not tour and '__' in key:
                company_prefix = key.split('__')[0]
                key_suffix = key.split('__')[1].replace('_', ' ').lower()
                
                # Try to find a tour from that company with a similar name
                for t in all_tours:
                    if t['key'].startswith(company_prefix):
                        tour_name_normalized = t['name'].lower().replace('-', ' ')
                        # Check if key suffix matches significant parts of the tour name
                        key_words = set(key_suffix.split())
                        name_words = set(tour_name_normalized.split())
                        overlap = len(key_words & name_words)
                        if overlap >= 3 or key_suffix in tour_name_normalized:
                            tour = t
                            print(f"   [FUZZY MATCH] {key} -> {t['key']} ({t['name']})")
                            break
            
            if tour and tour not in matched_tours:
                matched_tours.append(tour)
        
        # Rank tours by quality score (promotion + rating + review count)
        def calculate_tour_score(tour):
            score = 0
            
            # Promoted tours get big boost
            if tour.get('is_promoted'):
                score += 100
            if tour.get('promotion') == 'popular':
                score += 50
            elif tour.get('promotion') == 'featured':
                score += 30
            elif tour.get('promotion') == 'best_value':
                score += 20
            
            # Rating score (0-5 scale, multiply by 10 for weight)
            rating = tour.get('review_rating', 0) or 0
            score += rating * 10  # Max 50 points
            
            # Review count bonus (more reviews = more trusted)
            review_count = tour.get('review_count', 0) or 0
            if review_count >= 100:
                score += 15
            elif review_count >= 50:
                score += 10
            elif review_count >= 20:
                score += 5
            
            return score
        
        # Sort by score (highest first)
        matched_tours.sort(key=calculate_tour_score, reverse=True)
        total_available = len(matched_tours)
        
        # Check if this is a specific activity - skip company diversity for jetski/helicopter
        # (all jetski tours are from same company, so diversity would limit to 1)
        is_specific_activity = user_wants_jetski or wants_helicopter
        
        # Apply company diversity - spread results across different companies
        # when we have enough matching tours from different companies
        # BUT skip diversity for specific activities like jetski, helicopter
        if total_available >= 3 and not is_specific_activity:
            companies_seen = set()
            diverse_tours = []
            remaining_tours = []
            
            # First pass: pick top tour from each unique company
            for tour in matched_tours:
                company = tour.get('company', '')
                if company not in companies_seen and len(diverse_tours) < 3:
                    diverse_tours.append(tour)
                    companies_seen.add(company)
                else:
                    remaining_tours.append(tour)
            
            # If we have less than 3 diverse tours, fill from remaining (allowing duplicates)
            while len(diverse_tours) < 3 and remaining_tours:
                diverse_tours.append(remaining_tours.pop(0))
            
            matched_tours = diverse_tours
            print(f"   [RANK] Showing {len(matched_tours)} diverse tours from {len(companies_seen)} companies (of {total_available} total)")
        else:
            matched_tours = matched_tours[:3]  # Max 3 tours displayed
            if total_available > 0:
                reason = "(specific activity - no diversity filter)" if is_specific_activity else ""
                print(f"   [RANK] Showing {len(matched_tours)} of {total_available} matching tours {reason}")
        
        return {
            'tours': matched_tours,
            'user_wants': result.get('user_wants', ''),
            'match_quality': result.get('match_quality', 'none'),
            'explanation': result.get('explanation', ''),
            'total_matching_tours': total_available,  # Keep track of total available
            'needs_alternative': result.get('needs_alternative', False),
            'alternative_suggestion': result.get('alternative_suggestion')
        }
        
    except Exception as e:
        print(f"[ERROR] LLM tour matching error: {e}")
        return {
            'tours': [],
            'user_wants': '',
            'match_quality': 'error',
            'explanation': str(e),
            'needs_alternative': False,
            'alternative_suggestion': None
        }

def build_promoted_tours_section(tour_context):
    """Build a text section describing promoted tours for the AI"""
    promoted = tour_context.get('promoted', {})
    sections = []
    
    # Popular tours (highest priority)
    if promoted.get('popular'):
        popular_names = [t['name'] for t in promoted['popular'][:5]]
        sections.append(f"ðŸ”¥ POPULAR (Customer favorites - recommend enthusiastically!): {', '.join(popular_names)}")
    
    # Featured tours
    if promoted.get('featured'):
        featured_names = [t['name'] for t in promoted['featured'][:5]]
        sections.append(f"â­ FEATURED (Highly recommended experiences): {', '.join(featured_names)}")
    
    # Best value
    if promoted.get('best_value'):
        value_names = [t['name'] for t in promoted['best_value'][:5]]
        sections.append(f"ðŸ’Ž BEST VALUE (Great value for money): {', '.join(value_names)}")
    
    if sections:
        return "\n".join(sections) + "\n(When these tours match user preferences, prioritize them and be extra enthusiastic!)"
    else:
        return "(No promoted tours currently set)"

def build_tour_context(language='en'):
    """Build a concise tour knowledge base for AI context"""
    tours = load_all_tours(language)
    agent_settings = load_agent_settings()
    promotion_hints = agent_settings.get('ai_promotion_hints', {})
    
    # Group tours by category
    tour_summary = {
        'total_tours': len(tours),
        'categories': {
            'reef': [],
            'whitehaven': [],
            'sailing': [],
            'diving': [],
            'scenic': [],
            'other': []
        },
        'promoted': {
            'popular': [],
            'featured': [],
            'best_value': []
        }
    }
    
    for tour in tours:
        name = tour.get('name', '')
        description = tour.get('description', '')[:200]  # First 200 chars
        price = tour.get('price_adult', 'N/A')
        duration = tour.get('duration', 'N/A')
        company = tour.get('company', '')
        key = tour.get('key', '')
        promotion = tour.get('promotion')
        
        tour_info = {
            'name': name,
            'company': company,
            'description': description,
            'price': price,
            'duration': duration,
            'key': key,
            'promoted': promotion is not None,
            'promotion_level': promotion
        }
        
        # Add to promoted lists if applicable
        if promotion and promotion in tour_summary['promoted']:
            tour_info['promotion_hint'] = promotion_hints.get(promotion, '')
            tour_summary['promoted'][promotion].append(tour_info)
        
        # Categorize tours
        name_lower = name.lower()
        if 'reef' in name_lower or 'coral' in name_lower:
            tour_summary['categories']['reef'].append(tour_info)
        elif 'whitehaven' in name_lower:
            tour_summary['categories']['whitehaven'].append(tour_info)
        elif 'dive' in name_lower or 'snorkel' in name_lower:
            tour_summary['categories']['diving'].append(tour_info)
        elif 'sail' in name_lower or 'cruise' in name_lower:
            tour_summary['categories']['sailing'].append(tour_info)
        elif 'scenic' in name_lower or 'helicopter' in name_lower:
            tour_summary['categories']['scenic'].append(tour_info)
        else:
            tour_summary['categories']['other'].append(tour_info)
    
    # Sort each category to put promoted tours first
    for category in tour_summary['categories'].values():
        category.sort(key=lambda t: (0 if t.get('promoted') else 1, t.get('name', '')))
    
    return tour_summary

@app.route('/chat/preflight', methods=['POST'])
def chat_preflight():
    """FAST deterministic check if tours will likely be searched - triggers animation early"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        # Build context from recent user messages
        context = ""
        for msg in conversation_history[-4:]:
            if msg.get('role') == 'user':
                context += f"{msg.get('content', '')[:100]} "
        
        # Combined text for checking
        combined = f"{context} {user_message}".lower()
        msg_lower = user_message.lower()
        
        # ============================================================
        # DETERMINISTIC CHECK - No LLM, just pattern matching
        # Err on the side of showing animation (false positives OK)
        # ============================================================
        
        # INSTANT TRIGGERS - always search tours
        instant_triggers = [
            'jetski', 'jet ski', 'helicopter', 'scenic flight', 'seaplane',
            'skydiv', 'ocean rafting', 'popular', 'best tours', 'top tours',
            'recommended', 'other options', 'alternatives', 'different tours',
            'something else', 'more options', 'show me', 'what tours',
            'do you have', 'any tours', 'find me', 'search for', 'looking for tours'
        ]
        if any(trigger in msg_lower for trigger in instant_triggers):
            print(f"[PREFLIGHT] INSTANT trigger found in message")
            return jsonify({'will_search_tours': True, 'message_analyzed': user_message[:50]})
        
        # ACTIVITY KEYWORDS
        activities = [
            'reef', 'snorkel', 'diving', 'scuba', 'whitehaven', 'beach', 'island',
            'sailing', 'sail', 'cruise', 'boat', 'fishing', 'kayak', 'paddle',
            'wildlife', 'whale', 'turtle', 'sunset', 'sunrise', 'adventure',
            'family', 'romantic', 'couples', 'tour'
        ]
        
        # DURATION KEYWORDS
        durations = [
            'full day', 'half day', 'overnight', 'multi-day', 'multiday',
            'few hours', 'morning', 'afternoon', 'all day', 'quick', 'short',
            'long', 'extended', '2 day', '3 day', 'weekend'
        ]
        
        has_activity = any(act in combined for act in activities)
        has_duration = any(dur in combined for dur in durations)
        
        # Search if we have BOTH activity and duration in combined context
        will_search = has_activity and has_duration
        
        # ALSO search if message explicitly asks about tours/options
        if 'tour' in msg_lower and any(w in msg_lower for w in ['want', 'like', 'looking', 'show', 'find', 'have', 'get']):
            will_search = True
        
        safe_msg = user_message[:40].encode('ascii', 'ignore').decode('ascii')
        print(f"[PREFLIGHT] '{safe_msg}' -> activity={has_activity}, duration={has_duration}, will_search={will_search}")
        
        return jsonify({
            'will_search_tours': will_search,
            'message_analyzed': user_message[:50]
        })
    except Exception as e:
        print(f"[PREFLIGHT] Error: {e}")
        return jsonify({'will_search_tours': False, 'error': str(e)})

@app.route('/chat/generate-suggestions', methods=['POST'])
def generate_suggestions():
    """Generate 4 contextual user responses based on AI message and conversation state"""
    try:
        data = request.get_json()
        ai_message = data.get('ai_message', '')
        language = data.get('language', 'en')
        has_tour_results = data.get('has_tour_results', False)
        tour_names = data.get('tour_names', [])
        user_context = data.get('user_context', '').lower()
        conversation_length = data.get('conversation_length', 0)
        
        lower_msg = ai_message.lower()
        
        # =====================================================
        # WHEN TOURS ARE BEING DISPLAYED - contextual follow-ups
        # =====================================================
        if has_tour_results and tour_names:
            suggestions = []
            
            # Detect what user originally asked about to tailor suggestions
            asked_about_family = any(w in user_context for w in ['family', 'kids', 'children', 'child'])
            asked_about_snorkeling = any(w in user_context for w in ['snorkel', 'reef', 'underwater', 'fish'])
            asked_about_beach = any(w in user_context for w in ['beach', 'whitehaven', 'sand'])
            asked_about_sailing = any(w in user_context for w in ['sail', 'boat', 'cruise'])
            asked_about_budget = any(w in user_context for w in ['budget', 'cheap', 'affordable', 'backpack'])
            asked_about_romantic = any(w in user_context for w in ['couple', 'romantic', 'honeymoon', 'anniversary'])
            asked_about_adventure = any(w in user_context for w in ['adventure', 'thrill', 'exciting', 'adrenaline'])
            asked_about_duration = any(w in user_context for w in ['day', 'half', 'full', 'overnight', 'hours', 'quick'])
            
            # First suggestion: Ask for AI's recommendation/opinion
            suggestions.append("🎯 Which do you recommend?")
            
            # Second: Context-specific follow-up questions
            if asked_about_family:
                suggestions.append("👶 Which is best for kids?")
            elif asked_about_snorkeling:
                suggestions.append("🤿 Which has the best snorkeling?")
            elif asked_about_beach:
                suggestions.append("🏖️ Which has the most beach time?")
            elif asked_about_sailing:
                suggestions.append("⛵ Best sailing experience?")
            elif asked_about_budget:
                suggestions.append("💎 Which is best value?")
            elif asked_about_romantic:
                suggestions.append("💕 Which is most romantic?")
            elif asked_about_adventure:
                suggestions.append("🔥 Which is most exciting?")
            elif asked_about_duration:
                suggestions.append("⏰ When do these depart?")
            else:
                suggestions.append("🍽️ What's included?")
            
            # Third: "Show me other options" - always useful
            suggestions.append("🔄 Show me other options")
            
            # Fourth: Alternative direction based on what WASN'T mentioned
            if not asked_about_budget:
                suggestions.append("💰 Something cheaper?")
            elif not asked_about_adventure:
                suggestions.append("🎉 Something more exciting?")
            elif not asked_about_duration:
                suggestions.append("⏱️ Something shorter?")
            else:
                suggestions.append("😌 Something more relaxed?")
            
            return jsonify({'suggestions': suggestions[:4]})
        
        # =====================================================
        # NO TOURS YET - gathering information stage
        # =====================================================
        
        # Welcome/opening message asking about activities
        if 'what would you like to experience' in lower_msg or 'what kind of' in lower_msg or ('reef' in lower_msg and 'beach' in lower_msg and '?' in ai_message):
            return jsonify({'suggestions': ["🐠 Reef & Snorkeling", "🏖️ Whitehaven Beach", "⛵ Sailing Adventure", "🌟 Show Popular"]})
        
        # Asking to narrow down after "popular" - wants activity preference
        if 'narrow it down' in lower_msg or 'prefer a specific activity' in lower_msg:
            return jsonify({'suggestions': ["🐠 Great Barrier Reef", "🏖️ Beach & Relaxation", "⛵ Sailing & Cruises", "🎯 Just show popular"]})
        
        # Asking about duration specifically
        if 'how long' in lower_msg or 'duration' in lower_msg or 'how much time' in lower_msg:
            return jsonify({'suggestions': ["⚡ A few hours", "🌅 Half day", "☀️ Full day", "🌙 Overnight"]})
        
        # Asking about group/who
        if 'who' in lower_msg and ('travel' in lower_msg or 'with' in lower_msg):
            return jsonify({'suggestions': ["👨‍👩‍👧 Family with kids", "💑 Just us two", "👥 Group of friends", "🧳 Solo traveler"]})
        
        # Asking about budget
        if 'budget' in lower_msg or 'spend' in lower_msg or 'price' in lower_msg:
            return jsonify({'suggestions': ["💵 Budget friendly", "💰 Mid-range", "💎 Premium experience", "🤷 Flexible budget"]})
        
        # Follow-up after first exchange (no tours yet)
        if conversation_length > 2:
            return jsonify({'suggestions': ["☀️ Full day trip", "🌅 Half day", "🌟 Show me popular tours", "🎯 Surprise me!"]})
        
        # Default: activity choices for new conversation
        return jsonify({'suggestions': ["🐠 Reef Tours", "🏖️ Beach Tours", "⛵ Sailing", "🌟 Popular Tours"]})
        
    except Exception as e:
        print(f"[SUGGESTIONS] Error: {e}")
        return jsonify({'suggestions': ["🐠 Reef Tours", "🏖️ Beach Tours", "⛵ Sailing", "🌟 Popular"]})

@app.route('/chat/detect-intent', methods=['POST'])
def detect_intent():
    """Use GPT to detect if user wants to book/open tour or just compare/ask questions"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        available_tours = data.get('available_tours', [])
        
        import openai
        from elevenlabs_tts import get_openai_client
        
        client = get_openai_client()
        
        tour_names = ', '.join(available_tours[:3])
        
        prompt = f"""Analyze this user message and determine their intent:

User message: "{user_message}"
Available tours: {tour_names}

Determine if the user wants to:
1. BOOK/OPEN a tour (they want to see details/book a specific tour)
2. COMPARE tours (asking about differences, comparisons, "vs", "which is better")
3. ASK A QUESTION (asking if a tour has something, does it include X, can it do Y)

Respond with JSON only:
{{
  "intent": "booking" | "comparison" | "question",
  "tour_name": "exact tour name if intent is booking, otherwise null"
}}

Examples:
- "tell me more about northern exposure" â†’ {{"intent": "booking", "tour_name": "Northern Exposure Eco Adventure"}}
- "what's the difference between northern and southern" â†’ {{"intent": "comparison", "tour_name": null}}
- "does northern exposure have snorkeling" â†’ {{"intent": "question", "tour_name": null}}
- "i want to book northern exposure" â†’ {{"intent": "booking", "tour_name": "Northern Exposure Eco Adventure"}}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an intent detection system. Respond with JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=100
        )
        
        result_text = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        import json
        intent_data = json.loads(result_text)
        
        return jsonify(intent_data)
        
    except Exception as e:
        print(f"Error detecting intent: {e}")
        return jsonify({'intent': 'question', 'tour_name': None})

@app.route('/chat', methods=['POST'])
def chat():
    """AI-powered chat endpoint for tour recommendations"""
    try:
        # Import price conversion for display
        from elevenlabs_tts import convert_price_for_display
        
        # Get active account for filtering hidden images
        active_account = get_active_account()
        
        data = request.get_json()
        user_message = data.get('message', '')
        language = data.get('language', 'en')
        conversation_history = data.get('history', [])
        previously_shown_tour_keys = set(data.get('previously_shown_tour_keys', []))
        
        print(f"\n[CHAT] CHAT REQUEST:")
        try:
            print(f"   User message: '{user_message}'")
        except UnicodeEncodeError:
            print(f"   User message: (contains special characters)")
        print(f"   Language: {language}")
        print(f"   History length: {len(conversation_history)} messages")
        print(f"   Previously shown tours: {len(previously_shown_tour_keys)} tours")
        for i, msg in enumerate(conversation_history[-3:], 1):  # Show last 3
            try:
                print(f"   History[{i}]: [{msg.get('role')}] {msg.get('content', '')[:50]}...")
            except UnicodeEncodeError:
                print(f"   History[{i}]: [{msg.get('role')}] (contains special characters)")
        
        # STEP 1: Quick intent check via LLM - works in any language
        # Determine if user has given enough info to search for tours
        import openai
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Build brief context
        context = ""
        for msg in conversation_history[-4:]:
            if msg.get('role') == 'user':
                context += f"User: {msg.get('content', '')[:100]}\n"
        
        # PRE-CHECK: Detect specific tour names or activities that should bypass 2-preference rule
        msg_lower = user_message.lower()
        
        # Specific activities that should ALWAYS trigger search
        specific_activities = ['jetski', 'jet ski', 'helicopter', 'scenic flight', 'seaplane', 
                              'skydive', 'skydiving', 'parasail', 'fishing charter', 'kayak tour',
                              'whale watch', 'sunset cruise', 'sunset sail',
                              'half day beach', 'full day beach', 'half day reef', 'full day reef',
                              'half day sailing', 'full day sailing', 'overnight sailing',
                              'multi-day sailing', 'half day snorkeling', 'full day snorkeling']
        
        # Known tour names that should trigger immediate search
        # NOTE: Do NOT include destinations like "whitehaven beach" - those need 2 preferences!
        # Only include SPECIFIC tour/boat names
        known_tour_names = [
            'atlantic clipper', 'camira', 'thundercat', 'ocean rafting', 'northern exposure',
            'southern lights', 'whitsunday bullet', 'reefworld', 'cruise whitsundays',
            'wings', 'mantaray', 'apollo', 'solway lass', 'prosail', 'prima', 'brampton',
            'summertime', 'whitsunday blue', 'illusions', 'blizzard', 'brittania', 'ice',
            'on ice', 'airlie adventure', 'island trek',
            'two island safari', 'heart reef', 'whitehaven express',
            'fury', 'zoe', 'matador', 'condor', 'clipper', 'adventurer', 'getaway'
        ]
        # REMOVED: 'whitehaven beach' (destination, not tour name - needs duration)
        # REMOVED: 'hayman', 'hamilton', 'daydream' (islands, not tour names - too generic)
        
        # Check for popular/recommended tours request
        popular_keywords = ['popular', 'popular tours', 'show popular', 'what\'s popular', 'best tours', 'top tours', 'recommended', 'favorites']
        wants_popular = any(kw in msg_lower for kw in popular_keywords)
        
        # Check if user is asking for something specific
        is_specific_request = (
            wants_popular or
            any(activity in msg_lower for activity in specific_activities) or
            any(tour_name in msg_lower for tour_name in known_tour_names)
        )
        
        if is_specific_request:
            safe_msg = user_message[:50].encode('ascii', 'ignore').decode('ascii')
            print(f"[CHAT] SPECIFIC REQUEST detected: '{safe_msg}' - bypassing 2-preference rule")
            should_search_tours = True
        else:
            # Use LLM to determine intent
            intent_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "user",
                    "content": f"""User: "{user_message}"
Context: {context if context else 'None'}

Does user have AT LEAST 2 PREFERENCES to search? Count across BOTH message AND context!

DETAIL CATEGORIES:
1. Activity (sailing, reef, snorkeling, diving, helicopter, jetski, wildlife, kayak, island)
2. Duration (full day, half day, multi-day, overnight, 2 days, quick/short)
3. Audience (family, couples, backpackers, kids, solo, romantic)
4. Budget (budget, cheap, affordable, luxury, premium)
5. Destination (whitehaven, great barrier reef, gbr)

EXCEPTION - SEARCH with just 1 detail (specific enough):
- "scenic flight", "helicopter tour", "seaplane" = SEARCH
- "jetski tour", "jet ski" = SEARCH
- "skydive", "skydiving" = SEARCH
- "fishing trip", "fishing charter" = SEARCH

SEARCH = 2+ details combined OR specific exception activities
ASK = Only 1 general detail (needs more info about duration/audience)

⚠️ IMPORTANT: Count accumulated details across BOTH message AND context!

ASK examples (ONLY 1 detail - MUST ASK about duration!):
- "reef tour" = ASK (activity only - ask about duration)
- "sailing" = ASK (activity only - ask about duration)
- "snorkeling" = ASK (activity only)
- "great barrier reef" = ASK (destination only - ask about duration)
- "whitehaven beach" = ASK (destination only)
- "diving" = ASK (activity only)
- "hello" = ASK (greeting)

SEARCH examples (2+ details OR specific exception):
- "full day reef tour" = SEARCH (activity + duration)
- "reef tour with family" = SEARCH (activity + audience)  
- "scenic flight" = SEARCH (specific exception)
- Context:"sailing" + Message:"full day" = SEARCH (combined = 2 details)
- "overnight sailing" = SEARCH (duration + activity)

⚠️ STRICT: Single activity/destination words ALONE = ASK!
The minimum is: 1 activity/destination + 1 duration OR 1 audience!

Reply ONLY: SEARCH or ASK"""
                }],
                max_tokens=5,
                temperature=0
            )
            
            intent = intent_response.choices[0].message.content.strip().upper()
            should_search_tours = 'SEARCH' in intent
            # Strip emojis for Windows console compatibility
            safe_msg = user_message[:40].encode('ascii', 'ignore').decode('ascii')
            print(f"[CHAT] Intent check: '{safe_msg}' -> {intent} (should_search={should_search_tours})")
        
        # Load all tours - MUST be outside the if/else so it's always available
        all_tours = load_all_tours(language, preview_account=active_account)
        
        # Detect if user wants DIFFERENT tours early (need this for LLM call)
        wants_different_early = any(phrase in user_message.lower() for phrase in [
            'other', 'different', 'else', 'alternative', 'another', 'more option',
            'something else', 'not these', 'not for me', 'show me more', 'any others'
        ])
        
        # FORCE search if user wants different tours (overrides preflight)
        if wants_different_early and previously_shown_tour_keys:
            print(f"[CHAT] User wants OTHER tours - forcing search (overriding preflight)")
            should_search_tours = True
        
        # Only do expensive LLM tour matching if preflight says we should
        if should_search_tours:
            print(f"[CHAT] Preflight says search tours - doing LLM tour matching...")
            # Pass excluded keys if user wants different tours
            exclude_for_llm = previously_shown_tour_keys if wants_different_early else set()
            if exclude_for_llm:
                print(f"[CHAT] User wants OTHER tours - excluding {len(exclude_for_llm)} previously shown from LLM")
            match_result = find_matching_tours_with_llm(user_message, conversation_history, all_tours, language, exclude_keys=exclude_for_llm)
            pre_fetched_tours = match_result.get('tours', [])
            match_quality = match_result.get('match_quality', 'none')
            user_wants = match_result.get('user_wants', '')
            match_explanation = match_result.get('explanation', '')
            
            # Check if user is asking for a SPECIFIC tour by name
            # Don't use RAG to "fill up" results when user wants one specific tour
            specific_tour_phrases = [
                'do you have the', 'is there a', 'what about the', 'tell me about the',
                'clipper', 'matador', 'solway', 'condor', 'kiana', 'apollo', 'camira',
                'reefworld', 'heart reef', 'northern exposure', 'southern lights'
            ]
            is_specific_tour_request = any(phrase in user_message.lower() for phrase in specific_tour_phrases)
            
            # SEMANTIC SEARCH ENHANCEMENT: Use RAG to fill up results when we have < 3 tours
            # But NOT when user is asking for a specific tour by name
            if len(pre_fetched_tours) < 3 and CHROMA_AVAILABLE and not is_specific_tour_request:
                needed = 3 - len(pre_fetched_tours)
                print(f"[CHAT] Only {len(pre_fetched_tours)} tours from LLM - using RAG to find {needed} more...")
                
                # Get semantic matches
                semantic_results = get_tours_by_semantic_search(
                    user_message, 
                    all_tours, 
                    max_results=8,
                    min_similarity=0.15
                )
                
                if semantic_results:
                    # Filter out tours we already have and previously shown
                    existing_keys = {t.get('key') for t in pre_fetched_tours}
                    if exclude_for_llm:
                        existing_keys.update(exclude_for_llm)
                    
                    new_tours = [t for t in semantic_results if t.get('key') not in existing_keys]
                    
                    if new_tours:
                        # Add semantic matches to fill up to 3 tours
                        tours_to_add = new_tours[:needed]
                        pre_fetched_tours.extend(tours_to_add)
                        
                        if match_quality != 'exact':
                            match_quality = 'semantic_enhanced'
                        match_explanation += f' (+ {len(tours_to_add)} similar tours from semantic search)'
                        
                        print(f"[CHAT] RAG added {len(tours_to_add)} similar tours:")
                        for t in tours_to_add:
                            sim = t.get('similarity_score', 0)
                            print(f"  + {t['name'][:40]} ({sim:.1%} match)")
            elif is_specific_tour_request:
                print(f"[CHAT] Specific tour request detected - not using RAG to fill results")
        else:
            print(f"[CHAT] Preflight says don't search - skipping LLM tour matching (will ask follow-up)")
            pre_fetched_tours = []
            match_quality = 'none'
            user_wants = 'needs more info'
            match_explanation = 'Not enough parameters to search'
        
        # Initialize total_matching_tours (will be set properly when tours are processed)
        total_matching_tours = 0
        
        # Store total count BEFORE any filtering/limiting
        total_matching_tours = len(pre_fetched_tours)
        
        # Use the early detection (already done before LLM call)
        wants_different = wants_different_early
        
        if wants_different:
            print(f"[CHAT] User wants DIFFERENT tours - already excluded from LLM results")
        
        # Filter out previously shown tours
        # ALWAYS filter if user wants different, otherwise only if we have enough alternatives
        if wants_different or len(pre_fetched_tours) > 3:
            original_count = len(pre_fetched_tours)
            pre_fetched_tours = [t for t in pre_fetched_tours if t.get('key') not in previously_shown_tour_keys]
            if len(pre_fetched_tours) < original_count:
                print(f"[CHAT] Filtered out {original_count - len(pre_fetched_tours)} previously shown tours")
        
        # COMPANY DIVERSITY: Don't show more than 2 tours from the same company
        # EXCEPTION: Skip diversity for specific activities (jetski, helicopter) where one company has all tours
        is_specific_activity_request = any(kw in user_message.lower() for kw in ['jetski', 'jet ski', 'helicopter', 'scenic flight', 'heli'])
        
        if len(pre_fetched_tours) > 3 and not is_specific_activity_request:
            company_counts = {}
            diverse_tours = []
            for tour in pre_fetched_tours:
                company = tour.get('company', 'unknown')
                if company_counts.get(company, 0) < 2:  # Max 2 per company
                    diverse_tours.append(tour)
                    company_counts[company] = company_counts.get(company, 0) + 1
            if len(diverse_tours) >= 3:
                pre_fetched_tours = diverse_tours
                print(f"[CHAT] Applied company diversity - {len(set(t.get('company') for t in pre_fetched_tours[:3]))} different companies")
        elif is_specific_activity_request:
            print(f"[CHAT] Skipping company diversity for specific activity request")
        
        # Check if this is a budget request - sort by price instead of promotion
        budget_keywords = ['budget', 'cheap', 'affordable', 'backpack', 'student', 'low cost', 'inexpensive']
        combined_context = user_message.lower() + ' ' + ' '.join(
            h.get('content', '').lower() for h in conversation_history if h.get('role') == 'user'
        )
        is_budget_request = any(kw in combined_context for kw in budget_keywords)
        
        # Separate promoted and non-promoted tours
        promoted_tours = [t for t in pre_fetched_tours if t.get('promotion')]
        non_promoted_tours = [t for t in pre_fetched_tours if not t.get('promotion')]
        
        if is_budget_request:
            # BUDGET REQUEST: Sort by price (cheapest first)
            def get_price_num(tour):
                price_str = str(tour.get('price_adult', '$9999'))
                try:
                    return int(''.join(filter(str.isdigit, price_str.split('.')[0])))
                except:
                    return 9999
            promoted_tours.sort(key=get_price_num)
            non_promoted_tours.sort(key=get_price_num)
            print(f"[CHAT] Budget request - sorted by price (cheapest first)")
        else:
            # NORMAL: Sort promoted by level, SHUFFLE non-promoted for variety
            promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2}
            promoted_tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
            random.shuffle(non_promoted_tours)  # Randomize non-promoted tours!
            print(f"[CHAT] Normal request - promoted first, non-promoted shuffled for variety")
        
        # Combine: promoted first, then non-promoted
        pre_fetched_tours = promoted_tours + non_promoted_tours
        
        # Limit to top 3
        pre_fetched_tours = pre_fetched_tours[:3]
        
        print(f"[CHAT] Showing 3 of {total_matching_tours} matching tours")
        
        if pre_fetched_tours:
            print(f"[OK] LLM matched {len(pre_fetched_tours)} tours ({match_quality}):")
            for t in pre_fetched_tours:
                promo = f" ðŸ”¥ {t.get('promotion')}" if t.get('promotion') else ""
                print(f"      - {t['name']}{promo}")
        else:
            print(f"[i] No tours matched (user wants: {user_wants})")
        
        # Build tour context
        tour_context = build_tour_context(language)
        
        # Build available tours list for AI (outside f-string to avoid dict literal issues)
        available_tours_list = []
        for category in tour_context['categories'].values():
            for t in category[:20]:  # Max 20 per category
                available_tours_list.append({
                    'name': t['name'],
                    'company': t['company'],
                    'price': t['price'],
                    'duration': t['duration'],
                    'key': t['key']
                })
        available_tours_json = json.dumps(available_tours_list, indent=2)
        
        # Build SPECIFIC tour data section if we pre-fetched tours
        specific_tours_section = ""
        if not pre_fetched_tours:
            # No specific tours yet - AI is in conversation mode, gathering preferences
            if user_wants and user_wants != "not requesting tours":
                # User wanted something but we couldn't find it
                specific_tours_section = f"""

⚠️ NO EXACT MATCHES FOR "{user_wants}" - BUT YOU CAN SUGGEST ALTERNATIVES!

YOU MUST NOT:
- Make up tour names or describe imaginary tours
- List numbered tours without using [TOUR:key] tags

YOU SHOULD:
1. Acknowledge we don't have tours specifically for that criteria
2. Suggest REAL alternatives by using [FILTER:...] to show actual tours!
3. Recommend speaking to staff at counter for specialized requirements

IMPORTANT: If you suggest scenic flights, sailing, etc - USE [FILTER:...] TO SHOW THEM!

Example good response for accessibility question:
"While I don't have tours specifically tagged for accessibility, I can show you some options that might work well! 🌟

For a relaxing experience with minimal walking:
- **Scenic flights** let you see everything from the air - no physical activity needed!
- **Sailing cruises** offer comfortable deck seating with stunning views

Let me show you our scenic flights:
[FILTER:{{"activity":"scenic_flight"}}]

Or if you'd prefer a relaxing sailing experience:
[FILTER:{{"activity":"sailing"}}]

I'd also recommend chatting with our staff at the counter - they can contact operators directly about specific accessibility accommodations!"

KEY: Always use [FILTER:...] when mentioning tour types so REAL tours are displayed!
"""
            else:
                specific_tours_section = """

NOTE: No specific tours have been identified yet. Continue gathering user preferences!
When you have enough info, the system will provide specific tours to describe.
For now, ask engaging questions to understand what kind of experience they want.

⚠️ IMPORTANT: Do NOT describe or name any specific tours until tours are provided to you below!
"""
        
        if pre_fetched_tours:
            # Add context about match quality
            match_intro = ""
            
            # Don't tell AI how many total - just describe the top options
            if len(pre_fetched_tours) <= 3:
                match_intro = f"""
[OK] Here are great options for {user_wants}. Describe them all enthusiastically!
"""
            if match_quality == 'close':
                match_intro = f"""
[!] NOTE: User asked for "{user_wants}" - these are CLOSE MATCHES but not exact.
Acknowledge what they wanted and explain how these tours are similar/related.
"""
            elif match_quality == 'alternative':
                match_intro = f"""
[!] NOTE: User asked for "{user_wants}" but we don't have exact matches.
These are ALTERNATIVE suggestions. Apologize that we don't have exactly what they wanted,
then enthusiastically present these alternatives.
"""
            
            specific_tours_section = f"""

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ðŸš¨ CRITICAL: YOU MUST DESCRIBE THESE EXACT TOURS IN THIS EXACT ORDER!
DO NOT substitute different tours. DO NOT change the order. DO NOT make up tour names!
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
{match_intro}"""
            for i, tour in enumerate(pre_fetched_tours, 1):
                promo_badge = ""
                if tour.get('promotion') == 'popular':
                    promo_badge = " ðŸ”¥ POPULAR - Emphasize this is a top pick!"
                elif tour.get('promotion') == 'featured':
                    promo_badge = " â­ FEATURED"
                elif tour.get('promotion') == 'best_value':
                    promo_badge = " ðŸ’Ž BEST VALUE"
                
                highlights = tour.get('highlights', '')[:400] if tour.get('highlights') else 'Amazing experience'
                includes = tour.get('includes', '')[:250] if tour.get('includes') else ''
                description = tour.get('description', '')[:300] if tour.get('description') else ''
                
                specific_tours_section += f"""
â”â”â” TOUR #{i} (describe this as number {i}) â”â”â”
NAME: "{tour['name']}" â† USE THIS EXACT NAME
{promo_badge}
Company: {tour.get('company_name', tour.get('company', ''))}
Price: {tour.get('price_adult', 'Contact for price')}
Duration: {tour.get('duration', 'Full Day')}
Description: {description}
Highlights: {highlights}
Includes: {includes}
"""
            # Build the exact tour names for the template
            tour1_name = pre_fetched_tours[0]['name']
            tour2_name = pre_fetched_tours[1]['name'] if len(pre_fetched_tours) > 1 else 'Tour 2'
            tour3_name = pre_fetched_tours[2]['name'] if len(pre_fetched_tours) > 2 else 'Tour 3'
            
            specific_tours_section += f"""
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
ðŸš¨ðŸš¨ðŸš¨ CRITICAL: YOU MUST DESCRIBE THESE TOURS NOW! ðŸš¨ðŸš¨ðŸš¨
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

DO NOT ask for more preferences! Tour cards are ALREADY being shown to the user!
If you ask "how long do you have?" but show cards, it looks broken. DESCRIBE THE TOURS!

FORBIDDEN (YOUR OUTPUT WILL BE REJECTED):
- DO NOT make up tour names - only use the exact names from the tours listed above
- DO NOT create generic names like "Whitsunday Sailing Adventure" or "3-Day Reef Tour"
- DO NOT describe tours that aren't in the list above
- ONLY use the exact tour names provided: "{tour1_name}", "{tour2_name}", "{tour3_name}"

YOUR OUTPUT FORMAT (COPY THIS STRUCTURE EXACTLY):
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

"[PERSONALIZED INTRO - 1 sentence acknowledging EXACTLY what they asked for, e.g. 'Meeting fellow backpackers on a sailing adventure? I've got perfect options for you!' or 'Great choice wanting to explore the reef with family!'] ðŸŒŠ

1. **{tour1_name}** - [Write 2-3 exciting sentences about THIS tour. Highlight why it matches what THEY asked for!]

2. **{tour2_name}** - [Write 2-3 exciting sentences about THIS tour. Connect it to their specific request!]

3. **{tour3_name}** - [Write 2-3 exciting sentences about THIS tour. Show why it's perfect for them!]

Would you like more details on any of these? ðŸŒŸ"

ðŸš¨ CRITICAL RULES:
- ALWAYS describe the tours above - they are being shown as cards!
- Use EXACTLY these tour names: "{tour1_name}", "{tour2_name}", "{tour3_name}"
- Do NOT ask "how long" or "what duration" - just describe the tours!
- Do NOT substitute different tours!
- Do NOT reorder the tours!
- The intro must be short (1 sentence max) so TTS correctly highlights tour 1 for chunk 2
"""
        
        # Prepare system message with tour knowledge
        # Only include conversation strategy if no tours pre-fetched
        if pre_fetched_tours:
            conversation_strategy = """
⚠️ TOURS ARE ALREADY SELECTED BELOW - SKIP ALL QUESTIONS AND DESCRIBE THEM!
Do NOT ask "how long?" or "what type?" - THE TOURS ARE ALREADY CHOSEN!
Just write enthusiastic descriptions for each tour shown below."""
        else:
            conversation_strategy = """
CONVERSATION STRATEGY - RECOMMEND AFTER 2 PREFERENCES:
1. **GATHER 2 PREFERENCES** before recommending (e.g., activity + duration, OR activity + group type)
2. **ONCE YOU HAVE 2 PREFERENCES → USE [FILTER:...] IMMEDIATELY!**
3. **NEVER SAY "Let me show you..." WITHOUT INCLUDING [FILTER:...] in the SAME message!**
4. Be SUPER enthusiastic - you're a passionate local who LOVES the Whitsundays!
5. **ALWAYS use [FILTER:{{...}}] syntax to show tours** - this is REQUIRED!
6. Example flow:
   - User: "sailing tours" (1 preference) → Ask about duration
   - User: "full day" (2 preferences) → MUST include [FILTER:{{"duration":"full_day","activity":"island_tours"}}]"""
        
        # Language names for the system prompt
        language_names = {
            'en': 'English', 'zh': 'Chinese (Simplified)', 'ja': 'Japanese',
            'ko': 'Korean', 'de': 'German', 'fr': 'French', 'es': 'Spanish', 'hi': 'Hindi'
        }
        response_language = language_names.get(language, 'English')
        
        system_message = f"""You are a friendly and knowledgeable tour assistant for the Whitsunday Islands in Queensland, Australia. 

**IMPORTANT: RESPOND IN {response_language.upper()}!** The user has selected {response_language} as their language.
All your responses, questions, and tour descriptions MUST be in {response_language}.

You help visitors discover the perfect tours through a guided conversation. You have access to {tour_context['total_tours']} amazing tours.

YOUR ROLE: Act like a helpful local expert who guides tourists step-by-step to find their ideal tour. Keep it conversational and natural!

**GREAT BARRIER REEF vs CORAL REEF - IMPORTANT DISTINCTION:**
- "Great Barrier Reef" or "GBR" = Tours that actually GO to the outer Great Barrier Reef (Reefworld, Hardy Reef, Knuckle Reef, outer reef platforms)
- NOT the same as tours with "coral reef snorkeling" - many tours snorkel at fringing reefs near islands but don't visit the actual GBR
- If user asks for "Great Barrier Reef", ONLY recommend tours that explicitly visit the outer reef
- Tours like "Southern Lights" or "Northern Exposure" have coral snorkeling but do NOT go to the actual Great Barrier Reef

Our tour categories:
- Great Barrier Reef Tours: {len(tour_context['categories']['reef'])} tours (snorkeling, diving, reef exploration)
- Whitehaven Beach Tours: {len(tour_context['categories']['whitehaven'])} tours (world-famous white silica sand beach)
- Sailing & Cruises: {len(tour_context['categories']['sailing'])} tours (day sails, sunset cruises, multi-day adventures)
- Diving & Snorkeling: {len(tour_context['categories']['diving'])} tours (beginners to advanced)
- Scenic Tours: {len(tour_context['categories']['scenic'])} tours (helicopter, seaplane, scenic flights)

**FEATURED & POPULAR TOURS** (PRIORITIZE THESE! When these match user preferences, recommend them FIRST and be EXTRA enthusiastic!):
{build_promoted_tours_section(tour_context)}

[!] **CRITICAL: Give 2-3 sentence descriptions of EACH tour - never just list names!**

**IF SPECIFIC TOURS ARE PROVIDED BELOW**: YOU MUST DESCRIBE THEM! Do NOT ask follow-up questions!
**IF NO SPECIFIC TOURS PROVIDED**: Ask follow-up questions to gather preferences first.

{conversation_strategy}

**YOU ARE REPLACING A REAL PERSON!** 
- Be warm, personable, and genuinely excited about these tours
- Use emojis sparingly but effectively (🌊 🐠 ✨ 🏝️ 🚤 🌅)
- Give DETAILED 3-4 sentence descriptions that SELL each tour
- Highlight what makes each tour special and why they'll love it
- Create excitement and urgency - these are once-in-a-lifetime experiences!
- Sound like a friend who's been on these tours and can't wait for them to go too

**NEVER ASK ABOUT BUDGET/PRICE** - Users don't want to say prices out loud. They'll pick what fits their budget.

**ADD CONTEXT & PERSONALITY**: 
- "Great Barrier Reef? One of the 7 natural wonders! ðŸŒŠ"
- "Whitehaven Beach has the world's purest silica sand - perfect for photos! ðŸ“¸"
- "Multi-day trips let you see it all - sunrise, sunset, and the stars! âœ¨"

**ENCOURAGE SPECIFICITY**: Ask open-ended follow-ups like:
- "What would make this trip perfect for you?"
- "Any must-do activities?"
- "Celebrating anything special?"

**HANDLING "OTHER OPTIONS" / "SOMETHING ELSE" REQUESTS**:
When user says "other options", "something else", "different tours", "alternatives", "not these", "any others", etc.:
- Understand they want DIFFERENT tours than already shown
- The system will automatically exclude previously shown tours
- Show fresh alternatives that still match their criteria
- DON'T repeat any tours you mentioned before!

Keep responses SHORT but ALWAYS include tour recommendations once you have 2 preferences!

**WHEN TO RECOMMEND TOURS**: Once user has given 2 preferences!
- 1 preference (e.g., "reef") â†’ Ask ONE follow-up question (duration or group type)
- 2 preferences (e.g., "reef" + "full day") â†’ **USE [FILTER:...] IMMEDIATELY!**
- User gives 2+ preferences in one message â†’ **USE [FILTER:...] IMMEDIATELY!**
- **CRITICAL: You MUST include [FILTER:{{...}}] to show any tours!** 
- Without [FILTER:...], NO TOURS WILL BE DISPLAYED even if you describe them!

**NEVER GIVE EMPTY RESPONSES:**
- If you say "Let me show you..." or "Here are some options..." â†’ YOU MUST include [FILTER:...] in the SAME message
- If you commit to showing tours, SHOW THEM - don't make the user wait or ask again
- If no tours match, be HONEST: "I couldn't find exact matches, but here are similar options: [FILTER:...]"

**EXAMPLE - CORRECT:**
"Speed boat tours are thrilling! ðŸš¤ [FILTER:{{"duration":"full_day","activity":"scenic_adventure"}}]"

**EXAMPLE - WRONG (NO TOURS WILL SHOW!):**
"Speed boat tours sound exciting! Let me find some for you. Hang tight!" (MISSING [FILTER:...] = NOTHING HAPPENS!)

**QUICK REPLIES**: When asking multiple-choice questions, you can suggest options using [OPTIONS:option1,option2,option3] format.
Example: "How long can you be away? [OPTIONS:Half Day,Full Day,Multi-day]"

**CRITICAL MATCHING RULES**:
- If user said "multi-day", ONLY recommend multi-day/overnight tours (2+ days)
- If user said "full-day", ONLY recommend full-day tours  
- If user said "half-day", ONLY recommend half-day tours
- If user wants "cheapest", find the LOWEST PRICE tours that match ALL their other preferences
- STRICTLY match ALL collected preferences - duration, vibe, interests
- DO NOT recommend tours that don't match what they asked for!
- **NEVER MAKE UP TOUR NAMES!** You can ONLY describe tours that are explicitly listed in the "TOURS TO DESCRIBE" section below!
- If no tours are listed below, DO NOT describe any tours - just have a conversation and suggest alternatives
- INVENTED tours like "Whitehaven Beach Scenic Flight" or "Sailing Tours" (generic) are FORBIDDEN - these will confuse customers!
- **ALWAYS use [FILTER:...] tags when you have enough info (activity + duration OR just activity if duration is "any")** - this is REQUIRED to show tours!

**TWO WAYS TO RESPOND**:

**METHOD 1 - Use Filter System (PREFERRED - USE THIS 90% OF THE TIME):**
When you have enough info about activity/interest (with or without duration), USE FILTERS to show ALL matching tours!
If user says "any is good" for duration, still use [FILTER:...] with just the activity - the system will show tours of all durations!
**YOU MUST USE [FILTER:...] TAGS - DO NOT make up tour names! Only describe tours that actually exist!**

[!] **CRITICAL: When using [FILTER:...], you MUST write a COMPLETE response with numbered descriptions!**
The TTS reads your text out loud and highlights tour cards in sync. Each numbered item (1. 2. 3.) highlights the corresponding card.

**PERFECT EXAMPLE with [FILTER:]:**
"Full-day Whitehaven Beach tours are absolutely incredible! ðŸï¸ Let me show you some amazing options! [FILTER:{{"duration":"full_day","activity":"whitehaven_beach"}}]

1. **Your first option** takes you to the world-famous Whitehaven Beach with its stunning white silica sand! You'll have plenty of time to swim, relax, and take incredible photos. This is a must-do experience! âœ¨

2. **This next tour** combines beach time with snorkeling at pristine coral reefs! You'll explore underwater gardens teeming with colorful fish before relaxing on the beach. Perfect for adventure lovers! ðŸ 

3. **Finally, this option** offers a more intimate experience with smaller group sizes and extra time at Hill Inlet lookout! You'll capture those iconic turquoise water photos and have a magical day. ðŸ“¸

Would you like more details on any of these? ðŸŒŸ"

**BAD EXAMPLE (NO TOUR CARDS WILL HIGHLIGHT!):**
"Here are some Whitehaven Beach tours: [FILTER:{{"activity":"whitehaven_beach"}}]"

Return filter criteria in this format: [FILTER:{{"duration":"X","activity":"Y"}}]

**CRITICAL: Map user interests to activities correctly:**
- "Great Barrier Reef", "reef", "snorkeling", "diving", "coral" â†’ activity: "great_barrier_reef"
- "Whitehaven Beach", "beach", "white sand" â†’ activity: "whitehaven_beach"  
- "Sailing", "cruise", "island hopping" â†’ activity: "island_tours"
- Specific requests like "jet ski", "helicopter", "speed boat" â†’ system searches directly for those keywords

**WHEN TO USE FILTERS (REQUIRED to show tours!):**
[OK] "multi-day diving and snorkeling" â†’ [FILTER:{{"duration":"multi_day","activity":"great_barrier_reef"}}]
[OK] "full-day reef tour" â†’ [FILTER:{{"duration":"full_day","activity":"great_barrier_reef"}}]
[OK] "half-day beach tour" â†’ [FILTER:{{"duration":"half_day","activity":"whitehaven_beach"}}]
[OK] "full-day sailing" â†’ [FILTER:{{"duration":"full_day","activity":"island_tours"}}]
[OK] "family-friendly full-day tour" â†’ [FILTER:{{"duration":"full_day","family":true}}]
[OK] "reef tour with equipment provided" â†’ [FILTER:{{"activity":"great_barrier_reef","equipment":true}}]

NOTE: For specific tour types like "jet ski tours", "helicopter tours", "speed boat tours" - the system automatically
searches for tours containing those keywords. Just describe the pre-fetched tours provided to you!

Available filter options:
- duration: "half_day", "full_day", "multi_day"
- activity: "great_barrier_reef", "whitehaven_beach", "island_tours"
- family: true (ONLY use when user specifically has children/kids - this filters to family-friendly tours only)
- meals: true (meals included)
- equipment: true (equipment provided)

**HOW TO RECOMMEND TOURS - NUMBERED LIST FORMAT IS REQUIRED!**
The TTS system reads your response out loud and highlights each tour card as it speaks. For this to work, you MUST use this EXACT numbered list format:

[OK] CORRECT FORMAT (REQUIRED!):
"[Exciting 2-3 sentence intro paragraph about the activity type] â›µ

1. **First Tour Name** - [2-3 exciting sentences describing THIS tour, what makes it special, what they'll experience]

2. **Second Tour Name** - [2-3 exciting sentences about this tour]

3. **Third Tour Name** - [2-3 exciting sentences about this tour]

Would you like more details on any of these? ðŸŒŸ"

**CRITICAL RULES FOR TTS HIGHLIGHTING TO WORK:**
- [!] ALWAYS use numbered list format (1. 2. 3.) - this is how TTS knows when to highlight each card!
- Start each tour with the NUMBER followed by period: "1. " "2. " "3. "
- Use **bold** for tour names
- Each tour description MUST be 2-3 complete sentences (not just a few words!)
- Write descriptions that SELL the experience - this is what users hear!
- Include emojis throughout for personality! â›µðŸï¸ðŸŒŠâœ¨ðŸ 
- The intro paragraph plays first, THEN each numbered item highlights its corresponding tour card
- ALWAYS end with a follow-up question

**METHOD 2 - Recommend Specific Tours (RARE - only when filters don't work):**
Use this ONLY when user asks for something that doesn't map to our filters.

[!] **WHEN TO USE [FILTER:...]:**
- "overnight sailing" â†’ [FILTER:{{"duration":"multi_day","activity":"island_tours"}}]
- "full day reef tour" â†’ [FILTER:{{"duration":"full_day","activity":"great_barrier_reef"}}]
- "Whitehaven beach tours" â†’ [FILTER:{{"activity":"whitehaven_beach"}}]

[!] **IMPORTANT: When using [FILTER:...], you MUST STILL write a FULL numbered list with descriptions!**
The [FILTER:...] tag just tells the system WHICH tours to show - YOU still need to write the text that TTS speaks!

**CRITICAL TOUR DESCRIPTION RULES - YOU ARE REPLACING A REAL PERSON:**
When describing tours, you MUST give a compelling 3-4 sentence pitch for EACH tour that:
- Makes it sound exciting and unmissable!
- Highlights unique selling points (best views, exclusive access, amazing food, etc.)
- Creates urgency and FOMO ("one of Australia's most incredible experiences!")
- Uses vivid, sensory language ("crystal-clear waters", "powdery white sand", "breathtaking aerial views")
- Matches the tour to what the user specifically asked for
{specific_tours_section}
**DO NOT** give boring one-line descriptions. Your job is to SELL these experiences and make visitors excited to book!
Be conversational, ask questions, and help them discover their perfect adventure!"""

        # Build messages for OpenAI
        messages = [{"role": "system", "content": system_message}]
        
        # Add conversation history
        for msg in conversation_history:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": msg.get('content', '')
            })
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Use gpt-4o when we have pre-fetched tours (needs to follow exact names)
        # Use gpt-4o-mini for simple conversations (faster)
        model = "gpt-4o" if pre_fetched_tours else "gpt-4o-mini"
        
        print(f"\n[OPENAI] SENDING TO OPENAI:")
        print(f"   Model: {model}")
        print(f"   Total messages: {len(messages)}")
        print(f"   System message: {len(system_message)} chars")
        if pre_fetched_tours:
            print(f"   Pre-fetched tour names in prompt:")
            for t in pre_fetched_tours:
                in_prompt = t['name'] in system_message
                print(f"      - '{t['name']}' -> {'IN PROMPT' if in_prompt else 'MISSING!'}")
        for i, msg in enumerate(messages[1:], 1):  # Skip system message
            try:
                print(f"   Message {i}: [{msg['role']}] {msg['content'][:60]}...")
            except UnicodeEncodeError:
                print(f"   Message {i}: [{msg['role']}] (contains special characters)")
        
        # Call OpenAI
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=800,
            temperature=0.7
        )
        
        ai_message = response.choices[0].message.content
        
        # Check for specific tour tags FIRST (takes priority over filters)
        tour_pattern = r'\[TOUR:([a-zA-Z0-9\-_]+__[a-zA-Z0-9_]+)\]'
        tour_matches = re.findall(tour_pattern, ai_message)
        
        # Check if AI wants to use filter system
        filter_pattern = r'\[FILTER:({[^}]+})\]'
        filter_match = re.search(filter_pattern, ai_message)
        
        # Check if AI provided quick reply options
        options_pattern = r'\[OPTIONS:([^\]]+)\]'
        options_match = re.search(options_pattern, ai_message)
        quick_reply_options = None
        
        if options_match:
            # Parse options (comma-separated)
            options_str = options_match.group(1)
            options_list = [opt.strip() for opt in options_str.split(',')]
            quick_reply_options = [{'text': opt, 'value': opt} for opt in options_list]
            # Remove options marker from message
            ai_message = re.sub(options_pattern, '', ai_message).strip()
            print(f"ðŸ“‹ Quick reply options: {quick_reply_options}")
        
        # Safe print that handles emojis on Windows
        try:
            print(f"AI Response: {ai_message[:200]}...")
        except UnicodeEncodeError:
            print(f"AI Response: {ai_message[:200].encode('ascii', 'replace').decode('ascii')}...")
        
        # Extract previously shown tour keys from conversation history responses
        # Look for tour_keys in previous assistant responses (if stored)
        # For now, we'll extract from the response data structure
        # In a future enhancement, we could store tour_keys in conversation history metadata
        previously_shown_tour_keys = set()
        
        # PRIORITY: Use specific [TOUR:] tags if provided (they match the AI's descriptions!)
        if tour_matches:
            print(f"[->] AI recommending specific tours with [TOUR:] tags")
            print(f"   Found {len(tour_matches)} tour keys: {tour_matches}")
            
            # Get full tour details for the specified tours
            tours = load_all_tours(language)
            tour_details = []
            skipped_tours = []
            
            # Check if user is asking for more information about a specific tour
            # If so, don't skip it even if it was shown before
            user_msg_lower = user_message.lower()
            is_asking_about_tour = any(
                phrase in user_msg_lower for phrase in [
                    'more info', 'more information', 'tell me more', 'learn more', 
                    'details about', 'about the', 'what about', 'how about',
                    'difference between', 'compare', 'comparison', 'vs', 'versus',
                    'does it have', 'does it include', 'can it', 'is it'
                ]
            )
            
            for tour_key in tour_matches:
                # Only skip if user is NOT explicitly asking about this tour
                if tour_key in previously_shown_tour_keys and not is_asking_about_tour:
                    print(f"   [skip] Skipping previously shown tour: {tour_key}")
                    skipped_tours.append(tour_key)
                    continue
                    
                tour = next((t for t in tours if t.get('key') == tour_key), None)
                if tour:
                    tour_copy = tour.copy()
                    # Load images lazily for this tour (with account-specific hidden images filtered)
                    thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=5, account_username=active_account)
                    tour_copy['thumbnail'] = thumb
                    tour_copy['gallery'] = gallery
                    tour_copy['uses_placeholder_images'] = uses_placeholder
                    if tour_copy.get('price_adult'):
                        tour_copy['price_adult'] = convert_price_for_display(tour_copy['price_adult'], language)
                    if tour_copy.get('price_child'):
                        tour_copy['price_child'] = convert_price_for_display(tour_copy['price_child'], language)
                    tour_details.append(tour_copy)
                    print(f"   [OK] Found tour: {tour.get('name')} ({tour_key})")
                else:
                    print(f"   [ERR] Tour not found: {tour_key}")
            
            # Note: Alternative fetching is now handled by LLM-based matching
            
            # Remove both tour markers AND filter markers from display message
            display_message = re.sub(tour_pattern, '', ai_message).strip()
            display_message = re.sub(filter_pattern, '', display_message).strip()
            display_message = convert_price_for_display(display_message, language)
            
            # Limit to 3 tours
            tour_details = tour_details[:3]
            
            response_data = {
                'success': True,
                'message': display_message,
                'recommended_tours': tour_details,
                'tour_keys': [t['key'] for t in tour_details],
                'used_filters': False,
                'quick_reply_options': quick_reply_options,
                'total_matching_tours': total_matching_tours
            }
            
        elif filter_match or pre_fetched_tours:
            # We have tours to show! Either from [FILTER:] tag or pre-fetched
            print(f"[->] Returning tour recommendations")
            try:
                # Use pre-fetched tours if available
                if pre_fetched_tours:
                    print(f"   Using {len(pre_fetched_tours)} pre-fetched tours")
                    filtered_tours = pre_fetched_tours
                elif filter_match:
                    filter_criteria = json.loads(filter_match.group(1))
                    print(f"   Filter criteria from AI: {filter_criteria}")
                    
                    # Pass user message context to apply_filters for better matching
                    import threading
                    threading.current_thread().user_message_context = user_message.lower()
                    
                    filtered_tours = apply_filters(load_all_tours(language), filter_criteria, user_message_context=user_message.lower(), conversation_history=conversation_history)
                    
                    # Sort by promotion status
                    promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
                    filtered_tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
                else:
                    filtered_tours = []
                
                # Filter out previously shown tours (only if we have plenty of alternatives)
                original_count = len(filtered_tours)
                if len(filtered_tours) > 3:
                    filtered_tours = [t for t in filtered_tours if t.get('key') not in previously_shown_tour_keys]
                    if len(filtered_tours) < original_count:
                        print(f"   Filtered out {original_count - len(filtered_tours)} previously shown tours")
                
                # Always limit to 3 tours for display
                filtered_tours = filtered_tours[:3]
                
                # CRITICAL: If no tours match the filter, return empty
                if len(filtered_tours) == 0:
                    print(f"   [!] No tours match the filter criteria!")
                    display_message = re.sub(filter_pattern, '', ai_message).strip() if filter_match else ai_message
                    display_message = convert_price_for_display(display_message, language)
                    
                    response_data = {
                        'success': True,
                        'message': display_message,
                        'recommended_tours': [],
                        'tour_keys': [],
                        'used_filters': True,
                        'filter_count': 0,
                        'quick_reply_options': quick_reply_options,
                        'total_matching_tours': 0
                    }
                    return jsonify(response_data)
                else:
                    print(f"   Returning {len(filtered_tours)} tours:")
                    for t in filtered_tours:
                        promo = f" [PROMO] {t.get('promotion')}" if t.get('promotion') else ""
                        print(f"      - {t['name']}{promo}")
                
                # Convert prices and load images for display (lazy loading)
                tour_details = []
                # print(f"[LAZY-IMAGES] Loading images for {len(filtered_tours)} tours...")  # Disabled for cleaner logs
                for tour in filtered_tours:
                    tour_copy = tour.copy()
                    # Load images lazily for this tour (with account-specific hidden images filtered)
                    thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=5, account_username=active_account)
                    tour_copy['thumbnail'] = thumb
                    tour_copy['gallery'] = gallery
                    tour_copy['uses_placeholder_images'] = uses_placeholder
                    if tour_copy.get('price_adult'):
                        tour_copy['price_adult'] = convert_price_for_display(tour_copy['price_adult'], language)
                    if tour_copy.get('price_child'):
                        tour_copy['price_child'] = convert_price_for_display(tour_copy['price_child'], language)
                    tour_details.append(tour_copy)
                
                display_message = re.sub(filter_pattern, '', ai_message).strip() if filter_match else ai_message
                display_message = convert_price_for_display(display_message, language)
                
                if '?' not in display_message[-50:]:
                    display_message = display_message.rstrip() + "\n\nWould you like more details on any of these?"
                
                response_data = {
                    'success': True,
                    'message': display_message,
                    'recommended_tours': tour_details,
                    'tour_keys': [t['key'] for t in tour_details],
                    'used_filters': True,
                    'filter_count': len(filtered_tours),
                        'quick_reply_options': quick_reply_options,
                        'total_matching_tours': total_matching_tours
                }
                
            except Exception as e:
                print(f"[ERR] Error parsing filter criteria: {e}")
                filter_match = None
        
        # Only reach here if neither [TOUR:] tags, [FILTER:], nor pre_fetched_tours were found/worked
        if not tour_matches and not filter_match and not pre_fetched_tours:
            # Check if AI response contains numbered tour recommendations (1. **Tour Name**)
            # This happens when AI apologizes and gives new suggestions without using [FILTER:]
            numbered_tour_pattern = r'\d+\.\s*\*\*[^*]+\*\*'
            has_numbered_tours = re.search(numbered_tour_pattern, ai_message)
            
            if has_numbered_tours:
                print(f"[!] AI response has numbered tours but no [FILTER:] - doing late tour search...")
                # Try to search for tours based on conversation context
                late_match = find_matching_tours_with_llm(user_message, conversation_history, all_tours, language)
                late_tours = late_match.get('tours', [])
                
                if late_tours:
                    print(f"   Found {len(late_tours)} tours via late search")
                    # Limit and convert prices
                    late_tours = late_tours[:3]
                    tour_details = []
                    # print(f"[LAZY-IMAGES] Loading images for {len(late_tours)} late-search tours...")  # Disabled for cleaner logs
                    for tour in late_tours:
                        tour_copy = tour.copy()
                        # Load images lazily for this tour (with account-specific hidden images filtered)
                        thumb, gallery, uses_placeholder = load_tour_images(tour, max_images=5, account_username=active_account)
                        tour_copy['thumbnail'] = thumb
                        tour_copy['gallery'] = gallery
                        tour_copy['uses_placeholder_images'] = uses_placeholder
                        if tour_copy.get('price_adult'):
                            tour_copy['price_adult'] = convert_price_for_display(tour_copy['price_adult'], language)
                        tour_details.append(tour_copy)
                    
                    display_message = convert_price_for_display(ai_message, language)
                    
                    response_data = {
                        'success': True,
                        'message': display_message,
                        'recommended_tours': tour_details,
                        'tour_keys': [t['key'] for t in tour_details],
                        'used_filters': False,
                        'quick_reply_options': quick_reply_options,
                        'total_matching_tours': len(late_match.get('tours', []))
                    }
                    
                    print(f"[SEND] SENDING TO FRONTEND (late search):")
                    print(f"   Tours: {[t.get('name') for t in tour_details]}")
                    return jsonify(response_data)
            
            print(f"[BOT] AI response has no tour recommendations")
            
            # Just return the message as-is (conversational response)
            display_message = convert_price_for_display(ai_message, language)
            
            response_data = {
                'success': True,
                'message': display_message,
                'recommended_tours': [],
                'tour_keys': [],
                'used_filters': False,
                'quick_reply_options': quick_reply_options,
                'total_matching_tours': 0
            }
        
        print(f"\n[SEND] SENDING TO FRONTEND:")
        print(f"   Success: {response_data['success']}")
        print(f"   Message length: {len(response_data['message'])} chars")
        print(f"   Tours to send: {len(response_data['recommended_tours'])}")
        for i, tour in enumerate(response_data['recommended_tours'], 1):
            print(f"   Tour {i}: {tour.get('name')} ({tour.get('key')})")
        print(f"   JSON size: {len(str(response_data))} bytes\n")
        
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        print(f"Error in chat endpoint: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': "I'm having trouble right now. Please try the filter questions or browse all tours."
        }), 500

# =====================================================================
# QR CODE TRANSFER SYSTEM
# =====================================================================

# In-memory session storage (upgrade to database for production)
recommendation_sessions = {}

@app.route('/api/create-recommendation-session', methods=['POST'])
def create_recommendation_session():
    """Create a shareable session for tour recommendations"""
    try:
        data = request.get_json()
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())[:8]  # Short UUID for clean URLs
        
        # Store session data
        recommendation_sessions[session_id] = {
            'tours': data.get('tours', []),
            'preferences': data.get('preferences', {}),
            'chat_summary': data.get('chat_summary', ''),
            'created_at': time.time(),
            'language': data.get('language', 'en')
        }
        
        # Generate URL for recommendations page
        base_url = request.host_url.rstrip('/')
        recommendations_url = f"{base_url}/recommendations/{session_id}"
        
        print(f"[OK] Created session {session_id} with {len(data.get('tours', []))} tours")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'url': recommendations_url
        })
        
    except Exception as e:
        print(f"[ERR] Error creating session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/generate-qr/<session_id>')
def generate_qr_code(session_id):
    """Generate QR code for a recommendation session"""
    try:
        # Check if session exists
        if session_id not in recommendation_sessions:
            return jsonify({'error': 'Session not found'}), 404
        
        # Generate URL
        base_url = request.host_url.rstrip('/')
        recommendations_url = f"{base_url}/recommendations/{session_id}"
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(recommendations_url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
        
    except Exception as e:
        print(f"[ERR] Error generating QR code: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-qr')
def generate_qr_from_url():
    """Generate QR code for any URL"""
    try:
        url = request.args.get('url')
        if not url:
            return jsonify({'error': 'URL parameter required'}), 400
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to bytes
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
        
    except Exception as e:
        print(f"[ERR] Error generating QR code: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/recommendations/<session_id>')
def view_recommendations(session_id):
    """Mobile-optimized page displaying tour recommendations"""
    try:
        # Get session data
        session_data = recommendation_sessions.get(session_id)
        
        if not session_data:
            return render_template('error.html', 
                                 message="This recommendation link has expired or is invalid."), 404
        
        # Get tours with full details
        language = session_data.get('language', 'en')
        tours = session_data.get('tours', [])
        preferences = session_data.get('preferences', {})
        chat_summary = session_data.get('chat_summary', '')
        
        print(f"ðŸ“± Displaying {len(tours)} tours for session {session_id}")
        
        return render_template('recommendations.html',
                             tours=tours,
                             preferences=preferences,
                             chat_summary=chat_summary,
                             session_id=session_id)
        
    except Exception as e:
        print(f"[ERR] Error displaying recommendations: {e}")
        return render_template('error.html', 
                             message="An error occurred loading your recommendations."), 500

@app.route('/api/email-recommendations', methods=['POST'])
def email_recommendations():
    """Send recommendations to user's email"""
    try:
        data = request.get_json()
        email = data.get('email')
        session_id = data.get('session_id')
        
        if not email or not session_id:
            return jsonify({'success': False, 'error': 'Email and session ID required'}), 400
        
        # Get session data
        session_data = recommendation_sessions.get(session_id)
        if not session_data:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Generate recommendations URL
        base_url = request.host_url.rstrip('/')
        recommendations_url = f"{base_url}/recommendations/{session_id}"
        
        tours = session_data.get('tours', [])
        preferences = session_data.get('preferences', {})
        chat_summary = session_data.get('chat_summary', '')
        
        # Build email HTML
        tour_cards_html = ""
        for tour in tours[:10]:  # Max 10 tours in email
            tour_cards_html += f"""
            <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 15px; background: white;">
                <h3 style="margin: 0 0 10px 0; color: #0077b6;">{tour.get('name', 'Tour')}</h3>
                <p style="margin: 5px 0; color: #666;">
                    <strong>Company:</strong> {tour.get('company_display', tour.get('company', ''))}
                </p>
                <p style="margin: 5px 0; color: #666;">
                    <strong>Price:</strong> {tour.get('price_adult', 'Contact for price')} | 
                    <strong>Duration:</strong> {tour.get('duration', 'N/A')}
                </p>
                <p style="margin: 10px 0; color: #333;">{tour.get('summary', '')[:200]}...</p>
                <a href="{tour.get('link_booking', '#')}" 
                   style="display: inline-block; background: #0077b6; color: white; padding: 10px 20px; 
                          text-decoration: none; border-radius: 5px; margin-top: 10px;">
                    Book Now
                </a>
            </div>
            """
        
        preferences_html = ""
        if preferences:
            prefs_list = []
            if preferences.get('duration'): prefs_list.append(f"Duration: {preferences['duration']}")
            if preferences.get('activity'): prefs_list.append(f"Activity: {preferences['activity']}")
            if preferences.get('family'): prefs_list.append("Family-friendly")
            if preferences.get('budget'): prefs_list.append(f"Budget: {preferences['budget']}")
            
            if prefs_list:
                preferences_html = f"""
                <div style="background: #f0f8ff; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h3 style="margin: 0 0 10px 0; color: #0077b6;">Your Preferences:</h3>
                    <p style="margin: 5px 0;">{"<br>".join([f"âœ“ {p}" for p in prefs_list])}</p>
                </div>
                """
        
        email_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #0077b6 0%, #005a8b 100%); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">ðŸï¸ Your Whitsundays Tour Recommendations</h1>
                <p style="margin: 10px 0 0 0;">Personalized just for you!</p>
            </div>
            
            <div style="background: #f9f9f9; padding: 20px;">
                {preferences_html}
                
                {f'<p style="background: white; padding: 15px; border-left: 4px solid #0077b6; margin-bottom: 20px;"><em>"{chat_summary}"</em></p>' if chat_summary else ''}
                
                <h2 style="color: #0077b6; margin-bottom: 20px;">Your Recommended Tours:</h2>
                
                {tour_cards_html}
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{recommendations_url}" 
                       style="display: inline-block; background: #0077b6; color: white; padding: 15px 30px; 
                              text-decoration: none; border-radius: 8px; font-size: 16px; font-weight: bold;">
                        ðŸ“± View All Recommendations Online
                    </a>
                </div>
                
                <p style="text-align: center; color: #666; font-size: 14px; margin-top: 30px;">
                    This link is valid for 7 days. Bookmark it or share with your travel companions!
                </p>
            </div>
            
            <div style="background: #333; color: #ccc; padding: 20px; text-align: center; font-size: 12px; border-radius: 0 0 8px 8px;">
                <p style="margin: 5px 0;">Whitsundays Tour Kiosk</p>
                <p style="margin: 5px 0;">Discover your perfect adventure</p>
            </div>
        </body>
        </html>
        """
        
        # Send email using SendGrid
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        
        from_email = Email(os.getenv('SENDGRID_FROM_EMAIL', 'noreply@whitsundaystours.com'))
        to_email = To(email)
        subject = "ðŸï¸ Your Whitsundays Tour Recommendations"
        content = Content("text/html", email_html)
        
        mail = Mail(from_email, to_email, subject, content)
        response = sg.send(mail)
        
        print(f"[OK] Email sent to {email} - Status: {response.status_code}")
        
        return jsonify({
            'success': True,
            'message': 'Recommendations sent to your email!'
        })
        
    except Exception as e:
        print(f"[ERR] Error sending email: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to send email. Please try again.'
        }), 500

# ============================================================================
# TOUR EDITOR / DEVELOPER MODE
# ============================================================================

def find_company_csv(company):
    """Find the best CSV file for a company (checks multiple locations)"""
    # Priority order: data/company/en/_with_media > root _with_media > root _cleaned
    candidates = [
        f'data/{company}/en/tours_{company}_cleaned_with_media.csv',
        f'data/{company}/en/{company}_cleaned_with_media.csv',
        f'tours_{company}_cleaned_with_media.csv',
        f'tours_{company}_cleaned.csv',
    ]
    
    # Also check for any CSV in the data/company/en/ folder
    data_folder = f'data/{company}/en/'
    if os.path.isdir(data_folder):
        for f in os.listdir(data_folder):
            if f.endswith('_with_media.csv'):
                candidates.insert(0, os.path.join(data_folder, f))
    
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def get_all_tour_csvs():
    """Get all CSV files containing tours from all locations"""
    csv_files = []
    seen_companies = set()
    
    # 1. Check data/<company>/en/ folders (priority)
    for company_dir in glob.glob('data/*/'):
        company_name = os.path.basename(company_dir.rstrip('/\\'))
        en_folder = os.path.join(company_dir, 'en')
        if os.path.isdir(en_folder):
            # Look for _with_media.csv first, then any CSV
            media_csvs = glob.glob(os.path.join(en_folder, '*_with_media.csv'))
            if media_csvs:
                csv_files.extend(media_csvs)
                seen_companies.add(company_name)
    
    # 2. Check root directory for _with_media.csv
    prefix = 'tours_'
    suffix_media = '_cleaned_with_media.csv'
    suffix_clean = '_cleaned.csv'
    
    for csvfile in glob.glob('tours_*_cleaned_with_media.csv'):
        # Extract company name carefully - only strip prefix and suffix once
        # Use len() to handle company names that contain 'tours' (e.g., airlieadventuretours)
        if csvfile.startswith(prefix) and csvfile.endswith(suffix_media):
            company = csvfile[len(prefix):-len(suffix_media)]
        else:
            continue
        if company not in seen_companies:
            csv_files.append(csvfile)
            seen_companies.add(company)
    
    # 3. Check root directory for _cleaned.csv (fallback)
    for csvfile in glob.glob('tours_*_cleaned.csv'):
        if '_with_media' in csvfile:
            continue
        # Extract company name carefully
        if csvfile.startswith(prefix) and csvfile.endswith(suffix_clean):
            company = csvfile[len(prefix):-len(suffix_clean)]
        else:
            continue
        if company not in seen_companies:
            csv_files.append(csvfile)
            seen_companies.add(company)
    
    return csv_files

@app.route('/admin/editor')
def tour_editor():
    """Tour Editor - Developer Mode for editing tour listings"""
    # Require login
    username = session.get('user')
    if not username:
        return redirect(url_for('login'))
    
    # Check if this user needs approval for changes
    needs_approval = requires_approval(username)
    
    # Load all tours grouped by company
    companies = {}
    
    # Find all CSV files from all locations
    csv_files = get_all_tour_csvs()
    print(f"[Editor] Found {len(csv_files)} CSV files")
    
    for csvfile in csv_files:
        try:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Support both 'company_name' and 'company' columns
                        company = row.get('company_name') or row.get('company') or 'unknown'
                        if company not in companies:
                            companies[company] = []
                        companies[company].append({
                            'id': row.get('id', ''),
                            'name': row.get('name', 'Unnamed Tour'),
                            'company': company,
                            'csv_file': csvfile  # Track which file it came from
                        })
        except Exception as e:
            print(f"Error loading {csvfile}: {e}")
    
    print(f"[Editor] Loaded {len(companies)} companies with tours")
    
    # Get company names with account-specific overrides
    account_company_names = get_company_display_names_for_account(username)
    
    return render_template('tour_editor.html', 
                          companies=companies,
                          company_names=account_company_names,
                          username=username,
                          needs_approval=needs_approval,
                          is_admin=is_admin_user(username))

@app.route('/admin/api/company-name', methods=['POST'])
def update_company_display_name():
    """Update a company's display name
    
    For non-admin users: Stores as account-specific override (only affects their view)
    For admin users: Can update globally or per-account
    """
    global COMPANY_DISPLAY_NAMES
    
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.get_json()
    company_key = data.get('company_key')
    display_name = data.get('display_name', '').strip()
    update_globally = data.get('update_globally', False)  # Only admins can use this
    
    if not company_key or not display_name:
        return jsonify({'error': 'Company key and display name required'}), 400
    
    # For non-admin users, always save as account-specific override
    if requires_approval(username) or not update_globally:
        settings = load_account_settings(username)
        if 'company_name_overrides' not in settings:
            settings['company_name_overrides'] = {}
        
        settings['company_name_overrides'][company_key] = display_name
        save_account_settings(username, settings)
        
        return jsonify({
            'success': True,
            'account_specific': True,
            'message': 'Company name updated for your account'
        })
    
    # Admin - apply directly
    COMPANY_DISPLAY_NAMES[company_key] = display_name
    if save_company_display_names(COMPANY_DISPLAY_NAMES):
        git_sync_changes(f"Renamed company: {company_key} -> {display_name}")
        return jsonify({'success': True, 'message': 'Company name updated'})
    else:
        return jsonify({'error': 'Failed to save company name'}), 500

@app.route('/admin/api/tour/<key>')
def get_tour_for_editor(key):
    """API endpoint to get full tour data for editing"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    # Find the tour in any matching CSV
    csv_file = find_company_csv(company)
    
    if not csv_file:
        return jsonify({'error': f'Company not found: {company}'}), 404
    
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('id') == tid:
                    # Add the CSV file path so we know where to save
                    result = dict(row)
                    result['_csv_file'] = csv_file
                    return jsonify(result)
        
        return jsonify({'error': 'Tour not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/tour/<key>', methods=['POST'])
def save_tour_from_editor(key):
    """API endpoint to save tour changes back to CSV - requires approval for non-admins"""
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    csv_file = find_company_csv(company)
    
    if not csv_file:
        return jsonify({'error': f'Company not found: {company}'}), 404
    
    try:
        # Get the new data
        new_data = request.get_json()
        
        # Read all tours to get current data
        rows = []
        fieldnames = None
        original_tour = None
        
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        # Find the current tour data
        for row in rows:
            if row.get('id') == tid:
                original_tour = dict(row)
                break
        
        if not original_tour:
            return jsonify({'error': 'Tour not found'}), 404
        
        # Determine which fields require approval (content changes)
        # These fields contain actual tour content that needs review
        APPROVAL_REQUIRED_FIELDS = {
            'name', 'description', 'highlights', 'inclusions', 'exclusions',
            'what_to_bring', 'itinerary', 'important_info', 'images',
            'image_url', 'thumbnail', 'gallery'
        }
        
        # Separate changes that need approval from those that don't
        changes_needing_approval = {}
        changes_not_needing_approval = {}
        
        for field, new_value in new_data.items():
            old_value = original_tour.get(field, '')
            if str(old_value) != str(new_value):  # Only track actual changes
                if field in APPROVAL_REQUIRED_FIELDS:
                    changes_needing_approval[field] = {
                        'before': old_value,
                        'after': new_value
                    }
                else:
                    changes_not_needing_approval[field] = new_value
        
        # For admin users, apply everything directly
        if is_admin_user(username):
            # Apply all changes
            for i, row in enumerate(rows):
                if row.get('id') == tid:
                    for field, value in new_data.items():
                        row[field] = value
                    rows[i] = row
                    break
            
            # Check for new fields
            new_fields = [f for f in new_data.keys() if f not in fieldnames]
            if new_fields:
                fieldnames = list(fieldnames) + new_fields
            
            # Write back to CSV
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            tour_name = new_data.get('name', original_tour.get('name', tid))
            git_sync_changes(f"Updated tour: {tour_name}")
            
            return jsonify({'success': True, 'message': 'Tour saved successfully'})
        
        # For non-admin users:
        # 1. Apply changes that don't need approval directly
        # 2. Create a change request for content changes
        
        applied_changes = []
        
        # Apply non-approval changes directly
        if changes_not_needing_approval:
            for i, row in enumerate(rows):
                if row.get('id') == tid:
                    for field, value in changes_not_needing_approval.items():
                        row[field] = value
                    rows[i] = row
                    break
            
            new_fields = [f for f in changes_not_needing_approval.keys() if f not in fieldnames]
            if new_fields:
                fieldnames = list(fieldnames) + new_fields
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            applied_changes = list(changes_not_needing_approval.keys())
            git_sync_changes(f"Updated tour technical fields: {key}")
        
        # Create change request for content changes
        if changes_needing_approval:
            tour_name = new_data.get('name', original_tour.get('name', tid))
            
            # Build a readable description of changes
            change_summary = []
            for field in changes_needing_approval:
                if field == 'name':
                    change_summary.append('name')
                elif field == 'description':
                    change_summary.append('description')
                elif field in ('images', 'image_url', 'thumbnail', 'gallery'):
                    change_summary.append('images')
                else:
                    change_summary.append(field.replace('_', ' '))
            
            description = f"Edit {tour_name}: {', '.join(set(change_summary))}"
            
            # Build the new_data that would be applied (only the content fields)
            content_changes = {field: new_data[field] for field in changes_needing_approval}
            
            request_id = create_change_request(
                requested_by=username,
                change_type='tour_content_edit',
                description=description,
                changes_data={
                    'new_data': content_changes,
                    'before_after': changes_needing_approval,
                    'tour_name': tour_name,
                    'company': company
                },
                tour_key=key
            )
            
            message = 'Content changes submitted for approval'
            if applied_changes:
                message += f' (other changes applied: {", ".join(applied_changes)})'
            
            return jsonify({
                'success': True,
                'pending_approval': True,
                'request_id': request_id,
                'message': message,
                'applied_fields': applied_changes,
                'pending_fields': list(changes_needing_approval.keys())
            })
        
        # No changes at all (shouldn't normally happen)
        return jsonify({'success': True, 'message': 'No changes detected'})
        
    except Exception as e:
        print(f"Error saving tour: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/tours/export')
def export_tours():
    """Export all tours as JSON for backup"""
    all_tours = []
    csv_files = glob.glob('tours_*_cleaned_with_media.csv')
    
    for csvfile in csv_files:
        try:
            with open(csvfile, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    all_tours.append(dict(row))
        except Exception as e:
            print(f"Error reading {csvfile}: {e}")
    
    return jsonify({'tours': all_tours, 'count': len(all_tours)})

@app.route('/admin/api/tour/<key>/images')
def get_tour_images(key):
    """API endpoint to get all images for a tour (filtered by account's hidden images)"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    # Get hidden images for current user
    username = session.get('user')
    hidden_images = []
    if username:
        settings = load_account_settings(username)
        hidden_images = settings.get('hidden_images', {}).get(key, [])
    
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    images = []
    thumbnail_path = None
    found_folder = None
    
    # Check hash-based folder first
    folder = f"static/tour_images/{company}/{tid}"
    if os.path.isdir(folder):
        found_folder = folder
    else:
        # Check all folders in company directory for name-based folders
        company_folder = f"static/tour_images/{company}"
        if os.path.isdir(company_folder):
            for subfolder in os.listdir(company_folder):
                subfolder_path = os.path.join(company_folder, subfolder)
                if os.path.isdir(subfolder_path):
                    # Check if this folder has a media_manifest or if it matches by content
                    manifest_path = os.path.join(subfolder_path, 'media_manifest.json')
                    if os.path.exists(manifest_path):
                        try:
                            with open(manifest_path, 'r') as f:
                                manifest = json.load(f)
                                if manifest.get('tour_id') == tid:
                                    found_folder = subfolder_path
                                    break
                        except:
                            pass
            
            # If still not found, check image_url from CSV to find the folder
            if not found_folder:
                csv_file = find_company_csv(company)
                if csv_file:
                    with open(csv_file, newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('id') == tid:
                                # Extract folder from image_url
                                img_url = row.get('image_url', '')
                                if img_url:
                                    img_path = img_url.lstrip('/')
                                    if os.path.dirname(img_path):
                                        potential_folder = os.path.dirname(img_path)
                                        if os.path.isdir(potential_folder):
                                            found_folder = potential_folder
                                break
    
    # Scan the found folder for images
    if found_folder and os.path.isdir(found_folder):
        for filename in os.listdir(found_folder):
            ext = os.path.splitext(filename)[1].lower()
            if ext in extensions:
                filepath = f"/{found_folder}/{filename}".replace("\\", "/")
                
                # Skip hidden images for this user
                normalized_filepath = filepath.lstrip('/')
                if normalized_filepath in hidden_images or filepath in hidden_images:
                    continue
                
                is_thumb = filename.lower().startswith('thumbnail')
                images.append({
                    'path': filepath,
                    'filename': filename,
                    'is_thumbnail': is_thumb
                })
                if is_thumb:
                    thumbnail_path = filepath
    
    # If no explicit thumbnail, find the largest image
    if not thumbnail_path and images:
        try:
            largest = max(images, key=lambda x: os.path.getsize(x['path'].lstrip('/')))
            largest['is_thumbnail'] = True
            thumbnail_path = largest['path']
        except:
            pass
    
    return jsonify({
        'images': images,
        'thumbnail': thumbnail_path,
        'folder': found_folder or folder
    })

@app.route('/admin/api/tour/<key>/thumbnail', methods=['POST'])
def set_tour_thumbnail(key):
    """API endpoint to set a tour's thumbnail"""
    import shutil
    
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    data = request.get_json()
    source_path = data.get('image_path', '').lstrip('/')
    
    if not source_path or not os.path.exists(source_path):
        return jsonify({'error': 'Image not found'}), 404
    
    # Find the folder - check hash-based first, then name-based
    folder = f"static/tour_images/{company}/{tid}"
    if not os.path.isdir(folder):
        # Try to find by checking image_url from CSV
        csv_file = find_company_csv(company)
        if csv_file:
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id') == tid:
                        img_url = row.get('image_url', '')
                        if img_url:
                            potential_folder = os.path.dirname(img_url.lstrip('/'))
                            if os.path.isdir(potential_folder):
                                folder = potential_folder
                        break
    
    if not os.path.isdir(folder):
        return jsonify({'error': 'Tour folder not found'}), 404
    
    # Get the extension of the source file
    ext = os.path.splitext(source_path)[1].lower()
    
    # Remove any existing thumbnails
    for f in os.listdir(folder):
        if f.lower().startswith('thumbnail'):
            try:
                os.remove(os.path.join(folder, f))
            except:
                pass
    
    # Copy the source file as the new thumbnail
    thumb_path = os.path.join(folder, f"thumbnail{ext}")
    shutil.copy2(source_path, thumb_path)
    
    return jsonify({
        'success': True,
        'thumbnail': f"/{thumb_path}".replace("\\", "/")
    })

def sync_tour_images_to_csv(company, tid):
    """Sync images from folder to CSV images field"""
    folder = f"static/tour_images/{company}/{tid}"
    if not os.path.isdir(folder):
        return []
    
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.JPG', '.JPEG', '.PNG', '.WEBP', '.GIF']
    image_paths = []
    
    # Collect all images from folder
    for filename in sorted(os.listdir(folder)):
        if any(filename.endswith(ext) for ext in extensions):
            # Skip thumbnails - they're handled separately
            if filename.lower().startswith('thumbnail'):
                continue
            image_paths.append(f"static/tour_images/{company}/{tid}/{filename}")
    
    # Update CSV with new images
    csv_file = find_company_csv(company)
    if csv_file and os.path.exists(csv_file):
        try:
            rows = []
            fieldnames = None
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames) if reader.fieldnames else []
                for row in reader:
                    if row.get('id') == tid:
                        # Update images field (try both 'images' and 'image_urls' for compatibility)
                        if 'images' in fieldnames:
                            row['images'] = ','.join(image_paths)
                        elif 'image_urls' in fieldnames:
                            row['image_urls'] = ','.join(image_paths)
                        else:
                            # Add 'images' field if neither exists
                            fieldnames.append('images')
                            row['images'] = ','.join(image_paths)
                        print(f"[Sync] Updated images for {tid}: {len(image_paths)} images")
                    rows.append(row)
            
            # Write back
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"[Sync] Successfully wrote CSV: {csv_file}")
        except Exception as e:
            print(f"[Sync] Error updating CSV: {e}")
            import traceback
            traceback.print_exc()
    
    return image_paths

@app.route('/admin/api/tour/<key>/images/upload', methods=['POST'])
def upload_tour_images(key):
    """API endpoint to upload images for a tour"""
    from werkzeug.utils import secure_filename
    
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    if 'images' not in request.files:
        return jsonify({'error': 'No images provided'}), 400
    
    files = request.files.getlist('images')
    if not files:
        return jsonify({'error': 'No images provided'}), 400
    
    # ALWAYS use consistent folder structure: static/tour_images/{company}/{tour_id}/
    folder = f"static/tour_images/{company}/{tid}"
    
    # Create folder if it doesn't exist
    os.makedirs(folder, exist_ok=True)
    print(f"[Upload] Saving images to: {folder}")
    
    uploaded = 0
    for file in files:
        if file and file.filename:
            # Generate unique filename
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                continue
            
            # Use original filename but make it unique
            base_name = secure_filename(file.filename)
            name_part = os.path.splitext(base_name)[0]
            filename = f"{name_part}_{int(time.time() * 1000)}{ext}"
            
            filepath = os.path.join(folder, filename)
            file.save(filepath)
            uploaded += 1
    
    # IMPORTANT: Sync images to CSV so they appear in listings
    image_paths = sync_tour_images_to_csv(company, tid)
    
    # Sync changes to git (images + CSV updates)
    git_sync_changes(f"Uploaded {uploaded} images for {company}/{tid}")
    
    return jsonify({
        'success': True,
        'uploaded': uploaded,
        'folder': folder,
        'total_images': len(image_paths)
    })

@app.route('/admin/api/tour/<key>/images/delete', methods=['POST'])
def delete_tour_image(key):
    """API endpoint to delete/hide a tour image
    
    For non-admin users: Hides the image for their account only (stored in settings)
    For admin users: Can choose to delete globally or hide for specific account
    """
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    data = request.get_json()
    image_path = data.get('image_path', '').lstrip('/')
    delete_globally = data.get('delete_globally', False)  # Only admins can use this
    
    if not image_path:
        return jsonify({'error': 'No image path provided'}), 400
    
    # Normalize the image path for storage (use forward slashes for consistency)
    normalized_path = image_path.replace('\\', '/')
    
    # For non-admin users, always hide instead of delete
    if requires_approval(username) or not delete_globally:
        # Store in account's hidden_images
        settings = load_account_settings(username)
        if 'hidden_images' not in settings:
            settings['hidden_images'] = {}
        
        # Store by tour_key for easy lookup
        if key not in settings['hidden_images']:
            settings['hidden_images'][key] = []
        
        if normalized_path not in settings['hidden_images'][key]:
            settings['hidden_images'][key].append(normalized_path)
        
        save_account_settings(username, settings)
        
        return jsonify({
            'success': True, 
            'hidden': True,
            'message': 'Image hidden for your account'
        })
    
    # Admin with delete_globally=True - actually delete the file
    # Normalize path for filesystem
    fs_path = image_path.replace('/', os.sep).replace('\\', os.sep)
    
    # Security check: ensure the path is within the tour images folder
    expected_prefix = f"static{os.sep}tour_images{os.sep}{company}"
    if not fs_path.startswith(expected_prefix):
        return jsonify({'error': 'Invalid image path'}), 403
    
    if not os.path.exists(fs_path):
        return jsonify({'error': 'Image not found'}), 404
    
    # Don't allow deleting the thumbnail directly (use set_thumbnail instead)
    if os.path.basename(fs_path).lower().startswith('thumbnail'):
        return jsonify({'error': 'Cannot delete thumbnail directly. Set another image as thumbnail first.'}), 400
    
    try:
        os.remove(fs_path)
        # Sync remaining images to CSV
        sync_tour_images_to_csv(company, tid)
        # Sync deletion to git
        git_sync_changes(f"Deleted image for {company}/{tid}")
        return jsonify({'success': True, 'deleted': True, 'message': 'Image deleted globally'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/tour/<key>/sync-images', methods=['POST'])
def sync_images_endpoint(key):
    """API endpoint to sync folder images to CSV"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    image_paths = sync_tour_images_to_csv(company, tid)
    
    # Sync CSV changes to git
    git_sync_changes(f"Synced images for {company}/{tid}")
    
    return jsonify({
        'success': True,
        'images_synced': len(image_paths),
        'images': image_paths
    })

@app.route('/admin/api/tour/<key>/video-urls', methods=['GET', 'POST'])
def tour_video_urls(key):
    """API endpoint to get/set video URLs for a tour"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    csv_file = find_company_csv(company)
    if not csv_file:
        return jsonify({'error': f'Company not found: {company}'}), 404
    
    if request.method == 'GET':
        # Return current video URLs
        try:
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id') == tid:
                        video_urls = row.get('video_urls', '')
                        return jsonify({
                            'video_urls': video_urls,
                            'video_list': [v.strip() for v in video_urls.split(',') if v.strip()]
                        })
            return jsonify({'error': 'Tour not found'}), 404
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    else:  # POST - update video URLs
        data = request.get_json()
        video_urls = data.get('video_urls', '')
        
        print(f"[Video Save] Key: {key}, Company: {company}, TourID: {tid}")
        print(f"[Video Save] Received video_urls: {repr(video_urls)}")
        
        try:
            rows = []
            fieldnames = None
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                
                # Add video_urls column if it doesn't exist
                if 'video_urls' not in fieldnames:
                    fieldnames = list(fieldnames) + ['video_urls']
                
                for row in reader:
                    if row.get('id') == tid:
                        row['video_urls'] = video_urls
                        print(f"[Video] Updated video_urls for {tid}: {video_urls}")
                    rows.append(row)
            
            # Write back
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            return jsonify({
                'success': True,
                'video_urls': video_urls
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/admin/api/tour/<key>/delete', methods=['DELETE'])
def delete_tour(key):
    """API endpoint to delete a tour and optionally the company if no tours remain"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    csv_file = find_company_csv(company)
    if not csv_file:
        return jsonify({'error': f'Company not found: {company}'}), 404
    
    # Read all tours
    rows = []
    fieldnames = None
    tour_found = False
    
    try:
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get('id') == tid:
                    tour_found = True
                    # Skip this tour (don't add to rows)
                else:
                    rows.append(row)
    except Exception as e:
        return jsonify({'error': f'Failed to read CSV: {e}'}), 500
    
    if not tour_found:
        return jsonify({'error': 'Tour not found'}), 404
    
    company_deleted = False
    
    # If no tours remain, delete the company
    if len(rows) == 0:
        try:
            # Delete the CSV file
            os.remove(csv_file)
            
            # Try to delete the company folder if empty
            company_folder = f'data/{company}/en'
            if os.path.isdir(company_folder) and not os.listdir(company_folder):
                os.rmdir(company_folder)
            
            parent_folder = f'data/{company}'
            if os.path.isdir(parent_folder) and not os.listdir(parent_folder):
                os.rmdir(parent_folder)
            
            # Delete image folder
            image_folder = f'static/tour_images/{company}'
            if os.path.isdir(image_folder):
                import shutil
                shutil.rmtree(image_folder)
            
            # Delete reviews folder
            reviews_folder = f'tour_reviews/{company}'
            if os.path.isdir(reviews_folder):
                import shutil
                shutil.rmtree(reviews_folder)
            
            company_deleted = True
            print(f"[Delete] Deleted company {company} (no tours remaining)")
            
        except Exception as e:
            print(f"[Delete] Warning: Could not fully clean up company {company}: {e}")
    else:
        # Write remaining tours back
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"[Delete] Deleted tour {tid} from {company}, {len(rows)} tours remaining")
        except Exception as e:
            return jsonify({'error': f'Failed to save CSV: {e}'}), 500
    
    # Delete tour images folder
    tour_image_folder = f'static/tour_images/{company}/{tid}'
    if os.path.isdir(tour_image_folder):
        try:
            import shutil
            shutil.rmtree(tour_image_folder)
            print(f"[Delete] Deleted image folder: {tour_image_folder}")
        except Exception as e:
            print(f"[Delete] Warning: Could not delete image folder: {e}")
    
    # Delete tour reviews file
    review_file = f'tour_reviews/{company}/{tid}.json'
    if os.path.exists(review_file):
        try:
            os.remove(review_file)
            print(f"[Delete] Deleted review file: {review_file}")
        except Exception as e:
            print(f"[Delete] Warning: Could not delete review file: {e}")
    
    return jsonify({
        'success': True,
        'company_deleted': company_deleted,
        'remaining_tours': len(rows)
    })

@app.route('/admin/api/tour/<key>/reviews', methods=['GET'])
def get_tour_reviews(key):
    """API endpoint to get reviews for a tour"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    reviews_data = load_reviews(company, tid)
    
    if reviews_data:
        return jsonify(reviews_data)
    else:
        return jsonify({
            'reviews': [],
            'overall_rating': None,
            'review_count': 0,
            'source': 'Google Reviews'
        })

@app.route('/admin/api/tour/<key>/reviews', methods=['POST'])
def save_tour_reviews(key):
    """API endpoint to save reviews for a tour"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
    data = request.get_json()
    
    # Ensure the reviews directory exists
    reviews_dir = os.path.join('tour_reviews', company)
    os.makedirs(reviews_dir, exist_ok=True)
    
    # Save the reviews
    review_file = os.path.join(reviews_dir, f"{tid}.json")
    
    try:
        with open(review_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': 'Reviews saved successfully'
        })
    except Exception as e:
        print(f"Error saving reviews: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/company/<company>/apply-reviews', methods=['POST'])
def apply_reviews_to_company(company):
    """Apply reviews from one tour to all tours in the same company"""
    data = request.get_json()
    
    # Load all tours for this company to get their IDs
    csv_file = find_company_csv(company)
    if not csv_file:
        return jsonify({'error': f'Company not found: {company}'}), 404
    
    try:
        tour_ids = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('id'):
                    tour_ids.append(row['id'])
        
        if not tour_ids:
            return jsonify({'error': 'No tours found for this company'}), 404
        
        # Ensure the reviews directory exists
        reviews_dir = os.path.join('tour_reviews', company)
        os.makedirs(reviews_dir, exist_ok=True)
        
        # Save reviews to all tour files
        saved_count = 0
        for tid in tour_ids:
            review_file = os.path.join(reviews_dir, f"{tid}.json")
            with open(review_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            saved_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Reviews applied to {saved_count} tours',
            'count': saved_count
        })
    except Exception as e:
        print(f"Error applying reviews: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/api/company/<company>/update-field', methods=['POST'])
def update_company_field(company):
    """API endpoint to update a field for ALL tours from a company"""
    data = request.get_json()
    field_name = data.get('field')
    field_value = data.get('value')
    
    if not field_name:
        return jsonify({'error': 'Field name required'}), 400
    
    # Only allow certain fields to be bulk-updated for safety
    allowed_fields = ['departure_location', 'age_requirements', 'ideal_for', 'phone']
    if field_name not in allowed_fields:
        return jsonify({'error': f'Field "{field_name}" cannot be bulk-updated'}), 400
    
    csv_file = find_company_csv(company)
    if not csv_file:
        return jsonify({'error': f'Company not found: {company}'}), 404
    
    try:
        # Read all tours
        rows = []
        fieldnames = None
        
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        # Add field if it doesn't exist
        if field_name not in fieldnames:
            fieldnames = list(fieldnames) + [field_name]
        
        # Update all rows
        updated_count = 0
        for row in rows:
            row[field_name] = field_value
            updated_count += 1
        
        # Write back to CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        # Sync changes to connected devices
        git_sync_changes(f"Updated {field_name} for {company} tours")
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'field': field_name,
            'value': field_value
        })
        
    except Exception as e:
        print(f"Error updating company field: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ANALYTICS API ENDPOINTS
# ============================================================================

@app.route('/api/analytics/event', methods=['POST'])
def log_analytics():
    """Log an analytics event from the frontend"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        event_type = data.get('event_type')
        event_data = data.get('event_data', {})
        
        if not session_id or not event_type:
            return jsonify({'error': 'session_id and event_type required'}), 400
        
        # Use account from referral cookie, session, or default
        analytics_account = request.cookies.get('filtour_ref') or get_active_account() or DEFAULT_ANALYTICS_ACCOUNT
        session = log_analytics_event(session_id, event_type, event_data, account=analytics_account)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'event_type': event_type
        })
    except Exception as e:
        print(f"Analytics error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/start-session', methods=['POST'])
def start_analytics_session():
    """Start a new analytics session and return session ID"""
    try:
        session_id = f"session_{uuid.uuid4().hex[:12]}_{int(time.time())}"
        
        # Create initial session (use default account - kiosk doesn't know about users)
        # Use account from referral cookie, session, or default
        analytics_account = request.cookies.get('filtour_ref') or get_active_account() or DEFAULT_ANALYTICS_ACCOUNT
        log_analytics_event(session_id, 'session_start', {
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'referrer': request.headers.get('Referer', 'direct')
        }, account=analytics_account)
        
        return jsonify({
            'success': True,
            'session_id': session_id
        })
    except Exception as e:
        print(f"Analytics session start error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/summary')
@agent_required
def analytics_summary():
    """Get analytics summary (agent only) - shows logged-in user's analytics"""
    try:
        # Get analytics for logged-in user's account
        account = session.get('user', DEFAULT_ANALYTICS_ACCOUNT)
        summary = get_analytics_summary(account)
        return jsonify(summary)
    except Exception as e:
        print(f"Analytics summary error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/agent/analytics')
@agent_required
def agent_analytics_page():
    """Analytics dashboard for agents - shows logged-in user's analytics"""
    # Get analytics for logged-in user's account
    account = session.get('user', DEFAULT_ANALYTICS_ACCOUNT)
    summary = get_analytics_summary(account)
    return render_template('agent_analytics.html', summary=summary, account=account)

# ============================================================================
# TIDE DATA - Shute Harbour / Whitsundays
# ============================================================================

_tide_cache = {
    'data': None,
    'fetched_at': None
}

def scrape_tide_data(location='Shute-Harbour-Australia'):
    """Scrape 7-day tide data from tide-forecast.com for the Whitsundays"""
    import urllib.request
    import re as _re
    
    url = f'https://www.tide-forecast.com/locations/{location}/tides/latest'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode('utf-8', errors='replace')
    
    days = []
    tables = html.split('<table class="tide-day-tides">')
    
    for table_html in tables[1:]:
        table_html = table_html[:table_html.find('</table>')]
        
        rows = _re.findall(
            r'<tr(?:\s[^>]*)?>.*?<td>((?:High|Low)\s+Tide)</td>'
            r'.*?<b>\s*(\d{1,2}:\d{2}\s*(?:AM|PM))\s*</b>'
            r'.*?<span[^>]*>\(([^)]+)\)</span>'
            r'.*?<b[^>]*>(\d+\.\d+)\s*m</b>',
            table_html,
            _re.DOTALL
        )
        
        if not rows:
            continue
        
        day_date = rows[0][2].strip()
        tides = []
        for tide_type, time_str, date_str, height in rows:
            tides.append({
                'type': 'high' if 'High' in tide_type else 'low',
                'time': time_str.strip(),
                'height_m': float(height),
            })
        
        # Analyze Hill Inlet suitability
        low_tides = [t for t in tides if t['type'] == 'low']
        hill_inlet_rating = 'none'
        hill_inlet_note = ''
        best_low = None
        
        daytime_lows = []
        for lt in low_tides:
            try:
                t = datetime.strptime(lt['time'], '%I:%M %p')
                if 6 <= t.hour <= 16:
                    daytime_lows.append(lt)
            except:
                pass
        
        if daytime_lows:
            best_low = min(daytime_lows, key=lambda x: x['height_m'])
            if best_low['height_m'] < 1.0:
                hill_inlet_rating = 'great'
                hill_inlet_note = f"Low tide {best_low['time']} at {best_low['height_m']:.2f}m - excellent sand patterns"
            elif best_low['height_m'] < 1.5:
                hill_inlet_rating = 'good'
                hill_inlet_note = f"Low tide {best_low['time']} at {best_low['height_m']:.2f}m - visible sand patterns"
            else:
                hill_inlet_rating = 'poor'
                hill_inlet_note = f"Lowest daytime tide {best_low['time']} at {best_low['height_m']:.2f}m - limited visibility"
        
        if tides:
            days.append({
                'date_label': day_date,
                'tides': tides,
                'hill_inlet_rating': hill_inlet_rating,
                'hill_inlet_note': hill_inlet_note,
            })
    
    return days

def get_tide_data():
    """Get tide data with 6-hour caching"""
    now = datetime.now()
    
    if (_tide_cache['data'] is not None and 
        _tide_cache['fetched_at'] is not None and
        (now - _tide_cache['fetched_at']).total_seconds() < 6 * 3600):
        return _tide_cache['data']
    
    try:
        data = scrape_tide_data()
        _tide_cache['data'] = data
        _tide_cache['fetched_at'] = now
        print(f"[TIDES] Fetched {len(data)} days of tide data")
        return data
    except Exception as e:
        print(f"[TIDES] Error fetching tide data: {e}")
        if _tide_cache['data'] is not None:
            return _tide_cache['data']
        return []

@app.route('/agent/tides')
@agent_required
def agent_tides_page():
    """Tide forecast page for shop workers"""
    tide_days = get_tide_data()
    return render_template('agent_tides.html', 
                         tide_days=tide_days,
                         location='Shute Harbour',
                         cache_time=_tide_cache.get('fetched_at'))

@app.route('/api/tides')
@agent_required
def api_tides():
    """JSON API for tide data"""
    tide_days = get_tide_data()
    return jsonify({
        'success': True,
        'location': 'Shute Harbour',
        'days': tide_days,
        'cached_at': _tide_cache.get('fetched_at', '').isoformat() if _tide_cache.get('fetched_at') else None
    })

@app.route('/api/tides/refresh', methods=['POST'])
@agent_required
def refresh_tides():
    """Force refresh tide data"""
    _tide_cache['data'] = None
    _tide_cache['fetched_at'] = None
    tide_days = get_tide_data()
    return jsonify({
        'success': True,
        'days_count': len(tide_days)
    })

@app.route('/api/tides/public')
def api_tides_public():
    """Public tide data JSON (no auth required)"""
    tide_days = get_tide_data()
    return jsonify({
        'success': True,
        'location': 'Shute Harbour',
        'days': tide_days[:7],
        'cached_at': _tide_cache.get('fetched_at', '').isoformat() if _tide_cache.get('fetched_at') else None
    })

@app.route('/tides')
def kiosk_tides_page():
    """Public tide forecast page accessible from the kiosk"""
    tide_days = get_tide_data()
    return render_template('kiosk_tides.html',
                         tide_days=tide_days,
                         location='Shute Harbour')

@app.route('/api/analytics/session/<session_id>')
@agent_required
def get_session_details(session_id):
    """Get detailed events for a specific session"""
    try:
        account = session.get('user', DEFAULT_ANALYTICS_ACCOUNT)
        analytics = load_analytics(account)
        
        # Find the session
        for s in analytics.get('sessions', []):
            if s.get('session_id') == session_id:
                return jsonify({
                    'success': True,
                    'session': s
                })
        
        return jsonify({'error': 'Session not found'}), 404
    except Exception as e:
        print(f"Session details error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ACTIVE SESSION TRACKING - Don't interrupt customers during updates
# ============================================================================

_active_session_id = None
_active_session_started = None
_session_last_activity = None

@app.route('/api/session/heartbeat', methods=['POST'])
def session_heartbeat():
    """Called by frontend to indicate user is actively using the kiosk"""
    global _active_session_id, _active_session_started, _session_last_activity
    
    data = request.get_json() or {}
    session_id = data.get('session_id')
    
    if session_id:
        if _active_session_id != session_id:
            _active_session_id = session_id
            _active_session_started = time.time()
        _session_last_activity = time.time()
    
    return jsonify({'success': True, 'session_id': _active_session_id})

@app.route('/api/session/end', methods=['POST'])
def session_end_notification():
    """Called when user returns to home/splash screen (session ended)"""
    global _active_session_id, _active_session_started, _session_last_activity
    
    _active_session_id = None
    _active_session_started = None
    _session_last_activity = None
    
    return jsonify({'success': True, 'message': 'Session ended'})

@app.route('/api/session/status')
def session_status():
    """Check if there's an active session (for admin/debug)"""
    global _active_session_id, _active_session_started, _session_last_activity
    
    is_active = False
    idle_seconds = None
    
    if _active_session_id and _session_last_activity:
        idle_seconds = time.time() - _session_last_activity
        # Consider session active if activity in last 60 seconds
        is_active = idle_seconds < 60
    
    return jsonify({
        'active': is_active,
        'session_id': _active_session_id if is_active else None,
        'idle_seconds': round(idle_seconds, 1) if idle_seconds else None,
        'started_at': _active_session_started,
        'safe_to_update': not is_active
    })

def is_safe_to_update():
    """Check if it's safe to apply updates (no active customer session)"""
    global _active_session_id, _session_last_activity
    
    if not _active_session_id:
        return True
    
    if not _session_last_activity:
        return True
    
    # Consider safe if no activity in last 30 seconds
    idle_time = time.time() - _session_last_activity
    return idle_time > 30

# ============================================================================
# AUTO-UPDATE SYSTEM - Automatically pull from GitHub and restart
# ============================================================================

# Auto-update is for local kiosks only - disabled on Render/cloud (no git repo there)
# Render auto-deploys when GitHub receives pushes anyway
# Detect by checking for .git folder OR RENDER environment variable
IS_RENDER = os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID')
HAS_GIT_REPO = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.git'))
AUTO_UPDATE_ENABLED = HAS_GIT_REPO and not IS_RENDER  # Only enable on local kiosks with git
AUTO_UPDATE_INTERVAL = 60  # Check every 60 seconds
_update_available = False
_last_update_check = 0
_update_thread = None

def check_git_updates():
    """Check if there are updates available on GitHub"""
    global _update_available, _last_update_check
    import sys
    
    try:
        repo_path = os.path.dirname(os.path.abspath(__file__))
        
        # Check if this is a git repo
        if not os.path.exists(os.path.join(repo_path, '.git')):
            print("[AUTO-UPDATE] Not a git repo, skipping check", flush=True)
            return False
        
        print("[AUTO-UPDATE] Fetching from origin...", flush=True)
        sys.stdout.flush()
        
        # Get current HEAD hash BEFORE fetch
        head_before = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
        ).stdout.strip()
        
        # Fetch latest from remote
        fetch_result = subprocess.run(
            ['git', 'fetch', 'origin', 'main'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        
        if fetch_result.returncode != 0:
            print(f"[AUTO-UPDATE] Fetch failed: {fetch_result.stderr}", flush=True)
            return False
        
        # Get origin/main hash
        origin_hash = subprocess.run(
            ['git', 'rev-parse', 'origin/main'],
            cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
        ).stdout.strip()
        
        _last_update_check = time.time()
        
        # Only update if origin/main is DIFFERENT from our HEAD
        if head_before == origin_hash:
            print(f"[AUTO-UPDATE] Already up to date (HEAD={head_before[:8]})", flush=True)
            _update_available = False
            api_check_update._notified = False  # Reset notification flag
            return False
        
        print(f"[AUTO-UPDATE] HEAD={head_before[:8]} vs origin/main={origin_hash[:8]}", flush=True)
        
        # Check if we're behind origin/main (not just diverged)
        result = subprocess.run(
            ['git', 'rev-list', 'HEAD..origin/main', '--count'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        
        try:
            commits_behind = int(result.stdout.strip())
        except:
            commits_behind = 0
        
        # Also check if we're ahead (diverged history)
        ahead_result = subprocess.run(
            ['git', 'rev-list', 'origin/main..HEAD', '--count'],
            cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
        )
        try:
            commits_ahead = int(ahead_result.stdout.strip())
        except:
            commits_ahead = 0
        
        if commits_behind > 0 and commits_ahead == 0:
            # We're strictly behind - safe to fast-forward
            print(f"[AUTO-UPDATE] ✅ {commits_behind} new commit(s) available!", flush=True)
            _update_available = True
            api_check_update._notified = False  # Reset so frontend gets notified
            return True
        elif commits_behind > 0 and commits_ahead > 0:
            # Diverged history - try to push local commits first, then reset
            print(f"[AUTO-UPDATE] ⚠️ Diverged: {commits_ahead} ahead, {commits_behind} behind.", flush=True)
            
            # Try to push local commits (like analytics) before resetting
            # This preserves shop's local work
            try:
                push_result = subprocess.run(
                    ['git', 'push', 'origin', 'main'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=30
                )
                if push_result.returncode == 0:
                    print(f"[AUTO-UPDATE] ✅ Pushed {commits_ahead} local commit(s) to origin", flush=True)
                    # After pushing, we might still be behind, so check again
                    # But for now, proceed with update
                else:
                    print(f"[AUTO-UPDATE] ⚠️ Could not push local commits: {push_result.stderr[:200]}", flush=True)
                    print(f"[AUTO-UPDATE] Will reset to origin (local commits will be lost)", flush=True)
            except Exception as e:
                print(f"[AUTO-UPDATE] ⚠️ Error pushing local commits: {e}. Will reset to origin.", flush=True)
            
            print(f"[AUTO-UPDATE] Will reset to origin to get latest updates.", flush=True)
            _update_available = True
            api_check_update._notified = False  # Reset so frontend gets notified
            return True
        else:
            print("[AUTO-UPDATE] No new updates", flush=True)
            _update_available = False
        
        return False
        
    except Exception as e:
        print(f"[AUTO-UPDATE] Error checking for updates: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False

def pull_and_restart():
    """Pull updates and signal restart to the wrapper script (run_kiosk.py)"""
    global _update_available
    
    try:
        repo_path = os.path.dirname(os.path.abspath(__file__))
        
        print("[AUTO-UPDATE] Pulling updates...")
        
        # Remove the restart flag file FIRST (it blocks git operations)
        restart_flag = os.path.join(repo_path, 'config', '.restart_requested')
        if os.path.exists(restart_flag):
            try:
                os.remove(restart_flag)
                print("[AUTO-UPDATE] Removed old restart flag")
            except:
                pass
        
        # Clean up any untracked files in config/ that might block reset
        subprocess.run(
            ['git', 'clean', '-f', 'config/'],
            cwd=repo_path, capture_output=True, timeout=10
        )
        
        # Save local analytics before reset (so we don't lose data)
        analytics_backup = {}
        analytics_files = glob.glob(os.path.join(repo_path, 'data', 'analytics_*.json'))
        for af in analytics_files:
            try:
                with open(af, 'r', encoding='utf-8-sig') as f:
                    analytics_backup[af] = f.read()
            except:
                pass
        
        # Also backup instance.json (local device config - shouldn't be in git)
        instance_file = os.path.join(repo_path, 'config', 'instance.json')
        instance_backup = None
        if os.path.exists(instance_file):
            try:
                with open(instance_file, 'r', encoding='utf-8') as f:
                    instance_backup = f.read()
            except:
                pass
        
        # Before resetting, try to push any local commits (like analytics auto-push)
        # This prevents losing local work when branches have diverged
        try:
            push_check = subprocess.run(
                ['git', 'rev-list', 'origin/main..HEAD', '--count'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=5
            )
            commits_ahead = int(push_check.stdout.strip() or '0')
            
            if commits_ahead > 0:
                print(f"[AUTO-UPDATE] Pushing {commits_ahead} local commit(s) before reset...")
                push_result = subprocess.run(
                    ['git', 'push', 'origin', 'main'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=30
                )
                if push_result.returncode == 0:
                    print(f"[AUTO-UPDATE] ✅ Pushed local commits successfully")
                else:
                    print(f"[AUTO-UPDATE] ⚠️ Could not push local commits: {push_result.stderr[:100]}")
        except Exception as e:
            print(f"[AUTO-UPDATE] ⚠️ Error checking/pushing local commits: {e}")
        
        # Use reset --hard to ensure we match origin exactly (handles diverged history)
        # This is safer than pull which can fail on merge conflicts
        result = subprocess.run(
            ['git', 'reset', '--hard', 'origin/main'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60
        )
        
        if result.returncode == 0:
            print(f"[AUTO-UPDATE] ✅ Reset successful")
        else:
            print(f"[AUTO-UPDATE] Reset result: {result.stdout}")
            if result.stderr:
                print(f"[AUTO-UPDATE] Reset stderr: {result.stderr[:200]}")
        
        # Restore analytics files - MERGE local backup with remote data (from git reset)
        # This is critical for multi-kiosk setups: we don't want to overwrite
        # sessions pushed by another kiosk with our local-only data
        for af, backup_content in analytics_backup.items():
            try:
                # Strip BOM if present (PowerShell/Windows can add UTF-8 BOM)
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
                
                if added > 0:
                    print(f"[AUTO-UPDATE] Merged analytics: kept {len(local_sessions)} local + {added} remote sessions")
            except Exception as e:
                # Fallback: just restore the backup as-is
                print(f"[AUTO-UPDATE] ⚠️ Analytics merge failed ({e}), restoring backup")
                try:
                    with open(af, 'w', encoding='utf-8') as f:
                        f.write(backup_content)
                except:
                    pass
        
        # Restore instance.json (local device config)
        if instance_backup:
            try:
                os.makedirs(os.path.dirname(instance_file), exist_ok=True)
                with open(instance_file, 'w', encoding='utf-8') as f:
                    f.write(instance_backup)
            except:
                pass
        
        if result.returncode == 0:
            # Install any new dependencies quietly
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'],
                    cwd=repo_path,
                    capture_output=True,
                    timeout=120
                )
            except:
                pass
            
            _update_available = False
            print("[AUTO-UPDATE] Updates applied! Requesting restart...")
            
            # Create restart flag file for the runner script
            restart_flag = os.path.join(repo_path, 'config', '.restart_requested')
            os.makedirs(os.path.dirname(restart_flag), exist_ok=True)
            with open(restart_flag, 'w') as f:
                f.write(f'restart_requested_at={time.time()}')
            
            # Give the runner time to see the flag
            time.sleep(2)
            
            # Exit cleanly - the runner will restart us
            print("[AUTO-UPDATE] Exiting for restart...")
            os._exit(0)
        else:
            print(f"[AUTO-UPDATE] Pull failed: {result.stderr}")
            
    except Exception as e:
        print(f"[AUTO-UPDATE] Error pulling updates: {e}")

def auto_update_loop():
    """Background thread that checks for updates periodically"""
    global _update_available
    
    print("[AUTO-UPDATE] Background updater started", flush=True)
    
    # Wait a bit before first check
    time.sleep(10)
    
    check_count = 0
    while True:
        try:
            check_count += 1
            if AUTO_UPDATE_ENABLED:
                print(f"[AUTO-UPDATE] Check #{check_count}...", flush=True)
                if check_git_updates():
                    # Check if there's an active customer session
                    if not is_safe_to_update():
                        print("[AUTO-UPDATE] ⏳ Updates found but customer is active - waiting...", flush=True)
                        # Wait and check again in 30 seconds
                        for _ in range(6):  # Max wait 3 minutes
                            time.sleep(30)
                            if is_safe_to_update():
                                break
                            print("[AUTO-UPDATE] ⏳ Still waiting for customer session to end...", flush=True)
                    
                    # Final check before updating
                    if is_safe_to_update():
                        print("[AUTO-UPDATE] ✅ Safe to update - pulling and restarting...", flush=True)
                        # Give browsers 5 seconds to receive the update notification
                        time.sleep(5)
                        pull_and_restart()
                    else:
                        print("[AUTO-UPDATE] ⚠️ Customer still active after 3 min - will try again next cycle", flush=True)
                        _update_available = True  # Keep flag set for next cycle
            
            time.sleep(AUTO_UPDATE_INTERVAL)
            
        except Exception as e:
            print(f"[AUTO-UPDATE] Error in update loop: {e}", flush=True)
            import traceback
            traceback.print_exc()
            time.sleep(60)

@app.route('/api/check-update')
def api_check_update():
    """Endpoint for browser to check if updates are pending"""
    global _update_available, _update_notified
    
    # Only tell frontend about update ONCE per cycle
    # This prevents the notification from showing repeatedly
    if _update_available and not getattr(api_check_update, '_notified', False):
        api_check_update._notified = True
        return jsonify({
            'update_available': True,
            'last_check': _last_update_check,
            'version': APP_VERSION
        })
    
    return jsonify({
        'update_available': False,
        'last_check': _last_update_check,
        'version': APP_VERSION
    })

@app.route('/api/trigger-update', methods=['POST'])
def api_trigger_update():
    """Manually trigger an update check (admin only)"""
    if check_git_updates():
        # Start update in background thread
        threading.Thread(target=pull_and_restart, daemon=True).start()
        return jsonify({'status': 'updating', 'message': 'Update started, app will restart shortly'})
    return jsonify({'status': 'no_update', 'message': 'Already up to date'})

# ============================================================================
# ANALYTICS SYNC - Push analytics to git for remote viewing
# ============================================================================

def sync_analytics_to_git():
    """Sync analytics files to git so they can be viewed remotely.
    
    Robust pull-merge-push flow for multi-kiosk setups:
    1. Fetch latest from remote
    2. Merge remote analytics into local (picks up other kiosks' sessions)
    3. Commit the merged result
    4. Push to remote (retries with pull-merge if behind)
    """
    try:
        repo_path = os.path.dirname(os.path.abspath(__file__))
        
        # Step 1: Fetch latest from remote
        subprocess.run(
            ['git', 'fetch', 'origin', 'main'],
            cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30
        )
        
        # Step 2: For each analytics file, merge remote sessions into local
        analytics_files = glob.glob(os.path.join(repo_path, 'data', 'analytics_*.json'))
        merged_any = False
        
        for af in analytics_files:
            rel_path = os.path.relpath(af, repo_path).replace('\\', '/')
            try:
                # Get remote version of this file
                show_result = subprocess.run(
                    ['git', 'show', f'origin/main:{rel_path}'],
                    cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
                )
                
                if show_result.returncode == 0 and show_result.stdout.strip():
                    remote_data = json.loads(show_result.stdout)
                    remote_sessions = remote_data.get('sessions', [])
                    
                    # Load local file
                    with open(af, 'r', encoding='utf-8') as f:
                        local_data = json.load(f)
                    local_sessions = local_data.get('sessions', [])
                    local_ids = {s.get('session_id') for s in local_sessions if s.get('session_id')}
                    
                    # Add remote-only sessions to local
                    added = 0
                    for rs in remote_sessions:
                        if rs.get('session_id') and rs['session_id'] not in local_ids:
                            local_sessions.append(rs)
                            added += 1
                    
                    if added > 0:
                        # Sort and cap
                        local_sessions.sort(key=lambda s: s.get('started_at', ''))
                        if len(local_sessions) > 1000:
                            local_sessions = local_sessions[-1000:]
                        
                        local_data['sessions'] = local_sessions
                        local_data['last_updated'] = datetime.now().isoformat()
                        
                        with open(af, 'w', encoding='utf-8') as f:
                            json.dump(local_data, f, indent=2)
                        
                        merged_any = True
                        print(f"[ANALYTICS SYNC] Merged {added} remote session(s) into {os.path.basename(af)}")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"[ANALYTICS SYNC] Skipping merge for {os.path.basename(af)}: {e}")
        
        # Step 3: Check if there are any changes to commit (local new sessions + merged remote)
        status_result = subprocess.run(
            ['git', 'status', '--porcelain', 'data/analytics*.json'],
            cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10
        )
        
        if not status_result.stdout.strip():
            # No changes - nothing to push
            return
        
        # Step 4: Add, commit, push
        subprocess.run(
            ['git', 'add', 'data/analytics*.json'],
            cwd=repo_path, capture_output=True, encoding='utf-8', errors='replace', timeout=10
        )
        
        commit_result = subprocess.run(
            ['git', 'commit', '-m', f'Analytics sync {datetime.now().strftime("%Y-%m-%d %H:%M")}'],
            cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30
        )
        
        if commit_result.returncode != 0:
            if 'nothing to commit' in (commit_result.stdout or ''):
                return
            print(f"[ANALYTICS SYNC] Commit failed: {commit_result.stderr}")
            return
        
        # Step 5: Push (with retry on rejection)
        for attempt in range(2):
            push_result = subprocess.run(
                ['git', 'push', 'origin', 'main'],
                cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60
            )
            
            if push_result.returncode == 0:
                print(f"[ANALYTICS SYNC] ✅ Pushed analytics to git")
                return
            
            if attempt == 0 and ('rejected' in (push_result.stderr or '') or 'non-fast-forward' in (push_result.stderr or '')):
                # Behind remote - pull, rebase, and try again
                print(f"[ANALYTICS SYNC] Push rejected (another device pushed first), rebasing...")
                subprocess.run(
                    ['git', 'pull', '--rebase', 'origin', 'main'],
                    cwd=repo_path, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30
                )
            else:
                print(f"[ANALYTICS SYNC] ❌ Push failed: {push_result.stderr}")
                return
            
    except Exception as e:
        print(f"[ANALYTICS SYNC] Error: {e}")
        import traceback
        traceback.print_exc()

def pull_analytics_only(account=None):
    """Pull only the analytics file for a specific account from remote"""
    try:
        repo_path = os.path.dirname(os.path.abspath(__file__))
        account = account or DEFAULT_ANALYTICS_ACCOUNT
        
        analytics_file = f'data/analytics_{account}.json' if account != 'default' else 'data/analytics.json'
        analytics_path = os.path.join(repo_path, analytics_file)
        
        # Fetch latest from remote
        fetch_result = subprocess.run(
            ['git', 'fetch', 'origin', 'main'], 
            cwd=repo_path, 
            capture_output=True, 
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
        
        if fetch_result.returncode != 0:
            print(f"[ANALYTICS] Fetch failed: {fetch_result.stderr}")
            return False
        
        # Use git show to get the file content from origin/main
        # This is more reliable than checkout for getting remote file content
        show_result = subprocess.run(
            ['git', 'show', f'origin/main:{analytics_file}'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        
        if show_result.returncode == 0 and show_result.stdout:
            # File exists on remote - merge with local instead of overwriting
            os.makedirs(os.path.dirname(analytics_path), exist_ok=True)
            
            # Load remote analytics
            try:
                remote_analytics = json.loads(show_result.stdout)
            except json.JSONDecodeError as e:
                print(f"[ANALYTICS] Failed to parse remote file: {e}")
                return False
            
            # Load local analytics if it exists
            local_analytics = None
            if os.path.exists(analytics_path):
                try:
                    local_analytics = load_analytics(account)
                except:
                    local_analytics = {'sessions': [], 'summary': {}, 'account': account}
            else:
                local_analytics = {'sessions': [], 'summary': {}, 'account': account}
            
            # Merge sessions - combine both, removing duplicates by session_id
            local_session_ids = {s['session_id'] for s in local_analytics.get('sessions', [])}
            remote_sessions = remote_analytics.get('sessions', [])
            
            merged_sessions = local_analytics.get('sessions', [])[:]
            new_sessions_count = 0
            
            for remote_session in remote_sessions:
                if remote_session.get('session_id') not in local_session_ids:
                    merged_sessions.append(remote_session)
                    new_sessions_count += 1
            
            # Update analytics with merged sessions
            local_analytics['sessions'] = merged_sessions
            local_analytics['account'] = account
            
            # Keep only last 1000 sessions to prevent file bloat
            if len(local_analytics['sessions']) > 1000:
                local_analytics['sessions'] = local_analytics['sessions'][-1000:]
            
            # Save merged analytics
            save_analytics(local_analytics, account)
            
            if new_sessions_count > 0:
                print(f"[ANALYTICS] Merged {new_sessions_count} new session(s) from remote into {analytics_file}")
                return True
            else:
                print(f"[ANALYTICS] {analytics_file} already up to date (no new sessions)")
                return False
        else:
            # File doesn't exist on remote yet (first time, no remote data)
            if show_result.stderr and 'does not exist' in show_result.stderr:
                print(f"[ANALYTICS] {analytics_file} doesn't exist on remote yet (no remote data to pull)")
            else:
                print(f"[ANALYTICS] Could not pull {analytics_file}: {show_result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[ANALYTICS] Pull timeout - operation took too long")
        return False
    except Exception as e:
        print(f"[ANALYTICS] Pull error: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route('/api/analytics/refresh', methods=['POST'])
@agent_required
def refresh_analytics():
    """Sync analytics with git: push local changes, pull from other devices, merge"""
    try:
        username = session.get('user')
        if not username:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        pushed = False
        pulled = False
        
        # Use the robust sync function (pull-merge-push) to sync all analytics
        try:
            sync_analytics_to_git()
            pushed = True
        except Exception as e:
            print(f"[ANALYTICS REFRESH] Sync error: {e}")
        
        # Also do a targeted pull for this user's analytics (in case sync didn't cover it)
        pulled = pull_analytics_only(username)
        
        message = []
        if pushed:
            message.append('Analytics pushed to cloud')
        if pulled:
            message.append('Latest analytics pulled and merged')
        if not pushed and not pulled:
            message.append('Analytics already synced')
        
        return jsonify({
            'success': True, 
            'message': ' | '.join(message),
            'pushed': pushed,
            'pulled': pulled
        })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def analytics_sync_loop():
    """Background thread that syncs analytics periodically"""
    time.sleep(30)  # Wait before first sync
    
    while True:
        try:
            sync_analytics_to_git()
            time.sleep(300)  # Sync every 5 minutes
        except Exception as e:
            print(f"[ANALYTICS] Sync loop error: {e}")
            time.sleep(60)

# ============================================================================
# STARTUP - Initialize background threads
# ============================================================================

_startup_done = False

def start_background_services():
    """Start all background services (auto-update, analytics sync)"""
    global _startup_done, _update_thread
    
    if _startup_done:
        return
    _startup_done = True
    
    print("[STARTUP] Initializing background services...")
    
    # Start auto-update thread (only on local kiosks with git, not Render)
    if AUTO_UPDATE_ENABLED:
        _update_thread = threading.Thread(target=auto_update_loop, daemon=True)
        _update_thread.start()
        print("[AUTO-UPDATE] Auto-update system enabled (checking every 60s)")
    elif not HAS_GIT_REPO:
        print("[AUTO-UPDATE] Disabled (no .git folder - running on cloud deployment)")
    else:
        print("[AUTO-UPDATE] Disabled (RENDER environment detected)")
    
    # Enable analytics auto-sync on all devices with git repos
    # The sync function now does pull-merge-push, so multiple kiosks won't conflict
    if HAS_GIT_REPO and not IS_RENDER:
        analytics_thread = threading.Thread(target=analytics_sync_loop, daemon=True)
        analytics_thread.start()
        print("[ANALYTICS] Auto-sync enabled (push every 5 min, with merge from other devices)")
    else:
        print("[ANALYTICS] Auto-sync disabled (no git repo or cloud deployment)")

# Start services when module loads (works with both direct run and Waitress)
start_background_services()

if __name__ == '__main__':
    import socket
    # Explicitly set host and port for reliability
    host = '127.0.0.1'  # localhost only for security
    port = 5000
    
    print(f"[STARTUP] Starting Flask server on {host}:{port}...")
    print(f"[STARTUP] Access the kiosk at: http://localhost:{port}")
    
    try:
        app.run(host=host, port=port, debug=False, threaded=True)
    except OSError as e:
        if "Address already in use" in str(e) or "address is already in use" in str(e).lower():
            print(f"[ERROR] Port {port} is already in use!")
            print(f"[ERROR] Another instance might be running. Please stop it first.")
        else:
            print(f"[ERROR] Failed to start server: {e}")
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error starting server: {e}")
        import traceback
        traceback.print_exc()
        raise 

