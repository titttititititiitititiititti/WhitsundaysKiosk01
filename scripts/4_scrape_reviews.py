"""
4_scrape_reviews.py - STEP 4: Scrape Google Reviews

USAGE:
    python 4_scrape_reviews.py                           # All companies
    python 4_scrape_reviews.py tours_<company>_cleaned.csv  # Specific company

This is an INTERACTIVE script that:
    1. Opens a browser to Google search for the company
    2. YOU click "Reviews" and scroll to load reviews
    3. YOU press ENTER when reviews are visible
    4. Script extracts the reviews

Output: tour_reviews/<company>/<tour_id>.json
"""
import sys
import os

# Change to project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

if __name__ == '__main__':
    import subprocess
    
    print("=" * 70)
    print("⭐ GOOGLE REVIEWS SCRAPER")
    print("=" * 70)
    print()
    print("This is an INTERACTIVE script. You will need to:")
    print("  1. Click 'Reviews' in the browser")
    print("  2. Scroll down to load more reviews")
    print("  3. Press ENTER when reviews are visible")
    print()
    
    if len(sys.argv) > 1:
        # Specific CSV files provided
        result = subprocess.run(
            ['python', 'scrape_google_reviews_manual.py'] + sys.argv[1:],
            cwd=project_root
        )
    else:
        # Process all companies
        result = subprocess.run(
            ['python', 'scrape_google_reviews_manual.py'],
            cwd=project_root
        )

