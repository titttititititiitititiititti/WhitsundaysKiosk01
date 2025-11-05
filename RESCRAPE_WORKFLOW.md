# 🔄 Re-scraping Tours Workflow

## Step-by-Step Guide for Updating/Adding Tours

### ✅ What This Does:
- ✓ Checks if each tour already exists in your CSVs
- ✓ **Overwrites** existing tours with fresh data
- ✓ **Adds new tours** to existing company CSVs
- ✓ **Creates new CSVs** for new companies
- ✓ Automatically runs AI post-processing
- ✓ Automatically merges to _with_media.csv files
- ✓ Shows a quality report at the end

---

## 📝 Step 1: Add Your Tour Links

1. Open `scrape_tours.py`
2. Find the `TOUR_LINKS` section (around line 28)
3. Paste your tour URLs:

```python
TOUR_LINKS = [ 
    "https://company.com/amazing-reef-tour",
    "https://company.com/whitehaven-adventure",
    "https://anothercompany.com/new-tour",
    # Add as many as you want!
]
```

---

## 🚀 Step 2: Run the Scraper

```bash
python scrape_tours.py
```

**What happens automatically:**
1. Scrapes each tour link
2. Checks if tour already exists (by tour ID/hash)
3. If exists → Overwrites with fresh data
4. If new → Adds to company's CSV
5. If new company → Creates new CSV file
6. Runs AI postprocessor on ALL company CSVs
7. Merges cleaned data to _with_media.csv files
8. Shows quality report

You'll see output like:
```
Scraping: https://company.com/tour-1
  [UPDATE] Overwriting existing tour: Reef Adventure
  Added: Reef Adventure to tours_company.csv

Scraping: https://company.com/new-tour
  [NEW] Adding new tour: Beach Paradise
  Added: Beach Paradise to tours_company.csv

Scraping: https://newcompany.com/tour
  [NEW CSV] Creating new file: tours_newcompany.csv
  [NEW] Adding new tour: Island Hopper
```

---

## 📸 Step 3: Download Images

After scraping completes, download images for your tours:

```bash
python download_tour_media.py
```

**Options:**

### Option A: Download for ALL companies
Just run it as-is, and it will process all *_cleaned_with_media.csv files

### Option B: Download for specific companies only
Open `download_tour_media.py` and modify the target files:
```python
csv_files = [
    'tours_cruisewhitsundays_cleaned_with_media.csv',
    'tours_newcompany_cleaned_with_media.csv'
]
```

---

## 🎨 Step 4: Post-Process (Already Done!)

The scraper **automatically** runs AI post-processing, but if you need to run it manually:

```bash
# For a specific company
python ai_postprocess_csv.py tours_company.csv

# This creates: tours_company_cleaned.csv
```

Then merge to _with_media:
```bash
python merge_cleaned_to_media.py
```

---

## 🔍 Step 5: Verify Your Changes

Check the final quality report that prints automatically, or manually check:

1. **Check the CSV:** Open `tours_[company]_cleaned_with_media.csv`
2. **Check your Flask app:** Restart and view at http://localhost:5000
3. **Look for:**
   - ✓ Prices populated
   - ✓ Descriptions filled
   - ✓ Images showing
   - ✓ New tours appearing

---

## 📊 Quick Reference

| Task | Command |
|------|---------|
| Scrape tours | `python scrape_tours.py` |
| Download images | `python download_tour_media.py` |
| AI post-process (manual) | `python ai_postprocess_csv.py tours_company.csv` |
| Merge to media (manual) | `python merge_cleaned_to_media.py` |
| Start Flask app | `python app.py` |

---

## 💡 Pro Tips

1. **Scraping multiple tours?** Add them all to TOUR_LINKS at once
2. **New company?** The script will automatically create a new CSV
3. **Updating old tours?** Just re-scrape the URL - it will overwrite
4. **Missing prices?** Check the `missing_price_[tourId].html` files saved for debugging
5. **Want to re-download images?** Delete the image folder and run `download_tour_media.py` again

---

## ⚠️ Important Notes

- **Tour IDs** are based on URL hash - same URL = same tour = overwrite
- **Existing data** in other fields (like reviews) will be preserved during merge
- **Always restart Flask** after updating CSVs to see changes
- The entire workflow is **automated** - just run `scrape_tours.py`!

---

## 🆘 Troubleshooting

**"No price found"**
→ Check the saved `missing_price_[id].html` file
→ Might need to adjust price selectors in the script

**"Tour not updating"**
→ Tour ID might have changed (different URL format)
→ Check if it's creating a duplicate

**"Images not downloading"**
→ Make sure `download_tour_media.py` is looking at the right CSV files
→ Check that image URLs are in the CSV

**"Tours not showing in app"**
→ Restart Flask app (`python app.py`)
→ Check that _with_media.csv file was updated






