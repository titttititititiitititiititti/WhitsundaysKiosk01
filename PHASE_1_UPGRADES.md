# Phase 1: Quick Wins - Scraper Upgrades

## Summary

Implemented 3 major upgrades to improve data extraction quality without requiring AI to filter noise:

1. ✅ **Auto-Selenium Detection** - Automatically use browser automation when static HTML doesn't contain prices
2. ✅ **JSON-LD Structured Data Extraction** - Extract clean data from schema.org metadata
3. ✅ **Duration & Time Pattern Matching** - Regex patterns to extract tour duration and departure times

---

## Upgrade 1: Auto-Selenium Detection

### Problem
Many modern tour booking sites load prices dynamically via JavaScript. BeautifulSoup (static HTML parsing) can't see these prices.

### Solution
**Auto-detect when Selenium is needed:**
```python
if '$' not in html and 'price' not in html.lower():
    print("No price indicators in static HTML, using Selenium...")
    html = fetch_html_selenium(url)
```

### How It Works
1. First try fast static HTML fetch
2. Check if HTML contains any price indicators (`$` or word "price")
3. If not, automatically fall back to Selenium (slower but sees JavaScript-rendered content)
4. Continue with extraction using the Selenium-fetched HTML

### Benefits
- ✅ Catches prices that are only visible after JavaScript execution
- ✅ No manual intervention needed
- ✅ Still fast for static sites (only uses Selenium when needed)

---

## Upgrade 2: JSON-LD Structured Data Extraction

### Problem
Many tour sites embed clean, structured data in `<script type="application/ld+json">` tags (schema.org format), but we were ignoring it and scraping messy HTML instead.

### Solution
**Extract structured data first:**
```python
def extract_json_ld_data(soup):
    for script in soup.find_all('script', type='application/ld+json'):
        data = json.loads(script.string)
        if data['@type'] in ['Product', 'TourPackage', 'Event', 'Service']:
            return {
                'name': data.get('name'),
                'description': data.get('description'),
                'price': data.get('offers', {}).get('price'),
                'duration': data.get('duration'),
            }
```

### How It Works
1. Find all JSON-LD script tags in the page
2. Parse the JSON data
3. Check if it's a tour-related schema type (Product, TourPackage, etc.)
4. Extract clean fields: name, description, price, duration
5. Use this data to populate tour fields (overrides scraped data if available)

### Benefits
- ✅ **Clean, accurate data** (site owners maintain this for SEO/Google)
- ✅ **No HTML parsing noise** (structured, not messy text)
- ✅ **Commonly available** (most modern booking sites use schema.org)

### Example Output
```
[JSON-LD] Found structured data: ['name', 'description', 'price', 'duration']
[JSON-LD] Using price from structured data: $159
```

---

## Upgrade 3: Duration & Time Pattern Matching

### Problem
Duration and departure times were not being extracted consistently (or at all).

### Solution
**Regex patterns for common formats:**

#### Duration Patterns
```python
- "5 hours" → "5 Hours"
- "2 days" → "2 Days"
- "half-day" → "half-day"
- "3 nights" → "3 Nights"
```

#### Departure Time Patterns
```python
- "9:30 am" → extracted
- "Departs at 10:00 AM" → "10:00 AM"
- "2:15pm" → "2:15pm"
```

### How It Works
1. Get all text from the page
2. Search for duration patterns: `(\d+)\s*(?:hour|hr|hours|hrs)`, etc.
3. Search for time patterns: `(\d{1,2}:\d{2}\s*(?:am|pm))`, etc.
4. Format and return the first match found
5. Populate `duration` and `departure_times` fields

### Benefits
- ✅ **Consistent extraction** across different site formats
- ✅ **No manual parsing** needed
- ✅ **Multiple format support** (handles variations)

---

## Combined Effect: Better Data Quality

### Before Phase 1
```
Name: Falls to Paradise – Waterfall Tour
Description: (empty)
Price (Adult): N/A
Price (Child): N/A
Duration: (empty)
Departure Times: (empty)
```

### After Phase 1
```
Name: Falls to Paradise – Waterfall Tour
Description: Experience the ultimate tropical getaway... (from JSON-LD)
Price (Adult): $159 (from JSON-LD or deep fallback)
Price (Child): $149 (from deep fallback with label matching)
Duration: 5 Hours (from regex extraction)
Departure Times: 9:00 AM, 2:00 PM (from regex extraction)
```

---

## What's Next?

### Phase 2: Medium Effort (Optional)
- CSS selector targeting for common price/detail locations
- Filter out navigation/footer before sending to AI
- Smarter text extraction (focus on main content area)

### Phase 3: Fine-Tuning (If Needed)
- Per-company custom extractors
- Booking widget detection
- Image extraction from galleries

---

## How to Use

Just run the scraper as before:
```bash
python scrape_tours.py
```

**What happens:**
1. Scrapes tours with all Phase 1 upgrades active
2. Auto-uses Selenium when needed
3. Extracts JSON-LD data if available
4. Extracts duration and times via regex
5. Auto-runs AI postprocessor
6. Saves cleaned CSVs

---

## Files Modified
- `scrape_tours.py` - Added JSON-LD extraction, duration/time patterns, auto-Selenium detection

## Files Created
- `PHASE_1_UPGRADES.md` - This file


