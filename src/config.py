import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- RUTAS DE PROYECTO ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUT_DIR = BASE_DIR / "output"

HISTORY_PARQUET = PROCESSED_DATA_DIR / "history_with_xg.parquet"
UPCOMING_PARQUET = PROCESSED_DATA_DIR / "upcoming_fixtures.parquet"

OUTPUT_CSV = OUTPUT_DIR / "value_bets.csv"
OUTPUT_HTML = OUTPUT_DIR / "dashboard.html"
OUTPUT_JSON = OUTPUT_DIR / "predictions.json"

# --- SECRETOS Y APIS ---
API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

BASE_URL = "https://api.football-data.org/v4"
ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4/sports"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- MODELO Y EVALUACIÓN ---
DEFAULT_RHO = -0.13
DEFAULT_MIN_TRAIN_MATCHES = 200
RECENT_MATCHES = 10
DECAY_FACTOR = 0.0025
HOME_ADVANTAGE = 1.12
VALIDATION_THRESHOLD = 0.25

SEASON_WEIGHTS = {
    "2025": 1.0,
    "2024": 0.5
}

# --- LIGAS Y TEMPORADAS ---
LEAGUES = {
    "PL":  "Premier League (Inglaterra)",
    "PD":  "LaLiga (España)",
    "BL1": "Bundesliga (Alemania)",
    "FL1": "Ligue 1 (Francia)",
    "DED": "Eredivisie (Países Bajos)",
    "PPL": "Primeira Liga (Portugal)",
    "SA":  "Serie A (Italia)",
    "CL":  "UEFA Champions League",
}

# Lista de ligas para evaluación Walk-Forward (excluye Champions)
EVAL_LEAGUES = ["FL1", "PL", "PD", "PPL", "DED", "BL1", "SA"]
DEFAULT_SEASONS = [2023, 2024, 2025]

EXTRA_LEAGUES_CSV = {
    "PL_2526":  "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
    "PD_2526":  "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "BL1_2526": "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "FL1_2526": "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "SA_2526":  "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "DED_2526": "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "PPL_2526": "https://www.football-data.co.uk/mmz4281/2526/P1.csv",

    "PL_2425":  "https://www.football-data.co.uk/mmz4281/2425/E0.csv",
    "PD_2425":  "https://www.football-data.co.uk/mmz4281/2425/SP1.csv",
    "BL1_2425": "https://www.football-data.co.uk/mmz4281/2425/D1.csv",
    "FL1_2425": "https://www.football-data.co.uk/mmz4281/2425/F1.csv",
    "SA_2425":  "https://www.football-data.co.uk/mmz4281/2425/I1.csv",
    "DED_2425": "https://www.football-data.co.uk/mmz4281/2425/N1.csv",
    "PPL_2425": "https://www.football-data.co.uk/mmz4281/2425/P1.csv",

    "PL_2324":  "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
    "PD_2324":  "https://www.football-data.co.uk/mmz4281/2324/SP1.csv",
    "BL1_2324": "https://www.football-data.co.uk/mmz4281/2324/D1.csv",
    "FL1_2324": "https://www.football-data.co.uk/mmz4281/2324/F1.csv",
    "SA_2324":  "https://www.football-data.co.uk/mmz4281/2324/I1.csv",
    "DED_2324": "https://www.football-data.co.uk/mmz4281/2324/N1.csv",
    "PPL_2324": "https://www.football-data.co.uk/mmz4281/2324/P1.csv",
}

SEASONS = ["2024", "2025"]

# --- FILTROS DE APUESTAS ---
FILTERS_CONSERVATIVE = {
    "MIN_EV":         0.08,
    "MAX_EV":         99.0,
    "MIN_PROB_MODEL": 0.10,
    "MIN_ODDS":       1.50,
    "MAX_ODDS":       8.00,
}

ACTIVE_FILTERS = FILTERS_CONSERVATIVE
MIN_EV         = ACTIVE_FILTERS["MIN_EV"]
MAX_EV         = ACTIVE_FILTERS["MAX_EV"]
MIN_PROB_MODEL = ACTIVE_FILTERS["MIN_PROB_MODEL"]
MIN_ODDS       = ACTIVE_FILTERS["MIN_ODDS"]
MAX_ODDS       = ACTIVE_FILTERS["MAX_ODDS"]

# Regla óptima de producción para 1X2 Draw
DRAW_FILTER_CONFIG = {
    "ev_min": 0.08,
    "max_odds": 3.80,
    "market": "1X2 Draw"
}

# --- CONFIGURACIÓN DE PRODUCCIÓN ---
# Ligas con edge validado en backtest (CLV y yield positivos).
# PL: +19.9% yield | BL1: +18.9% yield | Resto: sin edge o negativo.
# El bot sigue enviando alertas de todas las ligas, pero solo estas
# se etiquetan como PICK con stake sugerido.
PRODUCTION_LEAGUES = ["PL", "BL1"]

# --- ODDS API ---
ODDS_API_SPORT_KEYS = {
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "BL1": "soccer_germany_bundesliga",
    "FL1": "soccer_france_ligue_one",
    "DED": "soccer_netherlands_eredivisie",
    "PPL": "soccer_portugal_primeira_liga",
    "SA":  "soccer_italy_serie_a",
    "CL":  "soccer_uefa_champs_league",
}

PREFERRED_BOOKMAKER = "onexbet"
ODDS_UPDATE_INTERVAL_HOURS = 3
ODDS_DB_PATH = "data/processed/odds_snapshots.db"