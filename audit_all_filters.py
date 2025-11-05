import csv
import glob
import re
from collections import Counter

# Copy all parse functions from app.py
def parse_duration(duration_str):
    """Parse duration string into categories - same logic as app.py"""
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
    
    # 1. Whitehaven Beach (very specific)
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
    if any(word in text for word in ["island hop", "island tour", "cruise", "sailing", "sail", "catamaran", "yacht", "boat tour", "day trip"]):
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

# Audit all tours
print("="*80)
print("COMPREHENSIVE FILTER AUDIT")
print("="*80)
print()

all_tours = []
issues = []

for csv_file in sorted(glob.glob('tours_*_cleaned_with_media.csv')):
    with open(csv_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        company = csv_file.replace('tours_', '').replace('_cleaned_with_media.csv', '')
        
        for row in reader:
            tour = {
                'name': row.get('name', '').strip(),
                'company': company,
                'duration_raw': row.get('duration', ''),
                'price_adult': row.get('price_adult', ''),
                'price_child': row.get('price_child', ''),
                'includes': row.get('includes', ''),
                'highlights': row.get('highlights', ''),
                'description': row.get('description', ''),
            }
            
            # Parse all filter values
            tour['duration_category'] = parse_duration(tour['duration_raw'])
            tour['price_category'] = parse_price(tour['price_adult'])
            tour['activity_type'] = parse_activity_type(tour['highlights'], tour['description'], tour['name'])
            tour['family_friendly'] = is_family_friendly(tour['price_child'], tour['includes'], tour['description'])
            tour['meals_included'] = has_meals_included(tour['includes'])
            tour['equipment_included'] = has_equipment_included(tour['includes'])
            
            all_tours.append(tour)
            
            # Check for issues
            if not tour['name']:
                issues.append(f"❌ Empty tour name in {company}")
            if tour['duration_category'] == 'unknown':
                issues.append(f"⚠️  {tour['name']} ({company}): Duration = 'unknown' (raw: '{tour['duration_raw']}')")
            if tour['price_category'] == 'unknown':
                issues.append(f"⚠️  {tour['name']} ({company}): Price = 'unknown' (raw: '{tour['price_adult']}')")

print(f"Total tours analyzed: {len(all_tours)}\n")

# Show distribution of each filter
print("DURATION CATEGORIES:")
duration_counts = Counter([t['duration_category'] for t in all_tours])
for cat, count in sorted(duration_counts.items()):
    print(f"  {cat}: {count} tours")

print("\nPRICE CATEGORIES:")
price_counts = Counter([t['price_category'] for t in all_tours])
for cat, count in sorted(price_counts.items()):
    print(f"  {cat}: {count} tours")

print("\nACTIVITY TYPES:")
# Flatten the lists of activities to count each activity type
all_activities = []
for t in all_tours:
    all_activities.extend(t['activity_type'])
activity_counts = Counter(all_activities)
for cat, count in sorted(activity_counts.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count} tours")
print(f"  (Note: Tours can appear in multiple categories)")

print("\nFAMILY FRIENDLY:")
family_counts = Counter([t['family_friendly'] for t in all_tours])
print(f"  Yes: {family_counts.get(True, 0)} tours")
print(f"  No: {family_counts.get(False, 0)} tours")

print("\nMEALS INCLUDED:")
meals_counts = Counter([t['meals_included'] for t in all_tours])
print(f"  Yes: {meals_counts.get(True, 0)} tours")
print(f"  No: {meals_counts.get(False, 0)} tours")

print("\nEQUIPMENT INCLUDED:")
equipment_counts = Counter([t['equipment_included'] for t in all_tours])
print(f"  Yes: {equipment_counts.get(True, 0)} tours")
print(f"  No: {equipment_counts.get(False, 0)} tours")

# Show issues
if issues:
    print("\n" + "="*80)
    print("ISSUES FOUND:")
    print("="*80)
    for issue in issues:
        print(issue)
else:
    print("\n" + "="*80)
    print("✅ NO ISSUES FOUND - All tours have valid filter values!")
    print("="*80)
