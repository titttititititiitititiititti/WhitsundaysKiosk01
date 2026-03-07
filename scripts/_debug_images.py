"""Debug script to check what sync_tour_images_to_csv would actually produce"""
import csv
import json
import os
import sys

# Check Nathan's hidden images format
settings_file = 'config/defaults/nathan/settings.json'
if not os.path.exists(settings_file):
    settings_file = 'config/accounts/nathan/settings.json'

with open(settings_file, 'r', encoding='utf-8') as f:
    settings = json.load(f)

hidden = settings.get('hidden_images', {})

# Pick the first tour with hidden images to debug
for tour_key, hidden_list in hidden.items():
    company, tid = tour_key.split('__', 1)
    folder = f"static/tour_images/{company}/{tid}"
    
    print(f"\n{'='*80}")
    print(f"Tour: {tour_key}")
    print(f"Folder: {folder}")
    print(f"Hidden images count: {len(hidden_list)}")
    
    # Show first few hidden image paths (to see format)
    print(f"\nFirst 3 hidden image paths:")
    for h in hidden_list[:3]:
        print(f"  '{h}'")
    
    # Scan folder
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.JPG', '.JPEG', '.PNG', '.WEBP', '.GIF']
    all_files = []
    if os.path.isdir(folder):
        for filename in sorted(os.listdir(folder)):
            if any(filename.endswith(ext) for ext in extensions):
                if filename.lower().startswith('thumbnail'):
                    print(f"\n  THUMBNAIL: {filename}")
                    continue
                all_files.append(f"static/tour_images/{company}/{tid}/{filename}")
    
    print(f"\nTotal non-thumbnail images in folder: {len(all_files)}")
    print(f"First 3 folder paths:")
    for p in all_files[:3]:
        print(f"  '{p}'")
    
    # Simulate filtering
    visible = []
    hidden_matched = 0
    for img_path in all_files:
        normalized = img_path.lstrip('/')
        with_slash = '/' + normalized
        if normalized in hidden_list or with_slash in hidden_list:
            hidden_matched += 1
        else:
            visible.append(img_path)
    
    print(f"\nFilter result: {len(visible)} visible, {hidden_matched} matched as hidden")
    print(f"  (Unaccounted: {len(all_files) - len(visible) - hidden_matched})")
    
    if visible:
        print(f"\nVisible images:")
        for v in visible:
            print(f"  {v}")
    else:
        print(f"\n*** NO VISIBLE IMAGES! ***")
    
    # Check CSV current state
    csv_file = f'data/{company}/en/tours_{company}_cleaned_with_media.csv'
    if os.path.exists(csv_file):
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('id') == tid:
                    img_urls = row.get('image_urls', '').strip()
                    img_url = row.get('image_url', '').strip()
                    url_count = len([x for x in img_urls.split(',') if x.strip()]) if img_urls else 0
                    print(f"\nCSV state:")
                    print(f"  image_url (thumb): {img_url[:80] if img_url else '(empty)'}")
                    print(f"  image_urls count: {url_count}")
                    if url_count > 0:
                        first_url = img_urls.split(',')[0].strip()
                        print(f"  First image_url: {first_url}")
                    break
    
    print()

