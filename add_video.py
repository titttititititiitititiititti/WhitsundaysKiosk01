import csv

csv_file = 'data/oceanrafting/en/tours_oceanrafting_cleaned_with_media.csv'

# Read all rows
rows = []
fieldnames = None
with open(csv_file, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        if row.get('id') == '7e123dff452a3bef':  # Northern Exposure
            # Add the YouTube video URL
            row['video_urls'] = 'https://www.youtube.com/watch?v=T5RLsh5DT7A'
            print(f"Updated video_urls for: {row.get('name')}")
        rows.append(row)

# Write back
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print('Done! Video URL saved.')

