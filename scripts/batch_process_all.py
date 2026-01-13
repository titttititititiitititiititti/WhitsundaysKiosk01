"""
batch_process_all.py - Process ALL Companies at Once

USAGE:
    python batch_process_all.py

This script runs the full workflow on all existing raw CSVs:
    1. AI post-processing (cleans data)
    2. Merge images back in
    
For NEW tours, use 1_scrape_tours.py first!
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
    print("🔄 BATCH PROCESSOR")
    print("=" * 70)
    print()
    print("This will re-process ALL existing tour CSVs with AI.")
    print("Use this when you want to:")
    print("  - Re-run AI with updated prompts")
    print("  - Clean up existing data")
    print()
    
    result = subprocess.run(
        ['python', 'batch_rescrape_and_process_all.py'],
        cwd=project_root
    )

