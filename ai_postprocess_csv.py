import csv
import os
import sys
import openai
from dotenv import load_dotenv
import re
from bs4 import BeautifulSoup
from typing import List, Tuple

# Load environment variables
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

# Allow CLI args: python ai_postprocess_csv.py <input_csv> [output_csv] [--force-include]
# --force-include: Skip the is_tour check and include all scraped pages as tours
DEFAULT_INPUT = 'tours_zigzagwhitsundays.csv'
DEFAULT_OUTPUT = 'tours_zigzagwhitsundays_cleaned.csv'

# Check for --force-include flag
FORCE_INCLUDE = '--force-include' in sys.argv
if FORCE_INCLUDE:
    sys.argv.remove('--force-include')
    print("[!] FORCE INCLUDE MODE: All scraped pages will be saved as tours (ignoring is_tour check)")

if len(sys.argv) >= 2:
    INPUT_CSV = sys.argv[1]
else:
    INPUT_CSV = DEFAULT_INPUT

if len(sys.argv) >= 3:
    OUTPUT_CSV = sys.argv[2]
else:
    if INPUT_CSV.lower().endswith('.csv'):
        OUTPUT_CSV = INPUT_CSV[:-4] + '_cleaned.csv'
    else:
        OUTPUT_CSV = DEFAULT_OUTPUT

if not os.path.exists(INPUT_CSV):
    print(f"Input CSV not found: {INPUT_CSV}")
    print("Usage: python ai_postprocess_csv.py <input_csv> [output_csv]")
    sys.exit(1)

# Deduplicate and clean raw_text

def clean_and_dedup_text(text):
    seen = set()
    cleaned = []
    for line in text.split('\n'):
        l = line.strip()
        # Skip if <4 words
        if len(l.split()) < 4:
            continue
        # Skip if duplicate
        if l in seen:
            continue
        seen.add(l)
        cleaned.append(line)
    return '\n'.join(cleaned)

# Extract tour chunks from raw_text
# Use \r?$ to handle both Windows (\r\n) and Unix (\n) line endings
TOUR_START_RE = re.compile(r'^=== TOUR START: (.+?) ===\r?$', re.MULTILINE)
TOUR_END_RE = re.compile(r'^=== TOUR END: (.+?) ===\r?$', re.MULTILINE)

def extract_tour_chunks(raw_text):
    chunks = []
    starts = [m for m in TOUR_START_RE.finditer(raw_text)]
    ends = [m for m in TOUR_END_RE.finditer(raw_text)]
    for start in starts:
        tour_name = start.group(1)
        start_idx = start.end()
        # Find the corresponding end marker
        end = next((e for e in ends if e.group(1) == tour_name and e.start() > start.start()), None)
        if end:
            end_idx = end.start()
            chunk = raw_text[start_idx:end_idx].strip()
        else:
            chunk = raw_text[start_idx:].strip()
        chunks.append((tour_name, chunk))
    return chunks

def strip_html_tags(text):
    soup = BeautifulSoup(text, 'html.parser')
    return soup.get_text(separator=' ', strip=True)

def clean_field(text):
    if text is None:
        return ''
    if isinstance(text, list):
        text = '\n'.join(str(x) for x in text)
    text = str(text)
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        l = line.strip()
        # Extract text from HTML tags if present
        if l.startswith('<') and l.endswith('>'):
            l = strip_html_tags(l)
        # Skip if now empty, too short, or just symbols
        if not l or len(l) < 3 or all(not c.isalnum() for c in l):
            continue
        cleaned.append(l)
    return '\n'.join(cleaned)

# --------------------------------------------
# Normalization helpers for structured fields
# --------------------------------------------

DURATION_HOURS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(hours|hour|hrs|hr|h)", re.IGNORECASE)
DURATION_DAYS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(days|day|nights|night|d)\b", re.IGNORECASE)

def parse_duration_normalized(text: str) -> Tuple[str, str, str]:
    """Return (duration_hours, duration_days, duration_category)."""
    if not text:
        return '', '', 'unknown'
    t = text.lower()
    hours_val = None
    days_val = None
    # Explicit numbers
    m_hours = DURATION_HOURS_RE.search(t)
    if m_hours:
        try:
            hours_val = float(m_hours.group(1))
        except Exception:
            pass
    m_days = DURATION_DAYS_RE.search(t)
    if m_days:
        try:
            days_val = float(m_days.group(1))
        except Exception:
            pass
    # Heuristics
    if 'half' in t and 'day' in t and hours_val is None:
        hours_val = 3.5
    if 'full' in t and 'day' in t and hours_val is None:
        hours_val = 8.0
    if 'multi' in t and 'day' in t and days_val is None:
        days_val = 2.0
    if 'overnight' in t and days_val is None:
        days_val = 2.0
    # Derive category
    category = 'unknown'
    if days_val and days_val >= 2:
        category = 'multi_day'
    elif hours_val is not None:
        if hours_val <= 4.0:
            category = 'half_day'
        elif hours_val <= 9.0:
            category = 'full_day'
        else:
            category = 'multi_day'
    elif 'multi day' in t or 'multi-day' in t:
        category = 'multi_day'
    elif 'half day' in t:
        category = 'half_day'
    elif 'full day' in t or 'day tour' in t:
        category = 'full_day'
    return (
        f"{hours_val}" if hours_val is not None else '',
        f"{days_val}" if days_val is not None else '',
        category
    )

WATER_KW = {'snorkel','dive','reef','boat','sail','sailing','cruise','island','jet ski','jetski','kayak','paddle','glass bottom'}
AIR_KW = {'scenic flight','flight','helicopter','aerial','plane','sky'}
LAND_KW = {'hike','walk','track','waterfall','segway','4wd','buggy','tour bus','coach'}

def extract_tour_type(text: str) -> str:
    t = (text or '').lower()
    is_water = any(k in t for k in WATER_KW)
    is_air = any(k in t for k in AIR_KW)
    is_land = any(k in t for k in LAND_KW)
    types = [is_water, is_air, is_land]
    if sum(1 for x in types if x) >= 2:
        return 'combo'
    if is_water:
        return 'water'
    if is_air:
        return 'air'
    if is_land:
        return 'land'
    return 'other'

LOCATION_WHITELIST = [
    'whitehaven', 'hill inlet', 'hook island', 'airlie beach', 'whitsunday island', 'hamilton island',
    'daydream island', 'reefworld', 'great barrier reef', 'langford', 'bowen', 'proserpine', 'cannonvale'
]

def extract_locations(text: str) -> List[str]:
    t = (text or '').lower()
    found = []
    for loc in LOCATION_WHITELIST:
        if loc in t:
            found.append(loc.title())
    return sorted(set(found))

TAGS_KW = {
    'sunset': ['sunset','dusk','golden hour'],
    'family-friendly': ['family','kids','children','child'],
    'small-group': ['small group','small-group','intimate'],
    'private': ['private','charter','exclusive'],
    'luxury': ['luxury','premium','vip'],
    'adventure': ['adventure','adrenaline','thrill','fast'],
    'relaxation': ['relax','leisure','chill','laid-back']
}

def derive_tags(text: str) -> List[str]:
    t = (text or '').lower()
    tags = []
    for tag, kws in TAGS_KW.items():
        if any(k in t for k in kws):
            tags.append(tag)
    return sorted(set(tags))

def derive_audience(text: str, price_child: str) -> str:
    t = (text or '').lower()
    if 'adults only' in t or '18+' in t:
        return 'adults_only'
    if price_child and str(price_child).strip() and 'n/a' not in str(price_child).lower():
        return 'family'
    if 'family' in t or 'kids' in t or 'children' in t:
        return 'family'
    return 'general'

def derive_intensity(text: str) -> str:
    t = (text or '').lower()
    if any(k in t for k in ['adrenaline','thrill','fast','jet','raft']):
        return 'adventurous'
    if any(k in t for k in ['relax','leisure','gentle','easy','cruise']):
        return 'relaxed'
    return 'moderate'

# Read the input CSV
with open(INPUT_CSV, newline='', encoding='utf-8') as infile:
    reader = list(csv.DictReader(infile))
    fieldnames = reader[0].keys() if reader else []

# Prepare output rows
output_rows = []

for row in reader:
    raw_text = row.get('raw_text', '')
    if not raw_text.strip():
        output_rows.append(row)
        continue
    for tour_name, chunk in extract_tour_chunks(raw_text):
        filtered_text = clean_and_dedup_text(chunk)
        filtered_text = filtered_text[:8000]  # Increased from 2000 to preserve more details
        # Get URL for context
        page_url = row.get('link_booking') or row.get('link_more_info') or ''
        # Add price info to the prompt so the AI can see it
        price_info = ""
        if row.get('price_adult'):
            price_info += f"SCRAPED PRICE DATA (may contain multiple options): {row['price_adult']}\n"
        if row.get('price_child'):
            price_info += f"Child Price: {row['price_child']}\n"
        if row.get('price_tiers'):
            price_info += f"Price Tiers: {row['price_tiers']}\n"
        prompt = f"""You are organizing tour information from a webpage. Your job is to PRESERVE and STRUCTURE content, not shorten it.

PAGE URL: {page_url}
PAGE H1 TITLE (from scraper): {tour_name}

Return a JSON object with these fields:

CRITICAL RULES:
1. USE THE H1 TITLE AS THE TOUR NAME - The "PAGE H1 TITLE" above is the main heading from this specific tour page. Use it as the tour name (you can clean it up slightly). IGNORE other tour names that appear in navigation menus, "related tours", or sidebars.
2. PRESERVE details in SEPARATE FIELDS - itineraries go in 'itinerary', menus go in 'menu', inclusions go in 'includes'
3. Keep DESCRIPTION focused on the experience and vibe - NOT a repeat of other fields
4. PARSE PRICING CAREFULLY - the SCRAPED PRICE DATA field may contain multiple pricing options mashed together. Your job is to separate them!

REQUIRED FIELDS:
- is_tour: (boolean) Is this a real bookable tour?
- name: (string) Use the PAGE H1 TITLE provided above as the tour name. Clean it up if needed (remove extra punctuation, etc.) but keep the core name. Do NOT use tour names from navigation menus or "related tours" sections - those are for OTHER tours, not this one.
- description: (string) SHORT, engaging 2-4 paragraph overview focused on:
  * The experience and vibe (luxury? adventure? relaxation?)
  * What makes this tour unique
  * Who would love it
  * DO NOT repeat menu items, inclusions list, or highlights here - those have separate fields
  * DO NOT include "Includes:" sections - use the 'includes' field
  * Keep it concise and marketing-focused, NOT an information dump
- price_adult: Extract the LOWEST or STANDARD adult price (format: "A$XXX" or "FROM A$XXX")
- price_child: Child price if mentioned separately
- price_tiers: (string) PARSE ALL pricing options from SCRAPED PRICE DATA with MEANINGFUL DESCRIPTIVE NAMES. 
  
  PRICING TIER RULES:
  * Each tier MUST have a unique descriptive name (NOT just "Adult", "Child", "Senior")
  * LOOK FOR PACKAGE/OPTION DESCRIPTIONS in HTML tables, dropdowns, or lists
  * Common package types: meal options ("with Marina Tavern lunch"), transfer options ("with coach transfers"), cabin types, activity bundles
  * If multiple prices for same category, add context: "Adult (Standard): A$269 | Adult (Premium): A$279"
  * Look for cabin types, dates, options: "Single Bunk: A$490 | Private Double Cabin: A$1,125"
  * If dates differ: "Adult (May-Oct): A$269 | Adult (Nov-Apr): A$279"
  * If options differ: "Adult (with transfers): A$149 | Adult (no transfers): A$129"
  * Package examples: "Day cruise with Marina Tavern lunch: A$152 | Day cruise with Popeye's lunch: A$135"
  * ONLY use generic "Adult: A$X" if there's truly ONE price per category with no package description
  * Format: "Tier Name: PRICE | Tier Name: PRICE" separated by pipe (|) 
- duration: (string) MUST be a TIME AMOUNT. Valid examples: "2 Hours", "Half Day", "Full Day", "2 Days 1 Night", "3 Days 2 Nights". NEVER use "Evening", "Morning", "Sunset" - these are times, not durations. If unclear, return null.
- times: Departure/return times (e.g., "Departs 9am, Returns 5pm"). If unclear, return null.
- departure_location: (string) Where the tour departs from. Look for specific locations like "Abell Point Marina", "Port of Airlie", "Shute Harbour", "Coral Sea Marina", marina names, or full addresses. Be specific - don't just say "Airlie Beach" if a specific marina is mentioned.
- includes: Everything included (be thorough)
- highlights: Key features (5-10 points if possible)
- itinerary: (optional) Day-by-day breakdown if present. Use **Day 1:**, **Day 2:**, etc. as bold headings. If no clear itinerary, return null.
- menu: (optional) Food menu if mentioned. Use **Menu:** or **Day 1 Menu:**, **Day 2 Menu:** as bold headings for each section. If no menu details, return null.
- age_requirements: (string) Age restrictions. Valid examples: "All ages welcome", "Ages 12+", "Adults only (18+)", "Minimum age 8". NEVER use vague phrases like "Ages 12 and under" - be specific about minimum/maximum. If unclear, return null.
- ideal_for: Who this tour suits

DATA QUALITY RULES - CRITICAL:
[!] If you cannot extract clear, accurate information, return null - do NOT guess or make up data
[!] Duration MUST be a time amount ("2 Hours", "Full Day", "3 Days 2 Nights") - NOT "Evening" or "Sunset"
[!] Age requirements MUST be specific ("Ages 12+", "All ages") - NOT vague like "Ages 12 and under"
[!] Times should be departure/return times ("9am", "5pm") - NOT durations
[!] When in doubt, return null - empty is better than wrong

DESCRIPTION EXAMPLE (what to do):
"Experience the Whitsundays in style aboard Summer Jo, a luxurious mega yacht offering intimate small-group adventures. Perfect for couples, families, and divers seeking connection with nature and fellow travelers.

Cruise through crystal-clear waters, explore hidden coves, and witness stunning sunsets. This 3-day journey combines adventure with comfort, featuring world-class diving opportunities and gourmet meals prepared fresh onboard."

DESCRIPTION ANTI-PATTERNS (what NOT to do):
[X] "Includes: crew, meals, equipment..." (use 'includes' field)
[X] Listing the entire menu (use 'menu' field)
[X] Repeating highlights (use 'highlights' field)
[X] Day-by-day itinerary (use 'itinerary' field)

FORMATTING in separate fields (itinerary, menu):
- Use **bold** for day headings: **Day 1:**, **Day 2:**
- Use **bold** for meal sections: **Breakfast:**, **Dinner:**
- Add blank lines between sections
- Use bullet points for lists

PRESERVE DETAILS - Customers want to know:
- Daily itineraries with bold day headings
- Meal details with bold menu sections
- Exact inclusions with bullet points
- All pricing tiers (handled separately)
- Age requirements
- What makes this tour special

PRICING PARSING EXAMPLES:

Example 1 - Cabin types (GOOD):
SCRAPED: "Private Double Cabin with Ensuite A$1,879.06 | Share Single A$826.26 | Share Double A$1,598"
OUTPUT: "Single Bunk: A$826.26 | Share Double: A$1,598 (for 2 people) | Private Double Cabin: A$1,879.06 (for 2 people)"

Example 2 - Package/Meal options (CRITICAL FOR CRUISE WHITSUNDAYS):
SCRAPED: HTML shows pricing table with rows like "Day cruise with Marina Tavern lunch" = $152, "Day cruise with Popeye's Fish & Chips lunch" = $135
OUTPUT: "Adult - Day cruise with Marina Tavern lunch: A$152 | Adult - Day cruise with Popeye's Fish & Chips lunch: A$135 | Senior - Day cruise with Marina Tavern lunch: A$143 | Senior - Day cruise with Popeye's Fish & Chips lunch: A$130"

Example 3 - Multiple prices for same category (REQUIRES CONTEXT):
SCRAPED: "Adult A$269 Adult A$279 Senior A$239 Senior A$249"
BAD OUTPUT: "Adult: A$269 | Adult: A$279 | Senior: A$239 | Senior: A$249"  [X] TOO VAGUE
GOOD OUTPUT: "Adult (Standard): A$269 | Adult (Premium): A$279 | Senior (Standard): A$239 | Senior (Premium): A$249"
OR if context is clear from text: "Adult (May-Oct): A$269 | Adult (Nov-Apr): A$279"

Example 3 - Simple single-tier pricing (OKAY to be generic):
SCRAPED: "Adult A$149 Child A$79"
OUTPUT: "Adult: A$149 | Child (4-14): A$79"

PRICE INFO (from scraper):
{price_info}

RAW TEXT:
{filtered_text}
"""
        print("\n--- AI PROMPT START ---\n")
        print(prompt)
        print("\n--- AI PROMPT END ---\n")
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,  # Increased from 500 to allow detailed responses
                temperature=0.5   # Lower temperature for more consistent extraction
            )
            import json
            raw_response = response.choices[0].message.content.strip()
            print("\n--- AI RAW RESPONSE START ---\n")
            print(raw_response)
            print("\n--- AI RAW RESPONSE END ---\n")
            # Extract the first {...} JSON block from the response
            json_match = re.search(r'\{[\s\S]*\}', raw_response)
            if json_match:
                json_str = json_match.group(0)
                ai_data = json.loads(json_str)
                # Check if it's a tour (or force include all if flag is set)
                is_tour = str(ai_data.get('is_tour', '')).lower() == 'true'
                if is_tour or FORCE_INCLUDE:
                    if FORCE_INCLUDE and not is_tour:
                        print(f"  [!] Force-including: {tour_name} (AI said is_tour=false)")
                    new_row = row.copy()
                    new_row['name'] = clean_field(ai_data.get('name', tour_name))
                    new_row['description'] = clean_field(ai_data.get('description', ''))
                    new_row['price_adult'] = clean_field(ai_data.get('price_adult', ''))
                    new_row['price_child'] = clean_field(ai_data.get('price_child', ''))
                    new_row['price_tiers'] = clean_field(ai_data.get('price_tiers', ''))
                    new_row['duration'] = clean_field(ai_data.get('duration', ''))
                    new_row['departure_times'] = clean_field(ai_data.get('times', ''))
                    new_row['departure_location'] = clean_field(ai_data.get('departure_location', ''))
                    new_row['includes'] = clean_field(ai_data.get('includes', ''))
                    new_row['highlights'] = clean_field(ai_data.get('highlights', ''))
                    # New detailed fields
                    new_row['itinerary'] = clean_field(ai_data.get('itinerary', ''))
                    new_row['menu'] = clean_field(ai_data.get('menu', ''))
                    new_row['age_requirements'] = clean_field(ai_data.get('age_requirements', ''))
                    new_row['ideal_for'] = clean_field(ai_data.get('ideal_for', ''))
                    new_row['raw_text'] = ''
                    # Normalized derived fields
                    combined_text = " ".join([
                        str(new_row.get('name','')),
                        str(new_row.get('description','')),
                        str(new_row.get('includes','')),
                        str(new_row.get('highlights','')),
                        filtered_text
                    ])
                    dh, dd, dc = parse_duration_normalized(new_row.get('duration',''))
                    new_row['duration_hours'] = dh
                    new_row['duration_days'] = dd
                    new_row['duration_category'] = dc
                    new_row['tour_type'] = extract_tour_type(combined_text)
                    new_row['locations'] = ",".join(extract_locations(combined_text))
                    tags_list = derive_tags(combined_text)
                    new_row['tags'] = ",".join(tags_list)
                    new_row['audience'] = derive_audience(combined_text, new_row.get('price_child',''))
                    new_row['intensity_level'] = derive_intensity(combined_text)
                    print(f"Appending tour: {new_row['name']}")
                    output_rows.append(new_row)
            else:
                print(f"No JSON found in AI response for tour '{tour_name}'")
                continue
        except Exception as e:
            print(f"AI post-processing failed for tour '{tour_name}' in row with URL {row.get('link_booking', '')}: {e}")
            print("Prompt that caused error:\n", prompt)
            # Do not copy the original row if AI fails

# Remove 'raw_html' from fieldnames and each row if you don't want it in the output
if 'raw_html' in fieldnames:
    fieldnames = [f for f in fieldnames if f != 'raw_html']
    for row in output_rows:
        if 'raw_html' in row:
            del row['raw_html']

# Ensure new normalized fields exist in fieldnames
extra_fields = [
    'duration_hours','duration_days','duration_category','tour_type','locations',
    'tags','audience','intensity_level',
    'itinerary','menu','age_requirements','ideal_for'
]
for f in extra_fields:
    if f not in fieldnames:
        fieldnames = list(fieldnames) + [f]

# Write the improved CSV
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)

print(f"AI post-processing complete. Cleaned CSV saved as {OUTPUT_CSV}") 