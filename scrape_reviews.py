"""
Review Scraper for Tour Kiosk Project

This script scrapes 10-20 reviews per tour from TripAdvisor and stores them for display.
Reviews are scraped from existing tour operator pages and stored in JSON format.

Usage:
    python scrape_reviews.py

Requirements:
    - selenium, undetected-chromedriver, beautifulsoup4
    - Tour CSV files with tour company names and tour names
"""

import csv
import json
import os
import time
import re
from urllib.parse import quote_plus, urljoin, unquote
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import random
import glob

# Directory to store review JSON files
REVIEWS_DIR = 'tour_reviews'

# Company TripAdvisor mappings (you'll need to update these with actual TripAdvisor URLs)
# These are educated guesses - you may need to verify/update them
TRIPADVISOR_COMPANY_URLS = {
    'redcatadventures': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2268383-Reviews-Red_Cat_Adventures-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'cruisewhitsundays': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427261-Reviews-Cruise_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'zigzagwhitsundays': 'https://www.tripadvisor.com/Attraction_Review-g255068-d4100589-Reviews-ZigZag_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'prosail': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427260-Reviews-ProSail_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'iconicwhitsunday': 'https://www.tripadvisor.com/Attraction_Review-g255068-d10668992-Reviews-Iconic_Whitsunday-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'exploregroup': 'https://www.tripadvisor.com/Attraction_Review-g255068-d4517595-Reviews-Explore_Group-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'oceanrafting': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2268380-Reviews-Ocean_Rafting-Airlie_Beach_Whitsunday_Islands_Queensland.html',
    'ozsail': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427262-Reviews-OzSail-Airlie_Beach_Whitsunday_Islands_Queensland.html',
}

def init_driver():
    """Initialize undetected Chrome driver"""
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    driver = uc.Chrome(options=options)
    return driver

def search_tripadvisor_for_tour(driver, tour_name, company_name):
    """Search TripAdvisor for a specific tour and return the URL"""
    try:
        # First try to use company-specific TripAdvisor page
        company_url = TRIPADVISOR_COMPANY_URLS.get(company_name.lower().replace(' ', '').replace('-', ''))
        if company_url:
            print(f"  Using known TripAdvisor URL for {company_name}")
            return company_url
        
        # Otherwise, search for the tour
        search_query = f"{tour_name} {company_name} Airlie Beach Whitsundays"
        search_url = f"https://www.tripadvisor.com/Search?q={quote_plus(search_query)}"
        
        print(f"  Searching TripAdvisor for: {search_query}")
        driver.get(search_url)
        time.sleep(random.uniform(3, 5))
        
        # Look for attraction links in search results
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        links = soup.find_all('a', href=re.compile(r'Attraction_Review'))
        
        if links:
            first_link = links[0].get('href')
            if not first_link.startswith('http'):
                first_link = urljoin('https://www.tripadvisor.com', first_link)
            print(f"  Found TripAdvisor page: {first_link}")
            return first_link
        else:
            print(f"  No TripAdvisor page found for {tour_name}")
            return None
            
    except Exception as e:
        print(f"  Error searching TripAdvisor: {e}")
        return None

def scrape_google_maps_reviews(driver, url, max_reviews=20):
    """Scrape reviews from a Google Maps page"""
    reviews = []
    
    try:
        print(f"    Loading Google Maps page...")
        driver.get(url)
        time.sleep(random.uniform(4, 6))
        
        # Scroll to load reviews
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract overall rating
        overall_rating = 0
        rating_elem = soup.find('div', class_=re.compile(r'.*fontDisplayLarge.*', re.I))
        if rating_elem:
            rating_text = rating_elem.get_text()
            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
            if rating_match:
                overall_rating = float(rating_match.group(1))
        
        # Extract review count
        review_count = 0
        count_elem = soup.find(text=re.compile(r'\d+.*reviews?', re.I))
        if count_elem:
            count_match = re.search(r'(\d+)', count_elem)
            if count_match:
                review_count = int(count_match.group(1))
        
        # Extract Google Maps reviews
        review_divs = (
            soup.find_all('div', class_=re.compile(r'.*review.*content.*', re.I)) or
            soup.find_all('div', attrs={'data-review-id': True}) or
            soup.find_all('div', class_=re.compile(r'.*jftiEf.*', re.I))
        )
        
        print(f"    Found {len(review_divs)} review containers")
        
        for div in review_divs[:max_reviews]:
            try:
                review_data = {}
                
                # Extract rating
                rating_span = div.find('span', attrs={'role': 'img'})
                if rating_span:
                    aria_label = rating_span.get('aria-label', '')
                    rating_match = re.search(r'(\d+)', aria_label)
                    if rating_match:
                        review_data['rating'] = int(rating_match.group(1))
                
                # Extract review text
                text_span = div.find('span', class_=re.compile(r'.*review.*text.*|.*wiI7pd.*', re.I))
                if text_span:
                    review_data['text'] = text_span.get_text(strip=True)
                
                # Extract author
                author_div = div.find('div', class_=re.compile(r'.*author.*|.*name.*', re.I))
                if author_div:
                    review_data['author'] = author_div.get_text(strip=True)
                else:
                    review_data['author'] = "Google User"
                
                # Extract date
                date_span = div.find('span', class_=re.compile(r'.*date.*|.*time.*', re.I))
                if date_span:
                    review_data['date'] = date_span.get_text(strip=True)
                
                if review_data.get('text'):
                    reviews.append(review_data)
                    
            except Exception as e:
                continue
        
        # Calculate overall rating if not found
        if overall_rating == 0 and reviews:
            overall_rating = sum(r.get('rating', 5) for r in reviews) / len(reviews)
        
        return {
            'reviews': reviews,
            'overall_rating': overall_rating or 0,
            'review_count': review_count or len(reviews),
            'source': 'Google Reviews',
            'source_url': url
        }
        
    except Exception as e:
        print(f"    Error scraping Google Maps: {e}")
        return None

def scrape_facebook_reviews(driver, url, max_reviews=20):
    """Scrape reviews from a Facebook page (basic - may be limited)"""
    reviews = []
    
    try:
        print(f"    Loading Facebook page...")
        driver.get(url)
        time.sleep(random.uniform(4, 6))
        
        # Scroll to load content
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Facebook reviews are harder to scrape due to dynamic loading
        # Try to extract basic rating if visible
        overall_rating = 0
        rating_elem = soup.find(text=re.compile(r'\d+\.?\d*.*out of 5', re.I))
        if rating_elem:
            rating_match = re.search(r'(\d+\.?\d*)', rating_elem)
            if rating_match:
                overall_rating = float(rating_match.group(1))
        
        # Try to extract review count
        review_count = 0
        count_elem = soup.find(text=re.compile(r'\d+.*reviews?', re.I))
        if count_elem:
            count_match = re.search(r'(\d+)', count_elem)
            if count_match:
                review_count = int(count_match.group(1))
        
        # Note: Full Facebook review scraping is complex due to dynamic content
        # For now, we'll at least get the rating if available
        
        return {
            'reviews': [],  # Facebook reviews are harder to scrape
            'overall_rating': overall_rating,
            'review_count': review_count,
            'source': 'Facebook',
            'source_url': url
        }
        
    except Exception as e:
        print(f"    Error scraping Facebook: {e}")
        return None

def scrape_google_reviews(driver, tour_name, company_name, max_reviews=20):
    """Scrape reviews from Google search results - try multiple results until we find reviews"""
    reviews = []
    
    try:
        # Search Google for reviews
        search_query = f"{tour_name} {company_name} Airlie Beach reviews"
        search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
        
        print(f"  Searching Google for: {search_query}")
        driver.get(search_url)
        time.sleep(random.uniform(3, 5))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Collect ALL potential review links from search results
        potential_links = []
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            # Look for review-related links (Google Maps, TripAdvisor, Facebook, etc.)
            if any(domain in href.lower() for domain in ['google.com/maps', 'tripadvisor.com', 'facebook.com', 'reviews']):
                # Extract actual URL from Google's redirect
                if '/url?q=' in href:
                    actual_url = href.split('/url?q=')[1].split('&')[0]
                    clean_url = unquote(actual_url)
                else:
                    clean_url = href
                
                # Avoid duplicates
                if clean_url not in potential_links and clean_url.startswith('http'):
                    potential_links.append(clean_url)
        
        print(f"  Found {len(potential_links)} potential review sources to try")
        
        # Try each link until we find reviews
        for idx, review_url in enumerate(potential_links[:5], 1):  # Try up to 5 sources
            print(f"  Trying source {idx}/{min(len(potential_links), 5)}: {review_url[:60]}...")
            
            review_data = None
            
            # Try Google Maps
            if 'google.com/maps' in review_url:
                review_data = scrape_google_maps_reviews(driver, review_url, max_reviews)
            
            # Try TripAdvisor (if we missed it in the first search)
            elif 'tripadvisor.com' in review_url and 'Attraction_Review' in review_url:
                review_data = scrape_tripadvisor_reviews(driver, review_url, max_reviews)
            
            # Try Facebook (basic scraping - may be limited)
            elif 'facebook.com' in review_url:
                review_data = scrape_facebook_reviews(driver, review_url, max_reviews)
            
            # If we got reviews from this source, use it!
            if review_data and review_data.get('reviews') and len(review_data['reviews']) > 0:
                print(f"  ✅ Found {len(review_data['reviews'])} reviews from this source!")
                return review_data
            else:
                print(f"  ⚠️  No reviews at this source, trying next...")
        
        # If we get here, none of the sources had reviews
        print(f"  ❌ No reviews found from any of the {len(potential_links)} sources")
        return {
            'reviews': [],
            'overall_rating': 0,
            'review_count': 0,
            'source': 'Google',
            'source_url': None
        }
        
    except Exception as e:
        print(f"  Error scraping Google reviews: {e}")
        return {
            'reviews': [],
            'overall_rating': 0,
            'review_count': 0,
            'source': 'Google',
            'source_url': None
        }

def scrape_tripadvisor_reviews(driver, url, max_reviews=20):
    """Scrape reviews from a TripAdvisor page"""
    reviews = []
    
    try:
        print(f"  Loading TripAdvisor page...")
        driver.get(url)
        time.sleep(random.uniform(4, 6))
        
        # Wait for reviews to load
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "review-container"))
            )
        except:
            # Try alternative selectors
            pass
        
        # Scroll to load more reviews
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract overall rating
        overall_rating = None
        rating_elem = soup.find('div', class_=re.compile(r'.*rating.*', re.I))
        if rating_elem:
            rating_text = rating_elem.get_text()
            rating_match = re.search(r'(\d+\.?\d*)', rating_text)
            if rating_match:
                overall_rating = float(rating_match.group(1))
        
        # Extract review count
        review_count = 0
        count_elem = soup.find(text=re.compile(r'\d+\s+reviews?', re.I))
        if count_elem:
            count_match = re.search(r'(\d+)', count_elem)
            if count_match:
                review_count = int(count_match.group(1))
        
        # Find review containers (TripAdvisor has multiple possible class names)
        review_containers = (
            soup.find_all('div', class_=re.compile(r'review-container|reviewSelector', re.I)) or
            soup.find_all('div', attrs={'data-automation': 'reviewCard'}) or
            soup.find_all('div', class_=re.compile(r'.*review.*card.*', re.I))
        )
        
        print(f"  Found {len(review_containers)} review containers")
        
        for container in review_containers[:max_reviews]:
            try:
                review_data = {}
                
                # Extract rating (bubble rating)
                rating_elem = container.find('span', class_=re.compile(r'.*bubble.*rating.*', re.I))
                if rating_elem:
                    rating_class = rating_elem.get('class', [])
                    for cls in rating_class:
                        if 'bubble_' in cls.lower():
                            rating_match = re.search(r'(\d+)', cls)
                            if rating_match:
                                review_data['rating'] = int(rating_match.group(1)) / 10
                                break
                
                # If no rating found yet, try alternative method
                if 'rating' not in review_data:
                    review_data['rating'] = 5.0  # Default to 5 stars if can't determine
                
                # Extract title
                title_elem = container.find(['div', 'span', 'a'], class_=re.compile(r'.*title.*', re.I))
                if title_elem:
                    review_data['title'] = title_elem.get_text(strip=True)
                
                # Extract review text
                text_elem = (
                    container.find('q', class_=re.compile(r'.*review.*text.*', re.I)) or
                    container.find('div', class_=re.compile(r'.*review.*text.*', re.I)) or
                    container.find('span', class_=re.compile(r'.*review.*text.*', re.I)) or
                    container.find('p', class_=re.compile(r'.*review.*text.*', re.I))
                )
                if text_elem:
                    review_data['text'] = text_elem.get_text(strip=True)
                
                # Extract author
                author_elem = container.find(['span', 'div', 'a'], class_=re.compile(r'.*username.*|.*author.*|.*profile.*', re.I))
                if author_elem:
                    review_data['author'] = author_elem.get_text(strip=True)
                else:
                    review_data['author'] = "TripAdvisor User"
                
                # Extract date
                date_elem = container.find(['span', 'div'], class_=re.compile(r'.*date.*|.*stay.*date.*', re.I))
                if date_elem:
                    review_data['date'] = date_elem.get_text(strip=True)
                
                # Only add review if we have text
                if review_data.get('text'):
                    reviews.append(review_data)
                    
            except Exception as e:
                print(f"    Error parsing individual review: {e}")
                continue
        
        print(f"  Successfully scraped {len(reviews)} reviews")
        
        return {
            'reviews': reviews,
            'overall_rating': overall_rating or (sum(r.get('rating', 5) for r in reviews) / len(reviews) if reviews else 5.0),
            'review_count': review_count or len(reviews),
            'source': 'TripAdvisor',
            'source_url': url
        }
        
    except Exception as e:
        print(f"  Error scraping reviews: {e}")
        return {
            'reviews': [],
            'overall_rating': 0,
            'review_count': 0,
            'source': 'TripAdvisor',
            'source_url': url
        }

def save_reviews(company, tour_id, review_data):
    """Save reviews to JSON file"""
    os.makedirs(REVIEWS_DIR, exist_ok=True)
    
    # Create company subdirectory
    company_dir = os.path.join(REVIEWS_DIR, company)
    os.makedirs(company_dir, exist_ok=True)
    
    # Save to JSON file
    filepath = os.path.join(company_dir, f"{tour_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(review_data, f, indent=2, ensure_ascii=False)
    
    print(f"  Saved reviews to {filepath}")

def load_all_tours():
    """Load all tours from CSV files"""
    tours = []
    csv_files = glob.glob('*_with_media.csv')
    
    for csvfile in csv_files:
        try:
            if os.path.exists(csvfile):
                with open(csvfile, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        tours.append({
                            'id': row['id'],
                            'name': row['name'],
                            'company': row['company_name'],
                            'csv_file': csvfile
                        })
        except Exception as e:
            print(f"Warning: Could not load {csvfile}: {e}")
            continue
    
    return tours

def main():
    """Main scraping function"""
    print("=" * 60)
    print("TOUR REVIEW SCRAPER")
    print("=" * 60)
    print()
    
    # Load tours
    tours = load_all_tours()
    print(f"Found {len(tours)} tours to scrape reviews for")
    print()
    
    if not tours:
        print("No tours found! Make sure *_with_media.csv files exist.")
        return
    
    # Initialize driver
    print("Initializing browser...")
    driver = init_driver()
    
    try:
        scraped_count = 0
        skipped_count = 0
        
        for i, tour in enumerate(tours, 1):
            print(f"\n[{i}/{len(tours)}] Processing: {tour['name']} ({tour['company']})")
            
            # Check if reviews already exist
            review_file = os.path.join(REVIEWS_DIR, tour['company'], f"{tour['id']}.json")
            if os.path.exists(review_file):
                print(f"  ⏭️  Reviews already exist, skipping...")
                skipped_count += 1
                continue
            
            # Try TripAdvisor first
            tripadvisor_url = search_tripadvisor_for_tour(driver, tour['name'], tour['company'])
            review_data = None
            
            if tripadvisor_url:
                # Scrape reviews from TripAdvisor
                review_data = scrape_tripadvisor_reviews(driver, tripadvisor_url, max_reviews=20)
                
                if review_data['reviews']:
                    print(f"  ✅ Found {len(review_data['reviews'])} TripAdvisor reviews")
                    save_reviews(tour['company'], tour['id'], review_data)
                    scraped_count += 1
                else:
                    print(f"  ⚠️  No TripAdvisor reviews found, trying Google...")
                    review_data = None
            
            # Fallback to Google if TripAdvisor failed
            if not review_data or not review_data['reviews']:
                print(f"  🔍 Searching Google for reviews...")
                review_data = scrape_google_reviews(driver, tour['name'], tour['company'], max_reviews=20)
                
                if review_data['reviews']:
                    print(f"  ✅ Found {len(review_data['reviews'])} reviews from {review_data['source']}")
                    save_reviews(tour['company'], tour['id'], review_data)
                    scraped_count += 1
                else:
                    print(f"  ⚠️  No reviews found from any source")
                    # Save empty review data so we don't try again
                    save_reviews(tour['company'], tour['id'], {
                        'reviews': [],
                        'overall_rating': 0,
                        'review_count': 0,
                        'source': 'None',
                        'source_url': None
                    })
            
            # Rate limiting
            time.sleep(random.uniform(3, 6))
        
        print("\n" + "=" * 60)
        print(f"SCRAPING COMPLETE")
        print(f"  Tours processed: {len(tours)}")
        print(f"  New reviews scraped: {scraped_count}")
        print(f"  Skipped (already exist): {skipped_count}")
        print("=" * 60)
        
    finally:
        driver.quit()
        print("\nBrowser closed.")

if __name__ == '__main__':
    main()

