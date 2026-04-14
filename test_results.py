
import sys
import os
import json
from datetime import datetime, timedelta

# Aggiungi directory corrente al path
sys.path.append(os.getcwd())

from si import FootballPredictor, Colors

def test_reality_check():
    print(f"{Colors.CYAN}--- TEST RECUPERO RISULTATI REALI (PRESENTI E PASSATI) ---{Colors.ENDC}")
    FD_KEY = "39df5a49a6764a999a9b14cafc9ca111"
    API_KEY = "c5d860df8229a7ad907688ad36a7693a"
    p = FootballPredictor(API_KEY, fd_key=FD_KEY)
    
    # 1. Verifica match passati (ieri)
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"\n[1] Verifica match passati ({yesterday})...")
    
    # Recuperiamo match da ESPN per ieri (fallback principale funzionante)
    past_matches = p.get_espn_fixtures(yesterday, quiet=True, top_only=False)
    
    if past_matches:
        finished = [m for m in past_matches if m['fixture']['status']['short'] in ["FT", "Final", "AET"]]
        print(f"    [V] Trovati {len(past_matches)} match totali ieri.")
        print(f"    [V] Trovati {len(finished)} match terminati con risultato reale.")
        if finished:
            m = finished[0]
            print(f"    Esempio Risultato: {m['teams']['home']['name']} {m['teams']['home']['score']} - {m['teams']['away']['score']} {m['teams']['away']['name']}")
    else:
        print(f"    [!] Nessun match trovato per ieri tramite ESPN.")

    # 2. Verifica match presenti (oggi)
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n[2] Verifica match presenti ({today})...")
    
    curr_matches = p.get_espn_fixtures(today, quiet=True, top_only=False)
    
    if curr_matches:
        live = [m for m in curr_matches if any(char.isdigit() for char in str(m['fixture']['status']['short'])) or str(m['fixture']['status']['short']).upper() in ["HT", "LIVE", "1H", "2H"]]
        scheduled = [m for m in curr_matches if m not in live and m['fixture']['status']['short'] not in ["FT", "Final"]]
        
        print(f"    [V] Trovati {len(curr_matches)} match totali oggi.")
        print(f"    [V] Match Live/Finiti: {len(live) + (len(curr_matches) - len(scheduled) - len(live))}")
        print(f"    [V] Match in programma: {len(scheduled)}")
        
        if live:
            m = live[0]
            print(f"    Esempio Live: {m['teams']['home']['name']} {m['teams']['home']['score']} - {m['teams']['away']['score']} {m['teams']['away']['name']} ({m['fixture']['status']['short']})")
        elif scheduled:
            m = scheduled[0]
            print(f"    Esempio Programmata: {m['teams']['home']['name']} vs {m['teams']['away']['name']} (Status: {m['fixture']['status']['short']})")
    else:
        print(f"    [!] Nessun match trovato per oggi tramite ESPN.")

    # 3. Verifica Reality Mode Logic (Fuzzy Match)
    print("\n[3] Verifica Logica Matching (Reality Mode)...")
    # Mock di un entry in history
    mock_entry = {
        "fid": "test_123",
        "m": "Inter vs Milan",
        "date": today,
        "r_pred": "1"
    }
    
    # Mock di dati ESPN
    mock_espn = [{
        "fixture": {"id": "espn_999", "status": {"short": "FT"}},
        "teams": {
            "home": {"name": "Internazionale", "score": 2},
            "away": {"name": "AC Milan", "score": 1}
        }
    }]
    
    h_name_part = "Inter"
    a_name_part = "Milan"
    h_keys = p._get_keywords(h_name_part)
    a_keys = p._get_keywords(a_name_part)
    
    found = False
    for ef in mock_espn:
        ef_h = ef['teams']['home']['name'].lower()
        ef_a = ef['teams']['away']['name'].lower()
        
        match_h = (any(k in ef_h for k in h_keys) or h_name_part.lower() in ef_h or ef_h in h_name_part.lower())
        match_a = (any(k in ef_a for k in a_keys) or a_name_part.lower() in ef_a or ef_a in a_name_part.lower())
        
        if match_h and match_a:
            print(f"    [V] Matching riuscito: '{mock_entry['m']}' associato a '{ef['teams']['home']['name']} vs {ef['teams']['away']['name']}'")
            found = True
            break
    
    if not found:
        print("    [!] Matching fallito nel test mock.")

if __name__ == "__main__":
    test_reality_check()
