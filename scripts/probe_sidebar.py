import requests
from bs4 import BeautifulSoup
import sys

def probe(url):
    print(f"Fetching {url}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Selectors to look for sidebar
        selectors = [
            'nav', 
            '[data-testid="sidebar"]', 
            '.sidebar', 
            'aside'
        ]
        
        found = False
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                print(f"\n[!] Found sidebar with selector: {sel}")
                # Print the first 2000 chars of structure to analyze nesting
                print(elem.prettify()[:2000])
                found = True
        
        if not found:
            print("No obvious sidebar found. Printing first 10 links:")
            for a in soup.find_all('a', href=True)[:10]:
                print(a)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    probe("https://docs.nado.xyz/faqs")
