import csv
import glob
import os
from openai import OpenAI

# Load API key from .env
with open('.env') as f:
    for line in f:
        if line.startswith('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = line.split('=', 1)[1].strip()
            break

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

print("="*80)
print("STEP 1: EXTRACT ACTUAL DEPARTURE LOCATIONS")
print("="*80)

def extract_location_text(tour_name, description, raw_text, company):
    """Extract the EXACT departure location text without forcing matches"""
    
    text = f"Tour: {tour_name}\n\n"
    if description:
        text += f"Description: {description[:2000]}\n\n"
    if raw_text:
        text += f"Additional: {raw_text[:3000]}"
    
    prompt = f"""Extract the EXACT departure location from this tour page.

TOUR TEXT:
{text}

INSTRUCTIONS:
1. Look for phrases like: "departs from", "meet at", "check-in at", "pickup from", "departure point"
2. Extract the EXACT location name as written (e.g., "Port of Airlie", "Coral Sea Marina Meeting Point B")
3. If it mentions a full address, extract just the location name
4. If multiple locations or pickup options, choose the PRIMARY departure point
5. If unclear or not mentioned, return "NOT FOUND"

Return ONLY the location name, nothing else. Be precise."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract departure location exactly as written."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=50,
            timeout=30.0
        )
        
        location = response.choices[0].message.content.strip()
        
        if location.upper() == "NOT FOUND" or not location:
            return None
        
        return location
        
    except Exception as e:
        print(f"    ERROR: {e}")
        return None

# Company-specific rules (known patterns)
COMPANY_RULES = {
    'cruisewhitsundays': 'Port of Airlie',
    # Add more as we discover them
}

csv_files = sorted(glob.glob('*_cleaned_with_media.csv'))
all_locations = {}  # location -> list of tours

print(f"\nProcessing {len(csv_files)} companies...\n")

for csvfile in csv_files:
    company = csvfile.replace('tours_', '').replace('_cleaned_with_media.csv', '')
    print(f"{company}:")
    
    with open(csvfile, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    for idx, row in enumerate(rows, 1):
        tour_name = row.get('name', 'Unknown')
        
        # Check company rule first
        if company in COMPANY_RULES:
            location = COMPANY_RULES[company]
            print(f"  [{idx}/{len(rows)}] {tour_name[:50]} -> {location} (company rule)")
        else:
            # Extract from text
            description = row.get('description', '')
            raw_text = row.get('raw_text', '')
            
            location = extract_location_text(tour_name, description, raw_text, company)
            
            if location:
                print(f"  [{idx}/{len(rows)}] {tour_name[:50]} -> {location}")
            else:
                location = "UNKNOWN"
                print(f"  [{idx}/{len(rows)}] {tour_name[:50]} -> NOT FOUND")
        
        # Store for analysis
        if location not in all_locations:
            all_locations[location] = []
        all_locations[location].append({
            'company': company,
            'tour': tour_name,
            'id': row.get('id', '')
        })
    
    print()

# Show summary
print("\n" + "="*80)
print("STEP 2: ALL UNIQUE LOCATIONS FOUND")
print("="*80)

for location, tours in sorted(all_locations.items(), key=lambda x: -len(x[1])):
    print(f"\n{location} ({len(tours)} tours)")
    if len(tours) <= 5:
        for t in tours:
            print(f"  - {t['tour'][:60]} ({t['company']})")
    else:
        for t in tours[:3]:
            print(f"  - {t['tour'][:60]} ({t['company']})")
        print(f"  ... and {len(tours)-3} more")

print("\n" + "="*80)
print("NEXT STEPS:")
print("="*80)
print("1. Review the locations above")
print("2. Provide coordinates for each location")
print("3. Re-run with the coordinate mapping")
print("="*80)




