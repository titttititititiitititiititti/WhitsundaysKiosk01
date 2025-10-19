# Scraper Improvements - Summary

## Changes Made

### 1. **Auto-Run AI Postprocessor After Scraping**
- After all tours are scraped and saved to company CSVs, the script now automatically runs `ai_postprocess_csv.py` on each CSV.
- This means you get cleaned CSVs automatically without a manual second step.
- **Location:** End of `main()` function in `scrape_tours.py`

### 2. **Improved Price Extraction**

#### A. Better Regex Patterns
- Now recognizes Australian dollar format: `A$ 159`
- Recognizes "FROM" prefix: `FROM $229`
- **Location:** `extract_first_price_from_html()` function

#### B. Smart Deep Fallback
- Scans all HTML elements (`span`, `div`, `p`, `li`, `td`, `th`) for prices
- **Intelligently matches "Adult" and "Child" labels** with nearby prices
- Example: If it sees "Adult" and "A$ 159" in the same element or parent, it extracts it as `price_adult`
- Also extracts `price_child` if found near "Child" label
- **Location:** Deep fallback section in `main()` function

### 3. **Better Logging**
- Now prints which fallback method found the price
- Prints separate messages for adult and child prices
- Saves HTML for manual review if no price is found at all

---

## How to Use

### Run the Scraper (One Command Does Everything)
```bash
python scrape_tours.py
```

**What happens:**
1. Scrapes all tours from the homepages/links you provided
2. Extracts price, duration, and other details using multiple fallback methods
3. Saves raw CSVs (e.g., `tours_redcatadventures.csv`)
4. **Automatically runs AI postprocessor** on each CSV
5. Saves cleaned CSVs (e.g., `tours_redcatadventures_cleaned.csv`)

### Expected Output
```
Scraping: https://redcatadventures.com.au/package/falls-to-paradise/
[Deep Fallback] Found adult price: A$159
[Deep Fallback] Found child price: A$149
  Added: Falls to Paradise – Waterfall Tour to tours_redcatadventures.csv
Done. Tours saved to company-specific CSV files.

=== Running AI Postprocessor ===
Processing tours_redcatadventures.csv...
  ✓ tours_redcatadventures.csv cleaned and saved as tours_redcatadventures_cleaned.csv

=== Scraping and Cleaning Complete ===
```

---

## What This Solves

### Before
- Price like "A$ 159" was often missed
- Had to manually run AI postprocessor after scraping
- No indication of which fallback method was used
- Missing child prices

### After
- ✅ Recognizes Australian dollar format (`A$`)
- ✅ Extracts both adult and child prices when labeled
- ✅ Auto-runs AI postprocessor after scraping
- ✅ Clear logging of which method found the price
- ✅ One command does everything

---

## Next Steps (Optional Improvements)

1. **Add Selenium for Dynamic Prices:**  
   If some prices are loaded via JavaScript (not visible in static HTML), we can add Selenium to wait for them to load.

2. **Extract Departure Times:**  
   Similar pattern-matching logic can be added for departure times.

3. **Better Duration Extraction:**  
   Look for "5 Hours" or "All day" patterns and extract them consistently.

---

## Files Modified
- `scrape_tours.py` - Main scraper with auto-postprocessor and improved price extraction
- `ai_postprocess_csv.py` - No changes (already accepts CLI args)

## Files Created
- `SCRAPER_IMPROVEMENTS.md` - This file


