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
    walk_forward_with_calibration,
    metrics_calibrated_vs_raw,
)
from src.calibration import (
    PlattCalibrator,
    IsotonicCalibrator,
    TemperatureCalibrator,
)


def main():
    df = pd.read_parquet("data/processed/history_with_xg.parquet")
    seasons = ["2024", "2025"]

    # ── 1. Walk-forward sin calibrar ─────────────────────────────────
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
    print("\n=== Métricas por temporada (raw) ===")
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

    # ── 2. Calibración Platt ─────────────────────────────────────────
    print("\n=== Walk-forward CON calibración (Platt) ===")
    preds_platt = walk_forward_with_calibration(
        df,
        seasons=seasons,
        calibrator_factory=PlattCalibrator,
        competition="PL",
        rho=-0.13,
        model="dixon_coles",
        min_train_matches=200,
    )
    metrics_platt = metrics_calibrated_vs_raw(preds_platt)
    print(metrics_platt.round(4).to_string(index=False))
    preds_platt.to_csv("output/eval_walk_forward_platt.csv", index=False)
    metrics_platt.to_csv("output/eval_calibration_platt.csv", index=False)

    # ── 3. Calibración Isotonic ──────────────────────────────────────
    print("\n=== Walk-forward CON calibración (Isotonic) ===")
    preds_iso = walk_forward_with_calibration(
        df,
        seasons=seasons,
        calibrator_factory=IsotonicCalibrator,
        competition="PL",
        rho=-0.13,
        model="dixon_coles",
        min_train_matches=200,
    )
    metrics_iso = metrics_calibrated_vs_raw(preds_iso)
    print(metrics_iso.round(4).to_string(index=False))
    preds_iso.to_csv("output/eval_walk_forward_isotonic.csv", index=False)
    metrics_iso.to_csv("output/eval_calibration_isotonic.csv", index=False)

    # ── 4. Calibración Temperature ───────────────────────────────────
    print("\n=== Walk-forward CON temperature scaling ===")
    preds_temp = walk_forward_with_calibration(
        df,
        seasons=seasons,
        calibrator_factory=TemperatureCalibrator,
        competition="PL",
        rho=-0.13,
        model="dixon_coles",
        min_train_matches=200,
    )
    metrics_temp = metrics_calibrated_vs_raw(preds_temp)
    print(metrics_temp.round(4).to_string(index=False))
    preds_temp.to_csv("output/eval_walk_forward_temperature.csv", index=False)
    metrics_temp.to_csv("output/eval_calibration_temperature.csv", index=False)

    # Mostrar la temperatura ajustada por temporada (informativo)
    order = {"H": 0, "D": 1, "A": 2}
    for season in seasons[1:]:
        idx = seasons.index(season)
        train_cal = preds_temp[preds_temp["season"].isin(seasons[:idx])]
        if len(train_cal) < 50:
            continue
        X = train_cal[["prob_H", "prob_D", "prob_A"]].values
        y = train_cal["actual"].map(order).values
        cal = TemperatureCalibrator().fit(X, y)
        print(f"  T ajustada para {season}: {cal.T:.4f}")


if __name__ == "__main__":
    main()