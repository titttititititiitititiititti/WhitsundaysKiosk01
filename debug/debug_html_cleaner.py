"""
Debug the HTML cleaner to see what's going wrong
"""
from scrape_tours import fetch_html
from smart_html_cleaner import clean_html_intelligently

url = "https://explorewhitsundays.com/waltzing-matilda-sunset-cruise/"

print("Fetching page...")
html = fetch_html(url)

print(f"Original HTML length: {len(html)} chars")
print(f"First 500 chars of HTML:\n{html[:500]}\n")

print("Cleaning HTML...")
cleaned = clean_html_intelligently(html)

print(f"Cleaned text length: {len(cleaned)} chars")
print(f"First 1000 chars of cleaned text:\n{cleaned[:1000]}\n")

# Check if FAQ text is present
if "alcohol" in cleaned.lower() or "faq" in cleaned.lower() or "luggage" in cleaned.lower():
    print("✓ FAQ information found in cleaned text!")
    # Find and show the FAQ section
    idx = cleaned.lower().find("alcohol")
    if idx == -1:
        idx = cleaned.lower().find("faq")
    if idx == -1:
        idx = cleaned.lower().find("luggage")
    if idx != -1:
        print(f"\nFAQ section starts at char {idx}:")
        print(cleaned[max(0, idx-100):idx+500])
else:
    print("✗ FAQ information NOT found in cleaned text")
    print(f"\nFull cleaned text ({len(cleaned)} chars):")
    print(cleaned)
    print("\n\n=== Checking original HTML for 'alcohol' ===")
    if "alcohol" in html.lower():
        print("✓ 'alcohol' found in original HTML - cleaner is removing it!")
    else:
        print("✗ 'alcohol' not found in original HTML either")

