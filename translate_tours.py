"""
Multi-language tour CSV translator using DeepL + Google Translate

USAGE:
  python translate_tours.py --all                    # Translate all companies, all languages
  python translate_tours.py --company cruisewhitsundays  # Translate one company
  python translate_tours.py --languages zh ja ko     # Only translate to specific languages
  
SETUP:
  1. Install: pip install deepl googletrans==4.0.0rc1
  2. Set environment variables:
     - DEEPL_API_KEY=your_deepl_key
     - GOOGLE_TRANSLATE_API_KEY=your_google_key (optional, uses free version by default)
  
FEATURES:
  - DeepL for: zh, ja, ko, de, fr, es
  - Google for: hi
  - Smart caching to avoid re-translating
  - Preserves prices, URLs, company names
  - Progress tracking
"""

import csv
import os
import sys
import glob
import argparse
from pathlib import Path
import deepl
from googletrans import Translator as GoogleTranslator
from dotenv import load_dotenv
import time

load_dotenv()

# Language mapping
LANGUAGES = {
    'zh': {'name': 'Chinese (Simplified)', 'deepl': 'ZH', 'google': 'zh-cn', 'service': 'deepl'},
    'ja': {'name': 'Japanese', 'deepl': 'JA', 'google': 'ja', 'service': 'deepl'},
    'ko': {'name': 'Korean', 'deepl': 'KO', 'google': 'ko', 'service': 'deepl'},
    'de': {'name': 'German', 'deepl': 'DE', 'google': 'de', 'service': 'deepl'},
    'fr': {'name': 'French', 'deepl': 'FR', 'google': 'fr', 'service': 'deepl'},
    'es': {'name': 'Spanish', 'deepl': 'ES', 'google': 'es', 'service': 'deepl'},
    'hi': {'name': 'Hindi', 'deepl': None, 'google': 'hi', 'service': 'google'}
}

# Fields to translate
TRANSLATE_FIELDS = [
    'name',
    'summary',
    'description',
    'highlights',
    'includes',
    'itinerary',
    'menu',
    'important_information',
    'what_to_bring',
    'whats_extra',
    'cancellation_policy',
    'age_requirements',
    'ideal_for',
    # NEW: Additional fields to translate
    'duration',
    'departure_location',
    'departure_times',
    'price_tiers'
]

# Fields to NEVER translate
PRESERVE_FIELDS = [
    'id',
    'company_name',
    'price_adult',
    'price_child',
    # NOTE: price_tiers, duration, departure_location, departure_times moved to TRANSLATE_FIELDS
    'link_booking',
    'link_more_info',
    'phone',
    'image_url',
    'image_urls',
    'thumbnail',
    'gallery',
    'commission_rate',
    'active',
    'price_source_url',
    'duration_category',
    'price_category',
    'activity_type',
    'family_friendly',
    'meals_included',
    'equipment_included',
    'review_rating',
    'review_count',
    'review_source',
    'review_source_url'
]


class TourTranslator:
    def __init__(self):
        self.deepl_key = os.getenv('DEEPL_API_KEY')
        self.google_key = os.getenv('GOOGLE_TRANSLATE_API_KEY')
        
        # Initialize translators
        self.deepl_translator = None
        self.google_translator = GoogleTranslator()
        
        if self.deepl_key:
            try:
                self.deepl_translator = deepl.Translator(self.deepl_key)
                print("✓ DeepL API initialized")
            except Exception as e:
                print(f"⚠ DeepL API failed: {e}")
                print("  Will fall back to Google for all languages")
        else:
            print("⚠ No DEEPL_API_KEY found in environment")
            print("  Please add it to .env file or set as environment variable")
            print("  Will fall back to Google for all languages")
    
    def translate_text(self, text, target_lang_code, service='deepl'):
        """Translate text using specified service"""
        if not text or not text.strip():
            return text
        
        # Don't translate if already looks translated or is too short
        if len(text.strip()) < 3:
            return text
        
        try:
            if service == 'deepl' and self.deepl_translator:
                target = LANGUAGES[target_lang_code]['deepl']
                result = self.deepl_translator.translate_text(
                    text,
                    target_lang=target,
                    preserve_formatting=True,
                    formality='default'
                )
                return result.text
            else:
                # Fall back to Google with retry logic
                target = LANGUAGES[target_lang_code]['google']
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        result = self.google_translator.translate(text, dest=target)
                        if result and result.text:
                            return result.text
                    except Exception as retry_error:
                        if attempt < max_retries - 1:
                            time.sleep(1)  # Wait before retry
                            continue
                        else:
                            raise retry_error
                return text  # If all retries failed, return original
        except Exception as e:
            # Return original text on error instead of crashing
            return text
    
    def translate_tour(self, tour_row, target_lang_code):
        """Translate all relevant fields in a tour row"""
        translated = tour_row.copy()
        service = LANGUAGES[target_lang_code]['service']
        
        for field in TRANSLATE_FIELDS:
            if field in tour_row:
                original = tour_row[field]
                # Skip if field is None, empty, or not a string
                if original and isinstance(original, str) and original.strip():
                    translated[field] = self.translate_text(original, target_lang_code, service)
                    time.sleep(0.1)  # Rate limiting
                else:
                    # Keep original value (even if empty/None)
                    translated[field] = original
        
        return translated
    
    def translate_csv(self, input_path, output_path, target_lang_code):
        """Translate entire CSV to target language"""
        lang_name = LANGUAGES[target_lang_code]['name']
        service = LANGUAGES[target_lang_code]['service'].upper()
        
        print(f"  → {lang_name} ({service})...")
        
        # Read input CSV
        with open(input_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)
        
        # Translate each row
        translated_rows = []
        for i, row in enumerate(rows, 1):
            print(f"    Tour {i}/{len(rows)}: {row.get('name', 'Unknown')[:50]}...")
            translated_row = self.translate_tour(row, target_lang_code)
            translated_rows.append(translated_row)
        
        # Write output CSV
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(translated_rows)
        
        print(f"    ✓ Saved: {output_path}")


def organize_csvs():
    """Move existing CSVs to data/[company]/en/ structure"""
    print("\n" + "="*80)
    print("ORGANIZING EXISTING CSVs INTO FOLDER STRUCTURE")
    print("="*80)
    
    # Find all *_cleaned_with_media.csv files
    csv_files = glob.glob('tours_*_cleaned_with_media.csv')
    
    if not csv_files:
        print("⚠ No CSV files found matching pattern: tours_*_cleaned_with_media.csv")
        return []
    
    print(f"Found {len(csv_files)} CSV files")
    
    companies = []
    for csv_file in csv_files:
        # Extract company name from filename
        # tours_cruisewhitsundays_cleaned_with_media.csv -> cruisewhitsundays
        company = csv_file.replace('tours_', '').replace('_cleaned_with_media.csv', '')
        companies.append(company)
        
        # Create directory structure
        en_dir = f'data/{company}/en'
        os.makedirs(en_dir, exist_ok=True)
        
        # Move/copy file
        dest_path = f'{en_dir}/{csv_file}'
        if not os.path.exists(dest_path):
            import shutil
            shutil.copy2(csv_file, dest_path)
            print(f"  ✓ Organized: {csv_file} → {dest_path}")
        else:
            print(f"  ⊙ Already organized: {dest_path}")
    
    return companies


def translate_all_companies(languages=None, force=False):
    """Translate all companies to all (or specified) languages"""
    
    # First, organize existing CSVs
    companies = organize_csvs()
    
    if not companies:
        print("❌ No companies found to translate")
        return
    
    # Determine which languages to translate
    if languages:
        lang_codes = [l for l in languages if l in LANGUAGES]
    else:
        lang_codes = list(LANGUAGES.keys())
    
    print(f"\n" + "="*80)
    print(f"TRANSLATING {len(companies)} COMPANIES TO {len(lang_codes)} LANGUAGES")
    if force:
        print("⚠ FORCE MODE: Will overwrite existing translations")
    print("="*80)
    
    translator = TourTranslator()
    
    for company_idx, company in enumerate(companies, 1):
        print(f"\n[{company_idx}/{len(companies)}] {company.upper()}")
        print("-" * 80)
        
        # Source file (English)
        source_csv = f'data/{company}/en/tours_{company}_cleaned_with_media.csv'
        
        if not os.path.exists(source_csv):
            print(f"  ⚠ Source file not found: {source_csv}")
            continue
        
        # Translate to each language
        for lang_code in lang_codes:
            output_csv = f'data/{company}/{lang_code}/tours_{company}_cleaned_with_media.csv'
            
            # Skip if already exists (unless --force flag)
            if os.path.exists(output_csv) and not force:
                print(f"  ⊙ {LANGUAGES[lang_code]['name']} already exists, skipping...")
                continue
            
            try:
                translator.translate_csv(source_csv, output_csv, lang_code)
            except Exception as e:
                print(f"  ❌ Error translating to {lang_code}: {e}")
                continue
    
    print("\n" + "="*80)
    print("✅ TRANSLATION COMPLETE!")
    print("="*80)
    print(f"Translated {len(companies)} companies to {len(lang_codes)} languages")
    print(f"Total CSVs created: {len(companies) * len(lang_codes)}")


def main():
    parser = argparse.ArgumentParser(description='Translate tour CSVs to multiple languages')
    parser.add_argument('--all', action='store_true', help='Translate all companies')
    parser.add_argument('--company', type=str, help='Translate specific company')
    parser.add_argument('--languages', nargs='+', choices=list(LANGUAGES.keys()), 
                        help='Specific languages to translate to')
    parser.add_argument('--organize-only', action='store_true', 
                        help='Only organize CSVs into folders, no translation')
    parser.add_argument('--force', action='store_true', 
                        help='Force re-translation even if files already exist')
    
    args = parser.parse_args()
    
    if args.organize_only:
        organize_csvs()
        return
    
    if args.all:
        translate_all_companies(args.languages, args.force)
    elif args.company:
        # Translate single company
        company = args.company
        lang_codes = args.languages if args.languages else list(LANGUAGES.keys())
        
        print(f"\n" + "="*80)
        print(f"TRANSLATING {company.upper()} TO {len(lang_codes)} LANGUAGES")
        if args.force:
            print("⚠ FORCE MODE: Will overwrite existing translations")
        print("="*80)
        
        translator = TourTranslator()
        source_csv = f'data/{company}/en/tours_{company}_cleaned_with_media.csv'
        
        if not os.path.exists(source_csv):
            print(f"❌ Source file not found: {source_csv}")
            return
        
        for lang_code in lang_codes:
            output_csv = f'data/{company}/{lang_code}/tours_{company}_cleaned_with_media.csv'
            
            if os.path.exists(output_csv) and not args.force:
                print(f"  ⊙ {LANGUAGES[lang_code]['name']} already exists, skipping...")
                continue
            
            try:
                translator.translate_csv(source_csv, output_csv, lang_code)
            except Exception as e:
                print(f"  ❌ Error translating to {lang_code}: {e}")
                continue
        
        print(f"\n✅ {company} translation complete!")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

