import os
import sys
from urllib.parse import urlparse
from ddgs import DDGS

# [DISC-001] Add persistent blacklist support for declined homepages
BLACKLIST_FILE = 'homepage_blacklist.txt'

def get_homepage(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"

def load_blacklist():
    blacklisted = set()
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    blacklisted.add(url)
    return blacklisted

def search_tour_companies(location, num_results=150, blacklist=None):
    query = f"tours in {location}"
    results = []
    seen_homepages = set()
    raw_results = []
    blacklist = blacklist or set()
    with DDGS() as ddgs:
        for r in ddgs.text(query, region='au-en', safesearch='Moderate', max_results=num_results):
            raw_results.append(r)
            link = r.get('href') or r.get('url')
            if not link:
                continue
            homepage = get_homepage(link)
            # Skip blacklisted homepages
            if homepage in blacklist:
                continue
            if homepage not in seen_homepages:
                seen_homepages.add(homepage)
                results.append(homepage)
            if len(results) >= num_results:
                break
    if not results:
        print('DEBUG: No homepages found. Raw search results:')
        for r in raw_results:
            print(r)
    return results

def manual_review(homepages):
    print("\nManual review: Press 'y' to keep, 'n' to blacklist, any other key to skip.\n")
    approved = []
    blacklisted = []
    for url in homepages:
        ans = input(f"Keep this homepage? {url} [y/N]: ").strip().lower()
        if ans == 'y':
            approved.append(url)
        elif ans == 'n':
            blacklisted.append(url)
    return approved, blacklisted

def main():
    if len(sys.argv) < 2:
        print("Usage: python find_tour_company_homepages.py <location>")
        sys.exit(1)
    location = ' '.join(sys.argv[1:])
    print(f"Searching for tour company homepages in: {location}")
    blacklist = load_blacklist()
    homepages = search_tour_companies(location, blacklist=blacklist)
    approved, newly_blacklisted = manual_review(homepages)
    with open('tour_company_homepages.txt', 'w', encoding='utf-8') as f:
        for url in approved:
            f.write(url + '\n')
    print(f"Saved {len(approved)} approved homepages to tour_company_homepages.txt.")
    # Persist newly blacklisted URLs
    if newly_blacklisted:
        # Append only URLs not already in blacklist
        to_write = [u for u in newly_blacklisted if u not in blacklist]
        if to_write:
            with open(BLACKLIST_FILE, 'a', encoding='utf-8') as bf:
                for u in to_write:
                    bf.write(u + '\n')
            print(f"Added {len(to_write)} URLs to {BLACKLIST_FILE}.")

if __name__ == '__main__':
    main() 