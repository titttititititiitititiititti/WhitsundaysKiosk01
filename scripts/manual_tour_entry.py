"""
Manual Tour Entry - Paste tour info and let AI structure it

USAGE:
    python scripts/manual_tour_entry.py

For tours that don't have full pages or when multiple tours are on one page.
Paste the raw text and the AI will extract structured tour data.
"""

import os
import sys
import csv
import json
import hashlib
from datetime import datetime

# Change to project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

# Fix Windows encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import openai
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Error: Please install required packages: pip install openai python-dotenv")
    sys.exit(1)

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# CSV fields (same as the main scraper)
CSV_FIELDS = [
    'id', 'name', 'company_name', 'description', 'highlights', 'includes',
    'duration', 'departure_times', 'departure_location', 'price_adult',
    'price_child', 'price_tiers', 'age_requirements', 'ideal_for',
    'itinerary', 'menu', 'important_info', 'tags', 'tour_type',
    'intensity_level', 'group_size', 'booking_url', 'images', 'thumbnail',
    'promotion', 'source_url'
]

def generate_tour_id(name, company):
    """Generate a unique ID for the tour"""
    unique_str = f"{company}_{name}_{datetime.now().isoformat()}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:16]

def process_with_ai(raw_text, company, tour_name_hint=None):
    """Use AI to extract structured tour data from raw text"""
    
    prompt = f"""You are extracting tour information from raw text that was copied from a tour operator's website.

COMPANY: {company}
{f'TOUR NAME HINT: {tour_name_hint}' if tour_name_hint else ''}

RAW TEXT:
---
{raw_text}
---

Extract the tour information and return a JSON object with these fields:
- name: Tour name (use the hint if provided, otherwise extract from text)
- description: Full description of the tour (2-4 sentences, engaging)
- highlights: Key highlights, pipe-separated (e.g., "Snorkeling | Lunch included | Expert guides")
- includes: What's included, pipe-separated (e.g., "Equipment | Lunch | Transfers")
- duration: Duration (e.g., "Full Day", "4 hours", "2 Days 1 Night")
- departure_times: Departure times if mentioned, pipe-separated
- departure_location: Where the tour departs from
- price_adult: Adult price with currency (e.g., "A$199", "$150")
- price_child: Child price if different
- price_tiers: Different pricing tiers, pipe-separated (e.g., "Adult: $199 | Child (4-14): $99 | Family: $450")
- age_requirements: Age restrictions or requirements
- ideal_for: Who this tour is ideal for (e.g., "Families | Adventure seekers | Couples")
- itinerary: Day-by-day or step-by-step itinerary if available
- menu: Food/meal details if mentioned
- important_info: Important information, what to bring, restrictions
- tags: Relevant tags, comma-separated (e.g., "snorkeling, great barrier reef, full day")
- tour_type: Type of tour (e.g., "Day Tour", "Multi-Day", "Sailing", "Diving")
- intensity_level: Activity level (e.g., "Easy", "Moderate", "Challenging")
- group_size: Group size info if mentioned

Return ONLY valid JSON. Use empty string "" for fields you can't determine.
Be thorough - extract as much information as possible from the text."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You extract structured tour data from raw text. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"Error processing with AI: {e}")
        return None

def manual_field_entry(tour_name_hint=None, raw_text=None):
    """Manually enter tour fields when AI is unavailable"""
    print("\n" + "=" * 60)
    print("MANUAL ENTRY MODE (AI unavailable)")
    print("=" * 60)
    print("Enter tour details. Press Enter to skip optional fields.\n")
    
    def get_input(prompt, default=""):
        val = input(f"{prompt}: ").strip()
        return val if val else default
    
    def get_multiline(prompt):
        print(f"{prompt} (Enter on empty line to finish):")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        return " | ".join(lines) if lines else ""
    
    # Show raw text for reference
    if raw_text:
        print("-" * 40)
        print("REFERENCE TEXT (first 500 chars):")
        print(raw_text[:500] + "..." if len(raw_text) > 500 else raw_text)
        print("-" * 40 + "\n")
    
    tour_data = {}
    
    # Required fields
    tour_data['name'] = get_input("Tour name", tour_name_hint or "")
    if not tour_data['name']:
        print("Tour name is required!")
        return None
    
    tour_data['description'] = get_input("Description (2-3 sentences)")
    tour_data['duration'] = get_input("Duration (e.g., '2 Hours', 'Full Day', '3 Days 2 Nights')")
    tour_data['price_adult'] = get_input("Adult price (e.g., 'A$199')")
    tour_data['price_child'] = get_input("Child price (optional)")
    tour_data['price_tiers'] = get_input("Price tiers (e.g., 'Adult: A$199 | Child: A$99 | Family: A$450')")
    
    # Location & times
    tour_data['departure_location'] = get_input("Departure location")
    tour_data['departure_times'] = get_input("Departure times (e.g., '9am | 1pm')")
    
    # Details
    tour_data['includes'] = get_input("What's included (pipe-separated, e.g., 'Lunch | Equipment | Transfers')")
    tour_data['highlights'] = get_input("Highlights (pipe-separated)")
    
    # Optional detailed fields
    print("\nOptional fields (press Enter to skip):")
    tour_data['itinerary'] = get_input("Itinerary (brief)")
    tour_data['ideal_for'] = get_input("Ideal for (e.g., 'Couples | Families | Adventure seekers')")
    tour_data['age_requirements'] = get_input("Age requirements (e.g., 'Ages 12+', 'All ages')")
    tour_data['important_info'] = get_input("Important info / What to bring")
    
    # Auto-generate some fields
    tour_data['tags'] = get_input("Tags (comma-separated)", "")
    tour_data['tour_type'] = get_input("Tour type (Day Tour/Multi-Day/Sailing/etc)", "Day Tour")
    tour_data['intensity_level'] = get_input("Intensity (Easy/Moderate/Challenging)", "Moderate")
    
    print("\n[OK] Tour data collected!")
    return tour_data

def get_multiline_input(prompt_text):
    """Get multiline input from user"""
    print(prompt_text)
    print("(Paste your text, then press Enter twice to finish)")
    print("-" * 50)
    
    lines = []
    empty_count = 0
    
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break
    
    return "\n".join(lines).strip()

def save_to_csv(tour_data, company):
    """Save the tour to the company's CSV file"""
    
    # Normalize company name - extract just the company part if path was included
    company = company.replace('\\', '/').split('/')[-1] if '\\' in company or '/' in company else company
    company = company.strip()
    
    # Find or create CSV file
    csv_patterns = [
        f'data/{company}/en/tours_{company}_cleaned_with_media.csv',
        f'tours_{company}_cleaned_with_media.csv',
        f'tours_{company}_cleaned.csv',
    ]
    
    csv_file = None
    existing_tours = []
    
    for pattern in csv_patterns:
        if os.path.exists(pattern):
            csv_file = pattern
            break
    
    if not csv_file:
        # Create new CSV in data folder
        os.makedirs(f'data/{company}/en', exist_ok=True)
        csv_file = f'data/{company}/en/tours_{company}_cleaned_with_media.csv'
        print(f"Creating new CSV: {csv_file}")
    else:
        # Read existing tours
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_tours = list(reader)
        except Exception as e:
            print(f"Warning: Could not read existing CSV: {e}")
    
    # Add the new tour
    existing_tours.append(tour_data)
    
    # Write all tours back
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for tour in existing_tours:
            # Ensure all fields exist
            row = {field: tour.get(field, '') for field in CSV_FIELDS}
            writer.writerow(row)
    
    return csv_file

def main():
    print("=" * 70)
    print("MANUAL TOUR ENTRY")
    print("=" * 70)
    print()
    print("Use this to add tours that don't have full pages,")
    print("or when multiple tours are listed on one page.")
    print()
    
    # Get company name
    print("Available companies (or enter a new one):")
    
    # List existing companies
    companies = set()
    import glob
    for pattern in ['data/*/en', 'tours_*_cleaned*.csv']:
        for path in glob.glob(pattern):
            # Normalize path separators for cross-platform compatibility
            normalized_path = path.replace('\\', '/')
            if 'data/' in normalized_path:
                # Extract company name from data/{company}/en
                parts = normalized_path.split('/')
                if len(parts) >= 2:
                    company = parts[1]  # data/{company}/en -> company is at index 1
                    companies.add(company)
            else:
                # Extract from tours_{company}_cleaned.csv
                company = path.replace('tours_', '').split('_cleaned')[0]
                companies.add(company)
    
    for i, comp in enumerate(sorted(companies), 1):
        print(f"  {i}. {comp}")
    
    print()
    company_input = input("Enter company name or number: ").strip()
    
    # Handle numeric selection
    if company_input.isdigit():
        idx = int(company_input) - 1
        sorted_companies = sorted(companies)
        if 0 <= idx < len(sorted_companies):
            company = sorted_companies[idx]
        else:
            company = company_input
    else:
        company = company_input.lower().replace(' ', '-').replace('_', '-')
    
    print(f"\nUsing company: {company}")
    
    # Loop to add multiple tours
    while True:
        print()
        print("=" * 70)
        print("ADD NEW TOUR")
        print("=" * 70)
        
        # Get tour name (optional hint)
        tour_name = input("\nTour name (optional, AI can detect it): ").strip()
        
        # Get raw text
        print()
        raw_text = get_multiline_input("Paste the tour information:")
        
        if not raw_text:
            print("No text provided, skipping...")
            continue
        
        print()
        print("Processing with AI...")
        
        # Process with AI
        tour_data = process_with_ai(raw_text, company, tour_name if tour_name else None)
        
        if not tour_data:
            print("\n[!] AI processing failed. Falling back to manual entry...")
            use_manual = input("Would you like to enter fields manually? (y/n): ").strip().lower()
            if use_manual == 'y':
                tour_data = manual_field_entry(tour_name, raw_text)
                if not tour_data:
                    print("Manual entry cancelled")
                    continue
            else:
                print("Skipping this tour...")
                continue
        
        # Add required fields
        tour_id = generate_tour_id(tour_data.get('name', 'unknown'), company)
        tour_data['id'] = tour_id
        tour_data['company_name'] = company
        tour_data['source_url'] = 'manual_entry'
        tour_data['images'] = ''
        tour_data['thumbnail'] = ''
        tour_data['promotion'] = ''
        tour_data['booking_url'] = ''
        
        # Display extracted data
        print()
        print("=" * 70)
        print("EXTRACTED TOUR DATA")
        print("=" * 70)
        print(f"Name: {tour_data.get('name', 'N/A')}")
        print(f"ID: {tour_id}")
        print(f"Duration: {tour_data.get('duration', 'N/A')}")
        print(f"Price: {tour_data.get('price_adult', 'N/A')}")
        print(f"Type: {tour_data.get('tour_type', 'N/A')}")
        print()
        print("Description:")
        print(f"  {tour_data.get('description', 'N/A')[:200]}...")
        print()
        print("Highlights:")
        print(f"  {tour_data.get('highlights', 'N/A')}")
        print()
        print("Includes:")
        print(f"  {tour_data.get('includes', 'N/A')}")
        print()
        
        # Confirm save
        save = input("Save this tour? (y/n): ").strip().lower()
        
        if save == 'y':
            csv_file = save_to_csv(tour_data, company)
            print(f"\n[OK] Tour saved to {csv_file}")
            print(f"     Tour ID: {tour_id}")
        else:
            print("Tour discarded")
        
        # Ask to continue
        print()
        another = input("Add another tour? (y/n): ").strip().lower()
        if another != 'y':
            break
    
    print()
    print("=" * 70)
    print("Done!")
    print("=" * 70)

if __name__ == '__main__':
    main()


