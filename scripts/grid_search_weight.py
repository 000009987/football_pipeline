"""
Grid search de regress_weight en enrich_fixture.

Para cada weight ∈ {4, 6, 8, 12, 16}, ejecuta walk-forward sobre las 7 ligas
y guarda el Brier agregado. Compara con el baseline actual (weight=12).

Uso: python scripts/grid_search_weight.py
"""
import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR, EVAL_LEAGUES
from src.feature_engineering import enrich_fixture
from src.models import predict_match
from src.logger import get_logger

logger = get_logger("grid_weight")

ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"
RHO_CACHE = OUTPUT_DIR / "rho_cache.json"
TEST_SEASONS = ["2025", "2026"]
MIN_TRAIN = 100
WEIGHTS = [4, 6, 8, 12, 16]


def brier_multiclass(y_idx, probs):
    total = 0.0
    for k in range(3):
        y_bin = (y_idx == k).astype(float)
        total += ((probs[:, k] - y_bin) ** 2).mean()
    return total / 3


def run_for_weight(history, rho_cache, weight):
    """Ejecuta walk-forward completo con un weight concreto. Devuelve Brier agregado."""
    rows = []
    for league in EVAL_LEAGUES:
        rho = float(rho_cache.get(league, {}).get("rho", -0.13))
        league_df = history[history["competition"] == league].sort_values("date")

        for season in TEST_SEASONS:
            train = league_df[league_df["season"].astype(str) < season]
            test = league_df[league_df["season"].astype(str) == season]
            if len(train) < MIN_TRAIN or len(test) == 0:
                continue

            for _, row in test.iterrows():
                try:
                    f = enrich_fixture(row, train, as_of_date=row["date"],
                                       regress_weight=weight)
                    p = predict_match(f["lambda_home"], f["lambda_away"],
                                      rho=rho, model="dixon_coles")
                    actual = "H" if row["home_goals"] > row["away_goals"] else (
                        "D" if row["home_goals"] == row["away_goals"] else "A"
                    )
                    rows.append({"prob_H": p["prob_home"], "prob_D": p["prob_draw"],
                                 "prob_A": p["prob_away"], "actual": actual})
                except Exception:
                    continue

    if not rows:
        return None, 0

    df = pd.DataFrame(rows)
    y = df["actual"].map({"H": 0, "D": 1, "A": 2}).values
    probs = df[["prob_H", "prob_D", "prob_A"]].values
    return brier_multiclass(y, probs), len(df)


def main():
    with RHO_CACHE.open() as f:
        rho_cache = json.load(f).get("leagues", {})

    history = pd.read_parquet(ENRICHED)
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)

    print(f"{'weight':>8} | {'Brier':>8} | {'n':>6}")
    print("-" * 30)

    results = {}
    for w in WEIGHTS:
        brier, n = run_for_weight(history, rho_cache, w)
        if brier is None:
            print(f"{w:>8} | ERROR")
            continue
        results[w] = brier
        print(f"{w:>8} | {brier:>8.4f} | {n:>6}")

    print()
    baseline = results.get(12)
    if baseline is not None:
        print(f"{'weight':>8} | {'Δ vs 12':>10} | {'Veredicto':>15}")
        print("-" * 40)
        for w, b in sorted(results.items()):
            delta = b - baseline
            if w == 12:
                veredicto = "(baseline)"
            elif delta < -0.005:
                veredicto = "MEJORA real"
            elif delta > 0.005:
                veredicto = "PEOR"
            else:
                veredicto = "ruido"
            print(f"{w:>8} | {delta:>+10.4f} | {veredicto:>15}")


if __name__ == "__main__":
    main()