"""
Add enhanced booking details to Explore Whitsundays tours only
This will add: important_information, what_to_bring, whats_extra, cancellation_policy
"""
import pandas as pd
import csv
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Step 1: Add new columns to the CSV
print("=" * 80)
print("ENHANCING EXPLORE WHITSUNDAYS TOURS")
print("=" * 80)

csv_file = 'tours_explorewhitsundays_cleaned_with_media.csv'
new_columns = ['important_information', 'what_to_bring', 'whats_extra', 'cancellation_policy']

print(f"\n[1/3] Adding new columns to {csv_file}...")
df = pd.read_csv(csv_file)

# Add columns if they don't exist
for col in new_columns:
    if col not in df.columns:
        df[col] = ''
        print(f"  ✓ Added column: {col}")
    else:
        print(f"  - Column already exists: {col}")

# Save with new columns
df.to_csv(csv_file, index=False)
print(f"  ✓ Saved {csv_file}")

# Step 2: Use AI to extract the new fields from raw_text
print(f"\n[2/3] Processing tours with AI to extract booking details...")

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Read the CSV
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# Process each tour
for idx, row in enumerate(rows, 1):
    tour_name = row.get('name', 'Unknown')
    raw_text = row.get('raw_text', '')
    
    if not raw_text or len(raw_text) < 100:
        print(f"  [{idx}/9] {tour_name}: Skipping (no raw_text)")
        continue
    
    print(f"  [{idx}/9] {tour_name}: Processing...")
    
    # Create the AI prompt
    prompt = f"""Extract booking-critical information from this tour page text.

TOUR TEXT:
{raw_text[:8000]}

Extract these fields ONLY if they exist on the page. If not found, return null:

- important_information: Requirements, restrictions, fitness levels, swimming ability, guest restrictions, supervision needs. Return as bullet points if found, otherwise null.
- what_to_bring: Complete packing list (clothing, toiletries, sun protection, etc.). Return as bullet points if found, otherwise null.
- whats_extra: Additional costs or optional extras not included (BYO alcohol, luggage storage, transfers, etc.). Return as bullet points if found, otherwise null.
- cancellation_policy: Cancellation terms, refund policy, booking conditions. Keep EXACT wording if found, otherwise null.

Return as JSON with these exact keys. Use null for missing fields (not empty string).
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract structured information from tour website text. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1500
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        data = json.loads(result_text)
        
        # Update the row with extracted data
        for field in new_columns:
            value = data.get(field)
            if value and value != 'null' and str(value).strip():
                row[field] = str(value).strip()
                print(f"      ✓ {field}")
            else:
                row[field] = ''
                
    except Exception as e:
        print(f"      ✗ Error: {e}")

# Step 3: Save the enhanced data back to CSV
print(f"\n[3/3] Saving enhanced data...")
with open(csv_file, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=df.columns)
    writer.writeheader()
    writer.writerows(rows)
print(f"  ✓ Saved to {csv_file}")

# Show summary
print("\n" + "=" * 80)
print("✅ ENHANCEMENT COMPLETE!")
print("=" * 80)
print("\nNew fields added:")
for col in new_columns:
    count = sum(1 for row in rows if row.get(col, '').strip())
    print(f"  - {col}: {count}/{len(rows)} tours have this data")

print("\n💡 Next: Update app.py and templates/index.html to display these fields")





