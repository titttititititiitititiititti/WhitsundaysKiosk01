#!/usr/bin/env python3
"""
Fix ALL Hero booking URLs to use the LandingPage format that works.
Format: /Book/LandingPage/?mode=2&id={productId}&token=...&src=...
"""

import json
import re
import requests

HERO_TOKEN = "8f0d64c87092161e01563"
HERO_BASE = "https://hero.airliebeachtourism.com.au"

def get_product_id_and_mode(widget_url):
    """
    Fetch widget URL and extract product ID and mode from the redirect.
    """
    try:
        response = requests.get(widget_url, allow_redirects=True, timeout=10)
        html = response.text
        
        # Extract the full redirect URL
        match = re.search(r"document\.location\.replace\(['\"]([^'\"]+)['\"]\)", html)
        if not match:
            return None, None
        
        full_url = match.group(1)
        
        # Extract product ID from WidgetLandingPage/XXXXX
        id_match = re.search(r'WidgetLandingPage/([^?]+)', full_url)
        if not id_match:
            return None, None
        
        product_id = id_match.group(1)
        
        # Extract mode from URL
        mode_match = re.search(r'mode=(\d+)', full_url)
        mode = mode_match.group(1) if mode_match else '2'
        
        return product_id, mode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None, None

def create_landing_page_url(product_id, mode='2'):
    """
    Create the LandingPage booking URL - this format WORKS!
    """
    return f"{HERO_BASE}/Book/LandingPage/?mode={mode}&id={product_id}&token={HERO_TOKEN}&src={HERO_BASE}"

def fix_all_urls():
    """Fix ALL Hero URLs in nathan's account to use LandingPage format"""
    
    settings_file = 'config/accounts/nathan/settings.json'
    print(f"[LOAD] Loading {settings_file}...")
    
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    tour_overrides = settings.get('tour_overrides', {})
    
    updated_count = 0
    failed_count = 0
    
    print(f"\n[PROCESS] Processing {len(tour_overrides)} tour overrides...\n")
    
    for tour_key, override in tour_overrides.items():
        widget_html = override.get('hero_widget_html', '')
        
        # Extract widget URL from iframe
        match = re.search(r'src=["\']([^"\']+widget\.hero\.travel[^"\']+)["\']', widget_html)
        if not match:
            print(f"[SKIP] {tour_key[:45]}: No widget URL")
            continue
        
        widget_url = match.group(1)
        print(f"[CHECK] {tour_key[:45]}:")
        print(f"   Widget: {widget_url}")
        
        # Get product info
        product_id, mode = get_product_id_and_mode(widget_url)
        
        if not product_id:
            print(f"   [FAIL] Could not extract product ID")
            failed_count += 1
            continue
        
        # Create LandingPage URL (the format that works!)
        booking_url = create_landing_page_url(product_id, mode)
        override['booking_button_url'] = booking_url
        
        print(f"   [OK] Product ID: {product_id}, Mode: {mode}")
        print(f"   [OK] URL: {booking_url[:70]}...")
        updated_count += 1
    
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
    print(f"\nAll URLs now use: /Book/LandingPage/?mode=X&id=XXXXX format")
    print(f"\nSettings saved to:")
    print(f"   - {settings_file}")
    print(f"   - {defaults_file}")

if __name__ == '__main__':
    fix_all_urls()

