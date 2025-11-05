"""
Manual Google Reviews Scraper

Simple approach:
1. Navigates to the page
2. YOU verify reviews are visible
3. YOU press ENTER
4. Script scrapes whatever text is on the page

Works with ANY page structure!
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
import sys
from urllib.parse import quote_plus

REVIEWS_DIR = 'tour_reviews'

def discover_companies(specified_csvs=None):
    """Auto-detect all companies that have tours, optionally filtered by specified CSVs"""
    companies = []
    
    if specified_csvs:
        # Use only the specified CSV files
        csv_files = []
        for csv_file in specified_csvs:
            # Try both cleaned and cleaned_with_media versions
            if os.path.exists(csv_file):
                csv_files.append(csv_file)
            elif os.path.exists(csv_file.replace('_cleaned.csv', '_cleaned_with_media.csv')):
                csv_files.append(csv_file.replace('_cleaned.csv', '_cleaned_with_media.csv'))
            elif os.path.exists(csv_file.replace('.csv', '_with_media.csv')):
                csv_files.append(csv_file.replace('.csv', '_with_media.csv'))
            else:
                print(f"⚠️  Warning: {csv_file} not found, skipping...")
    else:
        # Auto-discover all companies
        csv_files = glob.glob('tours_*_cleaned_with_media.csv')
    
    for csv_file in csv_files:
        # Extract company name from filename
        # "tours_cruisewhitsundays_cleaned_with_media.csv" -> "cruisewhitsundays"
        # "tours_cruisewhitsundays_cleaned.csv" -> "cruisewhitsundays"
        company = csv_file.replace('tours_', '').replace('_cleaned_with_media.csv', '').replace('_cleaned.csv', '').replace('.csv', '')
        
        # Check if it has actual tours
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if len(rows) > 0:  # Has tours
                    companies.append(company)
                    print(f"  ✓ {company}: {len(rows)} tours")
                else:
                    print(f"  ⊘ {company}: 0 tours (skipping)")
        except Exception as e:
            print(f"  ⚠ {company}: Error reading ({e})")
    
    return companies

def init_driver():
    """Initialize browser"""
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    
    driver = uc.Chrome(options=options)
    return driver

def extract_reviews_from_page(driver, page_html):
    """Extract reviews from the current page using multiple methods"""
    reviews = []
    
    soup = BeautifulSoup(page_html, 'html.parser')
    
    # Method 1: Look for review-like text blocks
    # Reviews are usually 50-500 characters
    all_text_elements = soup.find_all(['div', 'span', 'p'])
    
    seen_texts = set()
    
    # UI noise keywords to filter out
    ui_keywords = [
        'delete', 'see more', 'report', 'click here', 'redirected',
        'jump to', 'search box', 'quick settings', 'sign in',
        'past hour', 'past week', 'past month', 'custom range',
        'google policies', 'legal obligations', 'inappropriate content',
        'write a review', 'edit your review', 'local guide',
        'google review summary', 'automatically processed',
        'press/', 'choose what', 'giving feedback'
    ]
    
    for elem in all_text_elements:
        text = elem.get_text(strip=True)
        
        # Filter for review-like text
        if (50 <= len(text) <= 800 and  # Right length
            text not in seen_texts and  # Not duplicate
            not text.startswith('http') and  # Not a URL
            ' ' in text):  # Has spaces (real text)
            
            # Skip if contains too many UI keywords
            text_lower = text.lower()
            if any(keyword in text_lower for keyword in ui_keywords):
                continue
            
            # Skip if too many capital letters (likely UI labels)
            capitals = sum(1 for c in text if c.isupper())
            if capitals > len(text) * 0.3:  # More than 30% capitals
                continue
            
            # Basic quality checks
            words = text.split()
            if len(words) >= 10:  # At least 10 words
                # FILTER: Skip truncated reviews that end with "...more" or similar
                truncation_patterns = [
                    '...more',
                    '… more',
                    '... More',
                    '…More',
                    '...show more',
                    '... read more',
                    '…read more',
                    '(more)',
                    '... (more)',
                ]
                
                # Check if review ends with any truncation pattern
                is_truncated = any(text.endswith(pattern) for pattern in truncation_patterns)
                
                # Also check for common truncation in the middle followed by "more"
                if not is_truncated:
                    is_truncated = bool(re.search(r'\.\.\.\s*more\s*$', text, re.I))
                
                if is_truncated:
                    # Skip this truncated review
                    continue
                
                seen_texts.add(text)
                
                # Try to extract rating from nearby star emojis
                # Look for filled stars (★ ⭐) vs empty stars (☆)
                parent_text = elem.parent.get_text() if elem.parent else text
                filled_stars = parent_text.count('★') + parent_text.count('⭐')
                
                # Default to 5 if we can't find stars, or use the count
                rating = float(min(filled_stars, 5)) if filled_stars > 0 else 5.0
                
                review = {
                    'text': text,
                    'author': 'Customer',  # Default
                    'rating': rating
                }
                
                reviews.append(review)
                
                if len(reviews) >= 20:
                    break
    
    return reviews

def scrape_company_reviews(driver, company_display_name):
    """Scrape reviews for a company"""
    try:
        # Search Google
        search_query = f"{company_display_name} Airlie Beach reviews"
        search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
        
        print(f"\n  🔍 Searching: {search_query}")
        driver.get(search_url)
        time.sleep(4)
        
        # Extract rating from search page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text = soup.get_text()
        
        overall_rating = 0
        review_count = 0
        
        # Try multiple patterns to find rating
        patterns = [
            r'[54321]{5}(\d\.\d)([\d,]+)\s*reviews?',  # "543214.41,923 reviews" (Google's format)
            r'(\d\.\d)\s*[★⭐]+\s*([\d,]+)\s+(?:Google\s+)?reviews?',  # "4.4★1,923 reviews"
            r'(\d\.\d)\s*[★⭐]+.*?([\d,]+)\s+reviews?',  # "4.4★...1,923 reviews"
            r'(\d\.\d)\s+stars?.*?([\d,]+)\s+reviews?',  # "4.4 stars 1,923 reviews"
            r'Rating:\s*(\d\.\d).*?([\d,]+)\s+reviews?',  # "Rating: 4.4...1,923 reviews"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I | re.DOTALL)
            if match:
                overall_rating = float(match.group(1))
                review_count = int(match.group(2).replace(',', ''))
                print(f"  ✅ Rating: {overall_rating}★ ({review_count:,} reviews)")
                break
        
        if overall_rating == 0:
            print(f"  ⚠️  Could not extract rating")
            # Save debug file to troubleshoot
            with open(f'debug_rating_{company_display_name.replace(" ", "_")}.txt', 'w', encoding='utf-8') as f:
                f.write(text[:5000])  # First 5000 chars
        
        # Try to click Reviews
        print(f"\n  🖱️  Attempting to click 'Reviews'...")
        print(f"  ⏸️  ⏸️  ⏸️  MANUAL STEP ⏸️  ⏸️  ⏸️")
        print(f"  ")
        print(f"  👉 In the browser window:")
        print(f"     1. Click 'Reviews' if you see it")
        print(f"     2. Wait for reviews to load")
        print(f"     3. Scroll down to see more reviews")
        print(f"     4. When you can see 10-20 reviews, come back here")
        print(f"  ")
        input(f"  Press ENTER when reviews are visible on screen: ")
        
        print(f"\n  ✅ Scraping visible content...")
        
        # Get whatever is on the page now
        page_html = driver.page_source
        
        # Save for debugging
        with open(f'debug_reviews_{company_display_name.replace(" ", "_")}.html', 'w', encoding='utf-8') as f:
            f.write(page_html)
        
        # Extract reviews
        reviews = extract_reviews_from_page(driver, page_html)
        
        print(f"  📝 Extracted {len(reviews)} text blocks that look like reviews")
        
        # Show first review as sample
        if reviews:
            print(f"\n  📄 Sample review:")
            print(f"     \"{reviews[0]['text'][:100]}...\"")
        
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
    """Load tour IDs from the best available CSV file"""
    tour_ids = []
    
    # Prefer cleaned_with_media, then cleaned, then original
    csv_candidates = [
        f'tours_{company}_cleaned_with_media.csv',
        f'tours_{company}_cleaned.csv',
        f'tours_{company}.csv',
    ]
    
    for csvfile in csv_candidates:
        if os.path.exists(csvfile):
            try:
                with open(csvfile, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('id'):
                            tour_ids.append(row['id'])
                return tour_ids  # Return after first successful read
            except:
                continue
    
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
        'explorewhitsundays': 'Explore Whitsundays',
        'iconicwhitsunday': 'Iconic Whitsunday',
        'airliebeachdiving': 'Airlie Beach Diving',
        'crocodilesafari': 'Crocodile Safari',
        'helireef': 'HeliReef',
        'oceandynamics': 'Ocean Dynamics',
        'pioneeradventures': 'Pioneer Adventures',
        'saltydog': 'Salty Dog',
        'sundownercruises': 'Sundowner Cruises',
        'whitsunday-catamarans': 'Whitsunday Catamarans',
        'whitsundaydiveadventures': 'Whitsunday Dive Adventures',
        'whitsundaystanduppaddle': 'Whitsunday Stand Up Paddle',
        'whitsundaybullet': 'Whitsunday Bullet',
        'matadorwhitsundays': 'Matador Whitsundays',
        'sailing-whitsundays': 'Sailing Whitsundays',
    }
    return names.get(company, company.replace('_', ' ').replace('-', ' ').title())

def main():
    print("=" * 70)
    print("MANUAL GOOGLE REVIEWS SCRAPER")
    print("=" * 70)
    print("\n💡 YOU control when to scrape - manual and reliable!")
    print()
    print("How it works:")
    print("  1. Script opens browser and searches")
    print("  2. YOU click 'Reviews' and scroll to see reviews")
    print("  3. YOU press ENTER when ready")
    print("  4. Script scrapes whatever is visible")
    print()
    
    # Check for command-line arguments (CSV files)
    specified_csvs = None
    if len(sys.argv) > 1:
        specified_csvs = sys.argv[1:]
        print(f"📋 You specified {len(specified_csvs)} CSV file(s) to process:")
        for csv in specified_csvs:
            print(f"   - {csv}")
        print()
    
    # Discover companies with tours (filtered by specified CSVs if provided)
    print("🔍 Discovering companies with tours...")
    companies_to_scrape = discover_companies(specified_csvs)
    print(f"\n📊 Found {len(companies_to_scrape)} companies with tours\n")
    
    if not companies_to_scrape:
        print("❌ No companies found with tours!")
        return
    
    input("Press ENTER to start scraping...")
    
    driver = init_driver()
    
    try:
        success_count = 0
        
        for company in companies_to_scrape:
            print(f"\n{'='*70}")
            print(f"📍 {get_company_display_name(company)}")
            print(f"{'='*70}")
            
            tour_ids = load_tour_ids_for_company(company)
            if not tour_ids:
                print(f"  ⚠️  No tours found, skipping")
                continue
            
            print(f"  📊 Tours: {len(tour_ids)}")
            
            review_data = scrape_company_reviews(driver, get_company_display_name(company))
            
            if review_data and (review_data['overall_rating'] > 0 or review_data['reviews']):
                print(f"\n  💾 Saving to {len(tour_ids)} tour files...")
                print(f"     Rating: {review_data['overall_rating']}★")
                print(f"     Reviews: {len(review_data['reviews'])}")
                
                for tour_id in tour_ids:
                    save_reviews(company, tour_id, review_data)
                
                print(f"  ✅ Saved!")
                success_count += 1
            else:
                print(f"  ❌ No data collected")
            
            # Ask before continuing
            if company != companies_to_scrape[-1]:
                print(f"\n  ⏭️  Ready for next company?")
                input("  Press ENTER to continue...")
        
        print(f"\n{'='*70}")
        print(f"✅ COMPLETE: {success_count}/{len(companies_to_scrape)} companies")
        print(f"{'='*70}")
        
    finally:
        input("\nPress ENTER to close browser...")
        driver.quit()

if __name__ == '__main__':
    main()

