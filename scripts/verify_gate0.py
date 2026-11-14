"""
Verificación del Gate 0 de Fase 0.

Comprueba 7 condiciones:
  1. Fecha máxima nueva registrada.
  2. No duplicados.
  3. Metadatos de cuota.
  4. Coverage report reproducible.
  5. match_id sin nulos ni duplicados (Bloque 1).
  6. TZ consistente entre history y upcoming (Bloques 2+3).
  7. Header de alerts_history.csv == FIELDS (Bloque 2).
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import csv

import pandas as pd

from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR, UPCOMING_PARQUET
from src.alerts_logger import ALERTS_LOG, FIELDS
from src.logger import get_logger

logger = get_logger("verify_gate0")

RAW_HISTORY_PARQUET = PROCESSED_DATA_DIR / "history.parquet"
ENRICHED_PARQUET = PROCESSED_DATA_DIR / "history_with_xg.parquet"


def check_1_fecha_maxima():
    logger.info("Check 1: fecha máxima nueva")
    if not RAW_HISTORY_PARQUET.exists():
        return False, "no existe history.parquet"
    df = pd.read_parquet(RAW_HISTORY_PARQUET)
    d = pd.to_datetime(df["date"])
    if d.dt.tz is not None:
        d = d.dt.tz_localize(None)
    max_date = d.max()
    cutoff = pd.Timestamp("2026-10-01")
    if max_date < cutoff:
        return False, f"fecha máxima antigua: {max_date}"
    return True, f"fecha máxima: {max_date.date()}"


def check_2_no_duplicados():
    logger.info("Check 2: no duplicados")
    df = pd.read_parquet(ENRICHED_PARQUET)
    d = pd.to_datetime(df["date"])
    if d.dt.tz is not None:
        d = d.dt.tz_localize(None)
    df = df.assign(date=d)
    dup_key = df.duplicated(subset=["date", "home_team", "away_team"]).sum()
    if dup_key > 0:
        return False, f"{dup_key} duplicados por (date, home_team, away_team)"
    return True, f"{len(df)} partidos sin duplicados"


def check_3_odds_metadata():
    logger.info("Check 3: metadatos de cuota")
    if not ALERTS_LOG.exists():
        return False, "no existe alerts_history.csv"
    df = pd.read_csv(ALERTS_LOG)
    missing = [c for c in ["odds_source", "market", "capture_timestamp"] if c not in df.columns]
    if missing:
        return False, f"faltan columnas: {missing}"
    n_unverified = (df["odds_source"] == "Pinnacle (unverified)").sum()
    n_verified = df["odds_source"].notna().sum() - n_unverified
    if n_verified == 0 and n_unverified == 0:
        return False, "no hay alertas con odds_source"
    return True, f"{n_verified} verificadas, {n_unverified} unverified"


def check_4_coverage_report():
    logger.info("Check 4: coverage report")
    reports = list(OUTPUT_DIR.glob("coverage_report_*.csv"))
    summaries = list(OUTPUT_DIR.glob("coverage_summary_*.txt"))
    if not reports or not summaries:
        return False, "no existe coverage_report/summary en output/"
    return True, f"{len(reports)} report(s), {len(summaries)} summary(ies)"


def check_5_match_id_unique():
    logger.info("Check 5: match_id único")
    df = pd.read_parquet(ENRICHED_PARQUET)
    if "match_id" not in df.columns:
        return False, "falta columna match_id"
    n_nulls = int(df["match_id"].isna().sum())
    n_dups = int(df["match_id"].duplicated().sum())
    if n_nulls > 0:
        return False, f"{n_nulls} match_id nulos (refresh no genera IDs)"
    if n_dups > 0:
        return False, f"{n_dups} match_id duplicados"
    return True, f"{len(df)} match_id únicos, 0 nulos"


def check_6_date_semantics():
    logger.info("Check 6: semántica de fechas")
    if not ENRICHED_PARQUET.exists():
        return False, "no existe history_with_xg.parquet"
    if not UPCOMING_PARQUET.exists():
        return False, "no existe upcoming_fixtures.parquet"

    h = pd.read_parquet(ENRICHED_PARQUET)
    u = pd.read_parquet(UPCOMING_PARQUET)
    h_d = pd.to_datetime(h["date"])
    u_d = pd.to_datetime(u["date"])

    logger.info(f"  history tz: {h_d.dt.tz}")
    logger.info(f"  upcoming tz: {u_d.dt.tz}")

    if h_d.dt.tz is not None and str(h_d.dt.tz) != "UTC":
        return False, f"history TZ no es UTC: {h_d.dt.tz}"
    if u_d.dt.tz is not None and str(u_d.dt.tz) != "UTC":
        return False, f"upcoming TZ no es UTC: {u_d.dt.tz}"

    try:
        h_norm = h_d.dt.tz_localize(None)
        u_norm = u_d.dt.tz_localize(None)
        _ = u_norm.min() > h_norm.max()
    except Exception as e:
        return False, f"error normalizando/comparando: {e}"

    return True, f"history={h_d.dtype}, upcoming={u_d.dtype}, normalización OK"


def check_7_alerts_header():
    logger.info("Check 7: header alerts_history.csv")
    if not ALERTS_LOG.exists():
        return False, "no existe alerts_history.csv"
    raw = ALERTS_LOG.read_text(encoding="utf-8").strip().splitlines()
    if not raw:
        return False, "archivo vacío"
    header = next(csv.reader([raw[0]]))
    if header != FIELDS:
        return False, f"header != FIELDS. Ejecutar scripts/_fix_alerts_csv.py"
    return True, f"header coincide ({len(FIELDS)} cols)"


def main():
    logger.info("=" * 60)
    logger.info("VERIFICACIÓN GATE 0")
    logger.info("=" * 60)

    checks = [
        ("1. Fecha máxima nueva", check_1_fecha_maxima),
        ("2. No duplicados", check_2_no_duplicados),
        ("3. Metadatos de cuota", check_3_odds_metadata),
        ("4. Coverage report", check_4_coverage_report),
        ("5. match_id único", check_5_match_id_unique),
        ("6. Semántica de fechas", check_6_date_semantics),
        ("7. Header alerts_history", check_7_alerts_header),
    ]

    passed, failed = 0, 0
    for name, fn in checks:
        try:
            ok, msg = fn()
            logger.info(f"[{'PASS' if ok else 'FAIL'}] {name}: {msg}")
            passed += 1 if ok else 0
            failed += 0 if ok else 1
        except Exception as e:
            logger.error(f"[ERROR] {name}: {e}")
            failed += 1

    logger.info("=" * 60)
    logger.info(f"Resultado: {passed} PASS, {failed} FAIL")
    logger.info("GATE 0: APROBADO" if failed == 0 else "GATE 0: NO APROBADO")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()