"""
test_odds_integration.py
Batería de pruebas unitarias para la integración con The Odds API.
"""

import os
import sqlite3
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.odds_normalizer import normalize_odds_api_response, match_teams
from src.odds_storage import init_db, save_odds_snapshot, get_latest_stored_odds
from src.value_bet_detector import analyze_fixture, _ev


def test_normalization_odds_api():
    mock_event = {
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "onexbet",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2.10},
                            {"name": "Chelsea", "price": 3.60},
                            {"name": "Draw", "price": 3.40}
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "point": 2.5, "price": 1.85},
                            {"name": "Under", "point": 2.5, "price": 1.95}
                        ]
                    }
                ]
            }
        ]
    }

    norm = normalize_odds_api_response(mock_event, "Arsenal", "Chelsea", preferred_bookmaker="onexbet")

    assert norm["1"] == 2.10
    assert norm["X"] == 3.40
    assert norm["2"] == 3.60
    assert norm["O2.5"] == 1.85
    assert norm["U2.5"] == 1.95


def test_snapshot_persistence():
    init_db()
    h_team, a_team = "ArsenalTest", "ChelseaTest"
    odds_v1 = {"1": 2.00, "X": 3.20, "2": 3.80}

    save_odds_snapshot(
        internal_match_id="TEST_01",
        api_football_fixture_id=0,
        competition="PL",
        home_team=h_team,
        away_team=a_team,
        bookmaker="onexbet",
        normalized_odds=odds_v1,
        provider_updated_at="2026-10-14T10:00:00Z"
    )

    latest = get_latest_stored_odds(h_team, a_team, max_age_hours=24)
    assert latest is not None
    assert latest["1"] == 2.00


def test_model_probability_isolation():
    model_pred = {"prob_home": 0.50}
    odds_high = {"1": 2.20}

    bets_high = analyze_fixture(model_pred, odds_high, home_team="A", away_team="B")

    assert model_pred["prob_home"] == 0.50
    if bets_high:
        assert bets_high[0]["prob_model"] == 0.50
        assert bets_high[0]["ev"] == pytest.approx(0.10, abs=1e-3)


def test_team_matching():
    assert match_teams("Arsenal FC", "Arsenal")
    assert match_teams("Real Madrid CF", "Real Madrid")
    assert match_teams("Bayern München", "Bayern Munich")