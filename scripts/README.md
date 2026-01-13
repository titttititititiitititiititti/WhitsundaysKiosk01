# 🎯 Tour Processing Scripts

This folder contains all the scripts needed to add new tours to your kiosk project.

## 📋 The Complete Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: SCRAPE                                                             │
│  ─────────────────                                                          │
│  Script: 1_scrape_tours.py                                                  │
│  Input:  Tour URLs (paste into TOUR_LINKS list)                             │
│  Output: tours_<company>.csv (raw scraped data)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: AI CLEAN                                                           │
│  ─────────────────                                                          │
│  Script: 2_ai_postprocess.py                                                │
│  Input:  tours_<company>.csv                                                │
│  Output: tours_<company>_cleaned.csv (AI-structured data)                   │
│  Note:   Requires OpenAI API key in .env file                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: DOWNLOAD MEDIA                                                     │
│  ─────────────────────                                                      │
│  Script: 3_download_media.py                                                │
│  Input:  tours_<company>_cleaned.csv                                        │
│  Output: tours_<company>_cleaned_with_media.csv                             │
│          + static/tour_images/<company>/<tour>/ folders                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: SCRAPE REVIEWS                                                     │
│  ─────────────────────                                                      │
│  Script: 4_scrape_reviews.py                                                │
│  Input:  tours_<company>_cleaned.csv (company names)                        │
│  Output: tour_reviews/<company>/<tour_id>.json                              │
│  Note:   Interactive - requires manual browser steps                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: EXTRACT LOCATIONS                                                  │
│  ──────────────────────────                                                 │
│  Script: 5_extract_locations.py                                             │
│  Input:  All tours_*_cleaned_with_media.csv files                           │
│  Output: Updated CSVs with departure_location field                         │
│          + locations_detailed_report.txt                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ✅ DONE! Restart app.py to see new tours                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start: Add a New Tour Company

```bash
# 1. Open 1_scrape_tours.py and paste your tour URLs into TOUR_LINKS
# 2. Run the full workflow:
cd scripts
python 1_scrape_tours.py

# The scraper automatically runs AI postprocessing after scraping!
# For the remaining steps:
python 3_download_media.py ../tours_<company>_cleaned.csv
python 4_scrape_reviews.py ../tours_<company>_cleaned.csv
python 5_extract_locations.py
```

## 📦 Script Files Reference

| Script | Purpose | Time | Notes |
|--------|---------|------|-------|
| `1_scrape_tours.py` | Scrape tour data from websites | 1-5 min | Paste URLs in TOUR_LINKS |
| `2_ai_postprocess.py` | Clean data with AI | 2-5 min per tour | Needs OpenAI API key |
| `3_download_media.py` | Download images/videos | 1-3 min per tour | Uses Selenium |
| `4_scrape_reviews.py` | Get Google reviews | 2-5 min per company | Interactive/manual |
| `5_extract_locations.py` | Extract departure coords | 1-2 min | Uses AI |
| `batch_process_all.py` | Process all companies | 30-60 min | Full automation |
| `merge_cleaned_to_media.py` | Merge cleaned → media CSV | 10 sec | Preserves images |
| `audit_filters.py` | Verify filter categories | 5 sec | Quality check |

## ⚙️ Requirements

Make sure you have these in your `.env` file:
```
OPENAI_API_KEY=your_key_here
```

And these Python packages:
```
pip install pandas selenium beautifulsoup4 requests openai python-dotenv pillow undetected-chromedriver
```

## 🔍 Troubleshooting

**"No price found"** → Website may need Selenium. The scraper auto-detects this.

**"OpenAI API error"** → Check your .env file has a valid OPENAI_API_KEY

**"Images not downloading"** → Some sites block bots. Check static/tour_images/ folder.

**Tours not showing in app** → Make sure you restart `python app.py`

