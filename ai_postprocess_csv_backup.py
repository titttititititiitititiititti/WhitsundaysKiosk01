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

# Allow CLI args: python ai_postprocess_csv.py <input_csv> [output_csv]
DEFAULT_INPUT = 'tours_zigzagwhitsundays.csv'
DEFAULT_OUTPUT = 'tours_zigzagwhitsundays_cleaned.csv'

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
TOUR_START_RE = re.compile(r'^=== TOUR START: (.+?) ===$', re.MULTILINE)
TOUR_END_RE = re.compile(r'^=== TOUR END: (.+?) ===$', re.MULTILINE)

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
        filtered_text = filtered_text[:2000]  # Truncate to 2000 chars for testing
        # Add price info to the prompt so the AI can see it
        price_info = ""
        if row.get('price_adult'):
            price_info += f"Adult Price: {row['price_adult']}\n"
        if row.get('price_child'):
            price_info += f"Child Price: {row['price_child']}\n"
        if row.get('price_tiers'):
            price_info += f"Price Tiers: {row['price_tiers']}\n"
        prompt = f"""
You are extracting tour information from a webpage. Return a JSON object with these fields:

REQUIRED FIELDS:
- is_tour: true/false (Is this a real tour offering?)
- name: Tour name
- description: 2-3 sentence engaging description for customers
- price_adult: Adult price (format: "A$XXX" or "FROM A$XXX"). ALWAYS include if mentioned in PRICE INFO or text.
- price_child: Child price (format: "A$XXX"). Include if mentioned.
- duration: How long the tour lasts (e.g., "Full day", "5 hours", "2 days"). Extract from text even if vague.
- times: Departure/return times if mentioned
- includes: What's included (as comma-separated string or short list)
- highlights: Key attractions/activities (as array or comma-separated string)

IMPORTANT RULES:
1. If PRICE INFO section has prices, YOU MUST include them in your response
2. For duration: Look for hours, days, "full day", "half day", "morning", etc. NEVER leave as "N/A" if any time info exists
3. For times: Include departure times, return times, or duration spans (e.g., "10:30am - 3:30pm")
4. Fill ALL fields you can from the text - incomplete data is better than missing data

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
                max_tokens=500,
                temperature=0.7
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
                if str(ai_data.get('is_tour', '')).lower() == 'true':
                    new_row = row.copy()
                    new_row['name'] = clean_field(ai_data.get('name', tour_name))
                    new_row['description'] = clean_field(ai_data.get('description', ''))
                    new_row['price_adult'] = clean_field(ai_data.get('price_adult', ''))
                    new_row['price_child'] = clean_field(ai_data.get('price_child', ''))
                    new_row['duration'] = clean_field(ai_data.get('duration', ''))
                    new_row['departure_times'] = clean_field(ai_data.get('times', ''))
                    new_row['includes'] = clean_field(ai_data.get('includes', ''))
                    new_row['highlights'] = clean_field(ai_data.get('highlights', ''))
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
    'tags','audience','intensity_level'
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