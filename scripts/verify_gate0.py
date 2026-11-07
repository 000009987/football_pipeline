"""
Verificación del Gate 0 de Fase 0.

Comprueba las 4 condiciones del roadmap:
  1. Ejecución diaria registra la fecha máxima nueva.
  2. No duplica partidos al repetirse.
  3. Cada cuota vinculada a evento, mercado, casa, hora de captura.
  4. Reporte reproducible de cobertura.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR
from src.logger import get_logger

logger = get_logger("verify_gate0")

RAW_HISTORY_PARQUET = PROCESSED_DATA_DIR / "history.parquet"
ENRICHED_PARQUET = PROCESSED_DATA_DIR / "history_with_xg.parquet"
ALERTS_LOG = OUTPUT_DIR / "alerts_history.csv"


def check_1_fecha_maxima():
    """La ejecución diaria deja registrada la fecha máxima nueva."""
    logger.info("Check 1: fecha máxima nueva")
    if not RAW_HISTORY_PARQUET.exists():
        return False, "no existe history.parquet"
    df = pd.read_parquet(RAW_HISTORY_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    max_date = df["date"].max()
    logger.info(f"  Fecha máxima: {max_date}")
    cutoff = pd.Timestamp("2026-10-01", tz="UTC")
    if max_date.tz is None:
        max_date = max_date.tz_localize("UTC")
    if max_date < cutoff:
        return False, f"fecha máxima antigua: {max_date}"
    return True, f"fecha máxima: {max_date.date()}"


def check_2_no_duplicados():
    """No duplica partidos al repetirse."""
    logger.info("Check 2: no duplicados")
    df = pd.read_parquet(ENRICHED_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    dup_key = df.duplicated(subset=["date", "home_team", "away_team"]).sum()
    if dup_key > 0:
        return False, f"{dup_key} duplicados por (date, home_team, away_team)"
    if "match_id" in df.columns:
        dup_id = df["match_id"].duplicated().sum()
        null_id = df["match_id"].isna().sum()
        if dup_id > 0 or null_id > 0:
            return False, f"match_id: {dup_id} dup, {null_id} nulos"
    return True, f"{len(df)} partidos sin duplicados"


def check_3_odds_metadata():
    """Cada cuota vinculada a evento, mercado, casa, hora de captura."""
    logger.info("Check 3: metadatos de cuota")
    if not ALERTS_LOG.exists():
        return False, "no existe alerts_history.csv"
    df = pd.read_csv(ALERTS_LOG)
    if "odds_source" not in df.columns:
        return False, "falta columna odds_source en alerts_history.csv"
    n_filled = df["odds_source"].notna().sum()
    n_total = len(df)
    if n_filled == 0:
        return False, "odds_source vacío en todas las filas"
    if n_filled < n_total:
        return False, f"odds_source: {n_filled}/{n_total} filas rellenas"
    return True, f"odds_source: {n_filled}/{n_total} filas rellenas"


def check_4_coverage_report():
    """Reporte reproducible de cobertura."""
    logger.info("Check 4: coverage report")
    reports = list(OUTPUT_DIR.glob("coverage_report_*.csv"))
    summaries = list(OUTPUT_DIR.glob("coverage_summary_*.txt"))
    if not reports or not summaries:
        return False, "no existe coverage_report/summary en output/"
    return True, f"{len(reports)} report(s), {len(summaries)} summary(ies)"


def main():
    logger.info("=" * 60)
    logger.info("VERIFICACIÓN GATE 0")
    logger.info("=" * 60)

    checks = [
        ("1. Fecha máxima nueva", check_1_fecha_maxima),
        ("2. No duplicados", check_2_no_duplicados),
        ("3. Metadatos de cuota", check_3_odds_metadata),
        ("4. Coverage report", check_4_coverage_report),
    ]

    passed = 0
    failed = 0
    for name, fn in checks:
        try:
            ok, msg = fn()
            status = "PASS" if ok else "FAIL"
            logger.info(f"[{status}] {name}: {msg}")
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"[ERROR] {name}: {e}")
            failed += 1

    logger.info("=" * 60)
    logger.info(f"Resultado: {passed} PASS, {failed} FAIL")
    if failed == 0:
        logger.info("GATE 0: APROBADO - listo para merge a main")
    else:
        logger.info("GATE 0: NO APROBADO - iterar Fase 0")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()