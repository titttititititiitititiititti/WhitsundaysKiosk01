import os
print("Current working directory:", os.getcwd())
print("Templates folder exists:", os.path.isdir('templates'))
print("index.html exists:", os.path.isfile('templates/index.html'))
import csv
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from functools import wraps
import openai
from dotenv import load_dotenv
import random
import glob
import re
import json
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import qrcode
from io import BytesIO
import uuid
import time

# [CHAT-001] Initial Flask app serving chatbot UI and connecting tours.csv to GPT-4o.
# [CHAT-002] Load environment variables from .env using python-dotenv.

load_dotenv()

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'tour-kiosk-secret-key-2024')

# App version - update this when releasing new versions
APP_VERSION = "1.0.0"

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
        'ai_promotion_hints': {}
    }

def save_agent_settings(settings):
    """Save agent settings to config file"""
    settings_file = 'config/agent_settings.json'
    os.makedirs('config', exist_ok=True)
    settings['last_updated'] = datetime.now().isoformat()
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

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

def get_tour_promotion_status(tour_key):
    """Get the promotion status for a tour"""
    settings = load_agent_settings()
    promoted = settings.get('promoted_tours', {})
    
    for level, tours in promoted.items():
        if tour_key in tours:
            return level
    return None

def is_tour_enabled(tour_key):
    """Check if a tour is enabled (not disabled by agent)"""
    settings = load_agent_settings()
    return tour_key not in settings.get('disabled_tours', [])

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
    return session

def get_analytics_summary(account=None):
    """Get summary statistics from analytics data for an account"""
    account = account or DEFAULT_ANALYTICS_ACCOUNT
    analytics = load_analytics(account)
    sessions = analytics.get('sessions', [])
    
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
    
    # Calculate stats
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
    
    return {
        'total_sessions': total_sessions,
        'avg_duration_seconds': round(avg_duration, 1),
        'avg_duration_formatted': f"{int(avg_duration // 60)}m {int(avg_duration % 60)}s",
        'language_breakdown': languages,
        'mode_breakdown': modes,
        'top_tours_viewed': top_tours_viewed,
        'top_tours_booked': top_tours_booked,
        'total_chats': total_chats,
        'recent_sessions': sessions[-20:][::-1],  # Last 20, newest first
        'account': account
    }

# Company name mapping for prettier display
COMPANY_DISPLAY_NAMES = {
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

def find_thumbnail(company, tid, tour_name=None):
    """Find thumbnail for a tour, checking both hash-based and name-based folder structures"""
    extensions = [".jpg", ".jpeg", ".png", ".webp", ".JPG", ".JPEG", ".PNG", ".WEBP"]
    
    # Try hash-based ID folder first
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
    if tour_name:
        import re
        # Extract key words from tour name (lowercase, alphanumeric only)
        keywords = set(re.findall(r'[a-z0-9]+', tour_name.lower()))
        
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
    if any(word in text for word in ["jet boat", "jet ski", "speed boat", "thundercat", "fast boat", "adrenaline", "thrill"]):
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
def load_all_tours(language='en'):
    """Load tours from language-specific CSV folders with fallback to English and root directory"""
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
                        
                        if images_enabled:
                            thumb_path = find_thumbnail(company, tid, name)
                            
                            # Build gallery from image_urls (max 5 images for slideshow)
                            gallery = [thumb_path] if thumb_path else []
                            if row.get('image_urls'):
                                for img in row['image_urls'].split(',')[:4]:  # Max 4 more images (5 total with thumb)
                                    img_path = img.strip()
                                    if img_path and os.path.exists(img_path):
                                        img_url = '/' + img_path
                                        if img_url not in gallery:
                                            gallery.append(img_url)
                        else:
                            # Images disabled for this company - use random AI-generated placeholders
                            thumb_path = get_random_placeholder_image()
                            gallery = get_random_placeholder_gallery(3)
                        
                        # Load review data
                        review_data = load_reviews(company, tid)
                        
                        # Check if tour is disabled by agent
                        if not is_tour_enabled(key):
                            continue  # Skip disabled tours
                        
                        # Get promotion status
                        promotion = get_tour_promotion_status(key)
                        
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
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        
        users = load_users()
        
        if username in users and users[username]['password'] == password:
            session['user'] = username
            session['role'] = users[username]['role']
            session['name'] = users[username]['name']
            session['company'] = users[username].get('company')
            
            # Redirect based on role
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            
            if users[username]['role'] == 'agent':
                return redirect(url_for('agent_dashboard'))
            else:
                return redirect(url_for('operator_dashboard'))
        else:
            error = 'Invalid username or password'
    
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    return redirect(url_for('login'))

# ============================================================================
# AGENT MODE ROUTES
# ============================================================================

@app.route('/admin/agent')
# @agent_required  # Disabled for testing
def agent_dashboard():
    """Agent dashboard - manage tour visibility and promotions"""
    settings = load_agent_settings()
    
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
                        
                        all_tours.append({
                            'key': tour_key,
                            'id': row.get('id', ''),
                            'name': row.get('name', 'Unnamed Tour'),
                            'company': company,
                            'company_display': COMPANY_DISPLAY_NAMES.get(company, company),
                            'price': row.get('price_adult', ''),
                            'enabled': tour_key not in settings.get('disabled_tours', []),
                            'promotion': get_tour_promotion_status(tour_key)
                        })
        except Exception as e:
            print(f"Error loading {csvfile}: {e}")
    
    # Group by company
    companies = {}
    disabled_images_companies = settings.get('disabled_images_companies', [])
    for tour in all_tours:
        if tour['company'] not in companies:
            companies[tour['company']] = {
                'name': tour['company_display'],
                'tours': [],
                'images_enabled': tour['company'] not in disabled_images_companies
            }
        companies[tour['company']]['tours'].append(tour)
    
    # Get promotion stats
    promoted_counts = {
        'popular': len(settings.get('promoted_tours', {}).get('popular', [])),
        'featured': len(settings.get('promoted_tours', {}).get('featured', [])),
        'best_value': len(settings.get('promoted_tours', {}).get('best_value', []))
    }
    
    disabled_count = len(settings.get('disabled_tours', []))
    
    return render_template('agent_dashboard.html',
                          companies=companies,
                          settings=settings,
                          promoted_counts=promoted_counts,
                          disabled_count=disabled_count,
                          total_tours=len(all_tours),
                          company_names=COMPANY_DISPLAY_NAMES,
                          version=APP_VERSION)

@app.route('/admin/agent/api/toggle-tour', methods=['POST'])
# @agent_required  # Disabled for testing
def toggle_tour_visibility():
    """Toggle a tour's visibility (enabled/disabled)"""
    data = request.get_json()
    tour_key = data.get('tour_key')
    enabled = data.get('enabled', True)
    
    if not tour_key:
        return jsonify({'error': 'Tour key required'}), 400
    
    settings = load_agent_settings()
    disabled = settings.get('disabled_tours', [])
    
    if enabled and tour_key in disabled:
        disabled.remove(tour_key)
    elif not enabled and tour_key not in disabled:
        disabled.append(tour_key)
    
    settings['disabled_tours'] = disabled
    save_agent_settings(settings)
    
    return jsonify({'success': True, 'enabled': enabled})

@app.route('/admin/agent/api/set-promotion', methods=['POST'])
# @agent_required  # Disabled for testing
def set_tour_promotion():
    """Set or remove a tour's promotion level"""
    data = request.get_json()
    tour_key = data.get('tour_key')
    level = data.get('level')  # 'popular', 'featured', 'best_value', or None to remove
    
    if not tour_key:
        return jsonify({'error': 'Tour key required'}), 400
    
    settings = load_agent_settings()
    promoted = settings.get('promoted_tours', {'popular': [], 'featured': [], 'best_value': []})
    
    # Remove from all promotion levels first
    for promo_level in promoted:
        if tour_key in promoted[promo_level]:
            promoted[promo_level].remove(tour_key)
    
    # Add to new level if specified
    if level and level in promoted:
        promoted[level].append(tour_key)
    
    settings['promoted_tours'] = promoted
    save_agent_settings(settings)
    
    return jsonify({'success': True, 'level': level})

@app.route('/admin/agent/api/bulk-update', methods=['POST'])
# @agent_required  # Disabled for testing
def bulk_update_tours():
    """Bulk enable/disable or promote tours"""
    data = request.get_json()
    action = data.get('action')  # 'enable_all', 'disable_all', 'clear_promotions'
    company = data.get('company')  # Optional: limit to company
    
    settings = load_agent_settings()
    
    if action == 'enable_all':
        if company:
            settings['disabled_tours'] = [t for t in settings.get('disabled_tours', []) 
                                          if not t.startswith(company + '__')]
        else:
            settings['disabled_tours'] = []
    
    elif action == 'disable_all':
        # Get all tour keys
        csv_files = get_all_tour_csvs()
        all_keys = []
        for csvfile in csv_files:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        comp = row.get('company_name', '')
                        if not company or comp == company:
                            all_keys.append(f"{comp}__{row.get('id', '')}")
        settings['disabled_tours'] = list(set(settings.get('disabled_tours', []) + all_keys))
    
    elif action == 'clear_promotions':
        if company:
            for level in settings.get('promoted_tours', {}):
                settings['promoted_tours'][level] = [
                    t for t in settings['promoted_tours'][level] 
                    if not t.startswith(company + '__')
                ]
        else:
            settings['promoted_tours'] = {'popular': [], 'featured': [], 'best_value': []}
    
    save_agent_settings(settings)
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

# ============================================================================
# REMOTE UPDATE SYSTEM
# ============================================================================

import subprocess

@app.route('/health')
def health_check():
    """Simple health check endpoint for monitoring and update restart detection"""
    return jsonify({'status': 'ok', 'version': APP_VERSION})

@app.route('/admin/agent/api/check-updates')
def check_for_updates():
    """Check if there are updates available from GitHub"""
    try:
        # Fetch latest from remote
        result = subprocess.run(
            ['git', 'fetch', 'origin'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            timeout=30
        )
        
        # Check if we're behind origin/main
        result = subprocess.run(
            ['git', 'rev-list', 'HEAD..origin/main', '--count'],
            capture_output=True,
            text=True,
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
    """Pull latest changes from GitHub and restart the app"""
    try:
        # Pull the latest changes
        result = subprocess.run(
            ['git', 'pull', 'origin', 'main'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            timeout=60
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': result.stderr or 'Git pull failed'
            })
        
        # Schedule a restart
        # On Windows, we'll use a separate approach
        import sys
        import threading
        
        def restart_app():
            import time
            time.sleep(1)  # Give time for response to be sent
            
            # On Windows, we restart by running a batch command
            if sys.platform == 'win32':
                # Create a restart script
                restart_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'restart.bat')
                with open(restart_script, 'w') as f:
                    f.write('@echo off\n')
                    f.write('timeout /t 2 /nobreak > nul\n')
                    f.write(f'cd /d "{os.path.dirname(os.path.abspath(__file__))}"\n')
                    f.write(f'start "" "{sys.executable}" app.py\n')
                    f.write('exit\n')
                
                subprocess.Popen(['cmd', '/c', restart_script], 
                               creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # On Linux/Mac, use os.execv to restart in place
                os.execv(sys.executable, [sys.executable] + sys.argv)
            
            os._exit(0)
        
        # Start restart in background thread
        threading.Thread(target=restart_app, daemon=True).start()
        
        return jsonify({
            'success': True,
            'message': 'Update applied, restarting...',
            'output': result.stdout
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Timeout during update'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
    # Get language from query parameter or session (default: 'en')
    language = request.args.get('lang', 'en')
    tours = load_all_tours(language)
    random.shuffle(tours)
    initial_tours = tours[:12]
    shown_keys = [t['key'] for t in initial_tours]
    return render_template('index.html', tours=initial_tours, shown_keys=shown_keys, current_language=language)

@app.route('/api/tours')
def api_tours():
    """API endpoint to fetch filtered tours for video question flow"""
    language = request.args.get('lang', 'en')
    
    # Get filter parameters
    duration = request.args.get('duration', '')
    family_friendly = request.args.get('family_friendly', '')
    activities = request.args.getlist('activities')
    
    print(f"[API] ========== TOUR FILTERING ==========")
    print(f"[API] Duration filter: '{duration}'")
    print(f"[API] Family friendly filter: '{family_friendly}'")
    print(f"[API] Activities filter: {activities}")
    
    # Load all tours
    tours = load_all_tours(language)
    print(f"[API] Total tours loaded: {len(tours)}")
    
    filtered_tours = []
    duration_filtered = 0
    family_filtered = 0
    activities_filtered = 0
    
    for tour in tours:
        # Duration filter
        if duration:
            tour_duration = tour.get('duration_category', '').lower()
            if duration == 'half_day' and tour_duration not in ['half_day', 'half day']:
                duration_filtered += 1
                continue
            elif duration == 'full_day' and tour_duration not in ['full_day', 'full day']:
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
    
    # Sort filtered tours: promoted tours first, then by promotion level
    promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
    filtered_tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
    
    # Add gallery, includes, and company_name to each tour
    result_tours = []
    for tour in filtered_tours:
        tour_data = {
            'key': tour['key'],
            'name': tour['name'],
            'company': tour.get('company', ''),
            'company_name': tour.get('company_name', tour.get('company', '')),
            'image': tour.get('image', ''),
            'thumbnail_url': tour.get('thumbnail_url', ''),
            'thumbnail': tour.get('thumbnail', ''),
            'duration': tour.get('duration', ''),
            'price': tour.get('price', 0),
            'price_adult': tour.get('price_adult', ''),
            'rating': tour.get('rating', 0),
            'includes': tour.get('includes', ''),
            'highlights': tour.get('highlights', ''),
            'gallery': tour.get('gallery', []),
            'promotion': tour.get('promotion'),  # Include promotion status
            'is_promoted': tour.get('is_promoted', False),
            'review_rating': tour.get('review_rating', 0),
            'review_count': tour.get('review_count', 0),
            'uses_placeholder_images': tour.get('uses_placeholder_images', False),
            'departure_location': tour.get('departure_location', '')
        }
        result_tours.append(tour_data)
    
    return jsonify({'tours': result_tours})

@app.route('/tour/<key>')
def tour_page(key):
    """Load home page but with tour parameter - JavaScript will auto-open tour in modal"""
    language = request.args.get('lang', 'en')
    
    # Load all tours like normal home page
    tours = load_all_tours(language)
    random.shuffle(tours)
    initial_tours = tours[:12]
    shown_keys = [t['key'] for t in initial_tours]
    
    # Render index.html (home page) with tour_to_open parameter
    # JavaScript will detect this and automatically open the tour modal
    return render_template('index.html', tours=initial_tours, shown_keys=shown_keys, current_language=language, tour_to_open=key)
    
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
    """Generate QR code for a specific tour"""
    try:
        # Generate URL - use production domain if not localhost
        if 'localhost' in request.host or '127.0.0.1' in request.host:
            base_url = request.host_url.rstrip('/')
        else:
            base_url = 'https://www.filtour.com'
        
        language = request.args.get('lang', 'en')
        tour_url = f"{base_url}/tour/{key}?lang={language}"
        
        print(f"📱 Generating QR code for: {tour_url}")
        
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
        print(f"❌ Error generating tour QR code: {e}")
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

def apply_filters(tours, criteria):
    """Helper function to apply filter criteria to a list of tours"""
    filtered_tours = tours
    
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
        
        # OR logic: Show tours that match ANY of the selected activities
        def tour_matches_any_activity(tour):
            # Build searchable text for text-based matching (includes translated names)
            search_text = f"{tour.get('name', '')} {tour.get('description', '')} {tour.get('highlights', '')} {tour.get('includes', '')}".lower()
            
            for selected_activity in selected_activities:
                # First check the tour's activity_type array
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
                                    'ダイビング', 'スキューバ',  # Japanese
                                    '潜水', '水肺',  # Chinese
                                    'tauchen', 'plongée', 'buceo']  # German, French, Spanish
                    if any(word in search_text for word in diving_words):
                        return True
                elif selected_activity == 'snorkeling':
                    # Tours focused on snorkeling (not diving)
                    snorkel_words = ['snorkel', 'シュノーケル', 'シュノーケリング', '浮潜', 'schnorcheln', 'esnórquel']
                    dive_words_check = ['dive', 'diving', 'ダイビング', '潜水']
                    name_lower = tour.get('name', '').lower()
                    if any(word in search_text for word in snorkel_words):
                        if not any(word in name_lower for word in dive_words_check):
                            return True
                elif selected_activity == 'sailing':
                    sailing_words = ['sail', 'sailing', 'cruise', 'yacht', 'catamaran',
                                     'ヨット', 'クルーズ', 'セーリング',  # Japanese
                                     '帆船', '游船', '游轮',  # Chinese
                                     'segeln', 'voile', 'vela']  # German, French, Spanish
                    if any(word in search_text for word in sailing_words):
                        return True
                elif selected_activity == 'swimming':
                    swim_words = ['swim', 'beach', 'whitehaven', 'water', 'ビーチ', '海滩', 'strand', 'plage', 'playa']
                    if any(word in search_text for word in swim_words):
                        return True
                elif selected_activity == 'scenic_views':
                    scenic_words = ['scenic', 'view', 'helicopter', 'flight', 'aerial',
                                    '遊覧', '景色', 'ヘリコプター',  # Japanese
                                    '直升机', '风景',  # Chinese
                                    'rundflug', 'panoramique', 'escénico']  # German, French, Spanish
                    if any(word in search_text for word in scenic_words):
                        return True
                elif selected_activity == 'great_barrier_reef':
                    # General reef tours (includes snorkeling and diving)
                    reef_words = ['reef', 'リーフ', 'サンゴ', 'グレートバリア', '珊瑚', '大堡礁', 'riff', 'récif', 'arrecife']
                    if any(word in search_text for word in reef_words):
                        return True
                elif selected_activity == 'whitehaven_beach':
                    whitehaven_words = ['whitehaven', 'ホワイトヘブン', '白天堂', '白沙']
                    if any(word in search_text for word in whitehaven_words):
                        return True
                elif selected_activity == 'scenic_adventure':
                    adventure_words = ['scenic', 'adventure', 'helicopter', 'jet', 'アドベンチャー', '冒险', 'aventure']
                    if any(word in search_text for word in adventure_words):
                        return True
                        
            return False
        
        filtered_tours = [t for t in filtered_tours if tour_matches_any_activity(t)]
        print(f"   After activity filter: {len(filtered_tours)} tours")
    
    # Family filter logic:
    # - "Family with Kids" (family=True) → Only show family-friendly tours
    # - "Adults Only" (family=False/'adults_only') → Show ALL tours (adults can go anywhere)
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
    activities = request.args.getlist('activity')  # ✅ Get ALL selected activities
    family = request.args.get('family', '')
    meals = request.args.get('meals', '')
    equipment = request.args.get('equipment', '')
    company = request.args.get('company', '')
    
    print(f"Filter request: activities={activities}, duration={duration}, price={price}, family={family}, meals={meals}, equipment={equipment}")
    
    # Load all tours in the specified language
    tours = load_all_tours(language)
    
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
    
    # Randomize and limit results (but don't randomize if filtering by company - keep natural order)
    if for_map == 'true':
        # Return all tours for map view (no shuffle, no limit)
        limited_tours = filtered_tours
    else:
        # Normal filtering: show all matching results (no artificial limit)
        # Only shuffle if not filtering by company (keep company results in natural order)
        # BUT: always keep promoted tours at the top, shuffle within groups
        if not company:
            # Separate promoted and non-promoted tours
            promoted = [t for t in filtered_tours if t.get('promotion')]
            non_promoted = [t for t in filtered_tours if not t.get('promotion')]
            random.shuffle(non_promoted)  # Only shuffle non-promoted tours
            filtered_tours = promoted + non_promoted
        # Show all filtered results - no limit (users applied filters to see ALL matches)
        limited_tours = filtered_tours
    
    return jsonify({
        'tours': limited_tours,
        'total_found': len(filtered_tours)
    })

# Old basic chat removed - replaced with improved AI chat below (line 785)

@app.route('/more-tours')
def more_tours():
    language = request.args.get('lang', 'en')
    offset = int(request.args.get('offset', 0))
    count = int(request.args.get('count', 12))
    exclude_keys = set(request.args.get('exclude', '').split(',')) if request.args.get('exclude') else set()
    tours = load_all_tours(language)
    available = [t for t in tours if t['key'] not in exclude_keys]
    
    # Sort by promotion status first, then shuffle within groups
    promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
    promoted = [t for t in available if t.get('promotion')]
    non_promoted = [t for t in available if not t.get('promotion')]
    
    # Sort promoted by level, shuffle non-promoted
    promoted.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
    random.shuffle(non_promoted)
    
    # Combine: promoted first, then non-promoted
    sorted_tours = promoted + non_promoted
    selected = sorted_tours[offset:offset + count]
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
                                # Filter out broken image paths
                                image_urls = []
                                thumb = find_thumbnail(company, tid, row.get('name', ''))
                                if row.get('image_urls'):
                                    for img in row['image_urls'].split(','):
                                        img_path = img.strip()
                                        if not img_path:
                                            continue
                                        # Check if file actually exists before adding to gallery
                                        if os.path.exists(img_path):
                                            img_url = '/' + img_path
                                            if img_url != thumb:
                                                image_urls.append(img_url)
                                gallery = [thumb] + image_urls if thumb else image_urls
                            else:
                                # Images disabled - use random placeholders
                                gallery = get_random_placeholder_gallery(5)
                            
                            # Load full review data for detail page
                            review_data = load_reviews(company, tid)
                            
                            # Return all info needed for the detail page
                            return jsonify({
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
                    <h1>🏝️ New Tour Inquiry</h1>
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
                    <p>Inquiry submitted from Whitsundays Visitor Kiosk</p>
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

def extract_tour_filters(user_message, conversation_history):
    """Extract filter criteria from user message and conversation history"""
    # PRIORITIZE user's current message for activity detection
    current_msg = user_message.lower()
    
    # Only use USER messages from history (not assistant), skip welcome messages
    user_history = ""
    for msg in conversation_history[-4:]:
        if msg.get('role') == 'user':
            user_history += " " + msg.get('content', '').lower()
    
    filters = {}
    
    # Detect duration from current message OR user history
    # Include multi-language keywords (Chinese, Japanese, German, French, Spanish, Hindi)
    full_context = current_msg + " " + user_history
    
    # Duration keywords in multiple languages
    multi_day_keywords = ['multi-day', 'multiday', 'overnight', 'multi day', '2 day', '3 day', 'liveaboard',
                          '多日', '过夜', '两天', '三天',  # Chinese
                          '数日', '複数日', '二日', '三日',  # Japanese
                          'mehrtägig', 'übernachtung',  # German
                          'plusieurs jours', 'nuit',  # French
                          'varios días', 'noche']  # Spanish
    full_day_keywords = ['full day', 'full-day', 'all day', 'whole day',
                         '一整天', '全天', '整天',  # Chinese
                         '終日', '一日',  # Japanese
                         'ganztägig', 'ganzer tag',  # German
                         'journée complète', 'toute la journée',  # French
                         'día completo', 'todo el día']  # Spanish
    half_day_keywords = ['half day', 'half-day', 'few hours', 'morning', 'afternoon', 'short',
                         '半天', '上午', '下午', '几个小时',  # Chinese
                         '半日', '午前', '午後',  # Japanese
                         'halbtags', 'vormittag', 'nachmittag',  # German
                         'demi-journée', 'matin', 'après-midi',  # French
                         'medio día', 'mañana', 'tarde']  # Spanish
    
    if any(word in full_context for word in multi_day_keywords):
        filters['duration'] = 'multi_day'
    elif any(word in full_context for word in full_day_keywords):
        filters['duration'] = 'full_day'
    elif any(word in full_context for word in half_day_keywords):
        filters['duration'] = 'half_day'
    
    # Activity keywords in multiple languages
    diving_keywords = ['scuba', 'diving', 'dive tour', 'dive trip', 'certified dive',
                       '潜水', '水肺',  # Chinese
                       'ダイビング', 'スキューバ',  # Japanese
                       'tauchen', 'tauchgang',  # German
                       'plongée',  # French
                       'buceo', 'buzo']  # Spanish
    whitehaven_keywords = ['whitehaven', 'white haven', 'white sand', 'silica sand',
                           '白天堂', '白沙滩',  # Chinese
                           'ホワイトヘブン',  # Japanese
                           'weißer strand']  # German
    snorkeling_keywords = ['snorkel', 'snorkeling', 'snorkelling',
                           '浮潜',  # Chinese
                           'シュノーケリング', 'シュノーケル',  # Japanese
                           'schnorcheln',  # German
                           'palmes', 'tubas',  # French
                           'esnórquel']  # Spanish
    reef_keywords = ['reef', 'coral', 'great barrier', 'outer reef',
                     '珊瑚', '大堡礁', '礁',  # Chinese
                     'サンゴ', 'リーフ', 'グレートバリアリーフ',  # Japanese
                     'riff', 'korallen',  # German
                     'récif', 'corail',  # French
                     'arrecife', 'coral']  # Spanish
    sailing_keywords = ['sail', 'sailing', 'cruise', 'yacht', 'catamaran',
                        '帆船', '游船', '游轮', '双体船',  # Chinese
                        'ヨット', 'クルーズ', 'セーリング',  # Japanese
                        'segeln', 'kreuzfahrt', 'segelboot',  # German
                        'voile', 'croisière', 'yacht',  # French
                        'vela', 'navegación', 'crucero']  # Spanish
    scenic_keywords = ['helicopter', 'scenic flight', 'seaplane', 'aerial', 'jet boat',
                       '直升机', '水上飞机', '快艇',  # Chinese
                       'ヘリコプター', '遊覧飛行', '水上飛行機',  # Japanese
                       'hubschrauber', 'rundflug',  # German
                       'hélicoptère', 'vol panoramique',  # French
                       'helicóptero', 'vuelo escénico']  # Spanish
    beach_keywords = ['beach', '海滩', 'ビーチ', 'strand', 'plage', 'playa']
    
    # Detect activity PRIMARILY from current message first
    activity_detected = None
    
    # Check current message first - ORDER MATTERS! More specific filters first
    if any(word in current_msg for word in diving_keywords):
        activity_detected = 'diving'
    elif any(word in current_msg for word in whitehaven_keywords):
        activity_detected = 'whitehaven_beach'
    elif any(word in current_msg for word in snorkeling_keywords):
        activity_detected = 'snorkeling'
    elif any(word in current_msg for word in reef_keywords):
        activity_detected = 'great_barrier_reef'
    elif any(word in current_msg for word in sailing_keywords):
        activity_detected = 'island_tours'
    elif any(word in current_msg for word in scenic_keywords):
        activity_detected = 'scenic_adventure'
    elif any(word in current_msg for word in beach_keywords):
        activity_detected = 'whitehaven_beach'
    
    # If not found in current message, check user history
    if not activity_detected:
        if any(word in user_history for word in diving_keywords):
            activity_detected = 'diving'
        elif any(word in user_history for word in whitehaven_keywords):
            activity_detected = 'whitehaven_beach'
        elif any(word in user_history for word in snorkeling_keywords):
            activity_detected = 'snorkeling'
        elif any(word in user_history for word in reef_keywords):
            activity_detected = 'great_barrier_reef'
        elif any(word in user_history for word in sailing_keywords):
            activity_detected = 'island_tours'
    
    if activity_detected:
        filters['activity'] = activity_detected
    
    # Detect family filter (multi-language)
    family_keywords = ['family', 'kids', 'children', 'child',
                       '家庭', '孩子', '儿童',  # Chinese
                       '家族', '子供',  # Japanese
                       'familie', 'kinder',  # German
                       'famille', 'enfants',  # French
                       'familia', 'niños']  # Spanish
    if any(word in full_context for word in family_keywords):
        filters['family'] = True
    
    # Only return if we have at least activity OR duration
    if filters.get('activity') or filters.get('duration'):
        return filters
    
    return None

def build_promoted_tours_section(tour_context):
    """Build a text section describing promoted tours for the AI"""
    promoted = tour_context.get('promoted', {})
    sections = []
    
    # Popular tours (highest priority)
    if promoted.get('popular'):
        popular_names = [t['name'] for t in promoted['popular'][:5]]
        sections.append(f"🔥 POPULAR (Customer favorites - recommend enthusiastically!): {', '.join(popular_names)}")
    
    # Featured tours
    if promoted.get('featured'):
        featured_names = [t['name'] for t in promoted['featured'][:5]]
        sections.append(f"⭐ FEATURED (Highly recommended experiences): {', '.join(featured_names)}")
    
    # Best value
    if promoted.get('best_value'):
        value_names = [t['name'] for t in promoted['best_value'][:5]]
        sections.append(f"💎 BEST VALUE (Great value for money): {', '.join(value_names)}")
    
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
    """Quick check if chat will search for tours - returns immediately for UI feedback"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        # Check if we'll be searching for tours
        detected_filters = extract_tour_filters(user_message, conversation_history)
        
        return jsonify({
            'will_search_tours': detected_filters is not None,
            'filters': detected_filters
        })
    except Exception as e:
        return jsonify({'will_search_tours': False, 'error': str(e)})

@app.route('/chat', methods=['POST'])
def chat():
    """AI-powered chat endpoint for tour recommendations"""
    try:
        # Import price conversion for display
        from elevenlabs_tts import convert_price_for_display
        
        data = request.get_json()
        user_message = data.get('message', '')
        language = data.get('language', 'en')
        conversation_history = data.get('history', [])
        
        print(f"\n💬 CHAT REQUEST:")
        print(f"   User message: '{user_message}'")
        print(f"   Language: {language}")
        print(f"   History length: {len(conversation_history)} messages")
        for i, msg in enumerate(conversation_history[-3:], 1):  # Show last 3
            print(f"   History[{i}]: [{msg.get('role')}] {msg.get('content', '')[:50]}...")
        
        # STEP 1: Try to extract filter criteria from user message + history
        # This determines if we should fetch tours FIRST
        detected_filters = extract_tour_filters(user_message, conversation_history)
        pre_fetched_tours = []
        
        if detected_filters:
            print(f"🎯 DETECTED FILTERS: {detected_filters}")
            # Fetch matching tours FIRST so AI knows what it's describing!
            all_tours = load_all_tours(language)
            pre_fetched_tours = apply_filters(all_tours, detected_filters)
            
            # Sort by promotion status - promoted first!
            promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
            pre_fetched_tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
            
            # Limit to top 3 for AI to describe
            pre_fetched_tours = pre_fetched_tours[:3]
            print(f"   Found {len(pre_fetched_tours)} tours to describe:")
            for t in pre_fetched_tours:
                promo = f" 🔥 {t.get('promotion')}" if t.get('promotion') else ""
                print(f"      - {t['name']}{promo}")
        
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
            specific_tours_section = """

NOTE: No specific tours have been identified yet. Continue gathering user preferences!
When you have enough info, the system will provide specific tours to describe.
For now, ask engaging questions to understand what kind of experience they want.
"""
        
        if pre_fetched_tours:
            specific_tours_section = """

═══════════════════════════════════════════════════════════════
🚨 CRITICAL: YOU MUST DESCRIBE THESE EXACT TOURS IN THIS EXACT ORDER!
DO NOT substitute different tours. DO NOT change the order.
═══════════════════════════════════════════════════════════════
"""
            for i, tour in enumerate(pre_fetched_tours, 1):
                promo_badge = ""
                if tour.get('promotion') == 'popular':
                    promo_badge = " 🔥 POPULAR - Emphasize this is a top pick!"
                elif tour.get('promotion') == 'featured':
                    promo_badge = " ⭐ FEATURED"
                elif tour.get('promotion') == 'best_value':
                    promo_badge = " 💎 BEST VALUE"
                
                highlights = tour.get('highlights', '')[:400] if tour.get('highlights') else 'Amazing experience'
                includes = tour.get('includes', '')[:250] if tour.get('includes') else ''
                description = tour.get('description', '')[:300] if tour.get('description') else ''
                
                specific_tours_section += f"""
━━━ TOUR #{i} (describe this as number {i}) ━━━
NAME: "{tour['name']}" ← USE THIS EXACT NAME
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
═══════════════════════════════════════════════════════════════
YOUR OUTPUT FORMAT (COPY THIS STRUCTURE EXACTLY):
═══════════════════════════════════════════════════════════════

"Here are some incredible options for you! 🌊

1. **{tour1_name}** - [Write 2-3 exciting sentences about THIS tour using its details above. Make it sound amazing!]

2. **{tour2_name}** - [Write 2-3 exciting sentences about THIS tour using its details above. Make it sound amazing!]

3. **{tour3_name}** - [Write 2-3 exciting sentences about THIS tour using its details above. Make it sound amazing!]

Would you like more details on any of these? 🌟"

🚨 CRITICAL RULES:
- Use EXACTLY these tour names: "{tour1_name}", "{tour2_name}", "{tour3_name}"
- Do NOT substitute different tours!
- Do NOT reorder the tours!
- The intro must be short (1 sentence max) so TTS correctly highlights tour 1 for chunk 2
"""
        
        # Prepare system message with tour knowledge
        system_message = f"""You are a friendly and knowledgeable tour assistant for the Whitsunday Islands in Queensland, Australia. 

You help visitors discover the perfect tours through a guided conversation. You have access to {tour_context['total_tours']} amazing tours.

YOUR ROLE: Act like a helpful local expert who guides tourists step-by-step to find their ideal tour. Keep it conversational and natural!

Our tour categories:
- Great Barrier Reef Tours: {len(tour_context['categories']['reef'])} tours (snorkeling, diving, reef exploration)
- Whitehaven Beach Tours: {len(tour_context['categories']['whitehaven'])} tours (world-famous white silica sand beach)
- Sailing & Cruises: {len(tour_context['categories']['sailing'])} tours (day sails, sunset cruises, multi-day adventures)
- Diving & Snorkeling: {len(tour_context['categories']['diving'])} tours (beginners to advanced)
- Scenic Tours: {len(tour_context['categories']['scenic'])} tours (helicopter, seaplane, scenic flights)

**FEATURED & POPULAR TOURS** (PRIORITIZE THESE! When these match user preferences, recommend them FIRST and be EXTRA enthusiastic!):
{build_promoted_tours_section(tour_context)}

⚠️ **CRITICAL: Give 2-3 sentence descriptions of EACH tour - never just list names!**

**IF SPECIFIC TOURS ARE PROVIDED BELOW**: Describe those EXACT tours using their real names and details!
**IF NO SPECIFIC TOURS PROVIDED**: Ask follow-up questions to gather preferences first.

CONVERSATION STRATEGY - RECOMMEND AFTER 2 PREFERENCES:
1. **GATHER 2 PREFERENCES** before recommending (e.g., activity + duration, OR activity + group type)
2. **ONCE YOU HAVE 2 PREFERENCES → USE [FILTER:...] IMMEDIATELY!**
3. **NEVER SAY "Let me show you..." WITHOUT INCLUDING [FILTER:...] in the SAME message!**
4. Be SUPER enthusiastic - you're a passionate local who LOVES the Whitsundays!
5. **ALWAYS use [FILTER:{{...}}] syntax to show tours** - this is REQUIRED!
6. Example flow:
   - User: "sailing tours" (1 preference) → Ask about duration
   - User: "full day" (2 preferences) → MUST include [FILTER:{{"duration":"full_day","activity":"island_tours"}}]

**YOU ARE REPLACING A REAL PERSON!** 
- Be warm, personable, and genuinely excited about these tours
- Use emojis sparingly but effectively (🌊 🐠 ✨ 🏝️ 🚤 🌅)
- Give DETAILED 3-4 sentence descriptions that SELL each tour
- Highlight what makes each tour special and why they'll love it
- Create excitement and urgency - these are once-in-a-lifetime experiences!
- Sound like a friend who's been on these tours and can't wait for them to go too

**NEVER ASK ABOUT BUDGET/PRICE** - Users don't want to say prices out loud. They'll pick what fits their budget.

**ADD CONTEXT & PERSONALITY**: 
- "Great Barrier Reef? One of the 7 natural wonders! 🌊"
- "Whitehaven Beach has the world's purest silica sand - perfect for photos! 📸"
- "Multi-day trips let you see it all - sunrise, sunset, and the stars! ✨"

**ENCOURAGE SPECIFICITY**: Ask open-ended follow-ups like:
- "What would make this trip perfect for you?"
- "Any must-do activities?"
- "Celebrating anything special?"

Keep responses SHORT but ALWAYS include tour recommendations once you have 2 preferences!

**WHEN TO RECOMMEND TOURS**: Once user has given 2 preferences!
- 1 preference (e.g., "reef") → Ask ONE follow-up question (duration or group type)
- 2 preferences (e.g., "reef" + "full day") → **USE [FILTER:...] IMMEDIATELY!**
- User gives 2+ preferences in one message → **USE [FILTER:...] IMMEDIATELY!**
- **CRITICAL: You MUST include [FILTER:{{...}}] to show any tours!** 
- Without [FILTER:...], NO TOURS WILL BE DISPLAYED even if you describe them!

**NEVER GIVE EMPTY RESPONSES:**
- If you say "Let me show you..." or "Here are some options..." → YOU MUST include [FILTER:...] in the SAME message
- If you commit to showing tours, SHOW THEM - don't make the user wait or ask again
- If no tours match, be HONEST: "I couldn't find exact matches, but here are similar options: [FILTER:...]"

**EXAMPLE - CORRECT:**
"Speed boat tours are thrilling! 🚤 [FILTER:{{"duration":"full_day","activity":"scenic_adventure"}}]"

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

**TWO WAYS TO RESPOND**:

**METHOD 1 - Use Filter System (PREFERRED - USE THIS 90% OF THE TIME):**
When you have enough info about duration + activity/interest, USE FILTERS to show ALL matching tours!

⚠️ **CRITICAL: When using [FILTER:...], you MUST write a COMPLETE response with numbered descriptions!**
The TTS reads your text out loud and highlights tour cards in sync. Each numbered item (1. 2. 3.) highlights the corresponding card.

**PERFECT EXAMPLE with [FILTER:]:**
"Full-day Whitehaven Beach tours are absolutely incredible! 🏝️ Let me show you some amazing options! [FILTER:{{"duration":"full_day","activity":"whitehaven_beach"}}]

1. **Your first option** takes you to the world-famous Whitehaven Beach with its stunning white silica sand! You'll have plenty of time to swim, relax, and take incredible photos. This is a must-do experience! ✨

2. **This next tour** combines beach time with snorkeling at pristine coral reefs! You'll explore underwater gardens teeming with colorful fish before relaxing on the beach. Perfect for adventure lovers! 🐠

3. **Finally, this option** offers a more intimate experience with smaller group sizes and extra time at Hill Inlet lookout! You'll capture those iconic turquoise water photos and have a magical day. 📸

Would you like more details on any of these? 🌟"

**BAD EXAMPLE (NO TOUR CARDS WILL HIGHLIGHT!):**
"Here are some Whitehaven Beach tours: [FILTER:{{"activity":"whitehaven_beach"}}]"

Return filter criteria in this format: [FILTER:{{"duration":"X","activity":"Y"}}]

**CRITICAL: Map user interests to activities correctly:**
- "Great Barrier Reef", "reef", "snorkeling", "diving", "coral" → activity: "great_barrier_reef"
- "Whitehaven Beach", "beach", "white sand" → activity: "whitehaven_beach"  
- "Sailing", "cruise", "island hopping", "multi-day sailing" → activity: "island_tours"
- "Scenic", "helicopter", "seaplane", "flight" → activity: "scenic_adventure"
- "Speed boat", "jet boat", "fast boat", "adrenaline", "thrill" → activity: "scenic_adventure"

**WHEN TO USE FILTERS (REQUIRED to show tours!):**
✅ "multi-day diving and snorkeling" → [FILTER:{{"duration":"multi_day","activity":"great_barrier_reef"}}]
✅ "full-day reef tour" → [FILTER:{{"duration":"full_day","activity":"great_barrier_reef"}}]
✅ "half-day beach tour" → [FILTER:{{"duration":"half_day","activity":"whitehaven_beach"}}]
✅ "full-day sailing" → [FILTER:{{"duration":"full_day","activity":"island_tours"}}]
✅ "day sailing and cruise tours" → [FILTER:{{"duration":"full_day","activity":"island_tours"}}]
✅ "speed boat tour" → [FILTER:{{"activity":"scenic_adventure"}}]
✅ "half-day speed boat" → [FILTER:{{"duration":"half_day","activity":"scenic_adventure"}}]
✅ "full-day speed boat" → [FILTER:{{"duration":"full_day","activity":"scenic_adventure"}}]
✅ "multi-day sailing with meals" → [FILTER:{{"duration":"multi_day","activity":"island_tours","meals":true}}]
✅ "family-friendly full-day tour" → [FILTER:{{"duration":"full_day","family":true}}]
✅ "reef tour with equipment provided" → [FILTER:{{"activity":"great_barrier_reef","equipment":true}}]

Available filter options:
- duration: "half_day", "full_day", "multi_day"
- activity: "great_barrier_reef", "whitehaven_beach", "island_tours", "scenic_adventure"
- family: true (ONLY use when user specifically has children/kids - this filters to family-friendly tours only)
  NOTE: "Adults only" doesn't need a filter - adults can go on ANY tour! Don't use family:false
- meals: true (meals included)
- equipment: true (equipment provided)

**HOW TO RECOMMEND TOURS - NUMBERED LIST FORMAT IS REQUIRED!**
The TTS system reads your response out loud and highlights each tour card as it speaks. For this to work, you MUST use this EXACT numbered list format:

✅ CORRECT FORMAT (REQUIRED!):
"[Exciting 2-3 sentence intro paragraph about the activity type] ⛵

1. **First Tour Name** - [2-3 exciting sentences describing THIS tour, what makes it special, what they'll experience]

2. **Second Tour Name** - [2-3 exciting sentences about this tour]

3. **Third Tour Name** - [2-3 exciting sentences about this tour]

Would you like more details on any of these? 🌟"

**CRITICAL RULES FOR TTS HIGHLIGHTING TO WORK:**
- ⚠️ ALWAYS use numbered list format (1. 2. 3.) - this is how TTS knows when to highlight each card!
- Start each tour with the NUMBER followed by period: "1. " "2. " "3. "
- Use **bold** for tour names
- Each tour description MUST be 2-3 complete sentences (not just a few words!)
- Write descriptions that SELL the experience - this is what users hear!
- Include emojis throughout for personality! ⛵🏝️🌊✨🐠
- The intro paragraph plays first, THEN each numbered item highlights its corresponding tour card
- ALWAYS end with a follow-up question

**METHOD 2 - Recommend Specific Tours (RARE - only when filters don't work):**
Use this ONLY when user asks for something that doesn't map to our filters.

⚠️ **WHEN TO USE [FILTER:...]:**
- "overnight sailing" → [FILTER:{{"duration":"multi_day","activity":"island_tours"}}]
- "full day reef tour" → [FILTER:{{"duration":"full_day","activity":"great_barrier_reef"}}]
- "Whitehaven beach tours" → [FILTER:{{"activity":"whitehaven_beach"}}]

⚠️ **IMPORTANT: When using [FILTER:...], you MUST STILL write a FULL numbered list with descriptions!**
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
        
        print(f"\n📨 SENDING TO OPENAI:")
        print(f"   Total messages: {len(messages)}")
        print(f"   System message: {len(system_message)} chars")
        for i, msg in enumerate(messages[1:], 1):  # Skip system message
            print(f"   Message {i}: [{msg['role']}] {msg['content'][:60]}...")
        
        # Call OpenAI
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1200,  # Increased to allow detailed tour descriptions
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
            print(f"📋 Quick reply options: {quick_reply_options}")
        
        print(f"AI Response: {ai_message[:200]}...")
        
        # PRIORITY: Use specific [TOUR:] tags if provided (they match the AI's descriptions!)
        if tour_matches:
            print(f"🎯 AI recommending specific tours with [TOUR:] tags")
            print(f"   Found {len(tour_matches)} tour keys: {tour_matches}")
            
            # Get full tour details for the specified tours
            tours = load_all_tours(language)
            tour_details = []
            for tour_key in tour_matches:
                tour = next((t for t in tours if t.get('key') == tour_key), None)
                if tour:
                    tour_copy = tour.copy()
                    if tour_copy.get('price_adult'):
                        tour_copy['price_adult'] = convert_price_for_display(tour_copy['price_adult'], language)
                    if tour_copy.get('price_child'):
                        tour_copy['price_child'] = convert_price_for_display(tour_copy['price_child'], language)
                    tour_details.append(tour_copy)
                    print(f"   ✅ Found tour: {tour.get('name')} ({tour_key})")
                else:
                    print(f"   ❌ Tour not found: {tour_key}")
            
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
                'quick_reply_options': quick_reply_options
            }
            
        elif filter_match or pre_fetched_tours:
            # We have tours to show! Either from [FILTER:] tag or pre-fetched
            print(f"🎯 Returning tour recommendations")
            try:
                # Use pre-fetched tours if available, otherwise fetch based on filter
                if pre_fetched_tours:
                    print(f"   Using {len(pre_fetched_tours)} pre-fetched tours (AI described these!)")
                    filtered_tours = pre_fetched_tours
                elif filter_match:
                    filter_criteria = json.loads(filter_match.group(1))
                    print(f"   Filter criteria from AI: {filter_criteria}")
                    filtered_tours = apply_filters(load_all_tours(language), filter_criteria)
                    
                    # Sort by promotion status
                    promotion_order = {'popular': 0, 'featured': 1, 'best_value': 2, None: 3}
                    filtered_tours.sort(key=lambda t: promotion_order.get(t.get('promotion'), 3))
                    filtered_tours = filtered_tours[:3]
                
                print(f"   Returning {len(filtered_tours)} tours:")
                for t in filtered_tours:
                    promo = f" 🔥 {t.get('promotion')}" if t.get('promotion') else ""
                    print(f"      - {t['name']}{promo}")
                
                # Convert prices for display
                tour_details = []
                for tour in filtered_tours:
                    tour_copy = tour.copy()
                    if tour_copy.get('price_adult'):
                        tour_copy['price_adult'] = convert_price_for_display(tour_copy['price_adult'], language)
                    if tour_copy.get('price_child'):
                        tour_copy['price_child'] = convert_price_for_display(tour_copy['price_child'], language)
                    tour_details.append(tour_copy)
                
                # Remove filter marker from message if present
                display_message = re.sub(filter_pattern, '', ai_message).strip() if filter_match else ai_message
                display_message = convert_price_for_display(display_message, language)
                
                # Add follow-up if missing
                if '?' not in display_message[-50:]:
                    display_message = display_message.rstrip() + "\n\nWould you like more details on any of these?"
                
                response_data = {
                    'success': True,
                    'message': display_message,
                    'recommended_tours': tour_details,
                    'tour_keys': [t['key'] for t in tour_details],
                    'used_filters': True,
                    'filter_count': len(filtered_tours),
                    'quick_reply_options': quick_reply_options
                }
                
            except Exception as e:
                print(f"❌ Error parsing filter criteria: {e}")
                # Fall back to no-tour response
                filter_match = None
        
        # Only reach here if neither [TOUR:] tags nor [FILTER:] were found/worked
        if not tour_matches and not filter_match:
            print(f"🤖 AI response has no tour recommendations")
            
            # Just return the message as-is (conversational response)
            display_message = convert_price_for_display(ai_message, language)
            
            response_data = {
                'success': True,
                'message': display_message,
                'recommended_tours': [],
                'tour_keys': [],
                'used_filters': False,
                'quick_reply_options': quick_reply_options
            }
        
        print(f"\n📤 SENDING TO FRONTEND:")
        print(f"   Success: {response_data['success']}")
        print(f"   Message length: {len(response_data['message'])} chars")
        print(f"   Tours to send: {len(response_data['recommended_tours'])}")
        for i, tour in enumerate(response_data['recommended_tours'], 1):
            print(f"   Tour {i}: {tour.get('name')} ({tour.get('key')})")
        print(f"   JSON size: {len(str(response_data))} bytes\n")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
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
        
        print(f"✅ Created session {session_id} with {len(data.get('tours', []))} tours")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'url': recommendations_url
        })
        
    except Exception as e:
        print(f"❌ Error creating session: {e}")
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
        print(f"❌ Error generating QR code: {e}")
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
        print(f"❌ Error generating QR code: {e}")
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
        
        print(f"📱 Displaying {len(tours)} tours for session {session_id}")
        
        return render_template('recommendations.html',
                             tours=tours,
                             preferences=preferences,
                             chat_summary=chat_summary,
                             session_id=session_id)
        
    except Exception as e:
        print(f"❌ Error displaying recommendations: {e}")
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
                    <p style="margin: 5px 0;">{"<br>".join([f"✓ {p}" for p in prefs_list])}</p>
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
                <h1 style="margin: 0;">🏝️ Your Whitsundays Tour Recommendations</h1>
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
                        📱 View All Recommendations Online
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
        subject = "🏝️ Your Whitsundays Tour Recommendations"
        content = Content("text/html", email_html)
        
        mail = Mail(from_email, to_email, subject, content)
        response = sg.send(mail)
        
        print(f"✅ Email sent to {email} - Status: {response.status_code}")
        
        return jsonify({
            'success': True,
            'message': 'Recommendations sent to your email!'
        })
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
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
    for csvfile in glob.glob('tours_*_cleaned_with_media.csv'):
        company = csvfile.replace('tours_', '').replace('_cleaned_with_media.csv', '')
        if company not in seen_companies:
            csv_files.append(csvfile)
            seen_companies.add(company)
    
    # 3. Check root directory for _cleaned.csv (fallback)
    for csvfile in glob.glob('tours_*_cleaned.csv'):
        if '_with_media' in csvfile:
            continue
        company = csvfile.replace('tours_', '').replace('_cleaned.csv', '')
        if company not in seen_companies:
            csv_files.append(csvfile)
            seen_companies.add(company)
    
    return csv_files

@app.route('/admin/editor')
def tour_editor():
    """Tour Editor - Developer Mode for editing tour listings"""
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
                        company = row.get('company_name', 'unknown')
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
    
    return render_template('tour_editor.html', 
                          companies=companies,
                          company_names=COMPANY_DISPLAY_NAMES)

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
    """API endpoint to save tour changes back to CSV"""
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
        
        # Read all tours
        rows = []
        fieldnames = None
        
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        # Check for new fields that need to be added
        new_fields = []
        for field in new_data.keys():
            if field not in fieldnames:
                new_fields.append(field)
        
        if new_fields:
            fieldnames = list(fieldnames) + new_fields
        
        # Find and update the tour
        tour_found = False
        for i, row in enumerate(rows):
            if row.get('id') == tid:
                # Update the row with new data
                for field, value in new_data.items():
                    row[field] = value
                rows[i] = row
                tour_found = True
                break
        
        if not tour_found:
            return jsonify({'error': 'Tour not found'}), 404
        
        # Write back to CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return jsonify({'success': True, 'message': 'Tour saved successfully'})
        
    except Exception as e:
        print(f"Error saving tour: {e}")
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
    """API endpoint to get all images for a tour"""
    try:
        company, tid = key.split('__', 1)
    except ValueError:
        return jsonify({'error': 'Invalid tour key'}), 400
    
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
        
        # Use default account for analytics (kiosk doesn't know about user accounts)
        session = log_analytics_event(session_id, event_type, event_data, account=DEFAULT_ANALYTICS_ACCOUNT)
        
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
        log_analytics_event(session_id, 'session_start', {
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'referrer': request.headers.get('Referer', 'direct')
        }, account=DEFAULT_ANALYTICS_ACCOUNT)
        
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

if __name__ == '__main__':
    app.run(debug=True) 
