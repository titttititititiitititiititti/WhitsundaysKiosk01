# Stable Tour IDs - Implementation Summary

## Problem Solved

### Before
- Tour IDs were generated from the scraped tour name (from `<h1>` or `<h2>`)
- If the website changed the heading text slightly, the ID would change
- **Changed IDs = broken image paths** (images are stored in `static/tour_images/<company>/<id>/`)
- You'd have to re-download all images after re-scraping

Example:
```
Old scrape: "Falls to Paradise – Waterfall Tour" → id = "falls_to_paradise___waterfall_tour"
New scrape: "Falls to Paradise Waterfall Tour"   → id = "falls_to_paradise_waterfall_tour"
```
Different ID = broken image paths! ❌

---

## Solution: URL-Based Hash IDs

### After
- Tour IDs are now generated from a **hash of the tour URL**
- URLs don't change (unless the site restructures)
- **Same URL = same ID = image paths stay valid!** ✅

Example:
```python
url = "https://redcatadventures.com.au/package/falls-to-paradise/"
id = hashlib.md5(url.encode()).hexdigest()[:16]
# Result: "a3f5c8d9e2b1f4a6" (always the same for this URL)
```

Even if the tour name changes from:
- "Falls to Paradise – Waterfall Tour" 
- to "Falls to Paradise Waterfall Tour"

The ID stays **"a3f5c8d9e2b1f4a6"** because the URL is the same.

---

## Benefits

✅ **Stable Image Paths:**  
When you re-scrape, images are still found at:
`static/tour_images/redcatadventures/a3f5c8d9e2b1f4a6/thumbnail.jpg`

✅ **No Need to Re-Download Images:**  
As long as the URL doesn't change, your existing images work with new scrapes.

✅ **Consistent Keys in App:**  
Your Flask app uses `company__id` as the key, so detail views still work.

✅ **Works Across All CSVs:**  
Raw, cleaned, and with_media CSVs all use the same stable ID.

---

## How It Works

### In `scrape_tours.py` (Line 211-216)
```python
# Generate stable ID from URL hash (so image paths don't break on re-scrape)
url_hash = hashlib.md5(url.encode()).hexdigest()[:16]

return {
    'id': url_hash,
    'name': name,
    ...
}
```

The MD5 hash is:
- **Deterministic:** Same URL always produces same hash
- **Short:** 16 characters (half of full MD5) keeps it manageable
- **Unique:** Extremely unlikely to collide (1 in 18 quintillion)

---

## What This Means for Your Workflow

### When You Re-Scrape:
1. Run `python scrape_tours.py`
2. Raw CSVs are saved with stable IDs
3. AI postprocessor runs automatically (preserves IDs)
4. Your existing `_with_media.csv` files **still work** if you don't re-run image download
5. If you do re-run image download, images are saved to the same folder (because same ID)

### When You Don't Need to Re-Download Images:
- Just re-scrape
- AI postprocessor updates tour details
- Your app still finds images at the old paths (because IDs are stable)

---

## Important Notes

### If a Website Changes URLs:
- The ID will change (because it's based on URL)
- You'll need to re-download images for that tour
- This is rare and unavoidable (URL changes = different tour resource)

### Backwards Compatibility:
- Old tours with name-based IDs will still work
- New scrapes will use hash-based IDs
- You can gradually migrate by re-downloading images with new IDs if needed

---

## Files Modified
- `scrape_tours.py` - Added `import hashlib` and changed ID generation to URL hash

## Files Created
- `STABLE_IDS_SUMMARY.md` - This file


