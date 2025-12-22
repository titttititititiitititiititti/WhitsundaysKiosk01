# 🔄 Complete Tour Scraping Workflow Guide

**Last Updated:** December 22, 2025

---

## 📋 Quick Reference - The Complete Process

```
1. scrape_tours.py           → Scrapes tour data from websites
2. ai_postprocess_csv.py     → Cleans and enhances data with AI
3. download_tour_media.py    → Downloads images/videos for tours
4. scrape_google_reviews_manual.py → Gets Google reviews
5. extract_precise_locations.py → Extracts departure coordinates
```

---

## 🎯 STEP-BY-STEP WORKFLOW FOR NEW TOURS

### **Step 1: Scrape Tour Data**

**File:** `scrape_tours.py`

**What it does:** Visits tour pages and extracts raw tour information

**How to use:**
```bash
# 1. Open scrape_tours.py in your editor
# 2. Add tour URLs to the TOUR_LINKS list (around line 28):

TOUR_LINKS = [ 
    "https://example-tour-company.com/tour-1",
    "https://example-tour-company.com/tour-2",
    # Add your new tour URLs here
]

# 3. Run the scraper
python scrape_tours.py
```

**Output:** Creates/updates `tours_<companyname>.csv` with raw scraped data

**What gets scraped:**
- Tour name, URL, description
- Price, duration, departure times
- What's included, itinerary, important info
- Raw HTML content for AI processing

---

### **Step 2: AI Post-Processing**

**File:** `ai_postprocess_csv.py`

**What it does:** Uses OpenAI to clean, structure, and enhance the scraped data

**How to use:**
```bash
# Process a single company
python ai_postprocess_csv.py tours_companyname.csv

# OR process all companies at once
python batch_rescrape_and_process_all.py
```

**Requirements:** 
- OpenAI API key in `.env` file:
```env
OPENAI_API_KEY=your_key_here
```

**Output:** Creates `tours_<companyname>_cleaned.csv`

**What AI does:**
- Removes HTML tags and formatting
- Structures data into proper fields
- Extracts activities, keywords, ideal_for
- Categorizes duration (half_day, full_day, multi_day)
- Cleans pricing information
- Formats itineraries, menus, inclusions

---

### **Step 3: Download Tour Images & Videos**

**File:** `download_tour_media.py`

**What it does:** Downloads all media from tour pages and updates CSV with local paths

**How to use:**
```bash
# Download media for a specific company
python download_tour_media.py tours_companyname_cleaned.csv
```

**Output:** 
- Creates `static/tour_images/<company>/<tour_name>/` folders
- Creates `tours_<companyname>_cleaned_with_media.csv`

**What it downloads:**
- Main tour images
- Gallery images
- Videos (if available)
- Filters out logos and non-tour images

---

### **Step 4: Scrape Google Reviews**

**File:** `scrape_google_reviews_manual.py`

**What it does:** Opens browser and scrapes Google reviews for each company

**How to use:**
```bash
# Scrape reviews for specific companies
python scrape_google_reviews_manual.py tours_companyname_cleaned.csv

# OR scrape reviews for all companies
python scrape_google_reviews_manual.py
```

**Interactive process:**
1. Browser opens to Google search for the company
2. YOU verify reviews are visible on the page
3. Press ENTER to scrape
4. Repeat for each company

**Output:** Creates JSON files in `tour_reviews/` directory:
- `<company>_reviews.json`

**Review data includes:**
- Overall rating
- Review count
- Individual reviews with author, date, text, rating

---

### **Step 5: Extract Departure Locations**

**File:** `extract_precise_locations.py`

**What it does:** Extracts coordinates for departure locations

**How to use:**
```bash
python extract_precise_locations.py
```

**Output:** Updates CSVs with:
- `latitude` and `longitude` fields
- Normalized `departure_location` names

**Location sources:**
1. Master locations list (`MASTER_LOCATIONS_LIST.txt`)
2. Google Maps API (if configured)
3. Manual fallback coordinates for Airlie Beach area

---

## 🚀 AUTOMATED WORKFLOW (Recommended for Multiple Companies)

If you're adding tours from multiple companies, use the batch script:

```bash
# 1. Add all tour URLs to scrape_tours.py
# 2. Run the scraper
python scrape_tours.py

# 3. Process everything automatically
python batch_rescrape_and_process_all.py
```

This will:
- ✅ AI post-process ALL raw CSVs
- ✅ Merge images back in
- ✅ Show progress for each company
- ⚠️ Takes 15-30 minutes depending on number of tours

---

## 📁 Important Files & Their Purpose

### Configuration Files
- `tour_company_homepages.txt` - List of company homepages (fallback for scraping)
- `homepage_blacklist.txt` - URLs to avoid during crawling
- `MASTER_LOCATIONS_LIST.txt` - Master list of departure locations
- `.env` - API keys (OpenAI, SendGrid, etc.)

### Data Files
- `tours_<company>.csv` - Raw scraped data
- `tours_<company>_cleaned.csv` - AI-processed data
- `tours_<company>_cleaned_with_media.csv` - Final version with local image paths
- `tour_reviews/<company>_reviews.json` - Google reviews

### Helper Scripts
- `batch_rescrape_and_process_all.py` - Process all companies at once
- `apply_master_locations.py` - Apply standardized location names
- `merge_cleaned_to_media.py` - Merge cleaned data back into media CSVs
- `audit_all_filters.py` - Check all tours have correct filter categories

---

## ⚠️ Common Issues & Solutions

### Issue: "No tours found"
**Solution:** Check if the website structure changed. Update selectors in `scrape_tours.py`

### Issue: "OpenAI API error"
**Solution:** Check your `.env` file has valid `OPENAI_API_KEY`

### Issue: "Images not downloading"
**Solution:** 
- Check internet connection
- Some sites block automated downloads
- Try running `download_tour_media.py` again

### Issue: "Reviews not scraping"
**Solution:** 
- Make sure reviews are visible in browser
- Scroll down if needed before pressing ENTER
- Check if Google changed their layout

### Issue: "Duplicate tours appearing"
**Solution:** Run `audit_all_filters.py` to identify and fix duplicates

---

## 🎯 Best Practices

### Before Scraping
1. ✅ Check if company already exists in system
2. ✅ Verify tour URLs are direct tour pages (not category pages)
3. ✅ Add company to `tour_company_homepages.txt` if new

### During Scraping
1. ✅ Monitor console output for errors
2. ✅ Check raw CSV to verify data was captured
3. ✅ Don't interrupt AI post-processing (takes time per tour)

### After Scraping
1. ✅ Review `_cleaned.csv` for accuracy
2. ✅ Check images downloaded correctly
3. ✅ Verify reviews were scraped
4. ✅ Test tours appear correctly in the app
5. ✅ Run `audit_all_filters.py` to ensure proper categorization

---

## 🔍 How to Check Your Work

### 1. Check Raw Data
```bash
# Open the raw CSV
# Look for: tour names, prices, descriptions
cat tours_companyname.csv
```

### 2. Check Cleaned Data
```bash
# Open the cleaned CSV
# Look for: structured fields, no HTML tags, proper categories
cat tours_companyname_cleaned.csv
```

### 3. Check Images
```bash
# Look in the tour images folder
ls static/tour_images/companyname/
```

### 4. Check Reviews
```bash
# Look for the reviews JSON file
cat tour_reviews/companyname_reviews.json
```

### 5. Test in Browser
```bash
# Start the app
python app.py

# Visit: http://localhost:5000
# Search for your new tours
```

---

## 📊 Workflow Summary Diagram

```
┌─────────────────────┐
│   Company Website   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  scrape_tours.py    │  ← Add URLs here
│  (Raw Scraping)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ tours_company.csv   │  (Raw data)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ ai_postprocess_csv  │  ← Needs OpenAI key
│  (AI Cleaning)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│tours_company_cleaned│  (Clean data)
│        .csv         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│download_tour_media  │  ← Downloads images
│       .py           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│tours_company_cleaned│  (With local image paths)
│   _with_media.csv   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│scrape_google_reviews│  ← Manual verification
│     _manual.py      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  tour_reviews/      │  (Reviews JSON)
│ company_reviews.json│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│extract_precise_     │  ← Adds coordinates
│   locations.py      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   FINAL CSV with    │
│ All Data + Reviews  │
│  + Images + Coords  │
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│     app.py          │
│  (Live in Kiosk!)   │
└─────────────────────┘
```

---

## 🎓 Example: Adding Tours from "Ocean Adventures"

```bash
# Step 1: Add URLs to scrape_tours.py
TOUR_LINKS = [
    "https://oceanadventures.com/reef-snorkel-tour",
    "https://oceanadventures.com/sunset-cruise",
]

# Step 2: Scrape
python scrape_tours.py
# Output: tours_oceanadventures.csv

# Step 3: AI Clean
python ai_postprocess_csv.py tours_oceanadventures.csv
# Output: tours_oceanadventures_cleaned.csv

# Step 4: Download Media
python download_tour_media.py tours_oceanadventures_cleaned.csv
# Output: tours_oceanadventures_cleaned_with_media.csv
# Images in: static/tour_images/oceanadventures/

# Step 5: Get Reviews
python scrape_google_reviews_manual.py tours_oceanadventures_cleaned.csv
# Output: tour_reviews/oceanadventures_reviews.json

# Step 6: Extract Locations
python extract_precise_locations.py
# Updates CSV with coordinates

# Step 7: Test
python app.py
# Visit localhost:5000 and search for Ocean Adventures tours
```

---

## 📞 Need Help?

Check these files for more info:
- `README.md` - General project overview
- `COMPLETE_SUCCESS_SUMMARY.md` - Recent fixes and improvements
- `changelog.txt` - Version history

---

**Ready to scrape? Start with Step 1! 🚀**

