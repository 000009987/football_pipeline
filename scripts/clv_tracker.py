"""
CLV tracker: mide si las value bets del modelo cierran a mejor precio.

Regla:
  - Apostamos con cuota de APERTURA si EV = p*(odds-1) - (1-p) > umbral.
  - Comparamos con cuota de CIERRE.
  - CLV positivo => edge real.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from src.feature_engineering import enrich_fixture
from src.models import score_matrix_dixon_coles, market_probabilities
from src.evaluation import _ou_btts_from_matrix, _actual_result


def _first_available(row, cols):
    for c in cols:
        if c in row.index:
            v = row[c]
            if pd.notna(v):
                return float(v)
    return np.nan


def walk_forward_clv(df, seasons, competition="PL", rho=-0.13, min_train_matches=200):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["season"] = df["season"].astype(str)
    df = df.sort_values("date").reset_index(drop=True)
    if competition is not None:
        df = df[df["competition"] == competition].reset_index(drop=True)

    seasons = [str(s) for s in seasons]
    rows = []

    for season in seasons:
        train = df[df["season"] < season]
        test = df[df["season"] == season]
        if len(train) < min_train_matches or len(test) == 0:
            continue

        for _, row in test.iterrows():
            try:
                f = enrich_fixture(row, train, as_of_date=row["date"])
                matrix = score_matrix_dixon_coles(f["lambda_home"], f["lambda_away"], rho=rho)
                p1x2 = market_probabilities(matrix)
                pou = _ou_btts_from_matrix(matrix)
            except Exception:
                continue

            open_h = _first_available(row, ["PSH", "AvgH", "BFDH", "BWH", "BVH", "LBH"])
            open_d = _first_available(row, ["PSD", "AvgD", "BFDD", "BWD", "BVD", "LBD"])
            open_a = _first_available(row, ["PSA", "AvgA", "BFDA", "BWA", "BVA", "LBA"])
            close_h = _first_available(row, ["PSCH", "AvgCH", "BFDCH", "BWCH", "BVCH", "LBCH"])
            close_d = _first_available(row, ["PSCD", "AvgCD", "BFDCD", "BWCD", "BVCD", "LBCD"])
            close_a = _first_available(row, ["PSCA", "AvgCA", "BFDCA", "BWCA", "BVCA", "LBCA"])

            open_over = _first_available(row, ["P>2.5", "Avg>2.5", "B365>2.5", "BFE>2.5"])
            open_under = _first_available(row, ["P<2.5", "Avg<2.5", "B365<2.5", "BFE<2.5"])
            close_over = _first_available(row, ["PC>2.5", "AvgC>2.5", "B365C>2.5", "BFEC>2.5"])
            close_under = _first_available(row, ["PC<2.5", "AvgC<2.5", "B365C<2.5", "BFEC<2.5"])

            actual_1x2 = _actual_result(row)
            total_goals = int(row["home_goals"] + row["away_goals"])

            rows.append({
                "season": season,
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "prob_H": p1x2["prob_home"],
                "prob_D": p1x2["prob_draw"],
                "prob_A": p1x2["prob_away"],
                "prob_over_25": pou["prob_over_25"],
                "prob_under_25": pou["prob_under_25"],
                "actual_1x2": actual_1x2,
                "total_goals": total_goals,
                "over_25_real": int(total_goals >= 3),
                "open_h": open_h, "open_d": open_d, "open_a": open_a,
                "close_h": close_h, "close_d": close_d, "close_a": close_a,
                "open_over": open_over, "open_under": open_under,
                "close_over": close_over, "close_under": close_under,
            })

    return pd.DataFrame(rows)


def evaluate_market(preds, market, prob_col, open_col, close_col, actual_col, ev_threshold=0.05):
    mask = preds[open_col].notna() & preds[close_col].notna() & preds[prob_col].notna()
    sub = preds[mask]
    if len(sub) == 0:
        return None

    p = sub[prob_col].values
    odds_open = sub[open_col].values
    odds_close = sub[close_col].values
    y = sub[actual_col].values

    ev = p * (odds_open - 1) - (1 - p)
    bets = ev > ev_threshold
    n_bets = int(bets.sum())
    if n_bets == 0:
        return {"market": market, "ev_threshold": ev_threshold, "n_bets": 0,
                "clv_mean": np.nan, "clv_pos_pct": np.nan, "yield": np.nan}

    odds_open_b = odds_open[bets]
    odds_close_b = odds_close[bets]
    y_b = y[bets]

    clv_pct = (odds_open_b / odds_close_b - 1.0) * 100.0
    pnl = np.where(y_b == 1, odds_open_b - 1.0, -1.0)

    return {
        "market": market,
        "ev_threshold": ev_threshold,
        "n_bets": n_bets,
        "clv_mean": clv_pct.mean(),
        "clv_pos_pct": (clv_pct > 0).mean() * 100.0,
        "yield": pnl.mean() * 100.0,
    }


def main():
    df = pd.read_parquet("data/processed/history_with_xg.parquet")
    seasons = ["2024", "2025"]

    print("Corriendo walk-forward para CLV...")
    preds = walk_forward_clv(df, seasons=seasons, competition="PL", rho=-0.13)
    if preds.empty:
        print("Sin predicciones.")
        return

    preds.to_csv("output/clv_predictions.csv", index=False)
    print(f"Total partidos: {len(preds)}\n")

    preds["H_real"] = (preds["actual_1x2"] == "H").astype(int)
    preds["D_real"] = (preds["actual_1x2"] == "D").astype(int)
    preds["A_real"] = (preds["actual_1x2"] == "A").astype(int)
    preds["under_25_real"] = 1 - preds["over_25_real"]

    markets = [
        ("1X2 Home",   "prob_H",        "open_h",     "close_h",     "H_real"),
        ("1X2 Draw",   "prob_D",        "open_d",     "close_d",     "D_real"),
        ("1X2 Away",   "prob_A",        "open_a",     "close_a",     "A_real"),
        ("Over 2.5",   "prob_over_25",  "open_over",  "close_over",  "over_25_real"),
        ("Under 2.5",  "prob_under_25","open_under", "close_under", "under_25_real"),
    ]

    thresholds = [0.03, 0.05, 0.08, 0.10]
    results = []
    for market, prob_col, open_col, close_col, actual_col in markets:
        for th in thresholds:
            r = evaluate_market(preds, market, prob_col, open_col, close_col, actual_col, ev_threshold=th)
            if r:
                results.append(r)

    res_df = pd.DataFrame(results)
    res_df.to_csv("output/clv_summary.csv", index=False)

    print("=== CLV por mercado y umbral de EV ===")
    print(res_df.round(3).to_string(index=False))
    print()
    print("Interpretación:")
    print("  n_bets      = nº apuestas detectadas")
    print("  clv_mean    = movimiento medio de cuota a favor (%). >0 => edge")
    print("  clv_pos_pct = % apuestas con CLV positivo. >50% => edge")
    print("  yield       = retorno simulado con stake plano (%)")


if __name__ == "__main__":
    main()