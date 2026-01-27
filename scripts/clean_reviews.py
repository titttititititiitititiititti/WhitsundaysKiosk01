"""
Clean Reviews - Remove owner responses from existing review files

USAGE:
    python scripts/clean_reviews.py                    # Clean all reviews
    python scripts/clean_reviews.py cruisewhitsundays  # Clean specific company
"""

import os
import sys
import json
import re
import glob

# Change to project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

REVIEWS_DIR = 'tour_reviews'

def is_owner_response(text):
    """Check if text is an owner/business response, not a customer review"""
    text_lower = text.lower()
    
    # Owner response indicators at the START of text
    owner_start_patterns = [
        '(owner)',
        'owner)',
        'response from',
        'thank you for',
        'thanks for',
        'thank you so much',
        'thanks so much',
        "we're thrilled",
        "we're delighted",
        "we're so glad",
        "we're so happy",
        "we are thrilled",
        "we are delighted",
        "we truly appreciate",
        "we really appreciate",
        "we appreciate",
        "we hope to see you",
        "we hope to welcome",
        "we can't wait to",
        "we look forward",
        "hi there,",
        "hello,",
        "dear guest",
    ]
    
    # Check if text starts with owner patterns
    for pattern in owner_start_patterns:
        if text_lower.startswith(pattern):
            return True
    
    # Owner response patterns ANYWHERE in text
    owner_anywhere_patterns = [
        '(owner)',
        'owner)',
        ' (owner',
        'tours (owner',
        'whitsundays (owner',
        'adventures (owner',
        'sailing (owner',
        'cruises (owner',
        'we\'re stoked',
        'we\'ll be sure to pass',
        'the team will be',
        'our team will be',
        'thanks again for',
        'thank you again for',
        'we can\'t wait to welcome you back',
        'hope to welcome you back',
        'hope to see you again',
        'we hope you\'ll',
        'will be stoked to hear',
        'will be delighted to hear',
        'will be over the moon',
    ]
    
    for pattern in owner_anywhere_patterns:
        if pattern in text_lower:
            return True
    
    # Check for company name followed by common owner response starters
    if re.search(r'^[A-Z][a-zA-Z\s]+\s*\(owner\)', text):
        return True
    
    # Check for timestamps typical of owner responses
    if re.match(r'^(\d+\s+(days?|weeks?|months?|years?)\s+ago)', text_lower):
        return True
    
    # If it starts with "we" and sounds like a business response
    if text_lower.startswith('we ') or text_lower.startswith("we'"):
        business_response_phrases = [
            'we appreciate', 'we are so', 'we are glad', 'we are happy',
            'we\'re glad', 'we\'re happy', 'we\'re so', 'we\'re thrilled',
            'we hope', 'we look forward', 'we truly', 'we really'
        ]
        if any(text_lower.startswith(phrase) for phrase in business_response_phrases):
            return True
    
    return False

def is_random_text(text):
    """Check if text is random website content, not a review"""
    text_lower = text.lower()
    
    # Keywords that suggest random website text
    random_keywords = [
        'book now', 'add to cart', 'checkout', 'subscribe',
        'newsletter', 'contact us', 'about us', 'our team',
        'privacy policy', 'terms of service', 'cookie',
        'copyright', 'all rights reserved', 'powered by',
        'navigation', 'menu', 'services',
        'follow us', 'social media',
        'phone:', 'email:', 'address:', 'abn:', 'acn:',
        'frequently asked', 'faq', 'cancellation policy',
        'booking conditions', 'terms and conditions',
        'click here', 'learn more', 'read more',
        'response from the owner', 'owner response'
    ]
    
    if any(kw in text_lower for kw in random_keywords):
        return True
    
    # Check if it lacks review-like language
    review_indicators = [
        ' i ', ' my ', ' we ', ' our ', ' me ',
        'had a', 'was a', 'such a', 'what a',
        'experience', 'trip', 'tour', 'day', 'time',
        'amazing', 'great', 'fantastic', 'awesome', 'wonderful',
        'recommend', 'loved', 'enjoyed', 'beautiful', 'stunning',
        'staff', 'crew', 'guide', 'instructor', 'captain',
        'boat', 'snorkel', 'dive', 'beach', 'reef', 'island'
    ]
    
    has_review_indicator = any(ind in text_lower for ind in review_indicators)
    
    # If very short and no review indicators, it's probably random
    if len(text) < 100 and not has_review_indicator:
        return True
    
    return False

def clean_reviews_file(filepath):
    """Clean a single reviews file, removing owner responses and random text"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return 0, 0
    
    if 'reviews' not in data:
        return 0, 0
    
    original_count = len(data['reviews'])
    cleaned_reviews = []
    removed_count = 0
    
    for review in data['reviews']:
        text = review.get('text', '')
        
        if is_owner_response(text):
            removed_count += 1
            continue
        
        if is_random_text(text):
            removed_count += 1
            continue
        
        cleaned_reviews.append(review)
    
    if removed_count > 0:
        data['reviews'] = cleaned_reviews
        
        # Recalculate review count if we have it
        if 'review_count' in data and data['review_count'] == original_count:
            # Only update if it was tracking actual review count
            data['review_count'] = len(cleaned_reviews)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    return original_count, removed_count

def main():
    # Fix Windows encoding
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("REVIEW CLEANER - Remove Owner Responses & Random Text")
    print("=" * 70)
    print()
    
    # Check for specific company argument
    target_company = None
    if len(sys.argv) > 1:
        target_company = sys.argv[1]
        print(f"Targeting company: {target_company}")
    
    # Find all review files
    if target_company:
        review_files = glob.glob(f'{REVIEWS_DIR}/{target_company}/*.json')
    else:
        review_files = glob.glob(f'{REVIEWS_DIR}/**/*.json', recursive=True)
    
    print(f"Found {len(review_files)} review files\n")
    
    total_original = 0
    total_removed = 0
    files_cleaned = 0
    
    for filepath in review_files:
        original, removed = clean_reviews_file(filepath)
        total_original += original
        total_removed += removed
        
        if removed > 0:
            files_cleaned += 1
            relative_path = os.path.relpath(filepath)
            print(f"  [OK] {relative_path}: {original} -> {original - removed} reviews (-{removed})")
    
    print()
    print("=" * 70)
    print(f"COMPLETE")
    print(f"   Files cleaned: {files_cleaned}")
    print(f"   Reviews before: {total_original}")
    print(f"   Reviews removed: {total_removed}")
    print(f"   Reviews after: {total_original - total_removed}")
    print("=" * 70)

if __name__ == '__main__':
    main()

