import sys
from pathlib import Path

# Añadir raíz al path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from src.config import HISTORY_PARQUET, LEAGUES, DEFAULT_SEASONS, DEFAULT_RHO
from src.evaluation import walk_forward_markets
from src.evaluation_helpers import calculate_ev, calculate_profit, calculate_clv
from src.logger import get_logger

logger = get_logger("eval_draw_filters")

def run_filter_analysis():
    if not HISTORY_PARQUET.exists():
        logger.error(f"Archivo no encontrado: {HISTORY_PARQUET}")
        return

    df = pd.read_parquet(HISTORY_PARQUET)
    
    odds_draw_col = next((c for c in ["odds_draw", "odds_D", "PSD", "AvgD", "B365D"] if c in df.columns), None)
    odds_close_col = next((c for c in ["odds_draw_close", "odds_D_close", "PSCD", "AvgCD", "B365CD"] if c in df.columns), None)
    
    logger.info(f"Cuota apertura empate: '{odds_draw_col}' | Cuota cierre empate: '{odds_close_col}'")
    
    all_preds = []
    for league in LEAGUES:
        try:
            preds = walk_forward_markets(df, seasons=DEFAULT_SEASONS, competition=str(league), rho=DEFAULT_RHO)
            if preds is not None and not preds.empty:
                preds["league"] = league
                all_preds.append(preds)
        except Exception as e:
            logger.error(f"Error procesando {league}: {e}")
            
    if not all_preds:
        logger.warning("No se obtuvieron predicciones.")
        return

    data = pd.concat(all_preds, ignore_index=True)
    
    merge_keys = [k for k in ["season", "date", "home_team", "away_team"] if k in data.columns and k in df.columns]
    
    df_temp = df.copy()
    for key in merge_keys:
        data[key] = data[key].astype(str)
        df_temp[key] = df_temp[key].astype(str)
        
    odds_to_merge = [c for c in [odds_draw_col, odds_close_col] if c and c in df_temp.columns and c not in data.columns]
    if odds_to_merge:
        data = data.merge(df_temp[merge_keys + odds_to_merge].drop_duplicates(), on=merge_keys, how="left")
        
    data["odds"] = data[odds_draw_col]
    data["ev"] = calculate_ev(data["prob_D"], data["odds"])
    
    is_draw = (data["actual_1x2"] == "D") if "actual_1x2" in data.columns else (data["home_goals"] == data["away_goals"])
    data["profit"] = calculate_profit(is_draw, data["odds"])
    
    if odds_close_col and odds_close_col in data.columns:
        data["clv"] = calculate_clv(data["odds"], data[odds_close_col])
    else:
        data["clv"] = np.nan

    data = data.dropna(subset=["odds", "ev"]).copy()

    logger.info(f"Análisis sobre muestra de {len(data)} picks útiles.")
    
    ev_thresholds = [0.03, 0.05, 0.08, 0.10, 0.12]
    max_odds_limits = [None, 3.80, 3.60, 3.40]
    
    results = []
    for ev in ev_thresholds:
        for max_odds in max_odds_limits:
            subset = data[data["ev"] >= ev].copy()
            if max_odds is not None:
                subset = subset[subset["odds"] <= max_odds]
                
            n_bets = len(subset)
            if n_bets < 5:
                continue
                
            clv_mean = subset["clv"].mean() * 100 if "clv" in subset.columns and subset["clv"].notna().any() else np.nan
            clv_pos = (subset["clv"] > 0).mean() * 100 if "clv" in subset.columns and subset["clv"].notna().any() else np.nan
            yield_val = (subset["profit"].sum() / n_bets) * 100
            
            results.append({
                "EV_Min": f">{int(ev*100)}%",
                "Max_Odds": max_odds if max_odds else "Sin limite",
                "Apuestas": n_bets,
                "CLV_Medio": f"{clv_mean:+.2f}%" if not np.isnan(clv_mean) else "N/A",
                "CLV_Pos%": f"{clv_pos:.1f}%" if not np.isnan(clv_pos) else "N/A",
                "Yield": f"{yield_val:+.2f}%"
            })
            
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        print("\n" + df_res.to_string(index=False))

if __name__ == "__main__":
    run_filter_analysis()