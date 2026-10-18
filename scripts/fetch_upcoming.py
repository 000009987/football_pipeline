"""
Descarga fixtures futuros y sus cuotas, y guarda upcoming_fixtures.parquet.

Solo guarda partidos CON cuota de empate (los que no tienen cuota no son accionables).

Requiere:
  - FOOTBALL_DATA_API_KEY en .env
  - ODDS_API_KEY en .env

Uso:
  python scripts/fetch_upcoming.py            # solo PL + BL1
  python scripts/fetch_upcoming.py --all      # las 7 ligas
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse
import unicodedata
import requests
import pandas as pd
from datetime import datetime

from src.config import (
    API_KEY,
    BASE_URL,
    ODDS_API_KEY,
    ODDS_API_BASE_URL,
    ODDS_API_SPORT_KEYS,
    UPCOMING_PARQUET,
    PRODUCTION_LEAGUES,
)
from src.logger import get_logger

logger = get_logger("fetch_upcoming")

# Palabras que no distinguen equipos
_STOPWORDS = {"fc", "cf", "afc", "sc", "ac", "and", "de", "the", "club", "cd", "ud"}


_STOPWORDS = {
    "fc", "cf", "afc", "sc", "ac", "and", "de", "the", "club", "cd", "ud",
    "sv", "fsv", "tsg", "vfb", "vfl", "bsc", "spvgg", "1899", "07", "04", "05",
    "1", "2", "3",
}

# Alias de nombres entre APIs (bidireccional)
_ALIASES = {
    "munchen": "munich",
    "koln": "cologne",
    "gladbach": "monchengladbach",
    "moenchengladbach": "monchengladbach",
}


def _normalize(name: str) -> str:
    """Normaliza nombre: minúsculas, sin acentos, sin '&', sin guiones/puntos."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = name.replace("&", " and ")
    name = name.replace("-", " ").replace(".", " ").replace("'", " ")
    return " ".join(name.split())


def _tokens(name: str) -> set:
    """Tokens significativos con alias aplicados."""
    raw = _normalize(name).split()
    return {_ALIASES.get(t, t) for t in raw if t not in _STOPWORDS}


def _teams_match(team_a: str, team_b: str) -> bool:
    """Match de equipos: 2+ tokens comunes, subset, o un token común + alias."""
    ta, tb = _tokens(team_a), _tokens(team_b)
    if not ta or not tb:
        return False
    common = ta & tb
    if len(common) >= 2:
        return True
    # Caso "Elversberg" vs "SV 07 Elversberg" → uno es subset del otro
    if ta.issubset(tb) or tb.issubset(ta):
        return True
    return False

def fetch_fixtures(competition_code: str) -> list:
    url = f"{BASE_URL}/competitions/{competition_code}/matches"
    headers = {"X-Auth-Token": API_KEY}
    params = {"status": "SCHEDULED"}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code != 200:
            logger.error(f"[{competition_code}] HTTP {r.status_code}: {r.text[:200]}")
            return []
        return r.json().get("matches", [])
    except Exception as e:
        logger.error(f"[{competition_code}] Excepción fixtures: {e}")
        return []


def fetch_odds(sport_key: str) -> list:
    url = f"{ODDS_API_BASE_URL}/{sport_key}/odds/"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            logger.error(f"[{sport_key}] HTTP {r.status_code}: {r.text[:200]}")
            return []
        return r.json()
    except Exception as e:
        logger.error(f"[{sport_key}] Excepción odds: {e}")
        return []


def extract_draw_odds(odds_data: list, home_team: str, away_team: str, commence_iso: str):
    """Devuelve la cuota de empate o None. Usa fuzzy matching de equipos y fecha (±2h)."""
    for match in odds_data:
        try:
            m_time = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
            f_time = datetime.fromisoformat(commence_iso.replace("Z", "+00:00"))
            if abs((m_time - f_time).total_seconds()) > 7200:
                continue
        except Exception:
            continue

        if not _teams_match(home_team, match.get("home_team", "")):
            continue
        if not _teams_match(away_team, match.get("away_team", "")):
            continue

        # Preferir Pinnacle, luego el primero disponible
        bookmakers = sorted(
            match.get("bookmakers", []),
            key=lambda b: 0 if b.get("key") == "pinnacle" else 1,
        )
        for bm in bookmakers:
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    if outcome.get("name", "").lower() == "draw":
                        return float(outcome["price"])
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Procesar las 7 ligas (no solo PL+BL1)")
    args = parser.parse_args()

    leagues = list(ODDS_API_SPORT_KEYS.keys()) if args.all else PRODUCTION_LEAGUES
    logger.info(f"Descargando fixtures de: {leagues}")

    rows = []
    for league in leagues:
        logger.info(f"[{league}] Descargando fixtures...")
        fixtures = fetch_fixtures(league)
        if not fixtures:
            logger.warning(f"[{league}] Sin fixtures")
            continue

        logger.info(f"[{league}] {len(fixtures)} partidos programados. Descargando cuotas...")
        odds = fetch_odds(ODDS_API_SPORT_KEYS[league])
        logger.info(f"[{league}] The Odds API devuelve {len(odds)} partidos con cuota")

        matched = 0
        for m in fixtures:
            utc_date = m.get("utcDate")
            home = m.get("homeTeam", {}).get("name", "?")
            away = m.get("awayTeam", {}).get("name", "?")
            draw_odds = extract_draw_odds(odds, home, away, utc_date) if odds else None

            if draw_odds is None:
                continue  # descartar sin cuota

            matched += 1
            rows.append({
                "competition": league,
                "date": utc_date,
                "home_team": home,
                "away_team": away,
                "status": m.get("status"),
                "odds_draw": draw_odds,
                "season": str(datetime.now().year),
            })

        logger.info(f"[{league}] {matched} partidos matcheados con cuota")

    if not rows:
        logger.error("No se matcheó ningún partido. Revisa nombres de equipos.")
        return

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
    df = df.sort_values("date").reset_index(drop=True)

    UPCOMING_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(UPCOMING_PARQUET, index=False)
    logger.info(f"Guardado: {UPCOMING_PARQUET} ({len(df)} partidos con cuota)")
    logger.info(f"Rango: {df['date'].min()} → {df['date'].max()}")


if __name__ == "__main__":
    main()