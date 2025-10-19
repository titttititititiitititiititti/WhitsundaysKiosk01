"""
Quick test script to demonstrate the review system

This script shows how reviews are loaded and displayed for a sample tour.
Run this to verify the review system is working correctly.
"""

import json
import os
import glob
import csv

def test_review_loading():
    """Test loading reviews for tours"""
    print("=" * 60)
    print("REVIEW SYSTEM TEST")
    print("=" * 60)
    print()
    
    # Check if review directory exists
    if not os.path.exists('tour_reviews'):
        print("❌ 'tour_reviews' directory not found!")
        print("   Run 'python scrape_reviews.py' to scrape reviews first.")
        return
    
    print("✅ Review directory found")
    print()
    
    # Count total review files
    review_files = glob.glob('tour_reviews/**/*.json', recursive=True)
    print(f"📊 Total review files: {len(review_files)}")
    print()
    
    # Load a sample tour and its reviews
    csv_files = glob.glob('*_with_media.csv')
    
    if not csv_files:
        print("❌ No tour CSV files found!")
        return
    
    print("Sample Tours with Reviews:")
    print("-" * 60)
    
    sample_count = 0
    for csvfile in csv_files[:3]:  # Check first 3 CSV files
        try:
            with open(csvfile, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    company = row['company_name']
                    tour_id = row['id']
                    tour_name = row['name']
                    
                    # Try to load reviews
                    review_file = os.path.join('tour_reviews', company, f"{tour_id}.json")
                    
                    if os.path.exists(review_file):
                        with open(review_file, 'r', encoding='utf-8') as rf:
                            review_data = json.load(rf)
                        
                        rating = review_data.get('overall_rating', 0)
                        count = review_data.get('review_count', 0)
                        num_reviews = len(review_data.get('reviews', []))
                        
                        if rating > 0:
                            stars = '★' * int(rating) + '☆' * (5 - int(rating))
                            print(f"\n✅ {tour_name}")
                            print(f"   Company: {company}")
                            print(f"   Rating: {rating:.1f}/5.0 {stars}")
                            print(f"   Review Count: {count}")
                            print(f"   Scraped Reviews: {num_reviews}")
                            
                            # Show first review snippet
                            if review_data.get('reviews'):
                                first_review = review_data['reviews'][0]
                                print(f"   First Review: \"{first_review.get('text', '')[:100]}...\"")
                            
                            sample_count += 1
                            
                            if sample_count >= 5:
                                break
                    
                    if sample_count >= 5:
                        break
                        
        except Exception as e:
            print(f"Error reading {csvfile}: {e}")
            continue
    
    if sample_count == 0:
        print("\n❌ No tours with reviews found!")
        print("   Run 'python scrape_reviews.py' to scrape reviews.")
    else:
        print()
        print("-" * 60)
        print(f"\n✅ Review system working! Found {sample_count} tours with reviews.")
        print("\n💡 Next Steps:")
        print("   1. Run 'python scrape_reviews.py' to scrape more reviews")
        print("   2. Start the Flask app: 'python app.py'")
        print("   3. Open http://localhost:5000 to see reviews in action")
    
    print()
    print("=" * 60)

if __name__ == '__main__':
    test_review_loading()



