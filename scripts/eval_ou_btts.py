"""
Walk-forward de mercados de goles: Over/Under 2.5 y BTTS.
Incluye corrección de sesgo walk-forward.
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
    bias_corrected_markets,
    metrics_ou_corrected,
    metrics_btts_corrected,
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

    # ── 1. Baseline sin corregir ──────────────────────────────────────
    print("\n=== O/U 2.5 — Baseline (raw) ===")
    m_ou_raw = metrics_ou_market(preds)
    print(m_ou_raw.round(4).to_string(index=False))

    print("\n=== BTTS — Baseline (raw) ===")
    m_btts_raw = metrics_btts_market(preds)
    print(m_btts_raw.round(4).to_string(index=False))

    # ── 2. Corrección walk-forward ────────────────────────────────────
    preds_corr = bias_corrected_markets(preds, seasons=seasons)
    preds_corr.to_csv("output/eval_ou_btts_predictions_corrected.csv", index=False)

    print("\n=== O/U 2.5 — Corrección walk-forward ===")
    m_ou_corr = metrics_ou_corrected(preds_corr)
    print(m_ou_corr.round(4).to_string(index=False))
    m_ou_corr.to_csv("output/eval_ou_metrics_corrected.csv", index=False)

    print("\n=== BTTS — Corrección walk-forward ===")
    m_btts_corr = metrics_btts_corrected(preds_corr)
    print(m_btts_corr.round(4).to_string(index=False))
    m_btts_corr.to_csv("output/eval_btts_metrics_corrected.csv", index=False)

    # ── 3. Diagnóstico global ─────────────────────────────────────────
    print("\n=== Diagnóstico ===")
    y_over = (preds["total_goals"] >= 3).astype(int)
    y_btts = preds["btts_actual"]
    print(f"P(over 2.5) media modelo:  {preds['prob_over_25'].mean():.3f}")
    print(f"Frecuencia real over 2.5:  {y_over.mean():.3f}")
    print(f"P(BTTS yes) media modelo:  {preds['prob_btts_yes'].mean():.3f}")
    print(f"Frecuencia real BTTS:      {y_btts.mean():.3f}")


if __name__ == "__main__":
    main()