import requests
from bs4 import BeautifulSoup
import json
import sys

def analyze(url):
    print(f"Fetching {url}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Check for Next.js data
        next_data = soup.find('script', id='__NEXT_DATA__')
        if next_data:
            print("Found __NEXT_DATA__!")
            data = json.loads(next_data.string)
            # Print keys to explore structure
            print("Keys:", data.keys())
            
            # Try to find sidebar/nav props
            props = data.get('props', {})
            page_props = props.get('pageProps', {})
            print("PageProps Keys:", page_props.keys())
            
            # Look deeply?
            # Often in 'pageProps' -> 'sidebar' or 'layout' or 'manual' or 'space'
            
            # Dump a small part to see
            print(str(page_props)[:500])
        else:
            print("No __NEXT_DATA__ found.")
            
            # Check for other JSON blobs
            scripts = soup.find_all('script', type='application/json')
            for s in scripts:
                print(f"Found JSON script: {s.get('id')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze("https://docs.nado.xyz/faqs")
