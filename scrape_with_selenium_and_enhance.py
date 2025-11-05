"""
Complete workflow using Selenium to capture FAQs, then AI to extract booking details

USAGE:
  python scrape_with_selenium_and_enhance.py sailing-whitsundays explorewhitsundays
  
FEATURES:
  ✓ Loads pages with Selenium (captures JavaScript FAQs)
  ✓ Expands all FAQ accordions automatically
  ✓ AI extracts booking details (what to bring, BYO policies, cancellations, etc.)
  ✓ Updates CSV files - ready to display immediately!
"""
import csv
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
import sys
import time

# Import our selenium scraper
from selenium_scraper_with_faqs import fetch_with_selenium
from scrape_tours import extract_tour_info
from smart_html_cleaner import clean_html_intelligently

load_dotenv()

# Get company names from command line
if len(sys.argv) > 1:
    COMPANIES = sys.argv[1:]
else:
    print("Usage: python scrape_with_selenium_and_enhance.py <company1> <company2> ...")
    print("Example: python scrape_with_selenium_and_enhance.py sailing-whitsundays explorewhitsundays")
    sys.exit(1)

print("=" * 80)
print(f"SCRAPE + ENHANCE WITH SELENIUM")
print("=" * 80)
print(f"Companies to process: {', '.join(COMPANIES)}")
print("This will take 10-15 seconds per tour (Selenium + AI processing)")
print("=" * 80)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Process each company
for company_idx, COMPANY in enumerate(COMPANIES, 1):
    print(f"\n\n{'='*80}")
    print(f"[{company_idx}/{len(COMPANIES)}] PROCESSING: {COMPANY.upper()}")
    print(f"{'='*80}")
    
    # Normalize company name - handle both "sailing-whitsundays" and "tours_sailing-whitsundays.csv"
    if COMPANY.endswith('.csv'):
        # User passed full filename like "tours_sailing-whitsundays.csv"
        company_name = COMPANY.replace('tours_', '').replace('.csv', '')
        csv_file = f'tours_{company_name}_cleaned_with_media.csv'
    else:
        # User passed just company name like "sailing-whitsundays"
        company_name = COMPANY
        csv_file = f'tours_{company_name}_cleaned_with_media.csv'
    
    print(f"Looking for: {csv_file}")
    
    try:
        df = pd.read_csv(csv_file)
        urls = df['link_more_info'].dropna().tolist()
        print(f"\nFound {len(urls)} tours to process")
    except Exception as e:
        print(f"Error: Could not find {csv_file}: {e}")
        print(f"Skipping {COMPANY}...")
        continue

    # Step 1: Scrape tours with Selenium (expanding FAQs)
    print(f"\n[1/3] Scraping {len(urls)} tours with Selenium...")
    tours_with_content = []

    for idx, url in enumerate(urls, 1):
        print(f"  [{idx}/{len(urls)}] {url}...")
        try:
            # Fetch with Selenium (expands FAQs)
            html = fetch_with_selenium(url, expand_faqs=True)
            
            # Extract tour info
            tour = extract_tour_info(html, url)
            
            if tour:
                # Store both raw_html and raw_text
                tour['raw_html_selenium'] = html
                tours_with_content.append(tour)
                print(f"      ✓ Got {len(html)} chars of content")
            else:
                print(f"      ✗ Could not extract tour info")
        except Exception as e:
            print(f"      ✗ Error: {e}")

    print(f"\n✓ Successfully scraped {len(tours_with_content)}/{len(urls)} tours")

    # Step 2: Use AI to extract booking details
    print(f"\n[2/3] Extracting booking details with AI...")
    enhanced_tours = []

    for idx, tour in enumerate(tours_with_content, 1):
        tour_name = tour.get('name', 'Unknown')
        raw_html = tour.get('raw_html_selenium', '')
        
        # Clean the HTML
        cleaned_text = clean_html_intelligently(raw_html) if raw_html else tour.get('raw_text', '')
        
        print(f"  [{idx}/{len(tours_with_content)}] {tour_name}...")
        print(f"      Cleaned: {len(raw_html)} -> {len(cleaned_text)} chars")
        
        # AI prompt - flexible to work with any section names
        prompt = f"""You are extracting booking information from a tour website. The page text includes all content (FAQs have been expanded).

TOUR PAGE TEXT:
{cleaned_text[:15000]}

Extract these 4 types of information if present anywhere on the page (regardless of section titles):

1. important_information: Any critical requirements or restrictions guests MUST know:
   - Age limits, minimum/maximum ages
   - Fitness or health requirements
   - Swimming ability needed
   - Supervision requirements (children, adults)
   - Medical restrictions
   - Guest limitations
   Return as bullet points if found, otherwise null.

2. what_to_bring: Items guests should pack or bring:
   - Clothing recommendations
   - Personal items (sunscreen, hat, sunglasses, towel)
   - Equipment they need to bring
   - Toiletries
   Return as bullet points if found, otherwise null.

3. whats_extra: Costs, policies, or services NOT included in the base price:
   - BYO policies (alcohol, food, drinks)
   - Additional costs or optional extras
   - Luggage storage information
   - Transfer costs
   - Items NOT included
   Return as bullet points if found, otherwise null.

4. cancellation_policy: Cancellation, refund, and booking terms:
   - How many hours/days notice for refund
   - Refund percentage or terms
   - No-show policy
   - Booking conditions
   Keep the EXACT wording if found, otherwise null.

Return ONLY valid JSON with these 4 keys. Use null (not empty string) if information is not found.
Do NOT make up information - only extract what is explicitly stated on the page."""

        # Try with timeout and retry
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Extract structured info from tour text. Return valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=1500,
                    timeout=30.0
                )
                
                result_text = response.choices[0].message.content.strip()
                
                # Clean markdown
                if result_text.startswith('```'):
                    result_text = result_text.split('```')[1]
                    if result_text.startswith('json'):
                        result_text = result_text[4:]
                    result_text = result_text.strip()
                
                data = json.loads(result_text)
                
                # Add to tour data
                tour['important_information'] = str(data.get('important_information', '')).strip() if data.get('important_information') else ''
                tour['what_to_bring'] = str(data.get('what_to_bring', '')).strip() if data.get('what_to_bring') else ''
                tour['whats_extra'] = str(data.get('whats_extra', '')).strip() if data.get('whats_extra') else ''
                tour['cancellation_policy'] = str(data.get('cancellation_policy', '')).strip() if data.get('cancellation_policy') else ''
                
                found = []
                if tour['important_information']: found.append('important_info')
                if tour['what_to_bring']: found.append('what_to_bring')
                if tour['whats_extra']: found.append('whats_extra')
                if tour['cancellation_policy']: found.append('cancellation')
                
                if found:
                    print(f"      ✓ Found: {', '.join(found)}")
                else:
                    print(f"      - No booking details found")
                    
                enhanced_tours.append(tour)
                break  # Success
                        
            except (KeyboardInterrupt, TimeoutError, Exception) as e:
                if attempt < max_retries - 1:
                    print(f"      ⚠ Retry {attempt + 1}/{max_retries}: {type(e).__name__}")
                    time.sleep(2)
                else:
                    print(f"      ✗ Failed after {max_retries} attempts")
                    tour['important_information'] = ''
                    tour['what_to_bring'] = ''
                    tour['whats_extra'] = ''
                    tour['cancellation_policy'] = ''
                    enhanced_tours.append(tour)

    # Step 3: Merge with existing CSV
    print(f"\n[3/3] Merging with {csv_file}...")

    df_media = pd.read_csv(csv_file)

    # Ensure new columns exist
    new_cols = ['important_information', 'what_to_bring', 'whats_extra', 'cancellation_policy']
    for col in new_cols:
        if col not in df_media.columns:
            df_media[col] = ''

    # Update rows
    updated_count = 0
    for tour in enhanced_tours:
        tour_id = tour['id']
        mask = df_media['id'] == tour_id
        if mask.any():
            for col in new_cols:
                df_media.loc[mask, col] = tour.get(col, '')
            updated_count += 1
            print(f"  ✓ Updated: {tour.get('name', tour_id)}")

    df_media.to_csv(csv_file, index=False)
    print(f"\n✓ Updated {updated_count} tours in {csv_file}")

    # Summary for this company
    print("\n" + "=" * 80)
    print(f"✅ {COMPANY.upper()} COMPLETE!")
    print("=" * 80)
    print(f"Results for {COMPANY}:")
    for col in new_cols:
        count = df_media[col].astype(str).str.strip().ne('').sum()
        print(f"  - {col}: {count}/{len(df_media)} tours")

# Final summary
print("\n\n" + "=" * 80)
print("✅ ALL COMPANIES PROCESSED!")
print("=" * 80)
print(f"Processed {len(COMPANIES)} companies: {', '.join(COMPANIES)}")
print("\n💡 Your CSVs are updated and ready!")
print("💡 Refresh your browser to see the new booking details!")
print("=" * 80)
