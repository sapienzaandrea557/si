
import requests
import re
import time

def test():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.diretta.it/'
    }
    
    print("--- Testing Diretta.it Access ---")
    try:
        r = requests.get("https://www.diretta.it/", headers=headers, timeout=15)
        print(f"Main Page Status: {r.status_code}")
        
        # Extract fsign
        # Search for fsign in various ways
        fsign_patterns = [
            r'fsign\s*=\s*[\'"]([^\'"]+)[\'"]',
            r'fsign\s*:\s*[\'"]([^\'"]+)[\'"]',
            r'fsign\s*([^\s;]+)'
        ]
        
        fsign = None
        for pattern in fsign_patterns:
            match = re.search(pattern, r.text)
            if match:
                fsign = match.group(1)
                print(f"Found fsign with pattern {pattern}: {fsign}")
                break
        
        if not fsign:
            print("Could not find fsign in main page content.")
            # Print a snippet of where fsign might be
            idx = r.text.find('fsign')
            if idx != -1:
                print(f"Snippet around 'fsign': {r.text[idx-20:idx+100]}")
            headers['x-fsign'] = 'SW9D1eZo' # Default
        else:
            headers['x-fsign'] = fsign
        url = "https://www.diretta.it/x/feed/f_1_0_2_it_1"
        print(f"Fetching matches from: {url}")
        r_matches = requests.get(url, headers=headers, timeout=15)
        print(f"Matches Feed Status: {r_matches.status_code}")
        
        if r_matches.status_code == 200:
            content = r_matches.text
            print(f"Content Length: {len(content)}")
            if content:
                print(f"Content Preview (first 100 chars): {content[:100]}")
                # Count matches by looking for AA (match delimiter in Diretta feed)
                match_count = content.count('AA÷')
                print(f"Estimated matches: {match_count}")
                
                if match_count > 0:
                    # Find a match with odds (AN÷y)
                    matches_raw = content.split('AA÷')
                    found_m_id = None
                    for m_raw in matches_raw[1:]:
                        if 'AN÷y' in m_raw:
                            next_sep = m_raw.find('¬')
                            found_m_id = m_raw[:next_sep]
                            break
                    
                    if found_m_id:
                        print(f"Match with odds found! ID: {found_m_id}")
                        # Try fetching odds for this match
                        odds_url = f"https://www.diretta.it/x/feed/f_od_1_{found_m_id}_it_1"
                        print(f"Fetching odds from: {odds_url}")
                        r_odds = requests.get(odds_url, headers=headers, timeout=15)
                        print(f"Odds Feed Status: {r_odds.status_code}")
                        if r_odds.status_code == 200:
                            print(f"Odds Content Length: {len(r_odds.text)}")
                            if 'OD÷' in r_odds.text:
                                print("SUCCESS: Odds found!")
                                print(f"Odds data: {r_odds.text[:200]}")
                            else:
                                print("Odds feed empty or no odds for this match.")
                    else:
                        print("No match with odds found in the feed.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test()
