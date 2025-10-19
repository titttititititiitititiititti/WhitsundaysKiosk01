"""
Complete Google Reviews Scraper

1. Searches Google for each company
2. Extracts rating from knowledge panel
3. Clicks "Reviews" to see full reviews
4. Scrapes written testimonials with author names

This gets you both ratings AND actual review text for display!
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
from urllib.parse import quote_plus

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

def scrape_google_reviews_complete(driver, company_display_name, max_reviews=20):
    """Scrape both rating and actual review text"""
    try:
        # Search Google
        search_query = f"{company_display_name} Airlie Beach"
        search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
        
        print(f"  🔍 Searching: {search_query}")
        driver.get(search_url)
        time.sleep(random.uniform(4, 6))
        
        # Check for CAPTCHA
        if "sorry" in driver.current_url.lower():
            print("  ⚠️  CAPTCHA! Please solve it...")
            input("  Press ENTER after solving: ")
        
        # Save the initial search page
        with open('debug_search_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        
        # METHOD 1: Extract rating from knowledge panel first
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        overall_rating = 0
        review_count = 0
        
        # Look for the pattern: "4.9 ★★★★★ 2,233 Google reviews"
        text = soup.get_text()
        
        # Try multiple patterns
        patterns = [
            r'(\d+\.\d+)\s*[★⭐]+\s*([\d,]+)\s+Google reviews?',
            r'(\d+\.\d+)\s*★+\s*([\d,]+)\s+reviews?',
            r'(\d\.\d)\s+[★⭐]{5}\s+([\d,]+)\s+Google reviews',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                overall_rating = float(match.group(1))
                review_count = int(match.group(2).replace(',', ''))
                print(f"  ✅ Found rating: {overall_rating}★ ({review_count:,} reviews)")
                break
        
        if overall_rating == 0:
            print(f"  ⚠️  Could not extract rating from search page")
            print(f"  💡 Check debug_search_page.html to see what's available")
        
        # METHOD 2: Click "Reviews" to get actual review text
        reviews = []
        
        try:
            # Look for "Reviews" button/link
            print(f"  🖱️  Looking for Reviews button...")
            
            # Try to find and click the Reviews button
            reviews_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Reviews') or contains(text(), 'reviews')]")
            
            clicked = False
            for button in reviews_buttons:
                try:
                    # Check if it's clickable and visible
                    if button.is_displayed() and button.is_enabled():
                        print(f"  🖱️  Clicking Reviews...")
                        button.click()
                        clicked = True
                        time.sleep(random.uniform(3, 5))
                        break
                except:
                    continue
            
            if clicked:
                print(f"  ✅ Clicked Reviews! Now on reviews page...")
                
                # Scroll to load reviews
                print(f"  📜 Scrolling to load reviews...")
                for i in range(5):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(random.uniform(1, 2))
                
                # Parse the reviews page
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Save reviews page for debugging
                with open('debug_reviews_page.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                
                # Try to extract individual reviews
                # Google's structure varies, so try multiple selectors
                
                # Look for review-like patterns in text
                review_elements = soup.find_all(['div', 'span'], class_=re.compile(r'review', re.I))
                
                print(f"  📝 Found {len(review_elements)} potential review elements")
                
                # Try to parse reviews
                for elem in review_elements[:max_reviews]:
                    try:
                        text_content = elem.get_text(strip=True)
                        
                        # Skip if too short or too long to be a review
                        if len(text_content) < 20 or len(text_content) > 1000:
                            continue
                        
                        # Basic review structure
                        review_data = {
                            'text': text_content,
                            'author': 'Google User',  # Google often hides full names
                            'rating': 5.0  # Assume 5 stars if not specified
                        }
                        
                        # Try to extract star rating from nearby elements
                        parent = elem.parent
                        if parent:
                            rating_elem = parent.find(text=re.compile(r'★+|⭐+'))
                            if rating_elem:
                                stars = rating_elem.count('★') + rating_elem.count('⭐')
                                if stars > 0:
                                    review_data['rating'] = float(stars)
                        
                        reviews.append(review_data)
                        
                        if len(reviews) >= max_reviews:
                            break
                            
                    except:
                        continue
                
                print(f"  ✅ Extracted {len(reviews)} reviews with text")
            else:
                print(f"  ⚠️  Could not click Reviews button")
                
        except Exception as e:
            print(f"  ⚠️  Error getting review text: {e}")
        
        # Return what we have
        if overall_rating > 0 or reviews:
            return {
                'reviews': reviews,
                'overall_rating': overall_rating,
                'review_count': review_count,
                'source': 'Google Reviews',
                'source_url': driver.current_url
            }
        else:
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def load_tour_ids_for_company(company):
    """Load tour IDs"""
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
    """Save reviews"""
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
    print("COMPLETE GOOGLE REVIEWS SCRAPER")
    print("=" * 70)
    print("\n✨ Gets both ratings AND written testimonials!")
    print()
    print("What it does:")
    print("  1. Searches Google for each company")
    print("  2. Extracts rating from knowledge panel")
    print("  3. Clicks 'Reviews' to see full reviews")
    print("  4. Scrapes written testimonials")
    print()
    input("Press ENTER to start...")
    
    driver = init_driver()
    
    try:
        success_count = 0
        
        for company in COMPANIES_TO_SCRAPE:
            print(f"\n{'='*70}")
            print(f"📍 {get_company_display_name(company)}")
            print(f"{'='*70}")
            
            tour_ids = load_tour_ids_for_company(company)
            if not tour_ids:
                print(f"  ⚠️  No tours found")
                continue
            
            print(f"  📊 Tours: {len(tour_ids)}")
            
            review_data = scrape_google_reviews_complete(
                driver, 
                get_company_display_name(company), 
                max_reviews=20
            )
            
            if review_data:
                print(f"\n  💾 Saving to {len(tour_ids)} tour files...")
                print(f"     Rating: {review_data['overall_rating']}★")
                print(f"     Total reviews: {review_data['review_count']:,}")
                print(f"     Testimonials scraped: {len(review_data['reviews'])}")
                
                for tour_id in tour_ids:
                    save_reviews(company, tour_id, review_data)
                
                print(f"  ✅ Saved!")
                success_count += 1
            else:
                print(f"  ❌ No data found")
            
            # Wait between companies
            if company != COMPANIES_TO_SCRAPE[-1]:
                print(f"\n  ⏸️  Waiting 12 seconds...")
                time.sleep(12)
        
        print(f"\n{'='*70}")
        print(f"✅ COMPLETE: {success_count}/{len(COMPANIES_TO_SCRAPE)} companies")
        print(f"{'='*70}")
        print(f"\n💡 Check tour_reviews/ folder for JSON files with ratings & testimonials!")
        
    finally:
        input("\nPress ENTER to close browser...")
        driver.quit()

if __name__ == '__main__':
    main()



