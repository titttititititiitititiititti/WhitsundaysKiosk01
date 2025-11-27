"""
Process specific tour companies by name

Usage:
    python process_specific_companies.py cruisewhitsundays redcatadventures helireef
    
Or run without arguments to be prompted for company names.
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

def get_available_companies():
    """Get list of all available companies"""
    all_csvs = glob.glob('tours_*.csv')
    raw_csvs = [f for f in all_csvs if not ('_cleaned' in f or '_with_media' in f or '_PRODUCTION' in f or '_NEW' in f or '_FINAL' in f or '_test' in f or '_BACKUP' in f)]
    companies = sorted([os.path.basename(f).replace('tours_', '').replace('.csv', '') for f in raw_csvs])
    return companies

def main():
    available_companies = get_available_companies()
    
    if not available_companies:
        print("[X] No raw tour CSVs found!")
        print("   Make sure you have tours_<company>.csv files")
        return
    
    # Get company names from command line or prompt user
    if len(sys.argv) > 1:
        # Companies provided as arguments
        companies_to_process = sys.argv[1:]
    else:
        # Prompt user
        print("\n>> AVAILABLE COMPANIES:")
        for i, company in enumerate(available_companies, 1):
            print(f"   {i}. {company}")
        
        print("\n>> Enter company names to process (space-separated):")
        print("   Examples: cruisewhitsundays redcatadventures")
        print("             explorewhitsundays helireef")
        user_input = input("\nCompany names: ").strip()
        
        if not user_input:
            print("[X] No companies specified. Exiting.")
            return
        
        companies_to_process = user_input.split()
    
    # Validate company names
    invalid_companies = [c for c in companies_to_process if c not in available_companies]
    if invalid_companies:
        print(f"\n[X] Invalid company names: {', '.join(invalid_companies)}")
        print(f"\n[!] Available companies: {', '.join(available_companies)}")
        return
    
    # Confirm with user
    print("\n" + "="*60)
    print(f">> Will process {len(companies_to_process)} companies:")
    for company in companies_to_process:
        print(f"   - {company}")
    print("="*60)
    
    response = input("\nPress ENTER to continue or Ctrl+C to cancel: ")
    
    print("\n" + "="*60)
    print(">> Starting AI post-processing...")
    print("="*60)
    
    failed_process = []
    successful_process = []
    
    # STEP 1: AI post-process each specified company
    for i, company in enumerate(companies_to_process, 1):
        raw_csv = f'tours_{company}.csv'
        cleaned_csv = f'tours_{company}_cleaned.csv'
        
        if not os.path.exists(raw_csv):
            print(f"\n[X] [{i}/{len(companies_to_process)}] SKIPPING {company} - no raw CSV found")
            failed_process.append(company)
            continue
        
        print(f"\n\n{'='*60}")
        print(f"[{i}/{len(companies_to_process)}] AI PROCESSING: {company}")
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
            successful_process.append(company)
    
    # STEP 2: Merge processed companies with media
    if successful_process:
        print(f"\n\n{'#'*60}")
        print(f"# STEP 2: MERGING {len(successful_process)} COMPANIES WITH IMAGES")
        print(f"{'#'*60}")
        
        # Run merge for each successful company individually
        for company in successful_process:
            cleaned_csv = f'tours_{company}_cleaned.csv'
            raw_csv = f'tours_{company}.csv'
            with_media_csv = f'tours_{company}_cleaned_with_media.csv'
            
            if os.path.exists(with_media_csv):
                print(f"\n>> Merging {company}...")
                run_command([
                    'python',
                    'merge_cleaned_to_media.py',
                    cleaned_csv,
                    raw_csv,
                    with_media_csv
                ])
            else:
                print(f"\n[!] {company}: No _with_media.csv found, creating new one...")
                # Just copy cleaned to with_media if no existing media file
                run_command(['Copy-Item' if sys.platform == 'win32' else 'cp', cleaned_csv, with_media_csv])
    
    # Summary
    print(f"\n\n{'='*60}")
    print(f">> PROCESSING COMPLETE!")
    print(f"{'='*60}")
    
    print(f"\n>> RESULTS:")
    print(f"   [OK] Successful: {len(successful_process)}/{len(companies_to_process)}")
    if successful_process:
        print(f"        Companies: {', '.join(successful_process)}")
    
    if failed_process:
        print(f"   [X] Failed: {len(failed_process)}")
        print(f"       Companies: {', '.join(failed_process)}")
    
    print(f"\n>> Updated files:")
    for company in successful_process:
        print(f"   - tours_{company}_cleaned_with_media.csv")
    
    print(f"\n>> Refresh your browser to see the changes!")
    print(f"   (Flask auto-reloads, so no need to restart the server)")

if __name__ == '__main__':
    main()




