"""
value_bet_detector.py
Compara probabilidades del modelo contra cuotas del mercado.
Calcula EV (Expected Value) e identifica value bets.

Flujo:
  1. Recibe predicción del modelo (prob_home, prob_draw, prob_away, over/under, btts)
  2. Recibe cuotas de casas de apuestas (manuales o scrapeadas)
  3. Calcula: implied_prob = 1/odds  →  ev = prob_model * odds - 1
  4. Reporta apuestas con EV > MIN_EV
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MIN_EV, MIN_PROB_MODEL, MIN_ODDS, MAX_ODDS


# ── Tipos de apuestas soportados ───────────────────────────────────────────────

BET_MAP = {
    # (clave_modelo, nombre_display)
    "1":        ("prob_home",   "Victoria Local"),
    "X":        ("prob_draw",   "Empate"),
    "2":        ("prob_away",   "Victoria Visitante"),
    "O0.5":     ("over_0.5",    "Over 0.5"),
    "O1.5":     ("over_1.5",    "Over 1.5"),
    "O2.5":     ("over_2.5",    "Over 2.5"),
    "O3.5":     ("over_3.5",    "Over 3.5"),
    "U0.5":     ("under_0.5",   "Under 0.5"),
    "U1.5":     ("under_1.5",   "Under 1.5"),
    "U2.5":     ("under_2.5",   "Under 2.5"),
    "U3.5":     ("under_3.5",   "Under 3.5"),
    "BTTS_Y":   ("btts_yes",    "Ambos Marcan - Sí"),
    "BTTS_N":   ("btts_no",     "Ambos Marcan - No"),
}


def _implied_prob(odds: float) -> float:
    """Probabilidad implícita sin eliminar el vig."""
    return 1.0 / max(odds, 1.001)


def _ev(prob_model: float, odds: float) -> float:
    """Expected Value: retorno esperado por unidad apostada."""
    return prob_model * odds - 1.0


def analyze_fixture(prediction: dict, odds: dict,
                    home_team: str = "", away_team: str = "",
                    date: str = "", competition: str = "",
                    confianza: str = "ALTA") -> list[dict]:
    
    # No reportar value bets si la confianza es baja
    if confianza == "BAJA":
        return []
    
    # Si confianza es MEDIA, subir el umbral de EV requerido
    ev_threshold = MIN_EV if confianza == "ALTA" else MIN_EV * 1.5
    
    results = []
    for bet_key, odds_val in odds.items():
        if bet_key not in BET_MAP:
            continue
        model_key, bet_name = BET_MAP[bet_key]
        if model_key not in prediction:
            continue

        prob_model  = prediction[model_key]
        prob_impl   = _implied_prob(odds_val)
        ev          = _ev(prob_model, odds_val)
        edge        = prob_model - prob_impl

        if (ev >= ev_threshold
                and prob_model >= MIN_PROB_MODEL
                and MIN_ODDS <= odds_val <= MAX_ODDS):
            results.append({
                "date":         date,
                "competition":  competition,
                "home_team":    home_team,
                "away_team":    away_team,
                "bet_type":     bet_key,
                "bet_name":     bet_name,
                "odds":         round(odds_val, 2),
                "prob_model":   round(prob_model, 4),
                "prob_implied": round(prob_impl, 4),
                "edge":         round(edge, 4),
                "ev":           round(ev, 4),
                "ev_pct":       f"{ev:.1%}",
                "confianza":    confianza,
                "rating":       _rating(ev, edge),
            })

    results.sort(key=lambda x: -x["ev"])
    return results


def _rating(ev: float, edge: float) -> str:
    """Rating cualitativo de la apuesta."""
    score = ev * 0.6 + edge * 0.4
    if   score >= 0.12: return "⭐⭐⭐ FUERTE"
    elif score >= 0.07: return "⭐⭐ BUENA"
    elif score >= 0.04: return "⭐ MODERADA"
    else:               return "— DÉBIL"


def analyze_matchday(fixtures_with_odds: list[dict],
                     predictions: dict) -> pd.DataFrame:
    """
    fixtures_with_odds: lista de {home_team, away_team, date, competition, odds: {...}}
    predictions: {(home_team, away_team): prediction_dict}
    
    Retorna DataFrame con todas las value bets del día.
    """
    all_bets = []
    for f in fixtures_with_odds:
        key = (f["home_team"], f["away_team"])
        pred = predictions.get(key)
        if not pred:
            continue
        bets = analyze_fixture(
            prediction   = pred,
            odds         = f.get("odds", {}),
            home_team    = f["home_team"],
            away_team    = f["away_team"],
            date         = f.get("date", ""),
            competition  = f.get("competition", ""),
        )
        all_bets.extend(bets)

    if not all_bets:
        return pd.DataFrame()

    df = pd.DataFrame(all_bets)
    df = df.sort_values(["date", "ev"], ascending=[True, False])
    return df


def print_value_bets(df: pd.DataFrame):
    """Imprime tabla de value bets en consola."""
    if df.empty:
        print("No se encontraron value bets con los filtros actuales.")
        return

    print(f"\n{'='*80}")
    print(f"  VALUE BETS ENCONTRADAS: {len(df)}")
    print(f"{'='*80}")

    for comp, grp in df.groupby("competition"):
        print(f"\n📋 {comp}")
        print(f"  {'Partido':<35} {'Apuesta':<20} {'Cuota':>6} {'PModelo':>8} {'PImpl':>8} {'EV':>7} {'Rating'}")
        print(f"  {'-'*100}")
        for _, r in grp.iterrows():
            match = f"{r['home_team']} vs {r['away_team']}"[:34]
            print(f"  {match:<35} {r['bet_name']:<20} {r['odds']:>6.2f} "
                  f"{r['prob_model']:>8.1%} {r['prob_implied']:>8.1%} "
                  f"{r['ev']:>7.1%} {r['rating']}")


# ── Kelly Criterion ────────────────────────────────────────────────────────────

def kelly_fraction(prob_model: float, odds: float,
                   fraction: float = 0.25) -> float:
    """
    Kelly fraccionario para sizing de apuesta.
    fraction=0.25 → Quarter Kelly (más conservador, recomendado)
    
    Retorna % del bankroll a apostar.
    """
    b = odds - 1
    q = 1 - prob_model
    k = (b * prob_model - q) / b
    k = max(k, 0.0)
    return round(k * fraction, 4)


def add_kelly(df: pd.DataFrame) -> pd.DataFrame:
    """Añade columna kelly_pct al DataFrame de value bets."""
    if df.empty:
        return df
    df = df.copy()
    df["kelly_pct"] = df.apply(
        lambda r: kelly_fraction(r["prob_model"], r["odds"]), axis=1
    )
    df["kelly_pct_str"] = df["kelly_pct"].apply(lambda x: f"{x:.1%}")
    return df


# ── Demo ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulación de una predicción
    fake_pred = {
        "prob_home": 0.52, "prob_draw": 0.26, "prob_away": 0.22,
        "over_2.5": 0.58, "under_2.5": 0.42,
        "btts_yes": 0.54, "btts_no": 0.46,
        "over_1.5": 0.78, "over_3.5": 0.32,
        "lambda_home": 1.75, "lambda_away": 1.10,
    }
    # Cuotas de ejemplo (Bet365-style)
    fake_odds = {
        "1": 2.10, "X": 3.40, "2": 3.60,
        "O2.5": 1.75, "U2.5": 2.05,
        "BTTS_Y": 1.80, "BTTS_N": 1.95,
    }

    bets = analyze_fixture(fake_pred, fake_odds,
                           home_team="Arsenal", away_team="Chelsea",
                           date="2025-03-15", competition="Premier League")

    df = pd.DataFrame(bets)
    df = add_kelly(df)

    if not df.empty:
        print(df[["bet_name", "odds", "prob_model", "prob_implied",
                   "ev_pct", "rating", "kelly_pct_str"]].to_string(index=False))
    else:
        print("Sin value bets en este partido.")
