"""
Backtest walk-forward PL con/sin corrección Dixon-Coles.
Prueba múltiples valores de rho para encontrar el óptimo.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import poisson

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.feature_engineering import compute_ratings_for_team  # noqa: E402
from config import HOME_ADVANTAGE  # noqa: E402

HIST = Path("data/processed/history_with_xg.parquet")
MAX_GOALS = 10
TEST_SEASONS = [2024, 2025]


# ─────────────────────────────────────────────────────────────────
#  Dixon-Coles τ
# ─────────────────────────────────────────────────────────────────
def tau(x, y, lh, la, rho):
    if x == 0 and y == 0: return 1 - lh * la * rho
    if x == 0 and y == 1: return 1 + lh * rho
    if x == 1 and y == 0: return 1 + la * rho
    if x == 1 and y == 1: return 1 - rho
    return 1.0


def predict_probs(lh, la, rho=0.0):
    """Probabilidades 1X2 con Poisson + corrección Dixon-Coles opcional."""
    k = np.arange(MAX_GOALS + 1)
    p_h = poisson.pmf(k, lh)
    p_a = poisson.pmf(k, la)
    M = np.outer(p_h, p_a)

    if rho != 0.0:
        for x in (0, 1):
            for y in (0, 1):
                M[x, y] *= tau(x, y, lh, la, rho)
        M = M / M.sum()

    pH = np.tril(M, -1).sum()
    pD = np.trace(M)
    pA = np.triu(M, 1).sum()
    s = pH + pD + pA
    return pH / s, pD / s, pA / s


def lambdas_from_ratings(hr, ar):
    lh = hr["att_home"] * ar["def_away"] * hr["lg_avg_home"] * HOME_ADVANTAGE
    la = ar["att_away"] * hr["def_home"] * ar["lg_avg_away"]
    return float(np.clip(lh, 0.4, 4.0)), float(np.clip(la, 0.4, 4.0))


def true_class(hg, ag):
    if hg > ag:  return 0
    if hg == ag: return 1
    return 2


def run_backtest(df, mode, rho=0.0):
    if mode == "goals":
        col_h, col_a = "home_goals", "away_goals"
    elif mode == "xg":
        col_h, col_a = "home_xg", "away_xg"
    elif mode == "blend":
        col_h, col_a = "home_blend", "away_blend"
    else:
        raise ValueError(mode)

    cache = {}
    def ratings(team, date):
        key = (team, date)
        if key not in cache:
            cache[key] = compute_ratings_for_team(
                team, df, as_of_date=date,
                col_home=col_h, col_away=col_a,
            )
        return cache[key]

    test = df[df["season"].isin(TEST_SEASONS)].sort_values("date").reset_index(drop=True)

    losses, correct, skipped = [], [], 0
    for _, row in test.iterrows():
        hr = ratings(row["home_team"], row["date"])
        ar = ratings(row["away_team"], row["date"])
        if (hr["n_home"] + hr["n_away"]) < 5 or (ar["n_home"] + ar["n_away"]) < 5:
            skipped += 1
            continue

        lh, la = lambdas_from_ratings(hr, ar)
        pred = np.array(predict_probs(lh, la, rho=rho))
        pred = pred / pred.sum()

        y = true_class(row["home_goals"], row["away_goals"])
        losses.append(-np.log(max(pred[y], 1e-12)))
        correct.append(int(np.argmax(pred) == y))

    return {
        "mode": mode,
        "rho": rho,
        "n": len(losses),
        "skipped": skipped,
        "log_loss": round(float(np.mean(losses)), 4),
        "accuracy": round(float(np.mean(correct)), 4),
    }


def main():
    df = pd.read_parquet(HIST)
    df = df[df["competition"] == "PL"].copy()
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
    df = df.sort_values("date").reset_index(drop=True)

    df["home_blend"] = (df["home_goals"] + df["home_xg"]) / 2
    df["away_blend"] = (df["away_goals"] + df["away_xg"]) / 2

    test_n = df["season"].isin(TEST_SEASONS).sum()
    print(f"PL total: {len(df)} | test: {test_n} partidos\n")

    rhos = [0.0, -0.03, -0.05, -0.08, -0.10, -0.13, -0.15]
    results = []

    for mode in ["goals", "xg", "blend"]:
        print(f"── mode = {mode} ──")
        for rho in rhos:
            r = run_backtest(df, mode, rho=rho)
            results.append(r)
            print(f"  rho={rho:+.2f}  log_loss={r['log_loss']:.4f}  acc={r['accuracy']:.4f}")
        print()

    res = pd.DataFrame(results)
    print("=== MEJOR RHO POR MODO ===")
    best = res.loc[res.groupby("mode")["log_loss"].idxmin()]
    print(best.to_string(index=False))

    print("\n=== MEJOR GLOBAL ===")
    print(res.loc[res["log_loss"].idxmin()].to_string())
    print(f"\nReferencia mercado: log_loss ≈ 0.95-1.00")


if __name__ == "__main__":
    main()