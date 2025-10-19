"""
Google Search Knowledge Panel Scraper

Scrapes ratings directly from Google Search results (knowledge panel on the right).
No need to click anything - just get the rating from the search page!

This is the SIMPLEST method since the rating is right there.
"""

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import random
import json
import os
import re
import csv
import glob

REVIEWS_DIR = 'tour_reviews'

COMPANIES_TO_SCRAPE = [
    'cruisewhitsundays',
    'truebluesailing', 
    'redcatadventures',
    'zigzagwhitsundays',
    'prosail',
    'ozsail',
    'exploregroup',
    'iconicwhitsunday',
]

def init_driver():
    """Initialize browser"""
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--no-sandbox')
    
    driver = uc.Chrome(options=options)
    driver.implicitly_wait(3)
    
    return driver

def scrape_google_knowledge_panel(driver, company_display_name):
    """Scrape rating directly from Google Search knowledge panel"""
    try:
        # Search Google
        from urllib.parse import quote_plus
        search_query = f"{company_display_name} Airlie Beach"
        search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
        
        print(f"  Searching: {search_query}")
        driver.get(search_url)
        time.sleep(random.uniform(4, 6))
        
        # Check for CAPTCHA
        if "sorry" in driver.current_url.lower() or "captcha" in driver.page_source.lower():
            print("  ⚠️  CAPTCHA detected! Please solve it...")
            print("  Waiting 45 seconds...")
            time.sleep(45)
        
        # Save page for debugging
        with open('debug_search_panel.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        page_text = soup.get_text()
        
        # Look for rating pattern in knowledge panel
        # Patterns: "4.4 ★★★★★ 1,923 Google reviews"
        overall_rating = 0
        review_count = 0
        
        # Method 1: Look for "X.X" followed by stars and "reviews"
        rating_pattern = r'(\d+\.\d+)\s*[★⭐]+\s*([\d,]+)\s+(?:Google\s+)?reviews?'
        match = re.search(rating_pattern, page_text, re.I)
        
        if match:
            overall_rating = float(match.group(1))
            review_count = int(match.group(2).replace(',', ''))
            print(f"  ✅ Found: {overall_rating}★ ({review_count:,} reviews)")
        else:
            # Method 2: Just look for rating near "reviews"
            rating_match = re.search(r'(\d+\.\d+)\s*(?:stars?|★)', page_text)
            count_match = re.search(r'([\d,]+)\s+(?:Google\s+)?reviews?', page_text, re.I)
            
            if rating_match:
                overall_rating = float(rating_match.group(1))
            if count_match:
                review_count = int(count_match.group(1).replace(',', ''))
            
            if overall_rating > 0:
                print(f"  ✅ Found: {overall_rating}★ ({review_count:,} reviews)")
            else:
                print(f"  ⚠️  No rating found in knowledge panel")
        
        if overall_rating > 0:
            return {
                'reviews': [],  # Not scraping individual reviews from search page
                'overall_rating': overall_rating,
                'review_count': review_count,
                'source': 'Google Reviews',
                'source_url': search_url
            }
        else:
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def load_tour_ids_for_company(company):
    """Load all tour IDs for a company"""
    tour_ids = []
    csv_files = glob.glob(f'tours_{company}*.csv')
    
    for csvfile in csv_files:
        try:
            with open(csvfile, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id'):
                        tour_ids.append(row['id'])
        except:
            pass
    
    return tour_ids

def save_reviews(company, tour_id, review_data):
    """Save reviews to JSON"""
    os.makedirs(f'{REVIEWS_DIR}/{company}', exist_ok=True)
    filepath = f'{REVIEWS_DIR}/{company}/{tour_id}.json'
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(review_data, f, indent=2, ensure_ascii=False)

def get_company_display_name(company):
    """Get display name"""
    names = {
        'cruisewhitsundays': 'Cruise Whitsundays',
        'truebluesailing': 'True Blue Sailing',
        'redcatadventures': 'Red Cat Adventures',
        'zigzagwhitsundays': 'ZigZag Whitsundays',
        'prosail': 'ProSail',
        'ozsail': 'OzSail',
        'exploregroup': 'Explore Group',
        'iconicwhitsunday': 'Iconic Whitsunday',
    }
    return names.get(company, company.replace('_', ' ').title())

def main():
    print("=" * 70)
    print("GOOGLE SEARCH KNOWLEDGE PANEL SCRAPER")
    print("=" * 70)
    print("\nScrapes ratings directly from Google Search results!")
    print("(The knowledge panel on the right side)")
    print()
    input("Press ENTER to start...")
    
    driver = init_driver()
    
    try:
        success_count = 0
        
        for company in COMPANIES_TO_SCRAPE:
            print(f"\n{'='*70}")
            print(f"{get_company_display_name(company)}")
            print(f"{'='*70}")
            
            tour_ids = load_tour_ids_for_company(company)
            if not tour_ids:
                print(f"  ⚠️  No tours found")
                continue
            
            print(f"  Found {len(tour_ids)} tours")
            
            review_data = scrape_google_knowledge_panel(driver, get_company_display_name(company))
            
            if review_data and review_data['overall_rating'] > 0:
                print(f"  💾 Saving to {len(tour_ids)} files...")
                for tour_id in tour_ids:
                    save_reviews(company, tour_id, review_data)
                print(f"  ✅ Done!")
                success_count += 1
            else:
                print(f"  ❌ No rating found")
            
            # Wait between companies
            if company != COMPANIES_TO_SCRAPE[-1]:
                print(f"  ⏸️  Waiting 10 seconds...")
                time.sleep(10)
        
        print(f"\n{'='*70}")
        print(f"✅ SUCCESS: {success_count}/{len(COMPANIES_TO_SCRAPE)} companies")
        print(f"{'='*70}")
        
    finally:
        input("\nPress ENTER to close...")
        driver.quit()

if __name__ == '__main__':
    main()



