"""
Debug script to test Cruise Whitsundays review scraping

This will show exactly what's happening when we try to scrape
Cruise Whitsundays reviews.
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import quote_plus

def init_driver():
    """Initialize browser"""
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = uc.Chrome(options=options)
    return driver

def test_tripadvisor():
    """Test TripAdvisor URL for Cruise Whitsundays"""
    print("=" * 70)
    print("TEST 1: TripAdvisor Direct URL")
    print("=" * 70)
    
    url = "https://www.tripadvisor.com/Attraction_Review-g255068-d2427261-Reviews-Cruise_Whitsundays-Airlie_Beach_Whitsunday_Islands_Queensland.html"
    
    driver = init_driver()
    
    try:
        print(f"\nLoading: {url}")
        driver.get(url)
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Check if page loaded
        print("\n1. Page Title:", driver.title)
        
        # Look for overall rating
        print("\n2. Looking for overall rating...")
        rating_elem = soup.find('div', class_=re.compile(r'.*rating.*', re.I))
        if rating_elem:
            print(f"   Found rating element: {rating_elem.get_text()[:50]}")
        else:
            print("   ❌ No rating element found")
        
        # Look for review count
        print("\n3. Looking for review count...")
        count_elem = soup.find(text=re.compile(r'\d+\s+reviews?', re.I))
        if count_elem:
            print(f"   Found review count: {count_elem}")
        else:
            print("   ❌ No review count found")
        
        # Look for review containers
        print("\n4. Looking for review containers...")
        review_containers = soup.find_all('div', class_=re.compile(r'review-container|reviewSelector', re.I))
        print(f"   Found {len(review_containers)} review containers (method 1)")
        
        review_containers2 = soup.find_all('div', attrs={'data-automation': 'reviewCard'})
        print(f"   Found {len(review_containers2)} review containers (method 2)")
        
        review_containers3 = soup.find_all('div', class_=re.compile(r'.*review.*card.*', re.I))
        print(f"   Found {len(review_containers3)} review containers (method 3)")
        
        # Show first review if found
        if review_containers or review_containers2 or review_containers3:
            all_reviews = review_containers + review_containers2 + review_containers3
            if all_reviews:
                print("\n5. First review sample:")
                first = all_reviews[0]
                print(f"   {first.get_text()[:200]}...")
        
        # Save HTML for inspection
        with open('debug_tripadvisor.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("\n6. Saved page HTML to: debug_tripadvisor.html")
        
    finally:
        driver.quit()
    
    print("\n" + "=" * 70)

def test_google_search():
    """Test Google search for Cruise Whitsundays"""
    print("\n" + "=" * 70)
    print("TEST 2: Google Search")
    print("=" * 70)
    
    search_query = "Cruise Whitsundays Airlie Beach reviews"
    search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
    
    driver = init_driver()
    
    try:
        print(f"\nSearching Google: {search_query}")
        driver.get(search_url)
        time.sleep(4)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find all links
        print("\n1. Looking for review-related links...")
        links = soup.find_all('a', href=True)
        
        potential_links = []
        for link in links:
            href = link.get('href', '')
            if any(domain in href.lower() for domain in ['google.com/maps', 'tripadvisor.com', 'facebook.com']):
                if '/url?q=' in href:
                    from urllib.parse import unquote
                    actual_url = href.split('/url?q=')[1].split('&')[0]
                    clean_url = unquote(actual_url)
                else:
                    clean_url = href
                
                if clean_url not in potential_links and clean_url.startswith('http'):
                    potential_links.append(clean_url)
        
        print(f"\n2. Found {len(potential_links)} potential review sources:")
        for i, url in enumerate(potential_links[:5], 1):
            print(f"   {i}. {url[:80]}...")
        
        # Save HTML
        with open('debug_google.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("\n3. Saved page HTML to: debug_google.html")
        
    finally:
        driver.quit()
    
    print("\n" + "=" * 70)

def test_specific_tour():
    """Test specific tour: Camira Sailing Adventure"""
    print("\n" + "=" * 70)
    print("TEST 3: Specific Tour Search")
    print("=" * 70)
    
    search_query = "Camira Sailing Adventure Cruise Whitsundays reviews"
    search_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
    
    driver = init_driver()
    
    try:
        print(f"\nSearching Google: {search_query}")
        driver.get(search_url)
        time.sleep(4)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find links
        links = soup.find_all('a', href=True)
        
        potential_links = []
        for link in links:
            href = link.get('href', '')
            if any(domain in href.lower() for domain in ['google.com/maps', 'tripadvisor.com', 'facebook.com', 'cruisewhitsundays.com']):
                if '/url?q=' in href:
                    from urllib.parse import unquote
                    actual_url = href.split('/url?q=')[1].split('&')[0]
                    clean_url = unquote(actual_url)
                else:
                    clean_url = href
                
                if clean_url not in potential_links and clean_url.startswith('http'):
                    potential_links.append(clean_url)
        
        print(f"\nFound {len(potential_links)} potential sources:")
        for i, url in enumerate(potential_links[:5], 1):
            print(f"   {i}. {url}")
        
    finally:
        driver.quit()
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    print("\n🔍 DEBUGGING CRUISE WHITSUNDAYS REVIEW SCRAPING")
    print("=" * 70)
    print("\nThis will test 3 different approaches to find reviews...")
    print("\n")
    
    # Test 1: Direct TripAdvisor URL
    test_tripadvisor()
    
    # Test 2: Google search for company
    test_google_search()
    
    # Test 3: Google search for specific tour
    test_specific_tour()
    
    print("\n" + "=" * 70)
    print("✅ DEBUG COMPLETE")
    print("=" * 70)
    print("\nCheck the output above and the saved HTML files:")
    print("  - debug_tripadvisor.html")
    print("  - debug_google.html")
    print("\nThis will show what's being found (or not found).")
    print("=" * 70)



