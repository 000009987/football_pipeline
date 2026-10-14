"""
Evaluación walk-forward por temporada del modelo Dixon-Coles.
Sustituye el split 70/30 por walk-forward honesto.
"""
import sys
from pathlib import Path

# Añade la raíz del proyecto al sys.path para poder importar `src.*`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.evaluation import (
    walk_forward_by_season,
    metrics_by_season,
    reliability_curve,
)


def main():
    df = pd.read_parquet("data/processed/history_with_xg.parquet")

    seasons = ["2024", "2025"]

    preds = walk_forward_by_season(
        df,
        seasons=seasons,
        competition="PL",
        rho=-0.13,
        model="dixon_coles",
        min_train_matches=200,
    )

    if preds.empty:
        print("Sin predicciones. Revisa seasons, competition o min_train_matches.")
        return

    preds.to_csv("output/eval_walk_forward_predictions.csv", index=False)

    metrics = metrics_by_season(preds)
    print("\n=== Métricas por temporada ===")
    print(metrics.round(4).to_string(index=False))
    metrics.to_csv("output/eval_walk_forward_metrics.csv", index=False)

    y_H = (preds["actual"] == "H").astype(int).values
    curve = reliability_curve(preds["prob_H"].values, y_H, n_bins=10)
    print("\n=== Curva de fiabilidad P(H) ===")
    print(curve.round(3).to_string(index=False))

    if preds["odds_home"].notna().any():
        mask = preds["odds_home"].notna()
        implied = 1.0 / preds.loc[mask, "odds_home"].values
        mean_prob = preds.loc[mask, "prob_H"].mean()
        mean_implied = implied.mean()
        print(f"\nP(H) media modelo: {mean_prob:.3f}")
        print(f"P(H) implícita cuotas: {mean_implied:.3f}")
        print(f"Sesgo: {mean_prob - mean_implied:+.3f}")


if __name__ == "__main__":
    main()