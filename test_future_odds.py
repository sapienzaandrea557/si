
import sys
import os
import time
from datetime import datetime, timedelta

# Aggiungi directory corrente al path
sys.path.append(os.getcwd())

from si import FootballPredictor, DirettaScraper, Colors

def test_future_odds():
    print(f"{Colors.CYAN}--- TEST RECUPERO QUOTE REALI FUTURE ---{Colors.ENDC}")
    FD_KEY = "39df5a49a6764a999a9b14cafc9ca111"
    API_KEY = "c5d860df8229a7ad907688ad36a7693a"
    p = FootballPredictor(API_KEY, fd_key=FD_KEY)
    scraper = DirettaScraper()
    
    # 1. Recupero match di domani (offset 1)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"\n[1] Recupero match per domani ({tomorrow})...")
    
    matches = scraper.get_matches(day_offset=1)
    
    if not matches:
        print(f"    [!] Nessun match trovato per domani tramite Diretta.it.")
        return

    print(f"    [V] Trovati {len(matches)} match per domani.")
    
    # 2. Cerchiamo match con quote per domani
    print("\n[2] Ricerca quote reali per i match di domani...")
    found_with_odds = 0
    count = 0
    
    for m in matches:
        m_id = m.get('id')
        h, a = m.get('home'), m.get('away')
        
        # Filtriamo per match che hanno il flag odds o proviamo i primi 20
        if m.get('has_odds') or count < 20:
            print(f"    Controllo quote: {h} vs {a} (ID: {m_id})...", end=" ", flush=True)
            odds = scraper.get_odds(m_id)
            
            if odds:
                print(f"{Colors.GREEN}TROVATE!{Colors.ENDC} 1:{odds.get('1')} | X:{odds.get('X')} | 2:{odds.get('2')}")
                found_with_odds += 1
                if found_with_odds >= 5: break
            else:
                print(f"{Colors.GRAY}N/D{Colors.ENDC}")
            
            count += 1
            # Un piccolo delay per non essere bloccati durante il test
            time.sleep(0.5)

    if found_with_odds == 0:
        print(f"\n{Colors.YELLOW}[!] Nessuna quota reale trovata per domani. Potrebbe essere troppo presto o i feed sono diversi.{Colors.ENDC}")
    else:
        print(f"\n{Colors.GREEN}[V] Successo! Il sistema vede le quote REALI per i match futuri.{Colors.ENDC}")

    # 3. Verifica match dopodomani (offset 2)
    after_tomorrow = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
    print(f"\n[3] Verifica disponibilità match per dopodomani ({after_tomorrow})...")
    matches_at = scraper.get_matches(day_offset=2)
    if matches_at:
        print(f"    [V] Trovati {len(matches_at)} match anche per dopodomani.")
    else:
        print(f"    [!] Nessun match ancora caricato per dopodomani.")

if __name__ == "__main__":
    test_future_odds()
