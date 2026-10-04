import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.feature_engineering import enrich_fixture
from src.models import predict_match
from config import MIN_EV, MAX_EV, MIN_PROB_MODEL, MIN_ODDS, MAX_ODDS


def _result_label(hg: int, ag: int) -> str:
    if hg > ag: return "H"
    if hg < ag: return "A"
    return "D"


def run_backtest(df_history: pd.DataFrame,
                 test_fraction: float = 0.25,
                 rho: float = -0.13,
                 kelly_frac: float = 0.10,
                 initial_bankroll: float = 1000.0,
                 odds_source_cols: tuple = None,
                 col_home: str = "home_goals",
                 col_away: str = "away_goals",
                 verbose: bool = True) -> dict:

    df = df_history.copy().sort_values("date").reset_index(drop=True)

    # Detectar cuotas directamente
    odds_home_col = None
    odds_draw_col = None
    odds_away_col = None
    has_odds      = False

    candidates = [
        ("odds_home", "odds_draw", "odds_away"),
        ("B365H",     "B365D",     "B365A"),
        ("BWH",       "BWD",       "BWA"),
        ("PSH",       "PSD",       "PSA"),
        ("AvgH",      "AvgD",      "AvgA"),
    ]

    if verbose:
        print(f"  Columnas disponibles con 'odds': "
              f"{[c for c in df.columns if 'odds' in c.lower() or c in ['B365H','BWH','PSH','AvgH']]}")

    for h, d, a in candidates:
        if h in df.columns and d in df.columns and a in df.columns:
            test_vals = df[[h, d, a]].dropna()
            if verbose:
                print(f"  Probando {h}/{d}/{a}: {len(test_vals)} filas con datos")
            if len(test_vals) > 5:
                odds_home_col = h
                odds_draw_col = d
                odds_away_col = a
                has_odds      = True
                if verbose:
                    print(f"  ✓ Usando cuotas: {h}, {d}, {a}")
                break

    if not has_odds and verbose:
        print("  ✗ No se encontraron columnas de cuotas válidas")

    split_idx = int(len(df) * (1 - test_fraction))
    df_train  = df.iloc[:split_idx].copy()
    df_test   = df.iloc[split_idx:].copy()

    if verbose:
        print(f"  Train: {len(df_train)} | Test: {len(df_test)} | has_odds: {has_odds}")
        if has_odds:
            row0 = df_test.iloc[0]
            print(f"  Primer partido test: {row0['home_team']} vs {row0['away_team']}")
            print(f"  Cuotas primer partido: "
                  f"{row0[odds_home_col]} / {row0[odds_draw_col]} / {row0[odds_away_col]}")

    records      = []
    bankroll     = initial_bankroll
    total_staked = 0.0
    debug_first  = True

    for _, row in df_test.iterrows():
        try:
            features = enrich_fixture(row, df_train, as_of_date=row["date"],
                                       col_home=col_home, col_away=col_away)
            pred_dc  = predict_match(
                features["lambda_home"], features["lambda_away"],
                rho=rho, model="dixon_coles"
            )
            pred_p   = predict_match(
                features["lambda_home"], features["lambda_away"],
                model="poisson"
            )
        except Exception as e:
            if verbose and debug_first:
                print(f"  ERROR en enrich/predict: {e}")
            continue

        actual = _result_label(int(row["home_goals"]), int(row["away_goals"]))
        p_dc   = [pred_dc["prob_home"], pred_dc["prob_draw"], pred_dc["prob_away"]]
        p_po   = [pred_p["prob_home"],  pred_p["prob_draw"],  pred_p["prob_away"]]

        profit     = 0.0
        bet_placed = False

        if has_odds:
            try:
                oh = float(row[odds_home_col])
                od = float(row[odds_draw_col])
                oa = float(row[odds_away_col])

                if any(np.isnan([oh, od, oa])):
                    raise ValueError("NaN en cuotas")
                if any(v < 1.01 for v in [oh, od, oa]):
                    raise ValueError("cuota < 1.01")

                best_ev  = MIN_EV
                best_bet = None

                for outcome, prob, odds_val in [
                    ("H", pred_dc["prob_home"], oh),
                    ("D", pred_dc["prob_draw"], od),
                    ("A", pred_dc["prob_away"], oa),
                ]:
                    ev = prob * odds_val - 1
                    rango_ok = MIN_ODDS <= odds_val <= MAX_ODDS
                    prob_ok  = prob >= MIN_PROB_MODEL
                    ev_ok    = MIN_EV < ev <= MAX_EV
                    if verbose and debug_first:
                        print(f"  DEBUG apuesta {outcome}: prob={prob:.3f} "
                              f"odds={odds_val} EV={ev:+.3f} "
                              f"rango_ok={rango_ok} "
                              f"prob_ok={prob_ok} "
                              f"ev_ok={ev_ok}")
                    if ev > best_ev and rango_ok and prob_ok and ev_ok:
                        best_ev  = ev
                        best_bet = (outcome, prob, odds_val)

                if verbose and debug_first:
                    print(f"  best_bet={best_bet}")
                    debug_first = False

                if best_bet:
                    outcome, prob, odds_val = best_bet
                    b      = odds_val - 1
                    q      = 1 - prob
                    k_full = max((b * prob - q) / b, 0.0)
                    stake  = min(bankroll * k_full * kelly_frac,
                                 bankroll * 0.05)

                    if stake >= 0.50:
                        bet_placed    = True
                        total_staked += stake
                        if actual == outcome:
                            profit    = stake * b
                            bankroll += profit
                        else:
                            profit    = -stake
                            bankroll += profit

            except (ValueError, TypeError, KeyError) as e:
                if verbose and debug_first:
                    print(f"  EXCEPCION en cuotas: {e}")
                    debug_first = False

        records.append({
            "date":       row["date"],
            "home_team":  row["home_team"],
            "away_team":  row["away_team"],
            "actual":     actual,
            "ph_dc": p_dc[0], "pd_dc": p_dc[1], "pa_dc": p_dc[2],
            "ph_po": p_po[0], "pd_po": p_po[1], "pa_po": p_po[2],
            "pred_dc":    ("H" if p_dc[0]==max(p_dc)
                           else "D" if p_dc[1]==max(p_dc) else "A"),
            "profit":     profit,
            "bet_placed": bet_placed,
            "bankroll":   bankroll,
        })

    if not records:
        return {"error": "Sin datos para backtest"}

    res_df = pd.DataFrame(records)

    accuracy_dc = (res_df["pred_dc"] == res_df["actual"]).mean()

    def manual_logloss(df, cols):
        eps = 1e-7
        total = 0.0
        for _, r in df.iterrows():
            ph, pd_, pa = r[cols[0]], r[cols[1]], r[cols[2]]
            s = ph + pd_ + pa
            ph, pd_, pa = ph/s, pd_/s, pa/s
            if   r["actual"] == "H": p = max(ph,  eps)
            elif r["actual"] == "D": p = max(pd_, eps)
            else:                    p = max(pa,  eps)
            total -= np.log(p)
        return total / len(df)

    def manual_brier(df, cols):
        scores = []
        for _, r in df.iterrows():
            ph, pd_, pa = r[cols[0]], r[cols[1]], r[cols[2]]
            yh = 1 if r["actual"]=="H" else 0
            yd = 1 if r["actual"]=="D" else 0
            ya = 1 if r["actual"]=="A" else 0
            scores.append((ph-yh)**2 + (pd_-yd)**2 + (pa-ya)**2)
        return np.mean(scores) / 3

    log_dc   = manual_logloss(res_df, ["ph_dc","pd_dc","pa_dc"])
    log_po   = manual_logloss(res_df, ["ph_po","pd_po","pa_po"])
    brier_dc = manual_brier(res_df,   ["ph_dc","pd_dc","pa_dc"])
    brier_po = manual_brier(res_df,   ["ph_po","pd_po","pa_po"])

    bets_df   = res_df[res_df["bet_placed"]]
    n_bets    = len(bets_df)
    total_roi = (bankroll - initial_bankroll) / initial_bankroll
    yield_pct = (bets_df["profit"].sum() / total_staked) if total_staked > 0 else 0.0
    win_rate  = (bets_df["profit"] > 0).mean() if n_bets > 0 else 0.0

    metrics = {
        "n_matches":      len(res_df),
        "n_bets":         n_bets,
        "accuracy_dc":    round(accuracy_dc, 4),
        "log_loss_dc":    round(log_dc, 4),
        "log_loss_po":    round(log_po, 4),
        "brier_dc":       round(brier_dc, 4),
        "brier_po":       round(brier_po, 4),
        "roi":            round(total_roi, 4),
        "yield_per_bet":  round(yield_pct, 4),
        "win_rate":       round(win_rate, 4),
        "total_staked":   round(total_staked, 2),
        "final_bankroll": round(bankroll, 2),
        "results_df":     res_df,
    }

    if verbose:
        print("\n" + "="*55)
        print("  BACKTEST RESULTS")
        print("="*55)
        print(f"  Partidos evaluados:  {metrics['n_matches']:>8}")
        print(f"  Apuestas realizadas: {metrics['n_bets']:>8}")
        print(f"  Win rate:            {metrics['win_rate']:>8.1%}")
        print(f"  Accuracy 1X2:        {metrics['accuracy_dc']:>8.1%}")
        print(f"  Log-Loss DC:         {metrics['log_loss_dc']:>8.4f}")
        print(f"  Log-Loss Poisson:    {metrics['log_loss_po']:>8.4f}")
        print(f"  Brier Score DC:      {metrics['brier_dc']:>8.4f}")
        print(f"  Brier Score Poisson: {metrics['brier_po']:>8.4f}")
        print(f"  Total apostado:      ${metrics['total_staked']:>8,.2f}")
        print(f"  ROI total:           {metrics['roi']:>8.1%}")
        print(f"  Yield por apuesta:   {metrics['yield_per_bet']:>8.2%}")
        print(f"  Bankroll final:      ${metrics['final_bankroll']:>8,.2f}")
        print("="*55)

    return metrics