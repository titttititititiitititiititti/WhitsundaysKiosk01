"""
smart_html_cleaner.py

Cleans raw HTML from scraped pages into concise, meaningful text.
Removes scripts, styles, navigation, footers, and other non-content elements.
Keeps only tour-relevant information for efficient AI processing.

Usage:
    from smart_html_cleaner import clean_html_intelligently
    cleaned_text = clean_html_intelligently(raw_html)
"""

from bs4 import BeautifulSoup, Comment
import re


def clean_html_intelligently(html: str, max_length: int = 15000) -> str:
    """
    Clean HTML to extract only meaningful tour content.
    
    Args:
        html: Raw HTML string
        max_length: Maximum output length (default 15000 chars for AI processing)
    
    Returns:
        Cleaned text with only tour-relevant content
    """
    if not html:
        return ''
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Step 1: Remove non-content elements entirely
    tags_to_remove = [
        'script', 'style', 'noscript', 'iframe', 'svg', 'path',
        'meta', 'link', 'head', 'footer', 'nav', 'aside',
        'form', 'input', 'button', 'select', 'option',
        'header',  # Usually site navigation, not tour content
    ]
    
    for tag in tags_to_remove:
        for element in soup.find_all(tag):
            element.decompose()
    
    # Step 2: Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Step 3: Remove elements by class/id patterns (common non-content areas)
    # NOTE: Be VERY conservative here - patterns like 'modal', 'menu', 'header' can
    # remove main tour content on some sites (e.g., SeaLink uses modals for booking)
    noise_patterns = [
        'cookie-consent', 'cookie-banner', 'cookie-notice',
        'popup-overlay', 'newsletter-popup',
        'advertisement', 'google-ad', 'adsense',
        'social-share', 'share-buttons',
        'skip-to-content', 'screen-reader',
    ]
    
    for pattern in noise_patterns:
        # Remove by class (exact or partial match for specific patterns)
        for element in soup.find_all(class_=lambda x: x and pattern in str(x).lower()):
            element.decompose()
        # Remove by id
        for element in soup.find_all(id=lambda x: x and pattern in str(x).lower()):
            element.decompose()
    
    # Step 4: Extract text from remaining elements
    # Get the main body content
    body = soup.body if soup.body else soup
    
    # Extract text with smart spacing
    lines = []
    seen_lines = set()
    
    for element in body.descendants:
        if element.name in ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'div', 'span', 'strong', 'em', 'a']:
            text = element.get_text(separator=' ', strip=True)
            
            if not text:
                continue
            
            # Skip VERY short lines (1-2 chars only)
            if len(text) < 3:
                continue
            
            # Keep price-related lines regardless of alpha ratio
            has_price = '$' in text or 'price' in text.lower() or 'adult' in text.lower() or 'child' in text.lower()
            
            # Skip lines that are mostly numbers/symbols (IDs, codes) - but keep prices
            if not has_price:
                alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
                if alpha_ratio < 0.2:  # More lenient
                    continue
            
            # Skip lines with code-like patterns
            if re.search(r'[a-zA-Z]+\d+[a-zA-Z]+\d+', text):  # Mixed alphanumeric like "col2row4"
                continue
            
            # Skip duplicate lines
            text_key = text.lower()[:100]  # First 100 chars for comparison
            if text_key in seen_lines:
                continue
            seen_lines.add(text_key)
            
            # Skip lines that look like JavaScript/CSS
            if any(js_keyword in text.lower() for js_keyword in [
                'function(', 'var ', 'const ', 'let ', '{', '}', 
                'jquery', 'javascript', 'undefined', 'null',
                '@media', '@import', 'px;', 'margin:', 'padding:',
            ]):
                continue
            
            # Add headings with markers
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                lines.append(f"\n**{text}**\n")
            elif element.name == 'li':
                lines.append(f"• {text}")
            else:
                lines.append(text)
    
    # Step 5: Join and clean up
    result = '\n'.join(lines)
    
    # Remove excessive whitespace
    result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 newlines
    result = re.sub(r' {2,}', ' ', result)  # Max 1 space
    result = result.strip()
    
    # FALLBACK: If we got too little content, use simple text extraction
    if len(result) < 200:
        # The smart cleaning was too aggressive - fall back to simple extraction
        fallback_text = soup.get_text(separator='\n', strip=True)
        # Basic cleanup of fallback
        fallback_lines = []
        for line in fallback_text.split('\n'):
            line = line.strip()
            if len(line) > 3 and not line.startswith('{') and not line.startswith('function'):
                fallback_lines.append(line)
        result = '\n'.join(fallback_lines[:500])  # Limit to 500 lines
        result = re.sub(r'\n{3,}', '\n\n', result)
    
    # Step 6: Truncate if too long
    if len(result) > max_length:
        # Try to truncate at a sentence boundary
        truncated = result[:max_length]
        last_period = truncated.rfind('.')
        if last_period > max_length * 0.8:  # Only if we keep most of the content
            result = truncated[:last_period + 1]
        else:
            result = truncated + '...'
    
    return result


def extract_tour_sections(html: str) -> dict:
    """
    Extract specific tour sections from HTML.
    
    Returns dict with keys like: description, includes, itinerary, faq, etc.
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    sections = {
        'description': '',
        'includes': '',
        'highlights': '',
        'itinerary': '',
        'faq': '',
        'pricing': '',
        'duration': '',
        'departure': '',
    }
    
    # Look for common section patterns
    section_keywords = {
        'description': ['description', 'overview', 'about', 'summary'],
        'includes': ['include', 'what\'s included', 'whats included', 'inclusions'],
        'highlights': ['highlight', 'feature', 'why choose'],
        'itinerary': ['itinerary', 'schedule', 'day 1', 'day 2', 'timeline'],
        'faq': ['faq', 'frequently asked', 'questions'],
        'pricing': ['price', 'cost', 'rate', 'booking'],
        'duration': ['duration', 'hours', 'length', 'time'],
        'departure': ['depart', 'meet', 'pickup', 'check-in', 'location'],
    }
    
    # Find sections by heading + following content
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        heading_text = heading.get_text().lower()
        
        for section_name, keywords in section_keywords.items():
            if any(kw in heading_text for kw in keywords):
                # Get content after this heading
                content_parts = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        break  # Stop at next heading
                    text = sibling.get_text(strip=True)
                    if text:
                        content_parts.append(text)
                
                if content_parts:
                    sections[section_name] = '\n'.join(content_parts)
                break
    
    return sections


if __name__ == '__main__':
    # Test with a sample
    test_html = """
    <html>
    <head><script>var x = 1;</script><style>.foo{}</style></head>
    <body>
        <nav>Home | Tours | Contact</nav>
        <h1>Amazing Whitsundays Tour</h1>
        <p>Experience the beautiful Whitsundays on this incredible day trip.</p>
        <h2>What's Included</h2>
        <ul>
            <li>Lunch and refreshments</li>
            <li>Snorkeling equipment</li>
            <li>Professional guide</li>
        </ul>
        <h2>Pricing</h2>
        <p>Adults: $199 | Children: $99</p>
        <footer>Copyright 2024</footer>
    </body>
    </html>
    """
    
    cleaned = clean_html_intelligently(test_html)
    print("Cleaned text:")
    print(cleaned)
    print(f"\nLength: {len(cleaned)} chars")

