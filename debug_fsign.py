
import requests
import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.diretta.it/'
}

print("Fetching Diretta.it homepage...")
r = requests.get("https://www.diretta.it/", headers=headers, timeout=15)
print(f"Status: {r.status_code}")

# Search for fsign
# Pattern typically: "6_100_SW9D1eZo"
patterns = [
    r'["\']6_100_([a-zA-Z0-9]{8})["\']',
    r'fsign\s*[:=]\s*["\']([^"\']+)["\']',
    r'x-fsign\s*[:=]\s*["\']([^"\']+)["\']'
]

found = False
for p in patterns:
    matches = re.findall(p, r.text)
    if matches:
        print(f"Found matches for pattern {p}: {matches}")
        found = True

if not found:
    print("No direct fsign pattern found. Printing some script tags...")
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
    for i, s in enumerate(scripts):
        if 'fsign' in s or 'SW9D' in s:
            print(f"\n--- Script {i} contains potential fsign info ---")
            print(s[:500])
