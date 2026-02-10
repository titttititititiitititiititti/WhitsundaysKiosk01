#!/usr/bin/env python3
"""
Convert Hero widget URLs to direct booking LandingPage URLs.
This extracts the productId from each widget and creates a direct booking link.
"""

import json
import re
import requests
from urllib.parse import urlparse, parse_qs

# Hero token for airliebeachtourism (same for all their tours)
HERO_TOKEN = "8f0d64c87092161e01563"
HERO_BASE = "https://hero.airliebeachtourism.com.au"

def get_product_id_from_widget(widget_url):
    """
    Fetch a widget URL and extract the productId.
    widget.hero.travel URLs contain a JS redirect with the productId.
    """
    try:
        # Fetch the widget page
        response = requests.get(widget_url, allow_redirects=True, timeout=10)
        html = response.text
        
        # Look for productId in WidgetLandingPage URL (format: WidgetLandingPage/12345)
        match = re.search(r'WidgetLandingPage[/\\](\d+)', html)
        if match:
            return match.group(1)
        
        # Also try productId query parameter
        match = re.search(r'productId[=:](\d+)', html)
        if match:
            return match.group(1)
        
        # Check URL query params if it's a full URL
        parsed = urlparse(widget_url)
        params = parse_qs(parsed.query)
        if 'productId' in params:
            return params['productId'][0]
                
        return None
    except Exception as e:
        print(f"  [ERROR] Error fetching {widget_url}: {e}")
        return None

def create_landing_page_url(product_id):
    """Create the direct booking LandingPage URL"""
    return f"{HERO_BASE}/Book/LandingPage/?mode=2&id={product_id}&token={HERO_TOKEN}&src={HERO_BASE}"

def convert_nathan_widgets():
    """Convert all Hero widgets in nathan's account to direct booking URLs"""
    
    # Load nathan's settings
    settings_file = 'config/accounts/nathan/settings.json'
    print(f"[LOAD] Loading {settings_file}...")
    
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    tour_overrides = settings.get('tour_overrides', {})
    
    updated_count = 0
    failed_count = 0
    
    print(f"\n[PROCESS] Processing {len(tour_overrides)} tour overrides...\n")
    
    for tour_key, override in tour_overrides.items():
        booking_url = override.get('booking_button_url', '')
        widget_html = override.get('hero_widget_html', '')
        
        # Skip if already converted (contains LandingPage)
        if 'LandingPage' in booking_url:
            print(f"[SKIP] {tour_key[:40]}: Already converted")
            continue
        
        # Find widget URL from booking_button_url or hero_widget_html
        widget_url = None
        
        if 'widget.hero.travel' in booking_url:
            widget_url = booking_url
        elif 'hero.airliebeachtourism.com.au' in booking_url:
            widget_url = booking_url
        elif widget_html:
            # Extract src from iframe
            match = re.search(r'src=["\']([^"\']+)["\']', widget_html)
            if match:
                widget_url = match.group(1)
        
        if not widget_url:
            print(f"[WARN] {tour_key[:40]}: No widget URL found")
            failed_count += 1
            continue
        
        print(f"[CHECK] {tour_key[:40]}:")
        print(f"   Widget: {widget_url[:60]}...")
        
        # Get product ID
        product_id = get_product_id_from_widget(widget_url)
        
        if product_id:
            # Create new landing page URL
            new_url = create_landing_page_url(product_id)
            override['booking_button_url'] = new_url
            print(f"   [OK] Product ID: {product_id}")
            print(f"   [OK] New URL: {new_url[:60]}...")
            updated_count += 1
        else:
            print(f"   [FAIL] Could not extract product ID")
            failed_count += 1
    
    # Save updated settings
    print(f"\n[SAVE] Saving updated settings...")
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    
    # Also update defaults
    defaults_file = 'config/defaults/nathan/settings.json'
    with open(defaults_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    
    print(f"\n[DONE]")
    print(f"   Updated: {updated_count} tours")
    print(f"   Failed:  {failed_count} tours")
    print(f"\nSettings saved to:")
    print(f"   - {settings_file}")
    print(f"   - {defaults_file}")

if __name__ == '__main__':
    convert_nathan_widgets()

