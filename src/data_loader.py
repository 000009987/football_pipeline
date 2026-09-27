"""
data_loader.py
Descarga datos históricos y fixtures desde:
  - football-data.org (API v4)
  - football-data.co.uk  (CSV, para ligas no cubiertas)
"""

import os
import re
import time
import json
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import API_KEY, BASE_URL, LEAGUES, SEASONS, EXTRA_LEAGUES_CSV

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"X-Auth-Token": API_KEY}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict = None) -> dict:
    """GET con reintentos y respeto al rate limit (10 req/min en plan free)."""
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(3):
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429:
            print(f"  Rate limit alcanzado, esperando 65s...")
            time.sleep(65)
        elif resp.status_code == 403:
            print(f"  ERROR 403: comprueba tu API key en config.py")
            return {}
        else:
            print(f"  Error {resp.status_code} en {url}, intento {attempt+1}/3")
            time.sleep(5)
    return {}


def _cache_path(name: str) -> Path:
    return RAW_DIR / f"{name}.json"


def _load_cache(name: str, max_hours: int = 6):
    """Devuelve datos cacheados si son recientes."""
    p = _cache_path(name)
    if p.exists():
        age = time.time() - p.stat().st_mtime
        if age < max_hours * 3600:
            with open(p) as f:
                return json.load(f)
    return None


def _save_cache(name: str, data):
    with open(_cache_path(name), "w") as f:
        json.dump(data, f)


def _normalize_df_teams(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza nombres de equipos en un DataFrame completo.
    Unifica nombres cortos de CSVs con nombres largos de la API.
    """
    try:
        from src.feature_engineering import TEAM_NAME_MAP, normalize_team_name
        if "home_team" in df.columns:
            df["home_team"] = df["home_team"].apply(normalize_team_name)
        if "away_team" in df.columns:
            df["away_team"] = df["away_team"].apply(normalize_team_name)
    except ImportError:
        pass
    return df


# ── Histórico (resultados) ─────────────────────────────────────────────────────

def fetch_historical_matches(competition: str, season: str) -> pd.DataFrame:
    """
    Descarga todos los partidos de una liga/temporada.
    Devuelve DataFrame con columnas estandarizadas.
    """
    cache_key = f"matches_{competition}_{season}"
    cached = _load_cache(cache_key, max_hours=24)

    if cached:
        print(f"  [{competition} {season}] usando caché")
        raw = cached
    else:
        print(f"  [{competition} {season}] descargando...")
        raw = _get(f"competitions/{competition}/matches",
                   params={"season": season, "status": "FINISHED"})
        if raw:
            _save_cache(cache_key, raw)
        time.sleep(7)

    if not raw or "matches" not in raw:
        return pd.DataFrame()

    rows = []
    for m in raw["matches"]:
        score = m.get("score", {})
        ft    = score.get("fullTime", {})
        rows.append({
            "match_id":      m["id"],
            "date":          m["utcDate"][:10],
            "competition":   competition,
            "season":        season,
            "home_team":     m["homeTeam"]["name"],
            "away_team":     m["awayTeam"]["name"],
            "home_goals":    ft.get("home"),
            "away_goals":    ft.get("away"),
            "status":        m["status"],
        })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["home_goals", "away_goals"])
    df["home_goals"] = df["home_goals"].astype(int)
    df["away_goals"] = df["away_goals"].astype(int)
    df["total_goals"] = df["home_goals"] + df["away_goals"]
    return df


def fetch_all_historical(competitions: list = None, seasons: list = None) -> pd.DataFrame:
    """Descarga histórico de todas las ligas configuradas."""
    seasons = seasons or SEASONS

    # Ligas cubiertas por CSV (football-data.co.uk) — se excluyen de la API
    csv_covered = {re.sub(r"_\d{4}$", "", name) for name in EXTRA_LEAGUES_CSV.keys()}

    # Liga(s) sin CSV: se piden a la API
    if competitions is None:
        competitions = [c for c in LEAGUES.keys() if c not in csv_covered]
    else:
        competitions = [c for c in competitions if c not in csv_covered]

    all_dfs = []
    for comp in competitions:
        for season in seasons:
            df = fetch_historical_matches(comp, season)
            if not df.empty:
                all_dfs.append(df)

    # Extra leagues from CSV
    for league_name, url in EXTRA_LEAGUES_CSV.items():
        df = _fetch_csv_league(league_name, url)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)

    # Normalizar nombre de competición: quitar sufijo _YYZZ (PL_2324 -> PL)
    combined["competition"] = (
        combined["competition"]
        .astype(str)
        .str.replace(r"_\d{4}$", "", regex=True)
    )

    # Dedup por partido, priorizando filas con odds
    combined["_has_odds"] = combined["odds_home"].notna()
    combined = combined.sort_values("_has_odds", ascending=False)
    combined = combined.drop_duplicates(
        subset=["competition", "date", "home_team", "away_team"],
        keep="first",
    )
    combined = combined.drop(columns=["_has_odds"])

    combined = combined.sort_values("date").reset_index(drop=True)
    combined = _normalize_df_teams(combined)

    print(f"\nTotal partidos históricos cargados: {len(combined):,}")
    return combined


def _fetch_csv_league(league_name: str, url: str) -> pd.DataFrame:
    """Descarga CSV de football-data.co.uk y lo estandariza."""
    cache_key = f"csv_{league_name}"
    csv_path  = RAW_DIR / f"{cache_key}.csv"

    if csv_path.exists() and (time.time() - csv_path.stat().st_mtime) < 86400:
        print(f"  [{league_name}] usando caché CSV")
        raw = pd.read_csv(csv_path, encoding="latin1")
    else:
        print(f"  [{league_name}] descargando CSV...")
        try:
            raw = pd.read_csv(url, encoding="latin1")
            raw.to_csv(csv_path, index=False)
        except Exception as e:
            print(f"  Error descargando {league_name}: {e}")
            return pd.DataFrame()

    # Columnas estándar de football-data.co.uk
    col_map = {
        "Date": "date", "HomeTeam": "home_team", "AwayTeam": "away_team",
        "FTHG": "home_goals", "FTAG": "away_goals",
        "B365H": "odds_home", "B365D": "odds_draw", "B365A": "odds_away",
    }
    raw = raw.rename(columns={k: v for k, v in col_map.items() if k in raw.columns})

    required = ["date", "home_team", "away_team", "home_goals", "away_goals"]
    if not all(c in raw.columns for c in required):
        return pd.DataFrame()

    raw["competition"] = league_name

    # Extraer temporada del URL: .../2526/E0.csv -> "2025"
    _m = re.search(r"/(\d{2})(\d{2})/", url)
    raw["season"] = str(2000 + int(_m.group(1))) if _m else "2024"

    raw["date"]        = pd.to_datetime(raw["date"], dayfirst=True, errors="coerce")
    raw                = raw.dropna(subset=["date", "home_goals", "away_goals"])
    raw["home_goals"]  = raw["home_goals"].astype(int)
    raw["away_goals"]  = raw["away_goals"].astype(int)
    raw["total_goals"] = raw["home_goals"] + raw["away_goals"]
    raw = _normalize_df_teams(raw)
    return raw


# ── Fixtures (próximos partidos) ───────────────────────────────────────────────

def fetch_upcoming_fixtures(competition: str, days_ahead: int = 7) -> pd.DataFrame:
    """Próximos partidos de una competición en los siguientes N días."""
    today     = datetime.utcnow().date()
    date_to   = today + timedelta(days=days_ahead)
    cache_key = f"fixtures_{competition}_{today}"
    cached    = _load_cache(cache_key, max_hours=3)

    if cached:
        raw = cached
    else:
        raw = _get(f"competitions/{competition}/matches",
                   params={
                       "status": "SCHEDULED",
                       "dateFrom": str(today),
                       "dateTo":   str(date_to),
                   })
        if raw:
            _save_cache(cache_key, raw)
        time.sleep(7)

    if not raw or "matches" not in raw:
        return pd.DataFrame()

    rows = []
    for m in raw["matches"]:
        rows.append({
            "date":        m["utcDate"][:10],
            "competition": competition,
            "home_team":   m["homeTeam"]["name"],
            "away_team":   m["awayTeam"]["name"],
            "match_id":    m["id"],
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def fetch_all_upcoming(competitions: list = None, days_ahead: int = 7) -> pd.DataFrame:
    """Próximos partidos de todas las ligas configuradas."""
    competitions = competitions or list(LEAGUES.keys())
    all_dfs = []
    for comp in competitions:
        df = fetch_upcoming_fixtures(comp, days_ahead)
        if not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)
    print(f"\n✓ Próximos partidos encontrados: {len(combined)}")
    return combined


if __name__ == "__main__":
    print("=== Test data_loader ===")
    df = fetch_historical_matches("PL", "2023")
    print(df.head())
    print(f"Partidos: {len(df)}")