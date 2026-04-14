
import requests
import re

def test_fsigns():
    # Elenco fsigns trovati nel codice e nell'HTML (Fresh)
    fsigns = [
        "SW9D1eZo", "Mg9H0Flh", "zcDLaZ3b", "boA2KUSu", "0UPxbDYA", "pUAv7KCe", 
        "GU1e3xjd", "dYlOSQOD", "xGrwqq16", "KQMVOQ0g", "ClDjv3V5", "KIShoMk3",
        "W6BOzpK2", "bLyo6mco", "COuk57Ci", "6oug4RRc", "Or1bBrWD", "QVmLl54o",
        "tItR6sEf", "nZi4fKds", "Sd2Q088D", "hl1W8RZs", "MP4jLdJh", "0G3fKGYb"
    ]
    # ID di un match di oggi che ha quote (AN=y)
    m_id = "pMoNkyle" 
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.diretta.it/'
    }
    
    base_url = "https://www.diretta.it/x/feed"
    
    print(f"Testing odds for match {m_id} with different fsigns...")
    
    for fs in fsigns:
        headers['x-fsign'] = fs
        url = f"{base_url}/f_od_1_{m_id}_it_1"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            print(f"fsign: {fs} | Status: {r.status_code} | Length: {len(r.text)}")
            if len(r.text) > 10:
                print(f"  [V] SUCCESS! Content: {r.text[:100]}")
        except Exception as e:
            print(f"fsign: {fs} | Error: {e}")

if __name__ == "__main__":
    test_fsigns()
