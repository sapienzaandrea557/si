
import sys
import os
import time

# Add current directory to path
sys.path.append(os.getcwd())

from si import FootballPredictor, DirettaScraper

def verify_system():
    print("--- SMART BRAIN AI: VERIFICA FUNZIONAMENTO ---")
    FD_KEY = "39df5a49a6764a999a9b14cafc9ca111"
    API_KEY = "c5d860df8229a7ad907688ad36a7693a"
    brain = FootballPredictor(API_KEY, fd_key=FD_KEY)
    scraper = DirettaScraper()
    
    # 1. Verifica recupero match da Diretta
    print("\n[1] Verifica Recupero Match (Diretta.it)...")
    matches = scraper.get_matches(day_offset=0)
    if not matches:
        print("    [!] ERRORE: Nessun match recuperato da Diretta.it.")
        return
    print(f"    [V] Successo: {len(matches)} match trovati.")
    
    # 2. Verifica recupero quote per un match reale
    print("\n[2] Verifica Recupero Quote Reali...")
    # Cerchiamo un match con quote
    target_match = None
    for m in matches:
        if m.get('has_odds'):
            target_match = m
            break
            
    if not target_match:
        print("    [!] Nessun match con flag 'has_odds' trovato. Provo il primo della lista.")
        target_match = matches[0]
        
    m_id = target_match['id']
    h_team = target_match['home']
    a_team = target_match['away']
    print(f"    Target: {h_team} vs {a_team} (ID: {m_id})")
    
    odds = brain.get_odds(f"d_{m_id}") # Prefisso d_ forza l'uso di DirettaScraper
    
    if odds and odds.get('1X2') and odds['1X2'].get('Home'):
        o = odds['1X2']
        print(f"    [V] Quote 1X2 Recuperate: 1:{o['Home']} | X:{o['Draw']} | 2:{o['Away']}")
    else:
        # Fallback manuale se il prefisso non ha funzionato
        print("    [!] Prefisso d_ non ha prodotto quote. Provo fallback manuale...")
        d_odds = scraper.get_odds(m_id)
        if d_odds:
            print(f"    [V] Quote Diretta (Manuale): 1:{d_odds.get('1')} | X:{d_odds.get('X')} | 2:{d_odds.get('2')}")
        else:
            print("    [!] ERRORE: Impossibile recuperare quote per questo match.")
            
    # 3. Verifica Analisi e Calcolo EV/Kelly
    print("\n[3] Verifica Analisi Brain (EV & Kelly)...")
    # Mock data per un'analisi veloce
    try:
        # Tenta di analizzare il match target se abbiamo le quote
        if odds and odds.get('1X2') and odds['1X2'].get('Home'):
            print(f"    Analisi match reale: {h_team} vs {a_team}")
            # get_prediction(self, match_data, real_odds=None)
            pred = brain.get_prediction(target_match, real_odds=odds)
            if pred:
                print(f"    [V] Predizione Generata: {pred['best_pick']['r']} @{pred['best_pick']['q']}")
                print(f"    [V] EV: {pred['best_pick'].get('ev', 0)*100:.2f}% | Stake Kelly: {pred['best_pick'].get('stake', 0):.2f}%")
            else:
                print("    [!] Predizione non generata (dati insufficienti per questo match).")
    except Exception as e:
        print(f"    [!] Errore durante l'analisi: {e}")

if __name__ == "__main__":
    verify_system()
