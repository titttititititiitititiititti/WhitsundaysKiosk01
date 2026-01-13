"""
audit_filters.py - Verify All Tour Filter Categories

USAGE:
    python audit_filters.py

This script:
    - Scans all tours_*_cleaned_with_media.csv files
    - Checks that all tours have valid filter values
    - Reports any issues (unknown duration, price, etc.)
    - Shows distribution of filter categories

Run this after processing to ensure data quality!
"""
import sys
import os

# Change to project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

if __name__ == '__main__':
    # Run the audit script
    exec(open('audit_all_filters.py').read())

