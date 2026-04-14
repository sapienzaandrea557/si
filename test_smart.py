
import sys
import os
import time

# Add current directory to path
sys.path.append(os.getcwd())

from si import FootballPredictor, DirettaScraper, Colors

def test_search_and_odds():
    print(f"{Colors.CYAN}--- SMART BRAIN AI: TEST RICERCA E QUOTE ---{Colors.ENDC}")
    FD_KEY = "39df5a49a6764a999a9b14cafc9ca111"
    API_KEY = "c5d860df8229a7ad907688ad36a7693a"
    p = FootballPredictor(API_KEY, fd_key=FD_KEY)
    
    # Cerchiamo l'Inter (ID 505) o un'altra squadra
    query = "inter"
    print(f"\nRicerca squadra: {query}...")
    
    # Provo a saltare la ricerca e usare un match ID fisso se possibile
    # Ma prima vediamo se get_matches funziona
    print("Test get_matches(0)...")
    matches = p.diretta.get_matches(day_offset=0)
    print(f"Matches found: {len(matches)}")
    
    if matches:
        # Cerchiamo il primo match che ha odds (has_odds=True)
        m = None
        for dm in matches:
            if dm.get('has_odds'):
                m = dm
                break
        if not m: m = matches[0]
        
        h, a = m['home'], m['away']
        print(f"{Colors.GREEN}[V] Match trovato: {h} vs {a} (ID: {m['id']}){Colors.ENDC}")
        
        # Tentativo recupero quote
        print(f"Tentativo recupero quote per {m['id']}...")
        # Prefisso d_ forza l'uso di DirettaScraper.get_odds
        odds = p.get_odds(f"d_{m['id']}", h_name=h, a_name=a, date_str=time.strftime('%Y-%m-%d'))
        
        if odds and odds.get('1X2') and odds['1X2'].get('Home'):
            print(f"{Colors.GREEN}[V] Quote REALI trovate: {odds['1X2']}{Colors.ENDC}")
            
            # Analisi
            print("\nEseguo analisi match...")
            # Mock fixture data for analysis
            match_data = {
                "fixture": {"id": f"d_{m['id']}", "date": time.strftime('%Y-%m-%dT20:45:00+00:00')},
                "teams": {"home": {"name": h, "id": f"d_{m['id']}_h"}, "away": {"name": a, "id": f"d_{m['id']}_a"}},
                "league": {"id": 135, "name": "Serie A"} # Serie A mock
            }
            p.analyze_match_list([match_data], title="TEST ANALISI REALE")
        else:
            print(f"{Colors.YELLOW}[!] Quote REALI non trovate. Il sistema userà quote STIMATE (Fair Odds).{Colors.ENDC}")
            # Vediamo cosa succede con quote stimate
            match_data = {
                "fixture": {"id": f"d_{m['id']}", "date": time.strftime('%Y-%m-%dT20:45:00+00:00')},
                "teams": {"home": {"name": h, "id": f"d_{m['id']}_h"}, "away": {"name": a, "id": f"d_{m['id']}_a"}},
                "league": {"id": 135, "name": "Serie A"}
            }
            p.analyze_match_list([match_data], title="TEST ANALISI STIMATA")

if __name__ == "__main__":
    test_search_and_odds()
