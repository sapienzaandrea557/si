
import requests
import re

def test_specific_match_odds(m_id):
    headers = {
        'x-fsign': 'SW9D1eZo',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://www.diretta.it/',
        'Origin': 'https://www.diretta.it'
    }
    
    # Try different feed types
    feed_types = ["f_od_1", "f_od_2", "f_od_3", "f_od_4"]
    locales = ["it_1", "it_2", "en_1"]
    
    print(f"--- Testing Odds for Match ID: {m_id} ---")
    
    for ft in feed_types:
        for loc in locales:
            url = f"https://www.diretta.it/x/feed/{ft}_{m_id}_{loc}"
            try:
                r = requests.get(url, headers=headers, timeout=5)
                print(f"URL: {url} | Status: {r.status_code} | Length: {len(r.text)}")
                if len(r.text) > 50:
                    print(f"  [V] SUCCESS! Preview: {r.text[:200]}")
                    return True
            except Exception as e:
                print(f"  [!] Error for {url}: {e}")
    return False

if __name__ == "__main__":
    # Test with Bayern vs Real Madrid (from previous output)
    test_specific_match_odds("zXC8QVx3")
