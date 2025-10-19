"""
Direct Google Maps Review Scraper

Goes directly to Google Maps URLs (bypassing search) to avoid CAPTCHAs.
Google Maps has less aggressive bot detection than Google Search.

Usage:
    1. Find the tour/company on Google Maps manually
    2. Copy the Google Maps URL
    3. Add it to GOOGLE_MAPS_URLS below
    4. Run: python scrape_google_maps_direct.py
"""

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import random
import json
import os
import re

# ==========================================
# "https://www.google.com/maps/place/True+Blue+Sailing+(official+site)/@-20.2666101,148.7092224,17z/data=!3m1!4b1!4m6!3m5!1s0x6bd83547cf56aaab:0x523e9b367be989af!8m2!3d-20.2666101!4d148.7117973!16s%2Fg%2F11pz0kx_nc?entry=ttu&g_ep=EgoyMDI1MTAwOC4wIKXMDSoASAFQAw%3D%3DADD GOOGLE MAPS URLS HERE
# ==========================================

GOOGLE_MAPS_URLS = {
    # Format: 'company_name': {'url': 'google_maps_url', 'tour_ids': [list of tour ids]}
    
    'cruisewhitsundays': {
        'url': 'https://www.google.com/maps/place/Cruise+Whitsundays/@-20.2800481,148.7141176,17z/data=!3m1!4b1!4m6!3m5!1s0x6bd7dc8f8f8f8f8f:0x123456789!8m2!3d-20.2800481!4d148.7166925!16s%2Fg%2F11b8v0xyqm',
        # Will auto-fill based on CSV files
        'tour_ids': []  # Leave empty to scrape from CSV
    },
    
    'truebluesailing': {
        'url': 'https://www.google.com/maps/place/True+Blue+Sailing/@-20.2678,148.7198,17z',
        'tour_ids': []
    },
    
    # Add more companies...
}

def init_driver():
    """Initialize undetected Chrome with better stealth"""
    options = uc.ChromeOptions()
    
    # Remove headless for better detection avoidance
    # options.add_argument('--headless=new')  # Comment out headless
    
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    
    # Better user agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = uc.Chrome(options=options)  # Auto-detect Chrome version
    
    # Add random delays to seem more human
    driver.implicitly_wait(2)
    
    return driver

def scrape_google_maps_reviews(driver, url, max_reviews=20):
    """Scrape reviews from Google Maps"""
    reviews = []
    
    try:
        print(f"  Loading Google Maps...")
        driver.get(url)
        
        # Human-like delay
        time.sleep(random.uniform(5, 8))
        
        # Try to click on reviews tab
        try:
            # Look for reviews button/tab
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Save initial page
            with open('debug_maps_initial.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            
            # Scroll to load more reviews
            for i in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Extract overall rating
            overall_rating = 0
            # Google Maps rating is usually in a span with specific pattern
            rating_elements = soup.find_all(text=re.compile(r'\d+\.\d+'))
            for elem in rating_elements:
                match = re.search(r'(\d+\.\d+)', elem)
                if match:
                    potential_rating = float(match.group(1))
                    if 0 <= potential_rating <= 5:
                        overall_rating = potential_rating
                        break
            
            # Extract review count
            review_count = 0
            count_elements = soup.find_all(text=re.compile(r'\d+.*reviews?', re.I))
            for elem in count_elements:
                match = re.search(r'([\d,]+)', elem)
                if match:
                    review_count = int(match.group(1).replace(',', ''))
                    break
            
            print(f"  Found rating: {overall_rating}, count: {review_count}")
            
            # Try to find review text (this is harder in Maps)
            # Save the page for manual inspection
            with open('debug_maps_scrolled.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            
            print(f"  Saved HTML to debug_maps_*.html for inspection")
            
            # For now, return the rating even without full review text
            return {
                'reviews': reviews,  # May be empty
                'overall_rating': overall_rating,
                'review_count': review_count,
                'source': 'Google Reviews',
                'source_url': url
            }
            
        except Exception as e:
            print(f"  Error navigating: {e}")
            return None
            
    except Exception as e:
        print(f"  Error: {e}")
        return None

def load_tour_ids_for_company(company):
    """Load all tour IDs for a company from CSV files"""
    import csv
    import glob
    
    tour_ids = []
    csv_pattern = f'tours_{company}_cleaned_with_media.csv'
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        csv_pattern = f'tours_{company}_*.csv'
        csv_files = glob.glob(csv_pattern)
    
    for csvfile in csv_files:
        try:
            with open(csvfile, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id'):
                        tour_ids.append(row['id'])
        except Exception as e:
            print(f"  Warning: Could not load {csvfile}: {e}")
    
    return tour_ids

def save_reviews(company, tour_id, review_data):
    """Save reviews to JSON file"""
    os.makedirs(f'tour_reviews/{company}', exist_ok=True)
    filepath = f'tour_reviews/{company}/{tour_id}.json'
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(review_data, f, indent=2, ensure_ascii=False)

def main():
    print("=" * 70)
    print("DIRECT GOOGLE MAPS REVIEW SCRAPER")
    print("=" * 70)
    print("\nThis avoids Google Search CAPTCHAs by going directly to Maps!")
    print()
    
    driver = init_driver()
    
    try:
        for company, config in GOOGLE_MAPS_URLS.items():
            print(f"\n{'='*70}")
            print(f"Processing: {company}")
            print(f"{'='*70}")
            
            url = config['url']
            tour_ids = config.get('tour_ids', [])
            
            # Auto-load tour IDs if not specified
            if not tour_ids:
                print(f"  Auto-loading tour IDs from CSV...")
                tour_ids = load_tour_ids_for_company(company)
                print(f"  Found {len(tour_ids)} tours")
            
            if not tour_ids:
                print(f"  ⚠️  No tours found for {company}, skipping")
                continue
            
            print(f"  URL: {url}")
            print()
            
            # Scrape Google Maps
            review_data = scrape_google_maps_reviews(driver, url, max_reviews=20)
            
            if review_data and (review_data.get('overall_rating') > 0 or review_data.get('reviews')):
                print(f"  ✅ Success!")
                print(f"     Rating: {review_data['overall_rating']}")
                print(f"     Count: {review_data['review_count']}")
                print(f"     Reviews scraped: {len(review_data.get('reviews', []))}")
                
                # Save to all tour files
                print(f"\n  Saving to {len(tour_ids)} tour files...")
                for tour_id in tour_ids:
                    save_reviews(company, tour_id, review_data)
                print(f"  ✅ Saved!")
            else:
                print(f"  ❌ Failed to get reviews")
            
            # Long delay between companies
            time.sleep(random.uniform(10, 15))
        
        print(f"\n{'='*70}")
        print("COMPLETE")
        print(f"{'='*70}")
        
    finally:
        input("\n\nPress ENTER to close browser...")
        driver.quit()

if __name__ == '__main__':
    main()

