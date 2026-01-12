import os
print("Current working directory:", os.getcwd())
print("Templates folder exists:", os.path.isdir('templates'))
print("index.html exists:", os.path.isfile('templates/index.html'))
import csv
from flask import Flask, render_template, request, jsonify, send_file
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
    
    # First, load from organized data/{company}/{language}/ structure
    company_dirs = glob.glob('data/*/')
    
    for company_dir in company_dirs:
        company_name = os.path.basename(company_dir.rstrip('/'))
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
                        
                        # Load review data
                        review_data = load_reviews(company, tid)
                        
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
            'duration': tour.get('duration', ''),
            'price': tour.get('price', 0),
            'rating': tour.get('rating', 0),
            'includes': tour.get('includes', ''),
            'highlights': tour.get('highlights', ''),
            'gallery': tour.get('gallery', [])
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
            for selected_activity in selected_activities:
                # Handle activity filtering with hierarchical relationships
                if selected_activity == 'island_tours':
                    # Island Tours is broad - include island_tours AND whitehaven_beach
                    if 'island_tours' in tour['activity_type'] or 'whitehaven_beach' in tour['activity_type']:
                        return True
                else:
                    # For specific activities, check if tour has that activity
                    if selected_activity in tour['activity_type']:
                        return True
            return False
        
        filtered_tours = [t for t in filtered_tours if tour_matches_any_activity(t)]
        print(f"   After activity filter: {len(filtered_tours)} tours")
    
    if criteria.get('family') == True:
        filtered_tours = [t for t in filtered_tours if t['family_friendly']]
    elif criteria.get('family') == False:
        filtered_tours = [t for t in filtered_tours if not t['family_friendly']]
    
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
    if family: criteria['family'] = (family == 'true')
    if meals: criteria['meals'] = (meals == 'true')
    if equipment: criteria['equipment'] = (equipment == 'true')
    
    # Apply filters using helper function
    filtered_tours = apply_filters(tours, criteria)
    
    # Check if this is for the map (needs all tours, no limit)
    for_map = request.args.get('for_map', '')
    
    # Randomize and limit results (but don't randomize if filtering by company - keep natural order)
    if for_map == 'true':
        # Return all tours for map view (no shuffle, no limit)
        limited_tours = filtered_tours
    else:
        # Normal filtering: show all matching results (no artificial limit)
        # Only shuffle if not filtering by company (keep company results in natural order)
        if not company:
            random.shuffle(filtered_tours)
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
    random.shuffle(available)
    selected = available[:count]
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

def build_tour_context(language='en'):
    """Build a concise tour knowledge base for AI context"""
    tours = load_all_tours(language)
    
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
        }
    }
    
    for tour in tours:
        name = tour.get('name', '')
        description = tour.get('description', '')[:200]  # First 200 chars
        price = tour.get('price_adult', 'N/A')
        duration = tour.get('duration', 'N/A')
        company = tour.get('company', '')
        key = tour.get('key', '')
        
        tour_info = {
            'name': name,
            'company': company,
            'description': description,
            'price': price,
            'duration': duration,
            'key': key
        }
        
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
    
    return tour_summary

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
- family: true (for family-friendly), false (for adults-only)
- meals: true (meals included)
- equipment: true (equipment provided)

**HOW TO RECOMMEND TOURS - USE [TOUR:key] TAGS:**
When recommending specific tours, use [TOUR:company__tour_id] tags so the cards MATCH your descriptions!

✅ CORRECT FORMAT:
"[Exciting 2-3 sentence intro about the activity type] ⛵

1. **Camira Sailing Adventure** [TOUR:cruisewhitsundays__camira_sailing_adventure] - [2-3 exciting sentences about THIS specific tour]

2. **Lady Enid Adults Only Sailing Day Trip** [TOUR:lady_enid__lady_enid_adults_only_sailing_day_trip] - [2-3 exciting sentences]

3. **Tongarra Day Sailing Tour** [TOUR:tongarra__tongarra_day_sailing_tour] - [2-3 exciting sentences]

Ready to set sail? 🌊"

**CRITICAL RULES:**
- Describe exactly 3 tours
- Use REAL tour names AND their [TOUR:key] tags from the available tours list
- Each description should be 2-3 compelling sentences with emojis
- The [TOUR:key] tag ensures the card shown MATCHES your description
- Include emojis throughout for personality! ⛵🏝️🌊✨🐠
- ALWAYS end with a follow-up question like "Would you like more details on any of these, or shall I show you different options? 🌟"

**METHOD 2 - Recommend Specific Tours (RARE - only when filters don't work):**
Use this ONLY when user asks for something that doesn't map to our filters:
- "kayaking tours" (not a standard filter option)
- "tours with Ocean Rafting company" (specific company)

For these RARE cases, use [TOUR:company__id] tags with descriptions.

⚠️ **WHEN TO USE WHICH METHOD:**
- "overnight sailing" → USE [FILTER:...] (matches multi_day + island_tours) - SHORT INTRO ONLY!
- "full day reef tour" → USE [FILTER:...] (matches full_day + great_barrier_reef) - SHORT INTRO ONLY!
- "Ocean Rafting specifically" → USE [TOUR:...] with descriptions (can't filter by company)

**CRITICAL TOUR DESCRIPTION RULES - YOU ARE REPLACING A REAL PERSON:**
When describing tours, you MUST give a compelling 3-4 sentence pitch for EACH tour that:
- Makes it sound exciting and unmissable!
- Highlights unique selling points (best views, exclusive access, amazing food, etc.)
- Creates urgency and FOMO ("one of Australia's most incredible experiences!")
- Uses vivid, sensory language ("crystal-clear waters", "powdery white sand", "breathtaking aerial views")
- Matches the tour to what the user specifically asked for

**EXAMPLE OF GREAT TOUR DESCRIPTIONS:**

"Here are some incredible options for you! 🌊

1. **Camira Sailing Adventure** [TOUR:cruisewhitsundays__camira_sailing_adventure] - Hop aboard the Whitsundays' most iconic orange catamaran for an unforgettable day of sailing! You'll slice through turquoise waters, snorkel vibrant coral reefs, and feast on a legendary BBQ lunch while dolphins play alongside. This is THE quintessential Whitsundays experience!

2. **Great Barrier Reef Full Day** [TOUR:cruisewhitsundays__great_barrier_reef_full_day_adventure] - Dive into one of the Seven Natural Wonders of the World! Spend a full day at the outer reef where visibility is incredible and marine life is abundant - expect to see giant Maori wrasse, sea turtles, and thousands of tropical fish. Includes a premium seafood lunch and all snorkel gear!

3. **Ocean Rafting Northern Exposure** [TOUR:oceanrafting__northern_exposure] - Hold on tight for an adrenaline-pumping speedboat adventure to Whitehaven Beach! You'll race across the waves, walk the famous white silica sands, and snorkel pristine fringing reefs. Perfect if you want excitement AND natural beauty in one action-packed day!"

**DO NOT** give boring one-line descriptions. Your job is to SELL these experiences and make visitors excited to book!

Available tours include:
{available_tours_json}

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
            max_tokens=500,
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
            
        elif filter_match:
            # AI wants to use filter system!
            print(f"🎯 AI requesting filter-based search")
            try:
                filter_criteria = json.loads(filter_match.group(1))
                print(f"   Filter criteria: {filter_criteria}")
                
                # Use existing filter logic
                filtered_tours = apply_filters(load_all_tours(language), filter_criteria)
                
                print(f"   Found {len(filtered_tours)} tours matching filters")
                print(f"   ✅ Showing all {len(filtered_tours)} matching tours")
                
                # Show ALL matching tours (removed 6-tour limit)
                # Convert prices in tour data for display
                tour_details = []
                for tour in filtered_tours:
                    tour_copy = tour.copy()
                    if tour_copy.get('price_adult'):
                        tour_copy['price_adult'] = convert_price_for_display(tour_copy['price_adult'], language)
                    if tour_copy.get('price_child'):
                        tour_copy['price_child'] = convert_price_for_display(tour_copy['price_child'], language)
                    tour_details.append(tour_copy)
                
                # Remove filter marker from message
                display_message = re.sub(filter_pattern, '', ai_message).strip()
                
                # Convert prices in display message to appropriate currency
                display_message = convert_price_for_display(display_message, language)
                
                # Limit to 3 tours
                tour_details = tour_details[:3]
                
                # Don't append duplicate descriptions - the AI already describes the tours
                # Just add a follow-up question if not already present
                if '?' not in display_message[-50:]:
                    display_message = display_message.rstrip() + "\n\nWould you like more details on any of these, or shall I show you different options?"
                
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

if __name__ == '__main__':
    app.run(debug=True) 
