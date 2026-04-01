"""
resync_images_to_csv.py - Update CSV image columns from what's on disk

Scans static/tour_images/<company>/<tour_id>/ folders and updates
image_url and image_urls in ALL matching CSVs (all languages).

USAGE:
    python scripts/resync_images_to_csv.py                    # resync all tours
    python scripts/resync_images_to_csv.py sailing-whitsundays  # resync one company
    python scripts/resync_images_to_csv.py --dry-run          # preview without writing
"""
import os
import sys
import csv
import glob
from PIL import Image

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}


def score_image(path):
    """Score an image for thumbnail selection (bigger + good aspect ratio wins)."""
    try:
        im = Image.open(path)
        w, h = im.size
        area = w * h
        aspect = w / max(1, h)
        bonus = 1.2 if 1.3 <= aspect <= 2.2 else 1.0
        return area * bonus
    except Exception:
        return 0


def scan_tour_images(company, tour_id):
    """Return list of image paths for a tour from disk."""
    folder = os.path.join('static', 'tour_images', company, tour_id)
    if not os.path.isdir(folder):
        return []
    images = []
    for f in sorted(os.listdir(folder)):
        ext = os.path.splitext(f)[1].lower()
        if ext in IMAGE_EXTS and 'thumbnail' not in f.lower():
            images.append(os.path.join(folder, f).replace('\\', '/'))
    return images


def find_thumbnail(company, tour_id):
    """Check for an explicit thumbnail file."""
    folder = os.path.join('static', 'tour_images', company, tour_id)
    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        path = os.path.join(folder, f'thumbnail{ext}')
        if os.path.exists(path):
            return path.replace('\\', '/')
    return None


def find_all_csvs():
    """Find all tour CSVs (data/<company>/<lang>/ and root-level)."""
    csvs = []
    for path in glob.glob('data/*/*_with_media.csv'):
        csvs.append(path)
    for path in glob.glob('data/*/*/*_with_media.csv'):
        csvs.append(path)
    for path in glob.glob('*_with_media.csv'):
        csvs.append(path)
    return list(set(csvs))


def update_csv(csv_path, image_map, dry_run=False):
    """Update image columns in a CSV using the image_map.
    image_map: { (company, tour_id): (image_url, image_urls_str) }
    Returns number of rows updated."""
    with open(csv_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames or 'id' not in fieldnames or 'company_name' not in fieldnames:
        return 0

    updated = 0
    for row in rows:
        key = (row.get('company_name', ''), row.get('id', ''))
        if key in image_map:
            new_thumb, new_urls = image_map[key]
            old_thumb = row.get('image_url', '')
            old_urls = row.get('image_urls', '')
            if new_urls != old_urls or new_thumb != old_thumb:
                row['image_url'] = new_thumb
                row['image_urls'] = new_urls
                updated += 1

    if updated > 0 and not dry_run:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return updated


def main():
    dry_run = '--dry-run' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    filter_company = args[0] if args else None

    print("=" * 60)
    print("  Resync Tour Images -> CSVs")
    print("=" * 60)
    if dry_run:
        print("  DRY RUN - no files will be modified")
    if filter_company:
        print(f"  Filtering to company: {filter_company}")
    print()

    # Build image map from disk
    image_map = {}
    tour_images_root = os.path.join('static', 'tour_images')
    if not os.path.isdir(tour_images_root):
        print("No static/tour_images/ directory found.")
        sys.exit(1)

    companies_scanned = 0
    tours_scanned = 0

    for company in sorted(os.listdir(tour_images_root)):
        company_path = os.path.join(tour_images_root, company)
        if not os.path.isdir(company_path):
            continue
        if filter_company and company != filter_company:
            continue
        companies_scanned += 1

        for tour_id in sorted(os.listdir(company_path)):
            tour_path = os.path.join(company_path, tour_id)
            if not os.path.isdir(tour_path):
                continue
            tours_scanned += 1

            images = scan_tour_images(company, tour_id)
            if not images:
                continue

            thumb = find_thumbnail(company, tour_id)
            if not thumb:
                thumb = max(images, key=score_image) if images else images[0]

            image_map[(company, tour_id)] = (thumb, ','.join(images))

    print(f"Scanned {companies_scanned} companie(s), {tours_scanned} tour(s)")
    print(f"Found images for {len(image_map)} tour(s)")
    print()

    # Find and update CSVs
    csvs = find_all_csvs()
    print(f"Found {len(csvs)} CSV file(s) to check")
    print()

    total_updated = 0
    for csv_path in sorted(csvs):
        count = update_csv(csv_path, image_map, dry_run=dry_run)
        if count > 0:
            label = "would update" if dry_run else "updated"
            print(f"  {label} {count} row(s) in {csv_path}")
            total_updated += count

    print()
    print("=" * 60)
    if dry_run:
        print(f"  Would update {total_updated} row(s) across all CSVs.")
        print("  Run without --dry-run to apply changes.")
    else:
        print(f"  Updated {total_updated} row(s) across all CSVs.")
    print("=" * 60)


if __name__ == '__main__':
    main()
