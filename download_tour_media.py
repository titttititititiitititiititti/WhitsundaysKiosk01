"""
download_tour_media.py

Downloads images and videos for each tour listed in a CSV file using Selenium.
Saves media in static/tour_images/<company>/<tour_id or tour_name>/.
Skips files that already exist. Updates the CSV with local paths for images/videos.
Logs errors and missing media.

Requirements:
- pandas
- selenium
- chromedriver_autoinstaller (or manually install ChromeDriver)
- pillow (PIL)

Usage:
    python download_tour_media.py tours_cruisewhitsundays.csv
"""
import os
import sys
import re
import time
import pandas as pd
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import requests
from io import BytesIO
from PIL import Image
import hashlib
import json

# Keywords and extensions to detect likely logos/icons
LOGO_URL_KEYWORDS = {
    'logo', 'favicon', 'site-logo', 'header-logo', 'footer-logo', 'brandmark', 'brand-mark',
    'brand_logo', 'brand', 'powered-by', 'partner-logo'
}
LOGO_ATTR_KEYWORDS = {
    'logo', 'site-logo', 'header-logo', 'footer-logo', 'brand', 'brandmark', 'favicon', 'icon'
}
LOGO_EXTENSIONS = {'.svg', '.svgz', '.ico'}

# Try to import chromedriver_autoinstaller for convenience
try:
    import chromedriver_autoinstaller
    chromedriver_autoinstaller.install()
except ImportError:
    pass  # User must have ChromeDriver in PATH

def safe_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\- ]', '', name).replace(' ', '_')

def ensure_folder(path):
    os.makedirs(path, exist_ok=True)

def download_file(url, dest):
    try:
        if os.path.exists(dest):
            return dest  # Already downloaded
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            # Check image size and transparency before saving
            try:
                img = Image.open(BytesIO(r.content))
                # Skip obvious non-photo formats (logos/icons)
                _, ext = os.path.splitext(dest)
                if ext.lower() in LOGO_EXTENSIONS:
                    print(f"    Skipped (logo extension): {url}")
                    return None
                # Filter out images smaller than 200x200
                if img.width < 200 or img.height < 200:
                    print(f"    Skipped (too small): {url} [{img.width}x{img.height}]")
                    return None
                # Filter out images with transparency
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and 'transparency' in img.info):
                    alpha = img.convert("RGBA").getchannel("A")
                    if alpha.getextrema()[0] < 255:
                        print(f"    Skipped (transparent): {url}")
                        return None
            except Exception as e:
                print(f"    Error processing image {url}: {e}")
                return None
            with open(dest, 'wb') as f:
                f.write(r.content)
            return dest
    except Exception as e:
        print(f"    Error downloading {url}: {e}")
    return None

def compute_md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def is_likely_logo_url(url: str) -> bool:
    try:
        path = urlparse(url).path.lower()
    except Exception:
        path = (url or '').lower()
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1]
    if ext in LOGO_EXTENSIONS:
        return True
    # Keyword match in filename or path segments
    if any(kw in filename for kw in LOGO_URL_KEYWORDS):
        return True
    if any(kw in path for kw in LOGO_URL_KEYWORDS):
        return True
    return False

def extract_media_urls(driver, base_url):
    imgs = driver.find_elements(By.TAG_NAME, 'img')
    img_urls = set()
    for img in imgs:
        src = img.get_attribute('src') or img.get_attribute('data-src')
        if not src:
            continue
        # Filter out likely logos by attributes
        alt = (img.get_attribute('alt') or '').lower()
        cls = (img.get_attribute('class') or '').lower()
        el_id = (img.get_attribute('id') or '').lower()
        if any(kw in alt or kw in cls or kw in el_id for kw in LOGO_ATTR_KEYWORDS):
            # print(f"    Skipped (logo attr): {src}")
            continue
        full_url = urljoin(base_url, src)
        if is_likely_logo_url(full_url):
            # print(f"    Skipped (logo url): {full_url}")
            continue
        img_urls.add(full_url)
    # Videos
    videos = driver.find_elements(By.TAG_NAME, 'video')
    video_urls = set()
    for vid in videos:
        src = vid.get_attribute('src')
        if src:
            video_urls.add(urljoin(base_url, src))
        # Check <source> tags inside <video>
        sources = vid.find_elements(By.TAG_NAME, 'source')
        for s in sources:
            ssrc = s.get_attribute('src')
            if ssrc:
                video_urls.add(urljoin(base_url, ssrc))
        # Poster image
        poster = vid.get_attribute('poster')
        if poster:
            poster_url = urljoin(base_url, poster)
            if not is_likely_logo_url(poster_url):
                img_urls.add(poster_url)
    return list(img_urls), list(video_urls)

def main(csv_path):
    df = pd.read_csv(csv_path)
    # Add video_urls column if not present
    if 'video_urls' not in df.columns:
        df['video_urls'] = ''
    # Setup Selenium with auto-detected ChromeDriver
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    # Auto-install matching ChromeDriver version
    try:
        import chromedriver_autoinstaller
        chromedriver_autoinstaller.install()
    except Exception as e:
        print(f"Warning: Could not auto-install ChromeDriver: {e}")
    
    driver = webdriver.Chrome(options=chrome_options)
    for idx, row in df.iterrows():
        tour_id = row.get('id', str(idx))
        tour_name = row.get('name', f'Tour_{idx}')
        company = row.get('company_name', 'unknown')
        # Handle pandas NaN values properly
        link_more = row.get('link_more_info')
        link_book = row.get('link_booking')
        url = None
        if pd.notna(link_more) and isinstance(link_more, str) and link_more.startswith('http'):
            url = link_more
        elif pd.notna(link_book) and isinstance(link_book, str) and link_book.startswith('http'):
            url = link_book
        if not url:
            print(f"[{tour_id}] No valid URL, skipping.")
            continue
        print(f"[{tour_id}] Processing: {tour_name} ({url})")
        folder = os.path.join('static', 'tour_images', company, safe_filename(tour_id or tour_name))
        ensure_folder(folder)
        try:
            driver.get(url)
            time.sleep(2)  # Wait for JS to load
            img_urls, video_urls = extract_media_urls(driver, url)
            # Download images
            local_imgs = []
            for i, img_url in enumerate(img_urls):
                ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
                dest = os.path.join(folder, f'image_{i+1}{ext}')
                local = download_file(img_url, dest)
                if local:
                    local_imgs.append(local.replace('\\', '/'))
            # Download videos
            local_vids = []
            for i, vid_url in enumerate(video_urls):
                ext = os.path.splitext(urlparse(vid_url).path)[1] or '.mp4'
                dest = os.path.join(folder, f'video_{i+1}{ext}')
                local = download_file(vid_url, dest)
                if local:
                    local_vids.append(local.replace('\\', '/'))
            # Dedupe images by content hash and score for thumbnail
            unique_imgs = []
            seen_hashes = set()
            for p in local_imgs:
                try:
                    md5 = compute_md5(p)
                    if md5 in seen_hashes:
                        try:
                            os.remove(p)
                        except Exception:
                            pass
                        continue
                    seen_hashes.add(md5)
                    unique_imgs.append(p)
                except Exception:
                    unique_imgs.append(p)

            def score_image(path: str) -> float:
                try:
                    im = Image.open(path)
                    w, h = im.size
                    area = w * h
                    aspect = w / max(1, h)
                    aspect_bonus = 1.0
                    if 1.3 <= aspect <= 2.2:
                        aspect_bonus = 1.2
                    # Near-monochrome penalty
                    stat = im.convert('RGB').getextrema()
                    # getextrema returns (min,max) per channel; compute channel ranges
                    ranges = [(ch[1]-ch[0]) for ch in stat]
                    mono_penalty = 0.9 if max(ranges) < 15 else 1.0
                    return area * aspect_bonus * mono_penalty
                except Exception:
                    return 0

            # Choose best image as thumbnail candidate
            best_img = None
            if unique_imgs:
                best_img = max(unique_imgs, key=score_image)

            # Save manifest
            try:
                manifest = {
                    'source_url': url,
                    'images': [p.replace('\\','/') for p in unique_imgs],
                    'videos': [],
                    'thumbnail': best_img.replace('\\','/') if best_img else ''
                }
                with open(os.path.join(folder, 'media_manifest.json'), 'w', encoding='utf-8') as mf:
                    json.dump(manifest, mf, ensure_ascii=False, indent=2)
            except Exception:
                pass

            # Update DataFrame
            if local_imgs:
                df.at[idx, 'image_url'] = (best_img or unique_imgs[0]).replace('\\','/')
                df.at[idx, 'image_urls'] = ','.join([p.replace('\\','/') for p in unique_imgs])
            if local_vids:
                df.at[idx, 'video_urls'] = ','.join(local_vids)
            print(f"    Downloaded {len(local_imgs)} images, {len(local_vids)} videos.")
        except Exception as e:
            print(f"    Error processing {tour_name}: {e}")
    driver.quit()
    # Save updated CSV (avoid double _with_media suffix)
    if '_with_media.csv' in csv_path:
        out_csv = csv_path  # Overwrite the same file
    else:
    out_csv = csv_path.replace('.csv', '_with_media.csv')
    df.to_csv(out_csv, index=False)
    print(f"Done. Updated CSV saved as {out_csv}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python download_tour_media.py <tour_csv_file1> [<tour_csv_file2> ...]")
        sys.exit(1)
    for csv_path in sys.argv[1:]:
        print(f"\n=== Processing {csv_path} ===")
        main(csv_path) 