import csv

with open('tours_explorewhitsundays_cleaned_with_media.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    
print(f'Explore Whitsundays: {len(rows)} tours\n')

for i, r in enumerate(rows, 1):
    print(f'{i}. {r.get("name", "N/A")}')
    url = r.get('link_more_info', '')
    if url:
        print(f'   {url}')
    print()





