
import re
try:
    with open('diretta_fresh.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Try different patterns
    patterns = [
        r'fsign\s*=\s*["\']([^"\']+)["\']',
        r'["\']6_100_([a-zA-Z0-9]{8})["\']',
        r'defaultTopLeagues\s*=\s*\[\s*["\']([^"\']+)["\']'
    ]
    
    for p in patterns:
        m = re.search(p, content)
        if m:
            print(f"Pattern {p} matched: {m.group(1)}")
        else:
            print(f"Pattern {p} did NOT match.")
            
except Exception as e:
    print(f"Error: {e}")
