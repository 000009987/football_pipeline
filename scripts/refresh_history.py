"""
Refresca el histórico RAW con partidos jugados desde la última fecha.

ARQUITECTURA:
  - history.parquet           (raw football-data.co.uk)    ← este script actualiza
  - history_with_xg.parquet   (raw + xG)                   ← enrich_history_with_xg.py lo genera

Flujo diario (daily_run.py):
  1. refresh_history.py         ← este script (actualiza history.parquet)
  2. enrich_history_with_xg.py  (regenera history_with_xg.parquet)
  3. fetch_upcoming.py          (cuotas nuevas)
  4. update_clv_history.py      (resultados + CLV)
  5. send_alerts.py             (alertas)

Uso: python scripts/refresh_history.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import io

import pandas as pd
import requests

from src.config import EXTRA_LEAGUES_CSV, PROCESSED_DATA_DIR
from src.ids import apply_match_id
from src.logger import get_logger

logger = get_logger("refresh_history")

RAW_HISTORY_PARQUET = PROCESSED_DATA_DIR / "history.parquet"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina BOM y espacios de los nombres de columnas."""
    df = df.copy()
    df.columns = [
        c.replace("ï»¿", "").replace("\ufeff", "").strip()
        for c in df.columns
    ]
    return df


def fetch_current_season_csvs() -> pd.DataFrame:
    """Descarga y unifica los CSVs de la temporada 2026-27."""
    frames = []
    for key, url in EXTRA_LEAGUES_CSV.items():
        if "2627" not in key:
            continue
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                logger.warning(f"[{key}] HTTP {r.status_code}")
                continue
            df = _normalize_columns(pd.read_csv(io.StringIO(r.text), encoding="latin1"))

            league = key.split("_")[0]
            season_str = key.split("_")[1]
            df["competition"] = league
            df["season"] = int("20" + season_str[:2])
            frames.append(df)
            logger.info(f"[{key}] {len(df)} filas descargadas")
        except Exception as e:
            logger.error(f"[{key}] Error: {e}")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def transform_csv_to_internal(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma CSVs al esquema interno de history.parquet."""
    df = df.copy()

    df["date"] = pd.to_datetime(df.get("Date"), dayfirst=True, errors="coerce")
    df["home_team"] = df.get("HomeTeam")
    df["away_team"] = df.get("AwayTeam")
    df["home_goals"] = pd.to_numeric(df.get("FTHG"), errors="coerce")
    df["away_goals"] = pd.to_numeric(df.get("FTAG"), errors="coerce")
    df["total_goals"] = df["home_goals"] + df["away_goals"]
    df["status"] = "FINISHED"
    # match_id NO se asigna aquí: apply_match_id se encarga al final,
    # después de filtrar filas sin datos válidos, para no generar IDs
    # de partidos descartados.

    df = df.dropna(subset=["date", "home_goals", "away_goals"]).copy()
    df["home_goals"] = df["home_goals"].astype(int)
    df["away_goals"] = df["away_goals"].astype(int)
    df["total_goals"] = df["total_goals"].astype(int)

    return df


def main():
    if not RAW_HISTORY_PARQUET.exists():
        logger.error(
            f"No existe {RAW_HISTORY_PARQUET}. "
            f"Ejecuta 'python main.py --mode download' primero."
        )
        return

    logger.info(f"Cargando {RAW_HISTORY_PARQUET.name}")
    history = _normalize_columns(pd.read_parquet(RAW_HISTORY_PARQUET))
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)

    last_date = history["date"].max()
    n_before = len(history)
    logger.info(f"Histórico actual: {n_before} partidos, hasta {last_date.date()}")

    logger.info("Descargando CSVs de la temporada 2026-27...")
    current_raw = fetch_current_season_csvs()
    if current_raw.empty:
        logger.warning("No se descargó ningún CSV")
        return

    logger.info("Transformando CSVs al esquema interno...")
    current = transform_csv_to_internal(current_raw)
    logger.info(f"Partidos con resultado en CSVs: {len(current)}")

    new_matches = current[current["date"] > last_date].copy()
    logger.info(f"Partidos nuevos (> {last_date.date()}): {len(new_matches)}")

    if new_matches.empty:
        logger.info("El histórico está al día. No hay partidos nuevos.")
        return

    combined = pd.concat([history, new_matches], ignore_index=True, sort=False)
    combined = combined.sort_values("date").reset_index(drop=True)

    before = len(combined)
    combined = combined.drop_duplicates(
        subset=["date", "home_team", "away_team"], keep="last"
    ).reset_index(drop=True)
    removed = before - len(combined)
    if removed > 0:
        logger.info(f"Eliminados {removed} duplicados")

    # Generar match_id para partidos nuevos (determinístico, sin nulos)
    n_nulls_before = (
        combined["match_id"].isna().sum()
        if "match_id" in combined.columns
        else len(combined)
    )
    combined = apply_match_id(combined)
    n_nulls_after = combined["match_id"].isna().sum()
    logger.info(
        f"match_id generados: {n_nulls_before - n_nulls_after} "
        f"({n_nulls_after} nulos restantes)"
    )

    n_after = len(combined)
    combined.to_parquet(RAW_HISTORY_PARQUET, index=False)

    logger.info(f"Guardado: {RAW_HISTORY_PARQUET}")
    logger.info(f"Histórico: {n_before} -> {n_after} partidos (+{n_after - n_before})")
    logger.info(f"Rango: {combined['date'].min().date()} -> {combined['date'].max().date()}")
    logger.info("Siguiente paso: python scripts/enrich_history_with_xg.py")


if __name__ == "__main__":
    main()