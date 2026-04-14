
import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.diretta.it/',
    'x-fsign': 'SW9D1eZo'
}

print("--- FETCHING MATCHES ---")
url = "https://www.diretta.it/x/feed/f_1_0_2_it_1"
r = requests.get(url, headers=headers, timeout=15)

if r.status_code == 200:
    content = r.text
    matches_raw = content.split('AA÷')
    count = 0
    for m_raw in matches_raw[1:]:
        if 'AN÷y' in m_raw:
            next_sep = m_raw.find('¬')
            m_id = m_raw[:next_sep]
            
            # Get team names
            home = "N/D"
            away = "N/D"
            parts = m_raw.split('¬')
            for p in parts:
                if p.startswith('AE÷'): home = p[3:]
                if p.startswith('AF÷'): away = p[3:]
            
            print(f"\nMatch found: {home} vs {away} (ID: {m_id})")
            
            # Try odds
            odds_url = f"https://www.diretta.it/x/feed/f_od_1_{m_id}_it_1"
            r_odds = requests.get(odds_url, headers=headers, timeout=10)
            if r_odds.status_code == 200 and len(r_odds.text) > 10:
                print(f"  [SUCCESS] Odds feed: {r_odds.text[:100]}...")
            else:
                print(f"  [FAIL] Odds feed empty (Len: {len(r_odds.text)})")
            
            count += 1
            if count >= 10: break
else:
    print(f"Failed to fetch matches: {r.status_code}")
