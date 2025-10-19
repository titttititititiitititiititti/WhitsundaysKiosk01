"""
Fast CSV postprocessor - copies raw CSV to cleaned CSV with minimal processing.
Use this when you don't need AI enhancements, just want to preserve scraped data.

Usage: python fast_postprocess_csv.py <input_csv>
"""
import csv
import sys
import os

if len(sys.argv) < 2:
    print("Usage: python fast_postprocess_csv.py <input_csv>")
    sys.exit(1)

INPUT_CSV = sys.argv[1]
OUTPUT_CSV = INPUT_CSV.replace('.csv', '_cleaned.csv')

if not os.path.exists(INPUT_CSV):
    print(f"Error: {INPUT_CSV} not found")
    sys.exit(1)

print(f"Fast processing: {INPUT_CSV} -> {OUTPUT_CSV}")

# Read input
with open(INPUT_CSV, 'r', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

# Add normalized fields if missing
extra_fields = ['duration_hours', 'duration_days', 'duration_category', 
                'tour_type', 'locations', 'tags', 'audience', 'intensity_level']
new_fieldnames = list(fieldnames)
for field in extra_fields:
    if field not in new_fieldnames:
        new_fieldnames.append(field)

# Remove raw_html to save space
if 'raw_html' in new_fieldnames:
    new_fieldnames.remove('raw_html')

# Process each row
output_rows = []
for row in rows:
    # Remove raw_html
    if 'raw_html' in row:
        del row['raw_html']
    
    # Set defaults for new fields if they're empty
    for field in extra_fields:
        if not row.get(field):
            row[field] = ''
    
    output_rows.append(row)
    print(f"  Copied: {row.get('name', 'Unknown')}")

# Write output
with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=new_fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)

print(f"\n[OK] Fast processing complete. Saved to {OUTPUT_CSV}")
print(f"     Processed {len(output_rows)} tours")


