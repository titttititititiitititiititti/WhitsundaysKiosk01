"""
Selenium-based scraper that expands FAQs, pricing dropdowns, and captures all dynamic content
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def fetch_with_selenium(url, expand_faqs=True, expand_pricing=True, wait_time=5):
    """
    Fetch a webpage with Selenium and expand all interactive elements
    
    Args:
        url: URL to fetch
        expand_faqs: Whether to expand FAQ accordions
        expand_pricing: Whether to expand pricing dropdowns
        wait_time: Seconds to wait for page load
    
    Returns:
        HTML content as string
    """
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Wait for page to load
        time.sleep(wait_time)
        
        # Expand pricing options (look for common Cruise Whitsundays patterns)
        if expand_pricing:
            try:
                # Try to find and click pricing dropdowns/accordions
                pricing_selectors = [
                    'button[class*="price"]',
                    'button[class*="option"]',
                    'div[class*="pricing"] button',
                    'select[name*="price"]',
                    'select[name*="option"]',
                    '[class*="accordion"] button',
                    '[class*="dropdown"] button',
                    'button[aria-expanded="false"]'
                ]
                
                for selector in pricing_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            try:
                                if elem.is_displayed():
                                    driver.execute_script("arguments[0].click();", elem)
                                    time.sleep(0.5)
                            except:
                                pass
                    except:
                        pass
                
                # Try to expand select/option elements
                try:
                    selects = driver.find_elements(By.TAG_NAME, 'select')
                    for select in selects:
                        if select.is_displayed():
                            # Get all options from the select
                            options = select.find_elements(By.TAG_NAME, 'option')
                            # Click through to load any dynamic content
                            for option in options[:5]:  # Limit to first 5 to avoid too much delay
                                try:
                                    option.click()
                                    time.sleep(0.3)
                                except:
                                    pass
                except:
                    pass
                    
            except Exception as e:
                print(f"      Warning: Could not expand pricing: {e}")
        
        # Expand FAQ accordions
        if expand_faqs:
            try:
                faq_selectors = [
                    'button[class*="accordion"]',
                    'button[class*="faq"]',
                    'div[class*="faq"] button',
                    '[class*="collapse"] button',
                    'button[aria-expanded="false"]'
                ]
                
                for selector in faq_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            try:
                                if elem.is_displayed() and not elem.get_attribute('aria-expanded') == 'true':
                                    driver.execute_script("arguments[0].click();", elem)
                                    time.sleep(0.3)
                            except:
                                pass
                    except:
                        pass
                        
            except Exception as e:
                print(f"      Warning: Could not expand FAQs: {e}")
        
        # Scroll to load lazy-loaded content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        # Get the final HTML
        html = driver.page_source
        return html
        
    except Exception as e:
        print(f"      Error fetching {url}: {e}")
        return ""
    finally:
        if driver:
            driver.quit()
