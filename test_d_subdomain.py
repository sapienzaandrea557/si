
import requests

def test_d_subdomain():
    m_id = "pMoNkyle"
    fsign = "SW9D1eZo"
    headers = {
        'x-fsign': fsign,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://www.diretta.it/',
        'Origin': 'https://www.diretta.it'
    }
    
    url = f"https://d.diretta.it/x/feed/f_od_1_{m_id}_it_1"
    print(f"Testing d.diretta.it URL: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {r.status_code} | Length: {len(r.text)}")
        if len(r.text) > 10:
            print(f"Content: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_d_subdomain()
