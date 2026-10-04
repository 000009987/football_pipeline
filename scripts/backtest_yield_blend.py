# scripts/backtest_yield_blend.py
"""
Compara YIELD (con cuotas reales) entre:
  - Goles puros (baseline)
  - xG puro
  - Blend (goles+xG)/2

En las 5 grandes ligas.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.backtester import run_backtest  # noqa: E402

HIST = Path("data/processed/history_with_xg.parquet")
LEAGUES = ["PL", "PD", "SA", "BL1", "FL1"]
CONFIGS = [
    {"name": "GOALS", "col_home": "home_goals", "col_away": "away_goals", "rho": -0.13},
    {"name": "XG",    "col_home": "home_xg",    "col_away": "away_xg",    "rho": -0.25},
    {"name": "BLEND", "col_home": "home_blend", "col_away": "away_blend", "rho": -0.15},
]


def main():
    df_all = pd.read_parquet(HIST)
    df_all["home_blend"] = (df_all["home_goals"] + df_all["home_xg"]) / 2
    df_all["away_blend"] = (df_all["away_goals"] + df_all["away_xg"]) / 2

    print(f"{'Liga':<6} {'Modo':<7} {'#bets':>6} {'yield':>10} {'logloss':>9} {'acc':>8}")
    print("-" * 52)

    for comp in LEAGUES:
        df = df_all[df_all["competition"] == comp].copy()
        if len(df) < 200:
            continue
        for cfg in CONFIGS:
            res = run_backtest(
                df,
                test_fraction=0.30,
                rho=cfg["rho"],
                col_home=cfg["col_home"],
                col_away=cfg["col_away"],
                verbose=False,
            )
            if "error" in res:
                continue
            print(f"{comp:<6} {cfg['name']:<7} {res['n_bets']:>6} "
                  f"{res['yield_per_bet']:>+9.2%} "
                  f"{res['log_loss_dc']:>9.4f} "
                  f"{res['accuracy_dc']:>7.1%}")
        print()


if __name__ == "__main__":
    main()