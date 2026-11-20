"""
Descarga xG por partido de FotMob para las 7 ligas del proyecto.

V2: parser corregido (itera sub-items de Periods.All.stats).
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import requests
import pandas as pd

from src.config import PROCESSED_DATA_DIR
from src.logger import get_logger

logger = get_logger("download_fotmob_xg")

RAW_DIR = Path("data/raw/fotmob")
LEAGUES_CACHE = RAW_DIR / "leagues"
MATCHES_CACHE = RAW_DIR / "matchdetails"
OUTPUT = PROCESSED_DATA_DIR / "fotmob_xg.parquet"

LEAGUES = {
    "PL": 47, "BL1": 54, "PD": 87, "SA": 55, "FL1": 53, "DED": 57, "PPL": 61,
}
SEASONS = {2023: "2023/2024", 2024: "2024/2025", 2025: "2025/2026", 2026: "2026/2027"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.fotmob.com/",
}
RATE_LIMIT_SEC = 1.0


def _load_json_cache(path):
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_json_cache(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def fetch_league(league_code, season, use_cache=True):
    path = LEAGUES_CACHE / f"{league_code}_{season}.json"
    if use_cache:
        cached = _load_json_cache(path)
        if cached:
            return cached
    league_id = LEAGUES[league_code]
    fotmob_season = SEASONS[season].replace("/", "%2F")
    url = f"https://www.fotmob.com/api/data/leagues?id={league_id}&season={fotmob_season}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"[{league_code}/{season}] HTTP {r.status_code}")
    data = r.json()
    _save_json_cache(path, data)
    time.sleep(RATE_LIMIT_SEC)
    return data


def fetch_match_details(match_id, use_cache=True):
    path = MATCHES_CACHE / f"{match_id}.json"
    if use_cache:
        cached = _load_json_cache(path)
        if cached:
            return cached
    url = f"https://www.fotmob.com/api/data/matchDetails?matchId={match_id}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"matchDetails {match_id}: HTTP {r.status_code}")
    data = r.json()
    _save_json_cache(path, data)
    time.sleep(RATE_LIMIT_SEC)
    return data


def parse_xg_from_details(detail, league_code, season):
    """V2: busca en sub-items de Periods.All.stats."""
    try:
        general = detail.get("general", {})
        content = detail.get("content", {})

        home_name = general.get("homeTeam", {}).get("name")
        away_name = general.get("awayTeam", {}).get("name")
        match_id = general.get("matchId")
        match_date = general.get("matchTimeUTC", "")

        if not home_name or not away_name:
            return None

        periods = content.get("stats", {}).get("Periods", {})
        all_period = periods.get("All", {})
        categories = all_period.get("stats", [])

        xg_home = xg_away = xg_np_home = xg_np_away = None

        for cat in categories:
            if not isinstance(cat, dict):
                continue
            sub_items = cat.get("stats", [])
            if not isinstance(sub_items, list):
                continue
            for sub in sub_items:
                if not isinstance(sub, dict):
                    continue
                key = sub.get("key")
                tipo = sub.get("type")
                raw = sub.get("rawStats", [])
                if tipo != "text" or not isinstance(raw, list) or len(raw) != 2:
                    continue
                h = raw[0].get("value") if isinstance(raw[0], dict) else None
                a = raw[1].get("value") if isinstance(raw[1], dict) else None
                if h is None or a is None:
                    continue
                if key == "expected_goals" and xg_home is None:
                    xg_home, xg_away = h, a
                elif key == "expected_goals_non_penalty" and xg_np_home is None:
                    xg_np_home, xg_np_away = h, a

        if xg_home is None or xg_away is None:
            return None

        return {
            "fotmob_match_id": str(match_id),
            "league": league_code,
            "season": season,
            "date_utc": match_date,
            "home_team_fotmob": home_name,
            "away_team_fotmob": away_name,
            "home_xg": xg_home,
            "away_xg": xg_away,
            "home_np_xg": xg_np_home,
            "away_np_xg": xg_np_away,
        }
    except Exception as e:
        logger.warning(f"Error parseando: {e}")
        return None


def process_league_season(league_code, season, use_cache=True):
    logger.info(f"\n{'=' * 60}\n{league_code} {season}\n{'=' * 60}")
    league_data = fetch_league(league_code, season, use_cache)
    matches = league_data.get("fixtures", {}).get("allMatches", [])
    logger.info(f"  {len(matches)} partidos en la liga")

    rows = []
    skipped_not_finished = 0
    skipped_no_xg = 0

    for i, m in enumerate(matches, 1):
        status = m.get("status", {})
        if not status.get("finished", False):
            skipped_not_finished += 1
            continue
        match_id = str(m.get("id"))
        if not match_id:
            continue
        if i % 50 == 0:
            logger.info(f"  [{i}/{len(matches)}]")
        try:
            detail = fetch_match_details(match_id, use_cache)
            row = parse_xg_from_details(detail, league_code, season)
            if row is None:
                skipped_no_xg += 1
                continue
            rows.append(row)
        except Exception as e:
            logger.error(f"  Error con {match_id}: {e}")

    logger.info(f"  ✅ {len(rows)} con xG | ⏭ {skipped_not_finished} no jugados, {skipped_no_xg} sin xG")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", choices=list(LEAGUES.keys()), default=None)
    parser.add_argument("--season", type=int, choices=list(SEASONS.keys()), default=None)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    leagues = [args.league] if args.league else list(LEAGUES.keys())
    seasons = [args.season] if args.season else list(SEASONS.keys())
    use_cache = not args.no_cache

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LEAGUES_CACHE.mkdir(parents=True, exist_ok=True)
    MATCHES_CACHE.mkdir(parents=True, exist_ok=True)

    logger.info(f"Ligas: {leagues} | Temporadas: {seasons} | Cache: {use_cache}")

    all_rows = []
    for league in leagues:
        for season in seasons:
            try:
                all_rows.extend(process_league_season(league, season, use_cache))
            except Exception as e:
                logger.error(f"Error en {league} {season}: {e}")

    if not all_rows:
        logger.error("❌ No se extrajo ningún partido")
        return

    df = pd.DataFrame(all_rows).sort_values(["season", "league", "date_utc"]).reset_index(drop=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT, index=False)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"✅ GUARDADO: {OUTPUT}")
    logger.info(f"   Total: {len(df)}")
    logger.info(f"   xG home no-nulo: {df['home_xg'].notna().sum()}")
    logger.info(f"   Temporadas: {sorted(df['season'].unique())}")
    logger.info(f"   Ligas: {sorted(df['league'].unique())}")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    main()