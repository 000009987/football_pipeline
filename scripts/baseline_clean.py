"""
Baseline limpio de Dixon-Coles (Fase 1).

Walk-forward por temporada:
  - Train = partidos con date < inicio de la temporada test
  - Test  = partidos de la temporada test
  - Para cada partido test: predecir con rho de la liga (desde rho_cache.json)
    y HOME_ADVANTAGE=1.0
  - Comparar con Poisson (rho=0) y con el mercado (AvgCD)

Salidas:
  - output/baseline_clean_predictions_YYYYMMDD.csv
  - output/baseline_clean_metrics_YYYYMMDD.csv

Uso:
  python scripts/baseline_clean.py
  python scripts/baseline_clean.py --league PL
  python scripts/baseline_clean.py --no-market
"""
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR, EVAL_LEAGUES
from src.feature_engineering import enrich_fixture
from src.models import predict_match
from src.logger import get_logger

logger = get_logger("baseline_clean")

ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"
RHO_CACHE = OUTPUT_DIR / "rho_cache.json"
DEFAULT_RHO = -0.13
TEST_SEASONS = ["2025", "2026"]
MIN_TRAIN_MATCHES = 100


# ─── Métricas ────────────────────────────────────────────────────────

def brier_multiclass(y_idx, probs):
    total = 0.0
    for k in range(3):
        y_bin = (y_idx == k).astype(float)
        total += np.mean((probs[:, k] - y_bin) ** 2)
    return total / 3


def log_loss_multiclass(y_idx, probs, eps=1e-12):
    probs = np.clip(probs, eps, 1 - eps)
    n = len(y_idx)
    return -np.mean(np.log(probs[np.arange(n), y_idx]))


# ─── Carga de rho ────────────────────────────────────────────────────

def load_rho_per_league():
    if not RHO_CACHE.exists():
        logger.warning(f"No existe {RHO_CACHE}. Usando DEFAULT_RHO para todas.")
        return {}
    try:
        with RHO_CACHE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        leagues = data.get("leagues", {})
        logger.info(f"rho cache cargado: {len(leagues)} ligas")
        for liga, info in leagues.items():
            logger.info(f"  rho[{liga}] = {info['rho']:+.4f}")
        return leagues
    except Exception as e:
        logger.error(f"Error cargando {RHO_CACHE}: {e}")
        return {}


def get_rho(league, cache):
    if league in cache:
        return float(cache[league]["rho"])
    return DEFAULT_RHO


# ─── Mercado (AvgCD) ─────────────────────────────────────────────────

def market_probs_from_odds(odds_h, odds_d, odds_a):
    """Probabilidades implícitas normalizadas (sin overround)."""
    if pd.isna(odds_h) or pd.isna(odds_d) or pd.isna(odds_a):
        return None
    if odds_h <= 1 or odds_d <= 1 or odds_a <= 1:
        return None
    inv = np.array([1 / odds_h, 1 / odds_d, 1 / odds_a])
    return inv / inv.sum()


# ─── Walk-forward por liga/temporada ─────────────────────────────────

def walk_forward_league(history, league, seasons, rho_league, use_market=True):
    """Walk-forward para una liga y sus temporadas test."""
    league_df = history[history["competition"] == league].sort_values("date").reset_index(drop=True)
    if len(league_df) == 0:
        logger.warning(f"[{league}] Sin partidos")
        return pd.DataFrame()

    rows = []
    for season in seasons:
        season_str = str(season)
        train = league_df[league_df["season"].astype(str) < season_str]
        test = league_df[league_df["season"].astype(str) == season_str]

        if len(train) < MIN_TRAIN_MATCHES:
            logger.info(f"[{league}/{season}] skip (train={len(train)} < {MIN_TRAIN_MATCHES})")
            continue
        if len(test) == 0:
            continue

        logger.info(f"[{league}/{season}] train={len(train)}, test={len(test)}, rho={rho_league:+.4f}")

        for _, row in test.iterrows():
            try:
                f = enrich_fixture(row, train, as_of_date=row["date"])
                p_dc = predict_match(
                    f["lambda_home"], f["lambda_away"],
                    rho=rho_league, model="dixon_coles",
                )
                p_poi = predict_match(
                    f["lambda_home"], f["lambda_away"],
                    rho=0.0, model="poisson",
                )
            except Exception as e:
                logger.debug(f"[{league}] skip {row.get('home_team')} vs {row.get('away_team')}: {e}")
                continue

            actual = "H" if row["home_goals"] > row["away_goals"] else (
                "D" if row["home_goals"] == row["away_goals"] else "A"
            )

            rec = {
                "league": league,
                "season": season_str,
                "match_id": row.get("match_id", ""),
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "home_goals": int(row["home_goals"]),
                "away_goals": int(row["away_goals"]),
                "actual": actual,
                "prob_home_dc": p_dc["prob_home"],
                "prob_draw_dc": p_dc["prob_draw"],
                "prob_away_dc": p_dc["prob_away"],
                "prob_home_poi": p_poi["prob_home"],
                "prob_draw_poi": p_poi["prob_draw"],
                "prob_away_poi": p_poi["prob_away"],
                "rho_used": rho_league,
            }

            if use_market:
                o_h = row.get("odds_home")
                o_d = row.get("odds_draw")
                o_a = row.get("odds_away")
                mkt = market_probs_from_odds(o_h, o_d, o_a)
                if mkt is not None:
                    rec["prob_home_mkt"] = mkt[0]
                    rec["prob_draw_mkt"] = mkt[1]
                    rec["prob_away_mkt"] = mkt[2]

            rows.append(rec)

    return pd.DataFrame(rows)


# ─── Métricas agregadas ──────────────────────────────────────────────

def compute_metrics(preds):
    """Calcula Brier, LogLoss, Accuracy para DC, Poisson y Mercado."""
    order = {"H": 0, "D": 1, "A": 2}
    out = []
    for (league, season), g in preds.groupby(["league", "season"]):
        y_idx = g["actual"].map(order).values
        row = {"league": league, "season": season, "n": len(g)}

        for model, cols in [
            ("DC", ["prob_home_dc", "prob_draw_dc", "prob_away_dc"]),
            ("Poisson", ["prob_home_poi", "prob_draw_poi", "prob_away_poi"]),
            ("Mercado", ["prob_home_mkt", "prob_draw_mkt", "prob_away_mkt"]),
        ]:
            if all(c in g.columns for c in cols):
                probs = g[cols].dropna().values
                if len(probs) == len(g):
                    y = y_idx
                else:
                    # Filtrar filas con NaN
                    mask = g[cols].notna().all(axis=1).values
                    probs = g.loc[mask, cols].values
                    y = g.loc[mask, "actual"].map(order).values
                if len(probs) < 10:
                    continue
                row[f"brier_{model}"] = brier_multiclass(y, probs)
                row[f"logloss_{model}"] = log_loss_multiclass(y, probs)
                row[f"acc_{model}"] = (probs.argmax(axis=1) == y).mean()
                row[f"n_{model}"] = len(probs)

        out.append(row)
    return pd.DataFrame(out)


# ─── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", type=str, default=None)
    parser.add_argument("--no-market", action="store_true")
    args = parser.parse_args()

    if not ENRICHED.exists():
        logger.error(f"No existe {ENRICHED}")
        return

    logger.info(f"Cargando {ENRICHED.name}")
    history = pd.read_parquet(ENRICHED)
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)

    rho_cache = load_rho_per_league()

    leagues = [args.league] if args.league else EVAL_LEAGUES
    logger.info(f"Ligas a evaluar: {leagues}")
    logger.info(f"Temporadas test: {TEST_SEASONS}")

    all_preds = []
    for league in leagues:
        rho_league = get_rho(league, rho_cache)
        logger.info(f"\n{'=' * 60}\n{league} (rho={rho_league:+.4f})\n{'=' * 60}")
        preds = walk_forward_league(
            history, league, TEST_SEASONS, rho_league,
            use_market=not args.no_market,
        )
        if not preds.empty:
            all_preds.append(preds)

    if not all_preds:
        logger.warning("Sin predicciones. Revisa filtros.")
        return

    preds_df = pd.concat(all_preds, ignore_index=True)
    metrics_df = compute_metrics(preds_df)

    today = datetime.now().strftime("%Y%m%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    preds_path = OUTPUT_DIR / f"baseline_clean_predictions_{today}.csv"
    metrics_path = OUTPUT_DIR / f"baseline_clean_metrics_{today}.csv"
    preds_df.to_csv(preds_path, index=False)
    metrics_df.to_csv(metrics_path, index=False)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Guardado:")
    logger.info(f"  {preds_path} ({len(preds_df)} partidos)")
    logger.info(f"  {metrics_path} ({len(metrics_df)} filas)")
    logger.info(f"{'=' * 60}")

    # Resumen por liga (agregando temporadas)
    logger.info("\nResumen por liga (agregado):")
    for league, g in preds_df.groupby("league"):
        y_idx = g["actual"].map({"H": 0, "D": 1, "A": 2}).values
        probs_dc = g[["prob_home_dc", "prob_draw_dc", "prob_away_dc"]].values
        brier_dc = brier_multiclass(y_idx, probs_dc)
        logger.info(f"  {league:4s}: n={len(g):4d}  Brier(DC)={brier_dc:.4f}")

    logger.info("\nMétricas por liga/temporada (primeras 14 filas):")
    logger.info(f"\n{metrics_df.round(4).to_string(index=False)}")


if __name__ == "__main__":
    main()