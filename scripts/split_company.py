"""
split_company.py - Move tours from one company to new companies

Splits tours out of a source company into new company names.
Updates: CSVs (all languages), image folders, account settings (promoted_tours,
tour_overrides, hidden_images, extra_images, reviews).

USAGE:
    python scripts/split_company.py

Configure the MOVES dict below before running.

After running, use resync_images_to_csv.py to verify image paths are correct.
"""
import os
import sys
import csv
import json
import glob
import shutil

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

# =============================================================================
# CONFIGURE YOUR MOVES HERE
# =============================================================================
# Format: "new-company-name": ["tour_id_1", "tour_id_2", ...]
#
# Tours listed here will be moved OUT of SOURCE_COMPANY into the new company.
# Tours NOT listed stay in SOURCE_COMPANY.
#
# Run:  python scripts/split_company.py --list
# to see all tour IDs in the source company.
# =============================================================================

SOURCE_COMPANY = "sailing-whitsundays"

MOVES = {
    # "new-company-slug": [
    #     "fd56a077ec5a503c",   # Whitsunday Adventurer 2D/2N
    #     "fa0bf69d1ff5e9ca",   # Coral Sea Marina - Premium Tour
    # ],
    # "another-company": [
    #     "83caea5dc452753a",   # Powerplay Whitsundays Adventure
    # ],
}

# =============================================================================


def list_tours():
    """Print all tours in SOURCE_COMPANY for reference."""
    csv_path = f"data/{SOURCE_COMPANY}/en/tours_{SOURCE_COMPANY}_cleaned_with_media.csv"
    if not os.path.exists(csv_path):
        csv_candidates = glob.glob(f"data/{SOURCE_COMPANY}/*/*.csv")
        if csv_candidates:
            csv_path = csv_candidates[0]
        else:
            print(f"No CSV found for {SOURCE_COMPANY}")
            return

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\nTours in '{SOURCE_COMPANY}' ({len(rows)} total):\n")
    print(f"  {'ID':<20s}  {'Name'}")
    print(f"  {'-'*18}  {'-'*55}")
    for row in rows:
        print(f"  {row['id']:<20s}  {row['name'][:55]}")
    print(f"\nCopy the IDs you want to move into the MOVES dict in this script.")


def update_csv_files(new_company, tour_ids):
    """Update company_name and image paths in CSVs, creating new company CSV structure."""
    tour_id_set = set(tour_ids)
    languages = []

    # Find all language dirs for source company
    lang_dirs = glob.glob(f"data/{SOURCE_COMPANY}/*/")
    for ld in lang_dirs:
        lang = os.path.basename(ld.rstrip('/\\'))
        languages.append(lang)

    if not languages:
        print(f"  No language directories found for {SOURCE_COMPANY}")
        return 0

    total_moved = 0

    for lang in sorted(languages):
        src_csv = f"data/{SOURCE_COMPANY}/{lang}/tours_{SOURCE_COMPANY}_cleaned_with_media.csv"
        if not os.path.exists(src_csv):
            continue

        with open(src_csv, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            all_rows = list(reader)

        staying = []
        moving = []
        for row in all_rows:
            if row['id'] in tour_id_set:
                row['company_name'] = new_company
                # Update image paths
                for col in ('image_url', 'image_urls'):
                    if col in row and row[col]:
                        row[col] = row[col].replace(
                            f"tour_images/{SOURCE_COMPANY}/",
                            f"tour_images/{new_company}/"
                        )
                moving.append(row)
            else:
                staying.append(row)

        if not moving:
            continue

        # Write updated source CSV (tours that stay)
        with open(src_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(staying)

        # Create new company CSV
        dest_dir = f"data/{new_company}/{lang}"
        os.makedirs(dest_dir, exist_ok=True)
        dest_csv = f"{dest_dir}/tours_{new_company}_cleaned_with_media.csv"

        # If dest CSV already exists, merge
        existing_rows = []
        existing_ids = set()
        if os.path.exists(dest_csv):
            with open(dest_csv, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_rows = list(reader)
                existing_ids = {r['id'] for r in existing_rows}

        new_rows = [r for r in moving if r['id'] not in existing_ids]
        all_dest_rows = existing_rows + new_rows

        with open(dest_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_dest_rows)

        moved_count = len(new_rows)
        total_moved += moved_count
        print(f"  [{lang}] Moved {moved_count} tour(s) -> {dest_csv}")
        print(f"         {len(staying)} tour(s) remain in source")

    return total_moved


def move_image_folders(new_company, tour_ids):
    """Move image folders from source to new company."""
    moved = 0
    for tid in tour_ids:
        src = os.path.join('static', 'tour_images', SOURCE_COMPANY, tid)
        dest = os.path.join('static', 'tour_images', new_company, tid)
        if os.path.isdir(src):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(dest):
                # Merge: copy files that don't exist in dest
                for f in os.listdir(src):
                    sf = os.path.join(src, f)
                    df = os.path.join(dest, f)
                    if not os.path.exists(df):
                        shutil.copy2(sf, df)
                shutil.rmtree(src)
            else:
                shutil.move(src, dest)
            moved += 1
            print(f"  Moved images: {SOURCE_COMPANY}/{tid} -> {new_company}/{tid}")
    return moved


def update_account_settings(old_key_prefix, new_key_prefix, tour_ids):
    """Update tour keys in all account settings files."""
    tour_id_set = set(tour_ids)
    settings_files = glob.glob('config/defaults/*/settings.json')
    settings_files += glob.glob('config/accounts/*/settings.json')

    updated_files = 0
    for sf in settings_files:
        try:
            with open(sf, 'r', encoding='utf-8') as f:
                content = f.read()

            if old_key_prefix not in content:
                continue

            data = json.loads(content)
            changed = False

            def remap_key(k):
                """If key matches old prefix + one of our tour IDs, remap it."""
                if k.startswith(old_key_prefix):
                    tid = k[len(old_key_prefix):]
                    if tid in tour_id_set:
                        return new_key_prefix + tid
                return k

            # Update promoted_tours (list of keys)
            if 'promoted_tours' in data and isinstance(data['promoted_tours'], list):
                new_list = [remap_key(k) if isinstance(k, str) else k for k in data['promoted_tours']]
                if new_list != data['promoted_tours']:
                    data['promoted_tours'] = new_list
                    changed = True

            # Update dict-valued sections that use tour keys
            for section in ('tour_overrides', 'hidden_images', 'extra_images',
                            'custom_reviews', 'tour_reviews', 'promoted_tours_order'):
                if section in data and isinstance(data[section], dict):
                    new_dict = {}
                    for k, v in data[section].items():
                        new_dict[remap_key(k)] = v
                    if new_dict != data[section]:
                        data[section] = new_dict
                        changed = True

            if changed:
                with open(sf, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                updated_files += 1
                account = os.path.basename(os.path.dirname(sf))
                print(f"  Updated settings: {account} ({sf})")

        except Exception as e:
            print(f"  Warning: could not update {sf}: {e}")

    return updated_files


def main():
    if '--list' in sys.argv:
        list_tours()
        return

    dry_run = '--dry-run' in sys.argv

    if not MOVES:
        print("=" * 60)
        print("  Company Splitter")
        print("=" * 60)
        print()
        print("  No moves configured! Edit the MOVES dict in this script.")
        print()
        print("  To see available tours:")
        print("    python scripts/split_company.py --list")
        print()
        print("  Then fill in MOVES like:")
        print('    MOVES = {')
        print('        "new-company-name": [')
        print('            "abc123...",  # Tour Name')
        print('        ],')
        print('    }')
        return

    print("=" * 60)
    print("  Company Splitter")
    print("=" * 60)
    if dry_run:
        print("  DRY RUN - no changes will be made")
    print(f"\n  Source: {SOURCE_COMPANY}")
    for new_co, ids in MOVES.items():
        print(f"  -> {new_co}: {len(ids)} tour(s)")
    print()

    if not dry_run:
        confirm = input("  Proceed? (y/n): ").strip().lower()
        if confirm != 'y':
            print("  Cancelled.")
            return

    all_moved_ids = set()

    for new_company, tour_ids in MOVES.items():
        print(f"\n--- Moving {len(tour_ids)} tour(s) to '{new_company}' ---")
        all_moved_ids.update(tour_ids)

        if dry_run:
            print(f"  Would move {len(tour_ids)} tour(s) in CSVs")
            print(f"  Would move image folders")
            print(f"  Would update account settings keys")
            continue

        # 1. Update CSVs (all languages)
        csv_count = update_csv_files(new_company, tour_ids)

        # 2. Move image folders
        img_count = move_image_folders(new_company, tour_ids)

        # 3. Update account settings (tour keys)
        old_prefix = f"{SOURCE_COMPANY}__"
        new_prefix = f"{new_company}__"
        settings_count = update_account_settings(old_prefix, new_prefix, tour_ids)

        print(f"\n  Summary for '{new_company}':")
        print(f"    CSVs updated: {csv_count} row(s) across all languages")
        print(f"    Image folders moved: {img_count}")
        print(f"    Account settings updated: {settings_count} file(s)")

    # Also update root-level legacy CSVs if they exist
    if not dry_run:
        for legacy_csv in glob.glob(f"tours_{SOURCE_COMPANY}*_with_media.csv"):
            print(f"\n  Note: legacy CSV found at root: {legacy_csv}")
            print(f"  You may want to delete it or re-run the split manually.")

    print("\n" + "=" * 60)
    if dry_run:
        print("  DRY RUN complete. No files changed.")
    else:
        print("  Split complete!")
        print()
        print("  Next steps:")
        print("    1. Drop new images in static/tour_images/<new-company>/<tour_id>/")
        print("    2. Run: python scripts/resync_images_to_csv.py")
        print("    3. Verify in the app, then commit changes")
    print("=" * 60)


if __name__ == '__main__':
    main()
