#!/usr/bin/env python3
"""
Fix Hero booking URLs - handle numeric vs alphanumeric product IDs correctly.

Numeric IDs (25604): Use LandingPage/?mode=2&id=25604
Alphanumeric IDs (a9d0675ae2cd2e03): Use WidgetLandingPage URL (widget on their domain where Book Now works)
"""

import json
import re
import requests

HERO_TOKEN = "8f0d64c87092161e01563"
HERO_BASE = "https://hero.airliebeachtourism.com.au"

def get_widget_info(widget_url):
    """
    Fetch widget URL and extract product ID and full redirect URL.
    Returns (product_id, full_redirect_url, is_numeric)
    """
    try:
        response = requests.get(widget_url, allow_redirects=True, timeout=10)
        html = response.text
        
        # Extract the full redirect URL
        match = re.search(r"document\.location\.replace\(['\"]([^'\"]+)['\"]\)", html)
        if not match:
            return None, None, False
        
        full_url = match.group(1)
        
        # Extract product ID from WidgetLandingPage/XXXXX
        id_match = re.search(r'WidgetLandingPage/([^?]+)', full_url)
        if not id_match:
            return None, None, False
        
        product_id = id_match.group(1)
        is_numeric = product_id.isdigit()
        
        return product_id, full_url, is_numeric
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None, None, False

def create_booking_url(product_id, full_widget_url, is_numeric):
    """
    Create the appropriate booking URL based on product ID type.
    """
    if is_numeric:
        # Numeric IDs: Use LandingPage format (tested and works!)
        return f"{HERO_BASE}/Book/LandingPage/?mode=2&id={product_id}&token={HERO_TOKEN}&src={HERO_BASE}"
    else:
        # Alphanumeric IDs: Use the WidgetLandingPage URL directly
        # This shows the widget on their domain where Book Now works
        return full_widget_url

def fix_nathan_urls():
    """Fix all Hero URLs in nathan's account"""
    
    settings_file = 'config/accounts/nathan/settings.json'
    print(f"[LOAD] Loading {settings_file}...")
    
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    tour_overrides = settings.get('tour_overrides', {})
    
    numeric_count = 0
    alpha_count = 0
    failed_count = 0
    
    print(f"\n[PROCESS] Processing {len(tour_overrides)} tour overrides...\n")
    
    for tour_key, override in tour_overrides.items():
        widget_html = override.get('hero_widget_html', '')
        
        # Extract widget URL from iframe
        match = re.search(r'src=["\']([^"\']+widget\.hero\.travel[^"\']+)["\']', widget_html)
        if not match:
            print(f"[SKIP] {tour_key[:40]}: No widget URL in iframe")
            continue
        
        widget_url = match.group(1)
        print(f"[CHECK] {tour_key[:40]}:")
        
        # Get product info
        product_id, full_url, is_numeric = get_widget_info(widget_url)
        
        if not product_id:
            print(f"   [FAIL] Could not extract product ID")
            failed_count += 1
            continue
        
        # Create appropriate booking URL
        booking_url = create_booking_url(product_id, full_url, is_numeric)
        override['booking_button_url'] = booking_url
        
        if is_numeric:
            print(f"   [OK] Numeric ID: {product_id}")
            print(f"   [OK] LandingPage URL")
            numeric_count += 1
        else:
            print(f"   [OK] Alphanumeric ID: {product_id}")
            print(f"   [OK] WidgetLandingPage URL (their domain)")
            alpha_count += 1
    
    # Save updated settings
    print(f"\n[SAVE] Saving updated settings...")
    with open(settings_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    
    # Also update defaults
    defaults_file = 'config/defaults/nathan/settings.json'
    with open(defaults_file, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    
    print(f"\n[DONE]")
    print(f"   Numeric IDs (LandingPage):     {numeric_count} tours")
    print(f"   Alphanumeric IDs (Widget):     {alpha_count} tours")
    print(f"   Failed:                        {failed_count} tours")
    print(f"\nSettings saved to:")
    print(f"   - {settings_file}")
    print(f"   - {defaults_file}")

if __name__ == '__main__':
    fix_nathan_urls()

