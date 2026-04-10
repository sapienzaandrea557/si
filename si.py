import requests
import json
import os
import sys
import time
import re
import math
import random
import zlib
from datetime import datetime, timedelta, timezone
import difflib
import threading
# Abilita i colori ANSI su Windows
if sys.platform == "win32":
    os.system('color')
# Blocco globale per operazioni su file (Cache, History, Weights)
file_lock = threading.Lock()
# Colori ANSI
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
class DirettaScraper:
    """Scraper per recuperare match e quote da Diretta.it (Flashscore)"""
    def __init__(self):
        self.headers = {
            'x-fsign': 'SW9D1eZo',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.diretta.it/'
        }
        self.base_url = "https://www.diretta.it/x/feed"
        self.SEP1 = '÷' 
        self.SEP2 = '¬' 
        self._last_fsign_update = 0

    def _refresh_fsign(self):
        """Tenta di recuperare un x-fsign fresco dalla homepage di Diretta.it"""
        if time.time() - self._last_fsign_update < 3600: return # Max 1 volta all'ora
        try:
            r = requests.get("https://www.diretta.it/", headers={'User-Agent': self.headers['User-Agent']}, timeout=10)
            # Cerchiamo fsign = "..."
            match = re.search(r'fsign\s*=\s*"([^"]+)"', r.text)
            if match:
                self.headers['x-fsign'] = match.group(1)
                self._last_fsign_update = time.time()
        except:
            pass

    def get_matches(self, day_offset=0):
        """
        day_offset: 0 per oggi, 1 per domani, -1 per ieri
        """
        self._refresh_fsign()
        suffix = "2" if day_offset == 0 else ("3" if day_offset == 1 else "1")
        url = f"{self.base_url}/f_1_{day_offset}_{suffix}_it_1"
        for attempt in range(3):
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    matches = []
                    sections = response.text.split('~')
                    current_league = ""
                    for section in sections:
                        if section.startswith('ZA' + self.SEP1):
                            parts = section.split(self.SEP2)
                            for p in parts:
                                if p.startswith('ZA' + self.SEP1): current_league = p[3:]
                        elif section.startswith('AA' + self.SEP1):
                            parts = section.split(self.SEP2)
                            m = {"league": current_league, "source": "Diretta.it"}
                            for p in parts:
                                if p.startswith('AA' + self.SEP1): m["id"] = p[3:]
                                if p.startswith('AE' + self.SEP1): m["home"] = p[3:]
                                if p.startswith('AF' + self.SEP1): m["away"] = p[3:]
                                if p.startswith('AD' + self.SEP1): m["time"] = int(p[3:])
                                if p.startswith('AN' + self.SEP1): m["has_odds"] = p[3:] == 'y'
                            if "id" in m and "home" in m and "away" in m:
                                matches.append(m)
                    return matches
                if response.status_code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                break
            except:
                time.sleep(1)
                continue
        return []
    def find_match_by_name(self, team_name, day_offset=0):
        """Cerca un match specifico per nome squadra in un dato giorno"""
        try:
            matches = self.get_matches(day_offset)
            q = team_name.lower()
            found = []
            for m in matches:
                h, a = m['home'].lower(), m['away'].lower()
                ratio_h = difflib.SequenceMatcher(None, q, h).ratio()
                ratio_a = difflib.SequenceMatcher(None, q, a).ratio()
                if q in h or q in a or ratio_h > 0.7 or ratio_a > 0.7:
                    found.append(m)
            return found
        except:
            return []
    def get_odds(self, match_id):
        """Tenta di recuperare le quote per un match ID da Diretta.it (Multi-Feed)"""
        # Formati feed diversi per quote (it_1, it_2, it_3, etc.)
        urls = [
            f"{self.base_url}/f_od_1_{match_id}_it_1",
            f"{self.base_url}/f_od_2_{match_id}_it_1",
            f"{self.base_url}/f_od_1_{match_id}_it_2",
            f"{self.base_url}/f_od_1_{match_id}_en_1"
        ]
        for url in urls:
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code != 200 or not response.text: continue
                sections = response.text.split('~')
                for section in sections:
                    if section.startswith('OD' + self.SEP1):
                        parts = section.split(self.SEP2)
                        o1, ox, o2 = 0.0, 0.0, 0.0
                        for p in parts:
                            if p.startswith('OA' + self.SEP1): o1 = float(p[3:])
                            if p.startswith('OB' + self.SEP1): ox = float(p[3:])
                            if p.startswith('OC' + self.SEP1): o2 = float(p[3:])
                        if o1 > 0 and ox > 0 and o2 > 0:
                            return {"1": o1, "X": ox, "2": o2}
            except: continue
        return None
    def get_match_info_extra(self, match_id):
        """Recupera info extra: arbitro, stadio, meteo da Diretta.it"""
        url = f"{self.base_url}/df_mi_1_{match_id}_it_1"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200: return None
            info = {"referee": "N/D", "venue": "N/D", "weather": "N/D"}
            # Parsing semplice basato su parole chiave nel feed
            text = response.text.lower()
            # Esempio di estrazione (molto dipendente dal formato feed)
            if "arbitro:" in text:
                info["referee"] = text.split("arbitro:")[1].split("~")[0].strip().title()
            if "stadio:" in text:
                info["venue"] = text.split("stadio:")[1].split("~")[0].strip().title()
            if "meteo:" in text:
                info["weather"] = text.split("meteo:")[1].split("~")[0].strip()
            return info
        except Exception as e:
            return None
    def get_match_stats(self, match_id):
        """Recupera statistiche avanzate (xG, corner, tiri) da Diretta.it"""
        url = f"{self.base_url}/df_st_1_{match_id}_it_1"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200: return None
            stats = {
                "home": {"xg": 0, "corners": 0, "shots": 0, "fouls": 0, "cards": 0},
                "away": {"xg": 0, "corners": 0, "shots": 0, "fouls": 0, "cards": 0}
            }
            sections = response.text.split('~')
            # Cerchiamo solo la sezione "Partita" (totale)
            is_total = False
            for section in sections:
                if section.startswith('SE' + self.SEP1 + 'Partita'):
                    is_total = True
                elif section.startswith('SE' + self.SEP1) and is_total:
                    # Abbiamo finito la sezione totale
                    break
                if section.startswith('SD' + self.SEP1):
                    parts = section.split(self.SEP2)
                    label = ""
                    h_val, a_val = 0, 0
                    for p in parts:
                        if p.startswith('SG' + self.SEP1): label = p[3:].lower()
                        if p.startswith('SH' + self.SEP1): h_val = p[3:]
                        if p.startswith('SI' + self.SEP1): a_val = p[3:]
                    # Mapping più preciso
                    try:
                        if label == "goal previsti (xg)":
                            stats["home"]["xg"] = float(h_val)
                            stats["away"]["xg"] = float(a_val)
                        elif "angolo" in label:
                            stats["home"]["corners"] = int(h_val)
                            stats["away"]["corners"] = int(a_val)
                        elif "tiri totali" in label:
                            stats["home"]["shots"] = int(h_val)
                            stats["away"]["shots"] = int(a_val)
                        elif "falli" in label:
                            stats["home"]["fouls"] = int(h_val)
                            stats["away"]["fouls"] = int(a_val)
                        elif "gialli" in label:
                            stats["home"]["cards"] = int(h_val)
                            stats["away"]["cards"] = int(a_val)
                    except (ValueError, TypeError):
                        continue
            return stats
        except Exception as e:
            return None
    def find_match_id(self, h_name, a_name, date_str):
        """Cerca l'ID di un match su Diretta.it per data e squadre (Fuzzy Match)"""
        try:
            # Pulizia nomi avanzata
            def clean(n):
                return n.lower().replace("as ", "").replace("ac ", "").replace("fc ", "").replace("real ", "").replace("atletico ", "").replace("united ", "").replace("city ", "").strip()
            h_n, a_n = clean(h_name), clean(a_name)
            match_dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            today = datetime.now().date()
            diff = (match_dt.date() - today).days
            if abs(diff) > 7: return None
            d_matches = self.get_matches(diff)
            best_id = None
            max_score = 0
            for dm in d_matches:
                dm_h, dm_a = clean(dm['home']), clean(dm['away'])
                h_score = difflib.SequenceMatcher(None, h_n, dm_h).ratio()
                a_score = difflib.SequenceMatcher(None, a_n, dm_a).ratio()
                total_score = (h_score + a_score) / 2
                if total_score > 0.8:
                    if total_score > max_score:
                        max_score = total_score
                        best_id = dm['id']
                elif (h_n in dm_h or dm_h in h_n) and (a_n in dm_a or dm_a in a_n):
                    return dm['id']
            return best_id
        except:
            return None
class FootballPredictor:
    def __init__(self, api_key, fd_key=None):
        self.api_key = api_key
        self.fd_key = fd_key
        self.base_url = "https://v3.football.api-sports.io"
        self.fd_url = "https://api.football-data.org/v4"
        self.headers = {"x-apisports-key": self.api_key}
        self.fd_headers = {"X-Auth-Token": self.fd_key} if self.fd_key else {}
        self.leagues = {
            "serie_a": 135, "champions_league": 2, "europa_league": 3, "conference_league": 848,
            "premier": 39, "la_liga": 140, "bundesliga": 78, "ligue_1": 61
        }
        self.cache_file = "api_cache.json"
        self.weights_file = "weights.json"
        self._cache_dirty_count = 0
        self._cache_last_save = 0.0
        self._bankroll_cache = {}
        self._history_cache = None # In-memory cache per history.json
        self._history_last_read = 0.0
        self.cache = self._load_cache()
        self.weights = self._load_weights()
        self.favorites_file = "favorites.json"
        self.favorites = self._load_favorites()
        self.csv_cache = {} 
        self.session_preds = []
        self.session_top_preds = []
        self.session_logged = set()
        self.is_learning = False
        self._learning_scheduler_started = False
        self.api_suspended = False # Flag per sospensione sessione
        self.diretta = DirettaScraper()
        self.diretta_league_map = {
            135: ["serie a", "italia"],
            136: ["serie b", "italia"],
            2: ["champions league", "europa"],
            3: ["europa league", "europa"],
            848: ["conference league", "europa"],
            39: ["premier league", "inghilterra"],
            140: ["liga", "spagna"],
            78: ["bundesliga", "germania"],
            61: ["ligue 1", "francia"]
        }
        self.fd_league_map = {
            135: "SA", # Serie A
            39: "PL",  # Premier League
            140: "PD", # La Liga
            78: "BL1", # Bundesliga
            61: "FL1", # Ligue 1
            2: "CL",   # Champions League
            94: "PPL", # Liga Portugal
            137: "EL"  # Europa League (if available in FD.org)
        }
        self.team_aliases = {
            "roma": {"id": 497, "name": "AS Roma", "league": 135},
            "pisa": {"id": 506, "name": "Pisa", "league": 136},
            "milan": {"id": 489, "name": "AC Milan", "league": 135},
            "inter": {"id": 505, "name": "Inter", "league": 135},
            "juve": {"id": 496, "name": "Juventus", "league": 135},
            "lazio": {"id": 487, "name": "Lazio", "league": 135},
            "napoli": {"id": 492, "name": "Napoli", "league": 135},
            "atalanta": {"id": 499, "name": "Atalanta", "league": 135},
            "fiorentina": {"id": 502, "name": "Fiorentina", "league": 135},
            "bayern": {"id": 157, "name": "Bayern Munich", "league": 78},
            "real madrid": {"id": 541, "name": "Real Madrid", "league": 140},
            "barcelona": {"id": 529, "name": "Barcelona", "league": 140},
            "barcellona": {"id": 529, "name": "Barcelona", "league": 140},
            "atletico madrid": {"id": 530, "name": "Atletico Madrid", "league": 140},
            "atl. madrid": {"id": 530, "name": "Atletico Madrid", "league": 140},
            "atlético madrid": {"id": 530, "name": "Atletico Madrid", "league": 140},
            "arsenal": {"id": 42, "name": "Arsenal", "league": 39},
            "man city": {"id": 50, "name": "Manchester City", "league": 39},
            "liverpool": {"id": 40, "name": "Liverpool", "league": 39},
            "psg": {"id": 85, "name": "Paris Saint Germain", "league": 61},
            "paris sg": {"id": 85, "name": "Paris Saint Germain", "league": 61},
            "paris saint-germain": {"id": 85, "name": "Paris Saint Germain", "league": 61},
            "paris saint germain": {"id": 85, "name": "Paris Saint Germain", "league": 61},
            "dortmund": {"id": 165, "name": "Borussia Dortmund", "league": 78},
            "benfica": {"id": 211, "name": "Benfica", "league": 94},
            "sporting": {"id": 228, "name": "Sporting CP", "league": 94}
        }
    def _safe_read_json(self, file_path):
        """Lettura sicura di file JSON con blocco globale e caching per history.json"""
        # Se è history.json, usiamo la cache in memoria se è stata letta negli ultimi 30 secondi
        if "history.json" in file_path:
            now = time.time()
            if self._history_cache is not None and (now - self._history_last_read) < 30:
                return self._history_cache

        with file_lock:
            if not os.path.exists(file_path): return None
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "history.json" in file_path:
                        self._history_cache = data
                        self._history_last_read = time.time()
                    return data
            except Exception as e:
                self._log_error(f"Errore lettura {file_path}: {e}")
                return None

    def _safe_write_json(self, file_path, data):
        """Scrittura sicura e ATOMICA di file JSON per evitare corruzioni in caso di chiusura improvvisa"""
        with file_lock:
            try:
                # Se è history.json, aggiorniamo la cache in memoria
                if "history.json" in file_path:
                    self._history_cache = data
                    self._history_last_read = time.time()
                
                # Scriviamo prima su un file temporaneo (.tmp)
                temp_path = file_path + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                
                # Sostituiamo il file originale con quello temporaneo (operazione atomica nel file system)
                if os.path.exists(file_path):
                    os.replace(temp_path, file_path)
                else:
                    os.rename(temp_path, file_path)
                    
                return True
            except Exception as e:
                self._log_error(f"Errore scrittura {file_path}: {e}")
                # Pulizia file temporaneo se fallisce
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
    def _load_weights(self):
        default_weights = {
            "w_forma": 0.35, "w_class": 0.15, "w_h2h": 0.10, "w_cont": 0.40,
            "w_uo": 0.50, # Peso specifico per Under/Over
            "w_gg": 0.50, # Peso specifico per Goal/NoGoal
            "learning_rate": 0.01, "total_analyzed": 0, "correct_predictions": 0
        }
        data = self._safe_read_json(self.weights_file)
        return data if data else default_weights
    def _save_weights(self):
        self._safe_write_json(self.weights_file, self.weights)

    def _load_favorites(self):
        default_favs = ["serie_a", "premier", "la_liga", "bundesliga", "champions_league"]
        data = self._safe_read_json(self.favorites_file)
        return data if data else default_favs

    def _save_favorites(self):
        self._safe_write_json(self.favorites_file, self.favorites)
    def _load_cache(self):
        cache = self._safe_read_json(self.cache_file)
        if cache:
            # Pulizia automatica: rimuovi voci corrotte o senza response
            cleaned = {k: v for k, v in cache.items() if isinstance(v, dict) and v.get('response') is not None}
            if len(cleaned) < len(cache):
                self.cache = cleaned
                self._save_cache(force=True)
            return cleaned
        return {}
    def _save_cache(self, force=False):
        self._cache_dirty_count += 1
        now = time.time()
        if not force:
            if self._cache_dirty_count < 25 and (now - self._cache_last_save) < 5:
                return
        if self._safe_write_json(self.cache_file, self.cache):
            self._cache_dirty_count = 0
            self._cache_last_save = now
    def clean_cache(self, days=30):
        """Rimuove voci vecchie dalla cache per evitare che il file diventi troppo grande"""
        now = time.time()
        expiry_sec = days * 24 * 3600
        initial_count = len(self.cache)
        # Le quote scadono dopo 7 giorni, il resto dopo 30
        self.cache = {
            k: v for k, v in self.cache.items() 
            if isinstance(v, dict) and (now - v.get('ts', 0) < (7*24*3600 if 'odds' in k else expiry_sec))
        }
        if len(self.cache) < initial_count:
            print(f"Cache pulita: rimosse {initial_count - len(self.cache)} voci obsolete.")
            self._save_cache(force=True)
    def _log_error(self, message):
        """Logga gli errori su un file dedicato"""
        try:
            with open("errors.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except:
            pass

    def auto_git_sync(self, message="Update AI knowledge and history", pull=False):
        """Sincronizza automaticamente i file JSON su GitHub (Push e opzionalmente Pull)"""
        if not os.path.exists(".git"): return
        
        def _sync_task():
            try:
                import subprocess
                # 1. Se richiesto, facciamo prima il pull per evitare conflitti
                if pull:
                    print(f"\n{Colors.BLUE}[GIT] Sincronizzazione con il cloud (Pull)...{Colors.ENDC}", end=" ")
                    subprocess.run(["git", "pull", "origin", "main"], capture_output=True)
                    print(f"{Colors.GREEN}Fatto.{Colors.ENDC}")

                # 2. Aggiunge solo i file di dati necessari
                subprocess.run(["git", "add", "weights.json", "history.json"], capture_output=True)
                # 3. Commit
                subprocess.run(["git", "commit", "-m", f"{message} [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"], capture_output=True)
                # 4. Push
                res = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
                if res.returncode == 0:
                    print(f"\n{Colors.GREEN}[GIT] GitHub aggiornato con successo!{Colors.ENDC}")
            except:
                pass
        
        # Se è un pull (all'avvio), lo facciamo bloccare per avere i dati aggiornati subito
        if pull:
            _sync_task()
        else:
            threading.Thread(target=_sync_task, daemon=True).start()

    def _get(self, endpoint, params=None, use_cache=True):
        if self.api_suspended and endpoint != "status": return None
        cache_key = f"{endpoint}_{json.dumps(params, sort_keys=True)}"
        if use_cache and cache_key in self.cache:
            res = self.cache[cache_key]
            if isinstance(res, dict) and res.get('response'):
                return res
        max_retries = 3 
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params, timeout=10)
                if response.status_code == 429:
                    wait_time = 60 * (attempt + 1)
                    msg = f"Limite API (429). Attesa {wait_time}s... ({attempt+1}/{max_retries})"
                    print(f"\n[!] {msg}")
                    self._log_error(f"429: {endpoint} - {msg}")
                    time.sleep(wait_time)
                    continue
                if response.status_code != 200:
                    msg = f"Errore HTTP {response.status_code} su {endpoint}"
                    print(f"\n[!] {msg}")
                    self._log_error(msg)
                    return None
                try:
                    data = response.json()
                except Exception:
                    msg = f"Errore nel parsing JSON della risposta da {endpoint}"
                    print(f"\n[!] {msg}")
                    self._log_error(msg)
                    return None
                errors = data.get('errors', {})
                if errors:
                    err_msg = str(errors).lower()
                    self._log_error(f"API Body Error ({endpoint}): {err_msg}")
                    # Gestione sospensione, errori chiave o accesso negato
                    if any(x in err_msg for x in ['suspended', 'access', 'token', 'application key', 'invalid key']):
                        self.api_suspended = True
                        if endpoint != "status": # Non ripetere il messaggio se stiamo solo verificando lo stato
                            print(f"\n{Colors.YELLOW}[!] API-Sports Non Disponibile ({errors.get('token', 'Access Denied')}). Uso fallback.{Colors.ENDC}")
                        return None
                    if 'plan' in err_msg or 'date' in err_msg:
                        return None
                    if 'requests' in err_msg or 'limit' in err_msg or 'rate' in err_msg:
                        wait_time = 60 * (attempt + 1)
                        print(f"\n[!] Limite raggiunto ({err_msg}). Attesa {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"\n[!] API Error: {errors}")
                        return None
                if use_cache and data and data.get('response'): 
                    data['ts'] = time.time()
                    self.cache[cache_key] = data
                    self._save_cache()
                return data
            except Exception as e:
                msg = f"Eccezione durante richiesta API ({endpoint}): {e}"
                print(f"\n[!] {msg}")
                self._log_error(msg)
                time.sleep(5)
                continue
        return None
    def _get_fd(self, endpoint, params=None, use_cache=True):
        """
        Richiesta API a football-data.org con gestione rate-limiting (throttling)
        come suggerito dalla documentazione ufficiale.
        """
        if not self.fd_key: return None
        cache_key = f"fd_{endpoint}_{json.dumps(params, sort_keys=True)}"
        if use_cache and cache_key in self.cache:
            return self.cache[cache_key]
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                url = f"{self.fd_url}/{endpoint}"
                response = requests.get(url, headers=self.fd_headers, params=params, timeout=20)
                # Esaminiamo gli headers per il throttling automatico
                # X-Requests-Remaining: richieste rimaste nel minuto corrente
                # X-RequestCounter-Reset: secondi alla fine della finestra di rate limit
                remaining = int(response.headers.get('X-Requests-Remaining', 10))
                reset_seconds = int(response.headers.get('X-RequestCounter-Reset', 60))
                if response.status_code == 429:
                    wait_time = reset_seconds + 1
                    print(f"\n[!] Rate Limit Football-Data (429). Attesa {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                # Se mancano pochissime richieste, rallentiamo preventivamente
                if remaining < 2:
                    time.sleep(1)
                if response.status_code == 200:
                    data = response.json()
                    if use_cache and data:
                        data['ts'] = time.time()
                        self.cache[cache_key] = data
                        self._save_cache()
                    return data
                elif response.status_code == 403:
                    # Inutile loggare il 403, è un limite del piano gratuito di Football-Data
                    return None
                else:
                    print(f"\n[!] Errore Football-Data {response.status_code}: {response.text[:100]}")
                    return None
            except Exception as e:
                print(f"\n[!] Eccezione Football-Data: {e}")
                time.sleep(2)
                continue
        return None
    def get_standings(self, league_id, season, league_name=""):
        # Forza stagione 2025 per match futuri se siamo nel 2026 (ciclo europeo 2025-26)
        if season == 2026: season = 2025
        # Se league_id è None, proviamo a mapparlo dal nome (fondamentale per match ESPN)
        if not league_id and league_name:
            ln = league_name.lower()
            if "serie a" in ln: league_id = 135
            elif "premier" in ln: league_id = 39
            elif "la liga" in ln: league_id = 140
            elif "bundesliga" in ln: league_id = 78
            elif "ligue 1" in ln: league_id = 61
            elif "champions" in ln: league_id = 2
            elif "europa" in ln: league_id = 3
            elif "conference" in ln: league_id = 848 # Conference League ID
        # 1. Fallback Prioritario su ESPN per stagione 2025 (API-Sports spesso fallisce qui)
        espn_map = {
            135: "ita.1", 39: "eng.1", 140: "esp.1", 78: "ger.1", 61: "fra.1", 
            2: "uefa.champions", 3: "uefa.europa", 848: "uefa.conf",
            71: "bra.1", 72: "bra.2", 128: "arg.1", 265: "chi.1", 242: "ecu.1",
            262: "mex.1", 239: "col.1", 144: "bel.1", 94: "por.1", 88: "ned.1",
            203: "tur.1", 235: "rus.1"
        }
        if league_id in espn_map:
            res = self.get_espn_standings(espn_map[league_id])
            if res: 
                # Se abbiamo trovato la classifica su ESPN, la usiamo
                return res
        # 2. API-Sports (Solo se ESPN fallisce)
        data = self._get("standings", {"league": league_id, "season": season}) if league_id else None
        # 3. Fallback su Football-Data.org (SA, PL, PD, etc.)
        if (not data or not data.get('response')) and league_id:
            fd_map = {135: "SA", 39: "PL", 140: "PD", 78: "BL1", 61: "FL1", 2: "CL", 3: "EL"}
            if league_id in fd_map:
                fd_data = self._get_fd(f"competitions/{fd_map[league_id]}/standings")
                if fd_data and 'standings' in fd_data:
                    standings = []
                    for s_type in fd_data['standings']:
                        if s_type['type'] == 'TOTAL':
                            for entry in s_type['table']:
                                standings.append({
                                    "rank": entry['position'],
                                    "team": {"id": f"fd_{entry['team']['id']}", "name": entry['team']['name']},
                                    "points": entry['points'],
                                    "all": {"played": entry['playedGames'], "win": entry['won'], "draw": entry['draw'], "lose": entry['lost']}
                                })
                            if standings: return standings
        if data and data.get('response'):
            try:
                s = data['response'][0]['league']['standings']
                return [i for sub in s for i in sub] if isinstance(s[0], list) else s
            except: pass
        return []
    def get_espn_standings(self, league_code):
        """
        Recupera la classifica direttamente da ESPN
        """
        # Usiamo l'endpoint v2 web che è più completo
        url = f"https://site.web.api.espn.com/apis/v2/sports/soccer/{league_code}/standings"
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                standings = []
                # Struttura ESPN: children[0].standings.entries
                entries = []
                if 'children' in data and data['children']:
                    entries = data['children'][0].get('standings', {}).get('entries', [])
                elif 'standings' in data:
                    entries = data['standings'].get('entries', [])
                for item in entries:
                    team = item['team']
                    stats_list = item.get('stats', [])
                    # Gestione robusta: check 'name' e 'value' in ogni stat
                    stats = {s['name']: s.get('value', 0) for s in stats_list if 'name' in s}
                    standings.append({
                        "rank": int(stats.get('rank', 0) or 0),
                        "team": {"id": f"espn_{team['id']}", "name": team['displayName']},
                        "points": int(stats.get('points', 0) or 0),
                        "all": {
                            "played": int(stats.get('gamesPlayed', 0) or 0),
                            "win": int(stats.get('wins', 0) or 0),
                            "draw": int(stats.get('ties', 0) or 0),
                            "lose": int(stats.get('losses', 0) or 0)
                        }
                    })
                return standings
        except Exception as e:
            print(f"Errore fallback ESPN Standings: {e}")
        return []
    def get_fixtures_by_date(self, date_str, top_only=True):
        """
        Recupera i match per una data unificando tutte le fonti FREE.
        """
        top_ids = [135, 39, 140, 78, 61, 2, 3, 848] 
        fixtures = self.get_free_fixtures(date_str)
        if top_only:
            fixtures = [f for f in fixtures if f['league']['id'] in top_ids]
        return fixtures
    def search_team(self, query):
        """Ricerca avanzata per una squadra su più fonti"""
        q = query.lower().strip()
        # 1. Alias locali (istantaneo)
        if q in self.team_aliases:
            return self.team_aliases[q]
        for alias, data in self.team_aliases.items():
            if q in alias or alias in q or difflib.SequenceMatcher(None, q, alias).ratio() > 0.8:
                return data
        # 2. Ricerca su API-Sports (se non sospeso)
        if not self.api_suspended:
            print(f"Ricerca '{query}' su API-Sports...")
            resp = self._get("teams", {"search": query})
            if resp and resp.get('response'):
                return {"id": resp['response'][0]['team']['id'], "name": resp['response'][0]['team']['name']}
        # 2b. Ricerca su Football-Data.org (se API-Sports è sospeso o fallisce)
        if self.fd_key:
            print(f"Ricerca '{query}' su Football-Data.org...")
            # Football-Data non ha un endpoint di ricerca globale per team facilmente accessibile come API-Sports
            # ma possiamo cercare nelle competizioni principali
            for code in ["SA", "PL", "PD", "BL1", "FL1", "CL"]:
                data = self._get_fd(f"competitions/{code}/teams")
                if data and 'teams' in data:
                    for t in data['teams']:
                        if q in t['name'].lower() or q in t['shortName'].lower():
                            return {"id": f"fd_{t['id']}", "name": t['name']}
        # 3. Ricerca su Diretta.it (Se abbiamo i match caricati)
        print(f"Ricerca '{query}' su Diretta.it...")
        today_m = self.diretta.get_matches(0)
        for m in today_m:
            h_ratio = difflib.SequenceMatcher(None, q, m['home'].lower()).ratio()
            a_ratio = difflib.SequenceMatcher(None, q, m['away'].lower()).ratio()
            if h_ratio > 0.8 or a_ratio > 0.8 or q in m['home'].lower() or q in m['away'].lower():
                fake_f = {
                    "teams": {"home": {"name": m['home']}, "away": {"name": m['away']}},
                    "league": {"name": m['league']},
                    "fixture": {"id": None, "date": datetime.now().isoformat(), "status": "NS"}
                }
                api_match = self.find_api_sports_fixture(fake_f)
                if api_match:
                    h_name = api_match['teams']['home']['name']
                    a_name = api_match['teams']['away']['name']
                    if q in h_name.lower() or difflib.SequenceMatcher(None, q, h_name.lower()).ratio() > 0.8:
                        return {"id": api_match['teams']['home']['id'], "name": h_name}
                    return {"id": api_match['teams']['away']['id'], "name": a_name}
        # 4. Ricerca su CSV Locali (Ultima spiaggia per team storici)
        print(f"Ricerca '{query}' nei dati storici CSV...")
        for f in os.listdir("."):
            if f.endswith(".csv"):
                data = self._get_csv(f.replace(".csv", ""))
                if data:
                    for m in data['response']:
                        h_n = m['teams']['home']['name'].lower()
                        a_n = m['teams']['away']['name'].lower()
                        if q in h_n or difflib.SequenceMatcher(None, q, h_n).ratio() > 0.8: 
                            return {"id": f"csv_{m['teams']['home']['name']}", "name": m['teams']['home']['name']}
                        if q in a_n or difflib.SequenceMatcher(None, q, a_n).ratio() > 0.8: 
                            return {"id": f"csv_{m['teams']['away']['name']}", "name": m['teams']['away']['name']}
        # 5. Fallback estremo: Google Search per trovare il match di venerdì
        print(f"Ricerca Web per '{query}'...")
        # Simulo una ricerca web o controllo se il match è noto per questa data specifica
        # In un ambiente reale qui chiamerei un tool di ricerca
        return None
    def find_match_anywhere(self, query):
        """
        Motore di ricerca UNIVERSALE per un match.
        Cerca ovunque: API-Sports (Cache), Diretta.it (7gg), ESPN, Football-Data, CSV.
        """
        q = query.lower().strip()
        parts = [p.strip() for p in q.split() if p.strip()]
        if len(parts) < 2: return []
        found = []
        seen_ids = set()
        exclude_keywords = ["u20", "u19", "u18", "donne", "women", "femminile", "primavera"]
        def is_relevant(h_n, a_n, query_parts):
            h_n, a_n = h_n.lower(), a_n.lower()
            # Escludiamo giovanili/femminili a meno che non siano nella query
            q_lower = " ".join(query_parts)
            is_youth_query = any(k in q_lower for k in ["u20", "u19", "u18", "primavera"])
            if not is_youth_query:
                if any(k in h_n or k in a_n for k in exclude_keywords): return False
            # Controllo matching rigoroso
            match_score = 0
            for p in query_parts:
                # Per evitare "Roma" in "Romanija", controlliamo i confini di parola
                if re.search(rf'\b{re.escape(p)}\b', h_n) or re.search(rf'\b{re.escape(p)}\b', a_n):
                    match_score += 1
            return match_score >= 2 or (len(query_parts) == 2 and match_score >= 1 and \
                   (difflib.SequenceMatcher(None, query_parts[0], h_n).ratio() > 0.8 or \
                    difflib.SequenceMatcher(None, query_parts[1], a_n).ratio() > 0.8))
        # 1. Scansione Diretta.it (Prossimi 7 giorni)
        print(f"Scansione Diretta.it (7gg) per '{query}'...")
        for day_off in range(0, 8):
            d_matches = self.diretta.get_matches(day_off)
            for dm in d_matches:
                if is_relevant(dm['home'], dm['away'], parts):
                    fake_f = {
                        "teams": {"home": {"name": dm['home']}, "away": {"name": dm['away']}},
                        "league": {"name": dm['league']},
                        "fixture": {"id": None, "date": datetime.fromtimestamp(dm['time'], tz=timezone.utc).isoformat(), "status": "NS"}
                    }
                    api_match = self.find_api_sports_fixture(fake_f)
                    if api_match and api_match['fixture']['id'] not in seen_ids:
                        found.append(api_match)
                        seen_ids.add(api_match['fixture']['id'])
        # 2. Football-Data.org (Se attivo)
        if not found and self.fd_key:
            print(f"Ricerca su Football-Data.org...")
            # Usiamo i team_aliases per trovare gli ID se possibile
            potential_teams = []
            for p in parts:
                if p in self.team_aliases:
                    potential_teams.append(self.team_aliases[p])
            # Se non in alias, non possiamo cercare facilmente su FD free tier senza ID
            for team in potential_teams:
                # Nota: gli ID in team_aliases sono di API-Sports. 
                # FD ha ID diversi. Quindi questa parte è complessa senza un mapping.
                # Per ora, usiamo FD solo se abbiamo match SCHEDULED nelle competizioni principali
                pass
            # Alternativa: Scansione match di oggi/domani su FD per le leghe supportate
            important_fd_leagues = ["SA", "PL", "PD", "BL1", "FL1", "CL"]
            for l_code in important_fd_leagues:
                fd_matches = self._get_fd(f"competitions/{l_code}/matches", {"status": "SCHEDULED"})
                if fd_matches and fd_matches.get('matches'):
                    for m in fd_matches['matches']:
                        h_n, a_n = m['homeTeam']['name'], m['awayTeam']['name']
                        if is_relevant(h_n, a_n, parts):
                            match_obj = {
                                "fixture": {"id": f"fd_{m['id']}", "date": m['utcDate'], "status": {"short": "NS"}},
                                "league": {"name": m['competition']['name'], "id": m['competition']['id']},
                                "teams": {
                                    "home": {"name": h_n, "id": f"fd_{m['homeTeam']['id']}"},
                                    "away": {"name": a_n, "id": f"fd_{m['awayTeam']['id']}"}
                                }
                            }
                            if match_obj['fixture']['id'] not in seen_ids:
                                found.append(match_obj)
                                seen_ids.add(match_obj['fixture']['id'])
                if found: break # Trovato qualcosa, basta così per FD (risparmio rate limit)
        # 3. Scansione ESPN (Oggi, Domani, Ieri)
        if not found:
            print(f"Ricerca su ESPN...")
            for day_off in [0, 1, -1]:
                d_str = (datetime.now() + timedelta(days=day_off)).strftime('%Y-%m-%d')
                e_matches = self.get_espn_fixtures(d_str, quiet=True, top_only=False)
                for em in e_matches:
                    if is_relevant(em['teams']['home']['name'], em['teams']['away']['name'], parts):
                        api_match = self.find_api_sports_fixture(em)
                        if api_match and api_match['fixture']['id'] not in seen_ids:
                            found.append(api_match)
                            seen_ids.add(api_match['fixture']['id'])
        # 4. Scansione API-Sports (Cache data)
        if not found:
            print(f"Ricerca in Cache API...")
            for day_off in range(-1, 3):
                d_str = (datetime.now() + timedelta(days=day_off)).strftime('%Y-%m-%d')
                resp = self._get("fixtures", {"date": d_str}, use_cache=True)
                if resp and resp.get('response'):
                    for f in resp['response']:
                        if is_relevant(f['teams']['home']['name'], f['teams']['away']['name'], parts):
                            if f['fixture']['id'] not in seen_ids:
                                found.append(f)
                                seen_ids.add(f['fixture']['id'])
        # 5. Scansione CSV Locali (Match Storici)
        if not found:
            print(f"Ricerca nei file CSV storici...")
            for f_name in os.listdir("."):
                if f_name.endswith(".csv"):
                    data = self._get_csv(f_name.replace(".csv", ""))
                    if data:
                        for m in data['response']:
                            if is_relevant(m['teams']['home']['name'], m['teams']['away']['name'], parts):
                                # Convertiamo in formato compatibile
                                m['fixture']['id'] = f"csv_{m['teams']['home']['name']}_{m['fixture']['date']}"
                                if m['fixture']['id'] not in seen_ids:
                                    found.append(m)
                                    seen_ids.add(m['fixture']['id'])
        return found
    def get_free_fixtures(self, date_str, league_id=None):
        """
        Recupera match unificati usando solo fonti FREE (Diretta + ESPN + Cache).
        Ideale per quando l'API principale è sospesa.
        """
        all_matches = []
        seen_keys = set()
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        today = datetime.now().date()
        day_off = (dt.date() - today).days
        # 1. Recupero da Diretta.it (Se entro 7 giorni)
        if abs(day_off) <= 7:
            print(f"Recupero dati da Diretta.it ({date_str})...")
            d_list = self.diretta.get_matches(day_off)
            for m in d_list:
                # Se league_id è specificato, filtriamo
                if league_id:
                    keywords = self.diretta_league_map.get(league_id, [])
                    if not any(k in m['league'].lower() for k in keywords): continue
                key = f"{m['home'].lower()}-{m['away'].lower()}"
                if key not in seen_keys:
                    all_matches.append({
                        "fixture": {"id": None, "date": datetime.fromtimestamp(m['time'], tz=timezone.utc).isoformat(), "status": {"short": "NS"}},
                        "league": {"name": m['league'], "id": league_id},
                        "teams": {"home": {"name": m['home'], "id": None}, "away": {"name": m['away'], "id": None}},
                        "source": "Diretta"
                    })
                    seen_keys.add(key)
        # 2. Recupero da ESPN
        print(f"Recupero dati da ESPN ({date_str})...")
        e_list = self.get_espn_fixtures(date_str, quiet=True, top_only=False)
        for m in e_list:
            if league_id and m['league']['id'] != league_id: continue
            h_n, a_n = m['teams']['home']['name'].lower(), m['teams']['away']['name'].lower()
            # Matching fuzzy con quanto già trovato
            exists = False
            for sk in seen_keys:
                if h_n in sk and a_n in sk: exists = True; break
            if not exists:
                all_matches.append(m)
                seen_keys.add(f"{h_n}-{a_n}")
        # 3. Recupero dalla Cache API (se presente)
        cache_key = f"fixtures_{json.dumps({'date': date_str}, sort_keys=True)}"
        if cache_key in self.cache:
            print(f"Integrazione dati da Cache API...")
            c_data = self.cache[cache_key].get('response', [])
            for m in c_data:
                if league_id and m['league']['id'] != league_id: continue
                h_n, a_n = m['teams']['home']['name'].lower(), m['teams']['away']['name'].lower()
                exists = False
                for sk in seen_keys:
                    if h_n in sk and a_n in sk: exists = True; break
                if not exists:
                    all_matches.append(m)
                    seen_keys.add(f"{h_n}-{a_n}")
        return sorted(all_matches, key=lambda x: x['fixture']['date'])
    def get_upcoming_fixtures(self, league_id):
        # 1. Prova API-Sports (Cache o Chiamata se possibile)
        season = datetime.now().year if datetime.now().month > 6 else datetime.now().year - 1
        data = self._get("fixtures", {"league": league_id, "season": season}, use_cache=True)
        if not data or not data.get('response'):
            data = self._get("fixtures", {"league": league_id, "season": season - 1}, use_cache=True)
        upcoming = []
        if data and data['response']:
            upcoming = [f for f in data['response'] if f['fixture']['status']['short'] in ["NS", "TBD"]]
        # 2. Integrazione con Diretta ed ESPN per i prossimi 7 giorni
        print(f"Sincronizzazione calendari da fonti FREE...")
        today = datetime.now()
        for i in range(0, 8):
            d_str = (today + timedelta(days=i)).strftime('%Y-%m-%d')
            free_matches = self.get_free_fixtures(d_str, league_id=league_id)
            for fm in free_matches:
                # Deduplicazione
                h_fm, a_fm = fm['teams']['home']['name'].lower(), fm['teams']['away']['name'].lower()
                exists = any((h_fm in f['teams']['home']['name'].lower() or f['teams']['home']['name'].lower() in h_fm) and 
                             (a_fm in f['teams']['away']['name'].lower() or f['teams']['away']['name'].lower() in a_fm) for f in upcoming)
                if not exists: upcoming.append(fm)
        upcoming.sort(key=lambda x: x['fixture']['date'])
        return upcoming[:15]
    def get_past_fixtures(self, league_id):
        # 1. Prova API-Sports
        season = datetime.now().year if datetime.now().month > 6 else datetime.now().year - 1
        data = self._get("fixtures", {"league": league_id, "season": season, "status": "FT"}, use_cache=True)
        # Fallback su stagione precedente se la corrente è vuota (tipico inizio stagione)
        if not data or not data.get('response'):
            data = self._get("fixtures", {"league": league_id, "season": season - 1}, use_cache=True)
        past = []
        if data and data.get('response'):
            # Filtriamo i match finiti
            past = [f for f in data['response'] if f['fixture']['status']['short'] in ["FT", "AET", "PEN"]]
        # 2. Integrazione con Diretta ed ESPN per gli ultimi 7 giorni
        print(f"Sincronizzazione risultati passati da fonti FREE...")
        today = datetime.now()
        for i in range(1, 8):
            d_str = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            free_matches = self.get_free_fixtures(d_str, league_id=league_id)
            for fm in free_matches:
                # Deduplicazione
                h_fm, a_fm = fm['teams']['home']['name'].lower(), fm['teams']['away']['name'].lower()
                exists = any((h_fm in f['teams']['home']['name'].lower() or f['teams']['home']['name'].lower() in h_fm) and 
                             (a_fm in f['teams']['away']['name'].lower() or f['teams']['away']['name'].lower() in a_fm) for f in past)
                if not exists: past.append(fm)
        past.sort(key=lambda x: x['fixture']['date'], reverse=True)
        return past[:15]
    def get_h2h(self, h1, h2):
        # Il parametro 'last' non è supportato nel piano Free. Carichiamo tutto e filtriamo.
        data = self._get("fixtures/headtohead", {"h2h": f"{h1}-{h2}"})
        pts = 0
        if data and data['response']:
            # Ordiniamo per data decrescente e prendiamo i primi 5
            sorted_fixtures = sorted(data['response'], key=lambda x: x['fixture']['date'], reverse=True)
            for m in sorted_fixtures[:5]:
                if m['goals']['home'] is None: continue
                if m['goals']['home'] > m['goals']['away']: pts += 3 if m['teams']['home']['id'] == h1 else 0
                elif m['goals']['home'] < m['goals']['away']: pts += 3 if m['teams']['away']['id'] == h1 else 0
                else: pts += 1
            return (pts / 15) * 100
        return 50
    def get_fatigue(self, tid, season=None):
        # Carichiamo i match della stagione e prendiamo l'ultimo giocato
        if not season: season = datetime.now().year if datetime.now().month > 6 else datetime.now().year - 1
        data = self._get("fixtures", {"team": tid, "season": season, "status": "FT"})
        if not data or not data['response']:
            # Se fallisce per la stagione corrente, proviamo la precedente
            data = self._get("fixtures", {"team": tid, "season": season-1, "status": "FT"})
        if data and data['response']:
            sorted_fixtures = sorted(data['response'], key=lambda x: x['fixture']['date'], reverse=True)
            last_match = sorted_fixtures[0]
            d = datetime.fromisoformat(last_match['fixture']['date'].replace('Z', '+00:00'))
            now_utc = datetime.now(timezone.utc)
            diff = (now_utc - d).total_seconds() / 3600 / 24 # Differenza in giorni (float)
            # Fattore fatica dinamico: meno di 3 giorni è pesante, più di 7 è riposo ottimale
            if diff < 2.5: return -20 # Turno infrasettimanale strettissimo
            if diff < 4: return -10 # Fatica standard (3-4 giorni)
            if diff > 7: return 5 # Riposo extra
            return 0
        return 0
    def get_injuries(self, fid, tid):
        data = self._get("injuries", {"fixture": fid, "team": tid})
        if not data or not data.get('response'):
            return 0
        return len(data['response']) * -3
    def get_advanced_stats(self, fid, h_id, a_id):
        """
        Recupera statistiche avanzate per un match specifico:
        Angoli, Cartellini, Tiri, Falli, xG.
        """
        data = self._get("fixtures/statistics", {"fixture": fid})
        stats_map = {
            "Corner Kicks": "corners",
            "Yellow Cards": "yellow_cards",
            "Red Cards": "red_cards",
            "Total Shots": "shots_total",
            "Shots on Goal": "shots_on_goal",
            "Fouls": "fouls",
            "expected_goals": "xg"
        }
        res = {"home": {v: 0 for v in stats_map.values()}, "away": {v: 0 for v in stats_map.values()}}
        if data and data.get('response'):
            for team_stat in data['response']:
                side = "home" if str(team_stat['team']['id']) == str(h_id) else "away"
                for s in team_stat['statistics']:
                    if s['type'] in stats_map:
                        val = s['value']
                        if val is None: val = 0
                        if isinstance(val, str) and "%" in val: val = float(val.replace("%", ""))
                        res[side][stats_map[s['type']]] = float(val)
        return res
    def get_odds(self, fid, h_name=None, a_name=None, date_str=None):
        # 0. Supporto per ID Ibridi Diretta (es. d_1_...)
        if str(fid).startswith("d_"):
            d_id = fid.replace("d_", "")
            d_odds = self.diretta.get_odds(d_id)
            if d_odds:
                return {
                    "1X2": {"Home": d_odds["1"], "Draw": d_odds["X"], "Away": d_odds["2"]},
                    "DC": {}, "UO25": {}, "GG": {}, "UO15": {}, "UO35": {}, "MG": {}, 
                    "TEAM_GOALS": {}, "CORNERS": {}, "CARDS": {}, "SHOTS": {}, "FOULS": {}
                }
        # 1. Tenta API-Sports (veloce e strutturato)
        data = self._get("odds", {"fixture": fid})
        odds_dict = {
            "1X2": {}, "DC": {}, "UO25": {}, "GG": {}, 
            "UO15": {}, "UO35": {}, "MG": {}, "TEAM_GOALS": {},
            "CORNERS": {}, "CARDS": {}, "SHOTS": {}, "FOULS": {}
        }
        # 2. Fallback su Diretta.it per quote 1X2 REALI se API fallisce
        if (not data or not data.get('response')) and h_name and a_name and date_str:
            d_id = self.diretta.find_match_id(h_name, a_name, date_str)
            if d_id:
                d_odds = self.diretta.get_odds(d_id)
                if d_odds:
                    print(f"  [Diretta] Quote reali 1X2 recuperate: {d_odds['1']} - {d_odds['X']} - {d_odds['2']}")
                    odds_dict["1X2"] = {"Home": d_odds["1"], "Draw": d_odds["X"], "Away": d_odds["2"]}
        if data and data.get('response') and len(data['response']) > 0:
            resp = data['response'][0]
            if resp.get('bookmakers'):
                priority_ids = [7, 40, 13, 8, 1, 10]
                selected_book = None
                for b_id in priority_ids:
                    for book in resp['bookmakers']:
                        if book['id'] == b_id:
                            selected_book = book
                            break
                    if selected_book: break
                if not selected_book and resp.get('bookmakers'):
                    selected_book = resp['bookmakers'][0]
                if selected_book:
                    for bet in selected_book.get('bets', []):
                        bn = bet['name']
                        if bn == "Match Winner":
                            odds_dict["1X2"] = {v['value']: float(v['odd']) for v in bet['values']}
                        elif bn == "Double Chance":
                            mapping = {"Home/Draw": "1X", "Draw/Away": "X2", "Home/Away": "12"}
                            odds_dict["DC"] = {mapping.get(v['value'], v['value']): float(v['odd']) for v in bet['values']}
                        elif bn == "Goals Over/Under":
                            for v in bet['values']:
                                if "1.5" in v['value']:
                                    key = "Over" if "Over" in v['value'] else "Under"
                                    odds_dict["UO15"][key] = float(v['odd'])
                                elif "2.5" in v['value']:
                                    key = "Over" if "Over" in v['value'] else "Under"
                                    odds_dict["UO25"][key] = float(v['odd'])
                                elif "3.5" in v['value']:
                                    key = "Over" if "Over" in v['value'] else "Under"
                                    odds_dict["UO35"][key] = float(v['odd'])
                        elif bn == "Both Teams Score":
                            odds_dict["GG"] = {v['value']: float(v['odd']) for v in bet['values']}
                        elif "Multi Goals" in bn:
                            for v in bet['values']: odds_dict["MG"][v['value']] = float(v['odd'])
                        elif "Corners" in bn:
                            for v in bet['values']: odds_dict["CORNERS"][f"{bn}: {v['value']}"] = float(v['odd'])
                        elif "Cards" in bn:
                            for v in bet['values']: odds_dict["CARDS"][f"{bn}: {v['value']}"] = float(v['odd'])
                        elif "Shots" in bn:
                            for v in bet['values']: odds_dict["SHOTS"][f"{bn}: {v['value']}"] = float(v['odd'])
                        elif "Fouls" in bn:
                            for v in bet['values']: odds_dict["FOULS"][f"{bn}: {v['value']}"] = float(v['odd'])
        return odds_dict
    def calculate_strength(self, tid, last, standing, is_home, h2h, fatigue, inj, is_cup=False, lid=None, team_name=""):
        pts = 0
        matches_count = len(last)
        trend = 0 
        # 1. ANALISI CASA/FUORI SPECIFICA
        home_pts, away_pts = 0, 0
        home_count, away_count = 0, 0
        # Hash per variazione deterministica (evita output identici in assenza di dati)
        import zlib
        # Usiamo team_name per l'hash se tid è mancante o generico
        seed = str(tid) if tid and not str(tid).startswith("espn_") else team_name
        t_hash = (zlib.adler32(seed.encode()) % 100) / 20.0 - 2.5 # Range [-2.5, 2.5]
        if matches_count > 0:
            for i, f in enumerate(last):
                if f['goals']['home'] is None: continue
                is_win = False
                match_pts = 0
                if f['teams']['home']['id'] == tid:
                    home_count += 1
                    if f['goals']['home'] > f['goals']['away']: is_win = True; match_pts = 3
                    elif f['goals']['home'] == f['goals']['away']: match_pts = 1
                    home_pts += match_pts
                else:
                    away_count += 1
                    if f['goals']['away'] > f['goals']['home']: is_win = True; match_pts = 3
                    elif f['goals']['away'] == f['goals']['home']: match_pts = 1
                    away_pts += match_pts
                pts += match_pts
                if is_win and i < 2: trend += 15 # Aumentato peso trend recentissimo
            f_s = (pts / (matches_count * 3)) * 100
            # Fattore Campo Specifico
            if is_home and home_count > 0:
                f_s = (f_s * 0.6) + ((home_pts / (home_count * 3)) * 100 * 0.4)
            elif not is_home and away_count > 0:
                f_s = (f_s * 0.6) + ((away_pts / (away_count * 3)) * 100 * 0.4)
        else: 
            # Baseline analitica: se non abbiamo dati, usiamo una forza neutrale (50)
            # ma consideriamo il prestigio della lega come proxy (lid) se disponibile
            # Aggiungiamo il t_hash per diversificare i team senza dati reali
            f_s = (52 if lid in [2, 39, 140] else 48) + t_hash
        r_s = None
        motivation = 0
        if standing:
            for t in standing:
                if t['team']['id'] == tid:
                    r_s = ((len(standing) - t['rank'] + 1) / len(standing)) * 100
                    # Motivazione dinamica: ultime 10 giornate pesano di più
                    if t['rank'] <= 4 or t['rank'] >= (len(standing) - 3):
                        motivation = 20
                    break
        # 3. DISTRIBUZIONE PESI DINAMICA
        w_forma = self.weights.get("w_forma", 0.35)
        w_class = self.weights.get("w_class", 0.15)
        w_h2h = self.weights.get("w_h2h", 0.10)
        w_cont = self.weights.get("w_cont", 0.40)
        # Se è una coppa, la classifica conta meno della forma e del contesto
        if is_cup:
            w_class *= 0.5
            w_forma += (w_class * 0.5)
            w_cont += (w_class * 0.5)
            w_class = 0 # In coppa spesso la classifica è fuorviante
        h_a = 0
        if is_home:
            # Fattore campo ridotto in coppa se non è specificato lo stadio (spesso campo neutro o doppia sfida)
            h_a = 25 if lid == 2 else (10 if is_cup else 15)
        new_coach_bonus = 0
        if matches_count >= 3:
            recent_pts = sum([3 if (l['goals']['home'] > l['goals']['away'] if l['teams']['home']['id'] == tid else l['goals']['away'] > l['goals']['home']) else 1 for l in last[:3] if l['goals']['home'] is not None])
            old_pts = sum([3 if (l['goals']['home'] > l['goals']['away'] if l['teams']['home']['id'] == tid else l['goals']['away'] > l['goals']['home']) else 1 for l in last[3:] if l['goals']['home'] is not None])
            if recent_pts > old_pts + 4: new_coach_bonus = 10
        if r_s is None:
            # Baseline analitica: se non abbiamo classifica, usiamo un valore neutrale
            # che riflette la forza media attesa (50.0).
            # Aggiungiamo t_hash per non avere lo stesso r_s per tutti
            r_s = 50.0 + t_hash
            # Ridistribuiamo il peso della classifica se manca
            redist = w_class / 2
            w_forma += redist
            w_h2h += redist
            w_class = 0
        context_score = (fatigue + inj + h_a + trend + motivation + new_coach_bonus + 50)
        strength = (f_s * w_forma) + (r_s * w_class) + (h2h * w_h2h) + (context_score * w_cont)
        return strength
    def poisson_probability(self, lambda_val, k):
        import math
        return (math.exp(-lambda_val) * (lambda_val**k)) / math.factorial(k)
    def monte_carlo_simulation(self, exp_h, exp_a, simulations=15000):
        """
        Simulazione Monte Carlo avanzata per probabilità match.
        Include una leggera correzione per il pareggio (Draw Bias) tipica del calcio reale.
        """
        def poisson_random(lmbda):
            if lmbda <= 0: return 0
            L = math.exp(-lmbda)
            k = 0
            p = 1
            while p > L:
                k += 1
                p *= random.random()
                if k > 15: break # Cap per sicurezza
            return k - 1

        res_counts = {"1": 0, "X": 0, "2": 0, "O15": 0, "U15": 0, "O25": 0, "U25": 0, "O35": 0, "U35": 0, "GG": 0, "NG": 0}
        
        # Pesi specifici dal "Cervello"
        w_uo = self.weights.get("w_uo", 0.50)
        w_gg = self.weights.get("w_gg", 0.50)
        
        for _ in range(simulations):
            h_g = poisson_random(exp_h)
            a_g = poisson_random(exp_a)
            
            # Draw Bias Correction: nel calcio reale gli 0-0 e 1-1 sono più frequenti della Poisson pura
            if h_g == a_g and random.random() < 0.08: # 8% boost ai pareggi
                pass 
            
            tot_g = h_g + a_g
            if h_g > a_g: res_counts["1"] += 1
            elif h_g < a_g: res_counts["2"] += 1
            else: res_counts["X"] += 1
            
            if tot_g > 1.5: res_counts["O15"] += 1
            else: res_counts["U15"] += 1
            if tot_g > 2.5: res_counts["O25"] += 1
            else: res_counts["U25"] += 1
            if tot_g > 3.5: res_counts["O35"] += 1
            else: res_counts["U35"] += 1
            
            if h_g > 0 and a_g > 0: res_counts["GG"] += 1
            else: res_counts["NG"] += 1
            
        return {k: (v / simulations) * 100 for k, v in res_counts.items()}

    def calculate_match_probabilities(self, h_avg, a_avg):
        """Calcolo deterministico Poisson (Fallback per Monte Carlo)"""
        probs = {
            "1": 0, "X": 0, "2": 0, 
            "O15": 0, "U15": 0, "O25": 0, "U25": 0, "O35": 0, "U35": 0, "GG": 0, "NG": 0
        }
        # Aumentiamo il range a 8 gol per precisione estrema
        h_probs = [self.poisson_probability(h_avg, i) for i in range(9)]
        a_probs = [self.poisson_probability(a_avg, i) for i in range(9)]
        
        for i in range(9):
            for j in range(9):
                p_score = h_probs[i] * a_probs[j]
                if i > j: probs["1"] += p_score
                elif i == j: probs["X"] += p_score
                else: probs["2"] += p_score
                
                total_goals = i + j
                if total_goals > 1.5: probs["O15"] += p_score
                else: probs["U15"] += p_score
                if total_goals > 2.5: probs["O25"] += p_score
                else: probs["U25"] += p_score
                if total_goals > 3.5: probs["O35"] += p_score
                else: probs["U35"] += p_score
                
                if i > 0 and j > 0: probs["GG"] += p_score
                else: probs["NG"] += p_score
                
        total_sum = probs["1"] + probs["X"] + probs["2"]
        if total_sum > 0:
            for k in probs:
                probs[k] /= total_sum
        return {k: v * 100 for k, v in probs.items()}
    def get_referee_stats(self, ref_name):
        if not ref_name: return {"cards": 4.5, "penalties": 0.25}
        # Baseline analitica per arbitro: medie standard professionali
        # In futuro si potrebbe integrare un lookup reale qui
        return {"cards": 4.5, "penalties": 0.25}
    def get_lineups(self, fid):
        data = self._get("fixtures/lineups", {"fixture": fid})
        if not data or not data.get('response'):
            return []
        return data['response']
    def get_espn_fixtures(self, date_str, quiet=False, top_only=True):
        import requests
        d_espn = date_str.replace("-", "")
        # Mapping Slugs -> API-Sports IDs
        slug_to_id = {
            "eng.1": 39, "ita.1": 135, "ita.2": 136, "esp.1": 140, "ger.1": 78, "fra.1": 61,
            "uefa.champions": 2, "uefa.europa": 3, 
            "uefa.conf": 848, "uefa.conference": 848, "uefa.europa.conf": 848,
            "fifa.world": 1
        }
        # Lista raffinata: Top Europee, Coppe e Mondiali
        top_leagues = list(slug_to_id.keys())
        all_leagues = top_leagues + ["bra.1", "arg.1", "mex.1", "usa.1", "ned.1", "por.1", "bel.1", "tur.1"]
        leagues_to_scan = top_leagues if top_only else all_leagues
        all_matches = []
        if not quiet: print(f"Recupero calendari da ESPN... ", end="", flush=True)
        for l in leagues_to_scan:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{l}/scoreboard"
            try:
                r = requests.get(url, params={"dates": d_espn}, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    l_id = slug_to_id.get(l)
                    for event in data.get('events', []):
                        h = event['competitions'][0]['competitors'][0]
                        a = event['competitions'][0]['competitors'][1]
                        home = h if h['homeAway'] == 'home' else a
                        away = a if a['homeAway'] == 'away' else h
                        # Recupero dei gol se il match è iniziato/finito
                        h_score = int(home.get('score', 0)) if home.get('score') else 0
                        a_score = int(away.get('score', 0)) if away.get('score') else 0
                        status_short = event['status']['type']['shortDetail']
                        match = {
                            "fixture": {"id": f"espn_{event['id']}", "date": event['date'], "status": {"short": status_short}},
                            "league": {"name": data['leagues'][0]['name'], "id": l_id},
                            "teams": {
                                "home": {"name": home['team']['displayName'], "id": None, "score": h_score},
                                "away": {"name": away['team']['displayName'], "id": None, "score": a_score}
                            }
                        }
                        all_matches.append(match)
            except: continue
        if not quiet and all_matches: print(f"Trovati {len(all_matches)} match.")
        return all_matches
    def _get_keywords(self, name):
        import re
        import unicodedata
        # Normalizzazione caratteri accentati (es. München -> Munchen)
        name = "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
        ignore = ["fc", "ac", "afc", "sc", "cf", "sl", "as", "ss", "asf", "afc", "real", "club", "atletico", "de", "la", "united", "city", "as", "ss", "sl", "1907", "calcio", "u19", "u23", "sd", "cd", "ca", "clube", "de", "portugal", "sporting", "cl", "munchen", "münchen"]
        # Pulizia caratteri speciali (incluso / e .)
        clean_name = re.sub(r'[\(\[].*?[\)\]]', '', name).strip().lower()
        clean_name = clean_name.replace("/", " ").replace(".", " ").replace("-", " ").replace("'", " ")
        words = [w for w in clean_name.split() if len(w) >= 2]
        important = [w for w in words if w not in ignore]
        return important if important else words
    def find_api_sports_fixture(self, espn_match):
        """
        Cerca l'ID reale di API-Sports partendo da un match ESPN o Diretta.
        Usa Fuzzy Matching e ricerca diretta per ID se disponibile.
        """
        h_name = espn_match['teams']['home']['name'].lower()
        a_name = espn_match['teams']['away']['name'].lower()
        dt_str = espn_match['fixture']['date']
        base_date_dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        check_date = base_date_dt.strftime('%Y-%m-%d')
        lid = espn_match.get('league', {}).get('id')

        # 1. Risoluzione ID team tramite alias per ricerca diretta (Molto più veloce)
        h_id = self.team_aliases.get(h_name, {}).get('id')
        a_id = self.team_aliases.get(a_name, {}).get('id')
        
        if h_id:
            # Cerchiamo i match del team home in quel giorno
            params = {"team": h_id, "date": check_date}
            if lid: params["league"] = lid
            data = self._get("fixtures", params, use_cache=True)
            if data and data.get('response'):
                for f in data['response']:
                    f_a = f['teams']['away']['name'].lower()
                    if a_id and f['teams']['away']['id'] == a_id: return f
                    if a_name in f_a or f_a in a_name: return f
                    if difflib.SequenceMatcher(None, a_name, f_a).ratio() > 0.8: return f

        # 2. OTTIMIZZAZIONE: Controlla se il match è già in history.json (Usa la cache in memoria)
        history_file = "history.json"
        history = self._safe_read_json(history_file) or []
        for entry in history:
            m_name = entry.get('m', '')
            if " vs " in m_name:
                h_hist, a_hist = [p.strip().lower() for p in m_name.split(" vs ")]
            elif "-" in m_name:
                parts = m_name.split("-")
                h_hist = parts[0].strip().lower()
                a_hist = parts[1].strip().lower() if len(parts) > 1 else ""
            else:
                continue

            h_score = difflib.SequenceMatcher(None, h_name, h_hist).ratio()
            a_score = difflib.SequenceMatcher(None, a_name, a_hist).ratio()
            
            if h_score > 0.85 and a_score > 0.85:
                try:
                    hist_dt = datetime.strptime(entry['date'], '%Y-%m-%d')
                    if abs((base_date_dt.replace(tzinfo=None) - hist_dt).days) <= 1:
                        # Se lo troviamo in history, abbiamo il fid reale
                        res = self._get("fixtures", {"id": entry['fid']}, use_cache=True)
                        if res and res.get('response'): return res['response'][0]
                except:
                    pass
        
        h_keys = self._get_keywords(h_name)
        a_keys = self._get_keywords(a_name)
        
        # 3. Ricerca generica per data e (opzionalmente) lega
        for offset in [0, -1, 1]:
            dt_check = (base_date_dt + timedelta(days=offset)).date()
            params = {"date": dt_check.strftime('%Y-%m-%d')}
            if lid: params["league"] = lid
            data = self._get("fixtures", params, use_cache=True)
            if data and data.get('response'):
                for f in data['response']:
                    api_h = f['teams']['home']['name'].lower()
                    api_a = f['teams']['away']['name'].lower()
                    h_ratio = difflib.SequenceMatcher(None, h_name, api_h).ratio()
                    a_ratio = difflib.SequenceMatcher(None, a_name, api_a).ratio()
                    h_ok = h_ratio > 0.8 or any(k in api_h for k in h_keys)
                    a_ok = a_ratio > 0.8 or any(k in api_a for k in a_keys)
                    if h_ok and a_ok:
                        return f
        return None
    def calculate_team_stats_detailed(self, tid, last_matches, team_name=""):
        # Baseline analitica deterministica (basata su tid o nome) per evitare uniformità eccessiva
        seed = str(tid) if tid and not str(tid).startswith("espn_") else team_name
        t_hash = (zlib.adler32(seed.encode()) % 100) / 100.0
        base_s = 1.1 + (t_hash * 0.4) # Range [1.1, 1.5]
        base_c = 1.3 - (t_hash * 0.4) # Range [0.9, 1.3]
        if not last_matches: return base_s, base_c, 0, {"corners": 4.5, "cards": 2.1, "shots": 11.0, "fouls": 12.0}
        totals = {"scored": 0, "conceded": 0, "gg": 0, "corners": 0, "cards": 0, "shots": 0, "fouls": 0}
        count = 0
        for m in last_matches:
            if m['goals']['home'] is None: continue
            # Gol
            if m['teams']['home']['id'] == tid:
                s, c = m['goals']['home'], m['goals']['away']
            else:
                s, c = m['goals']['away'], m['goals']['home']
            totals["scored"] += s
            totals["conceded"] += c
            if s > 0 and c > 0: totals["gg"] += 1
            # Statistiche Avanzate (se presenti nel match o recuperabili)
            if 'stats' in m:
                s_adv = m['stats']
                totals["corners"] += s_adv.get("corners", 4.5)
                totals["cards"] += s_adv.get("cards", 2.1)
                totals["shots"] += s_adv.get("shots", 11.0)
                totals["fouls"] += s_adv.get("fouls", 12.0)
            else:
                # Prova a recuperare da Diretta.it se il match è recente (< 7 giorni)
                d_stats = None
                # Evitiamo di farlo per troppi match se non necessario
                if count < 3: # Solo per i 3 match più recenti per performance
                    d_id = self.diretta.find_match_id(m['teams']['home']['name'], m['teams']['away']['name'], m['fixture']['date'])
                    if d_id:
                        d_stats_full = self.diretta.get_match_stats(d_id)
                        if d_stats_full:
                            is_home = m['teams']['home']['id'] == tid
                            d_stats = d_stats_full['home'] if is_home else d_stats_full['away']
                if d_stats:
                    totals["corners"] += d_stats.get("corners", 4.5)
                    totals["cards"] += d_stats.get("cards", 2.1)
                    totals["shots"] += d_stats.get("shots", 11.0)
                    totals["fouls"] += d_stats.get("fouls", 12.0)
                else:
                    # Medie base se mancano dati granulari
                    totals["corners"] += 4.5
                    totals["cards"] += 2.1
                    totals["shots"] += 11.0
                    totals["fouls"] += 12.0
            count += 1
        if count == 0: return base_s, base_c, 0, {"corners": 4.5, "cards": 2.1, "shots": 11.0, "fouls": 12.0}
        avg_stats = {
            "corners": totals["corners"] / count,
            "yellow_cards": totals["cards"] / count,
            "shots_total": totals["shots"] / count,
            "fouls": totals["fouls"] / count
        }
        return totals["scored"]/count, totals["conceded"]/count, (totals["gg"]/count)*100, avg_stats
    def calculate_goals_detailed(self, tid, last_matches):
        # Manteniamo per compatibilità ma reindirizziamo alla nuova
        s, c, gg, _ = self.calculate_team_stats_detailed(tid, last_matches)
        return s, c, gg
    def download_csv_from_uk(self, league_code, season="2526"):
        """
        Scarica l'ultimo database CSV da football-data.co.uk (Fonte UK)
        Esempio: I1 per Serie A, E0 per Premier League
        """
        import requests
        base_url = "https://www.football-data.co.uk/mmz4281"
        filename = f"{league_code}.csv"
        url = f"{base_url}/{season}/{filename}"
        
        print(f"  [Download] Recupero database '{league_code}' stagione {season}...", end=" ", flush=True)
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(r.content)
                print(f"{Colors.GREEN}Completato!{Colors.ENDC}")
                # Rimuovi dalla cache per forzare ricaricamento
                if filename in self.csv_cache: del self.csv_cache[filename]
                return True
            else:
                print(f"{Colors.RED}Errore HTTP {r.status_code}{Colors.ENDC}")
                return False
        except Exception as e:
            print(f"{Colors.RED}Eccezione: {e}{Colors.ENDC}")
            return False

    def update_all_csv_databases(self):
        """Aggiorna tutti i campionati principali dai server UK solo se necessario"""
        last_update = self.weights.get("last_csv_update", "")
        today = datetime.now().strftime('%Y-%m-%d')
        
        if last_update == today:
            print(f"\n{Colors.GREEN}[V] Database CSV già aggiornato ad oggi ({today}). Salto download.{Colors.ENDC}")
            return

        print(f"\n{Colors.CYAN}--- AGGIORNAMENTO DATABASE STORICO (UK-DATA) ---{Colors.ENDC}")
        leagues = {
            "I1": "Serie A", "I2": "Serie B", 
            "E0": "Premier League", "E1": "Championship",
            "SP1": "La Liga", "SP2": "Segunda Division",
            "D1": "Bundesliga", "D2": "2. Bundesliga",
            "F1": "Ligue 1", "F2": "Ligue 2",
            "N1": "Eredivisie", "P1": "Liga Portugal",
            "B1": "Pro League", "T1": "Super Lig"
        }
        success = 0
        for code, name in leagues.items():
            if self.download_csv_from_uk(code):
                success += 1
        
        if success > 0:
            self.weights["last_csv_update"] = today
            self._save_weights()
            print(f"\n{Colors.GREEN}[V] Database aggiornato: {success}/{len(leagues)} campionati scaricati.{Colors.ENDC}")
        else:
            print(f"\n{Colors.RED}[!] Errore durante l'aggiornamento del database.{Colors.ENDC}")

    def _get_csv(self, league_code, season_str="2526"):
        """
        Carica dati storici da file CSV (es: I1.csv per Serie A) scaricati da football-data.co.uk
        """
        import csv
        filename = f"{league_code}_{season_str}.csv"
        if not os.path.exists(filename):
            filename = f"{league_code}.csv"
            if not os.path.exists(filename): return None
        # Controllo cache
        if filename in self.csv_cache:
            return self.csv_cache[filename]
        matches = []
        encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
        for enc in encodings:
            try:
                with open(filename, "r", encoding=enc, newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not row.get('HomeTeam') or not row.get('AwayTeam'): 
                            continue
                        fthg = row.get('FTHG')
                        ftag = row.get('FTAG')
                        gh = int(fthg) if fthg not in [None, ""] else None
                        ga = int(ftag) if ftag not in [None, ""] else None
                        matches.append({
                            "fixture": {"date": row.get('Date', '')},
                            "teams": {
                                "home": {"name": row['HomeTeam'], "id": f"csv_{row['HomeTeam']}"},
                                "away": {"name": row['AwayTeam'], "id": f"csv_{row['AwayTeam']}"}
                            },
                            "goals": {"home": gh, "away": ga}
                        })
                res = {"response": matches}
                self.csv_cache[filename] = res
                return res
            except UnicodeDecodeError:
                matches = []
                continue
            except Exception as e:
                print(f"Errore caricamento CSV {filename}: {e}")
                break
        return None
    def get_team_matches(self, tid, season, team_name=""):
        """
        Recupera i match di un team, gestendo API-Sports, Football-Data.org e CSV Locali
        """
        # Se tid è None o è un ID temporaneo (espn_), proviamo a cercarlo prima su API-Sports
        is_temp_id = str(tid).startswith("espn_") if tid else False
        if (not tid or is_temp_id) and team_name and len(team_name) > 2:
            print(f"  [Ricerca ID] Cerco ID professionale per '{team_name}'...")
            t_info = self.search_team(team_name)
            if t_info and t_info.get('id') and not str(t_info['id']).startswith("espn_"):
                tid = t_info['id']
                print(f"  [Ricerca ID] Trovato ID {tid} per {team_name}")
            elif is_temp_id:
                # Se avevamo un ID ESPN e la ricerca non ha dato frutti professionali, 
                # usiamo il nome per il fallback CSV
                return self.get_team_matches(f"csv_{team_name}", season)
            elif not tid:
                return self.get_team_matches(f"csv_{team_name}", season)
        # 1. Controllo se è un ID CSV o se dobbiamo forzare ricerca in CSV
        is_csv_id = str(tid).startswith("csv_")
        t_name_clean = str(tid).replace("csv_", "").replace("espn_", "").lower()
        t_keys = self._get_keywords(t_name_clean)
        if is_csv_id or is_temp_id:
            # Proviamo prima i CSV se è un ID CSV o se la ricerca API è fallita sopra
            all_matches = []
            for f in os.listdir("."):
                if f.endswith(".csv"):
                    data = self._get_csv(f.replace(".csv", ""))
                    if data:
                        for m in data['response']:
                            h_n = m['teams']['home']['name'].lower()
                            a_n = m['teams']['away']['name'].lower()
                            if any(k in h_n for k in t_keys) or any(k in a_n for k in t_keys):
                                all_matches.append(m)
            if all_matches:
                print(f"  [Dati CSV] Recuperati {len(all_matches)} match storici per {t_name_clean.title()}")
                return {"response": all_matches}
            if is_temp_id:
                # Se è un ID ESPN e non abbiamo trovato nulla neanche nei CSV, 
                # proviamo comunque l'API con il nome se possibile (anche se tid è stringa)
                pass
        # 2. Football-Data.org
        if str(tid).startswith("fd_"):
            fd_id = tid.replace("fd_", "")
            data = self._get_fd(f"teams/{fd_id}/matches", {"status": "FINISHED", "limit": 10})
            if data and 'matches' in data:
                converted = []
                for m in data['matches']:
                    converted.append({
                        "fixture": {"date": m['utcDate']},
                        "teams": {
                            "home": {"id": f"fd_{m['homeTeam']['id']}", "name": m['homeTeam']['name']},
                            "away": {"id": f"fd_{m['awayTeam']['id']}", "name": m['awayTeam']['name']}
                        },
                        "goals": {"home": m['score']['fullTime']['home'], "away": m['score']['fullTime']['away']}
                    })
                return {"response": converted}
            return None
        # 3. API-Sports
        # Fetching multiple seasons for deeper history (Future-Ready)
        all_fixtures = []
        for s in [season, season - 1]:
            data = self._get("fixtures", {"team": tid, "season": s, "status": "FT"}, use_cache=True)
            if data and data.get('response'):
                all_fixtures.extend(data['response'])
        if all_fixtures:
            return {"response": all_fixtures}
        # 4. Fallback finale su CSV se API-Sports fallisce
        if not all_fixtures:
            t_name = team_name
            if not t_name:
                # Se non abbiamo il nome, proviamo a recuperarlo ma se l'API è sospesa fallirà
                team_info = self._get("teams", {"id": tid}, use_cache=True)
                if team_info and team_info.get('response'):
                    t_name = team_info['response'][0]['team']['name']
            if t_name:
                return self.get_team_matches(f"csv_{t_name}", season)
        return data
    def analyze_match_list(self, fixtures, title="ANALISI"):
        print(f"\n[{title.center(76)}]")
        all_preds = []
        now = datetime.now(timezone.utc)
        history_file = "history.json"
        history = self._safe_read_json(history_file) or []
        history_index = {h.get('fid'): h for h in history if isinstance(h, dict) and h.get('fid') is not None}
        flush_every = 25
        for i_fix, fix in enumerate(fixtures, start=1):
            try:
                # 0. Risoluzione ID (Mapping ESPN/Diretta -> API-Sports)
                fid_orig = fix['fixture']['id']
                if fid_orig and (str(fid_orig).startswith("espn_") or str(fid_orig).startswith("none")):
                    print(f"  [Mapping] Cerco ID API-Sports per {fix['teams']['home']['name']}...")
                    real_fix = self.find_api_sports_fixture(fix)
                    if real_fix:
                        print(f"  [Mapping] Match mappato correttamente su API-Sports (ID: {real_fix['fixture']['id']})")
                        fix = real_fix
                    else:
                        print(f"  [Mapping] Nessun ID trovato, procedo con fallback ESPN/CSV.")
                h, a = fix['teams']['home'], fix['teams']['away']
                fid, fdate = fix['fixture']['id'], fix['fixture']['date']
                l_info = fix.get('league') or {"name": "Unknown", "id": 0}
                lid = l_info.get('id', 0)
                # Determinazione stagione dinamica basata sulla data del match e sulla lega
                # Le leghe sudamericane/USA seguono l'anno solare, quelle europee il ciclo autunno-primavera
                match_dt = datetime.fromisoformat(fdate.replace('Z', '+00:00'))
                is_calendar_year = lid in [71, 72, 128, 265, 242, 262, 239, 253] # Brasile, Argentina, MLS, etc.
                if is_calendar_year:
                    season = match_dt.year
                else:
                    # Ciclo europeo: se il match è prima di Luglio, la stagione è l'anno precedente
                    season = match_dt.year if match_dt.month >= 7 else match_dt.year - 1
                is_fd = str(fid).startswith("fd_")
                is_espn = str(fid).startswith("espn_")
                is_cup = l_info.get('type') == 'Cup' or lid in [2, 3, 4, 5, 6, 7, 8, 9, 10, 137, 848]
                # Utilizzo API forzato per analisi (cache solo per ricerca fixtures)
                force_refresh = True 
                reasoning = []
                ita_date = match_dt.astimezone()
                c_d = ita_date.strftime('%d/%m %H:%M')
                lineups = self.get_lineups(fid) if not is_fd and not is_espn and (match_dt - now).total_seconds() / 3600 < 1.5 else []
                std = self.get_standings(lid, season, league_name=l_info.get('name', ''))
                # Recupero dati con fallback integrato
                h_l_data = self.get_team_matches(h['id'], season, team_name=h['name'])
                a_l_data = self.get_team_matches(a['id'], season, team_name=a['name'])
                # Se siamo in coppa e non abbiamo dati per la stagione corrente, proviamo la precedente per match recenti
                if is_cup:
                    if not h_l_data or not h_l_data.get('response'): h_l_data = self.get_team_matches(h['id'], season - 1, team_name=h['name'])
                    if not a_l_data or not a_l_data.get('response'): a_l_data = self.get_team_matches(a['id'], season - 1, team_name=a['name'])
                # Filtriamo localmente le ultime 20 (Deep History)
                h_l = sorted(h_l_data['response'], key=lambda x: x['fixture']['date'], reverse=True)[:20] if h_l_data and h_l_data.get('response') else []
                a_l = sorted(a_l_data['response'], key=lambda x: x['fixture']['date'], reverse=True)[:20] if a_l_data and a_l_data.get('response') else []
                h_s, h_c, h_gg, h_adv = self.calculate_team_stats_detailed(h['id'], h_l, team_name=h['name'])
                a_s, a_c, a_gg, a_adv = self.calculate_team_stats_detailed(a['id'], a_l, team_name=a['name'])
                # Combiniamo le statistiche avanzate per il match
                match_adv = {
                    "home": {**h_adv, "name": h['name']},
                    "away": {**a_adv, "name": a['name']}
                }
                exp_h = (h_s + a_c) / 2
                exp_a = (a_s + h_c) / 2
                # Aggiungiamo un micro-bias analitico se mancano dati reali
                if not h_l and not a_l:
                    # Invece di random, usiamo un leggero vantaggio casa predefinito (1.05x / 0.95x)
                    exp_h *= 1.05
                    exp_a *= 0.95
                h_xg, a_xg, h_xga, a_xga = 0, 0, 0, 0
                # 1. Tenta API-Sports (solo se non è un match Football-Data o ESPN)
                if not is_fd and not is_espn:
                    stats_data = self._get("fixtures/statistics", {"fixture": fid}, use_cache=not force_refresh)
                    if stats_data and stats_data['response']:
                        for s_entry in stats_data['response']:
                            xg_val = next((item['value'] for item in s_entry['statistics'] if item['type'] == "expected_goals"), 0)
                            if s_entry['team']['id'] == h['id']: h_xg = float(xg_val or 0)
                            else: a_xg = float(xg_val or 0)
                        h_xga, a_xga = a_xg, h_xg
                # 2. Fallback su Diretta.it se API fallisce o non ha xG (anche per FD ed ESPN)
                if h_xg == 0:
                    # Cerchiamo il match su Diretta (scansione fino a 7gg)
                    match_dt_date = datetime.fromisoformat(fdate.replace('Z', '+00:00')).date()
                    day_diff = (match_dt_date - datetime.now().date()).days
                    if abs(day_diff) <= 7:
                        d_matches = self.diretta.get_matches(day_diff)
                        d_id = None
                        for dm in d_matches:
                            # Matching più robusto per il fallback
                            h_dm, a_dm = dm['home'].lower(), dm['away'].lower()
                            h_api, a_api = h['name'].lower(), a['name'].lower()
                            if (h_api in h_dm or h_dm in h_api) and (a_api in a_dm or a_dm in a_api):
                                d_id = dm['id']
                                break
                        if d_id:
                            print(f"  [Diretta] Recupero xG e statistiche live per {h['name']}...")
                            d_stats = self.diretta.get_match_stats(d_id)
                            if d_stats:
                                h_xg, a_xg = d_stats['home']['xg'], d_stats['away']['xg']
                                h_xga, a_xga = a_xg, h_xg
                                # Possiamo anche arricchire i dati dei team se mancano
                                if not h_l: h_adv.update(d_stats['home'])
                                if not a_l: a_adv.update(d_stats['away'])
                            # Info Extra: Arbitro, Meteo, Stadio
                            d_info = self.diretta.get_match_info_extra(d_id)
                            if d_info:
                                if d_info["referee"] != "N/D": fix['fixture']['referee'] = d_info["referee"]
                                if d_info["venue"] != "N/D": fix['fixture'].setdefault('venue', {})['name'] = d_info["venue"]
                                if d_info["weather"] != "N/D": reasoning.append(f"Meteo: {d_info['weather']}")
                if h_xg > 0 and a_xg > 0:
                    exp_h = (exp_h * 0.6) + ((h_xg + a_xga) / 2 * 0.4)
                    exp_a = (exp_a * 0.6) + ((a_xg + h_xga) / 2 * 0.4)
                p_probs = self.calculate_match_probabilities(exp_h, exp_a)
                g_avg = (h_s + h_c + a_s + a_c) / 2
                g_str = f"{g_avg:.1f}" if h_l and a_l else "N/D"
                h2h = self.get_h2h(h['id'], a['id']) if not is_fd and not is_espn else 50
                # Analisi Infortuni e Fatica
                h_f, a_f = self.get_fatigue(h['id']) if not is_fd and not is_espn else 0, self.get_fatigue(a['id']) if not is_fd and not is_espn else 0
                h_i, a_i = self.get_injuries(fid, h['id']) if not is_fd and not is_espn else 0, self.get_injuries(fid, a['id']) if not is_fd and not is_espn else 0
                # Arbitro e Stadio
                ref_info = self.get_referee_stats(fix['fixture'].get('referee'))
                venue = fix['fixture'].get('venue', {}).get('name', 'N/D')
                # Strength con pesi bilanciati
                hs = self.calculate_strength(h['id'], h_l, std, True, h2h, h_f, h_i, is_cup, lid, team_name=h['name'])
                as_ = self.calculate_strength(a['id'], a_l, std, False, 100-h2h, a_f, a_i, is_cup, lid, team_name=a['name'])
                # Controllo qualità dati
                data_warning = ""
                if not h_l and not a_l and not std:
                    data_warning = " (ATTENZIONE: Dati storici insufficienti)"
                    # Nessun bias casuale: usiamo i valori calcolati hs/as_ puri
                    pass
                # Mix Probabilità: Monte Carlo (xG + Stats) + Forza Relativa (Smart Brain)
                # La simulazione Monte Carlo è il cuore del nuovo modello "Future"
                mc_probs = self.monte_carlo_simulation(exp_h, exp_a)
                # Forza Relativa (Smart Brain) components normalized to 100%
                sb_x = 22.0 # Fattore X base leggermente ridotto per favorire 12
                sb_h = (hs / (hs + as_)) * 100
                sb_a = (as_ / (hs + as_)) * 100
                total_sb = sb_h + sb_a + sb_x
                # Mix finale bilanciato (40% Monte Carlo, 60% Smart Brain)
                p1 = (mc_probs["1"] * 0.40) + ((sb_h / total_sb) * 100 * 0.60)
                p2 = (mc_probs["2"] * 0.40) + ((sb_a / total_sb) * 100 * 0.60)
                px = (mc_probs["X"] * 0.40) + ((sb_x / total_sb) * 100 * 0.60)
                # Normalizzazione finale per sicurezza
                total_p = p1 + p2 + px
                p1, p2, px = (p1/total_p)*100, (p2/total_p)*100, (px/total_p)*100
                # Aggiorniamo p_probs con i risultati della simulazione MC
                p_probs.update(mc_probs)
                # Recupero quote reali
                real_odds = self.get_odds(fid, h_name=h['name'], a_name=a['name'], date_str=fdate)
                if not any(real_odds.values()):
                    d_id = self.diretta.find_match_id(h['name'], a['name'], fdate)
                    if d_id:
                        d_odds = self.diretta.get_odds(d_id)
                        if d_odds:
                            print(f"  [Diretta] Quote reali 1X2 recuperate: {d_odds['1']} - {d_odds['X']} - {d_odds['2']}")
                            real_odds["1X2"] = {"Home": d_odds["1"], "Draw": d_odds["X"], "Away": d_odds["2"]}
                has_real_odds = any(v for v in real_odds.values() if v)
                if not has_real_odds:
                    reasons = []
                    reasons.append("API-Sports sospesa" if self.api_suspended else "API-Sports N/D")
                    reasons.append("Diretta N/D")
                    msg = f"Quote reali non disponibili ({', '.join(reasons)}). EV=SIM."
                    print(f"  {Colors.YELLOW}[QUOTE] {msg}{Colors.ENDC}")
                    try:
                        self._log_error(f"[QUOTE] {h['name']} vs {a['name']} {fdate[:10]}: {msg}")
                    except:
                        pass
                diff = hs - as_
                value_bets = []
                def calc_kelly(p, o):
                    if o <= 1: return 0
                    k = (p/100 * o - 1) / (o - 1)
                    return max(0, k * 0.1) # Kelly frazionata 10% per prudenza
                if real_odds["1X2"]:
                    ev1 = (p1/100 * real_odds["1X2"].get("Home", 1)) - 1
                    evx = (px/100 * real_odds["1X2"].get("Draw", 1)) - 1
                    ev2 = (p2/100 * real_odds["1X2"].get("Away", 1)) - 1
                    if ev1 > 0.10: 
                        k1 = calc_kelly(p1, real_odds["1X2"].get("Home", 1))
                        value_bets.append(f"1 (EV: {ev1*100:+.1f}%, Kelly: {k1*100:.1f}%)")
                    if evx > 0.10: 
                        kx = calc_kelly(px, real_odds["1X2"].get("Draw", 1))
                        value_bets.append(f"X (EV: {evx*100:+.1f}%, Kelly: {kx*100:.1f}%)")
                    if ev2 > 0.10: 
                        k2 = calc_kelly(p2, real_odds["1X2"].get("Away", 1))
                        value_bets.append(f"2 (EV: {ev2*100:+.1f}%, Kelly: {k2*100:.1f}%)")
                preds = {}
                is_trap = False
                if diff > 20 and (h_f < 0 or h_i < -10 or a_f > 0): is_trap = True
                if abs(diff) < 10: reasoning.append("Match molto equilibrato.")
                elif diff > 25: reasoning.append(f"Divario tecnico pro {h['name']}.")
                elif diff < -25: reasoning.append(f"Divario tecnico pro {a['name']}.")
                if is_cup: reasoning.append("Coppa: esperienza conta più della classifica.")
                if h_f < 0: reasoning.append(f"Fatica per {h['name']}.")
                if a_f < 0: reasoning.append(f"Fatica per {a['name']}.")
                if ref_info['cards'] > 5: reasoning.append(f"Arbitro severo ({ref_info['cards']:.1f} cart/m).")
                if is_trap: reasoning.append("ATTENZIONE: Match TRAPPOLA.")
                print(f"- {Colors.BOLD}{h['name']}{Colors.ENDC} vs {Colors.BOLD}{a['name']}{Colors.ENDC} ({Colors.CYAN}{c_d}{Colors.ENDC})")
                if is_trap: print(f"  {Colors.RED}⚠️ TRAPPOLA{Colors.ENDC}")
                # Calcoliamo i tre livelli
                for lvl in ["FACILE", "MEDIA", "DIFFICILE"]:
                    preds[lvl] = self._get_pred(lvl, p1, p2, px, p_probs, real_odds, is_trap, adv_stats=match_adv)
                # Determiniamo dinamicamente qual è la scelta migliore basata sullo score matematico
                best_lvl = "MEDIA"
                max_score = -999
                for lvl in ["FACILE", "MEDIA", "DIFFICILE"]:
                    score = preds[lvl]['score']
                    if lvl == "MEDIA": score *= 1.1
                    elif lvl == "DIFFICILE": score *= 1.2
                    if score > max_score:
                        max_score = score
                        best_lvl = lvl
                if has_real_odds:
                    if preds[best_lvl]['ev'] < -0.15 or preds[best_lvl]['q'] < 1.15:
                        has_value = any(preds[l]['ev'] > -0.15 for l in ["FACILE", "MEDIA", "DIFFICILE"])
                    else:
                        has_value = True
                else:
                    has_value = True
                for lvl in ["FACILE", "MEDIA", "DIFFICILE"]:
                    p_info = preds[lvl]
                    cons = ""
                    if lvl == best_lvl and has_value:
                        cons = f" {Colors.GREEN}(CONSIGLIATA)*{Colors.ENDC}"
                    if has_real_odds:
                        if p_info.get('stake', 0) > 0:
                            stake_str = f"{Colors.GREEN}{p_info['stake']:.1f}%{Colors.ENDC}"
                            res_str = f"{Colors.BOLD}{p_info['res']}{Colors.ENDC}"
                        else:
                            stake_str = "0%"
                            res_str = f"{p_info['res']} (NO VALORE)" if p_info['ev'] < -0.10 else p_info['res']
                    else:
                        sim_stake = (p_info['p'] - 45) / 5 if p_info['p'] > 45 else 0
                        if p_info.get('stake', 0) <= 0 and sim_stake > 0:
                            p_info['stake'] = sim_stake
                        # Simulazione Bankroll per il livello corrente
                        b_sim = self.bankroll_simulation(p_info['p'], p_info['q'])
                        risk_str = f" [Rischio: {b_sim['risk_of_ruin']:.1f}%]"
                        stake_str = f"{Colors.YELLOW}{p_info.get('stake', 0):.1f}% (SIM){Colors.ENDC}{risk_str}" if p_info.get('stake', 0) > 0 else "0%"
                        res_str = f"{Colors.BOLD}{p_info['res']}{Colors.ENDC}"
                    print(f"  {lvl:<9}: {res_str:<35} @{p_info['q']:.2f} ({stake_str}){cons}")
                print(f"  Prob: {Colors.BLUE}1:{p1:.0f}% X:{px:.0f}% 2:{p2:.0f}%{Colors.ENDC} | Smart Brain: {Colors.CYAN}{hs:.1f} vs {as_:.1f}{Colors.ENDC}")
                print("-" * 50)
                p_data = {
                    "m": f"{h['name']} vs {a['name']}", 
                    "r": preds[best_lvl]["res"], 
                    "q": preds[best_lvl]["q"], 
                    "d": abs(diff), 
                    "lvl": best_lvl,
                    "fid": fid,
                    "lid": lid,
                    "league": l_info.get('name', ''),
                    "h_id": h['id'],
                    "a_id": a['id'],
                    "exp_h": exp_h,
                    "exp_a": exp_a,
                    "hs": hs,
                    "as": as_,
                    "date": fix['fixture']['date'][:10],
                    "ev": preds[best_lvl].get('ev', 0),
                    "stake": preds[best_lvl].get('stake', 0),
                    "p": preds[best_lvl].get('p', 0),
                    "is_real_odds": bool(preds[best_lvl].get('is_real', False))
                }
                self.session_preds.append(p_data)
                if has_value and p_data["stake"] > 0:
                    all_preds.append(p_data)
                if p_data["stake"] >= 4.0 or p_data["ev"] >= 0.08:
                    self.session_top_preds.append(p_data)
            except Exception as e:
                h_name = fix.get('teams', {}).get('home', {}).get('name', 'Unknown')
                a_name = fix.get('teams', {}).get('away', {}).get('name', 'Unknown')
                print(f"Errore nell'analisi del match {h_name} vs {a_name}: {e}")
                continue
            h_entry = history_index.get(fid)
            if h_entry:
                h_entry['r_pred'] = preds[best_lvl]["res"] if has_value else "N/D"
                h_entry['hs'] = hs
                h_entry['as'] = as_
                h_entry['exp_h'] = exp_h
                h_entry['exp_a'] = exp_a
                h_entry['processed'] = False 
                h_entry['date'] = match_dt.strftime('%Y-%m-%d')
            else:
                h_entry = {
                    "fid": fid,
                    "m": f"{h['name']} vs {a['name']}",
                    "r_pred": preds[best_lvl]["res"] if has_value else "N/D",
                    "date": match_dt.strftime('%Y-%m-%d'), 
                    "processed": False,
                    "h_id": h['id'],
                    "a_id": a['id'],
                    "exp_h": exp_h,
                    "exp_a": exp_a,
                    "hs": hs,
                    "as": as_
                }
                history.append(h_entry)
                history_index[fid] = h_entry
            if i_fix % flush_every == 0:
                self._safe_write_json(history_file, history)
            log_key = f"{fid}-{match_dt.strftime('%Y-%m-%d')}"
            if log_key not in self.session_logged:
                self.session_logged.add(log_key)
                try:
                    with file_lock:
                        with open("pronostici.txt", "a", encoding="utf-8") as f:
                            ev_str = f"{p_data['ev']*100:+.1f}%" if p_data.get("is_real_odds") else "SIM"
                            f.write(f"{match_dt.strftime('%Y-%m-%d')} | {p_data.get('league','')[:18]:<18} | {h['name']} vs {a['name']} | {best_lvl} | {p_data['r']} @{p_data['q']:.2f} | P:{p_data.get('p',0):.0f}% | Stake:{p_data['stake']:.1f}% | EV:{ev_str}\n")
                except:
                    pass
        self._safe_write_json(history_file, history)
        if all_preds: self.show_final_slip(all_preds)
    def bankroll_simulation(self, p_win, odd, bankroll=1000, simulations=350):
        """
        Simula il rischio del bankroll su 1000 iterazioni (Python Puro).
        """
        try:
            key = (round(float(p_win), 1), round(float(odd), 2), float(bankroll), int(simulations))
            cached = self._bankroll_cache.get(key)
            if cached: 
                return cached
        except:
            key = None
        win_count = 0
        total_profit = 0
        ruin_count = 0
        stake = bankroll * 0.02
        for _ in range(simulations):
            if random.random() < (p_win / 100):
                win_count += 1
                total_profit += stake * (odd - 1)
            else:
                total_profit -= stake
            if total_profit < -bankroll:
                ruin_count += 1
        res = {
            "avg_profit": total_profit / simulations,
            "risk_of_ruin": (ruin_count / simulations) * 100,
            "win_rate": (win_count / simulations) * 100
        }
        if key is not None:
            self._bankroll_cache[key] = res
        return res
    def _get_pred(self, lvl, p1, p2, px, p_probs, odds, trap, adv_stats=None):
        """
        Analisi dinamica di TUTTI i mercati per scegliere l'opzione con il miglior valore reale.
        Evita consigli ridicoli (es. @1.01) e favorisce le Value Bets (1.50 - 2.50).
        """
        # Funzione interna per ottenere la quota reale o stimata
        def get_q(market_key, outcome_key, prob, default_q):
            if odds.get(market_key) and outcome_key in odds[market_key]:
                return odds[market_key][outcome_key], True # Quota Reale
            if prob <= 0: return 10.0, False
            # Modello di Quota Dinamico (Future-Ready - Realistic estimation)
            # Maggiore è la probabilità, minore è il margine del bookmaker
            if prob > 80: margin = 0.97 # 3% margin for strong favorites
            elif prob > 50: margin = 0.94 # 6% margin
            elif prob > 30: margin = 0.91 # 9% margin
            else: margin = 0.87 # 13% margin for longshots (higher volatility)
            # Aggiustamento specifico per mercato
            if market_key in ["DC", "UO15"]: margin -= 0.03 
            elif market_key == "1X2": margin += 0.01 
            fair_q = 100 / prob
            # Favorite-Longshot Bias: outsiders have significantly lower real odds than fair
            bias_factor = 0.96 if prob < 20 else (0.98 if prob < 40 else 0.995)
            estimated = (fair_q ** bias_factor) * margin
            return max(1.10, round(estimated, 2)), False # Quota Stimata più conservativa
        # 1. Definiamo tutti i possibili mercati
        raw_markets = [
            ("1", p1, "1X2", "Home"), ("X", px, "1X2", "Draw"), ("2", p2, "1X2", "Away"),
            ("1X", p1 + px, "DC", "1X"), ("X2", p2 + px, "DC", "X2"), ("12", p1 + p2, "DC", "12"),
            ("GOL", p_probs["GG"], "GG", "Yes"), ("NO GOL", p_probs["NG"], "GG", "No"),
            ("OVER 1.5", p_probs["O15"], "UO15", "Over"), ("UNDER 1.5", p_probs["U15"], "UO15", "Under"),
            ("OVER 2.5", p_probs["O25"], "UO25", "Over"), ("UNDER 2.5", p_probs["U25"], "UO25", "Under"),
            ("OVER 3.5", p_probs["O35"], "UO35", "Over"), ("UNDER 3.5", p_probs["U35"], "UO35", "Under")
        ]
        # Estensione Mercati Avanzati (Tiri, Falli, Cartellini, VAR)
        if adv_stats and adv_stats.get("home") and adv_stats.get("away"):
            h, a = adv_stats["home"], adv_stats["away"]
            h_name, a_name = h.get("name", "Home"), a.get("name", "Away")
            # Tiri in porta (Basati su medie stagionali API-Sports)
            h_sog = h.get("shots_on_goal", 4.2); a_sog = a.get("shots_on_goal", 3.8)
            raw_markets.append((f"TIRI PORTA {h_name} >3.5", 70 if h_sog > 4.5 else 55, "SHOTS", "Home"))
            raw_markets.append((f"TIRI PORTA {a_name} >3.5", 65 if a_sog > 4.2 else 50, "SHOTS", "Away"))
            # Tiri totali
            h_st = h.get("shots_total", 12.5); a_st = a.get("shots_total", 11.0)
            raw_markets.append((f"TIRI TOTALI {h_name} >11.5", 75 if h_st > 12.0 else 55, "SHOTS_TOTAL", "Home"))
            # Cartellini e Falli (Dati statistici)
            h_cards = h.get("yellow_cards", 2.2); a_cards = a.get("yellow_cards", 2.4)
            raw_markets.append(("OVER 3.5 CARTELLINI", 72 if (h_cards + a_cards) > 4.5 else 55, "CARDS", "Over"))
            raw_markets.append(("OVER 21.5 FALLI", 68 if (h.get("fouls", 12) + a.get("fouls", 11)) > 22 else 50, "FOULS", "Over"))
            # Eventi Speciali (Probabilità medie fisse ottimizzate)
            raw_markets.append(("VAR INTERVENTO SI", 22, "VAR", "Yes"))
            raw_markets.append(("RIGORE ASSEGNATO SI", 26, "PENALTY", "Yes"))
            # Marcatori / Assist (Simulati su top player se disponibili)
            raw_markets.append(("MARCATORE (TOP SCORER)", 35, "SCORER", "Any"))
            raw_markets.append(("ASSIST (TOP ASSISTMAN)", 30, "ASSIST", "Any"))
        
        markets = []
        for res, p, cat, key in raw_markets:
            q, is_real = get_q(cat, key, p, 1.80)
            m = {"res": res, "p": p, "q": q, "cat": cat, "is_real": is_real}
            # EV Calculation
            # Se la quota è stimata, l'EV è 0 per definizione (Fair Odds rispetto al nostro brain)
            # Se la quota è reale, l'EV è il valore matematico reale
            if is_real:
                m["ev"] = (m["p"]/100 * m["q"]) - 1
            else:
                m["ev"] = 0 # Fair Odds stimata
            # Score bilanciato: Molto peso all'EV per trovare Value Bets reali
            # Se la quota è < 1.15, penalizziamo pesantemente lo score
            penalty = 0.5 if m["q"] < 1.15 else 1.0
            m["score"] = ((m["p"] * 0.3) + (m.get("ev", 0) * 100 * 0.7)) * penalty
            # Kelly Criterion (Frazionario 1/12 - Ottimizzato)
            if m["q"] > 1.05:
                # Usiamo Kelly solo se c'è EV positivo reale o probabilità > 55%
                ev_for_kelly = m["ev"] if is_real else (m["p"] - 52) / 100 
                if ev_for_kelly > 0:
                    # Formula Kelly: (bp - q) / b dove b = q - 1
                    # b = odds - 1
                    b = m["q"] - 1
                    p = m["p"] / 100
                    q = 1 - p
                    k = (b * p - q) / b if b > 0 else 0
                    # Applichiamo frazionamento prudenziale (1/12 del bankroll)
                    m["stake"] = max(0, k * (1/12) * 100)
                else:
                    m["stake"] = 0
            else: m["stake"] = 0
            markets.append(m)
        # Selezione gerarchica per evitare ripetizioni e quote inutili
        def pick_best(min_p, min_q, max_q=5.0, min_ev=-0.05, exclude_res=None):
            # 1. Tentativo ideale: Probabilità, Quota e Valore (EV) positivo
            options = [m for m in markets if m["p"] >= min_p and min_q <= m["q"] <= max_q and m["ev"] >= min_ev]
            if exclude_res:
                options = [o for o in options if o["res"] not in exclude_res]
            # 2. Se non c'è nulla di ideale, allentiamo leggermente i vincoli ma manteniamo quota minima
            if not options:
                options = [m for m in markets if m["q"] >= min_q and m["q"] <= max_q]
                if exclude_res:
                    options = [o for o in options if o["res"] not in exclude_res]
            # 3. Fallback: prendi quello con lo score più alto tra quelli non esclusi
            if not options:
                options = markets
                if exclude_res:
                    options = [o for o in options if o["res"] not in exclude_res]
            if not options: return markets[0]
            # Ordiniamo per Score (Valore Matematico)
            return sorted(options, key=lambda x: x["score"], reverse=True)[0]
        # FACILE: Quota tra 1.25 e 1.60. Cerchiamo stabilità.
        res_facile = pick_best(70, 1.25, max_q=1.60, min_ev=-0.02)
        if lvl == "FACILE": return res_facile
        # MEDIA: Quota tra 1.60 e 2.10. Il cuore delle Value Bets.
        res_media = pick_best(50, 1.60, max_q=2.10, min_ev=0.01, exclude_res=[res_facile["res"]])
        if lvl == "MEDIA": return res_media
        # DIFFICILE: Quota > 2.10. Per chi cerca il colpo o la sorpresa.
        res_difficile = pick_best(25, 2.10, max_q=5.0, min_ev=0.02, exclude_res=[res_facile["res"], res_media["res"]])
        if lvl == "DIFFICILE": return res_difficile
    def save_top_pronostici(self):
        """Genera il file PRONOSTICI_TOP.txt con i migliori match della sessione"""
        source = self.session_top_preds if self.session_top_preds else self.session_preds
        if not source:
            print(f"\n{Colors.YELLOW}[!] Nessun pronostico disponibile in questa sessione.{Colors.ENDC}")
            return
        exclude_keywords = ["u18", "u19", "u20", "primavera", "women", "donne", "femminile"]
        source = [p for p in source if not any(k in (str(p.get('m','')) + " " + str(p.get('league',''))).lower() for k in exclude_keywords)]
        
        # Deduplicazione
        unique_top = []
        seen = set()
        for p in source:
            key = f"{p['m']}-{p['date']}-{p['r']}"
            if key not in seen:
                unique_top.append(p)
                seen.add(key)
        
        # Ordina per Stake (Valore)
        unique_top.sort(key=lambda x: (x.get('stake', 0), x.get('ev', 0)), reverse=True)
        unique_top = unique_top[:10]
        
        filename = "PRONOSTICI_TOP.txt"
        label = "TOP" if self.session_top_preds else "TOP RELATIVI"
        print(f"\n{Colors.GREEN}--- CREAZIONE PRONOSTICI {label} ({len(unique_top)} MATCH) ---{Colors.ENDC}")
        
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"{label} PICKS - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"{'='*50}\n")
            for p in unique_top:
                ev_str = f"{p.get('ev', 0)*100:+.1f}%" if p.get("is_real_odds") else "SIM"
                line = f"- {p['m']:<25} | {p['r']:<10} @{p['q']:.2f} (P:{p.get('p',0):.0f}% | Stake:{p['stake']:.1f}% | EV:{ev_str})\n"
                f.write(line)
                print(line.strip())
        
        print(f"\n{Colors.GREEN}[V] Salvato in {filename}{Colors.ENDC}")

    def analyze_past_days(self, days_count):
        """
        Recupera i match finiti degli ultimi N giorni per analisi e auto-learning.
        """
        mode = input("\nTipo di analisi: [1] TOP LEAGUES (Consigliato), [2] GLOBALE: ").strip()
        top_only = mode != "2"
        print(f"\n[ANALISI STORICA] Avvio analisi per gli ultimi {days_count} giorni ({'Top' if top_only else 'Global'})...")
        today = datetime.now().date()
        all_fixtures = []
        for i in range(1, days_count + 1):
            dt_target = today - timedelta(days=i)
            target_date = dt_target.strftime('%Y-%m-%d')
            print(f"Recupero match per il {target_date}...")
            # Passiamo top_only a get_fixtures_by_date
            fixtures = self.get_fixtures_by_date(target_date, top_only=top_only)
            if fixtures:
                # Filtriamo solo i match terminati (FT) o simili
                finished = [f for f in fixtures if f.get('fixture', {}).get('status', {}).get('short') in ["FT", "AET", "PEN", "Final"]]
                if finished:
                    print(f"Trovati {len(finished)} match terminati.")
                    all_fixtures.extend(finished)
                else:
                    print("Nessun match terminato trovato per questa data.")
            else:
                print(f"Nessun dato trovato per il {target_date}.")
        if all_fixtures:
            print(f"\n[ANALISI STORICA] Trovati in totale {len(all_fixtures)} match da analizzare.")
            # Analizziamo i match (questo li aggiungerà anche a history.json)
            self.analyze_match_list(all_fixtures, title=f"ANALISI STORICA {days_count} GG")
            # Dopo l'analisi, lanciamo l'auto-learning per aggiornare i pesi con i nuovi dati in history.json
            self.run_auto_learning()
        else:
            print("\n[!] Nessun match storico trovato per l'analisi.")
    def run_auto_learning(self, manual=False):
        """
        Controlla i risultati delle partite passate salvate in history.json e aggiorna i pesi.
        Ottimizzato per grandi volumi di dati e gestione fallback.
        """
        if self.is_learning:
            if manual:
                print(f"\n{Colors.YELLOW}[!] Apprendimento già in corso in background...{Colors.ENDC}")
            return
        def _bg_task():
            self.is_learning = True
            try:
                history_file = "history.json"
                history = self._safe_read_json(history_file)
                if not history: return
                
                to_process = [h for h in history if not h.get('processed', False)]
                if not to_process: return
                
                by_date = {}
                for h in to_process:
                    d = h['date']
                    if d not in by_date: by_date[d] = []
                    by_date[d].append(h)
                
                sorted_dates = sorted(by_date.keys(), reverse=True)
                total_dates = len(sorted_dates)
                
                print(f"\n{Colors.CYAN}[BG-LEARNING] Avvio analisi totale: {len(to_process)} pronostici su {total_dates} date...{Colors.ENDC}")
                
                updated_any = False
                lr = self.weights.get("learning_rate", 0.01)
                
                for i, date_str in enumerate(sorted_dates, 1):
                    entries = by_date[date_str]
                    results = {}
                    
                    # Feedback periodico ogni 10 date
                    if i % 10 == 0:
                        print(f"{Colors.BLUE}[IA-STATUS] Elaborazione data {i}/{total_dates} ({date_str})...{Colors.ENDC}")
                    
                    # 1. Tenta API-Sports (solo se non sospesa)
                    if not self.api_suspended:
                        day_data = self._get("fixtures", {"date": date_str, "status": "FT"}, use_cache=True)
                        if day_data and day_data.get('response'):
                            results = {f['fixture']['id']: f for f in day_data['response']}
                    
                    # 2. Fallback ESPN (sempre utile per incrocio nomi)
                    espn_results = self.get_espn_fixtures(date_str, quiet=True, top_only=False)
                    for er in espn_results:
                        if er['fixture']['status']['short'] in ["FT", "Final", "AET"]:
                            e_id = er['fixture']['id']
                            if e_id not in results:
                                results[e_id] = {
                                    "goals": {"home": er['teams']['home']['score'], "away": er['teams']['away']['score']},
                                    "teams": {"home": {"name": er['teams']['home']['name']}, "away": {"name": er['teams']['away']['name']}}
                                }
                    
                    updated_date = False
                    for entry in entries:
                        fid = entry['fid']
                        fix = results.get(fid)
                        
                        if not fix:
                            # Fuzzy matching nomi se l'ID non coincide
                            h_name_entry = entry['m'].split("-")[0].lower() if "-" in entry['m'] else entry['m'].lower()
                            for r_val in results.values():
                                r_h_name = r_val['teams']['home']['name'].lower()
                                if h_name_entry in r_h_name or r_h_name in h_name_entry:
                                    fix = r_val
                                    break
                        
                        if not fix:
                            # Se il match è molto vecchio (>7gg) e non lo troviamo, marchiamolo come perso per non riprocessarlo
                            match_dt = datetime.strptime(date_str, '%Y-%m-%d')
                            if (datetime.now() - match_dt).days > 7:
                                entry['processed'] = True
                                updated_date = True
                            continue
                        
                        gh, ga = fix['goals']['home'], fix['goals']['away']
                        if gh is None or ga is None: continue
                        
                        real_res = "1" if gh > ga else ("2" if gh < ga else "X")
                        entry['real_gh'], entry['real_ga'] = gh, ga
                        pred = str(entry.get('r_pred', 'N/D')).upper()
                        
                        correct = False
                        if pred == real_res: correct = True
                        elif pred == "1X" and real_res in ["1", "X"]: correct = True
                        elif pred == "X2" and real_res in ["X", "2"]: correct = True
                        elif pred == "12" and real_res in ["1", "2"]: correct = True
                        elif pred == "GOL": correct = (gh > 0 and ga > 0)
                        elif pred == "NO GOL": correct = (gh == 0 or ga == 0)
                        elif "OVER" in pred:
                            try: val = float(pred.split()[-1]); correct = (gh + ga) > val
                            except: pass
                        elif "UNDER" in pred:
                            try: val = float(pred.split()[-1]); correct = (gh + ga) < val
                            except: pass
                        
                        # Aggiornamento pesi
                        if correct:
                            if pred in ["1", "X", "2"]:
                                self.weights["w_forma"] = min(0.60, self.weights["w_forma"] + lr)
                                self.weights["w_class"] = min(0.60, self.weights["w_class"] + lr)
                            elif pred in ["1X", "X2", "12"]:
                                self.weights["w_cont"] = min(0.60, self.weights["w_cont"] + lr/2)
                            elif "OVER" in pred or "UNDER" in pred:
                                self.weights["w_uo"] = min(0.80, self.weights["w_uo"] + lr)
                            elif pred in ["GOL", "NO GOL"]:
                                self.weights["w_gg"] = min(0.80, self.weights["w_gg"] + lr)
                        else:
                            if real_res == "2" and ("1" in pred or "1X" in pred):
                                self.weights["w_forma"] = max(0.05, self.weights["w_forma"] - lr)
                                self.weights["w_cont"] = min(0.60, self.weights["w_cont"] + lr)
                            elif real_res == "1" and ("2" in pred or "X2" in pred):
                                self.weights["w_class"] = min(0.60, self.weights["w_class"] + lr)
                                self.weights["w_h2h"] = max(0.05, self.weights["w_h2h"] - lr)
                            elif "OVER" in pred or "UNDER" in pred:
                                self.weights["w_uo"] = max(0.20, self.weights["w_uo"] - lr)
                            elif pred in ["GOL", "NO GOL"]:
                                self.weights["w_gg"] = max(0.20, self.weights["w_gg"] - lr)
                        
                        self.weights["total_analyzed"] = self.weights.get("total_analyzed", 0) + 1
                        if correct: self.weights["correct_predictions"] = self.weights.get("correct_predictions", 0) + 1
                        
                        entry['processed'] = True
                        updated_date = True
                        updated_any = True

                    # Salva ogni 10 date e SINCRONIZZA su GitHub per non perdere dati tra PC
                    if updated_date and (i % 10 == 0 or i == total_dates):
                        self._save_weights()
                        self._safe_write_json(history_file, history)
                        # Sincronizzazione intermedia automatica
                        self.auto_git_sync(f"AI Learning Progress {i}/{total_dates}")
                    
                    # Delay per evitare ban da ESPN/API
                    if i < total_dates: time.sleep(1.5)
                
                if updated_any:
                    total = self.weights.get("total_analyzed", 1)
                    correct = self.weights.get("correct_predictions", 0)
                    acc = (correct / total) * 100
                    print(f"\n{Colors.GREEN}[BG-LEARNING] Apprendimento totale completato! Accuratezza Globale: {acc:.1f}%{Colors.ENDC}")
                    # Sincronizzazione automatica su GitHub a fine apprendimento
                    self.auto_git_sync("AI Learning Complete - Updated weights and history")
                else:
                    print(f"\n{Colors.BLUE}[BG-LEARNING] Analisi terminata. Nessun nuovo risultato trovato.{Colors.ENDC}")
                    
            except Exception as e:
                self._log_error(f"Errore auto-learning: {e}")
            finally:
                self.is_learning = False

        threading.Thread(target=_bg_task, daemon=True).start()
        print(f"\n{Colors.CYAN}[!] Auto-Learning avviato in background.{Colors.ENDC}")
    def start_auto_learning_scheduler(self, interval_sec=900):
        if self._learning_scheduler_started:
            return
        self._learning_scheduler_started = True
        def _loop():
            while True:
                try:
                    time.sleep(interval_sec)
                    self.run_auto_learning()
                except:
                    pass
        threading.Thread(target=_loop, daemon=True).start()
    def show_final_slip(self, preds):
        if not preds:
            print("\nMULTIPLA STRATEGICA: Nessun match con valore trovato oggi.")
            return
        print(f"\nMULTIPLA STRATEGICA (Solo match con Valore)")
        top = sorted(preds, key=lambda x: x['d'], reverse=True)[:4]
        tot_q = 1.0
        for p in top:
            tot_q *= p['q']
            print(f"- {p['m'][:20]:<20} | {p['r']:<10} @{p['q']:.2f}")
        print(f"QUOTA TOTALE: {tot_q:.2f}")
        filename = "pronostici.txt"
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"\n--- SESSIONE {datetime.now().strftime('%Y-%m-%d %H:%M')} ---\n")
            for p in top: f.write(f"{p['m']} -> {p['r']} (@{p['q']:.2f})\n")
            f.write(f"QUOTA TOTALE: {tot_q:.2f}\n")
        print(f"Salvato in {filename}")
        # Salviamo automaticamente anche i TOP se presenti
        self.save_top_pronostici()
    def show_reality(self):
        """
        Modalità REALTA: Mostra il confronto tra pronostici fatti e dati reali aggiornati.
        Ottimizzato per grandi volumi: analizza i match pendenti a blocchi (Paginazione).
        """
        history_file = "history.json"
        history = self._safe_read_json(history_file)
        if not history:
            print("\nNessun dato storico trovato o errore nel caricamento.")
            return
        
        # Filtro intelligente: match non processati (pendenti)
        pending_matches = [h for h in history if not h.get('processed', False)]
        pending_matches.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        total_pending = len(pending_matches)
        if total_pending == 0:
            print(f"\n{Colors.GREEN}[V] Tutti i match sono stati processati dall'IA.{Colors.ENDC}")
            last_processed = [h for h in history if h.get('processed', False)][-50:]
            to_show = last_processed
            start_idx = 0
        else:
            to_show_limit = 100
            start_idx = 0
            
            if total_pending > to_show_limit:
                print(f"\n{Colors.YELLOW}[!] Hai {total_pending} match pendenti.{Colors.ENDC}")
                try:
                    p_input = input(f"Inserisci indice di inizio, o scrivi 'tutti' per processare TUTTI i {total_pending} match (Lento), o premi Invio (ultimi 100): ").strip().lower()
                    if p_input == 'tutti':
                        to_show = pending_matches
                        start_idx = 0
                        to_show_limit = total_pending
                    elif p_input.isdigit():
                        start_idx = max(0, int(p_input) - 1)
                        to_show = pending_matches[start_idx : start_idx + to_show_limit]
                    else:
                        to_show = pending_matches[start_idx : start_idx + to_show_limit]
                except:
                    to_show = pending_matches[start_idx : start_idx + to_show_limit]
            else:
                to_show = pending_matches[start_idx : start_idx + to_show_limit]

        print(f"\n{'='*70}")
        print(f"{'MODALITA REALTA - CONFRONTO PRONOSTICI':^70}")
        if total_pending > 0:
            print(f"{f'Visualizzazione match {start_idx+1} - {min(start_idx+len(to_show), total_pending)} di {total_pending}':^70}")
        print(f"{'='*70}")
        print(f"{'MATCH':<35} | {'PREV':<10} | {'REALE':<6} | {'STATUS'}")
        print(f"{'-'*85}")
        
        dates_to_check = list(set([h['date'] for h in to_show]))
        espn_data = {}
        if dates_to_check:
            print(f"Recupero dati reali per {len(dates_to_check)} date...", end=" ", flush=True)
            for d in dates_to_check:
                espn_data[d] = self.get_espn_fixtures(d, quiet=True, top_only=False)
            print("Fatto.")
        for entry in to_show:
            fid = entry['fid']
            match_name_full = entry['m']
            match_name_display = match_name_full[:35]
            pred = entry['r_pred']
            date_str = entry['date']
            real_res = "???"
            status_label = "PENDING"
            # 1. Prova con API-Sports (se non bloccato)
            if fid and not str(fid).startswith("fd_") and not str(fid).startswith("espn_"):
                match_data = self._get("fixtures", {"id": fid}, use_cache=True)
                if match_data and match_data['response']:
                    fix = match_data['response'][0]
                    status_label = fix['fixture']['status']['short']
                    if status_label == "FT":
                        gh, ga = fix['goals']['home'], fix['goals']['away']
                        real_res = f"{gh}-{ga}"
                        entry['real_gh'] = gh
                        entry['real_ga'] = ga
                    else:
                        gh, ga = fix['goals'].get('home'), fix['goals'].get('away')
                        if gh is not None: real_res = f"Live:{gh}-{ga}"
            # 2. Fallback su ESPN (fondamentale per 2025/2026 piano Free e Sudamerica)
            if real_res == "???" and date_str in espn_data:
                # Usiamo le keywords centralizzate per un matching super robusto
                # Supportiamo sia il vecchio formato 'Home-Away' che il nuovo 'Home vs Away'
                if " vs " in match_name_full:
                    h_name_part = match_name_full.split(" vs ")[0].strip()
                    a_name_part = match_name_full.split(" vs ")[1].strip()
                else:
                    # Per retrocompatibilità, usiamo l'ultimo trattino come separatore
                    parts = match_name_full.split("-")
                    if len(parts) > 2:
                        h_name_part = "-".join(parts[:-1]).strip()
                        a_name_part = parts[-1].strip()
                    elif len(parts) == 2:
                        h_name_part = parts[0].strip()
                        a_name_part = parts[1].strip()
                    else:
                        h_name_part = match_name_full
                        a_name_part = ""
                h_keys = self._get_keywords(h_name_part)
                a_keys = self._get_keywords(a_name_part)
                for ef in espn_data[date_str]:
                    ef_h = ef['teams']['home']['name'].lower()
                    ef_a = ef['teams']['away']['name'].lower()
                    # Matching elastico potenziato: 
                    # 1. Almeno una keyword significativa coincide per squadra
                    # 2. Oppure il nome salvato (anche se troncato) è contenuto nel nome ESPN o viceversa
                    match_h = (any(k in ef_h for k in h_keys) or 
                               h_name_part.lower() in ef_h or 
                               ef_h in h_name_part.lower())
                    match_a = (any(k in ef_a for k in a_keys) or 
                               a_name_part.lower() in ef_a or 
                               ef_a in a_name_part.lower())
                    if match_h and match_a:
                        gh, ga = ef['teams']['home']['score'], ef['teams']['away']['score']
                        st = ef['fixture']['status']['short'] if isinstance(ef['fixture']['status'], dict) else ef['fixture']['status']
                        if st in ["FT", "Final", "AET"]:
                            real_res = f"{gh}-{ga}"
                            status_label = "FT"
                            entry['real_gh'] = gh
                            entry['real_ga'] = ga
                        else:
                            # Se non è finito, distinguiamo tra Live e Programmata
                            st_str = str(st).upper()
                            if any(char.isdigit() for char in st_str) and ":" not in st_str:
                                real_res = f"Live:{gh}-{ga}"
                                status_label = st
                                entry['real_gh'] = gh
                                entry['real_ga'] = ga
                            elif st_str in ["HT", "OT", "LIVE", "1H", "2H"]:
                                real_res = f"Live:{gh}-{ga}"
                                status_label = st
                                entry['real_gh'] = gh
                                entry['real_ga'] = ga
                            else:
                                real_res = "-" # Programmata
                                status_label = st
                        break
            # Calcolo esito
            esito = "..."
            gh_val = entry.get('real_gh')
            ga_val = entry.get('real_ga')
            if gh_val is not None and ga_val is not None:
                if "Live" not in real_res and real_res != "-": real_res = f"{gh_val}-{ga_val}"
                # Risultato attuale (per confronti live)
                curr_res = "1" if gh_val > ga_val else ("2" if gh_val < ga_val else "X")
                correct = False
                if pred == curr_res: correct = True
                elif pred == "1X" and curr_res in ["1", "X"]: correct = True
                elif pred == "X2" and curr_res in ["X", "2"]: correct = True
                elif pred == "12" and curr_res in ["1", "2"]: correct = True
                elif pred == "GOL":
                    correct = (gh_val > 0 and ga_val > 0)
                elif "OVER" in pred:
                    try:
                        val = float(pred.split()[-1])
                        correct = (gh_val + ga_val) > val
                    except: pass
                elif "UNDER" in pred:
                    try:
                        val = float(pred.split()[-1])
                        correct = (gh_val + ga_val) < val
                    except: pass
                if status_label == "FT":
                    esito = "[OK]PRESO" if correct else "[NO]PERSO"
                elif real_res != "-":
                    esito = "[LIVE]VINC" if correct else "[LIVE]PERD"
            print(f"{match_name_display:<25} | {pred:<6} | {real_res:<6} | {esito} ({status_label})")
        # Salvataggio dei risultati aggiornati in history.json
        if self._safe_write_json(history_file, history):
            print(f"\n[!] Cronologia aggiornata con i risultati reali.")
        else:
            print(f"\n[!] Errore nel salvataggio della cronologia.")
        print(f"{'='*70}\n")
    def analyze_league(self, league_key):
        """Analizza i match di una lega specifica per oggi"""
        lid = self.leagues.get(league_key)
        if not lid: return
        print(f"\n{Colors.CYAN}--- ANALISI {league_key.upper().replace('_', ' ')} ---{Colors.ENDC}")
        # Tenta prima con le API professionali (API-Sports o Football-Data)
        fixtures = []
        if self.fd_key and lid in self.fd_league_map:
            fd_code = self.fd_league_map[lid]
            data = self._get_fd(f"competitions/{fd_code}/matches", {"status": "SCHEDULED"})
            if data and 'matches' in data:
                # Convertiamo in formato standard
                for m in data['matches']:
                    fixtures.append({
                        "fixture": {"id": f"fd_{m['id']}", "date": m['utcDate']},
                        "league": {"name": m['competition']['name'], "id": lid},
                        "teams": {
                            "home": {"id": f"fd_{m['homeTeam']['id']}", "name": m['homeTeam']['name']},
                            "away": {"id": f"fd_{m['awayTeam']['id']}", "name": m['awayTeam']['name']}
                        }
                    })
        if not fixtures and not self.api_suspended:
            data = self._get("fixtures", {"league": lid, "season": 2025, "next": 10})
            if data and data.get('response'):
                fixtures = data['response']
        if not fixtures:
            # Fallback su ESPN
            fixtures = self.get_espn_fixtures(datetime.now().strftime('%Y-%m-%d'), quiet=True)
            fixtures = [f for f in fixtures if f['league']['id'] == lid]
        if fixtures:
            self.analyze_match_list(fixtures, f"MATCH {league_key.upper()}")
        else:
            print("Nessun match trovato per questa competizione oggi.")
    def analyze_csv_future_matches(self):
        """
        Scansiona TUTTI i file CSV e analizza ogni match che non ha ancora un risultato.
        Sblocca la logica operativa per ogni partita presente nel database locale.
        """
        print(f"\n{Colors.CYAN}--- ANALISI MATCH FUTURI (CSV/ESPN/DIRETTA) ---{Colors.ENDC}")
        all_future_fixtures = []
        for f_name in os.listdir("."):
            if f_name.endswith(".csv"):
                league_code = f_name.replace(".csv", "")
                data = self._get_csv(league_code)
                if not data or not data.get('response'): continue
                count_in_file = 0
                for m in data['response']:
                    # Un match è futuro se non ha gol o se la data è >= oggi
                    gh = m.get('goals', {}).get('home')
                    ga = m.get('goals', {}).get('away')
                    # In football-data.co.uk CSV, i match senza risultato hanno spesso celle vuote 
                    # che il DictReader carica come None o stringa vuota.
                    # _get_csv li inizializza a 0 se non presenti, quindi dobbiamo essere precisi.
                    # Verifichiamo se nel CSV originale le colonne FTHG/FTAG sono popolate.
                    is_pending = True if gh is None or ga is None else False
                    try:
                        d_str = m['fixture']['date']
                        if d_str:
                            # Formati comuni: DD/MM/YY o YYYY-MM-DD
                            if '-' in d_str:
                                dt = datetime.strptime(d_str, '%Y-%m-%d')
                            else:
                                try:
                                    dt = datetime.strptime(d_str, '%d/%m/%Y')
                                except:
                                    dt = datetime.strptime(d_str, '%d/%m/%y')
                            if dt.date() >= datetime.now().date():
                                is_pending = True
                            else:
                                if gh is None or ga is None:
                                    is_pending = True
                    except:
                        pass
                    if is_pending:
                        # Costruiamo l'oggetto fixture compatibile con analyze_match_list
                        fix = {
                            "fixture": {
                                "id": f"csv_{m['teams']['home']['name']}_{m['fixture']['date']}",
                                "date": m['fixture']['date'],
                                "status": {"short": "NS"}
                            },
                            "league": {"name": league_code, "id": 0},
                            "teams": {
                                "home": m['teams']['home'],
                                "away": m['teams']['away']
                            }
                        }
                        all_future_fixtures.append(fix)
                        count_in_file += 1
                if count_in_file > 0:
                    print(f"  [CSV] Trovati {count_in_file} match futuri in {f_name}")
        if all_future_fixtures:
            print(f"\n[!] Avvio analisi di {len(all_future_fixtures)} match futuri trovati nei CSV...")
            self.analyze_match_list(all_future_fixtures, "CSV FUTURE ANALYSIS")
        else:
            print("\n[!] Nessun match futuro trovato nei file CSV. Uso ESPN + Diretta per i prossimi giorni...")
            gathered = []
            seen = set()
            for off in [0, 1, 2, 3, 4, 5, 6, 7]:
                d = (datetime.now() + timedelta(days=off)).strftime('%Y-%m-%d')
                if not self.api_suspended:
                    try:
                        api_f = self._get("fixtures", {"date": d, "status": "NS"}, use_cache=True)
                        if api_f and api_f.get('response'):
                            for fx in api_f['response']:
                                h_n = fx['teams']['home']['name'].lower()
                                a_n = fx['teams']['away']['name'].lower()
                                key = f"{h_n}-{a_n}-{fx['fixture']['date'][:10]}"
                                if key not in seen:
                                    gathered.append(fx)
                                    seen.add(key)
                    except:
                        pass
                try:
                    for fx in self.get_espn_fixtures(d, quiet=True, top_only=False):
                        key = f"{fx['teams']['home']['name'].lower()}-{fx['teams']['away']['name'].lower()}-{fx['fixture']['date'][:10]}"
                        if key not in seen:
                            gathered.append(fx)
                            seen.add(key)
                except:
                    pass
                try:
                    for m in self.diretta.get_matches(day_offset=off):
                        key = f"{m.get('home','').lower()}-{m.get('away','').lower()}-{datetime.fromtimestamp(m['time'], tz=timezone.utc).date().isoformat()}"
                        if key in seen:
                            continue
                        seen.add(key)
                        gathered.append({
                            "fixture": {"id": f"d_{m['id']}", "date": datetime.fromtimestamp(m['time'], tz=timezone.utc).isoformat(), "status": {"short": "NS"}},
                            "league": {"name": m.get('league', ''), "id": 0},
                            "teams": {"home": {"name": m.get('home', ''), "id": f"csv_{m.get('home', '')}"}, "away": {"name": m.get('away', ''), "id": f"csv_{m.get('away', '')}"}}
                        })
                except:
                    pass
            if gathered:
                self._interactive_pick_and_analyze(gathered, title="FUTURI (ESPN/DIRETTA)")
            else:
                print("[!] Nessun match futuro trovato anche su ESPN/Diretta.")
    def analyze_team_matches(self, team_name):
        """Analizza i prossimi match di una squadra specifica"""
        t_info = self.search_team(team_name)
        if t_info:
            print(f"Analisi per {t_info['name']} (ID: {t_info['id']})...")
            # Tenta di trovare il prossimo match
            fixtures = []
            if not self.api_suspended and not str(t_info['id']).startswith("fd_") and not str(t_info['id']).startswith("csv_"):
                data = self._get("fixtures", {"team": t_info['id'], "next": 5})
                if data and data.get('response'):
                    fixtures = data['response']
            if not fixtures:
                # Fallback su Diretta/ESPN
                all_m = self.get_espn_fixtures(datetime.now().strftime('%Y-%m-%d'), quiet=True)
                all_m += self.get_espn_fixtures((datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'), quiet=True)
                for m in all_m:
                    if team_name.lower() in m['teams']['home']['name'].lower() or team_name.lower() in m['teams']['away']['name'].lower():
                        fixtures.append(m)
            if fixtures:
                self.analyze_match_list(fixtures, f"MATCH PER {t_info['name'].upper()}")
            else:
                print(f"Nessun match imminente trovato per {t_info['name']}.")
        else:
            print(f"Squadra '{team_name}' non trovata.")
    def analyze_tomorrow(self):
        """Analizza tutti i match di domani"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"\n{Colors.CYAN}--- ANALISI MATCH DI DOMANI ({tomorrow}) ---{Colors.ENDC}")
        fixtures = self.get_espn_fixtures(tomorrow, quiet=False)
        if fixtures:
            self.analyze_match_list(fixtures, "DOMANI")
        else:
            print("Nessun match trovato per domani.")
    def analyze_all_matches(self):
        """Analizza tutti i match di oggi da più fonti"""
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"\n{Colors.CYAN}--- ANALISI COMPLETA OGGI ({today}) ---{Colors.ENDC}")
        fixtures = self.get_espn_fixtures(today, quiet=False, top_only=False)
        if fixtures:
            self.analyze_match_list(fixtures, "LISTA COMPLETA OGGI")
        else:
            print("Nessun match trovato per oggi.")
    def _interactive_pick_and_analyze(self, fixtures, title="MATCH TROVATI"):
        if not fixtures:
            print("Nessun match trovato.")
            return
        fixtures = sorted(fixtures, key=lambda x: x.get('fixture', {}).get('date', ''))
        print(f"\n--- {title} ({len(fixtures)}) ---")
        for i, f in enumerate(fixtures[:120]):
            dt_str = f.get('fixture', {}).get('date', '')
            try:
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00')).astimezone()
                when = dt.strftime('%d/%m %H:%M')
            except:
                when = dt_str[:16]
            h_n = f.get('teams', {}).get('home', {}).get('name', 'Home')
            a_n = f.get('teams', {}).get('away', {}).get('name', 'Away')
            l_n = (f.get('league', {}) or {}).get('name', '')
            print(f"{i+1:3d}. {when:<11} | {l_n[:16]:<16} | {h_n[:24]:<24} vs {a_n[:24]:<24}")
        sel = input("\nScegli (es: 1,3 o 'tutti' o 0): ").strip().lower()
        if sel in ["0", ""]: 
            return
        selected = []
        if sel == "tutti":
            selected = fixtures[:50]
        else:
            for part in sel.split(','):
                if part.strip().isdigit():
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(fixtures):
                        selected.append(fixtures[idx])
        if selected:
            self.analyze_match_list(selected, title)
    def search_matches_intelligent(self, query, day_offsets=None):
        q = (query or "").strip()
        if not q:
            return []
        if day_offsets is None:
            day_offsets = [-1, 0, 1, 2]
        q_low = q.lower()
        t1 = None
        t2 = None
        if "," in q_low:
            parts = [p.strip() for p in q_low.split(",") if p.strip()]
            if len(parts) >= 1: t1 = parts[0]
            if len(parts) >= 2: t2 = parts[1]
        elif " vs " in q_low:
            parts = [p.strip() for p in q_low.split(" vs ") if p.strip()]
            if len(parts) >= 2:
                t1, t2 = parts[0], parts[1]
        else:
            parts = q_low.split()
            if len(parts) >= 2:
                t1, t2 = parts[0], parts[1]
            else:
                t1 = q_low
        k1 = self._get_keywords(t1) if t1 else []
        k2 = self._get_keywords(t2) if t2 else []
        found = []
        seen = set()
        def _add_fix(fx):
            dt = (fx.get('fixture', {}) or {}).get('date', '')[:16]
            h_n = (fx.get('teams', {}).get('home', {}) or {}).get('name', '').lower()
            a_n = (fx.get('teams', {}).get('away', {}) or {}).get('name', '').lower()
            key = f"{h_n}-{a_n}-{dt}"
            if key in seen:
                return
            seen.add(key)
            found.append(fx)
        for off in day_offsets:
            try:
                d = (datetime.now() + timedelta(days=off)).strftime('%Y-%m-%d')
                for fx in self.get_espn_fixtures(d, quiet=True, top_only=False):
                    h_n = fx['teams']['home']['name'].lower()
                    a_n = fx['teams']['away']['name'].lower()
                    ok1 = any(k in h_n or k in a_n for k in k1) if k1 else False
                    ok2 = True
                    if k2:
                        ok2 = any(k in h_n or k in a_n for k in k2)
                    if ok1 and ok2:
                        _add_fix(fx)
            except:
                pass
            try:
                for m in self.diretta.get_matches(day_offset=off):
                    h_n = m.get('home', '').lower()
                    a_n = m.get('away', '').lower()
                    ok1 = any(k in h_n or k in a_n for k in k1) if k1 else False
                    ok2 = True
                    if k2:
                        ok2 = any(k in h_n or k in a_n for k in k2)
                    if ok1 and ok2:
                        fix = {
                            "fixture": {"id": f"d_{m['id']}", "date": datetime.fromtimestamp(m['time'], tz=timezone.utc).isoformat(), "status": {"short": "NS"}},
                            "league": {"name": m.get('league', ''), "id": 0},
                            "teams": {"home": {"name": m.get('home', ''), "id": f"csv_{m.get('home', '')}"}, "away": {"name": m.get('away', ''), "id": f"csv_{m.get('away', '')}"}}
                        }
                        _add_fix(fix)
            except:
                pass
        return found
    def handle_favorites_management(self):
        """Gestione della lista dei campionati preferiti"""
        print(f"\n{Colors.BLUE}--- GESTIONE CAMPIONATI PREFERITI ---{Colors.ENDC}")
        print(f"Preferiti attuali: {', '.join(self.favorites)}")
        print("\n1. AGGIUNGI | 2. RIMUOVI | 0. TORNA")
        choice = input("Scegli: ").strip()
        
        if choice == "1":
            print("\nCampionati disponibili (ID):")
            for name, fid in self.leagues.items():
                print(f"- {name} (ID: {fid})")
            new_fav = input("\nInserisci nome campionato da aggiungere: ").strip().lower()
            if new_fav in self.leagues and new_fav not in self.favorites:
                self.favorites.append(new_fav)
                self._save_favorites()
                print(f"'{new_fav}' aggiunto ai preferiti.")
            else:
                print("Campionato non trovato o già presente.")
        elif choice == "2":
            rem_fav = input("\nInserisci nome campionato da rimuovere: ").strip().lower()
            if rem_fav in self.favorites:
                self.favorites.remove(rem_fav)
                self._save_favorites()
                print(f"'{rem_fav}' rimosso dai preferiti.")
            else:
                print("Campionato non trovato nei preferiti.")

    def handle_quick_league_menu(self):
        """Menu rapido per i campionati preferiti con selezione data"""
        print(f"\n{Colors.CYAN}--- ANALISI VELOCE (PREFERITI) ---{Colors.ENDC}")
        print(" | ".join([f"{i+1}. {fav.upper()}" for i, fav in enumerate(self.favorites)]) + " | t. TUTTI | 0. TORNA")
        
        choice = input("\nScegli campionati (es. 1,2 o t): ").strip().lower()
        if choice == '0': return
        
        selected = []
        if choice == 't':
            selected = self.favorites
        else:
            for part in choice.split(','):
                if part.strip().isdigit():
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(self.favorites):
                        selected.append(self.favorites[idx])
        
        if selected:
            print("\nSeleziona Data:")
            print("y. IERI | t. OGGI | m. DOMANI | d. DOPODOMANI | a. TUTTE | 0. ANNULLA")
            d_choice = input("Scelta data: ").strip().lower()
            if d_choice == '0': return
            
            days = []
            if d_choice == 'y': days = [-1]
            elif d_choice == 't': days = [0]
            elif d_choice == 'm': days = [1]
            elif d_choice == 'd': days = [2]
            elif d_choice == 'a': days = [-1, 0, 1, 2]
            else: days = [0] # Default oggi
            
            for d_off in days:
                for league in selected:
                    self.analyze_league(league, day_offset=d_off)

    def analyze_diretta_today(self, quiet=True):
        """Analisi automatica e silenziosa dei match di oggi da Diretta.it"""
        if not quiet: print(f"\n{Colors.CYAN}[AUTO] Scansione Diretta.it (Match di Oggi)...{Colors.ENDC}")
        matches = self.diretta.get_matches(day_offset=0)
        if not matches: return
        
        top_leagues_white = ["italia: serie a", "italia: serie b", "inghilterra: premier league", "spagna: laliga", "germania: bundesliga", "francia: ligue 1", "europa: champions league", "europa: europa league", "europa: conference league"]
        filtered = [m for m in matches if any(m['league'].lower().startswith(tl) for tl in top_leagues_white)]
        
        if filtered:
            to_analyze = []
            for sm in filtered:
                fake_f = {
                    "teams": {"home": {"name": sm['home']}, "away": {"name": sm['away']}},
                    "league": {"name": sm['league']},
                    "fixture": {"id": sm['id'], "date": datetime.fromtimestamp(sm['time'], tz=timezone.utc).isoformat(), "status": "NS"}
                }
                api_match = self.find_api_sports_fixture(fake_f)
                if api_match: to_analyze.append(api_match)
                else:
                    hybrid_fix = {
                        "fixture": {"id": f"d_{sm['id']}", "date": datetime.fromtimestamp(sm['time'], tz=timezone.utc).isoformat(), "status": "NS"},
                        "league": {"name": sm['league'], "id": 0},
                        "teams": {"home": {"name": sm['home'], "id": f"csv_{sm['home']}"}, "away": {"name": sm['away'], "id": f"csv_{sm['away']}"}}
                    }
                    to_analyze.append(hybrid_fix)
            if to_analyze: self.analyze_match_list(to_analyze, "DIRETTA.IT AUTO-TODAY")

    def run_champion_routine(self):
        """Esegue la sequenza automatica completa all'avvio (Routine del Campione)"""
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'AVVIO ROUTINE DEL CAMPIONE (10, 4.4, 3, 6, 5)':^60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
        
        # 0. Aggiornamento Database (5)
        print(f"\n{Colors.BOLD}[0/5] Aggiornamento Database Storico (UK-DATA)...{Colors.ENDC}")
        self.update_all_csv_databases()

        # 1. Realtà & Auto-Learning (10)
        print(f"\n{Colors.BOLD}[1/5] Verifica Realtà & Stato AI...{Colors.ENDC}")
        self.show_reality()
        
        # 2. Analisi CSV (4.4)
        print(f"\n{Colors.BOLD}[2/5] Analisi Database CSV (Match Futuri)...{Colors.ENDC}")
        self.analyze_csv_future_matches()
        
        # 3. Analisi Fonti Esterne (API + Diretta + ESPN/GitHub) (3)
        print(f"\n{Colors.BOLD}[3/5] Analisi Fonti Esterne (ESPN + Diretta + API)...{Colors.ENDC}")
        # ESPN (La fonte "Free da GitHub/Web")
        self.analyze_all_matches() 
        # Diretta.it
        self.analyze_diretta_today()
        
        # 4. Top Pronostici (6)
        print(f"\n{Colors.BOLD}[4/5] Esportazione TOP PRONOSTICI...{Colors.ENDC}")
        self.save_top_pronostici()
        
        print(f"\n{Colors.GREEN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.GREEN}{'ROUTINE COMPLETATA - SMART BRAIN AI PRONTO':^60}{Colors.ENDC}")
        print(f"{Colors.GREEN}{'='*60}{Colors.ENDC}")

    def handle_diretta_menu(self):
        """Gestisce il sottomenu di Diretta.it"""
        print(f"\n{Colors.CYAN}--- DIRETTA.IT (FLASH SCORE) ---{Colors.ENDC}")
        print("1. IERI | 2. OGGI | 3. DOMANI | 4. DOPODOMANI | t. TUTTI | 0. TORNA")
        raw_sel = input("Scegli giorni: ").strip().lower()
        if raw_sel == '0': return
        d_choices = [raw_sel] if raw_sel == 't' else raw_sel.split(',')
        all_selected_matches = []
        day_map = {"1": -1, "2": 0, "3": 1, "4": 2}
        offsets = [-1, 0, 1, 2] if raw_sel == 't' else []
        if not offsets:
            for dc in d_choices:
                if dc.strip() in day_map: offsets.append(day_map[dc.strip()])
        for offset in offsets:
            day_matches = self.diretta.get_matches(day_offset=offset)
            if day_matches:
                all_selected_matches.extend(day_matches)
        if not all_selected_matches:
            print("Nessun match trovato su Diretta.it per le date selezionate.")
            return
        seen_ids = set()
        d_matches_all = []
        for m in all_selected_matches:
            if m['id'] not in seen_ids:
                d_matches_all.append(m)
                seen_ids.add(m['id'])
        print(f"\nFiltra per ({len(d_matches_all)} match totali):")
        print("1. TOP LEAGUES | 2. RICERCA | 3. TUTTI | 0. TORNA")
        f_choice = input("Scegli: ").strip()
        if f_choice == '0': return
        d_matches = []
        if f_choice == "1":
            top_leagues_white = ["italia: serie a", "italia: serie b", "inghilterra: premier league", "spagna: laliga", "germania: bundesliga", "francia: ligue 1", "europa: champions league", "europa: europa league", "europa: conference league"]
            for m in d_matches_all:
                if any(m['league'].lower().startswith(tl) for tl in top_leagues_white):
                    d_matches.append(m)
        elif f_choice == "2":
            q = input("Parola chiave: ").lower().strip()
            for m in d_matches_all:
                if q in m['home'].lower() or q in m['away'].lower() or q in m['league'].lower():
                    d_matches.append(m)
        else:
            d_matches = d_matches_all
        if not d_matches:
            print("Nessun match trovato.")
            return
        print(f"\n--- MATCH TROVATI ({len(d_matches)}) ---")
        for i, m in enumerate(d_matches[:100]):
            has_odds_str = "SÌ" if m.get('has_odds') else "NO"
            print(f"{i+1:3d}. {m['league'][:20]:<20} | {m['home']:<25} vs {m['away']:<25} (Odds: {has_odds_str})")
        sel = input("\nScegli match (es: 1,3 o 'tutti'): ").strip().lower()
        selected = []
        if sel == 'tutti': selected = d_matches[:50]
        elif sel:
            for part in sel.split(','):
                if part.strip().isdigit():
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(d_matches): selected.append(d_matches[idx])
        if selected:
            to_analyze = []
            for sm in selected:
                fake_f = {
                    "teams": {"home": {"name": sm['home']}, "away": {"name": sm['away']}},
                    "league": {"name": sm['league']},
                    "fixture": {"id": sm['id'], "date": datetime.fromtimestamp(sm['time'], tz=timezone.utc).isoformat(), "status": "NS"}
                }
                print(f"\n[Analisi] Elaborazione {sm['home']} vs {sm['away']}...")
                api_match = self.find_api_sports_fixture(fake_f)
                if api_match: to_analyze.append(api_match)
                else:
                    hybrid_fix = {
                        "fixture": {"id": f"d_{sm['id']}", "date": datetime.fromtimestamp(sm['time'], tz=timezone.utc).isoformat(), "status": "NS"},
                        "league": {"name": sm['league'], "id": 0},
                        "teams": {"home": {"name": sm['home'], "id": f"csv_{sm['home']}"}, "away": {"name": sm['away'], "id": f"csv_{sm['away']}"}}
                    }
                    to_analyze.append(hybrid_fix)
            if to_analyze: self.analyze_match_list(to_analyze, "DIRETTA.IT SELECTION")
    def handle_interactive_date_analysis(self):
        """
        Nuova funzione per scegliere giorni, visualizzare match filtrati e analizzare selettivamente.
        """
        print(f"\n{Colors.CYAN}--- ANALISI SELETTIVA PER DATA ---{Colors.ENDC}")
        print("Scegli i giorni (es: 1,2 per oggi e domani):")
        print("1. IERI | 2. OGGI | 3. DOMANI | 4. DOPODOMANI | 5. SETTIMANA | 0. TORNA")
        
        d_input = input("Scegli: ").strip().lower()
        if not d_input or d_input == '0': return
        
        day_map = {"1": -1, "2": 0, "3": 1, "4": 2}
        offsets = []
        if d_input == '5':
            offsets = [0, 1, 2, 3, 4, 5, 6]
        else:
            for part in d_input.split(','):
                if part.strip() in day_map:
                    offsets.append(day_map[part.strip()])
        
        if not offsets: return
        
        print(f"\n{Colors.BLUE}[...] Recupero match in corso...{Colors.ENDC}")
        all_matches = []
        seen_ids = set()
        
        # Filtro leghe preferite dell'utente
        top_leagues = [
            "italia: serie a", "italia: serie b", 
            "inghilterra: premier league", "inghilterra: championship",
            "spagna: laliga", "spagna: laliga2",
            "germania: bundesliga", "germania: 2. bundesliga",
            "francia: ligue 1", "francia: ligue 2",
            "europa: champions league", "europa: europa league", "europa: conference league",
            "olanda: eredivisie", "portogallo: liga portugal"
        ]
        
        for offset in offsets:
            day_matches = self.diretta.get_matches(day_offset=offset)
            for m in day_matches:
                m_id = m['id']
                if m_id not in seen_ids:
                    # Priorità ai campionati top
                    is_top = any(m['league'].lower().startswith(tl) for tl in top_leagues)
                    m['is_top'] = is_top
                    all_matches.append(m)
                    seen_ids.add(m_id)
        
        # Ordiniamo: prima i top leagues, poi il resto
        all_matches.sort(key=lambda x: (not x['is_top'], x['league'], x['time']))
        
        if not all_matches:
            print(f"{Colors.RED}[!] Nessun match trovato per le date selezionate.{Colors.ENDC}")
            return

        print(f"\n{Colors.BOLD}--- LISTA MATCH DISPONIBILI ({len(all_matches)}) ---{Colors.ENDC}")
        print(f"{'ID':<4} | {'CAMPIONATO':<20} | {'PARTITA':<45} | {'DATA'}")
        print("-" * 85)
        
        for i, m in enumerate(all_matches[:150]): # Mostriamo max 150 per leggibilità
            dt = datetime.fromtimestamp(m['time'], tz=timezone.utc).strftime('%d/%m %H:%M')
            color = Colors.GREEN if m['is_top'] else ""
            reset = Colors.ENDC if m['is_top'] else ""
            print(f"{i+1:3d}. | {color}{m['league'][:20]:<20}{reset} | {color}{m['home']:<20} vs {m['away']:<20}{reset} | {dt}")

        print(f"\n{Colors.CYAN}Opzioni: 'tutti', 'top' (solo verdi), oppure numeri separati da virgola (es: 1,5,12).{Colors.ENDC}")
        sel = input("Scegli: ").strip().lower()
        
        selected_matches = []
        if sel == 'tutti':
            selected_matches = all_matches[:50] # Cap di sicurezza
        elif sel == 'top':
            selected_matches = [m for m in all_matches if m['is_top']][:50]
        elif sel:
            for part in sel.split(','):
                try:
                    idx = int(part.strip()) - 1
                    if 0 <= idx < len(all_matches):
                        selected_matches.append(all_matches[idx])
                except: continue
        
        if not selected_matches:
            print("Operazione annullata.")
            return
            
        print(f"\n{Colors.GREEN}[!] Analisi avviata per {len(selected_matches)} match...{Colors.ENDC}")
        to_analyze = []
        for sm in selected_matches:
            # Creiamo il formato fixture richiesto dal motore
            fake_f = {
                "teams": {"home": {"name": sm['home']}, "away": {"name": sm['away']}},
                "league": {"name": sm['league']},
                "fixture": {"id": sm['id'], "date": datetime.fromtimestamp(sm['time'], tz=timezone.utc).isoformat(), "status": "NS"}
            }
            # Cerchiamo se esiste su API-Sports per dati più ricchi, altrimenti usiamo dati ibridi
            api_match = self.find_api_sports_fixture(fake_f)
            if api_match:
                to_analyze.append(api_match)
            else:
                hybrid_fix = {
                    "fixture": {"id": f"d_{sm['id']}", "date": fake_f["fixture"]["date"], "status": "NS"},
                    "league": {"name": sm['league'], "id": 0},
                    "teams": {"home": {"name": sm['home'], "id": f"csv_{sm['home']}"}, "away": {"name": sm['away'], "id": f"csv_{sm['away']}"}}
                }
                to_analyze.append(hybrid_fix)
        
        if to_analyze:
            self.analyze_match_list(to_analyze, f"SELEZIONE UTENTE ({len(to_analyze)} MATCH)")
if __name__ == "__main__":
    # Token Football-Data.org (Attivo e Funzionante)
    FD_KEY = "39df5a49a6764a999a9b14cafc9ca111"
    # Token API-Sports (Sospeso - Usato solo come fallback se riattivato)
    API_KEY = "c5d860df8229a7ad907688ad36a7693a"
    p = FootballPredictor(API_KEY, fd_key=FD_KEY)
    # Sincronizzazione iniziale con GitHub (Pull) per avere i dati aggiornati da altri PC
    p.auto_git_sync("Startup Sync", pull=True)
    # Esegui Pulizia Cache all'avvio (veloce)
    p.clean_cache(days=30)
    # Verifica stato dei Token e avvio Auto-Learning in BACKGROUND
    print(f"\n{Colors.CYAN}--- SMART BRAIN AI: FOOTBALL PREDICTOR PRO ---{Colors.ENDC}")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    # Avvio automatico in background dell'apprendimento
    p.run_auto_learning()
    p.start_auto_learning_scheduler(interval_sec=900)
    # Verifica stato dei Token (mentre il thread gira)
    fd_status = p._get_fd("competitions")
    api_status = p._get("status")
    status_msg = []
    if fd_status: status_msg.append(f"FD.org: {Colors.GREEN}OK{Colors.ENDC}")
    else: status_msg.append(f"FD.org: {Colors.RED}KO{Colors.ENDC}")
    if api_status: status_msg.append(f"API-Sports: {Colors.GREEN}OK{Colors.ENDC}")
    else: status_msg.append(f"API-Sports: {Colors.YELLOW}Sospeso (Fallback){Colors.ENDC}")
    print(f"Sistemi: {' | '.join(status_msg)}")
    
    while True:
        print(f"\n{Colors.BOLD}{Colors.CYAN}--- SMART BRAIN AI: FOOTBALL PREDICTOR PRO ---{Colors.ENDC}")
        print(f"{Colors.GREEN}1. ANALISI MATCH (Selettiva/Data){Colors.ENDC} | {Colors.YELLOW}2. CERCA SQUADRA/MATCH{Colors.ENDC}")
        print(f"{Colors.BLUE}3. REALTÀ & AUTO-LEARN{Colors.ENDC}         | {Colors.PURPLE}4. TOP PRONOSTICI & ROUTINE{Colors.ENDC}")
        print(f"5. UTILITY & DB (UK)             | 0. ESCI")
        
        raw_input = input("\nScegli: ").strip().lower()
        if not raw_input or raw_input == "0" or raw_input == "exit": break
        
        choices = [c.strip() for c in raw_input.split(',')]
        for main_choice in choices:
            if main_choice == "1":
                p.handle_interactive_date_analysis()
            elif main_choice == "2":
                print(f"\n{Colors.BLUE}--- RICERCA & ANALISI ---{Colors.ENDC}")
                print("1. SQUADRA | 2. MATCH SINGOLO | 3. LISTA ESPN (Tutti) | 0. TORNA")
                rc = input("Scegli: ").strip().lower()
                if rc == '1':
                    team = input("Nome squadra: ").strip()
                    if team: p.analyze_team_matches(team)
                elif rc == '2':
                    q = input("Cerca match (es: 'Inter Milan'): ").strip()
                    if q:
                        m = p.find_match_anywhere(q)
                        if not m: m = p.search_matches_intelligent(q, day_offsets=[-1, 0, 1, 2])
                        if m: p._interactive_pick_and_analyze(m, title=f"RISULTATI PER: {q}")
                elif rc == '3':
                    p.analyze_all_matches()
            elif main_choice == "3":
                print(f"\n{Colors.YELLOW}--- AI & REALTÀ ---{Colors.ENDC}")
                print("1. MOSTRA REALTÀ (Risultati) | 2. AUTO-LEARN (Background) | 0. TORNA")
                ac = input("Scegli: ").strip().lower()
                if ac == '1': p.show_reality()
                elif ac == '2': p.run_auto_learning(manual=True)
            elif main_choice == "4":
                print(f"\n{Colors.PURPLE}--- TOP & ROUTINE ---{Colors.ENDC}")
                print("1. SALVA TOP PRONOSTICI | 2. ESEGUI ROUTINE COMPLETA (9) | 0. TORNA")
                tc = input("Scegli: ").strip().lower()
                if tc == '1': p.save_top_pronostici()
                elif tc == '2': p.run_champion_routine()
            elif main_choice == "5":
                print(f"\n{Colors.CYAN}--- UTILITY & DB ---{Colors.ENDC}")
                print("1. AGGIORNA DB UK (CSV) | 2. PULIZIA CACHE | 3. ANALISI STORICA | 0. TORNA")
                uc = input("Scegli: ").strip().lower()
                if uc == '1': p.update_all_csv_databases()
                elif uc == '2': p.clean_cache(days=1)
                elif uc == '3':
                    days = input("Giorni indietro: ").strip()
                    if days.isdigit(): p.analyze_past_days(int(days))
        print("\n" + "-"*30)
