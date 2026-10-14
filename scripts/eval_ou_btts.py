"""
Walk-forward de mercados de goles: Over/Under 2.5 y BTTS.
Compara contra cuotas de cierre cuando están disponibles.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.evaluation import (
    walk_forward_markets,
    metrics_ou_market,
    metrics_btts_market,
)


def main():
    df = pd.read_parquet("data/processed/history_with_xg.parquet")
    seasons = ["2024", "2025"]

    preds = walk_forward_markets(
        df,
        seasons=seasons,
        competition="PL",
        rho=-0.13,
        min_train_matches=200,
    )

    if preds.empty:
        print("Sin predicciones. Revisa filtros.")
        return

    preds.to_csv("output/eval_ou_btts_predictions.csv", index=False)

    print("\n=== Over/Under 2.5 (modelo vs cuotas) ===")
    m_ou = metrics_ou_market(preds)
    print(m_ou.round(4).to_string(index=False))
    m_ou.to_csv("output/eval_ou_metrics.csv", index=False)

    print("\n=== BTTS (modelo vs baseline) ===")
    m_btts = metrics_btts_market(preds)
    print(m_btts.round(4).to_string(index=False))
    m_btts.to_csv("output/eval_btts_metrics.csv", index=False)

    # Diagnóstico: media del modelo vs frecuencia real
    print("\n=== Diagnóstico global ===")
    y_over = (preds["total_goals"] >= 3).astype(int)
    y_btts = preds["btts_actual"]
    print(f"P(over 2.5) media modelo:  {preds['prob_over_25'].mean():.3f}")
    print(f"Frecuencia real over 2.5:  {y_over.mean():.3f}")
    print(f"P(BTTS yes) media modelo:  {preds['prob_btts_yes'].mean():.3f}")
    print(f"Frecuencia real BTTS:      {y_btts.mean():.3f}")

    # Comparación con cuotas de cierre
    mask = preds["odds_over_25_close"].notna() & preds["odds_under_25_close"].notna()
    if mask.sum() > 0:
        p_over_mkt = 1.0 / preds.loc[mask, "odds_over_25_close"]
        p_under_mkt = 1.0 / preds.loc[mask, "odds_under_25_close"]
        p_over_mkt_norm = (p_over_mkt / (p_over_mkt + p_under_mkt)).mean()
        print(f"P(over 2.5) implícita cuotas cierre: {p_over_mkt_norm:.3f}")
        print(f"N partidos con cuotas cierre: {mask.sum()}")


if __name__ == "__main__":
    main()