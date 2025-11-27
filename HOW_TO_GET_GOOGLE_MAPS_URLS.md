# How to Get Google Maps URLs (Avoiding CAPTCHAs)

## The Problem

Automated scraping triggers CAPTCHAs on:
- ❌ Google Search
- ❌ TripAdvisor
- ✅ **Google Maps (less protected!)**

## The Solution

**Manually find the Google Maps URLs**, then let the scraper work directly with those URLs.

---

## Step-by-Step Guide

### 1. Search Google Manually (in your browser)

```
Search: "Cruise Whitsundays Airlie Beach"
```

### 2. Look for the Google Maps Result

You'll see a knowledge panel on the right with:
- Business name
- **Star rating (e.g., 4.9 ⭐ 2,985 reviews)**
- Address, phone, website
- **"View on Google Maps" link**

### 3. Click "View on Google Maps" or the Reviews Link

This opens Google Maps with the business selected.

### 4. Copy the URL

The URL will look like:
```
https://www.google.com/maps/place/Cruise+Whitsundays/@-20.2800481,148.7141176,17z/data=!3m1!4b1!4m6!3m5!...
```

You can simplify it to:
```
https://www.google.com/maps/place/Cruise+Whitsundays/@-20.2800481,148.7141176,17z
```

### 5. Add to the Scraper

Edit `scrape_google_maps_direct.py`:

```python
GOOGLE_MAPS_URLS = {
    'cruisewhitsundays': {
        'url': 'https://www.google.com/maps/place/Cruise+Whitsundays/@-20.2800481,148.7141176,17z',
        'tour_ids': []  # Leave empty - auto-loads from CSV
    },
}
```

### 6. Run the Scraper

```bash
python scrape_google_maps_direct.py
```

---

## For Your Current Tours

### Based on your screenshot, here are the URLs to add:

**True Blue Sailing** (2,985 reviews):
```python
'truebluesailing': {
    'url': 'https://www.google.com/maps/place/True+Blue+Sailing',
    'tour_ids': []
},
```

**Cruise Whitsundays**:
1. Search Google: "Cruise Whitsundays Airlie Beach"
2. Look for the Maps result with reviews
3. Copy that URL
4. Add to the script

---

## Quick Method for Finding Multiple Companies

### Use this search pattern:

```
"[Company Name] Airlie Beach google maps"
```

Examples:
- "Cruise Whitsundays Airlie Beach google maps"
- "Red Cat Adventures Airlie Beach google maps"
- "ZigZag Whitsundays Airlie Beach google maps"

The first result should be the Google Maps page!

---

## Why This Works

✅ **No automated searching** - You manually find URLs  
✅ **Direct to Maps** - Bypasses Google Search CAPTCHAs  
✅ **Less bot detection** - Maps is more lenient than Search  
✅ **One URL = All tours** - Apply company reviews to all their tours  

---

## Complete Workflow

1. **For each major company**:
   - Google: "[Company] Airlie Beach"
   - Find Maps URL
   - Copy it

2. **Edit `scrape_google_maps_direct.py`**:
   - Add all URLs to `GOOGLE_MAPS_URLS`

3. **Run once**:
   ```bash
   python scrape_google_maps_direct.py
   ```

4. **Done!**
   - Reviews saved for all tours
   - Can be used as fallback when TripAdvisor fails

---

## Example: Your Screenshot

From your True Blue Sailing screenshot:

```
✅ 4.9 stars
✅ 2,985 Google reviews  
✅ Located at: southern marina M arm (jetty, Coral Sea Marina, 1-3 Shingley Dr, Airlie Beach QLD 4802
```

This is PERFECT for scraping! Much better than TripAdvisor.

---

## Pro Tips

### Tip 1: Run Browser Visibly (Not Headless)

The script is set to run with visible browser - this helps avoid detection!

### Tip 2: One Company at a Time

If you get CAPTCHAs, just do one company, close browser, wait 5 minutes, do next one.

### Tip 3: Use for Major Operators Only

For companies with LOTS of tours (like Cruise Whitsundays), this is perfect!  
For small operators, the automated scraper might work fine.

---

## Quick Reference

**File to edit**: `scrape_google_maps_direct.py`  
**Section**: `GOOGLE_MAPS_URLS = {...}`  
**Run command**: `python scrape_google_maps_direct.py`  
**Results**: Saved to `tour_reviews/[company]/[tour_id].json`  

---

**Last Updated**: October 12, 2025  
**Status**: ✅ Ready to Use










