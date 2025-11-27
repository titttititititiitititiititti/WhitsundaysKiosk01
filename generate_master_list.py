#!/usr/bin/env python3
"""
Generate a master list of all companies and their tours for manual location mapping.
"""

import csv
import glob

def main():
    # Find all CSV files
    csv_files = glob.glob('tours_*_cleaned_with_media.csv')
    csv_files.sort()
    
    output = []
    output.append("="*80)
    output.append("MASTER DEPARTURE LOCATIONS LIST")
    output.append("="*80)
    output.append("")
    output.append("Instructions:")
    output.append("1. Fill in the COMPANY DEFAULT for each company")
    output.append("2. If a specific tour departs from a different location, fill in that tour's location")
    output.append("3. Tours left blank will use the company default")
    output.append("4. Save this file when done")
    output.append("")
    output.append("Available locations we have coordinates for:")
    output.append("  - Port of Airlie")
    output.append("  - Shop 9/33 Port Dr, Port of Airlie")
    output.append("  - Coral Sea Marina Meeting Point C")
    output.append("  - Coral Sea Marina Meeting Point B")
    output.append("  - Coral Sea Marina Meeting Point D")
    output.append("  - Coral Sea Marina")
    output.append("  - Shute Harbor / Shute Harbour")
    output.append("  - Shingley Beach")
    output.append("  - Airlie Beach Dive Centre")
    output.append("")
    output.append("You can add new locations - just write the name!")
    output.append("")
    output.append("="*80)
    output.append("")
    
    total_tours = 0
    
    for csv_file in csv_files:
        # Extract company name
        company_name = csv_file.replace('tours_', '').replace('_cleaned_with_media.csv', '')
        
        # Read tours
        with open(csv_file, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        output.append("")
        output.append("="*80)
        output.append(f"COMPANY: {company_name}")
        output.append(f"Total tours: {len(rows)}")
        output.append("="*80)
        output.append("")
        output.append("COMPANY DEFAULT DEPARTURE LOCATION: _______________________________")
        output.append("")
        output.append("Tours (leave blank to use company default):")
        output.append("-"*80)
        
        for row in rows:
            tour_name = row.get('name', 'Unnamed Tour')
            tour_id = row.get('tour_id', '')
            current_location = row.get('departure_location', '').strip()
            
            if current_location:
                output.append(f"  [{tour_id}] {tour_name}")
                output.append(f"      Current: {current_location}")
                output.append(f"      Override: _______________________________")
            else:
                output.append(f"  [{tour_id}] {tour_name}")
                output.append(f"      Location: _______________________________")
            output.append("")
        
        total_tours += len(rows)
    
    output.append("")
    output.append("="*80)
    output.append(f"TOTAL: {len(csv_files)} companies, {total_tours} tours")
    output.append("="*80)
    
    # Write to file
    with open('MASTER_LOCATIONS_LIST.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print(f"✅ Generated: MASTER_LOCATIONS_LIST.txt")
    print(f"   {len(csv_files)} companies, {total_tours} tours")
    print()
    print("Fill in the blanks and save when ready!")

if __name__ == '__main__':
    main()




