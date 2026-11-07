"""
Calcula rho óptimo por liga usando los últimos N partidos del histórico.

Estrategia:
  - Para cada liga, tomar los últimos 300 partidos
  - Calcular lambdas para cada uno con enrich_fixture(as_of_date=date)
  - Estimar rho con estimate_rho (MLE)
  - Cachear en output/rho_cache.json

Tiempo: ~2-4 min la primera vez (7 ligas × 300 partidos × ~50ms).

Uso:
  python scripts/compute_league_rho.py
  python scripts/compute_league_rho.py --league PL
  python scripts/compute_league_rho.py --n-matches 500
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse
import json

import pandas as pd

from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR, EVAL_LEAGUES
from src.feature_engineering import enrich_fixture
from src.models import estimate_rho
from src.logger import get_logger

logger = get_logger("compute_league_rho")

ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"
RHO_CACHE = OUTPUT_DIR / "rho_cache.json"
DEFAULT_RHO = -0.13
MIN_MATCHES_FOR_RHO = 50


def compute_lambdas_for_league(history: pd.DataFrame, league: str, n_matches: int = 300) -> pd.DataFrame:
    """
    Calcula lambdas para los últimos n_matches de una liga.

    Para cada partido, usa enrich_fixture con as_of_date=date del partido,
    así solo ve partidos anteriores (walk-forward honesto).
    """
    league_df = history[history["competition"] == league].copy()
    if len(league_df) == 0:
        logger.warning(f"[{league}] Sin partidos en el histórico")
        return pd.DataFrame()

    league_df = league_df.sort_values("date").tail(n_matches).reset_index(drop=True)
    logger.info(f"[{league}] Calculando lambdas para {len(league_df)} partidos (últimos {n_matches})")

    rows = []
    for idx, match in league_df.iterrows():
        try:
            # Train = partidos de la MISMA liga con date < match.date
            train = league_df[league_df["date"] < match["date"]]
            if len(train) < 10:
                # Muy pocos partidos previos, skipear
                continue

            f = enrich_fixture(match, train, as_of_date=match["date"])
            rows.append({
                "date": match["date"],
                "lambda_home": f["lambda_home"],
                "lambda_away": f["lambda_away"],
                "home_goals": int(match["home_goals"]),
                "away_goals": int(match["away_goals"]),
            })
        except Exception as e:
            logger.debug(f"[{league}] Skip {match.get('home_team')} vs {match.get('away_team')}: {e}")
            continue

        if (idx + 1) % 50 == 0:
            logger.info(f"[{league}] Procesados {idx + 1}/{len(league_df)}")

    if not rows:
        logger.warning(f"[{league}] No se pudo calcular ningún lambda")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    logger.info(f"[{league}] {len(df)} lambdas calculados")
    return df


def compute_rho_for_league(history: pd.DataFrame, league: str, n_matches: int = 300) -> dict:
    """Calcula rho para una liga. Devuelve dict con metadatos."""
    lambdas = compute_lambdas_for_league(history, league, n_matches)

    if len(lambdas) < MIN_MATCHES_FOR_RHO:
        logger.warning(
            f"[{league}] Solo {len(lambdas)} partidos (min {MIN_MATCHES_FOR_RHO}). "
            f"Usando rho default {DEFAULT_RHO}"
        )
        return {
            "rho": DEFAULT_RHO,
            "n_matches": len(lambdas),
            "status": "insufficient_data",
        }

    rho = estimate_rho(lambdas)
    logger.info(f"[{league}] rho = {rho:.6f} (n={len(lambdas)})")

    return {
        "rho": float(rho),
        "n_matches": len(lambdas),
        "first_date": lambdas["date"].min().isoformat() if "date" in lambdas.columns else None,
        "last_date": lambdas["date"].max().isoformat() if "date" in lambdas.columns else None,
        "status": "ok",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", type=str, default=None,
                        help="Solo calcular una liga (ej. PL)")
    parser.add_argument("--n-matches", type=int, default=300,
                        help="Partidos recientes por liga (default: 300)")
    args = parser.parse_args()

    if not ENRICHED.exists():
        logger.error(f"No existe {ENRICHED}")
        return

    logger.info(f"Cargando {ENRICHED.name}")
    history = pd.read_parquet(ENRICHED)
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)
    history = history.sort_values("date").reset_index(drop=True)

    leagues = [args.league] if args.league else EVAL_LEAGUES
    logger.info(f"Calculando rho para: {leagues}")

    cache = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_matches_per_league": args.n_matches,
        "default_rho": DEFAULT_RHO,
        "leagues": {},
    }

    # Cargar caché existente si existe (para preservar ligas no recalculadas)
    if RHO_CACHE.exists() and args.league:
        try:
            existing = json.load(RHO_CACHE.open())
            cache["leagues"] = existing.get("leagues", {})
        except Exception:
            pass

    for league in leagues:
        logger.info("=" * 60)
        logger.info(f"Procesando {league}")
        logger.info("=" * 60)
        try:
            result = compute_rho_for_league(history, league, args.n_matches)
            cache["leagues"][league] = result
        except Exception as e:
            logger.error(f"[{league}] Error: {e}")
            cache["leagues"][league] = {
                "rho": DEFAULT_RHO,
                "n_matches": 0,
                "status": f"error: {e}",
            }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with RHO_CACHE.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info(f"Guardado: {RHO_CACHE}")
    logger.info("=" * 60)
    logger.info("Resumen:")
    for league, data in cache["leagues"].items():
        logger.info(
            f"  {league:4s}: rho={data['rho']:+.4f}  "
            f"n={data['n_matches']:4d}  status={data['status']}"
        )


if __name__ == "__main__":
    main()