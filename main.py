"""
main.py
Orquestador principal del pipeline.

Uso:
  python main.py --mode analyze   # analiza partidos de los próximos 7 días
  python main.py --mode backtest  # valida el modelo con datos históricos
  python main.py --mode download  # solo descarga/actualiza datos históricos
  
  # Analizar un partido específico con cuotas manuales:
  python main.py --mode single --home "Arsenal" --away "Chelsea" \\
                 --odds "1:2.10,X:3.40,2:3.60,O2.5:1.85,BTTS_Y:1.75"
"""

import argparse
import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# Rutas
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from config import LEAGUES, SEASONS, OUTPUT_CSV, OUTPUT_HTML
from src.data_loader      import fetch_all_historical, fetch_all_upcoming
from src.feature_engineering import enrich_fixture
from src.models           import predict_match, estimate_rho
from src.value_bet_detector import (analyze_fixture, add_kelly,
                                     print_value_bets)
from src.backtester       import run_backtest


# ── Caché de datos históricos ──────────────────────────────────────────────────

_HISTORY_CACHE = None
_RHO_CACHE     = None

def get_history(force_reload: bool = False) -> pd.DataFrame:
    global _HISTORY_CACHE
    if _HISTORY_CACHE is None or force_reload:
        processed_path = ROOT / "data" / "processed" / "history.parquet"
        if processed_path.exists() and not force_reload:
            print("Cargando histórico desde disco...")
            _HISTORY_CACHE = pd.read_parquet(processed_path)
        else:
            print("Descargando datos históricos (esto tarda la primera vez)...")
            _HISTORY_CACHE = fetch_all_historical()
            if not _HISTORY_CACHE.empty:
                processed_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Convertir columnas de cuotas a número
                # Algunos CSVs las traen como texto
                df = _HISTORY_CACHE.copy()
                for col in df.columns:
                    if df[col].dtype == object:
                        try:
                            df[col] = pd.to_numeric(df[col], errors='ignore')
                        except Exception:
                            pass
                
                # Columnas problemáticas — forzar conversión o eliminar
                for col in df.select_dtypes(include='object').columns:
                    if col not in ['date', 'competition', 'season', 
                                   'home_team', 'away_team', 'status',
                                   'FTR', 'HTR', 'Referee', 'Div',
                                   'ï»¿Div', 'Time']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                _HISTORY_CACHE = df
                _HISTORY_CACHE.to_parquet(processed_path, index=False)
                print(f"✓ Guardado en {processed_path}")
    return _HISTORY_CACHE   


def get_rho(df: pd.DataFrame) -> float:
    global _RHO_CACHE
    if _RHO_CACHE is None:
        print("Estimando parámetro rho (Dixon-Coles)...")
        _RHO_CACHE = estimate_rho(df)
        print(f"  rho estimado: {_RHO_CACHE:.4f}")
    return _RHO_CACHE


# ── Modo: análisis de próximos partidos ───────────────────────────────────────

def run_analyze(days_ahead: int = 7, manual_odds: dict = None):
    """
    Descarga fixtures próximos, predice y detecta value bets.
    Si no hay cuotas automáticas, muestra solo probabilidades del modelo.
    """
    df_history = get_history()
    if df_history.empty:
        print("ERROR: No hay datos históricos. Verifica tu API key en config.py")
        return

    rho = get_rho(df_history)

    print(f"\nObteniendo partidos de los próximos {days_ahead} días...")
    fixtures = fetch_all_upcoming(days_ahead=days_ahead)

    if fixtures.empty:
        print("No se encontraron fixtures próximos.")
        return

    all_predictions = {}
    results = []

    for _, fix in fixtures.iterrows():
        try:
            features = enrich_fixture(fix, df_history)
            pred     = predict_match(features["lambda_home"],
                                     features["lambda_away"],
                                     rho=rho, model="dixon_coles")
            key = (fix["home_team"], fix["away_team"])
            all_predictions[key] = pred

            row = {
                "date":        features["date"],
                "competition": features["competition"],
                "home_team":   features["home_team"],
                "away_team":   features["away_team"],
                "lambda_home": features["lambda_home"],
                "lambda_away": features["lambda_away"],
                **{k: v for k, v in pred.items()
                   if isinstance(v, (int, float)) and k != "model"},
            }
            results.append(row)
        except Exception as e:
            print(f"  Error en {fix.get('home_team','?')} vs "
                  f"{fix.get('away_team','?')}: {e}")

    df_preds = pd.DataFrame(results)

    # Mostrar predicciones
    print(f"\n{'='*70}")
    print(f"  PREDICCIONES ({len(df_preds)} partidos)")
    print(f"{'='*70}")
    print(f"  {'Partido':<35} {'λH':>5} {'λA':>5} {'%H':>7} {'%D':>7} "
          f"{'%A':>7} {'O2.5':>7} {'BTTS':>6}")
    print(f"  {'-'*70}")
    for _, r in df_preds.iterrows():
        match = f"{r['home_team']} vs {r['away_team']}"[:34]
        print(f"  {match:<35} {r['lambda_home']:>5.2f} {r['lambda_away']:>5.2f} "
              f"{r['prob_home']:>7.1%} {r['prob_draw']:>7.1%} {r['prob_away']:>7.1%} "
              f"{r.get('over_2.5',0):>7.1%} {r.get('btts_yes',0):>6.1%}")

    # Value bets con cuotas manuales (si se pasan)
    if manual_odds:
        print("\n\n  Analizando value bets con cuotas manuales...")
        all_bets = []
        for key, pred in all_predictions.items():
            ht, at = key
            row_match = fixtures[
                (fixtures["home_team"] == ht) & (fixtures["away_team"] == at)
            ].iloc[0] if not fixtures[
                (fixtures["home_team"] == ht) & (fixtures["away_team"] == at)
            ].empty else None
            if row_match is not None:
                bets = analyze_fixture(
                    pred, manual_odds,
                    home_team=ht, away_team=at,
                    competition=row_match.get("competition", "")
                )
                all_bets.extend(bets)
        
        df_bets = add_kelly(pd.DataFrame(all_bets))
        print_value_bets(df_bets)
        if not df_bets.empty:
            df_bets.to_csv(ROOT / OUTPUT_CSV, index=False)
            print(f"\n  CSV guardado en: {OUTPUT_CSV}")

    return df_preds


# ── Modo: partido único con cuotas ────────────────────────────────────────────

def run_single(home: str, away: str, competition: str = "PL",
               odds_str: str = "") -> dict:
    """
    Predice un partido específico.
    odds_str: "1:2.10,X:3.40,2:3.60,O2.5:1.85"
    """
    df_history = get_history()
    rho        = get_rho(df_history)

    fixture = pd.Series({
        "home_team":   home,
        "away_team":   away,
        "competition": competition,
        "date":        str(datetime.today().date()),
    })

    features = enrich_fixture(fixture, df_history)
    pred     = predict_match(features["lambda_home"], features["lambda_away"],
                              rho=rho, model="dixon_coles")

    print(f"\n{'='*60}")
    print(f"  {home}  vs  {away}")
    print(f"  xG esperados: {features['lambda_home']:.2f} - {features['lambda_away']:.2f}")
    print(f"{'='*60}")
    print(f"  Victoria local:   {pred['prob_home']:.1%}")
    print(f"  Empate:           {pred['prob_draw']:.1%}")
    print(f"  Victoria visit.:  {pred['prob_away']:.1%}")
    print(f"\n  Over 1.5:         {pred['over_1.5']:.1%}")
    print(f"  Over 2.5:         {pred['over_2.5']:.1%}")
    print(f"  Over 3.5:         {pred['over_3.5']:.1%}")
    print(f"  BTTS Sí:          {pred['btts_yes']:.1%}")
    print(f"\n  Top marcadores exactos:")
    for score, p in sorted(pred["exact_scores"].items(), key=lambda x: -x[1])[:8]:
        print(f"    {score}: {p:.2%}")

    if odds_str:
        odds = {}
        for pair in odds_str.split(","):
            k, v = pair.strip().split(":")
            odds[k.strip()] = float(v.strip())
        
        bets = analyze_fixture(pred, odds, home_team=home, away_team=away)
        df_bets = add_kelly(pd.DataFrame(bets))
        
        if not df_bets.empty:
            print(f"\n{'='*60}")
            print(f"  VALUE BETS DETECTADAS")
            print(f"{'='*60}")
            for _, r in df_bets.iterrows():
                print(f"  {r['bet_name']:<22} cuota {r['odds']:.2f}  "
                      f"modelo {r['prob_model']:.1%}  impl {r['prob_implied']:.1%}  "
                      f"EV {r['ev_pct']}  Kelly {r['kelly_pct_str']}  {r['rating']}")
        else:
            print("\n  Sin value bets con estos filtros / cuotas.")

    return pred


# ── Modo: backtest ─────────────────────────────────────────────────────────────

def run_backtest_mode(competition: str = "PL"):
    df_history = get_history()
    
    # Ligas con cuotas disponibles
    odds_comps = [c for c in df_history["competition"].unique() 
                  if "odds" in c.lower() or c in ["Eliteserien"]]
    
    # Filtrar la liga objetivo
    df_target = df_history[df_history["competition"] == competition]
    
    if df_target.empty:
        print(f"Sin datos para {competition}")
        print(f"Competiciones disponibles: {sorted(df_history['competition'].unique())}")
        return
    
    # Usar TODO el historial para entrenar ratings, solo testear en la liga objetivo
    print(f"\nEntrenando con {len(df_history):,} partidos totales")
    print(f"Testeando en {competition}: {len(df_target)} partidos")
    
    # Detectar columnas de cuotas
    odds_cols = ("odds_home", "odds_draw", "odds_away")
    alt_maps = [
        ("B365H", "B365D", "B365A"),
        ("BWH",   "BWD",   "BWA"),
        ("PSH",   "PSD",   "PSA"),
    ]
    for h, d, a in alt_maps:
        if all(c in df_target.columns for c in [h, d, a]):
            odds_cols = (h, d, a)
            break
    
    run_backtest(df_target, 
                 test_fraction=0.30,
                 odds_source_cols=odds_cols,
                 verbose=True)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Football Betting Pipeline")
    parser.add_argument("--mode",   default="analyze",
                        choices=["analyze", "single", "backtest", "download"])
    parser.add_argument("--days",   type=int, default=7)
    parser.add_argument("--home",   default="")
    parser.add_argument("--away",   default="")
    parser.add_argument("--comp",   default="PL")
    parser.add_argument("--odds",   default="")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    if args.mode == "download":
        get_history(force_reload=True)

    elif args.mode == "analyze":
        run_analyze(days_ahead=args.days)

    elif args.mode == "single":
        if not args.home or not args.away:
            print("Usa --home 'Equipo A' --away 'Equipo B'")
            sys.exit(1)
        run_single(args.home, args.away, args.comp, args.odds)

    elif args.mode == "backtest":
        run_backtest_mode(args.comp)


if __name__ == "__main__":
    main()
