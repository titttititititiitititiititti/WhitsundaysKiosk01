"""
merge_cleaned_to_media.py - Merge Cleaned Data → Media Files

USAGE:
    python merge_cleaned_to_media.py

This script:
    - Finds all _cleaned.csv files
    - Merges their data into corresponding _with_media.csv files
    - Preserves image paths while updating other fields

Use this when you've re-processed CSVs with AI and want to
update the media files without re-downloading images.
"""
import sys
import os

# Change to project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)
sys.path.insert(0, project_root)

if __name__ == '__main__':
    # Import and run the merge function
    from merge_cleaned_to_media import merge_cleaned_to_media
    merge_cleaned_to_media()

