"""Chequeo temporal: CLV por liga para 1X2 Draw y Under 2.5."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from scripts.clv_tracker import walk_forward_clv, evaluate_market


def main():
    df = pd.read_parquet("data/processed/history_with_xg.parquet")
    seasons = ["2024", "2025"]

    markets_short = [
        ("1X2 Draw",  "prob_D",         "open_d",     "close_d",     "D_real"),
        ("Under 2.5", "prob_under_25",  "open_under", "close_under", "under_25_real"),
    ]

    print("=== CLV por liga (umbral EV 5%) ===\n")
    print(f"{'Liga':>5}  {'Mercado':>12}  {'n':>4}  {'CLV':>8}  {'CLV+':>7}  {'Yield':>8}")
    print("-" * 60)

    for comp in ["PL", "BL1", "PD", "SA", "FL1", "DED", "PPL"]:
        p = walk_forward_clv(df, seasons=seasons, competition=comp, rho=-0.13)
        if p.empty:
            print(f"{comp:>5}  sin datos")
            continue
        p["H_real"] = (p["actual_1x2"] == "H").astype(int)
        p["D_real"] = (p["actual_1x2"] == "D").astype(int)
        p["A_real"] = (p["actual_1x2"] == "A").astype(int)
        p["under_25_real"] = 1 - p["over_25_real"]

        for market, prob_col, open_col, close_col, actual_col in markets_short:
            r = evaluate_market(p, market, prob_col, open_col, close_col, actual_col, ev_threshold=0.05)
            if r and r["n_bets"] > 0:
                print(f"{comp:>5}  {market:>12}  {r['n_bets']:>4}  "
                      f"{r['clv_mean']:>+8.3f}  {r['clv_pos_pct']:>6.1f}%  {r['yield']:>+7.2f}%")


if __name__ == "__main__":
    main()