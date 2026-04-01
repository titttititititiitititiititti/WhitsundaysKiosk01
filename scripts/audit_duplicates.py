"""
audit_duplicates.py - Find duplicate tours and show which are enabled/disabled

Scans all CSVs and all account settings to produce a report showing:
1. Which tours are enabled on which accounts
2. Duplicate tour names across different companies
3. Tours that are not enabled on ANY account (safe to delete)

USAGE:
    python scripts/audit_duplicates.py
"""
import os
import sys
import csv
import json
import glob
from collections import defaultdict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)


def load_all_tours_from_csv():
    """Load every tour from every English CSV. Returns list of dicts."""
    tours = []
    seen_keys = set()
    
    # data/<company>/en/*.csv
    for csvfile in glob.glob('data/*/en/*_with_media.csv'):
        try:
            with open(csvfile, 'r', newline='', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    company = row.get('company_name', 'unknown')
                    tid = row.get('id', '')
                    key = f"{company}__{tid}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    tours.append({
                        'key': key,
                        'id': tid,
                        'name': row.get('name', '').strip(),
                        'company': company,
                        'csv_file': csvfile,
                        'price': row.get('price_adult', ''),
                        'duration': row.get('duration', ''),
                    })
        except Exception as e:
            print(f"Error reading {csvfile}: {e}")
    
    # root-level legacy CSVs
    for csvfile in glob.glob('*_with_media.csv'):
        try:
            with open(csvfile, 'r', newline='', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    company = row.get('company_name', 'unknown')
                    tid = row.get('id', '')
                    key = f"{company}__{tid}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    tours.append({
                        'key': key,
                        'id': tid,
                        'name': row.get('name', '').strip(),
                        'company': company,
                        'csv_file': csvfile,
                        'price': row.get('price_adult', ''),
                        'duration': row.get('duration', ''),
                    })
        except Exception as e:
            pass
    
    return tours


def load_all_account_settings():
    """Load enabled_tours from all accounts (defaults + local)."""
    accounts = {}
    
    for settings_dir in ['config/defaults', 'config/accounts']:
        for sf in glob.glob(f'{settings_dir}/*/settings.json'):
            account = os.path.basename(os.path.dirname(sf))
            try:
                with open(sf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                enabled = data.get('enabled_tours', [])
                # Merge if account already seen (defaults + local)
                if account in accounts:
                    existing = accounts[account]
                    if isinstance(existing, list) and isinstance(enabled, list):
                        accounts[account] = list(set(existing + enabled))
                    elif enabled == "__ALL__" or existing == "__ALL__":
                        accounts[account] = "__ALL__"
                else:
                    accounts[account] = enabled
            except Exception:
                pass
    
    return accounts


def normalize_name(name):
    """Normalize tour name for fuzzy duplicate matching."""
    import re
    n = name.lower().strip()
    n = re.sub(r'[^a-z0-9\s]', '', n)
    n = re.sub(r'\s+', ' ', n)
    # Remove common suffixes/prefixes
    for word in ['sailing', 'tour', 'adventure', 'experience', 'trip']:
        n = n.replace(word, '')
    return n.strip()


def main():
    print("=" * 80)
    print("  Tour Audit - Duplicates & Enabled/Disabled Status")
    print("=" * 80)
    
    tours = load_all_tours_from_csv()
    accounts = load_all_account_settings()
    
    print(f"\n  Total tours in CSVs: {len(tours)}")
    print(f"  Accounts found: {', '.join(sorted(accounts.keys()))}")
    
    # Skip test/throwaway accounts for the "used" analysis
    skip_accounts = set()
    for account, enabled_list in accounts.items():
        if enabled_list == "__ALL__":
            skip_accounts.add(account)
            print(f"  Skipping '{account}' (has __ALL__ - test/demo account)")
        elif isinstance(enabled_list, list) and len(enabled_list) == 0:
            skip_accounts.add(account)
            print(f"  Skipping '{account}' (empty enabled_tours)")
    
    real_accounts = {k: v for k, v in accounts.items() if k not in skip_accounts}
    print(f"  Real accounts: {', '.join(sorted(real_accounts.keys()))}")
    
    # Build enabled map: tour_key -> list of real accounts it's enabled on
    enabled_on = defaultdict(list)
    for account, enabled_list in real_accounts.items():
        if isinstance(enabled_list, list):
            for key in enabled_list:
                enabled_on[key].append(account)
    
    # Find tours not enabled on ANY account
    orphans = [t for t in tours if not enabled_on[t['key']]]
    
    # Find duplicate names across different companies (fuzzy match)
    name_groups = defaultdict(list)
    for t in tours:
        norm = normalize_name(t['name'])
        if norm and len(norm) > 3:
            name_groups[norm].append(t)
    
    # Also find by key words (boat names like "Powerplay", "MiLady", "Kiana", etc.)
    boat_names = defaultdict(list)
    import re
    for t in tours:
        # Extract probable boat/vessel name (first 1-3 significant words)
        words = re.sub(r'[^a-zA-Z0-9\s]', '', t['name']).split()
        if words:
            boat = words[0].lower()
            # Skip generic words
            if boat not in ('private', 'the', 'a', 'an', 'premium', 'on', 'shared'):
                boat_names[boat].append(t)
    
    # Merge both detection methods
    all_dupe_groups = {}
    for name, group in name_groups.items():
        if len(group) > 1:
            companies = set(t['company'] for t in group)
            all_dupe_groups[name] = group
    
    for boat, group in boat_names.items():
        if len(group) > 1:
            companies = set(t['company'] for t in group)
            if len(companies) > 1:
                key = f"boat:{boat}"
                if key not in all_dupe_groups:
                    all_dupe_groups[key] = group
    
    dupes = all_dupe_groups
    
    # --- Report ---
    
    # 1. Orphan tours (not on any account)
    print(f"\n{'=' * 80}")
    print(f"  TOURS NOT ENABLED ON ANY ACCOUNT ({len(orphans)} total)")
    print(f"  These are safe to delete from CSVs.")
    print(f"{'=' * 80}")
    
    orphans_by_company = defaultdict(list)
    for t in orphans:
        orphans_by_company[t['company']].append(t)
    
    for company in sorted(orphans_by_company.keys()):
        co_tours = orphans_by_company[company]
        print(f"\n  [{company}] ({len(co_tours)} unused tours)")
        for t in co_tours:
            print(f"    {t['key']:<55s}  {t['name'][:50]}")
    
    # 2. Duplicates (same name, different companies)
    print(f"\n{'=' * 80}")
    print(f"  DUPLICATE TOUR NAMES ACROSS COMPANIES ({len(dupes)} groups)")
    print(f"{'=' * 80}")
    
    for norm_name, group in sorted(dupes.items(), key=lambda x: x[0]):
        companies = set(t['company'] for t in group)
        tag = "CROSS-COMPANY" if len(companies) > 1 else "SAME COMPANY"
        print(f"\n  [{tag}] Possible duplicates:")
        for t in group:
            accts = enabled_on[t['key']]
            status = f"on: {', '.join(accts)}" if accts else "** NOT USED **"
            print(f"    {t['company']:<30s}  {t['name'][:45]:<45s}  {status}")
    
    # 3. Summary per company
    print(f"\n{'=' * 80}")
    print(f"  SUMMARY BY COMPANY")
    print(f"{'=' * 80}")
    
    company_stats = defaultdict(lambda: {'total': 0, 'enabled': 0, 'orphan': 0})
    for t in tours:
        company_stats[t['company']]['total'] += 1
        if enabled_on[t['key']]:
            company_stats[t['company']]['enabled'] += 1
        else:
            company_stats[t['company']]['orphan'] += 1
    
    print(f"\n  {'Company':<35s}  {'Total':>5s}  {'Used':>5s}  {'Unused':>6s}")
    print(f"  {'-'*33}  {'-'*5}  {'-'*5}  {'-'*6}")
    for company in sorted(company_stats.keys()):
        s = company_stats[company]
        unused_marker = " <-- can clean" if s['orphan'] > 0 else ""
        print(f"  {company:<35s}  {s['total']:>5d}  {s['enabled']:>5d}  {s['orphan']:>6d}{unused_marker}")
    
    total_orphans = sum(s['orphan'] for s in company_stats.values())
    total_tours = sum(s['total'] for s in company_stats.values())
    print(f"\n  Total: {total_tours} tours, {total_tours - total_orphans} used, {total_orphans} unused")
    
    # 4. Write deletion list for cleanup
    if orphans:
        out_file = 'orphan_tours_to_delete.txt'
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write("# Tours not enabled on any account - safe to delete\n")
            f.write(f"# Generated by audit_duplicates.py\n")
            f.write(f"# {len(orphans)} tours\n\n")
            for t in sorted(orphans, key=lambda x: (x['company'], x['name'])):
                f.write(f"{t['key']}  |  {t['name']}  |  {t['company']}  |  {t['csv_file']}\n")
        print(f"\n  Wrote deletion list to: {out_file}")
        print(f"  Review it, then run: python scripts/cleanup_orphans.py")


if __name__ == '__main__':
    main()
