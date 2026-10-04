"""
feature_engineering.py
Calcula ratings de ataque/defensa, forma reciente y métricas derivadas.
Usa ponderación temporal exponencial para dar más peso a partidos recientes.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DECAY_FACTOR, RECENT_MATCHES, HOME_ADVANTAGE

# ── Normalización de nombres de equipos ───────────────────────────────────────
# Mapea nombres cortos de CSVs al nombre largo de la API
TEAM_NAME_MAP = {
    # ── Premier League ──
    "Arsenal":                  "Arsenal FC",
    "Aston Villa":              "Aston Villa FC",
    "Bournemouth":              "AFC Bournemouth",
    "Brentford":                "Brentford FC",
    "Brighton":                 "Brighton & Hove Albion FC",
    "Burnley":                  "Burnley FC",
    "Chelsea":                  "Chelsea FC",
    "Crystal Palace":           "Crystal Palace FC",
    "Everton":                  "Everton FC",
    "Fulham":                   "Fulham FC",
    "Ipswich":                  "Ipswich Town FC",
    "Leeds":                    "Leeds United FC",
    "Leicester":                "Leicester City FC",
    "Liverpool":                "Liverpool FC",
    "Man City":                 "Manchester City FC",
    "Manchester City":          "Manchester City FC",   # alias Understat
    "Man United":               "Manchester United FC",
    "Manchester United":        "Manchester United FC", # alias Understat
    "Newcastle":                "Newcastle United FC",
    "Newcastle United":         "Newcastle United FC",  # alias Understat
    "Nott'm Forest":            "Nottingham Forest FC",
    "Nottingham Forest":        "Nottingham Forest FC", # alias Understat
    "Southampton":              "Southampton FC",
    "Sunderland":               "Sunderland AFC",
    "Tottenham":                "Tottenham Hotspur FC",
    "West Ham":                 "West Ham United FC",
    "Wolves":                   "Wolverhampton Wanderers FC",
    "Wolverhampton Wanderers":  "Wolverhampton Wanderers FC",  # alias Understat

    # ── LaLiga ──
    "Ath Bilbao":           "Athletic Club",
    "Ath Madrid":           "Club Atlético de Madrid",
    "Atletico Madrid":      "Club Atlético de Madrid",
    "Barcelona":            "FC Barcelona",
    "Betis":                "Real Betis Balompié",
    "Celta":                "RC Celta de Vigo",
    "Espanol":              "RCD Espanyol de Barcelona",
    "Espanyol":             "RCD Espanyol de Barcelona",
    "Getafe":               "Getafe CF",
    "Girona":               "Girona FC",
    "Granada":              "Granada CF",
    "Las Palmas":           "UD Las Palmas",
    "Leganes":              "CD Leganés",
    "Mallorca":             "RCD Mallorca",
    "Osasuna":              "CA Osasuna",
    "Rayo Vallecano":       "Rayo Vallecano de Madrid",
    "Real Madrid":          "Real Madrid CF",
    "Real Sociedad":        "Real Sociedad de Fútbol",
    "Sevilla":              "Sevilla FC",
    "Sociedad":             "Real Sociedad de Fútbol",
    "Valencia":             "Valencia CF",
    "Valladolid":           "Real Valladolid CF",
    "Villarreal":           "Villarreal CF",
    "Alaves":               "Deportivo Alavés",
    "Almeria":              "UD Almería",
    "Cadiz":                "Cádiz CF",
    "Elche":                "Elche CF",

    # ── Bundesliga ──
    "Augsburg":             "FC Augsburg",
    "Bayern Munich":        "FC Bayern München",
    "Bayer Leverkusen":     "Bayer 04 Leverkusen",
    "Dortmund":             "Borussia Dortmund",
    "Ein Frankfurt":        "Eintracht Frankfurt",
    "Freiburg":             "SC Freiburg",
    "Heidenheim":           "1. FC Heidenheim 1846",
    "Hoffenheim":           "TSG 1899 Hoffenheim",
    "Köln":                 "1. FC Köln",
    "Koln":                 "1. FC Köln",
    "Leipzig":              "RB Leipzig",
    "Mainz":                "1. FSV Mainz 05",
    "M'gladbach":           "Borussia Mönchengladbach",
    "Monchengladbach":      "Borussia Mönchengladbach",
    "St Pauli":             "FC St. Pauli 1910",
    "Stuttgart":            "VfB Stuttgart",
    "Union Berlin":         "1. FC Union Berlin",
    "Werder Bremen":        "SV Werder Bremen",
    "Wolfsburg":            "VfL Wolfsburg",
    "Hamburg":              "Hamburger SV",
    "Schalke 04":           "FC Schalke 04",
    "Paderborn":            "SC Paderborn 07",

    # ── Ligue 1 ──
    "Angers":               "Angers SCO",
    "Auxerre":              "AJ Auxerre",
    "Brest":                "Stade Brestois 29",
    "Clermont":             "Clermont Foot 63",
    "Lens":                 "RC Lens",
    "Lille":                "Lille OSC",
    "Lorient":              "FC Lorient",
    "Lyon":                 "Olympique Lyonnais",
    "Marseille":            "Olympique de Marseille",
    "Metz":                 "FC Metz",
    "Monaco":               "AS Monaco FC",
    "Montpellier":          "Montpellier HSC",
    "Nantes":               "FC Nantes",
    "Nice":                 "OGC Nice",
    "Paris SG":             "Paris Saint-Germain FC",
    "Reims":                "Stade de Reims",
    "Rennes":               "Stade Rennais FC 1901",
    "Strasbourg":           "RC Strasbourg Alsace",
    "Toulouse":             "Toulouse FC",
    "Le Havre":             "Le Havre AC",
    "St Etienne":           "AS Saint-Étienne",

    # ── Serie A ──
    "AC Milan":             "AC Milan",
    "Atalanta":             "Atalanta BC",
    "Bologna":              "Bologna FC 1909",
    "Cagliari":             "Cagliari Calcio",
    "Como":                 "Como 1907",
    "Cremonese":            "US Cremonese",
    "Empoli":               "Empoli FC",
    "Fiorentina":           "ACF Fiorentina",
    "Frosinone":            "Frosinone Calcio",
    "Genoa":                "Genoa CFC",
    "Inter":                "FC Internazionale Milano",
    "Juventus":             "Juventus FC",
    "Lazio":                "SS Lazio",
    "Lecce":                "US Lecce",
    "Milan":                "AC Milan",
    "Monza":                "AC Monza",
    "Napoli":               "SSC Napoli",
    "Parma":                "Parma Calcio 1913",
    "Roma":                 "AS Roma",
    "Salernitana":          "US Salernitana 1919",
    "Sampdoria":            "UC Sampdoria",
    "Sassuolo":             "US Sassuolo Calcio",
    "Torino":               "Torino FC",
    "Udinese":              "Udinese Calcio",
    "Venezia":              "Venezia FC",
    "Verona":               "Hellas Verona FC",

    # ── Eredivisie ──
    "Ajax":                 "AFC Ajax",
    "AZ":                   "AZ Alkmaar",
    "Excelsior":            "SBV Excelsior",
    "Feyenoord":            "Feyenoord Rotterdam",
    "Fortuna Sittard":      "Fortuna Sittard",
    "Go Ahead":             "Go Ahead Eagles",
    "Groningen":            "FC Groningen",
    "Heerenveen":           "SC Heerenveen",
    "Heracles":             "Heracles Almelo",
    "NAC Breda":            "NAC Breda",
    "NEC":                  "NEC Nijmegen",
    "PSV":                  "PSV Eindhoven",
    "RKC Waalwijk":         "RKC Waalwijk",
    "Sparta Rotterdam":     "Sparta Rotterdam",
    "Twente":               "FC Twente",
    "Utrecht":              "FC Utrecht",
    "Volendam":             "FC Volendam",
    "Zwolle":               "PEC Zwolle",

    # ── Primeira Liga ──
    "Benfica":              "Sport Lisboa e Benfica",
    "Braga":                "Sporting Clube de Braga",
    "Estoril":              "GD Estoril Praia",
    "Famalicao":            "FC Famalicão",
    "Gil Vicente":          "Gil Vicente FC",
    "Guimaraes":            "Vitória SC",
    "Maritimo":             "CS Marítimo",
    "Moreirense":           "Moreirense FC",
    "Nacional":             "CD Nacional",
    "Pacos Ferreira":       "FC Paços de Ferreira",
    "Porto":                "FC Porto",
    "Rio Ave":              "Rio Ave FC",
    "Santa Clara":          "CD Santa Clara",
    "Sporting CP":          "Sporting Clube de Portugal",
    "Vizela":               "FC Vizela",
    "Arouca":               "FC Arouca",
    "Casa Pia":             "Casa Pia AC",
    "Chaves":               "GD Chaves",
    "Estrela":              "CF Estrela da Amadora",
    
           # ── Alias Understat (Bundesliga) ──
    # Overrides (dict literal: la última entrada gana)
    "Bochum":                   "Bochum",
    "Borussia Dortmund":        "Borussia Dortmund",
    "Darmstadt":                "Darmstadt",
    "Eintracht Frankfurt":      "Eintracht Frankfurt",
    "Hamburger SV":             "Hamburger SV",
    "Holstein Kiel":            "Holstein Kiel",
    "VfB Stuttgart":            "VfB Stuttgart",
    # Alias específicos Understat
    "Augsburg":                 "FC Augsburg",
    "Bayer Leverkusen":         "Leverkusen",
    "Bayern Munich":            "FC Bayern München",
    "Borussia M.Gladbach":      "Borussia Mönchengladbach",
    "FC Cologne":               "FC Koln",
    "FC Heidenheim":            "1. FC Heidenheim 1846",
    "Freiburg":                 "SC Freiburg",
    "Hoffenheim":               "TSG 1899 Hoffenheim",
    "Mainz 05":                 "1. FSV Mainz 05",
    "RasenBallsport Leipzig":   "RB Leipzig",
    "St. Pauli":                "FC St. Pauli 1910",
    "Union Berlin":             "1. FC Union Berlin",
    "Werder Bremen":            "SV Werder Bremen",
    "Wolfsburg":                "VfL Wolfsburg",

    # ── Alias Understat (Ligue 1) ──
    "Clermont Foot":            "Clermont Foot 63",
    "Paris Saint Germain":      "Paris Saint-Germain FC",
    "Saint-Etienne":            "AS Saint-Étienne",

    # ── Alias Understat (La Liga) ──
    "Celta Vigo":               "RC Celta de Vigo",
    "Rayo Vallecano":           "Vallecano",
    "Real Betis":               "Real Betis Balompié",
    "Real Oviedo":              "Oviedo",
    "Real Valladolid":          "Real Valladolid CF",
}


def normalize_team_name(name: str) -> str:
    """Normaliza nombre de equipo unificando entre fuentes CSV y API."""
    if not name or not isinstance(name, str):
        return name
    name = name.strip()
    # Match exacto
    if name in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[name]
    # Match case-insensitive
    name_lower = name.lower()
    for short, full in TEAM_NAME_MAP.items():
        if short.lower() == name_lower:
            return full
    return name


def compute_weights(dates: pd.Series, decay: float = DECAY_FACTOR) -> np.ndarray:
    """
    Peso exponencial: partidos más recientes pesan más.
    w_i = exp(-decay * días_desde_partido)
    """
    reference = dates.max()
    days_ago = (reference - dates).dt.days.values
    weights = np.exp(-decay * days_ago)
    return weights / weights.sum()   # normalizado


def build_team_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """
    (DEPRECATED — el ratings_cache nunca se actualiza. No usar hasta arreglar.)
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    league_avgs = (
        df.groupby("competition")
          .agg(avg_home=("home_goals", "mean"), avg_away=("away_goals", "mean"))
          .reset_index()
    )
    df = df.merge(league_avgs, on="competition", how="left")

    ratings_cache = {}  # {team: (att, def)} updated rolling

    home_att, home_def = [], []
    away_att, away_def = [], []

    for idx, row in df.iterrows():
        ht, at = row["home_team"], row["away_team"]
        ha, hd = ratings_cache.get(ht, (1.0, 1.0))
        aa, ad = ratings_cache.get(at, (1.0, 1.0))
        home_att.append(ha)
        home_def.append(hd)
        away_att.append(aa)
        away_def.append(ad)

    df["home_att_rating"] = home_att
    df["home_def_rating"] = home_def
    df["away_att_rating"] = away_att
    df["away_def_rating"] = away_def
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  Ratings por equipo (parametrizable: goles o xG)
# ─────────────────────────────────────────────────────────────────────────────
def compute_ratings_for_team(team: str, df: pd.DataFrame,
                              as_of_date=None,
                              col_home: str = "home_goals",
                              col_away: str = "away_goals") -> dict:
    """
    Ratings de ataque/defensa para `team`.

    col_home / col_away: columnas usadas como "goles" del partido.
        - Goles: ("home_goals", "away_goals")   ← default
        - xG:    ("home_xg",    "away_xg")

    La forma (form_5, form_10) SIEMPRE se calcula con goles reales,
    independientemente de las columnas usadas para ratings.
    """
    team = normalize_team_name(team)
    if as_of_date is None:
        as_of_date = df["date"].max()

    cutoff = as_of_date - pd.Timedelta(days=730)
    past = df[(df["date"] < as_of_date) & (df["date"] >= cutoff)].copy()
    if len(past) < 200:
        past = df[df["date"] < as_of_date].copy()

    if col_home not in past.columns or col_away not in past.columns:
        raise ValueError(f"Faltan columnas {col_home}/{col_away} en df")

    past = past.dropna(subset=[col_home, col_away])

    home_matches = past[past["home_team"] == team].copy()
    away_matches = past[past["away_team"] == team].copy()

    def weighted_avg(series, dates, fallback=1.0):
        if len(series) == 0:
            return fallback
        w = compute_weights(dates)
        return float(np.average(series, weights=w))

    comp = df[df["home_team"] == team]["competition"].mode()
    if comp.empty:
        comp = df[df["away_team"] == team]["competition"].mode()
    competition = comp.iloc[0] if not comp.empty else None

    if competition:
        league_data = past[past["competition"] == competition]
        lg_avg_home = league_data[col_home].mean() if len(league_data) > 10 else 1.3
        lg_avg_away = league_data[col_away].mean() if len(league_data) > 10 else 1.1
    else:
        lg_avg_home, lg_avg_away = 1.3, 1.1

    if not np.isfinite(lg_avg_home) or lg_avg_home <= 0:
        lg_avg_home = 1.3
    if not np.isfinite(lg_avg_away) or lg_avg_away <= 0:
        lg_avg_away = 1.1

    n_home = len(home_matches)
    n_away = len(away_matches)

    att_home = (weighted_avg(home_matches[col_home], home_matches["date"], lg_avg_home)
                / lg_avg_home) if n_home >= 3 else 1.0
    def_home = (weighted_avg(home_matches[col_away], home_matches["date"], lg_avg_away)
                / lg_avg_away) if n_home >= 3 else 1.0
    att_away = (weighted_avg(away_matches[col_away], away_matches["date"], lg_avg_away)
                / lg_avg_away) if n_away >= 3 else 1.0
    def_away = (weighted_avg(away_matches[col_home], away_matches["date"], lg_avg_home)
                / lg_avg_home) if n_away >= 3 else 1.0

    def regress(rating, n, target=1.0, weight=12):
        return (rating * n + target * weight) / (n + weight)

    att_home = regress(att_home, n_home)
    def_home = regress(def_home, n_home)
    att_away = regress(att_away, n_away)
    def_away = regress(def_away, n_away)

    # ── Forma: SIEMPRE con goles reales (independiente de col_home/col_away) ──
    all_team = pd.concat([
        home_matches.assign(_scored=home_matches["home_goals"],
                            _conceded=home_matches["away_goals"]),
        away_matches.assign(_scored=away_matches["away_goals"],
                            _conceded=away_matches["home_goals"]),
    ]).sort_values("date")

    def pts_from_recent(n):
        recent = all_team.tail(n)
        if len(recent) < 3:
            return 0.5
        pts = sum(
            3 if r["_scored"] > r["_conceded"]
            else 1 if r["_scored"] == r["_conceded"]
            else 0
            for _, r in recent.iterrows()
        )
        return pts / (n * 3)

    return {
        "att_home":    round(att_home, 4),
        "def_home":    round(def_home, 4),
        "att_away":    round(att_away, 4),
        "def_away":    round(def_away, 4),
        "form_5":      round(pts_from_recent(5), 4),
        "form_10":     round(pts_from_recent(10), 4),
        "lg_avg_home": round(lg_avg_home, 4),
        "lg_avg_away": round(lg_avg_away, 4),
        "n_home":      n_home,
        "n_away":      n_away,
    }


def enrich_fixture(fixture_row: pd.Series, df_history: pd.DataFrame,
                   as_of_date=None,
                   col_home: str = "home_goals",
                   col_away: str = "away_goals") -> dict:
    ht = normalize_team_name(fixture_row["home_team"])
    at = normalize_team_name(fixture_row["away_team"])

    hr = compute_ratings_for_team(ht, df_history, as_of_date=as_of_date,
                                   col_home=col_home, col_away=col_away)
    ar = compute_ratings_for_team(at, df_history, as_of_date=as_of_date,
                                   col_home=col_home, col_away=col_away)

    n_home_total = hr["n_home"] + hr["n_away"]
    n_away_total = ar["n_home"] + ar["n_away"]
    min_partidos = min(n_home_total, n_away_total)

    if min_partidos < 10:
        confianza = "BAJA"
    elif min_partidos < 25:
        confianza = "MEDIA"
    else:
        confianza = "ALTA"

    lambda_home = (hr["att_home"] * ar["def_away"] * hr["lg_avg_home"]
                   * HOME_ADVANTAGE)
    lambda_away = (ar["att_away"] * hr["def_home"] * ar["lg_avg_away"])

    lambda_home = float(np.clip(lambda_home, 0.4, 4.0))
    lambda_away = float(np.clip(lambda_away, 0.4, 4.0))

    return {
        "home_team":   ht,
        "away_team":   at,
        "competition": fixture_row.get("competition", ""),
        "date":        str(fixture_row.get("date", ""))[:10],
        "lambda_home": round(lambda_home, 4),
        "lambda_away": round(lambda_away, 4),
        "confianza":   confianza,
        "n_partidos":  min_partidos,
        "att_home":    hr["att_home"], "def_home": hr["def_home"],
        "att_away":    ar["att_away"], "def_away": ar["def_away"],
        "form_home":   hr["form_5"],   "form_away": ar["form_5"],
    }