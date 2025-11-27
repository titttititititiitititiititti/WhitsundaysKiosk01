#!/usr/bin/env python3
"""
Automatically categorize the 20 tours with 'unknown' duration
"""

import csv
import glob
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def categorize_duration(tour_name, duration_text, description):
    """Use AI to determine if a tour is half_day, full_day, or multi_day"""
    
    prompt = f"""You are categorizing a tour by duration. Based on the information below, determine if this is:
- "half_day" (less than 5 hours, sunset cruises, short experiences)
- "full_day" (5-12 hours, single full day experience)
- "multi_day" (overnight, 2+ days, multi-night)

Tour: {tour_name}
Duration: {duration_text}
Description: {description[:500]}

Return ONLY one word: half_day, full_day, or multi_day"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at categorizing tour durations. Return only: half_day, full_day, or multi_day"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10,
            timeout=15.0
        )
        
        category = response.choices[0].message.content.strip().lower()
        
        # Validate
        if category in ['half_day', 'full_day', 'multi_day']:
            return category
        else:
            return None
            
    except Exception as e:
        print(f"    ⚠️  AI error: {e}")
        return None


def main():
    print("="*80)
    print("FIXING UNKNOWN DURATION CATEGORIES")
    print("="*80)
    
    total_fixed = 0
    
    for csv_file in glob.glob('tours_*_cleaned_with_media.csv'):
        company = csv_file.replace('tours_', '').replace('_cleaned_with_media.csv', '')
        
        # Read CSV
        with open(csv_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames
        
        unknown_count = sum(1 for r in rows if r.get('duration_category', '').lower() == 'unknown')
        
        if unknown_count == 0:
            continue
        
        print(f"\n{company}: {unknown_count} unknown duration(s)")
        
        updated = 0
        for row in rows:
            if row.get('duration_category', '').lower() == 'unknown':
                tour_name = row.get('name', '')
                duration = row.get('duration', '')
                description = row.get('description', '')
                
                print(f"  [{tour_name[:50]}]...", end=' ')
                
                category = categorize_duration(tour_name, duration, description)
                
                if category:
                    row['duration_category'] = category
                    print(f"→ {category} ✓")
                    updated += 1
                else:
                    print(f"→ Failed, keeping 'unknown'")
        
        # Write back
        if updated > 0:
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"  ✓ Updated {updated} tours")
            total_fixed += updated
    
    print("\n" + "="*80)
    print(f"✅ Fixed {total_fixed}/20 unknown durations")
    print("="*80)
    print("\nRefresh your browser to see all tours in filters!")


if __name__ == '__main__':
    main()



