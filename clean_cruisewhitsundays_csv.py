import csv
import os
import shutil

# List of valid tour links (provided by user)
VALID_LINKS = [
    'https://www.cruisewhitsundays.com/experiences/crusing-nomads/',
    'https://www.cruisewhitsundays.com/experiences/great-barrier-reef-full-day-adventure/',
    'https://www.cruisewhitsundays.com/experiences/reefsuites/',
    'https://www.cruisewhitsundays.com/experiences/reefsleep/',
    'https://www.cruisewhitsundays.com/experiences/camira-sailing-adventure/',
    'https://www.cruisewhitsundays.com/experiences/camira-sunset-sail/',
    'https://www.cruisewhitsundays.com/experiences/ultimate-whitsundays-combo/',
    'https://www.cruisewhitsundays.com/experiences/whitehaven-beach-chill-grill/',
    'https://www.cruisewhitsundays.com/experiences/whitsunday-islands-whitehaven-beach-half-day-cruise/',
    'https://www.cruisewhitsundays.com/experiences/whitehaven-beach-hamilton-island-tour/',
    'https://www.cruisewhitsundays.com/experiences/whitsunday-crocodile-safari/',
    'https://www.cruisewhitsundays.com/experiences/hamilton-island-golf/',
    'https://www.cruisewhitsundays.com/experiences/hamilton-island-freestyle/',
    'https://www.cruisewhitsundays.com/experiences/daydream-island-escape/',
]

CSV_FILE = 'tours_cruisewhitsundays.csv'
CLEANED_CSV_FILE = 'tours_cruisewhitsundays_cleaned_2.csv'

# Backup original
backup_file = CSV_FILE + '.bak'
shutil.copy(CSV_FILE, backup_file)
print(f'Backup saved as {backup_file}')

# Load CSV
with open(CSV_FILE, newline='', encoding='utf-8') as f:
    reader = list(csv.DictReader(f))
    fieldnames = reader[0].keys() if reader else []

# Filter rows
cleaned_rows = [row for row in reader if row.get('link_booking', '').strip() in VALID_LINKS]
print(f'Kept {len(cleaned_rows)} out of {len(reader)} tours after link filtering.')

def row_score(row):
    # Score: count of non-empty fields, with extra weight for description/price
    score = sum(1 for v in row.values() if v.strip())
    if row.get('description', '').strip():
        score += 5
    if row.get('price_adult', '').strip():
        score += 2
    return score

unique = {}
for link in VALID_LINKS:
    candidates = [row for row in cleaned_rows if row.get('link_booking', '').strip() == link]
    if candidates:
        best_row = max(candidates, key=row_score)
        unique[link] = best_row

deduped_rows = list(unique.values())
print(f'After deduplication: {len(deduped_rows)} unique, best-info tours.')

# Save cleaned CSV
with open(CLEANED_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(deduped_rows)
print(f'Cleaned CSV saved as {CLEANED_CSV_FILE}') 