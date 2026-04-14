
import sys
import os
import time

# Aggiungi la directory corrente al path per importare si
sys.path.append(os.getcwd())

from si import DirettaScraper, FootballPredictor

def test_diretta_odds():
    scraper = DirettaScraper()
    print("--- Test DirettaScraper ---")
    
    # 1. Recupera i match di oggi
    print("Recupero match di oggi...")
    matches = scraper.get_matches(day_offset=0)
    
    if not matches:
        print("Nessun match trovato oggi.")
        return

    print(f"Trovati {len(matches)} match.")
    
    # 2. Prendi i primi 10 match e prova a recuperare le quote
    count = 0
    for m in matches:
        m_id = m.get('id')
        h_team = m.get('home_team')
        a_team = m.get('away_team')
        
        if m_id:
            print(f"\nRecupero quote per: {h_team} vs {a_team} (ID: {m_id})")
            odds = scraper.get_odds(m_id)
            if odds:
                print(f"  Quote 1X2: 1:{odds.get('1')} | X:{odds.get('X')} | 2:{odds.get('2')}")
                count += 1
            else:
                print(f"  Quote non trovate per questo match.")
        
        if count >= 5:
            break

def test_brain_odds_fallback():
    print("\n--- Test FootballPredictor Odds Fallback ---")
    brain = FootballPredictor()
    
    # Cerchiamo un match reale per oggi tramite lo scraper
    scraper = DirettaScraper()
    matches = scraper.get_matches(day_offset=0)
    
    if not matches:
        print("Nessun match trovato oggi per testare il fallback.")
        return
        
    m = matches[0]
    h_name = m['home_team']
    a_name = m['away_team']
    date_str = m['date'] # "2026-04-13"
    
    print(f"Test fallback per: {h_name} vs {a_name} ({date_str})")
    
    # Chiamiamo get_odds con un fid fittizio per forzare il fallback
    # get_odds(self, fid, h_name=None, a_name=None, date_str=None)
    odds = brain.get_odds("dummy_id", h_name=h_name, a_name=a_name, date_str=date_str)
    
    if odds and odds.get('1X2'):
        print(f"Successo! Quote recuperate tramite fallback: {odds['1X2']}")
    else:
        print("Fallback fallito o quote non disponibili.")

if __name__ == "__main__":
    test_diretta_odds()
    test_brain_odds_fallback()
