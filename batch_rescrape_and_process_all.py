"""
Batch RE-SCRAPE and AI post-process ALL companies

HOW TO USE:
1. Update TOUR_LINKS in scrape_tours.py with the URLs you want to re-scrape
2. Run scrape_tours.py manually to get fresh data
3. Run THIS script to AI post-process all raw CSVs and merge images

OR just run THIS script to re-process existing scraped data with new AI prompt
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
        print("[X] No raw tour CSVs found!")
        print("   Make sure you have tours_<company>.csv files")
        print("\n[!] To re-scrape:")
        print("   1. Update TOUR_LINKS in scrape_tours.py")
        print("   2. Run: python scrape_tours.py")
        print("   3. Then run this script again")
        return
    
    companies = sorted([csv.replace('tours_', '').replace('.csv', '') for csv in raw_csvs])
    
    print(f"\n>> Found {len(companies)} companies with raw scraped data:")
    for company in companies:
        print(f"   - {company}")
    
    print("\n" + "="*60)
    print("This will:")
    print("   1. Run AI post-processing on all raw CSVs (15-30 mins)")
    print("   2. Merge images back in")
    print("\n   [!] Already re-scraped? Great! This will process the new data.")
    print("   [!] Haven't re-scraped? This will re-process existing data with improved AI.")
    print("="*60)
    
    response = input("\nPress ENTER to continue or Ctrl+C to cancel: ")
    
    print("\n" + "="*60)
    print(">> Starting batch AI post-processing...")
    print("="*60)
    
    failed_process = []
    
    # STEP 1: AI post-process each company
    print(f"\n\n{'#'*60}")
    print(f"# STEP 1: AI POST-PROCESSING ALL COMPANIES")
    print(f"{'#'*60}")
    
    for i, company in enumerate(companies, 1):
        raw_csv = f'tours_{company}.csv'
        cleaned_csv = f'tours_{company}_cleaned.csv'
        
        print(f"\n\n{'='*60}")
        print(f"[{i}/{len(companies)}] AI PROCESSING: {company}")
        print(f"{'='*60}")
        
        returncode = run_command([
            'python',
            'ai_postprocess_csv.py',
            raw_csv,
            cleaned_csv
        ])
        
        if returncode != 0:
            print(f"[X] PROCESS FAILED: {company}")
            failed_process.append(company)
        else:
            print(f"[OK] PROCESS SUCCESS: {company}")
    
    # STEP 2: Merge all cleaned files with media
    print(f"\n\n{'#'*60}")
    print(f"# STEP 2: MERGING ALL WITH IMAGES")
    print(f"{'#'*60}")
    
    run_command(['python', 'merge_cleaned_to_media.py'])
    
    # Summary
    print(f"\n\n{'='*60}")
    print(f">> BATCH PROCESSING COMPLETE!")
    print(f"{'='*60}")
    
    print(f"\n>> PROCESSING RESULTS:")
    print(f"   [OK] Successful: {len(companies) - len(failed_process)}/{len(companies)}")
    if failed_process:
        print(f"   [X] Failed: {len(failed_process)}")
        print(f"      Companies: {', '.join(failed_process)}")
    
    print(f"\n>> All _with_media.csv files have been updated with:")
    print(f"   - New AI-processed descriptions (concise, no redundancy)")
    print(f"   - Better data quality (no bad durations/ages)")
    print(f"   - Preserved image paths")
    print(f"\n>> Restart your Flask app to see the changes!")

if __name__ == '__main__':
    main()

