#!/usr/bin/env python3
"""
Generate an editable text file for manual duration category editing
"""

import csv
import glob

output = []
output.append("="*80)
output.append("MANUAL DURATION CATEGORY EDITOR")
output.append("="*80)
output.append("")
output.append("Instructions:")
output.append("1. Change the category for any tour (half_day, full_day, or multi_day)")
output.append("2. Save this file")
output.append("3. Run: python apply_duration_edits.py")
output.append("")
output.append("="*80)
output.append("")

all_tours = []

for csv_file in sorted(glob.glob('tours_*_cleaned_with_media.csv')):
    company = csv_file.replace('tours_', '').replace('_cleaned_with_media.csv', '')
    
    with open(csv_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            all_tours.append({
                'company': company,
                'id': row.get('id', ''),
                'name': row.get('name', ''),
                'duration': row.get('duration', ''),
                'duration_category': row.get('duration_category', 'unknown')
            })

# Group by current category
by_category = {}
for tour in all_tours:
    cat = tour['duration_category']
    if cat not in by_category:
        by_category[cat] = []
    by_category[cat].append(tour)

for category in ['unknown', 'half_day', 'full_day', 'multi_day']:
    if category not in by_category:
        continue
    
    tours = by_category[category]
    output.append(f"\n{'='*80}")
    output.append(f"CATEGORY: {category.upper()} ({len(tours)} tours)")
    output.append(f"{'='*80}\n")
    
    for tour in tours:
        output.append(f"[{tour['id']}] {tour['name']} ({tour['company']})")
        output.append(f"  Duration: {tour['duration']}")
        output.append(f"  Category: {category}")
        output.append("")

output.append("\n" + "="*80)
output.append(f"TOTAL: {len(all_tours)} tours")
output.append("="*80)

with open('DURATION_CATEGORIES_EDIT.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print("✅ Generated: DURATION_CATEGORIES_EDIT.txt")
print("   Edit the categories and run: python apply_duration_edits.py")















