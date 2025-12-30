from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def dump_sidebar():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    try:
        print("Navigating to Nado docs...")
        driver.get("https://docs.nado.xyz/")
        
        # Wait for sidebar
        print("Waiting for sidebar...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/onboarding-tutorial']"))
        )
        
        # Expand Onboarding
        print("Expanding Onboarding Tutorial...")
        onboarding = driver.find_element(By.CSS_SELECTOR, "a[href='/onboarding-tutorial']")
        # Use JS click to be safe
        driver.execute_script("arguments[0].click();", onboarding)
        time.sleep(2) # Wait for expansion animation
        
        # Capture HTML
        print("Capturing HTML...")
        # Get the common ancestor for sidebar
        # Often 'nav' or 'aside' or div with specific class
        sidebar = driver.execute_script("""
            // Find common parent of Onboarding
            const el = document.querySelector("a[href='/onboarding-tutorial']");
            let p = el.parentElement;
            while(p && p.tagName !== 'ASIDE' && p.id !== 'table-of-contents') {
                p = p.parentElement;
            }
            return p ? p.outerHTML : document.body.outerHTML;
        """)
        
        with open("sidebar_debug.html", "w", encoding="utf-8") as f:
            f.write(sidebar)
        print("Sidebar dumped to sidebar_debug.html")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    dump_sidebar()
