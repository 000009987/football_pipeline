"""
Baseline limpio de Dixon-Coles (Fase 1).

Walk-forward por temporada:
  - Para cada (liga, test_season):
      * train = partidos con season < test_season
      * Estimar rho con SOLO train (walk-forward interno con lambdas OOS)
      * test = partidos de test_season
      * Para cada partido test: predecir con rho estimado (sin leakage)
  - Comparar con Poisson (rho=0) y con el mercado (odds de apertura)

Sin leakage: rho se estima con lambdas OOS de train, no con datos futuros.

Salidas:
  - output/baseline_clean_predictions_YYYYMMDD.csv
  - output/baseline_clean_metrics_YYYYMMDD.csv
  - output/baseline_clean_rho_YYYYMMDD.csv  (log de rho por liga/temporada)

Uso:
  python scripts/baseline_clean.py
  python scripts/baseline_clean.py --league PL
  python scripts/baseline_clean.py --no-market
  python scripts/baseline_clean.py --n-rho-matches 200   # partidos de train para estimar rho
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR, EVAL_LEAGUES
from src.feature_engineering import enrich_fixture
from src.models import predict_match, estimate_rho
from src.logger import get_logger

logger = get_logger("baseline_clean")

ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"
DEFAULT_RHO = -0.13
TEST_SEASONS = ["2025", "2026"]
MIN_TRAIN_MATCHES = 100
MIN_RHO_LAMBDAS = 50
DEFAULT_N_RHO_MATCHES = 300


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


# ─── rho walk-forward (sin leakage) ─────────────────────────────────

def compute_rho_walk_forward(train_df: pd.DataFrame, n_matches: int = DEFAULT_N_RHO_MATCHES) -> tuple[float, int]:
    """
    Estima rho usando SOLO train_df.

    Para evitar leakage dentro de train, calcula lambdas OOS:
      para cada partido i en train, lambda se calcula con train[:i]
      (as_of_date = date del partido i).

    Devuelve (rho, n_lambdas_ok).
    """
    if len(train_df) < MIN_TRAIN_MATCHES:
        return DEFAULT_RHO, 0

    sample = train_df.sort_values("date").tail(n_matches).copy()

    rows = []
    for _, match in sample.iterrows():
        history = train_df[train_df["date"] < match["date"]]
        if len(history) < 10:
            continue
        try:
            f = enrich_fixture(match, history, as_of_date=match["date"])
            rows.append({
                "lambda_home": f["lambda_home"],
                "lambda_away": f["lambda_away"],
                "home_goals": int(match["home_goals"]),
                "away_goals": int(match["away_goals"]),
            })
        except Exception:
            continue

    if len(rows) < MIN_RHO_LAMBDAS:
        return DEFAULT_RHO, len(rows)

    lambdas_df = pd.DataFrame(rows)
    rho = estimate_rho(lambdas_df)
    return float(rho), len(rows)


# ─── Mercado (odds de apertura) ─────────────────────────────────────

def market_probs_from_odds(odds_h, odds_d, odds_a):
    """Probabilidades implícitas normalizadas (sin overround)."""
    if pd.isna(odds_h) or pd.isna(odds_d) or pd.isna(odds_a):
        return None
    if odds_h <= 1 or odds_d <= 1 or odds_a <= 1:
        return None
    inv = np.array([1 / odds_h, 1 / odds_d, 1 / odds_a])
    return inv / inv.sum()


# ─── Walk-forward por liga/temporada ────────────────────────────────

def walk_forward_league(history, league, seasons, use_market=True, n_rho_matches=DEFAULT_N_RHO_MATCHES):
    """
    Walk-forward para una liga, estimando rho por cada test_season
    con solo train de esa temporada.

    Devuelve (preds_df, rho_log_df).
    """
    league_df = history[history["competition"] == league].sort_values("date").reset_index(drop=True)
    if len(league_df) == 0:
        logger.warning(f"[{league}] Sin partidos")
        return pd.DataFrame(), pd.DataFrame()

    rows = []
    rho_log = []

    for season in seasons:
        season_str = str(season)
        train = league_df[league_df["season"].astype(str) < season_str].copy()
        test = league_df[league_df["season"].astype(str) == season_str].copy()

        if len(train) < MIN_TRAIN_MATCHES:
            logger.info(f"[{league}/{season}] skip (train={len(train)} < {MIN_TRAIN_MATCHES})")
            continue
        if len(test) == 0:
            continue

        # ── rho walk-forward (solo train) ───────────────────────────
        rho_season, n_lambdas = compute_rho_walk_forward(train, n_matches=n_rho_matches)
        logger.info(
            f"[{league}/{season}] train={len(train)}, test={len(test)}, "
            f"rho={rho_season:+.4f} (n_lambdas={n_lambdas})"
        )
        rho_log.append({
            "league": league,
            "season": season_str,
            "rho": rho_season,
            "n_lambdas": n_lambdas,
            "n_train": len(train),
            "n_test": len(test),
        })

        # ── predicciones de test con rho_season ─────────────────────
        for _, row in test.iterrows():
            try:
                f = enrich_fixture(row, train, as_of_date=row["date"])
                p_dc = predict_match(
                    f["lambda_home"], f["lambda_away"],
                    rho=rho_season, model="dixon_coles",
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
                "rho_used": rho_season,
                "n_rho_lambdas": n_lambdas,
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

    return pd.DataFrame(rows), pd.DataFrame(rho_log)


# ─── Métricas agregadas ─────────────────────────────────────────────

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
                mask = g[cols].notna().all(axis=1).values
                probs = g.loc[mask, cols].values
                y = g.loc[mask, "actual"].map(order).values
                if len(probs) < 10:
                    continue
                row[f"brier_{model}"] = brier_multiclass(y, probs)
                row[f"logloss_{model}"] = log_loss_multiclass(y, probs)
                row[f"acc_{model}"] = (probs.argmax(axis=1) == y).mean()
                row[f"n_{model}"] = len(probs)
                ci = bootstrap_ci(y, probs, n_boot=500)  # 500 para no tardar demasiado
                row[f"brier_{model}_lo"] = ci["brier_lo"]
                row[f"brier_{model}_hi"] = ci["brier_hi"]
                row[f"logloss_{model}_lo"] = ci["logloss_lo"]
                row[f"logloss_{model}_hi"] = ci["logloss_hi"]

        out.append(row)
    return pd.DataFrame(out)

def bootstrap_ci(y_idx, probs, n_boot=1000, alpha=0.05):
    """
    Calcula IC95% para Brier y LogLoss via bootstrap.
    Devuelve dict con brier_ci, logloss_ci (lower, upper) y medianas.
    """
    rng = np.random.default_rng(42)
    n = len(y_idx)
    briers, loglosses = [], []

    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        y_b = y_idx[idx]
        p_b = probs[idx]
        briers.append(brier_multiclass(y_b, p_b))
        loglosses.append(log_loss_multiclass(y_b, p_b))

    briers = np.array(briers)
    loglosses = np.array(loglosses)
    lo, hi = alpha / 2 * 100, (1 - alpha / 2) * 100

    return {
        "brier_mean": float(np.mean(briers)),
        "brier_lo": float(np.percentile(briers, lo)),
        "brier_hi": float(np.percentile(briers, hi)),
        "logloss_mean": float(np.mean(loglosses)),
        "logloss_lo": float(np.percentile(loglosses, lo)),
        "logloss_hi": float(np.percentile(loglosses, hi)),
    }

# ─── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", type=str, default=None)
    parser.add_argument("--no-market", action="store_true")
    parser.add_argument("--n-rho-matches", type=int, default=DEFAULT_N_RHO_MATCHES,
                        help="Partidos de train para estimar rho (default: 300)")
    args = parser.parse_args()

    if not ENRICHED.exists():
        logger.error(f"No existe {ENRICHED}")
        return

    logger.info(f"Cargando {ENRICHED.name}")
    history = pd.read_parquet(ENRICHED)
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)

    leagues = [args.league] if args.league else EVAL_LEAGUES
    logger.info(f"Ligas a evaluar: {leagues}")
    logger.info(f"Temporadas test: {TEST_SEASONS}")
    logger.info(f"n_rho_matches (por liga/temporada): {args.n_rho_matches}")

    all_preds = []
    all_rho_log = []
    for league in leagues:
        logger.info(f"\n{'=' * 60}\n{league}\n{'=' * 60}")
        preds, rho_log = walk_forward_league(
            history, league, TEST_SEASONS,
            use_market=not args.no_market,
            n_rho_matches=args.n_rho_matches,
        )
        if not preds.empty:
            all_preds.append(preds)
        if not rho_log.empty:
            all_rho_log.append(rho_log)

    if not all_preds:
        logger.warning("Sin predicciones. Revisa filtros.")
        return

    preds_df = pd.concat(all_preds, ignore_index=True)
    rho_df = pd.concat(all_rho_log, ignore_index=True) if all_rho_log else pd.DataFrame()
    metrics_df = compute_metrics(preds_df)

    today = datetime.now().strftime("%Y%m%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    preds_path = OUTPUT_DIR / f"baseline_clean_predictions_{today}.csv"
    metrics_path = OUTPUT_DIR / f"baseline_clean_metrics_{today}.csv"
    rho_path = OUTPUT_DIR / f"baseline_clean_rho_{today}.csv"
    preds_df.to_csv(preds_path, index=False)
    metrics_df.to_csv(metrics_path, index=False)
    if not rho_df.empty:
        rho_df.to_csv(rho_path, index=False)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Guardado:")
    logger.info(f"  {preds_path} ({len(preds_df)} partidos)")
    logger.info(f"  {metrics_path} ({len(metrics_df)} filas)")
    if not rho_df.empty:
        logger.info(f"  {rho_path} ({len(rho_df)} filas)")
    logger.info(f"{'=' * 60}")

    # Resumen por liga (agregando temporadas)
    logger.info("\nResumen por liga (agregado):")
    for league, g in preds_df.groupby("league"):
        y_idx = g["actual"].map({"H": 0, "D": 1, "A": 2}).values
        probs_dc = g[["prob_home_dc", "prob_draw_dc", "prob_away_dc"]].values
        brier_dc = brier_multiclass(y_idx, probs_dc)
        logger.info(f"  {league:4s}: n={len(g):4d}  Brier(DC)={brier_dc:.4f}")

    # Log de rho por liga/temporada
    if not rho_df.empty:
        logger.info("\nrho por liga/temporada (walk-forward, sin leakage):")
        logger.info(f"\n{rho_df.round(4).to_string(index=False)}")

    logger.info("\nMétricas por liga/temporada:")
    logger.info(f"\n{metrics_df.round(4).to_string(index=False)}")


if __name__ == "__main__":
    main()