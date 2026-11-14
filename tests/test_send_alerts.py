import pandas as pd

from scripts import send_alerts


def test_compute_live_predictions_uses_only_fixture_competition(monkeypatch):
    history = pd.DataFrame({
        "competition": ["PL", "CL", "BL1"],
        "home_team": ["Arsenal", "Arsenal", "Bayern"],
        "away_team": ["Chelsea", "Real Madrid", "Dortmund"],
    })
    upcoming = pd.DataFrame([
        {
            "competition": "PL",
            "date": pd.Timestamp("2026-11-20"),
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "odds_draw": 3.2,
        },
        {
            "competition": "BL1",
            "date": pd.Timestamp("2026-11-20"),
            "home_team": "Bayern",
            "away_team": "Dortmund",
            "odds_draw": 3.4,
        },
    ])
    received_competitions = []

    def fake_enrich_fixture(fixture, history_league, as_of_date):
        received_competitions.append(set(history_league["competition"]))
        return {"lambda_home": 1.5, "lambda_away": 1.2}

    monkeypatch.setattr(send_alerts, "enrich_fixture", fake_enrich_fixture)

    predictions = send_alerts.compute_live_predictions(upcoming, history, {})

    assert received_competitions == [{"PL"}, {"BL1"}]
    assert predictions["competition"].tolist() == ["PL", "BL1"]
