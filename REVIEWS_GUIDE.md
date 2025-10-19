# Tour Reviews Integration Guide

## Overview

Your tour kiosk now includes a comprehensive review system that scrapes and displays customer reviews from TripAdvisor for each tour. Reviews are displayed on both tour cards (star ratings) and full detail pages (individual reviews).

## Features

✅ **Star Ratings on Tour Cards** - Quick visual feedback on tour quality  
✅ **Full Review Display** - Detailed customer feedback on tour detail pages  
✅ **10-20 Reviews Per Tour** - Curated selection of the most helpful reviews  
✅ **Aggregate Ratings** - Overall rating score and total review count  
✅ **Source Attribution** - Links back to TripAdvisor for more reviews  
✅ **Automatic Integration** - Reviews load seamlessly with tour data  

## How It Works

### Multi-Source Review Scraping

The scraper now uses a **two-tier fallback system**:

1. **TripAdvisor First** - Tries to find and scrape reviews from TripAdvisor
2. **Google Fallback** - If TripAdvisor fails, searches Google for "[tour name] reviews" and scrapes:
   - Google Reviews (Google Maps)
   - Facebook reviews
   - Any other review site that appears first

This ensures **maximum coverage** - even tours without TripAdvisor pages can get reviews!

### 1. Review Storage
Reviews are stored in JSON files organized by company:
```
tour_reviews/
├── cruisewhitsundays/
│   ├── camira_sailing_adventure.json
│   ├── reef_explorer.json
│   └── ...
├── redcatadventures/
│   └── ...
└── ...
```

Each JSON file contains:
- **reviews**: Array of 10-20 individual reviews
- **overall_rating**: Aggregate rating (0-5 stars)
- **review_count**: Total number of reviews on TripAdvisor
- **source**: "TripAdvisor"
- **source_url**: Direct link to TripAdvisor page

### 2. Display Integration

**Tour Cards (Grid View)**:
- Star rating (★★★★☆)
- Review count (e.g., "127 reviews")
- Only shown if rating > 0

**Tour Detail Pages**:
- Overall rating score (e.g., "4.8")
- Star visualization
- Total review count
- Individual review cards with:
  - Author name
  - Date
  - Star rating
  - Review title
  - Review text
- Link to view all reviews on TripAdvisor

## Using the Review Scraper

### Prerequisites
```bash
pip install selenium undetected-chromedriver beautifulsoup4
```

### Running the Scraper

**First Time (Scrape All Tours)**:
```bash
python scrape_reviews.py
```

**Update Reviews** (skips existing):
```bash
python scrape_reviews.py
```

**Force Re-scrape** (delete tour_reviews folder first):
```bash
rmdir /s tour_reviews  # Windows
# or
rm -rf tour_reviews    # Mac/Linux

python scrape_reviews.py
```

### What the Scraper Does

1. **Loads all tours** from your `*_with_media.csv` files
2. **Searches TripAdvisor** for each tour/company
3. **If TripAdvisor found**: Scrapes 10-20 reviews from TripAdvisor
4. **If TripAdvisor fails**: 
   - Searches Google for "[tour name] reviews"
   - Finds first review source (Google Reviews, Facebook, etc.)
   - Scrapes reviews from that source
5. **Extracts**:
   - Review text and titles
   - Star ratings
   - Author names
   - Dates
   - Overall ratings
6. **Saves to JSON** for fast loading
7. **Rate limits** to avoid blocking (3-6 seconds between tours)

### Customizing TripAdvisor URLs

If the scraper can't find a tour's TripAdvisor page automatically, you can add it manually in `scrape_reviews.py`:

```python
TRIPADVISOR_COMPANY_URLS = {
    'cruisewhitsundays': 'https://www.tripadvisor.com/Attraction_Review-g255068-d2427261...',
    'yourcompany': 'https://www.tripadvisor.com/...',  # Add your URL here
    # ... more companies
}
```

## Re-scraping Empty Reviews

If you ran the scraper before the Google fallback was added, some tours might have empty review files. Use this helper script:

```bash
python rescrape_empty_reviews.py
```

This will:
1. Find all tours with empty reviews
2. Delete those empty files
3. Prompt you to re-run the scraper

Then run:
```bash
python scrape_reviews.py
```

The scraper will now use the Google fallback for those tours!

## Troubleshooting

### No Reviews Displaying

**Problem**: Tours show no star ratings  
**Solution**: 
1. Check if `tour_reviews/` folder exists
2. Run `python scrape_reviews.py` to scrape reviews
3. If some tours still empty, run `python rescrape_empty_reviews.py`
4. Restart Flask app (`python app.py`)

### Scraper Not Finding Tours

**Problem**: Scraper reports "No TripAdvisor page found"  
**Solution**: 
1. Manually search TripAdvisor for the tour company
2. Add the URL to `TRIPADVISOR_COMPANY_URLS` in `scrape_reviews.py`
3. Re-run the scraper

### Reviews Look Wrong

**Problem**: Review text is garbled or incomplete  
**Cause**: TripAdvisor changed their HTML structure  
**Solution**: 
1. The scraper uses flexible CSS selectors
2. If issues persist, update the `scrape_tripadvisor_reviews()` function
3. Check the scraped JSON files in `tour_reviews/` to verify data

### Scraper Getting Blocked

**Problem**: "Access Denied" or timeouts  
**Solution**: 
1. The scraper uses `undetected-chromedriver` to avoid detection
2. Increase delays: Change `time.sleep(random.uniform(3, 6))` to longer waits
3. Use a VPN if repeatedly blocked
4. Run scraper during off-peak hours

## Data Structure

### Review JSON Format
```json
{
  "reviews": [
    {
      "rating": 5.0,
      "title": "Amazing experience!",
      "text": "This tour was absolutely incredible...",
      "author": "John D",
      "date": "March 2024"
    }
  ],
  "overall_rating": 4.8,
  "review_count": 127,
  "source": "TripAdvisor",
  "source_url": "https://www.tripadvisor.com/..."
}
```

## Maintenance

### Updating Reviews Periodically

Since tours accumulate new reviews over time, you should periodically refresh:

1. **Monthly Update** (recommended):
   ```bash
   python scrape_reviews.py
   ```
   This will only scrape tours without existing reviews.

2. **Full Refresh** (every 6 months):
   ```bash
   rmdir /s tour_reviews
   python scrape_reviews.py
   ```

### Monitoring Review Quality

Check `tour_reviews/` folder regularly to ensure:
- All tours have review files
- Review counts seem reasonable
- Text is properly formatted

## Future Enhancements

Possible additions to the review system:
- [ ] Sort tours by rating in filters
- [ ] "Most Reviewed" filter option
- [ ] Review sentiment analysis
- [ ] Multiple review sources (Google Reviews, Facebook)
- [ ] Review response from operators
- [ ] Photo reviews from TripAdvisor

## Technical Notes

- Reviews are loaded lazily (only when needed)
- Star ratings use Unicode characters (★ ☆)
- Full reviews only load on detail pages (improves performance)
- JSON format allows easy updates and extensions
- No database required - file-based for simplicity

## Support

If you encounter issues:
1. Check the console output from `scrape_reviews.py`
2. Examine the JSON files in `tour_reviews/`
3. Verify TripAdvisor URLs are correct
4. Ensure all dependencies are installed

---

**Last Updated**: October 2024  
**Scraper Version**: 1.0

