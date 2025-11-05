"""
Smart HTML cleaner that removes noise while keeping valuable tour content
"""
from bs4 import BeautifulSoup
import re

def clean_html_intelligently(html_content):
    """
    Removes navigation, footers, scripts, styles, and other noise
    Keeps the main tour content including FAQs, descriptions, prices, etc.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # STEP 1: Find main content FIRST before removing anything
    main_content = None
    content_selectors = [
        'main',
        'article', 
        '[role="main"]',
        '.page-content',
        '.content',
        '.main-content',
        '#content',
        '#main-content',
        '.tour-detail',
        '.product-detail',
        '.entry-content',
        'body'  # Fallback to body if nothing else found
    ]
    
    for selector in content_selectors:
        main_content = soup.select_one(selector)
        if main_content:
            break
    
    # STEP 2: Now clean within the main content area only
    if main_content:
        # Remove completely useless elements from main content
        for element in main_content.find_all(['script', 'style', 'noscript', 'iframe', 'svg']):
            element.decompose()
        
        # Remove navigation headers and footers within content
        for element in main_content.find_all(['nav', 'header', 'footer']):
            # Check if it's actually navigation or just a section header
            if element.name in ['nav'] or (element.get('class') and any('nav' in c for c in element.get('class'))):
                element.decompose()
        
        # Remove specific noise elements (be less aggressive)
        noise_patterns = [
            'cookie-banner', 'gdpr-notice', 'consent-popup',
            'newsletter-signup', 'social-share-buttons',
            'sticky-header', 'floating-menu'
        ]
        
        for pattern in noise_patterns:
            for element in main_content.find_all(class_=lambda x: x and pattern in str(x).lower()):
                element.decompose()
        
        text = main_content.get_text(separator=' ', strip=True)
    else:
        # Fallback: just get all text
        text = soup.get_text(separator=' ', strip=True)
    
    # Clean up the text
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common repeated navigation text
    noise_phrases = [
        'Skip to content',
        'Menu',
        'Close menu',
        'Search',
        'Cart',
        'Login',
        'Sign up',
        'Subscribe to newsletter',
        'Follow us on',
        'Copyright',
        'All rights reserved',
        'Terms and conditions',
        'Privacy policy',
        'Accept all cookies',
        'Manage cookies'
    ]
    
    for phrase in noise_phrases:
        text = text.replace(phrase, '')
    
    # Remove excessive whitespace again after cleanup
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


# Test it
if __name__ == '__main__':
    print("Testing HTML cleaner...")
    
    # Test with a sample HTML
    sample_html = """
    <html>
    <head>
        <script>console.log('tracking');</script>
        <style>.hidden { display: none; }</style>
    </head>
    <body>
        <nav class="main-navigation">
            <ul><li>Home</li><li>Tours</li></ul>
        </nav>
        <div class="cookie-banner">Accept cookies</div>
        <main class="content">
            <h1>Amazing Tour</h1>
            <p>This is a great tour with beautiful scenery.</p>
            <h2>Frequently Asked Questions</h2>
            <p>Can I bring alcohol? Yes you can!</p>
        </main>
        <footer>
            Copyright 2024. Privacy Policy.
        </footer>
    </body>
    </html>
    """
    
    cleaned = clean_html_intelligently(sample_html)
    print("\nCleaned text:")
    print(cleaned)
    print(f"\nOriginal length: {len(sample_html)} chars")
    print(f"Cleaned length: {len(cleaned)} chars")
    print(f"Reduction: {100 - (len(cleaned)/len(sample_html)*100):.1f}%")

