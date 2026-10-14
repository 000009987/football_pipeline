"""
odds_scheduler.py
Gestión de consultas a The Odds API y almacenamiento local en SQLite.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ODDS_UPDATE_INTERVAL_HOURS, PREFERRED_BOOKMAKER
from src.odds_client import OddsAPIClient
from src.odds_normalizer import normalize_odds_api_response, match_teams
from src.odds_storage import get_latest_stored_odds, save_odds_snapshot

_LEAGUE_FETCH_CACHE = {}


def fetch_and_store_fixture_odds(
    home_team: str,
    away_team: str,
    competition: str,
    date_str: str,
    force_update: bool = False
) -> Dict[str, float]:
    """
    Obtiene las cuotas para un partido dado.
    """
    if not force_update:
        cached_odds = get_latest_stored_odds(home_team, away_team, max_age_hours=ODDS_UPDATE_INTERVAL_HOURS)
        if cached_odds:
            return cached_odds

    if competition not in _LEAGUE_FETCH_CACHE:
        client = OddsAPIClient()
        events = client.fetch_odds_for_league(competition)
        _LEAGUE_FETCH_CACHE[competition] = events
    else:
        events = _LEAGUE_FETCH_CACHE[competition]

    if not events:
        fallback_odds = get_latest_stored_odds(home_team, away_team, max_age_hours=168)
        return fallback_odds or {}

    target_event = None
    for ev in events:
        ev_home = ev.get("home_team", "")
        ev_away = ev.get("away_team", "")
        if match_teams(home_team, ev_home) and match_teams(away_team, ev_away):
            target_event = ev
            break

    if not target_event:
        fallback_odds = get_latest_stored_odds(home_team, away_team, max_age_hours=168)
        return fallback_odds or {}

    normalized_odds = normalize_odds_api_response(
        event_data=target_event,
        home_team=home_team,
        away_team=away_team,
        preferred_bookmaker=PREFERRED_BOOKMAKER
    )

    if not normalized_odds:
        fallback_odds = get_latest_stored_odds(home_team, away_team, max_age_hours=168)
        return fallback_odds or {}

    provider_updated_at = datetime.now(timezone.utc).isoformat()
    internal_match_id = f"{competition}_{date_str}_{home_team}_{away_team}"

    save_odds_snapshot(
        internal_match_id=internal_match_id,
        api_football_fixture_id=0,
        competition=competition,
        home_team=home_team,
        away_team=away_team,
        bookmaker=PREFERRED_BOOKMAKER,
        normalized_odds=normalized_odds,
        provider_updated_at=provider_updated_at,
        raw_response=target_event
    )

    return normalized_odds