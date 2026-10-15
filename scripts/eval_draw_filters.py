import sys
from pathlib import Path

# Añadir la raíz del proyecto a sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
from src.evaluation import walk_forward_markets

def run_filter_analysis():
    df = pd.read_parquet("data/processed/history_with_xg.parquet")
    
    # Identificar nombres de columnas de cuotas de empate en el Parquet
    odds_draw_col = next((c for c in ["odds_draw", "odds_D", "PSD", "AvgD", "B365D"] if c in df.columns), None)
    odds_close_col = next((c for c in ["odds_draw_close", "odds_D_close", "PSCD", "AvgCD", "B365CD"] if c in df.columns), None)
    
    print(f"Cuota apertura empate detectada: '{odds_draw_col}'")
    print(f"Cuota cierre empate detectada:   '{odds_close_col}'")
    
    if odds_draw_col is None:
        print("ERROR: No se encontró la columna de cuotas de empate en el archivo Parquet.")
        return

    seasons = sorted(df["season"].unique())
    comp_col = "competition" if "competition" in df.columns else "league"
    leagues = [l for l in df[comp_col].unique() if pd.notna(l) and l != 'CL']
    
    print(f"Temporadas: {seasons}")
    print(f"Ligas a evaluar: {leagues}")
    print("Ejecutando Walk-Forward global...")
    
    all_preds = []
    for league in leagues:
        try:
            preds = walk_forward_markets(df, seasons=seasons, competition=str(league), rho=-0.13)
            if preds is not None and not preds.empty:
                preds["league"] = league
                all_preds.append(preds)
        except Exception as e:
            print(f"Error procesando {league}: {e}")
            
    if not all_preds:
        print("No se obtuvieron predicciones.")
        return

    data = pd.concat(all_preds, ignore_index=True)
    
    # Normalizar tipos para evitar conflictos en la fusión (ej. int64 vs object en 'season')
    merge_keys = [k for k in ["season", "date", "home_team", "away_team"] if k in data.columns and k in df.columns]
    
    df_temp = df.copy()
    for key in merge_keys:
        data[key] = data[key].astype(str)
        df_temp[key] = df_temp[key].astype(str)
        
    odds_to_merge = [c for c in [odds_draw_col, odds_close_col] if c and c in df_temp.columns and c not in data.columns]
    
    if odds_to_merge:
        data = data.merge(df_temp[merge_keys + odds_to_merge].drop_duplicates(), on=merge_keys, how="left")
        
    # Calcular EV, Profit y CLV para el mercado de Empate (1X2 Draw)
    data["odds"] = data[odds_draw_col]
    data["ev"] = (data["prob_D"] * data["odds"]) - 1.0
    
    # Calcular Profit (1 unidad por apuesta)
    is_draw = (data["actual_1x2"] == "D") if "actual_1x2" in data.columns else (data["home_goals"] == data["away_goals"])
    data["profit"] = np.where(is_draw, data["odds"] - 1.0, -1.0)
    
    # Calcular CLV si existe cuota de cierre
    if odds_close_col and odds_close_col in data.columns:
        data["clv"] = (data["odds"] / data[odds_close_col]) - 1.0
    else:
        data["clv"] = np.nan

    # Eliminar registros con cuota nula
    data = data.dropna(subset=["odds", "ev"]).copy()

    print(f"\n=======================================================")
    print(f" ANÁLISIS DE FILTROS EN 1X2 DRAW (Muestra útil: {len(data)} picks)")
    print(f"=======================================================")
    
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
        print(df_res.to_string(index=False))
    else:
        print("No se generaron combinaciones con suficiente muestra.")

if __name__ == "__main__":
    run_filter_analysis()