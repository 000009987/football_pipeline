"""
Grid search de regress_weight en enrich_fixture.

Para cada weight ∈ {4, 6, 8, 12, 16}, ejecuta walk-forward sobre las 7 ligas
con rho estimado walk-forward por liga/temporada (sin leakage).

Uso: python scripts/grid_search_weight.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.config import PROCESSED_DATA_DIR, EVAL_LEAGUES
from src.feature_engineering import enrich_fixture
from src.models import predict_match, estimate_rho
from src.logger import get_logger

logger = get_logger("grid_weight")

ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"
TEST_SEASONS = ["2025", "2026"]
MIN_TRAIN = 100
MIN_RHO_LAMBDAS = 50
N_RHO_MATCHES = 300
WEIGHTS = [4, 6, 8, 12, 16]


def brier_multiclass(y_idx, probs):
    total = 0.0
    for k in range(3):
        y_bin = (y_idx == k).astype(float)
        total += ((probs[:, k] - y_bin) ** 2).mean()
    return total / 3


def compute_rho_walk_forward(train_df, n_matches=N_RHO_MATCHES):
    """Estima rho con SOLO train_df (walk-forward interno, sin leakage)."""
    if len(train_df) < MIN_TRAIN:
        return -0.13, 0

    sample = train_df.sort_values("date").tail(n_matches).copy()
    rows = []
    for _, match in sample.iterrows():
        history = train_df[train_df["date"] < match["date"]]
        if len(history) < 10:
            continue
        try:
            f = enrich_fixture(match, history, as_of_date=match["date"])
            rows.append({
                "lambda_home": f["lambda_home"],
                "lambda_away": f["lambda_away"],
                "home_goals": int(match["home_goals"]),
                "away_goals": int(match["away_goals"]),
            })
        except Exception:
            continue

    if len(rows) < MIN_RHO_LAMBDAS:
        return -0.13, len(rows)

    return estimate_rho(pd.DataFrame(rows)), len(rows)


def run_for_weight(history, weight):
    """Ejecuta walk-forward completo con un weight concreto. rho walk-forward por liga/temporada."""
    rows = []
    for league in EVAL_LEAGUES:
        league_df = history[history["competition"] == league].sort_values("date")

        for season in TEST_SEASONS:
            train = league_df[league_df["season"].astype(str) < season].copy()
            test = league_df[league_df["season"].astype(str) == season].copy()
            if len(train) < MIN_TRAIN or len(test) == 0:
                continue

            rho, n_lambdas = compute_rho_walk_forward(train, n_matches=N_RHO_MATCHES)
            logger.info(f"[{league}/{season}] rho={rho:+.4f} (n_lambdas={n_lambdas})")

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
    history = pd.read_parquet(ENRICHED)
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)

    print(f"{'weight':>8} | {'Brier':>8} | {'n':>6}")
    print("-" * 30)

    results = {}
    for w in WEIGHTS:
        brier, n = run_for_weight(history, w)
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