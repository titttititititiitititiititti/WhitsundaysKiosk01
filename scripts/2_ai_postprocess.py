"""
2_ai_postprocess.py - STEP 2: AI Clean & Structure Data

USAGE:
    python 2_ai_postprocess.py tours_<company>.csv
    
    OR to process all raw CSVs:
    python 2_ai_postprocess.py --all

This script:
    - Uses OpenAI GPT-4o to extract and structure tour data
    - Cleans HTML and formatting
    - Extracts: prices, duration, inclusions, highlights, etc.
    - Creates tours_<company>_cleaned.csv

REQUIRES: OPENAI_API_KEY in .env file
"""
import sys
import os
import glob

# Change to project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

def process_single(csv_file):
    """Process a single CSV file"""
    import subprocess
    result = subprocess.run(
        ['python', 'ai_postprocess_csv.py', csv_file],
        cwd=project_root
    )
    return result.returncode == 0

def process_all():
    """Process all raw CSV files"""
    raw_csvs = glob.glob('tours_*.csv')
    raw_csvs = [f for f in raw_csvs if not any(x in f for x in ['_cleaned', '_with_media', '_PRODUCTION', '_NEW', '_FINAL', '_test', '_BACKUP'])]
    
    if not raw_csvs:
        print("❌ No raw tour CSVs found!")
        return
    
    print(f"📋 Found {len(raw_csvs)} raw CSV files to process:\n")
    for csv in raw_csvs:
        print(f"   - {csv}")
    
    print("\n" + "=" * 60)
    
    for i, csv_file in enumerate(raw_csvs, 1):
        print(f"\n[{i}/{len(raw_csvs)}] Processing {csv_file}...")
        success = process_single(csv_file)
        if success:
            print(f"   ✅ Created {csv_file.replace('.csv', '_cleaned.csv')}")
        else:
            print(f"   ❌ Failed to process {csv_file}")
    
    print("\n" + "=" * 60)
    print("✅ AI Post-Processing Complete!")
    print("=" * 60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("=" * 70)
        print("📝 AI POST-PROCESSOR")
        print("=" * 70)
        print()
        print("Usage:")
        print("  python 2_ai_postprocess.py <csv_file>   # Process single file")
        print("  python 2_ai_postprocess.py --all        # Process all raw CSVs")
        print()
        print("Example:")
        print("  python 2_ai_postprocess.py tours_oceanadventures.csv")
        print()
        sys.exit(1)
    
    if sys.argv[1] == '--all':
        process_all()
    else:
        csv_file = sys.argv[1]
        if not os.path.exists(csv_file):
            # Try in parent directory
            csv_file = os.path.join(project_root, sys.argv[1])
        
        if not os.path.exists(csv_file):
            print(f"❌ File not found: {sys.argv[1]}")
            sys.exit(1)
        
        process_single(csv_file)

