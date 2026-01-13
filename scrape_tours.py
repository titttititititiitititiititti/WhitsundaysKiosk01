"""
Simplified scrape_tours.py

Paste your tour links in the TOUR_LINKS list below. The script will visit each link, extract tour info, and append/update the relevant CSV. No crawling, subpages, or image downloading.

Usage:
    python scrape_tours.py
"""
import requests
from bs4 import BeautifulSoup
import re
import csv
import os
import pandas as pd
from urllib.parse import urlparse
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import hashlib
import json

# Import HTML cleaner to reduce content size before saving
from smart_html_cleaner import clean_html_intelligently

# === Paste your tour links here ===
TOUR_LINKS = [ 
 "https://jetskitour.com.au/tour/airlie-adventure/"
 "https://jetskitour.com.au/tour/two-island-safari/"
 "https://jetskitour.com.au/tour/ultimate-island-trek/"
 "https://skyone.com.au/airlie-beach/#bookings" ]

    
# =================================

# === Paste your tour homepages here (fallback) ===
TOUR_HOME_PAGES = [


    # "https://oceanrafting.com.au"
    # "https://redcatadventures.com.au"
]
# =====================================

def load_homepages_from_file(path: str = 'tour_company_homepages.txt'):
    homepages = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if not url:
                        continue
                    if not url.startswith('http'):
                        continue
                    homepages.append(url)
        except Exception as e:
            print(f"Warning: Unable to read {path}: {e}")
    return list(dict.fromkeys(homepages))  # dedupe, keep order

def normalize_homepages_list(lst):
    # If user accidentally concatenated multiple literals into one string, split them
    normalized = []
    for item in lst:
        if not isinstance(item, str):
            continue
        if item.count('http') > 1:
            # Split at each http/https boundary (handles no separators)
            parts = re.split(r'(?=https?://)', item)
            for p in parts:
                u = p.strip().strip('\"\' \,)')
                if u.startswith('http'):
                    normalized.append(u)
        else:
            normalized.append(item)
    # Remove empties and dedupe
    normalized = [u.strip() for u in normalized if u and u.strip().startswith('http')]
    return list(dict.fromkeys(normalized))

# Configurable keywords for tour link discovery
TOUR_LINK_KEYWORDS = [
    'tour', 'experience', 'adventure', 'cruise', 'activity', 'excursion', 'package',
    'safari', 'charter', 'trek', 'hike', 'island', 'islands', 'sailing', 'snorkel',
    'dive', 'diving', 'sightseeing', 'expedition', 'explore', 'trip', 'daytrip', 'boat',
    'fishing', 'flight', 'scenic', 'kayak', 'canoe', 'paddle', 'eco', 'wildlife', 'nature'
]
# Conservative keywords to exclude (non-tour pages)
EXCLUDE_LINK_KEYWORDS = [
    'contact', 'about', 'faq', 'login', 'terms', 'privacy', 'cart', 'checkout', 'account', 'blog', 'news', 'gift',
    'gallery', 'video', 'compare', 'location', 'fleet', 'media', 'story', 'weather', 'walk', 'anchorages', 'offset', 'cabin',
    'accommodation', 'hotel', 'offers', 'deals', 'search', 'menu', 'safety', 'environment', 'accessibility', 'acknowledgement',
    'how-to', 'get-to', 'press', 'events', 'calendar', 'newsletter', 'subscribe', 'unsubscribe', 'sitemap', 'map', 'jobs', 'careers', 'employment', 'partners', 'sponsor', 'testimonials', 'reviews', 'rating', 'award', 'history', 'heritage', 'tradition', 'culture', 'community', 'support', 'help', 'info', 'information', 'resources', 'downloads', 'download', 'pdf', 'doc', 'docx', 'zip', 'disclaimer', 'copyright', 'legal', 'imprint', 'impressum', 'cookie', 'cookies', 'gdpr', 'ccpa'
]
# Max number of links per homepage (set to None for unlimited)
MAX_LINKS_PER_HOMEPAGE = 20

CSV_COLUMNS = [
    'id', 'name', 'company_name', 'summary', 'description', 'duration',
    'departure_location', 'departure_times', 'price_adult', 'price_child',
    'includes', 'highlights', 'keywords', 'duration_hours', 'link_booking',
    'link_more_info', 'phone', 'image_url', 'image_urls', 'commission_rate', 'active',
    'price_source_url', 'price_tiers', 'raw_text', 'raw_html'
]

# Helper to clean text
clean = lambda s: re.sub(r'\s+', ' ', s).strip() if s else ''

def extract_company_name(url):
    netloc = urlparse(url).netloc
    parts = netloc.split('.')
    if len(parts) >= 3 and parts[-2] in {'com', 'org', 'net'} and parts[-1] == 'au':
        return parts[-3]
    return parts[-2]

def fetch_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def extract_all_price_texts(soup):
    price_texts = []
    for el in soup.find_all(text=True):
        if '$' in el:
            price_texts.append(el.strip())
    return price_texts

def extract_json_ld_data(soup):
    """Extract structured data from JSON-LD scripts"""
    structured_data = {}
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(script.string)
            # Handle both single objects and arrays
            if isinstance(data, list):
                data = data[0] if data else {}
            
            # Check if it's a relevant type
            schema_type = data.get('@type', '')
            if schema_type in ['Product', 'TourPackage', 'Event', 'Service', 'Offer']:
                # Extract name
                if data.get('name'):
                    structured_data['name'] = data['name']
                
                # Extract description
                if data.get('description'):
                    structured_data['description'] = data['description']
                
                # Extract price from offers
                offers = data.get('offers', {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                
                if offers.get('price'):
                    structured_data['price'] = str(offers['price'])
                elif offers.get('lowPrice'):
                    structured_data['price'] = str(offers['lowPrice'])
                
                # Extract duration
                if data.get('duration'):
                    structured_data['duration'] = data['duration']
                
                print(f"[JSON-LD] Found structured data: {list(structured_data.keys())}")
                return structured_data
        except Exception as e:
            continue
    
    return structured_data

def extract_duration_and_times(text):
    """Extract duration and departure times from text"""
    duration = ''
    times = []
    
    # Duration patterns
    duration_patterns = [
        (r'(\d+)\s*(?:hour|hr|hours|hrs)', 'hours'),
        (r'(\d+)\s*(?:day|days)', 'days'),
        (r'(half[- ]day|full[- ]day|all\s+day)', 'literal'),
        (r'(\d+)\s*(?:night|nights)', 'nights'),
    ]
    
    for pattern, unit in duration_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if unit == 'literal':
                duration = match.group(1)
            elif unit == 'hours':
                duration = f"{match.group(1)} Hours"
            elif unit == 'days':
                duration = f"{match.group(1)} Days"
            elif unit == 'nights':
                duration = f"{match.group(1)} Nights"
            break
    
    # Departure time patterns
    time_patterns = [
        r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))',
        r'departs?\s*(?:at|:)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))',
    ]
    
    for pattern in time_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        times.extend(matches)
    
    return duration, ', '.join(set(times)) if times else ''

def extract_tour_info(html, url):
    from bs4 import NavigableString
    soup = BeautifulSoup(html, 'html.parser')

    # [PHASE 2 UPGRADE] Extract from specific CSS selectors first
    extracted_data = {}
    
    # Try to find price in common locations
    price_selectors = ['span.price', '.price', '[class*="price"]', '.tour-price', '.booking-price']
    for selector in price_selectors:
        price_elem = soup.select_one(selector)
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            if 'A$' in price_text or '$' in price_text:
                # Check if it contains Adult/Child labels
                if 'adult' in price_text.lower():
                    extracted_data['price_with_labels'] = price_text
                    print(f"[CSS Selector] Found price element: {price_text[:100]}")
                    break
                elif not extracted_data.get('price_simple'):
                    extracted_data['price_simple'] = price_text
                    print(f"[CSS Selector] Found price: {price_text}")
    
    # Try to find quick details / tour info section
    detail_selectors = ['.quick-details', '.tour-details', '.tour-info', '[class*="quick-detail"]']
    for selector in detail_selectors:
        detail_elem = soup.select_one(selector)
        if detail_elem:
            detail_text = detail_elem.get_text(strip=True)
            extracted_data['quick_details'] = detail_text
            print(f"[CSS Selector] Found quick details: {detail_text[:100]}")
            break

    # Prefer <body> if it exists, fallback to whole soup
    body = soup.body
    descendants = body.descendants if body else soup.descendants

    seen_lines = set()
    lines = []
    for el in descendants:
        if isinstance(el, NavigableString):
            text = el.strip()
            # Filter: skip if <4 words
            if len(text.split()) < 4:
                continue
            # Filter: skip if all uppercase (unless contains 'review' or 'tour')
            if text.isupper() and not ("review" in text.lower() or "tour" in text.lower()):
                continue
            # Filter: skip if only numbers/symbols
            if not any(c.isalpha() for c in text):
                continue
            # Filter: skip if duplicate in this tour
            if text in seen_lines:
                continue
            # Filter: skip if any word contains both numbers and letters (e.g., 'col-2141929553')
            if any(re.search(r'[a-zA-Z]', w) and re.search(r'\d', w) for w in text.split()):
                continue
            # Filter: skip if line is 1 or 2 characters long
            if len(text) <= 2:
                continue
            seen_lines.add(text)
            lines.append(text)
    # Try to extract a name from the first heading
    name = ''
    if soup.find(['h1', 'h2']):
        name = clean(soup.find(['h1', 'h2']).get_text())
    if not name:
        name = 'Tour'

    # Initialize price variables
    price_adult = ''
    
    # Use smart HTML cleaner to get clean, concise content (max 8000 chars for AI)
    main_content = clean_html_intelligently(html, max_length=8000)
    
    # Add start and finish markers for each tour
    start_marker = f"=== TOUR START: {name} ==="
    end_marker = f"=== TOUR END: {name} ==="
    main_content = f"{start_marker}\n{main_content}\n{end_marker}"
    
    # Disabled raw_html to prevent CSV field size errors
    main_html = ''

    # [UPGRADE 2] Extract JSON-LD structured data
    json_ld_data = extract_json_ld_data(soup)
    if json_ld_data.get('name') and not name:
        name = json_ld_data['name']
    if json_ld_data.get('price') and not price_adult:
        price_adult = f"${json_ld_data['price']}"
        print(f"[JSON-LD] Using price from structured data: {price_adult}")
    
    # [PHASE 2] Parse extracted data from CSS selectors
    price_child = ''
    if extracted_data.get('price_with_labels'):
        # Parse "AdultAges 15+A$159ChildAges 4 - 14A$149" format
        price_text = extracted_data['price_with_labels']
        adult_match = re.search(r'[Aa]dult.*?[A]?\$\s*([0-9,]+)', price_text)
        child_match = re.search(r'[Cc]hild.*?[A]?\$\s*([0-9,]+)', price_text)
        if adult_match and not price_adult:
            price_adult = f"A${adult_match.group(1)}"
            print(f"[CSS Parser] Adult price: {price_adult}")
        if child_match:
            price_child = f"A${child_match.group(1)}"
            print(f"[CSS Parser] Child price: {price_child}")
    elif extracted_data.get('price_simple') and not price_adult:
        price_adult = extracted_data['price_simple']
        print(f"[CSS Parser] Simple price: {price_adult}")
    
    # [UPGRADE 3] Extract duration and times from quick details or all text
    if extracted_data.get('quick_details'):
        extracted_duration, extracted_times = extract_duration_and_times(extracted_data['quick_details'])
        if extracted_duration:
            print(f"[CSS Parser] Duration from quick details: {extracted_duration}")
    else:
        full_text = soup.get_text()
        extracted_duration, extracted_times = extract_duration_and_times(full_text)
    
    # Use JSON-LD duration if available
    if json_ld_data.get('duration'):
        extracted_duration = json_ld_data['duration']

    # Generate stable ID from URL hash (so image paths don't break on re-scrape)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    
    # Return all fields, including raw_text and raw_html
    return {
        'id': url_hash,
        'name': name,
        'company_name': extract_company_name(url),
        'summary': '',
        'description': json_ld_data.get('description', ''),
        'duration': extracted_duration,
        'departure_location': '',
        'departure_times': extracted_times,
        'price_adult': price_adult,
        'price_child': price_child,
        'includes': '',
        'highlights': '',
        'keywords': '',
        'duration_hours': '',
        'link_booking': url,
        'link_more_info': url,
        'phone': '',
        'image_url': '',
        'image_urls': '',
        'commission_rate': '',
        'active': 'TRUE',
        'price_source_url': url,
        'price_tiers': '',
        'raw_text': main_content,
        'raw_html': main_html
    }

def append_to_csv(tour, csv_path):
    """
    Add or update a tour in the CSV file.
    If a tour with the same ID exists, it will be overwritten.
    If the CSV doesn't exist, it will be created.
    """
    file_exists = os.path.isfile(csv_path)
    
    if file_exists:
        # Read existing tours
        existing_tours = []
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_tours.append(row)
        
        # Check if this tour already exists (by ID)
        tour_updated = False
        for i, existing_tour in enumerate(existing_tours):
            if existing_tour.get('id') == tour.get('id'):
                # Overwrite the existing tour
                existing_tours[i] = tour
                tour_updated = True
                print(f"  [UPDATE] Overwriting existing tour: {tour['name']}")
                break
        
        if not tour_updated:
            # New tour, append it
            existing_tours.append(tour)
            print(f"  [NEW] Adding new tour: {tour['name']}")
        
        # Write all tours back to CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for tour_row in existing_tours:
                writer.writerow(tour_row)
    else:
        # Create new CSV file
        print(f"  [NEW CSV] Creating new file: {csv_path}")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerow(tour)
        print(f"  [NEW] Adding new tour: {tour['name']}")

def discover_tour_links(homepage_url):
    try:
        html = fetch_html(homepage_url)
        soup = BeautifulSoup(html, 'html.parser')
        base = homepage_url.rstrip('/')
        manual_candidates = []
        seen = set()
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True) or ''
            # Only internal links
            if not href.startswith('http'):
                href = urljoin(base + '/', href)
            if urlparse(href).netloc != urlparse(base).netloc:
                continue
            # Exclude unwanted file types
            if any(href.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.zip']):
                print(f"[EXCLUDED: filetype] {href}")
                continue
            # Exclude links with unwanted keywords (only in href, not text/content)
            excluded_kw = next((kw for kw in EXCLUDE_LINK_KEYWORDS if kw in href.lower()), None)
            if excluded_kw:
                print(f"[EXCLUDED: keyword '{excluded_kw}'] {href}")
                continue
            # Exclude homepage itself
            if href.rstrip('/') == homepage_url.rstrip('/'):
                continue
            # Exclude anchor-only links
            if href.endswith('#') or href.split('#')[0].rstrip('/') == homepage_url.rstrip('/'):
                continue
            # Only present unique links
            if href in seen:
                continue
            seen.add(href)
            # After all exclusion filters, send all remaining links to manual review
            manual_candidates.append((text, href))
        print(f"\nManual review for {homepage_url}: Press 'y' to keep, any other key to skip.\n")
        approved = []
        for text, link in manual_candidates:
            ans = input(f"Keep this link? [{text}] {link} [y/N]: ").strip().lower()
            if ans == 'y':
                approved.append(link)
        return approved
    except Exception as e:
        print(f"  Error discovering links from {homepage_url}: {e}")
        return []

def filter_tour_links(links):
    # Remove links that are homepage or book-now pages
    filtered = []
    for homepage, link in links:
        if link.endswith('/book-now/') or link.rstrip('/') == homepage.rstrip('/'):
            continue
        filtered.append((homepage, link))
    return filtered

def extract_price_tiers(soup):
    price_tiers = []
    price_adult = ''
    for table in soup.find_all('table'):
        # Get all rows
        rows = table.find_all('tr')
        if not rows:
            continue
        # Get headers from the first row
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
        # For each subsequent row, extract label and prices
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True)
            prices = [c.get_text(strip=True) for c in cells[1:]]
            for p in prices:
                if '$' in p:
                    price_tiers.append(f"{label}: {p}")
                    if label.lower() == 'adult' and not price_adult:
                        price_adult = p
    return '; '.join(price_tiers) if price_tiers else '', price_adult

def extract_price_adult(soup):
    # Try to find a single price (e.g., $123)
    text = soup.get_text()
    match = re.search(r'\$\s?([0-9]+(?:\.[0-9]{2})?)', text)
    if match:
        return match.group(0)
    return ''

def extract_first_price_from_html(html):
    # Look for 'FROM $<amount>' or 'A$<amount>' or just '$<amount>'
    # Try "FROM" prefix first
    match = re.search(r'FROM\s*[A]?\$\s*([0-9,]+)', html, re.IGNORECASE)
    if match:
        return f"FROM ${match.group(1)}"
    # Try Australian dollar format
    match = re.search(r'A\$\s*([0-9,]+)', html)
    if match:
        return f"A${match.group(1)}"
    # Try regular dollar format
    match = re.search(r'\$\s*([0-9,]+)', html)
    if match:
        return f"${match.group(1)}"
    return ''

def fetch_html_selenium(url, wait_time=10, expand_accordions=True):
    """
    Fetch HTML with Selenium, optionally expanding all accordion/dropdown sections
    
    Args:
        url: URL to fetch
        wait_time: How long to wait for page load
        expand_accordions: If True, automatically clicks all FAQ/accordion buttons
    """
    options = uc.ChromeOptions()
    # options.add_argument('--headless')  # Try with and without headless
    options.add_argument('--disable-gpu')
    driver = uc.Chrome(options=options)
    driver.get(url)
    
    # Wait for page to load
    time.sleep(3)
    
    try:
        # Try to click the 'PRICES' or 'PRICES & DEPARTURES' tab/button if present
        try:
            tab = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'prices & departures') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'prices')]"))
            )
            tab.click()
            print("Clicked on 'PRICES' or 'PRICES & DEPARTURES' tab.")
            time.sleep(2)
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '$')]"))
            )
        except Exception as e:
            print("Could not click 'PRICES' or 'PRICES & DEPARTURES' tab (may not exist):", e)
        
        # Expand all accordions/dropdowns if requested
        if expand_accordions:
            print("  🔽 Expanding all accordion sections...")
            expanded_count = 0
            
            # Common accordion/dropdown selectors
            accordion_selectors = [
                # Generic patterns
                "button[class*='accordion']",
                "button[class*='expand']",
                "button[class*='toggle']",
                "button[class*='collapse']",
                "div[class*='accordion']",
                "div[class*='toggle']",
                "[role='button']",
                "summary",  # HTML5 <details> element
                
                # Bootstrap accordions
                ".accordion-toggle",
                ".accordion-button",
                ".collapse-toggle",
                
                # Common custom classes
                ".faq-question",
                ".faq-toggle",
                ".dropdown-toggle",
                ".expand-button",
                ".show-more",
                ".read-more",
                
                # Text-based matching (case insensitive)
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'inclusions')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'what to bring')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'times')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'itinerary')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'details')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more info')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'read more')]",
                "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]",
            ]
            
            for selector in accordion_selectors:
                try:
                    # Determine if it's XPath or CSS selector
                    if selector.startswith('/'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        try:
                            # Check if element is visible and clickable
                            if element.is_displayed() and element.is_enabled():
                                # Scroll into view
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                                time.sleep(0.3)
                                
                                # Try to click
                                element.click()
                                expanded_count += 1
                                time.sleep(0.5)  # Wait for content to expand
                        except Exception:
                            # Element not clickable or already expanded
                            continue
                except Exception:
                    # Selector didn't match anything
                    continue
            
            print(f"  ✓ Expanded {expanded_count} accordion sections")
            
            # Give the page time to fully render expanded content
            time.sleep(2)
        
    except Exception as e:
        print(f"  ⚠️ Error during page interaction: {e}")
    
    # Get the final HTML
    html = driver.page_source
    driver.quit()
    
    # Save for debugging
    with open('selenium_debug.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Saved Selenium HTML to selenium_debug.html")
    
    return html

def main():
    discovered_links = []
    # Manual-only mode: use inline TOUR_HOME_PAGES or TOUR_LINKS
    active_homepages = normalize_homepages_list(TOUR_HOME_PAGES)
    if active_homepages:
        print("Discovering tour links from homepages...")
        for homepage in active_homepages:
            print(f"  Scanning: {homepage}")
            links = discover_tour_links(homepage)
            print(f"    Found {len(links)} tour links.")
            discovered_links.extend([(homepage, link) for link in links])
        # Save discovered links for review
        with open('discovered_links.txt', 'w', encoding='utf-8') as f:
            for homepage, link in discovered_links:
                f.write(f"{homepage},{link}\n")
        print(f"Discovered {len(discovered_links)} total tour links. Saved to discovered_links.txt.")
        # Filter out unwanted links
        tour_links = filter_tour_links(discovered_links)
    elif TOUR_LINKS:
        print("Using manually provided tour links.")
        tour_links = [(None, url) for url in TOUR_LINKS]
    else:
        print("Please paste your tour homepages in the TOUR_HOME_PAGES list or tour links in the TOUR_LINKS list at the top of the script.")
        return
    
    # Deduplicate URLs before scraping (prevents duplicate tours in CSV)
    print(f"\nTotal links before deduplication: {len(tour_links)}")
    seen_urls = set()
    unique_tour_links = []
    for homepage, url in tour_links:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_tour_links.append((homepage, url))
    tour_links = unique_tour_links
    print(f"Unique tours to scrape: {len(tour_links)}\n")
    
    # Save each company's tours to a separate CSV
    company_csvs = {}
    all_tours = [] # Collect all tours for summary
    for homepage, url in tour_links:
        try:
            print(f"Scraping: {url}")
            # Try BeautifulSoup first
            html = None
            try:
                html = fetch_html(url)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    print(f"  [403 Blocked] Site is blocking requests, trying Selenium...")
                    try:
                        html = fetch_html_selenium(url)
                    except Exception as se:
                        print(f"  [Selenium Failed] {se}")
                        raise e  # Re-raise original error if Selenium also fails
                else:
                    raise e  # Re-raise non-403 errors
            
            if html is None:
                print(f"  [Error] Could not fetch HTML for {url}")
                continue
            
            # [UPGRADE 1] Auto-detect if we need Selenium (no price in static HTML)
            if '$' not in html and 'price' not in html.lower():
                print(f"  [Auto-Selenium] No price indicators in static HTML, using Selenium...")
                try:
                    html = fetch_html_selenium(url)
                except Exception as e:
                    print(f"  [Auto-Selenium] Failed: {e}, continuing with static HTML...")
            
            tour = extract_tour_info(html, url)
            # extract_tour_info already extracts prices via CSS selectors, use those first
            price_adult = tour.get('price_adult', '')
            price_child = tour.get('price_child', '')
            fallback_price_child = ''  # Initialize to avoid UnboundLocalError
            
            # Try table extraction for price tiers (backup method)
            price_tiers, tier_price_adult = extract_price_tiers(BeautifulSoup(html, 'html.parser'))
            if not price_adult and tier_price_adult:
                price_adult = tier_price_adult
                print(f"[Price Tiers] Found adult price: {price_adult}")
            
            # Fallback: if price_adult is still empty, try to extract from full HTML
            if not price_adult:
                fallback_price = extract_first_price_from_html(html)
                if fallback_price:
                    print(f"[Fallback] Found price in HTML for {tour['name']}: {fallback_price}")
                    price_adult = fallback_price
            # Deep fallback: scan all elements for price patterns if still not found
            if not price_adult:
                soup = BeautifulSoup(html, 'html.parser')
                possible_prices = []
                
                # Look for prices near "Adult" or "Child" labels
                for el in soup.find_all(['span', 'div', 'p', 'li', 'td', 'th']):
                    text = el.get_text(strip=True)
                    # Check if this element or nearby contains "Adult" or "Child"
                    parent_text = ''
                    if el.parent:
                        parent_text = el.parent.get_text(strip=True)
                    combined = text + ' ' + parent_text
                    
                    # Look for A$ or $ followed by numbers
                    match = re.search(r'A\$\s*([0-9,]+)', text)
                    if match:
                        price_val = f"A${match.group(1)}"
                        if 'adult' in combined.lower() and not price_adult:
                            price_adult = price_val
                            print(f"[Deep Fallback] Found adult price: {price_adult}")
                        elif 'child' in combined.lower() and not fallback_price_child:
                            fallback_price_child = price_val
                            print(f"[Deep Fallback] Found child price: {fallback_price_child}")
                        else:
                            possible_prices.append(price_val)
                    else:
                        match = re.search(r'\$\s*([0-9,]+)', text)
                        if match:
                            price_val = f"${match.group(1)}"
                            if 'adult' in combined.lower() and not price_adult:
                                price_adult = price_val
                                print(f"[Deep Fallback] Found adult price: {price_adult}")
                            elif 'child' in combined.lower() and not fallback_price_child:
                                fallback_price_child = price_val
                                print(f"[Deep Fallback] Found child price: {fallback_price_child}")
                            else:
                                possible_prices.append(price_val)
                
                # If still no adult price, take the first found price
                if not price_adult and possible_prices:
                    price_adult = possible_prices[0]
                    print(f"[Deep Fallback] Found price in HTML for {tour['name']}: {price_adult}")
                
                if price_adult:
                    tour['price_adult'] = price_adult
                if fallback_price_child:
                    tour['price_child'] = fallback_price_child
                
                if not price_adult:
                    # Optionally, save the HTML for manual review
                    with open(f"missing_price_{tour['id']}.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    print(f"[Warning] No price found for {tour['name']}. HTML saved for review.")
            # Always save the found prices to the tour dict
            if price_adult:
                tour['price_adult'] = price_adult
            if price_child:
                tour['price_child'] = price_child
            if fallback_price_child:
                tour['price_child'] = fallback_price_child
            tour['price_tiers'] = price_tiers
            all_tours.append(tour)
            company = tour['company_name']
            csv_path = f"tours_{company}.csv"
            if csv_path not in company_csvs:
                company_csvs[csv_path] = True
            append_to_csv(tour, csv_path)
            print(f"  Added: {tour['name']} to {csv_path}")
        except Exception as e:
            print(f"  Error scraping {url}: {e}")
    print(f"Done. Tours saved to company-specific CSV files.")

    # Print summary of tours missing price information
    missing_price = []
    for row in all_tours:  # all_tours is your list of dicts for each tour
        if not row.get('price_adult') and not row.get('price_tiers'):
            missing_price.append(row.get('name', 'Unknown'))
    if missing_price:
        print("\n[SCRAPE SUMMARY] The following tours are missing price information:")
        for name in missing_price:
            print(f" - {name}")
    else:
        print("\n[SCRAPE SUMMARY] All tours have price information.")
    
    # Auto-run AI postprocessor on each company CSV
    print("\n=== Running AI Postprocessor ===")
    print("NOTE: This uses OpenAI API to extract descriptions, highlights, etc.")
    print("      Progress will be shown for each tour...\n")
    
    for csv_path in company_csvs.keys():
        if os.path.exists(csv_path):
            print(f"Processing {csv_path}...")
            try:
                import subprocess
                # Run without capture_output so you can see real-time progress
                result = subprocess.run(['python', 'ai_postprocess_csv.py', csv_path], 
                                      timeout=600)
                if result.returncode == 0:
                    print(f"  [OK] {csv_path} cleaned and saved as {csv_path[:-4]}_cleaned.csv\n")
                else:
                    print(f"  [ERROR] AI postprocessor returned exit code {result.returncode}\n")
            except subprocess.TimeoutExpired:
                print(f"  [ERROR] AI postprocessor timed out after 10 minutes\n")
            except Exception as e:
                print(f"  [ERROR] Failed to run AI postprocessor on {csv_path}: {e}\n")
    
    # Auto-run merge script to update _with_media.csv files (ONLY for scraped companies)
    print("\n=== Merging Cleaned Data to Media Files ===")
    print(f"Processing only the {len(company_csvs)} companies that were scraped...\n")
    try:
        # Import the merge function directly and run only on scraped companies
        from merge_cleaned_to_media import merge_cleaned_to_media
        
        # Get list of cleaned files for companies we just scraped
        scraped_cleaned_files = [csv_path.replace('.csv', '_cleaned.csv') for csv_path in company_csvs.keys()]
        
        # Filter to only process the files we just scraped
        import glob
        all_cleaned_files = glob.glob('*_cleaned.csv')
        files_to_merge = [f for f in all_cleaned_files if f in scraped_cleaned_files]
        
        if files_to_merge:
            print(f"Found {len(files_to_merge)} cleaned CSV files from this scraping session:\n")
            
            for cleaned_file in files_to_merge:
                # Derive the corresponding _with_media.csv filename
                base_name = cleaned_file.replace('_cleaned.csv', '')
                media_file = f"{base_name}_cleaned_with_media.csv"
                
                # Check if _with_media.csv exists
                if not os.path.exists(media_file):
                    print(f"[SKIP] {cleaned_file}")
                    print(f"       {media_file} does not exist - this appears to be a new company!")
                    print(f"       Creating initial _with_media.csv file...")
                    # Copy the cleaned file as the initial _with_media file
                    import shutil
                    shutil.copy(cleaned_file, media_file)
                    print(f"       [OK] Created {media_file}\n")
                    continue
                
                try:
                    # Load both CSVs
                    df_cleaned = pd.read_csv(cleaned_file)
                    df_media = pd.read_csv(media_file)
                    
                    print(f"[OK] {cleaned_file}")
                    print(f"     Merging into {media_file}")
                    
                    # Get columns that should be updated from cleaned (exclude image columns)
                    update_cols = [col for col in df_cleaned.columns 
                                  if col not in ['image_url', 'image_urls'] and col in df_media.columns]
                    
                    # Try to match by URL (most reliable for new scrapes)
                    url_to_cleaned = {}
                    for _, row in df_cleaned.iterrows():
                        url = row.get('link_booking', '')
                        if url and url not in url_to_cleaned:
                            url_to_cleaned[url] = row.to_dict()
                    
                    updated_count = 0
                    for idx, row in df_media.iterrows():
                        url = row.get('link_booking', '')
                        if url in url_to_cleaned:
                            cleaned_data = url_to_cleaned[url]
                            for col in update_cols:
                                if col in cleaned_data:
                                    df_media.at[idx, col] = cleaned_data[col]
                            # Also update the ID to the new hash-based ID
                            if 'id' in cleaned_data:
                                df_media.at[idx, 'id'] = cleaned_data['id']
                            updated_count += 1
                    
                    # Save updated media file
                    df_media.to_csv(media_file, index=False)
                    print(f"     Updated {updated_count} tours")
                    print(f"     Preserved image paths for all tours")
                    print()
                    
                except Exception as e:
                    print(f"[ERROR] {cleaned_file}: {e}")
                    print()
        else:
            print("No cleaned files found for the scraped companies.")
        
    except Exception as e:
        print(f"  [ERROR] Failed to run merge: {e}")
    
    print("\n=== Scraping, Cleaning, and Merging Complete ===")
    
    # Final validation report
    print("\n" + "=" * 80)
    print("FINAL DATA QUALITY REPORT")
    print("=" * 80)
    
    for csv_path in company_csvs.keys():
        media_csv = csv_path.replace('.csv', '_cleaned_with_media.csv')
        if os.path.exists(media_csv):
            import pandas as pd
            df = pd.read_csv(media_csv)
            print(f"\n{csv_path.replace('.csv', '')} ({len(df)} tours):")
            
            # Check for missing prices
            missing_price = df[(df['price_adult'].isna()) | (df['price_adult'] == '') | (df['price_adult'] == 'Unknown')]
            if len(missing_price) > 0:
                print(f"  ⚠ {len(missing_price)} tours missing adult price:")
                for _, row in missing_price.iterrows():
                    print(f"     - {row['name']}")
            else:
                print(f"  ✓ All tours have prices")
            
            # Check for missing descriptions
            missing_desc = df[(df['description'].isna()) | (df['description'] == '')]
            if len(missing_desc) > 0:
                print(f"  ⚠ {len(missing_desc)} tours missing description:")
                for _, row in missing_desc.iterrows():
                    print(f"     - {row['name']}")
            else:
                print(f"  ✓ All tours have descriptions")
    
    print("\n" + "=" * 80)
    print("Restart your Flask app to see the updated tours!")
    print("=" * 80)

if __name__ == '__main__':
    main() 