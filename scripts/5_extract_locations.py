"""
5_extract_locations.py - STEP 5: Extract Departure Locations

USAGE:
    python 5_extract_locations.py

This script:
    - Uses AI to find departure locations in tour descriptions
    - Looks for phrases like "meet at", "departs from", etc.
    - Updates all tours_*_cleaned_with_media.csv files
    - Creates locations_detailed_report.txt

REQUIRES: OPENAI_API_KEY in .env file
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
    print("📍 LOCATION EXTRACTOR")
    print("=" * 70)
    print()
    print("This will scan all tour descriptions to find departure locations.")
    print("It uses AI to identify phrases like:")
    print("  - 'meet at [LOCATION]'")
    print("  - 'departs from [LOCATION]'")
    print("  - 'check-in at [LOCATION]'")
    print()
    
    result = subprocess.run(
        ['python', 'extract_precise_locations.py'],
        cwd=project_root
    )

