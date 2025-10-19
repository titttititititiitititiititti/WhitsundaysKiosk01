"""
TripAdvisor Scraper with Manual CAPTCHA Solving

Scrapes reviews from TripAdvisor. When CAPTCHA appears, you solve it manually.
Gets detailed reviews with text, titles, dates - much better than just ratings!
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

# TripAdvisor URLs for major companies
TRIPADVISOR_URLS = {
    'cruisewhitsundays': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427261-Reviews-Cruise_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'redcatadventures': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2268383-Reviews-Red_Cat_Adventures-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'zigzagwhitsundays': 'https://www.tripadvisor.com/Attraction_Review-g255068-d4100589-Reviews-ZigZag_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'prosail': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427260-Reviews-ProSail_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'ozsail': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427262-Reviews-OzSail-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'iconicwhitsunday': 'https://www.tripadvisor.com/Attraction_Review-g255068-d10668992-Reviews-Iconic_Whitsunday-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'exploregroup': 'https://www.tripadvisor.com/Attraction_Review-g255068-d4517595-Reviews-Explore_Group-Airlie_Beach_Whitsunday_Islands_Queensland.html',
}

def init_driver():
    """Initialize browser"""
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--no-sandbox')
    
    driver = uc.Chrome(options=options)
    driver.implicitly_wait(3)
    
    return driver

def scrape_tripadvisor_reviews(driver, url, max_reviews=20):
    """Scrape TripAdvisor with manual CAPTCHA solving"""
    reviews = []
    
    try:
        print(f"  Loading TripAdvisor...")
        driver.get(url)
        time.sleep(random.uniform(5, 8))
        
        # Check for CAPTCHA - better detection
        page_title = driver.title.lower()
        current_url = driver.current_url.lower()
        
        # If we see CAPTCHA page or DataDome
        if ("captcha" in page_title or "please verify" in page_title or 
            "datadome" in driver.page_source[:5000] or  # Only check first 5000 chars
            "captcha-delivery.com" in driver.page_source[:5000]):
            
            print("  ⚠️  ⚠️  ⚠️  CAPTCHA DETECTED! ⚠️  ⚠️  ⚠️")
            print("  👉 Please solve the CAPTCHA in the browser")
            print("  ⏰ After solving, press ENTER here...")
            input("     Press ENTER when CAPTCHA is solved and page has loaded: ")
            print("  ✅ Continuing...")
            time.sleep(3)  # Give page a moment to settle
        
        # Check if we're on the right page
        if "tripadvisor.com" not in driver.current_url:
            print(f"  ❌ Not on TripAdvisor! Current URL: {driver.current_url[:100]}")
            return None
        
        # Scroll to load reviews
        print(f"  Scrolling to load reviews...")
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 3))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Save for debugging
        with open('debug_tripadvisor_manual.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        
        # Extract overall rating
        overall_rating = 0
        rating_elem = soup.find(text=re.compile(r'\d+\.\d+.*reviews?', re.I))
        if rating_elem:
            match = re.search(r'(\d+\.\d+)', rating_elem)
            if match:
                overall_rating = float(match.group(1))
        
        # Extract review count
        review_count = 0
        count_elem = soup.find(text=re.compile(r'([\d,]+)\s+reviews?', re.I))
        if count_elem:
            match = re.search(r'([\d,]+)', count_elem)
            if match:
                review_count = int(match.group(1).replace(',', ''))
        
        print(f"  Rating: {overall_rating}★, Count: {review_count:,}")
        
        # Extract individual reviews
        review_selectors = [
            soup.find_all('div', class_=re.compile(r'review-container|reviewSelector', re.I)),
            soup.find_all('div', attrs={'data-automation': 'reviewCard'}),
            soup.find_all('div', class_=re.compile(r'.*review.*', re.I))
        ]
        
        review_containers = []
        for selector_result in review_selectors:
            if selector_result:
                review_containers = selector_result
                break
        
        print(f"  Found {len(review_containers)} review containers")
        
        for container in review_containers[:max_reviews]:
            try:
                review_data = {}
                
                # Rating
                rating_span = container.find('span', class_=re.compile(r'.*bubble.*rating.*', re.I))
                if rating_span:
                    for cls in rating_span.get('class', []):
                        if 'bubble_' in cls.lower():
                            match = re.search(r'(\d+)', cls)
                            if match:
                                review_data['rating'] = int(match.group(1)) / 10
                                break
                
                # Title
                title_elem = container.find(['div', 'span', 'a'], class_=re.compile(r'.*title.*', re.I))
                if title_elem:
                    review_data['title'] = title_elem.get_text(strip=True)
                
                # Text
                text_elem = container.find(['q', 'div', 'span'], class_=re.compile(r'.*review.*text.*', re.I))
                if text_elem:
                    review_data['text'] = text_elem.get_text(strip=True)
                
                # Author
                author_elem = container.find(['span', 'div'], class_=re.compile(r'.*username.*|.*author.*', re.I))
                if author_elem:
                    review_data['author'] = author_elem.get_text(strip=True)
                
                # Date
                date_elem = container.find(['span', 'div'], class_=re.compile(r'.*date.*', re.I))
                if date_elem:
                    review_data['date'] = date_elem.get_text(strip=True)
                
                if review_data.get('text'):
                    reviews.append(review_data)
                    
            except:
                continue
        
        print(f"  ✅ Scraped {len(reviews)} detailed reviews")
        
        return {
            'reviews': reviews,
            'overall_rating': overall_rating or (sum(r.get('rating', 5) for r in reviews) / len(reviews) if reviews else 0),
            'review_count': review_count or len(reviews),
            'source': 'TripAdvisor',
            'source_url': url
        }
        
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

def main():
    print("=" * 70)
    print("TRIPADVISOR SCRAPER (Manual CAPTCHA)")
    print("=" * 70)
    print("\n💡 TripAdvisor has detailed reviews with text, titles, dates!")
    print("⚠️  You'll need to solve CAPTCHAs manually when they appear.")
    print()
    input("Press ENTER to start...")
    
    driver = init_driver()
    
    try:
        success_count = 0
        
        for company, url in TRIPADVISOR_URLS.items():
            print(f"\n{'='*70}")
            print(f"{company.upper()}")
            print(f"{'='*70}")
            
            tour_ids = load_tour_ids_for_company(company)
            if not tour_ids:
                print(f"  ⚠️  No tours found")
                continue
            
            print(f"  Tours: {len(tour_ids)}")
            print(f"  URL: {url[:60]}...")
            
            review_data = scrape_tripadvisor_reviews(driver, url, max_reviews=20)
            
            if review_data and (review_data['overall_rating'] > 0 or review_data['reviews']):
                print(f"  💾 Saving to {len(tour_ids)} files...")
                for tour_id in tour_ids:
                    save_reviews(company, tour_id, review_data)
                print(f"  ✅ Done!")
                success_count += 1
            else:
                print(f"  ❌ Failed")
            
            # Wait between companies
            if company != list(TRIPADVISOR_URLS.keys())[-1]:
                print(f"  ⏸️  Waiting 15 seconds...")
                time.sleep(15)
        
        print(f"\n{'='*70}")
        print(f"✅ SUCCESS: {success_count}/{len(TRIPADVISOR_URLS)} companies")
        print(f"{'='*70}")
        
    finally:
        input("\nPress ENTER to close...")
        driver.quit()

if __name__ == '__main__':
    main()

