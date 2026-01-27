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
                print(f"  [!] Warning: {csv_file} not found, skipping...")
    else:
        # Auto-discover all companies
        csv_files = glob.glob('tours_*_cleaned_with_media.csv')
    
    for csv_file in csv_files:
        # Extract company name from filename using slicing (not replace!)
        # "tours_cruisewhitsundays_cleaned_with_media.csv" -> "cruisewhitsundays"
        # Company names like "airlieadventuretours" contain "tours" so .replace() breaks them
        prefix = 'tours_'
        if csv_file.startswith(prefix):
            rest = csv_file[len(prefix):]
            if rest.endswith('_cleaned_with_media.csv'):
                company = rest[:-len('_cleaned_with_media.csv')]
            elif rest.endswith('_cleaned.csv'):
                company = rest[:-len('_cleaned.csv')]
            elif rest.endswith('.csv'):
                company = rest[:-len('.csv')]
            else:
                company = rest
        else:
            company = csv_file
        
        # Check if it has actual tours
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if len(rows) > 0:  # Has tours
                    companies.append(company)
                    print(f"  [OK] {company}: {len(rows)} tours")
                else:
                    print(f"  ⊘ {company}: 0 tours (skipping)")
        except Exception as e:
            print(f"  [!] {company}: Error reading ({e})")
    
    return companies

def init_driver():
    """Initialize browser"""
    options = uc.ChromeOptions()
    options.add_argument('--start-maximized')
    
    driver = uc.Chrome(options=options)
    return driver

def safe_print(msg):
    """Print with UTF-8 encoding for Windows compatibility"""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Strip emojis for Windows
        import re
        clean_msg = re.sub(r'[^\x00-\x7F]+', '', msg)
        print(clean_msg)

def is_owner_response(text):
    """Check if text is an owner/business response, not a customer review"""
    text_lower = text.lower()
    
    # Owner response indicators at the START of text
    owner_start_patterns = [
        '(owner)',
        'owner)',
        'response from',
        'thank you for',
        'thanks for',
        'thank you so much',
        'thanks so much',
        "we're thrilled",
        "we're delighted",
        "we're so glad",
        "we're so happy",
        "we are thrilled",
        "we are delighted",
        "we truly appreciate",
        "we really appreciate",
        "we appreciate",
        "we hope to see you",
        "we hope to welcome",
        "we can't wait to",
        "we look forward",
        "hi there,",
        "hello,",
        "dear guest",
    ]
    
    # Check if text starts with owner patterns
    for pattern in owner_start_patterns:
        if text_lower.startswith(pattern):
            return True
    
    # Owner response patterns ANYWHERE in text
    owner_anywhere_patterns = [
        '(owner)',
        'owner)',
        ' (owner',
        'tours (owner',
        'whitsundays (owner',
        'adventures (owner',
        'sailing (owner',
        'cruises (owner',
        'we\'re stoked',
        'we\'ll be sure to pass',
        'the team will be',
        'our team will be',
        'thanks again for',
        'thank you again for',
        'we can\'t wait to welcome you back',
        'hope to welcome you back',
        'hope to see you again',
        'we hope you\'ll',
        'will be stoked to hear',
        'will be delighted to hear',
        'will be over the moon',
    ]
    
    for pattern in owner_anywhere_patterns:
        if pattern in text_lower:
            return True
    
    # Check for company name followed by common owner response starters
    # Pattern: "[Company Name] (owner)..." or response starting with we're/we are
    if re.search(r'^[A-Z][a-zA-Z\s]+\s*\(owner\)', text):
        return True
    
    # Check for timestamps typical of owner responses (e.g., "2 weeks ago" at start)
    if re.match(r'^(\d+\s+(days?|weeks?|months?|years?)\s+ago)', text_lower):
        return True
    
    # If it starts with "we" and sounds like a business response
    if text_lower.startswith('we ') or text_lower.startswith("we'"):
        business_response_phrases = [
            'we appreciate', 'we are so', 'we are glad', 'we are happy',
            'we\'re glad', 'we\'re happy', 'we\'re so', 'we\'re thrilled',
            'we hope', 'we look forward', 'we truly', 'we really'
        ]
        if any(text_lower.startswith(phrase) for phrase in business_response_phrases):
            return True
    
    return False

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
        'press/', 'choose what', 'giving feedback', 'sort by',
        'most relevant', 'newest first', 'highest rating', 'lowest rating',
        'all reviews', 'filter by', 'translate review', 'original',
        'photo', 'photos', 'helpful', 'share', 'flag as inappropriate',
        'google llc', 'privacy', 'terms', 'about these results',
        'response from the owner', 'owner response'
    ]
    
    # Keywords that suggest this is random website text, not a review
    random_text_keywords = [
        'book now', 'add to cart', 'checkout', 'subscribe',
        'newsletter', 'contact us', 'about us', 'our team',
        'privacy policy', 'terms of service', 'cookie',
        'copyright', 'all rights reserved', 'powered by',
        'navigation', 'menu', 'home', 'services',
        'follow us', 'social media', 'facebook', 'instagram', 'twitter',
        'phone:', 'email:', 'address:', 'abn:', 'acn:',
        'frequently asked', 'faq', 'cancellation policy',
        'booking conditions', 'terms and conditions'
    ]
    
    for elem in all_text_elements:
        text = elem.get_text(strip=True)
        
        # Filter for review-like text
        if (50 <= len(text) <= 800 and  # Right length
            text not in seen_texts and  # Not duplicate
            not text.startswith('http') and  # Not a URL
            ' ' in text):  # Has spaces (real text)
            
            text_lower = text.lower()
            
            # Skip if contains UI keywords
            if any(keyword in text_lower for keyword in ui_keywords):
                continue
            
            # Skip if contains random website text keywords
            if any(keyword in text_lower for keyword in random_text_keywords):
                continue
            
            # Skip if too many capital letters (likely UI labels)
            capitals = sum(1 for c in text if c.isupper())
            if capitals > len(text) * 0.3:  # More than 30% capitals
                continue
            
            # IMPORTANT: Skip owner/business responses
            if is_owner_response(text):
                print(f"  [SKIP] Owner response: \"{text[:50]}...\"")
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
                
                # Additional check: real reviews typically have first-person language
                # or describe experiences
                review_indicators = [
                    ' i ', ' my ', ' we ', ' our ', ' me ',
                    'had a', 'was a', 'such a', 'what a',
                    'experience', 'trip', 'tour', 'day', 'time',
                    'amazing', 'great', 'fantastic', 'awesome', 'wonderful',
                    'recommend', 'loved', 'enjoyed', 'beautiful', 'stunning',
                    'staff', 'crew', 'guide', 'instructor', 'captain',
                    'boat', 'snorkel', 'dive', 'beach', 'reef', 'island'
                ]
                
                has_review_indicator = any(ind in text_lower for ind in review_indicators)
                
                if not has_review_indicator:
                    # Be more strict - skip if no review-like language
                    continue
                
                seen_texts.add(text)
                
                # Try to extract rating from nearby star emojis
                # Look for filled stars (★ ⭐) vs empty stars (☆)
                parent_text = elem.parent.get_text() if elem.parent else text
                filled_stars = parent_text.count('★') + parent_text.count('⭐')
                
                # Default to 5 if we can't find stars, or use the count
                rating = float(min(filled_stars, 5)) if filled_stars > 0 else 5.0
                
                # Try to extract author name from nearby elements
                author = 'Customer'
                parent = elem.parent
                if parent:
                    # Look for name-like text nearby (short, capitalized)
                    siblings = parent.find_all(['span', 'div'], limit=5)
                    for sib in siblings:
                        sib_text = sib.get_text(strip=True)
                        # Author names are typically 2-4 words, title case
                        if (5 <= len(sib_text) <= 40 and 
                            sib_text.istitle() and 
                            ' ' in sib_text and
                            not any(kw in sib_text.lower() for kw in ['review', 'star', 'ago', 'google'])):
                            author = sib_text
                            break
                
                review = {
                    'text': text,
                    'author': author,
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
        
        print(f"\n  Searching: {search_query}")
        driver.get(search_url)
        time.sleep(4)
        
        # Extract rating from search page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text = soup.get_text()
        
        overall_rating = 0
        review_count = 0
        
        # Try multiple patterns to find rating
        patterns = [
            # Google's compact format: "543214.41,923 reviews"
            r'[54321]{5}(\d\.\d)([\d,]+)\s*reviews?',
            # Standard: "4.4★ 1,923 reviews" or "4.4 ★ 1,923 Google reviews"
            r'(\d\.\d)\s*[★⭐]+\s*([\d,]+)\s+(?:Google\s+)?reviews?',
            # With dots between: "4.4★...1,923 reviews"
            r'(\d\.\d)\s*[★⭐]+.*?([\d,]+)\s+reviews?',
            # Text stars: "4.4 stars 1,923 reviews"
            r'(\d\.\d)\s+stars?.*?([\d,]+)\s+reviews?',
            # With "Rating:" prefix
            r'Rating:\s*(\d\.\d).*?([\d,]+)\s+reviews?',
            # Just rating and reviews nearby (looser): "4.4" ... "1,923 reviews"
            r'(\d\.\d)\s*\(?([\d,]+)\s+reviews?\)?',
            # Rating in parentheses: "(4.4)" with reviews
            r'\((\d\.\d)\).*?([\d,]+)\s+reviews?',
            # Google Maps style: "4.4 (1,923)"
            r'(\d\.\d)\s*\(([\d,]+)\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.I | re.DOTALL)
            if match:
                try:
                    rating_val = float(match.group(1))
                    count_val = int(match.group(2).replace(',', ''))
                    # Sanity check - rating should be 1-5, count should be reasonable
                    if 1.0 <= rating_val <= 5.0 and count_val > 0:
                        overall_rating = rating_val
                        review_count = count_val
                        print(f"  [OK] Rating: {overall_rating} ({review_count:,} reviews)")
                        break
                except (ValueError, IndexError):
                    continue
        
        # Also try to find just the rating if we didn't get a count
        if overall_rating == 0:
            rating_only_patterns = [
                r'(\d\.\d)\s*out of 5',  # "4.4 out of 5"
                r'(\d\.\d)\s*[★⭐]',  # "4.4★"
                r'[★⭐]+\s*(\d\.\d)',  # "★★★★☆ 4.4"
            ]
            for pattern in rating_only_patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    try:
                        rating_val = float(match.group(1))
                        if 1.0 <= rating_val <= 5.0:
                            overall_rating = rating_val
                            print(f"  [OK] Rating found: {overall_rating} (count unknown)")
                break
                    except (ValueError, IndexError):
                        continue
        
        if overall_rating == 0:
            print(f"  [!] Could not auto-detect rating")
            # Ask user to manually enter the rating they see on screen
            print(f"  ")
            print(f"  Can you see the rating on the Google page?")
            user_rating = input(f"  Enter rating (e.g. 4.7) or press ENTER to skip: ").strip()
            if user_rating:
                try:
                    overall_rating = float(user_rating)
                    print(f"  [OK] Using manual rating: {overall_rating}")
                except ValueError:
                    print(f"  [!] Invalid rating, skipping")
            
            user_count = input(f"  Enter review count (e.g. 1234) or press ENTER to skip: ").strip()
            if user_count:
                try:
                    review_count = int(user_count.replace(',', ''))
                    print(f"  [OK] Using manual count: {review_count}")
                except ValueError:
                    print(f"  [!] Invalid count, skipping")
        
        # Try to click Reviews
        print(f"\n  Attempting to click 'Reviews'...")
        print(f"  === MANUAL STEP ===")
        print(f"  ")
        print(f"  In the browser window:")
        print(f"     1. Click 'Reviews' if you see it")
        print(f"     2. Wait for reviews to load")
        print(f"     3. Scroll down to see more reviews")
        print(f"     4. When you can see 10-20 reviews, come back here")
        print(f"  ")
        input(f"  Press ENTER when reviews are visible on screen: ")
        
        print(f"\n  Scraping visible content...")
        
        # Get whatever is on the page now
        page_html = driver.page_source
        
        # Save for debugging
        with open(f'debug_reviews_{company_display_name.replace(" ", "_")}.html', 'w', encoding='utf-8') as f:
            f.write(page_html)
        
        # Extract reviews
        reviews = extract_reviews_from_page(driver, page_html)
        
        print(f"  Extracted {len(reviews)} text blocks that look like reviews")
        
        # Show first review as sample
        if reviews:
            print(f"\n  Sample review:")
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
        print(f"  [ERROR] {e}")
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
    print("\nYOU control when to scrape - manual and reliable!")
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
        print(f"You specified {len(specified_csvs)} CSV file(s) to process:")
        for csv in specified_csvs:
            print(f"   - {csv}")
        print()
    
    # Discover companies with tours (filtered by specified CSVs if provided)
    print("Discovering companies with tours...")
    companies_to_scrape = discover_companies(specified_csvs)
    print(f"\nFound {len(companies_to_scrape)} companies with tours\n")
    
    if not companies_to_scrape:
        print("[!] No companies found with tours!")
        return
    
    input("Press ENTER to start scraping...")
    
    driver = init_driver()
    
    try:
        success_count = 0
        
        for i, company in enumerate(companies_to_scrape):
            try:
            print(f"\n{'='*70}")
                print(f">>> [{i+1}/{len(companies_to_scrape)}] {get_company_display_name(company)}")
            print(f"{'='*70}")
            
            tour_ids = load_tour_ids_for_company(company)
            if not tour_ids:
                    print(f"  [!] No tours found, skipping")
                continue
            
                print(f"  Tours: {len(tour_ids)}")
            
            review_data = scrape_company_reviews(driver, get_company_display_name(company))
            
            if review_data and (review_data['overall_rating'] > 0 or review_data['reviews']):
                    print(f"\n  Saving to {len(tour_ids)} tour files...")
                    print(f"     Rating: {review_data['overall_rating']}")
                print(f"     Reviews: {len(review_data['reviews'])}")
                
                for tour_id in tour_ids:
                    save_reviews(company, tour_id, review_data)
                
                    print(f"  [OK] Saved!")
                success_count += 1
            else:
                    print(f"  [!] No data collected")
                
            except Exception as e:
                print(f"\n  [ERROR] Failed on {company}: {e}")
                import traceback
                traceback.print_exc()
                print(f"  Continuing to next company...")
            
            # Ask before continuing
            if i < len(companies_to_scrape) - 1:
                print(f"\n  Ready for next company?")
                input("  Press ENTER to continue...")
        
        print(f"\n{'='*70}")
        print(f"COMPLETE: {success_count}/{len(companies_to_scrape)} companies")
        print(f"{'='*70}")
        
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("\nPress ENTER to close browser...")
        driver.quit()

if __name__ == '__main__':
    main()

