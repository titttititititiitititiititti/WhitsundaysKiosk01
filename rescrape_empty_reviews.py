"""
Re-scrape tours that have empty reviews

This script finds all tours with empty review files and re-scrapes them
using the updated scraper with Google fallback.

Usage:
    python rescrape_empty_reviews.py
"""

import os
import json
import glob
import shutil

def find_empty_reviews():
    """Find all tours with empty reviews"""
    empty_reviews = []
    
    if not os.path.exists('tour_reviews'):
        print("No 'tour_reviews' directory found. Run scrape_reviews.py first.")
        return empty_reviews
    
    review_files = glob.glob('tour_reviews/**/*.json', recursive=True)
    
    for review_file in review_files:
        try:
            with open(review_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if reviews are empty
            if not data.get('reviews') or len(data.get('reviews', [])) == 0:
                empty_reviews.append(review_file)
        except Exception as e:
            print(f"Error reading {review_file}: {e}")
            continue
    
    return empty_reviews

def main():
    print("=" * 60)
    print("RE-SCRAPE EMPTY REVIEWS")
    print("=" * 60)
    print()
    
    # Find empty reviews
    empty_reviews = find_empty_reviews()
    
    if not empty_reviews:
        print("✅ No empty reviews found! All tours have reviews.")
        return
    
    print(f"Found {len(empty_reviews)} tours with empty reviews:")
    print()
    
    for review_file in empty_reviews[:10]:  # Show first 10
        print(f"  - {review_file}")
    
    if len(empty_reviews) > 10:
        print(f"  ... and {len(empty_reviews) - 10} more")
    
    print()
    print("=" * 60)
    print()
    
    response = input("Delete these empty review files and re-scrape? (yes/no): ").lower().strip()
    
    if response in ['yes', 'y']:
        # Delete empty review files
        for review_file in empty_reviews:
            try:
                os.remove(review_file)
                print(f"✅ Deleted: {review_file}")
            except Exception as e:
                print(f"❌ Error deleting {review_file}: {e}")
        
        print()
        print("=" * 60)
        print("Empty review files deleted!")
        print()
        print("Now run: python scrape_reviews.py")
        print()
        print("The scraper will:")
        print("  1. Skip tours with existing reviews")
        print("  2. Re-scrape tours with deleted (empty) reviews")
        print("  3. Try TripAdvisor first, then Google as fallback")
        print("=" * 60)
    else:
        print("\nCancelled. No files were deleted.")

if __name__ == '__main__':
    main()



