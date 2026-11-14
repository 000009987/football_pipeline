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
    
    
    

# ─── Validación de cuota y prob en send_alerts (B2.10) ───────────────

def test_invalid_odds_are_skipped():
    """
    B2.10: send_alerts skipea partidos con cuota inválida.

    Verifica que si una cuota está fuera de [1, 100], validate_odds devuelve
    False y el flujo de send_alerts no debería predecir.

    Este test es de contrato: verifica que send_alerts.py usa validate_odds.
    """
    from src.evaluation_helpers import validate_odds
    from pathlib import Path

    # 1. Validadores hacen su trabajo
    assert validate_odds(0.5) is False, "Cuota 0.5 debería ser inválida"
    assert validate_odds(150.0) is False, "Cuota 150 debería ser inválida"
    assert validate_odds(None) is False, "Cuota None debería ser inválida"

    # 2. send_alerts.py importa y usa validate_odds
    src = Path("scripts/send_alerts.py").read_text(encoding="utf-8")
    assert "validate_odds" in src, "send_alerts.py no importa validate_odds"
    assert "not validate_odds(" in src, "send_alerts.py no llama a validate_odds"


def test_invalid_prob_are_skipped():
    """
    B2.10: send_alerts skipea partidos con probabilidad inválida.

    Verifica que si prob_D está fuera de [0, 1], validate_prob devuelve False.
    """
    from src.evaluation_helpers import validate_prob
    from pathlib import Path

    # 1. Validadores hacen su trabajo
    assert validate_prob(-0.1) is False, "Prob -0.1 debería ser inválida"
    assert validate_prob(1.5) is False, "Prob 1.5 debería ser inválida"
    assert validate_prob(None) is False, "Prob None debería ser inválida"

    # 2. send_alerts.py importa y usa validate_prob
    src = Path("scripts/send_alerts.py").read_text(encoding="utf-8")
    assert "validate_prob" in src, "send_alerts.py no importa validate_prob"
    assert "not validate_prob(" in src, "send_alerts.py no llama a validate_prob"
