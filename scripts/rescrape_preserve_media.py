"""
Re-scrape tours while preserving images and reviews.

This script will:
1. Backup existing media columns (image_url, image_urls, video_urls)
2. Backup review columns (review_rating, review_count, reviews_summary)
3. Re-scrape the tour pages with Selenium
4. Run AI post-processing for better content
5. Restore the media and review columns from backup

Usage:
    python scripts/rescrape_preserve_media.py jetskitour
"""

import sys
import os
import csv
import glob
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Columns to preserve (don't overwrite with new scrape)
PRESERVE_COLUMNS = [
    'image_url', 'image_urls', 'video_urls',
    'review_rating', 'review_count', 'reviews_summary', 'reviews_json',
    'commission_rate', 'active'
]

def backup_preserved_data(csv_file):
    """Extract data we want to preserve from existing CSV"""
    preserved = {}
    
    if not os.path.exists(csv_file):
        print(f"  No existing file to backup: {csv_file}")
        return preserved
    
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tour_id = row.get('id')
            if tour_id:
                preserved[tour_id] = {}
                for col in PRESERVE_COLUMNS:
                    if col in row and row[col]:
                        preserved[tour_id][col] = row[col]
                # Also preserve the booking/info links in case scraper generates new IDs
                preserved[tour_id]['_link'] = row.get('link_booking') or row.get('link_more_info')
    
    print(f"  Backed up {len(preserved)} tours with preserved data")
    return preserved

def get_tour_links(csv_file):
    """Extract tour URLs from existing CSV"""
    links = []
    if os.path.exists(csv_file):
        with open(csv_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('link_booking') or row.get('link_more_info') or row.get('price_source_url')
                if url:
                    links.append(url)
    return list(set(links))

def restore_preserved_data(csv_file, preserved_data):
    """Merge preserved data back into the new CSV"""
    if not os.path.exists(csv_file):
        print(f"  No file to restore to: {csv_file}")
        return
    
    rows = []
    fieldnames = None
    
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    
    # Add any missing preserve columns
    for col in PRESERVE_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)
    
    # Restore preserved data
    restored_count = 0
    for row in rows:
        tour_id = row.get('id')
        link = row.get('link_booking') or row.get('link_more_info')
        
        # Try to match by ID first, then by link
        backup = preserved_data.get(tour_id)
        if not backup:
            # Try to find by matching link
            for pid, pdata in preserved_data.items():
                if pdata.get('_link') == link:
                    backup = pdata
                    break
        
        if backup:
            for col in PRESERVE_COLUMNS:
                if col in backup and backup[col]:
                    row[col] = backup[col]
            restored_count += 1
    
    # Write back
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  Restored preserved data for {restored_count} tours")

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/rescrape_preserve_media.py <company_name>")
        print("Example: python scripts/rescrape_preserve_media.py jetskitour")
        sys.exit(1)
    
    company = sys.argv[1].lower()
    
    # Find the CSV files
    csv_patterns = [
        f"tours_{company}_cleaned_with_media.csv",
        f"tours_{company}_cleaned.csv",
        f"tours_{company}.csv",
        f"data/{company}/en/tours_{company}_cleaned_with_media.csv"
    ]
    
    media_csv = None
    for pattern in csv_patterns:
        if os.path.exists(pattern):
            media_csv = pattern
            break
    
    if not media_csv:
        print(f"ERROR: Could not find CSV for company '{company}'")
        sys.exit(1)
    
    print(f"=" * 70)
    print(f"RE-SCRAPING {company.upper()} TOURS (preserving media & reviews)")
    print(f"=" * 70)
    print()
    
    # Step 1: Backup preserved data
    print("[1/5] Backing up images and reviews...")
    preserved = backup_preserved_data(media_csv)
    
    # Step 2: Get tour links
    print("\n[2/5] Extracting tour URLs...")
    links = get_tour_links(media_csv)
    
    if not links:
        print("  ERROR: No tour links found!")
        sys.exit(1)
    
    print(f"  Found {len(links)} tour URLs:")
    for link in links:
        print(f"    - {link}")
    
    # Step 3: Write links to scraper config and run scraper
    print("\n[3/5] Running scraper with Selenium...")
    
    # Import scraper functions
    from scrape_tours import fetch_html_selenium, extract_tour_info, append_to_csv
    
    raw_csv = f"tours_{company}.csv"
    
    # Clear existing raw CSV to avoid duplicates
    if os.path.exists(raw_csv):
        os.rename(raw_csv, raw_csv + '.bak')
        print(f"  Backed up existing {raw_csv}")
    
    for url in links:
        print(f"\n  Scraping: {url}")
        try:
            html = fetch_html_selenium(url, wait_time=12, expand_accordions=True)
            if html:
                tour_data = extract_tour_info(html, url)
                if tour_data:
                    append_to_csv(tour_data, raw_csv)
                    print(f"    SUCCESS: {tour_data.get('name', 'Unknown')}")
                else:
                    print(f"    WARNING: Could not extract tour data")
            else:
                print(f"    WARNING: Could not fetch HTML")
        except Exception as e:
            print(f"    ERROR: {e}")
    
    # Step 4: Run AI post-processing
    print("\n[4/5] Running AI post-processing...")
    try:
        # Run the AI post-processor as a subprocess to avoid import issues
        import subprocess
        result = subprocess.run(
            ['python', 'ai_postprocess_csv.py', raw_csv],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"  WARNING: AI processing had issues: {result.stderr}")
    except Exception as e:
        print(f"  ERROR in AI processing: {e}")
    
    # Step 5: Restore preserved data
    print("\n[5/5] Restoring images and reviews...")
    cleaned_csv = f"tours_{company}_cleaned.csv"
    if os.path.exists(cleaned_csv):
        restore_preserved_data(cleaned_csv, preserved)
    
    # Also update the _with_media version
    if os.path.exists(media_csv) and media_csv != cleaned_csv:
        restore_preserved_data(media_csv, preserved)
    
    # Create/update _with_media if needed
    cleaned_with_media = f"tours_{company}_cleaned_with_media.csv"
    if os.path.exists(cleaned_csv) and not os.path.exists(cleaned_with_media):
        import shutil
        shutil.copy(cleaned_csv, cleaned_with_media)
        restore_preserved_data(cleaned_with_media, preserved)
    elif os.path.exists(cleaned_csv):
        # Merge cleaned data into with_media
        restore_preserved_data(cleaned_with_media, preserved)
    
    print()
    print("=" * 70)
    print("DONE! Tours re-scraped with preserved images and reviews.")
    print("=" * 70)

if __name__ == '__main__':
    main()

