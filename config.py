API_KEY = "03b862d9fa1146f1b977153267df8322"
BASE_URL = "https://api.football-data.org/v4"

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

EXTRA_LEAGUES_CSV = {
        # ── Temporada ACTUAL 2025-26 ──────────────────────────────
    "PL_2526":  "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
    "PD_2526":  "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "BL1_2526": "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "FL1_2526": "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "SA_2526":  "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "DED_2526": "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "PPL_2526": "https://www.football-data.co.uk/mmz4281/2526/P1.csv",

    # ── Temporada anterior 2024-25 ────────────────────────────
    "PL_2425":  "https://www.football-data.co.uk/mmz4281/2425/E0.csv",
    "PD_2425":  "https://www.football-data.co.uk/mmz4281/2425/SP1.csv",
    "BL1_2425": "https://www.football-data.co.uk/mmz4281/2425/D1.csv",
    "FL1_2425": "https://www.football-data.co.uk/mmz4281/2425/F1.csv",
    "SA_2425":  "https://www.football-data.co.uk/mmz4281/2425/I1.csv",
    "DED_2425": "https://www.football-data.co.uk/mmz4281/2425/N1.csv",
    "PPL_2425": "https://www.football-data.co.uk/mmz4281/2425/P1.csv",

    # ── Dos temporadas atrás 2023-24 ──────────────────────────
    "PL_2324":  "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
    "PD_2324":  "https://www.football-data.co.uk/mmz4281/2324/SP1.csv",
    "BL1_2324": "https://www.football-data.co.uk/mmz4281/2324/D1.csv",
    "FL1_2324": "https://www.football-data.co.uk/mmz4281/2324/F1.csv",
    "SA_2324":  "https://www.football-data.co.uk/mmz4281/2324/I1.csv",
    "DED_2324": "https://www.football-data.co.uk/mmz4281/2324/N1.csv",
    "PPL_2324": "https://www.football-data.co.uk/mmz4281/2324/P1.csv",


}

SEASONS        = ["2024", "2025"]
RECENT_MATCHES = 10
DECAY_FACTOR   = 0.0025
HOME_ADVANTAGE = 1.12

MIN_EV          = 0.08
MIN_PROB_MODEL  = 0.10
MIN_ODDS        = 1.30
MAX_ODDS        = 8.00

OUTPUT_CSV  = "output/value_bets.csv"
OUTPUT_HTML = "output/dashboard.html"

# --- Parámetros de Validación y Pesado ---
SEASON_WEIGHTS = {
    "2025": 1.0,  # Temporada actual: peso completo
    "2024": 0.5   # Temporada anterior: peso reducido
}

VALIDATION_THRESHOLD = 0.25  # Diferencia máxima vs cuotas (25%)