"""
Backtest walk-forward multi-liga con/sin corrección Dixon-Coles.
Prueba múltiples valores de rho para encontrar el óptimo.
Modos: goals, xg, blend.
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
COMPETITIONS = ["PL", "PD", "SA", "BL1", "FL1"]


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


def run_league(df_all, comp, mode, rhos):
    """Devuelve mejor log_loss y su rho para una liga y modo."""
    df = df_all[df_all["competition"] == comp].copy()
    if len(df) < 200:
        return None
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
    df = df.sort_values("date").reset_index(drop=True)

    results = []
    for rho in rhos:
        r = run_backtest(df, mode, rho=rho)
        results.append(r)
    res = pd.DataFrame(results)
    best = res.loc[res["log_loss"].idxmin()]
    return {
        "competition": comp,
        "mode": mode,
        "best_rho": best["rho"],
        "log_loss": best["log_loss"],
        "accuracy": best["accuracy"],
        "n_test": best["n"],
    }


def main():
    df_all = pd.read_parquet(HIST)
    df_all["home_blend"] = (df_all["home_goals"] + df_all["home_xg"]) / 2
    df_all["away_blend"] = (df_all["away_goals"] + df_all["away_xg"]) / 2

    rhos = [0.0, -0.05, -0.10, -0.15, -0.18, -0.20, -0.22, -0.25, -0.30]

    all_results = []
    for comp in COMPETITIONS:
        for mode in ["goals", "xg", "blend"]:
            print(f"  {comp} / {mode} ...")
            r = run_league(df_all, comp, mode, rhos)
            if r:
                all_results.append(r)

    res = pd.DataFrame(all_results)
    print()
    print("=" * 70)
    print("  MEJOR LOG-LOSS POR (LIGA, MODO)")
    print("=" * 70)
    pivot_ll = res.pivot(index="competition", columns="mode", values="log_loss")
    print(pivot_ll.round(4).to_string())
    print()
    print("=" * 70)
    print("  MEJOR RHO POR (LIGA, MODO)")
    print("=" * 70)
    pivot_rho = res.pivot(index="competition", columns="mode", values="best_rho")
    print(pivot_rho.to_string())
    print()
    print("=" * 70)
    print("  MEJOR ACCURACY POR (LIGA, MODO)")
    print("=" * 70)
    pivot_acc = res.pivot(index="competition", columns="mode", values="accuracy")
    print(pivot_acc.round(4).to_string())
    print()
    print("=" * 70)
    print("  RESUMEN: MEDIA DE LOG-LOSS POR MODO")
    print("=" * 70)
    print(res.groupby("mode")["log_loss"].agg(["mean", "min", "max"]).round(4).to_string())
    print()
    print(f"Referencia mercado: log_loss ≈ 0.95-1.00")


if __name__ == "__main__":
    main()