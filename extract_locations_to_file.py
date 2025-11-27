import csv
import glob
import os
from openai import OpenAI

# Load API key
with open('.env') as f:
    for line in f:
        if line.startswith('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = line.split('=', 1)[1].strip()
            break

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

# Open output file
output = open('location_analysis.txt', 'w', encoding='utf-8')

def log(msg):
    output.write(msg + '\n')
    output.flush()

log("="*80)
log("EXTRACTING ACTUAL DEPARTURE LOCATIONS")
log("="*80)

def extract_location_text(tour_name, description, raw_text):
    text = f"Tour: {tour_name}\n\n"
    if description:
        text += f"Description: {description[:2000]}\n\n"
    if raw_text:
        text += f"Additional: {raw_text[:3000]}"
    
    prompt = f"""Extract the EXACT departure location from this tour.

{text}

Look for: "departs from", "meet at", "check-in at", "departure point"
Return ONLY the location name. If not found, return "NOT FOUND"."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract exact departure location."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=50,
            timeout=30.0
        )
        
        location = response.choices[0].message.content.strip()
        return None if location.upper() == "NOT FOUND" else location
    except:
        return None

# Company rules
COMPANY_RULES = {
    'cruisewhitsundays': 'Port of Airlie',
}

csv_files = sorted(glob.glob('*_cleaned_with_media.csv'))
all_locations = {}

log(f"\nProcessing {len(csv_files)} companies...\n")

for csvfile in csv_files:
    company = csvfile.replace('tours_', '').replace('_cleaned_with_media.csv', '')
    log(f"\n{company}:")
    
    with open(csvfile, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    for idx, row in enumerate(rows, 1):
        tour_name = row.get('name', 'Unknown')
        
        if company in COMPANY_RULES:
            location = COMPANY_RULES[company]
            log(f"  [{idx}/{len(rows)}] {tour_name[:45]}... -> {location} (rule)")
        else:
            location = extract_location_text(
                tour_name,
                row.get('description', ''),
                row.get('raw_text', '')
            )
            
            if location:
                log(f"  [{idx}/{len(rows)}] {tour_name[:45]}... -> {location}")
            else:
                location = "UNKNOWN"
                log(f"  [{idx}/{len(rows)}] {tour_name[:45]}... -> NOT FOUND")
        
        if location not in all_locations:
            all_locations[location] = []
        all_locations[location].append({
            'company': company,
            'tour': tour_name
        })

log("\n" + "="*80)
log("ALL UNIQUE LOCATIONS FOUND")
log("="*80)

for location, tours in sorted(all_locations.items(), key=lambda x: -len(x[1])):
    log(f"\n{location} ({len(tours)} tours)")
    for t in tours[:5]:
        log(f"  - {t['tour'][:55]} ({t['company']})")
    if len(tours) > 5:
        log(f"  ... and {len(tours)-5} more")

log("\n" + "="*80)
log("DONE! Check this file for results.")
log("="*80)

output.close()
print("Results saved to: location_analysis.txt")




