"""
Migrate tours from virtual company assignments to real CSV companies.

Reads config/tour_company_assignments.json and for each reassigned tour:
1. Moves the CSV row from the old company CSV to a new company CSV (all 8 languages)
2. Updates the company_name column in the new CSV
3. Copies the image folder to the new company path
4. Updates all account settings (enabled_tours, promoted_tours, etc.) with new keys
5. Clears the processed entries from tour_company_assignments.json

The product ID stays the same -- only the company prefix changes.

Usage: python scripts/migrate_companies.py [--dry-run]
"""

import os
import sys
import csv
import json
import shutil
import glob

# Run from project root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DRY_RUN = '--dry-run' in sys.argv
ASSIGNMENTS_FILE = 'config/tour_company_assignments.json'
COMPANY_NAMES_FILE = 'config/company_names.json'
LANGUAGES = ['en', 'de', 'es', 'fr', 'hi', 'ja', 'ko', 'zh']

# Settings keys that contain tour keys
TOUR_KEY_FIELDS = ['enabled_tours', 'cruise_ship_friendly_tours']
TOUR_DICT_FIELDS = ['tour_overrides', 'hidden_images', 'extra_images', 'custom_reviews', 'tour_reviews']
TOUR_LIST_DICT_FIELDS = ['promoted_tours']  # dict of lists: {category: [key, key, ...]}

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def remap_key(old_key, assignments):
    """Given an old tour key, return (new_key, new_company) or None if not reassigned."""
    if old_key not in assignments:
        return None
    old_company, tid = old_key.split('__', 1)
    new_company = assignments[old_key]
    new_key = f"{new_company}__{tid}"
    return new_key, new_company

def main():
    assignments = load_json(ASSIGNMENTS_FILE)
    if not assignments:
        print("No tour company assignments to migrate.")
        return

    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Migrating {len(assignments)} tour(s) to real companies...\n")

    # Group by old company -> new company
    # {old_company: {new_company: [tour_id, ...]}}
    migrations = {}
    for old_key, new_company in assignments.items():
        old_company, tid = old_key.split('__', 1)
        migrations.setdefault(old_company, {}).setdefault(new_company, []).append(tid)

    # Build full key remap: old_key -> new_key
    key_remap = {}
    for old_key, new_company in assignments.items():
        old_company, tid = old_key.split('__', 1)
        key_remap[old_key] = f"{new_company}__{tid}"

    print("Key remapping:")
    for old, new in sorted(key_remap.items()):
        print(f"  {old}  ->  {new}")
    print()

    # ── Step 1: Migrate CSV rows ──
    print("=" * 60)
    print("STEP 1: Migrate CSV rows")
    print("=" * 60)

    for old_company, new_companies in migrations.items():
        for lang in LANGUAGES:
            old_csv = f"data/{old_company}/{lang}/tours_{old_company}_cleaned_with_media.csv"
            if not os.path.exists(old_csv):
                continue

            with open(old_csv, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                all_rows = list(reader)

            # Separate: rows to keep in old CSV vs rows to move
            keep_rows = []
            move_rows = {}  # new_company -> [rows]

            for row in all_rows:
                tid = row['id']
                moved = False
                for new_company, tids in new_companies.items():
                    if tid in tids:
                        move_rows.setdefault(new_company, []).append(row)
                        moved = True
                        break
                if not moved:
                    keep_rows.append(row)

            total_moved = sum(len(rows) for rows in move_rows.values())
            if total_moved == 0:
                continue

            print(f"\n  [{lang}] {old_csv}: {len(all_rows)} total, keeping {len(keep_rows)}, moving {total_moved}")

            # Write new company CSVs
            for new_company, rows in move_rows.items():
                new_dir = f"data/{new_company}/{lang}"
                new_csv = f"{new_dir}/tours_{new_company}_cleaned_with_media.csv"
                print(f"    -> {new_csv} ({len(rows)} tours)")

                if not DRY_RUN:
                    os.makedirs(new_dir, exist_ok=True)

                    # If CSV already exists, merge (append new rows)
                    existing_rows = []
                    existing_ids = set()
                    if os.path.exists(new_csv):
                        with open(new_csv, 'r', encoding='utf-8', newline='') as f:
                            r = csv.DictReader(f)
                            existing_rows = list(r)
                            existing_ids = {row['id'] for row in existing_rows}

                    with open(new_csv, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        # Write existing rows first
                        for row in existing_rows:
                            writer.writerow(row)
                        # Write migrated rows with updated company_name
                        for row in rows:
                            if row['id'] not in existing_ids:
                                row['company_name'] = new_company
                                writer.writerow(row)

            # Rewrite old CSV without the moved rows
            if not DRY_RUN and keep_rows:
                with open(old_csv, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in keep_rows:
                        writer.writerow(row)
                print(f"    Rewrote {old_csv} with {len(keep_rows)} remaining tours")
            elif not DRY_RUN and not keep_rows:
                print(f"    ⚠ {old_csv} would be empty — keeping as-is with 0 rows")
                with open(old_csv, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

    # ── Step 2: Copy image folders ──
    print("\n" + "=" * 60)
    print("STEP 2: Copy image folders")
    print("=" * 60)

    for old_key, new_key in key_remap.items():
        old_company, tid = old_key.split('__', 1)
        new_company = new_key.split('__', 1)[0]

        old_img = f"static/tour_images/{old_company}/{tid}"
        new_img = f"static/tour_images/{new_company}/{tid}"

        if os.path.isdir(old_img):
            if os.path.isdir(new_img):
                print(f"  [SKIP] {new_img} already exists")
            else:
                print(f"  {old_img}  ->  {new_img}")
                if not DRY_RUN:
                    os.makedirs(os.path.dirname(new_img), exist_ok=True)
                    shutil.copytree(old_img, new_img)
        else:
            print(f"  [NO IMAGES] {old_img} doesn't exist")

    # ── Step 3: Update account settings ──
    print("\n" + "=" * 60)
    print("STEP 3: Update account settings")
    print("=" * 60)

    settings_files = glob.glob('config/defaults/*/settings.json')
    for sf in settings_files:
        account = sf.replace('\\', '/').split('/')[-2]
        settings = load_json(sf)
        changed = False

        # List fields (enabled_tours, cruise_ship_friendly_tours)
        for field in TOUR_KEY_FIELDS:
            if field in settings and isinstance(settings[field], list):
                new_list = []
                for key in settings[field]:
                    if key in key_remap:
                        new_list.append(key_remap[key])
                        changed = True
                    else:
                        new_list.append(key)
                settings[field] = new_list

        # Dict fields (tour_overrides, hidden_images, extra_images, etc.)
        for field in TOUR_DICT_FIELDS:
            if field in settings and isinstance(settings[field], dict):
                new_dict = {}
                for key, val in settings[field].items():
                    if key in key_remap:
                        new_dict[key_remap[key]] = val
                        changed = True
                    else:
                        new_dict[key] = val
                settings[field] = new_dict

        # Promoted tours: {category: [key, ...]}
        for field in TOUR_LIST_DICT_FIELDS:
            if field in settings and isinstance(settings[field], dict):
                for cat, keys in settings[field].items():
                    if isinstance(keys, list):
                        new_keys = []
                        for key in keys:
                            if key in key_remap:
                                new_keys.append(key_remap[key])
                                changed = True
                            else:
                                new_keys.append(key)
                        settings[field][cat] = new_keys

        if changed:
            print(f"  Updated: {sf} ({account})")
            if not DRY_RUN:
                save_json(sf, settings)
        else:
            print(f"  No changes: {sf}")

    # Also update agent_settings.json if it exists
    agent_settings_file = 'config/agent_settings.json'
    if os.path.exists(agent_settings_file):
        agent = load_json(agent_settings_file)
        changed = False
        for account_name, acct_data in agent.items():
            if isinstance(acct_data, dict):
                for field in TOUR_KEY_FIELDS:
                    if field in acct_data and isinstance(acct_data[field], list):
                        new_list = [key_remap.get(k, k) for k in acct_data[field]]
                        if new_list != acct_data[field]:
                            acct_data[field] = new_list
                            changed = True
        if changed:
            print(f"  Updated: {agent_settings_file}")
            if not DRY_RUN:
                save_json(agent_settings_file, agent)

    # ── Step 4: Clear assignments ──
    print("\n" + "=" * 60)
    print("STEP 4: Clear tour_company_assignments.json")
    print("=" * 60)

    if not DRY_RUN:
        save_json(ASSIGNMENTS_FILE, {})
        print("  Cleared all assignments (tours are now in their real CSVs)")
    else:
        print("  [DRY RUN] Would clear all assignments")

    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Migration complete!")
    print(f"  {len(key_remap)} tours moved to {len(set(assignments.values()))} new companies")
    print("=" * 60)

    if not DRY_RUN:
        print("\nReminder: Restart the app to see changes. Image folders were COPIED")
        print("(not moved) — you can delete the old ones from sailing-whitsundays/")
        print("and explorewhitsundays/ after verifying everything works.")

if __name__ == '__main__':
    main()
