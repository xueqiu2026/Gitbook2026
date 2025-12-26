from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import sys

def check_structure(url):
    print(f"Launching Selenium to fetch {url}...")
    try:
        options = Options()
        options.add_argument('--headless')
        # Windows environment often needs these
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        # Determine selector - GitBook v2 often uses these
        selectors = [
            'nav', 
            '[data-testid="sidebar"]', 
            'div[class*="sidebar"]',
            'aside'
        ]
        
        found = None
        for sel in selectors:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                found = elems[0]
                print(f"Found sidebar with: {sel}")
                break
        
        if found:
            # Print structure
            # Let's just print text to see indentation/nesting chars?
            # Or print HTML
            html = found.get_attribute('outerHTML')
            print(html[:2000])
        else:
            print("Sidebar not found even with Selenium.")
            
        driver.quit()

    except Exception as e:
        print(f"Selenium Error: {e}")

if __name__ == "__main__":
    check_structure("https://docs.nado.xyz/faqs")
