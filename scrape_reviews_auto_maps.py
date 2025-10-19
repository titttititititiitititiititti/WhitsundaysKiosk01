"""
Automated Google Maps Review Scraper

Searches Google for each company, finds the Maps link automatically,
clicks it, then scrapes reviews. Best of both worlds!

Usage:
    python scrape_reviews_auto_maps.py
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import random
import json
import os
import re
import csv
import glob
from urllib.parse import quote_plus, unquote

REVIEWS_DIR = 'tour_reviews'

# Companies to scrape (will auto-load from CSV files)
COMPANIES_TO_SCRAPE = [
    'cruisewhitsundays',
    'truebluesailing',
    'redcatadventures',
    'zigzagwhitsundays',
    'prosail',
    'ozsail',
    'exploregroup',
    'iconicwhitsunday',
    # Add more as needed
]

def init_driver():
    """Initialize undetected Chrome - visible browser to handle CAPTCHAs if needed"""
    options = uc.ChromeOptions()
    
    # Visible browser (easier to debug and handle CAPTCHAs)
    options.add_argument('--start-maximized')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Let undetected_chromedriver auto-detect Chrome version
    driver = uc.Chrome(options=options)
    driver.implicitly_wait(3)
    
    return driver

def search_google_and_find_maps_link(driver, company_name):
    """Search Google and extract the Maps link"""
    try:
        # Build search query
        search_query = f"{company_name} Airlie Beach"
        search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
        
        print(f"  Searching Google: {search_query}")
        driver.get(search_url)
        time.sleep(random.uniform(3, 5))
        
        # Check if CAPTCHA appeared
        if "sorry" in driver.current_url.lower() or "captcha" in driver.page_source.lower():
            print("  ⚠️  CAPTCHA detected! Please solve it in the browser...")
            print("  Waiting 30 seconds for you to solve it...")
            time.sleep(30)
            
            # Check again
            if "sorry" in driver.current_url.lower():
                print("  ❌ Still blocked. Skipping this company.")
                return None
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Method 1: Look for "View larger map" link
        maps_links = soup.find_all('a', href=re.compile(r'google\.com/maps', re.I))
        
        if maps_links:
            for link in maps_links:
                href = link.get('href', '')
                # Extract clean URL
                if '/url?q=' in href:
                    actual_url = href.split('/url?q=')[1].split('&')[0]
                    maps_url = unquote(actual_url)
                elif href.startswith('https://www.google.com/maps'):
                    maps_url = href
                else:
                    continue
                
                # Validate it's a place page
                if '/place/' in maps_url or 'query=' in maps_url:
                    print(f"  ✅ Found Maps link!")
                    return maps_url
        
        # Method 2: Try to find Maps button/link by clicking
        try:
            # Look for clickable Maps elements
            maps_button = driver.find_elements(By.XPATH, "//*[contains(text(), 'View larger map')]")
            if not maps_button:
                maps_button = driver.find_elements(By.XPATH, "//*[contains(text(), 'Directions')]")
            if not maps_button:
                maps_button = driver.find_elements(By.XPATH, "//a[contains(@href, 'google.com/maps')]")
            
            if maps_button:
                print(f"  Clicking Maps link...")
                maps_button[0].click()
                time.sleep(random.uniform(3, 5))
                
                # Get the new URL
                current_url = driver.current_url
                if 'google.com/maps' in current_url:
                    print(f"  ✅ Navigated to Maps!")
                    return current_url
        except Exception as e:
            print(f"  Could not click Maps link: {e}")
        
        print(f"  ⚠️  No Maps link found in search results")
        return None
        
    except Exception as e:
        print(f"  ❌ Error searching: {e}")
        return None

def scrape_google_maps_reviews(driver, url, max_reviews=20):
    """Scrape reviews from Google Maps"""
    reviews = []
    
    try:
        # If we're not already on Maps, navigate there
        if 'google.com/maps' not in driver.current_url:
            print(f"  Loading Maps...")
            driver.get(url)
            time.sleep(random.uniform(4, 6))
        
        # Try to click on the reviews section/tab
        try:
            # Look for reviews button
            reviews_button = driver.find_elements(By.XPATH, "//*[contains(text(), 'reviews')]")
            if reviews_button:
                print(f"  Clicking reviews section...")
                reviews_button[0].click()
                time.sleep(random.uniform(2, 4))
        except:
            pass
        
        # Scroll to load reviews
        print(f"  Scrolling to load reviews...")
        for i in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
        
        # Parse the page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Save for debugging
        with open('debug_maps_final.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        
        # Extract overall rating
        overall_rating = 0
        rating_patterns = [
            r'(\d+\.\d+)\s*stars?',
            r'(\d+\.\d+)\s*★',
            r'rating.*?(\d+\.\d+)',
        ]
        
        page_text = soup.get_text()
        for pattern in rating_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                potential_rating = float(match.group(1))
                if 0 <= potential_rating <= 5:
                    overall_rating = potential_rating
                    break
        
        # Extract review count
        review_count = 0
        count_patterns = [
            r'([\d,]+)\s+reviews?',
            r'([\d,]+)\s+ratings?',
        ]
        
        for pattern in count_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                review_count = int(match.group(1).replace(',', ''))
                break
        
        print(f"  Found: {overall_rating}★ ({review_count} reviews)")
        
        # Try to extract individual reviews (Google Maps structure changes often)
        review_divs = soup.find_all('div', class_=re.compile(r'.*review.*', re.I))
        
        print(f"  Found {len(review_divs)} potential review elements")
        
        # Note: Full review scraping from Maps is complex and fragile
        # For now, we'll just get the rating/count which is most important
        
        return {
            'reviews': reviews,  # May be empty - that's okay
            'overall_rating': overall_rating,
            'review_count': review_count,
            'source': 'Google Reviews',
            'source_url': driver.current_url
        }
        
    except Exception as e:
        print(f"  ❌ Error scraping Maps: {e}")
        return None

def load_tour_ids_for_company(company):
    """Load all tour IDs for a company from CSV files"""
    tour_ids = []
    csv_pattern = f'tours_{company}_cleaned_with_media.csv'
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        csv_pattern = f'tours_{company}*.csv'
        csv_files = glob.glob(csv_pattern)
    
    for csvfile in csv_files:
        try:
            with open(csvfile, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('id'):
                        tour_ids.append(row['id'])
        except Exception as e:
            pass
    
    return tour_ids

def save_reviews(company, tour_id, review_data):
    """Save reviews to JSON file"""
    os.makedirs(f'{REVIEWS_DIR}/{company}', exist_ok=True)
    filepath = f'{REVIEWS_DIR}/{company}/{tour_id}.json'
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(review_data, f, indent=2, ensure_ascii=False)

def get_company_display_name(company):
    """Get prettier company name"""
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
    print("AUTOMATED GOOGLE MAPS REVIEW SCRAPER")
    print("=" * 70)
    print()
    print("This will:")
    print("  1. Search Google for each company")
    print("  2. Find and click the Maps link")
    print("  3. Scrape reviews from Maps")
    print("  4. Save to all tour files for that company")
    print()
    print("⚠️  If CAPTCHAs appear, please solve them in the browser!")
    print()
    
    input("Press ENTER to start...")
    
    driver = init_driver()
    
    try:
        success_count = 0
        failed_count = 0
        
        for company in COMPANIES_TO_SCRAPE:
            print(f"\n{'='*70}")
            print(f"Processing: {get_company_display_name(company)}")
            print(f"{'='*70}")
            
            # Load tour IDs
            tour_ids = load_tour_ids_for_company(company)
            if not tour_ids:
                print(f"  ⚠️  No tours found in CSV, skipping")
                continue
            
            print(f"  Found {len(tour_ids)} tours for this company")
            
            # Search Google and find Maps link
            maps_url = search_google_and_find_maps_link(driver, get_company_display_name(company))
            
            if not maps_url:
                print(f"  ❌ Could not find Maps link")
                failed_count += 1
                continue
            
            # Scrape reviews from Maps
            review_data = scrape_google_maps_reviews(driver, maps_url, max_reviews=20)
            
            if review_data and review_data.get('overall_rating') > 0:
                print(f"  ✅ Success!")
                print(f"     Rating: {review_data['overall_rating']}★")
                print(f"     Reviews: {review_data['review_count']}")
                
                # Save to all tour files
                print(f"  Saving to {len(tour_ids)} tour files...")
                for tour_id in tour_ids:
                    save_reviews(company, tour_id, review_data)
                
                print(f"  ✅ Saved!")
                success_count += 1
            else:
                print(f"  ❌ Could not get reviews")
                failed_count += 1
            
            # Long delay between companies to avoid detection
            if company != COMPANIES_TO_SCRAPE[-1]:  # Don't wait after last one
                print(f"\n  Waiting 15 seconds before next company...")
                time.sleep(15)
        
        print(f"\n{'='*70}")
        print("SCRAPING COMPLETE")
        print(f"{'='*70}")
        print(f"  ✅ Success: {success_count} companies")
        print(f"  ❌ Failed: {failed_count} companies")
        print(f"{'='*70}")
        
    finally:
        input("\nPress ENTER to close browser...")
        driver.quit()

if __name__ == '__main__':
    main()

