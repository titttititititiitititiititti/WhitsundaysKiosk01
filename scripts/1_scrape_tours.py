"""
1_scrape_tours.py - STEP 1: Scrape Tour Data

USAGE:
    1. Paste your tour URLs into the TOUR_LINKS list below
    2. Run: python 1_scrape_tours.py
    3. This will create tours_<company>.csv and auto-run AI processing

The script will:
    - Visit each tour URL
    - Extract tour info (name, price, duration, etc.)
    - Save to tours_<company>.csv
    - Auto-run AI post-processing to clean the data
"""
import sys
import os

# Add parent directory to path so we can import the main script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================================
# PASTE YOUR TOUR LINKS HERE (one per line, with commas!)
# ============================================================================
TOUR_LINKS = [

    "https://www.sealink.com.au/whitsundays/experiences/whitehaven-beach-big-island-day-tour/",
]
# ============================================================================

if __name__ == '__main__':
    if not TOUR_LINKS:
        print("=" * 70)
        print("📝 HOW TO USE THIS SCRIPT")
        print("=" * 70)
        print()
        print("1. Open this file (1_scrape_tours.py) in your editor")
        print()
        print("2. Find the TOUR_LINKS list near the top and add your URLs:")
        print()
        print('   TOUR_LINKS = [')
        print('       "https://example-company.com/tour-1",')
        print('       "https://example-company.com/tour-2",')
        print('   ]')
        print()
        print("3. Save the file and run it again:")
        print("   python 1_scrape_tours.py")
        print()
        print("=" * 70)
        sys.exit(0)
    
    # Import and update the main scraper's TOUR_LINKS
    import scrape_tours
    scrape_tours.TOUR_LINKS = TOUR_LINKS
    
    print("=" * 70)
    print(f"🚀 STARTING SCRAPE: {len(TOUR_LINKS)} tours")
    print("=" * 70)
    print()
    
    # Run the main scraper
    scrape_tours.main()

