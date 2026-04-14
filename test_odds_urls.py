
import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.diretta.it/',
    'x-fsign': 'SW9D1eZo'
}

match_id = "pMoNkyle"
base_url = "https://www.diretta.it/x/feed"

suffixes = ["it_1", "it_2", "it_3", "en_1", "it_0", "it_4"]
types = ["f_od_1", "f_od_2", "f_od_3", "f_od_4", "f_od_5"]

for t in types:
    for s in suffixes:
        url = f"{base_url}/{t}_{match_id}_{s}"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and len(r.text) > 10:
            print(f"SUCCESS: {url} returned {len(r.text)} bytes.")
            print(f"Data: {r.text[:200]}")
        else:
            # print(f"FAIL: {url} ({r.status_code}) - len: {len(r.text)}")
            pass
