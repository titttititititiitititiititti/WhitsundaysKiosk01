"""
3_download_media.py - STEP 3: Download Tour Images & Videos

USAGE:
    python 3_download_media.py tours_<company>_cleaned.csv
    
    OR to process all cleaned CSVs:
    python 3_download_media.py --all

This script:
    - Visits each tour URL with Selenium
    - Downloads all images and videos
    - Filters out logos and small images
    - Saves to static/tour_images/<company>/<tour>/
    - Creates tours_<company>_cleaned_with_media.csv
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
        ['python', 'download_tour_media.py', csv_file],
        cwd=project_root
    )
    return result.returncode == 0

def process_all():
    """Process all cleaned CSV files"""
    cleaned_csvs = glob.glob('tours_*_cleaned.csv')
    # Exclude files that already have media
    cleaned_csvs = [f for f in cleaned_csvs if '_with_media' not in f]
    
    if not cleaned_csvs:
        print("❌ No cleaned CSV files found!")
        print("   Run 2_ai_postprocess.py first")
        return
    
    print(f"📋 Found {len(cleaned_csvs)} cleaned CSV files:\n")
    for csv in cleaned_csvs:
        print(f"   - {csv}")
    
    print("\n" + "=" * 60)
    print("⚠️  This will download images for all tours.")
    print("    This may take 1-3 minutes per tour.")
    input("\nPress ENTER to continue or Ctrl+C to cancel...")
    
    for i, csv_file in enumerate(cleaned_csvs, 1):
        print(f"\n[{i}/{len(cleaned_csvs)}] Downloading media for {csv_file}...")
        success = process_single(csv_file)
        if success:
            print(f"   ✅ Created {csv_file.replace('.csv', '_with_media.csv')}")
        else:
            print(f"   ❌ Failed to process {csv_file}")
    
    print("\n" + "=" * 60)
    print("✅ Media Download Complete!")
    print("=" * 60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("=" * 70)
        print("📸 MEDIA DOWNLOADER")
        print("=" * 70)
        print()
        print("Usage:")
        print("  python 3_download_media.py <csv_file>   # Process single file")
        print("  python 3_download_media.py --all        # Process all cleaned CSVs")
        print()
        print("Example:")
        print("  python 3_download_media.py tours_oceanadventures_cleaned.csv")
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

