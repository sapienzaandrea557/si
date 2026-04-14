
import requests
import re

def test_with_cookies():
    m_id = "pMoNkyle"
    s = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    }
    
    print("Fetching homepage for cookies...")
    r = s.get("https://www.diretta.it/", headers=headers)
    
    # Extract fsign
    m = re.search(r'[\"\']6_100_([a-zA-Z0-9]{8})[\"\']', r.text)
    fsign = m.group(1) if m else "SW9D1eZo"
    print(f"Using fsign: {fsign}")
    
    headers.update({
        'x-fsign': fsign,
        'Referer': 'https://www.diretta.it/',
        'Origin': 'https://www.diretta.it',
        'x-requested-with': 'XMLHttpRequest'
    })
    
    url = f"https://www.diretta.it/x/feed/f_od_1_{m_id}_it_1"
    print(f"Testing URL: {url} with cookies...")
    
    r_odds = s.get(url, headers=headers)
    print(f"Status: {r_odds.status_code} | Length: {len(r_odds.text)}")
    if len(r_odds.text) > 10:
        print(f"Content: {r_odds.text[:200]}")

if __name__ == "__main__":
    test_with_cookies()
