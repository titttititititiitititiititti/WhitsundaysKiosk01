#!/usr/bin/env python3
"""
Extract precise departure locations from tour descriptions.
Looks for keywords like "meet at", "departs from", etc.
"""

import csv
import glob
import os
import re
from collections import defaultdict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Company-specific overrides (confirmed by user)
COMPANY_RULES = {
    'cruisewhitsundays': 'Port of Airlie',
    # Add more as we discover them
}

# Tour-specific overrides (for tours with known exact addresses)
TOUR_OVERRIDES = {
    'waltzing matilda sunset cruise': 'Shop 9/33 Port Dr, Port of Airlie',
    'waltzing matilda: 2 day 1 night whitsundays cruise': 'Shop 9/33 Port Dr, Port of Airlie',
}

def extract_location_with_ai(tour_name, description, raw_text):
    """Use AI to find the specific departure location mentioned in the text."""
    
    # Combine all available text
    full_text = f"{tour_name}\n\n{description}\n\n{raw_text}"
    
    # Truncate if too long (keep first part which usually has logistics)
    if len(full_text) > 12000:
        full_text = full_text[:12000]
    
    prompt = f"""Extract the EXACT departure location/meeting point from this tour description.

Look for phrases like:
- "meet at [LOCATION]"
- "departs from [LOCATION]"  
- "check-in at [LOCATION]"
- "meeting point: [LOCATION]"
- "pick up from [LOCATION]"
- "starting point: [LOCATION]"
- "departure location: [LOCATION]"
- "leaves from [LOCATION]"
- "located at [LOCATION]"

Extract the COMPLETE location name or address. Include:
- Shop numbers (e.g., "Shop 9/33 Port Dr")
- Specific meeting points (e.g., "Meeting Point C")
- Business names (e.g., "Coral Sea Marina")
- Street addresses if provided

IMPORTANT:
- Return ONLY the location name/address, nothing else
- If multiple locations mentioned, return the PRIMARY departure point
- If no clear location is found, return "NOT FOUND"
- Do NOT make assumptions or return generic locations

TOUR TEXT:
{full_text}

LOCATION:"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at extracting specific location information from text. Return only the exact location mentioned, or 'NOT FOUND'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=100,
            timeout=30.0
        )
        
        location = response.choices[0].message.content.strip()
        
        # Clean up the response
        location = location.replace('"', '').replace("'", '').strip()
        
        # Check if it's a non-answer
        if any(phrase in location.lower() for phrase in ['not found', 'no location', 'not specified', 'not mentioned', 'unclear']):
            return None
            
        # If it's too long, it's probably not a location
        if len(location) > 150:
            return None
            
        return location if location else None
        
    except Exception as e:
        print(f"    ⚠️  AI error: {e}")
        return None


def process_company(company_name, csv_file):
    """Process all tours for a company and extract locations."""
    
    tours_data = []
    
    with open(csv_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"\n{company_name}:")
    print(f"  Processing {len(rows)} tours...")
    
    for idx, row in enumerate(rows, 1):
        tour_name = row.get('name', 'Unnamed Tour')
        tour_id = row.get('tour_id', '')
        description = row.get('description', '')
        raw_text = row.get('raw_text', '')
        
        # Check for tour-specific override first (highest priority)
        tour_name_lower = tour_name.lower()
        if tour_name_lower in TOUR_OVERRIDES:
            location = TOUR_OVERRIDES[tour_name_lower]
            print(f"  [{idx}/{len(rows)}] {tour_name[:50]} -> {location} (tour override)")
            tours_data.append({
                'tour_name': tour_name,
                'tour_id': tour_id,
                'location': location,
                'method': 'tour_override'
            })
            continue
        
        # Check for company-specific rule
        if company_name in COMPANY_RULES:
            location = COMPANY_RULES[company_name]
            print(f"  [{idx}/{len(rows)}] {tour_name[:50]} -> {location} (company rule)")
            tours_data.append({
                'tour_name': tour_name,
                'tour_id': tour_id,
                'location': location,
                'method': 'company_rule'
            })
            continue
        
        # Try AI extraction
        print(f"  [{idx}/{len(rows)}] {tour_name[:50]}...", end=' ')
        location = extract_location_with_ai(tour_name, description, raw_text)
        
        if location:
            print(f"-> {location}")
            tours_data.append({
                'tour_name': tour_name,
                'tour_id': tour_id,
                'location': location,
                'method': 'extracted'
            })
        else:
            print(f"-> NOT FOUND")
            tours_data.append({
                'tour_name': tour_name,
                'tour_id': tour_id,
                'location': None,
                'method': 'not_found'
            })
    
    return tours_data


def apply_company_fallbacks(all_company_data):
    """For each company, use the most common location as fallback for tours without locations."""
    
    print("\n" + "="*80)
    print("APPLYING COMPANY-LEVEL FALLBACKS")
    print("="*80)
    
    for company_name, tours in all_company_data.items():
        # Count locations for this company
        location_counts = defaultdict(int)
        for tour in tours:
            if tour['location'] and tour['method'] in ['extracted', 'company_rule', 'tour_override']:
                location_counts[tour['location']] += 1
        
        if not location_counts:
            continue
        
        # Find most common location
        most_common = max(location_counts.items(), key=lambda x: x[1])
        fallback_location = most_common[0]
        fallback_count = most_common[1]
        
        # Only apply fallback if it's used by at least 30% of tours or at least 2 tours
        total_tours = len(tours)
        if fallback_count >= 2 or (fallback_count / total_tours) >= 0.3:
            print(f"\n{company_name}:")
            print(f"  Most common location: {fallback_location} ({fallback_count}/{total_tours} tours)")
            
            # Apply to tours without locations
            applied = 0
            for tour in tours:
                if not tour['location']:
                    tour['location'] = fallback_location
                    tour['method'] = 'company_fallback'
                    applied += 1
            
            if applied > 0:
                print(f"  ✓ Applied to {applied} tour(s) without locations")


def main():
    print("="*80)
    print("EXTRACTING PRECISE DEPARTURE LOCATIONS")
    print("="*80)
    
    # Find all CSV files
    csv_files = glob.glob('tours_*_cleaned_with_media.csv')
    csv_files.sort()
    
    if not csv_files:
        print("❌ No CSV files found!")
        return
    
    print(f"\nFound {len(csv_files)} companies")
    
    # Process each company
    all_company_data = {}
    
    for csv_file in csv_files:
        # Extract company name
        company_name = csv_file.replace('tours_', '').replace('_cleaned_with_media.csv', '')
        
        tours_data = process_company(company_name, csv_file)
        all_company_data[company_name] = tours_data
    
    # Apply company-level fallbacks
    apply_company_fallbacks(all_company_data)
    
    # Generate summary report
    print("\n" + "="*80)
    print("SUMMARY: ALL UNIQUE LOCATIONS")
    print("="*80)
    
    # Group all tours by location
    locations_map = defaultdict(list)
    
    for company_name, tours in all_company_data.items():
        for tour in tours:
            location = tour['location'] if tour['location'] else "UNKNOWN"
            locations_map[location].append({
                'name': tour['tour_name'],
                'company': company_name,
                'method': tour['method']
            })
    
    # Sort by number of tours (most common first)
    sorted_locations = sorted(locations_map.items(), key=lambda x: len(x[1]), reverse=True)
    
    print("\n")
    for location, tours in sorted_locations:
        count = len(tours)
        print(f"{location} ({count} tours)")
        
        # Show first 3 examples
        for tour in tours[:3]:
            method_emoji = {
                'tour_override': '⭐',
                'company_rule': '📌',
                'extracted': '🔍',
                'company_fallback': '🔄',
                'not_found': '❓'
            }.get(tour['method'], '·')
            print(f"  {method_emoji} {tour['name']} ({tour['company']})")
        
        if count > 3:
            print(f"  ... and {count - 3} more")
        print()
    
    # Save detailed report
    with open('locations_detailed_report.txt', 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("DETAILED DEPARTURE LOCATIONS REPORT\n")
        f.write("="*80 + "\n\n")
        
        for location, tours in sorted_locations:
            f.write(f"\n{location} ({len(tours)} tours)\n")
            f.write("-" * 80 + "\n")
            for tour in tours:
                f.write(f"  [{tour['method']}] {tour['name']} ({tour['company']})\n")
    
    print("\n✅ Detailed report saved to: locations_detailed_report.txt")
    
    # Now update the CSVs
    print("\n" + "="*80)
    print("UPDATING CSV FILES")
    print("="*80)
    
    for company_name, tours in all_company_data.items():
        csv_file = f'tours_{company_name}_cleaned_with_media.csv'
        
        # Read the CSV
        with open(csv_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames
        
        # Update departure_location field
        updated = 0
        for row in rows:
            tour_id = row.get('tour_id', '')
            
            # Find matching tour data
            for tour in tours:
                if tour['tour_id'] == tour_id:
                    if tour['location']:
                        row['departure_location'] = tour['location']
                        updated += 1
                    break
        
        # Write back
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"  ✓ {company_name}: Updated {updated}/{len(rows)} tours")
    
    print("\n" + "="*80)
    print("✅ COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("1. Review 'locations_detailed_report.txt'")
    print("2. Provide coordinates for each unique location")
    print("3. I'll map them to the tours!")


if __name__ == '__main__':
    main()

