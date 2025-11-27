"""
Batch process ALL company CSVs with AI post-processing, then merge images back in
"""
import glob
import os
import subprocess
import sys

def run_command(cmd):
    """Run a command and print output in real-time"""
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    for line in process.stdout:
        print(line, end='')
    
    process.wait()
    return process.returncode

def main():
    # Find all raw scraped CSVs (not _cleaned or _with_media)
    all_csvs = glob.glob('tours_*.csv')
    raw_csvs = [f for f in all_csvs if not ('_cleaned' in f or '_with_media' in f or '_PRODUCTION' in f or '_NEW' in f or '_FINAL' in f or '_test' in f or '_BACKUP' in f)]
    
    if not raw_csvs:
        print("No raw tour CSVs found!")
        return
    
    print(f"\n🚀 Found {len(raw_csvs)} companies to process:")
    for csv in sorted(raw_csvs):
        company_name = csv.replace('tours_', '').replace('.csv', '')
        print(f"   - {company_name}")
    
    print("\n" + "="*60)
    input("Press ENTER to start batch processing (this will take a while)...")
    print("="*60)
    
    failed_companies = []
    
    # Step 1: AI post-process each company
    for i, raw_csv in enumerate(sorted(raw_csvs), 1):
        company_name = raw_csv.replace('tours_', '').replace('.csv', '')
        cleaned_csv = f'tours_{company_name}_cleaned.csv'
        
        print(f"\n\n{'#'*60}")
        print(f"# [{i}/{len(raw_csvs)}] Processing: {company_name}")
        print(f"{'#'*60}")
        
        # Run AI post-processing
        returncode = run_command([
            'python',
            'ai_postprocess_csv.py',
            raw_csv,
            cleaned_csv
        ])
        
        if returncode != 0:
            print(f"❌ FAILED: {company_name}")
            failed_companies.append(company_name)
        else:
            print(f"✅ SUCCESS: {company_name}")
    
    # Step 2: Merge all cleaned files with media
    print(f"\n\n{'#'*60}")
    print(f"# STEP 2: Merging all cleaned data with images...")
    print(f"{'#'*60}")
    
    run_command(['python', 'merge_cleaned_to_media.py'])
    
    # Summary
    print(f"\n\n{'='*60}")
    print(f"🎉 BATCH PROCESSING COMPLETE!")
    print(f"{'='*60}")
    print(f"✅ Successful: {len(raw_csvs) - len(failed_companies)}/{len(raw_csvs)}")
    
    if failed_companies:
        print(f"❌ Failed: {len(failed_companies)}")
        print(f"   Companies: {', '.join(failed_companies)}")
    
    print(f"\n📁 All _with_media.csv files have been updated with:")
    print(f"   - New AI-processed descriptions")
    print(f"   - Better data quality (no bad durations/ages)")
    print(f"   - Preserved image paths")
    print(f"\n🚀 Restart your Flask app to see the changes!")

if __name__ == '__main__':
    main()




