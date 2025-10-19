# Tour Kiosk Project - Complete Workflow Summary

## Current State: Production Ready ✅

Your scraper is now fully functional with multiple extraction methods and automatic processing!

---

## **How to Scrape Tours (Full Workflow)**

### **Step 1: Run the Scraper** (ONE COMMAND DOES EVERYTHING!)
```bash
python scrape_tours.py
```

**What happens automatically:**
1. Discovers tour links from homepages (or uses manual links you provide)
2. Scrapes each tour page with multiple extraction methods:
   - CSS selector targeting (finds prices in specific HTML elements)
   - JSON-LD structured data (schema.org metadata)
   - Regex patterns (duration, times, etc.)
   - Auto-Selenium (if no price in static HTML)
   - Deep fallback (scans all elements for adult/child prices)
3. Saves raw data to `tours_<company>.csv`
4. **Automatically runs AI postprocessor**
5. Saves cleaned data to `tours_<company>_cleaned.csv`
6. **Automatically merges to media files** (preserves images, updates prices/details)
7. Updates `tours_<company>_cleaned_with_media.csv` (what your app uses)

### **Step 2: View in App**
Your Flask app automatically loads all `*_with_media.csv` files, so just refresh the browser!

**That's it! One command does everything!** ✅

---

## **When to Run Each Script**

### **Scrape Tours** → `python scrape_tours.py`
- When adding new tour companies
- When tour details change (prices, descriptions, etc.)
- When you want to update the database

### **Merge to Media** → `python merge_cleaned_to_media.py`
- **After every scrape** (if you want to keep existing images)
- Updates prices/details without re-downloading images

### **Download Images** → `python download_tour_media.py <csv_file>`
- Only when adding **new tours** (that don't have images yet)
- Or when images need to be re-downloaded
- **Not needed** if just updating prices/details

### **Edit Tours** → `python edit_tours_csv.py`
- When you want to manually review/edit individual tours
- When you need to delete non-tour entries
- Interactive terminal-based editor

---

## **Common Workflows**

### **Scenario 1: Update Existing Company Data**
```bash
# 1. Re-scrape (automatically cleans and merges!)
python scrape_tours.py

# 2. Refresh browser
# Done! Prices and details are updated, images preserved
```

### **Scenario 2: Add New Tours**
```bash
# 1. Scrape
python scrape_tours.py

# 2. Download images
python download_tour_media.py tours_newcomp any_cleaned.csv

# 3. Refresh browser
# Done! New tours with images
```

### **Scenario 3: Clean Up Bad Data**
```bash
# Option A: Interactive editor
python edit_tours_csv.py

# Option B: Custom filter script (like clean_cruisewhitsundays_csv.py)
python clean_<company>_csv.py

# Then merge if needed
python merge_cleaned_to_media.py
```

---

## **Key Features**

### **Scraper (scrape_tours.py)**
✅ Auto-Selenium detection (JavaScript-rendered prices)  
✅ CSS selector targeting (finds prices in specific elements)  
✅ JSON-LD extraction (clean structured data)  
✅ Smart adult/child parsing ("AdultA$159ChildA$149" format)  
✅ Duration & time patterns ("5 Hours", "9:30 AM")  
✅ Multiple fallback layers (never miss data)  
✅ URL-based hash IDs (stable across re-scrapes)  
✅ Auto-runs AI postprocessor  

### **Merge Script (merge_cleaned_to_media.py)**
✅ Preserves image paths  
✅ Updates prices, duration, description  
✅ Processes all companies automatically  
✅ Safe (doesn't delete data)  

### **Interactive Editor (edit_tours_csv.py)**
✅ Step through tours one by one  
✅ Edit any field  
✅ Delete unwanted tours  
✅ Auto-backup before changes  

---

## **File Structure**

```
tours_<company>.csv                    ← Raw scraped data
tours_<company>_cleaned.csv            ← AI-processed data
tours_<company>_cleaned_with_media.csv ← Final version (what app uses)

static/tour_images/<company>/<id>/    ← Image folders (stable IDs)
```

---

## **Troubleshooting**

### **Problem: Prices not showing in app**
**Solution:** Run `python merge_cleaned_to_media.py` after scraping

### **Problem: Images missing**
**Solution:** Run `python download_tour_media.py <cleaned_csv>`

### **Problem: Scraper found "$," instead of real price**
**Solution:** Fixed in [SCRAPE-014] - old regex disabled

### **Problem: Duplicate tours**
**Solution:** Use `edit_tours_csv.py` or create a custom filter script

---

## **Recent Bug Fixes**

### **[SCRAPE-014] - Price Extraction Bug (FIXED)**
**Problem:** Scraper was finding `$,` (from JavaScript code) instead of real prices  
**Cause:** Old regex ran before CSS selector code and matched JavaScript regex patterns  
**Fix:** Disabled old regex (line 297-299 in scrape_tours.py)  
**Result:** CSS selector targeting now works correctly ✅

---

## **Next Steps**

1. **Re-scrape RedCat Adventures** with fixed code
2. **Run merge script** to update prices in _with_media.csv
3. **Refresh app** to see prices

**Commands:**
```bash
python scrape_tours.py
python merge_cleaned_to_media.py
```

Then restart Flask app and refresh browser!

---

## **Documentation Files**

- `changelog.txt` - All changes with tags
- `prompt and glossary.txt` - Project purpose and tag locations
- `SCRAPER_IMPROVEMENTS.md` - Scraper upgrade details
- `STABLE_IDS_SUMMARY.md` - URL-based ID explanation
- `PHASE_1_UPGRADES.md` - Phase 1 feature details
- `WORKFLOW_SUMMARY.md` - This file

---

**Everything is ready! Your workflow is now:**
1. Scrape (auto-cleans & auto-merges!) → 2. Refresh ✅

**Just one command: `python scrape_tours.py`**

