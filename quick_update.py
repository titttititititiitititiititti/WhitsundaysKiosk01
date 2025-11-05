import csv

# Update airliebeachdiving
print("Updating airliebeachdiving...")
with open('tours_airliebeachdiving_cleaned_with_media.csv', 'r', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = reader.fieldnames

for row in rows:
    row['departure_location'] = 'Shop 11 293 Shute Harbour Road, Airlie Beach QLD 4802'

with open('tours_airliebeachdiving_cleaned_with_media.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f"Done! Updated {len(rows)} tours")

# Update crocodilesafari
print("\nUpdating crocodilesafari...")
with open('tours_crocodilesafari_cleaned_with_media.csv', 'r', encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    fieldnames = reader.fieldnames

for row in rows:
    row['departure_location'] = 'Courtesy Bus Pickup'

with open('tours_crocodilesafari_cleaned_with_media.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
print(f"Done! Updated {len(rows)} tours")

print("\n✅ Complete!")




