import csv

# List of valid tour URLs
VALID_URLS = [
    "https://www.cruisewhitsundays.com/experiences/crusing-nomads/",
    "https://www.cruisewhitsundays.com/experiences/great-barrier-reef-full-day-adventure/",
    "https://www.cruisewhitsundays.com/experiences/reefsuites/",
    "https://www.cruisewhitsundays.com/experiences/reefsleep/",
    "https://www.cruisewhitsundays.com/experiences/camira-sailing-adventure/",
    "https://www.cruisewhitsundays.com/experiences/camira-sunset-sail/",
    "https://www.cruisewhitsundays.com/experiences/ultimate-whitsundays-combo/",
    "https://www.cruisewhitsundays.com/experiences/whitehaven-beach-chill-grill/",
    "https://www.cruisewhitsundays.com/experiences/whitsunday-islands-whitehaven-beach-half-day-cruise/",
    "https://www.cruisewhitsundays.com/experiences/whitehaven-beach-hamilton-island-tour/",
    "https://www.cruisewhitsundays.com/experiences/whitsunday-crocodile-safari/",
    "https://www.cruisewhitsundays.com/experiences/hamilton-island-golf/",
    "https://www.cruisewhitsundays.com/experiences/hamilton-island-freestyle/",
    "https://www.cruisewhitsundays.com/experiences/daydream-island-escape/",
]

input_file = "tours_cruisewhitsundays_cleaned.csv"
output_file = "tours_cruisewhitsundays_filtered.csv"

with open(input_file, newline='', encoding='utf-8') as infile, open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    reader = csv.DictReader(infile)
    writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
    writer.writeheader()
    for row in reader:
        if row['link_more_info'] in VALID_URLS:
            writer.writerow(row) 