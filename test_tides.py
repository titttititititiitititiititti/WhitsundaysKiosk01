"""Quick test script to find working tide data sources for Airlie Beach"""
import urllib.request
import json
import re

# Test 1: Open-Meteo Marine API (free, no key)
print("=== Open-Meteo Marine API ===")
try:
    url = "https://marine-api.open-meteo.com/v1/marine?latitude=-20.27&longitude=148.72&hourly=wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_period,ocean_current_velocity&forecast_days=3&timezone=Australia/Brisbane"
    resp = urllib.request.urlopen(url, timeout=10)
    data = json.loads(resp.read())
    print(f"Available hourly keys: {list(data.get('hourly', {}).keys())}")
    h = data['hourly']
    for i in range(0, min(24, len(h['time'])), 3):
        print(f"  {h['time'][i]}: wave={h['wave_height'][i]}m, swell={h['swell_wave_height'][i]}m, period={h['wave_period'][i]}s")
    print("SUCCESS - Wave data available")
except Exception as e:
    print(f"FAILED: {e}")

# Test 2: Check if tide-forecast.com allows iframe embedding
print("\n=== tide-forecast.com iframe check ===")
try:
    url = "https://www.tide-forecast.com/locations/Shute-Harbour-Australia/tides/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    headers = dict(resp.headers)
    xfo = headers.get("x-frame-options", headers.get("X-Frame-Options", "NOT SET"))
    csp = headers.get("content-security-policy", "NOT SET")
    print(f"  X-Frame-Options: {xfo}")
    print(f"  CSP frame-ancestors: {'frame-ancestors' in csp if csp != 'NOT SET' else 'N/A'}")
    if xfo == "NOT SET" and "frame-ancestors" not in str(csp):
        print("  EMBEDDABLE - Can use iframe!")
    else:
        print("  NOT embeddable in iframe")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 3: Check tideschart.com  
print("\n=== tideschart.com check ===")
try:
    url = "https://www.tideschart.com/Australia/Queensland/Whitsunday-Region/Shute-Harbour/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    headers = dict(resp.headers)
    xfo = headers.get("x-frame-options", headers.get("X-Frame-Options", "NOT SET"))
    print(f"  X-Frame-Options: {xfo}")
    print(f"  Status: {resp.status}")
    data = resp.read().decode("utf-8", errors="replace")
    # Try to find tide data in the HTML
    tides = re.findall(r'((?:High|Low)\s+Tide.*?(?:\d+:\d+\s*(?:AM|PM|am|pm)))', data[:5000])
    for t in tides[:4]:
        print(f"  Found: {t[:80]}")
    if not tides:
        # Try another pattern
        tides2 = re.findall(r'(\d+:\d+\s*(?:AM|PM).*?(?:high|low))', data, re.IGNORECASE)
        for t in tides2[:4]:
            print(f"  Found2: {t[:80]}")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 4: Check tides4fishing.com
print("\n=== tides4fishing.com check ===")
try:
    url = "https://tides4fishing.com/au/queensland/airlie-beach"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    headers = dict(resp.headers)
    xfo = headers.get("x-frame-options", headers.get("X-Frame-Options", "NOT SET"))
    print(f"  X-Frame-Options: {xfo}")
    print(f"  Status: {resp.status}")
    data = resp.read().decode("utf-8", errors="replace")
    # Search for tide info
    tides = re.findall(r'((?:high|low)\s*tide.*?\d+:\d+)', data[:10000], re.IGNORECASE)
    for t in tides[:4]:
        print(f"  Found: {t[:100]}")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 5: Try BOM tides search page
print("\n=== BOM Tides JSON API ===")
try:
    # BOM angular app uses a JSON API
    url = "http://www.bom.gov.au/australia/tides/scripts/tides_data.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print(f"  Keys: {list(data.keys())[:5]}")
    print(f"  Stations: {len(data) if isinstance(data, list) else 'dict'}")
    if isinstance(data, dict):
        for k in list(data.keys())[:3]:
            print(f"    {k}: {str(data[k])[:100]}")
except Exception as e:
    print(f"  FAILED: {e}")

print("\n=== DONE ===")

