"""
Manual Review URL Override

If automated scraping fails for certain companies, you can manually
add their review page URLs here and this will scrape them directly.

Usage:
    1. Manually search Google/TripAdvisor for the tour company
    2. Find their review page URL
    3. Add it to MANUAL_REVIEW_URLS below
    4. Run: python add_manual_review_urls.py
"""

import undetected_chromedriver as uc
from scrape_reviews import scrape_tripadvisor_reviews, scrape_google_maps_reviews, init_driver, save_reviews
import time
import random

# ==========================================
# ADD YOUR MANUAL URLS HERE
# ==========================================

MANUAL_REVIEW_URLS = {
    # Example format:
    # 'company_name': {
    #     'url': 'https://www.tripadvisor.com/...',
    #     'type': 'tripadvisor'  # or 'google_maps'
    # },
    
    'cruisewhitsundays': {
        'url': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427261-Reviews-Cruise_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html',
        'type': 'tripadvisor',
        'tour_ids': ['camira_sailing_adventure', 'camira_sunset_sail', 'reefsleep', 'reefsuites', 'reef_explorer']
    },
    
    # Add more companies as needed:
    # 'airliebeachdiving': {
    #     'url': 'https://...',
    #     'type': 'tripadvisor',
    #     'tour_ids': ['tour_id_1', 'tour_id_2']
    # },
}

# ==========================================

def scrape_manual_urls():
    """Scrape reviews from manually provided URLs"""
    print("=" * 70)
    print("MANUAL REVIEW URL SCRAPER")
    print("=" * 70)
    print()
    
    if not MANUAL_REVIEW_URLS:
        print("❌ No manual URLs configured!")
        print("   Edit add_manual_review_urls.py and add URLs to MANUAL_REVIEW_URLS")
        return
    
    driver = init_driver()
    
    try:
        for company, config in MANUAL_REVIEW_URLS.items():
            print(f"\n{'='*70}")
            print(f"Processing: {company}")
            print(f"{'='*70}")
            
            url = config['url']
            url_type = config['type']
            tour_ids = config.get('tour_ids', [])
            
            print(f"URL: {url}")
            print(f"Type: {url_type}")
            print(f"Will apply to {len(tour_ids)} tours")
            print()
            
            # Scrape based on type
            review_data = None
            
            if url_type == 'tripadvisor':
                print("Scraping TripAdvisor...")
                review_data = scrape_tripadvisor_reviews(driver, url, max_reviews=20)
            elif url_type == 'google_maps':
                print("Scraping Google Maps...")
                review_data = scrape_google_maps_reviews(driver, url, max_reviews=20)
            else:
                print(f"❌ Unknown type: {url_type}")
                continue
            
            # Check if we got reviews
            if review_data and review_data.get('reviews'):
                print(f"✅ Found {len(review_data['reviews'])} reviews!")
                print(f"   Rating: {review_data.get('overall_rating', 0)}")
                print(f"   Total count: {review_data.get('review_count', 0)}")
                
                # Save to all specified tour IDs
                if tour_ids:
                    print(f"\nSaving to {len(tour_ids)} tour files...")
                    for tour_id in tour_ids:
                        save_reviews(company, tour_id, review_data)
                        print(f"   ✅ Saved: {company}/{tour_id}.json")
                else:
                    print("⚠️  No tour IDs specified - reviews not saved")
            else:
                print(f"❌ No reviews found at this URL")
            
            # Rate limiting
            time.sleep(random.uniform(3, 5))
        
        print(f"\n{'='*70}")
        print("✅ MANUAL SCRAPING COMPLETE")
        print(f"{'='*70}")
        
    finally:
        driver.quit()

if __name__ == '__main__':
    print("\n🔧 MANUAL REVIEW URL SCRAPER")
    print()
    print("This will scrape reviews from manually configured URLs")
    print("and apply them to specified tours.")
    print()
    
    scrape_manual_urls()



