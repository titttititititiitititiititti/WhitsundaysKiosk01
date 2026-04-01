"""
download_from_urls.py - Scrape images from webpages into company tour folders

Give it a company name and a list of webpage URLs.
For each URL it opens the page, scrapes every image that passes the quality
filters (min 240px, no logos, no transparent/solid-color images), deduplicates,
and saves them into static/tour_images/<company>/<folder_name>/.

USAGE:
    python scripts/download_from_urls.py

Configure PAGES below before running.
After downloading, run: python scripts/resync_images_to_csv.py
"""
import os
import sys
import re
import time
import hashlib
import json
from urllib.parse import urljoin, urlparse
from io import BytesIO

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

# =============================================================================
# CONFIGURE HERE
# =============================================================================
# Images are saved to your Desktop: Desktop/scraped_images/<folder_name>/
OUTPUT = os.path.join(os.path.expanduser("~"), "Desktop", "scraped_images")

# Each entry = one folder of images. Name it whatever you want.
PAGES = {
    "Whitsunday Blue": "https://whitsundayblue.com/gallery",
    "Power Play Whitsundays": "https://www.powerplaywhitsundays.com/gallery",
    "Whitsunday Blue": "https://whitsundayblue.com/gallery",
    "Providence Sailing": "https://www.providencesailing.com.au/about",
    "Apoolo Maxi-Yacht": "https://apollomaxiyacht.com.au/gallery/", 
    "True Blue Sailing": "https://truebluesailing.com.au/atlantic-clipper-overnight-tour/",
    "True Blue Sailing": "https://truebluesailing.com.au/new-horizon-overnight-tour/",
    "Summer Jo": "https://summerjo.com.au/gallery"
    

    #    "another-name": "https://example.com/some-page",
}
# =============================================================================

# --- Filtering config ---
MIN_SIZE = 240          # minimum width AND height in px
LOGO_URL_KEYWORDS = {
    'logo', 'favicon', 'site-logo', 'header-logo', 'footer-logo', 'brandmark',
    'brand-mark', 'brand_logo', 'brand', 'powered-by', 'partner-logo', 'icon'
}
LOGO_ATTR_KEYWORDS = {
    'logo', 'site-logo', 'header-logo', 'footer-logo', 'brand', 'brandmark',
    'favicon', 'icon'
}
LOGO_EXTENSIONS = {'.svg', '.svgz', '.ico'}
MAX_SOLID_RATIO = 0.10  # skip images where >10% of pixels are a single color


def is_likely_logo_url(url):
    try:
        path = urlparse(url).path.lower()
    except Exception:
        path = (url or '').lower()
    filename = os.path.basename(path)
    ext = os.path.splitext(filename)[1]
    if ext in LOGO_EXTENSIONS:
        return True
    if any(kw in filename for kw in LOGO_URL_KEYWORDS):
        return True
    if any(kw in path for kw in LOGO_URL_KEYWORDS):
        return True
    return False


def is_solid_or_flat(img):
    """Check if an image is mostly a single solid color (logos, banners, etc.)"""
    try:
        small = img.convert('RGB').resize((50, 50))
        pixels = list(small.getdata())
        total = len(pixels)
        from collections import Counter
        counts = Counter(pixels)
        most_common_count = counts.most_common(1)[0][1]
        return (most_common_count / total) > MAX_SOLID_RATIO
    except Exception:
        return False


def compute_md5(data):
    return hashlib.md5(data).hexdigest()


def extract_image_urls(driver, base_url):
    """Extract all candidate image URLs from the page using every method possible."""
    from selenium.webdriver.common.by import By
    img_urls = set()

    def add_url(u):
        if not u or len(u) < 10:
            return
        full = urljoin(base_url, u)
        if not is_likely_logo_url(full):
            img_urls.add(full)

    # 1. <img> tags - src, data-src, data-lazy-src, data-original
    for img in driver.find_elements(By.TAG_NAME, 'img'):
        for attr in ('src', 'data-src', 'data-lazy-src', 'data-original', 'data-bg', 'data-image'):
            val = img.get_attribute(attr)
            if val and ('http' in val or val.startswith('/')):
                alt = (img.get_attribute('alt') or '').lower()
                cls = (img.get_attribute('class') or '').lower()
                if not any(kw in alt or kw in cls for kw in LOGO_ATTR_KEYWORDS):
                    add_url(val)
        # srcset
        srcset = img.get_attribute('srcset') or ''
        for part in srcset.split(','):
            url = part.strip().split()[0] if part.strip() else ''
            if url:
                add_url(url)

    # 2. CSS background-image on ALL elements (catches gallery divs, sections, etc.)
    try:
        bg_urls = driver.execute_script("""
            var urls = [];
            document.querySelectorAll('*').forEach(function(el) {
                var bg = getComputedStyle(el).backgroundImage;
                if (bg && bg !== 'none') {
                    var matches = bg.match(/url\\(["']?([^"')]+)["']?\\)/g);
                    if (matches) {
                        matches.forEach(function(m) {
                            var u = m.replace(/url\\(["']?/, '').replace(/["']?\\)/, '');
                            if (u && u.length > 10) urls.push(u);
                        });
                    }
                }
                // data attributes that might hold image urls
                ['data-bg', 'data-src', 'data-image', 'data-background', 
                 'data-lazy', 'data-original', 'data-thumb'].forEach(function(attr) {
                    var v = el.getAttribute(attr);
                    if (v && (v.startsWith('http') || v.startsWith('/'))) urls.push(v);
                });
            });
            return urls;
        """)
        for u in (bg_urls or []):
            add_url(u)
    except Exception:
        pass

    # 3. <a> tags linking directly to images
    for a in driver.find_elements(By.TAG_NAME, 'a'):
        href = a.get_attribute('href') or ''
        ext = os.path.splitext(urlparse(href).path)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            add_url(href)

    # 4. <source> and <video> posters
    for vid in driver.find_elements(By.TAG_NAME, 'video'):
        poster = vid.get_attribute('poster')
        if poster:
            add_url(poster)

    # 5. Scan page source for any remaining image URLs the DOM didn't expose
    try:
        source = driver.page_source
        import re as _re
        for match in _re.findall(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)', source, _re.IGNORECASE):
            add_url(match)
    except Exception:
        pass

    return list(img_urls)


def download_and_filter(url):
    """Download an image URL, filter it, return (bytes, PIL.Image) or None."""
    import requests
    from PIL import Image

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        img = Image.open(BytesIO(r.content))

        # Size filter
        if img.width < MIN_SIZE or img.height < MIN_SIZE:
            return None

        # Extension filter
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if ext in LOGO_EXTENSIONS:
            return None

        # Transparency filter
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and 'transparency' in img.info):
            alpha = img.convert("RGBA").getchannel("A")
            if alpha.getextrema()[0] < 255:
                return None

        # Solid color filter
        if is_solid_or_flat(img):
            return None

        return r.content, img
    except Exception:
        return None


def scrape_page(driver, url, folder):
    """Scrape a single page and save images to folder."""
    from PIL import Image

    os.makedirs(folder, exist_ok=True)
    print(f"\n  Opening: {url}")

    try:
        driver.get(url)
        time.sleep(5)  # initial wait for JS frameworks to boot

        # Scroll slowly through the entire page to trigger all lazy loaders
        page_height = driver.execute_script("return document.body.scrollHeight")
        scroll_pos = 0
        while scroll_pos < page_height:
            scroll_pos += 400
            driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
            time.sleep(0.4)
            # Page may grow as content loads
            page_height = driver.execute_script("return document.body.scrollHeight")

        # Scroll back to top and wait for any final loads
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        # Click any "load more" / "show all" buttons if present
        try:
            from selenium.webdriver.common.by import By
            for btn in driver.find_elements(By.TAG_NAME, 'button') + driver.find_elements(By.TAG_NAME, 'a'):
                txt = (btn.text or '').lower()
                if any(kw in txt for kw in ('load more', 'show more', 'show all', 'view all', 'see all')):
                    btn.click()
                    time.sleep(3)
                    break
        except Exception:
            pass
    except Exception as e:
        print(f"  Error loading page: {e}")
        return 0

    img_urls = extract_image_urls(driver, url)
    print(f"  Found {len(img_urls)} candidate image(s)")

    saved = 0
    seen_hashes = set()

    for i, img_url in enumerate(img_urls):
        result = download_and_filter(img_url)
        if result is None:
            continue

        data, img = result

        # Deduplicate by content hash
        h = compute_md5(data)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        ext = os.path.splitext(urlparse(img_url).path)[1] or '.jpg'
        if ext.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            ext = '.jpg'

        dest = os.path.join(folder, f'image_{saved + 1}{ext}')
        with open(dest, 'wb') as f:
            f.write(data)

        saved += 1
        print(f"    Saved image_{saved}{ext} ({img.width}x{img.height})")

    # Pick best thumbnail
    if saved > 0:
        images = []
        for f in sorted(os.listdir(folder)):
            fpath = os.path.join(folder, f)
            if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.webp'):
                try:
                    img = Image.open(fpath)
                    area = img.width * img.height
                    aspect = img.width / max(1, img.height)
                    score = area * (1.2 if 1.3 <= aspect <= 2.2 else 1.0)
                    images.append((fpath, score))
                except Exception:
                    pass
        if images:
            best = max(images, key=lambda x: x[1])[0]
            manifest = {
                'source_url': url,
                'images': [os.path.join(folder, f).replace('\\', '/') for f in sorted(os.listdir(folder))
                           if os.path.splitext(f)[1].lower() in ('.jpg', '.jpeg', '.png', '.webp', '.gif')],
                'thumbnail': best.replace('\\', '/')
            }
            with open(os.path.join(folder, 'media_manifest.json'), 'w', encoding='utf-8') as mf:
                json.dump(manifest, mf, indent=2)

    return saved


def main():
    if not PAGES:
        print("=" * 60)
        print("  Image Scraper - Webpage to Company Folders")
        print("=" * 60)
        print()
        print("  No pages configured! Edit this script and set:")
        print()
        print('  PAGES = {')
        print('      "folder-name": "https://example.com/tour-page",')
        print('      "another":     "https://othersite.com/page",')
        print('  }')
        print()
        print(f"  Images are saved to: {OUTPUT}/<folder_name>/")
        return

    print("=" * 60)
    print(f"  Image Scraper -> {OUTPUT}")
    print("=" * 60)
    print(f"  {len(PAGES)} page(s) to scrape")
    print(f"  Filters: min {MIN_SIZE}px, no logos, no solid colors")
    print()

    # Setup Selenium
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    try:
        import chromedriver_autoinstaller
        chromedriver_autoinstaller.install()
    except ImportError:
        pass

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--window-size=1920,1080')
    driver = webdriver.Chrome(options=chrome_options)

    total = 0

    for folder_name, url in PAGES.items():
        folder = os.path.join(OUTPUT, folder_name)
        print(f"\n[{folder_name}]")
        count = scrape_page(driver, url, folder)
        print(f"  -> Saved {count} image(s) to {folder}")
        total += count

    driver.quit()

    print()
    print("=" * 60)
    print(f"  Done! Scraped {total} image(s) across {len(PAGES)} page(s)")
    print(f"  Saved to: {OUTPUT}")
    print()
    print("  Next step: run this to update all CSVs:")
    print("    python scripts/resync_images_to_csv.py")
    print("=" * 60)


if __name__ == '__main__':
    main()
