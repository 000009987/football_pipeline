"""
Fase 0 — Convierte la columna `date` de naive a UTC en history.parquet
y history_with_xg.parquet.

Las fechas de football-data.co.uk son del mismo día en hora UK (Europe/London).
Convertir a UTC: interpretar como Europe/London y convertir a UTC.

Uso:
  python scripts/fix_timestamps_utc.py --dry-run   # solo muestra
  python scripts/fix_timestamps_utc.py             # aplica
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import argparse

import pandas as pd

from src.config import PROCESSED_DATA_DIR
from src.logger import get_logger

logger = get_logger("fix_timestamps")

RAW_HISTORY_PARQUET = PROCESSED_DATA_DIR / "history.parquet"
ENRICHED_PARQUET = PROCESSED_DATA_DIR / "history_with_xg.parquet"


def convert_to_utc(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte `date` de naive a UTC asumiendo Europe/London como TZ origen."""
    df = df.copy()
    d = pd.to_datetime(df["date"])

    if d.dt.tz is not None:
        logger.info(f"Ya tiene TZ: {d.dt.tz}. Convirtiendo a UTC.")
        df["date"] = d.dt.tz_convert("UTC")
    else:
        logger.info("Naive detectado. Asumiendo UTC y etiquetando TZ.")
        df["date"] = d.dt.tz_localize("UTC")

    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for path in [RAW_HISTORY_PARQUET, ENRICHED_PARQUET]:
        if not path.exists():
            logger.warning(f"No existe {path}, saltando")
            continue

        logger.info(f"Procesando {path.name}")
        df = pd.read_parquet(path)
        d_before = pd.to_datetime(df["date"])

        logger.info(f"  Antes: dtype={d_before.dtype}, tz={d_before.dt.tz}, "
                    f"min={d_before.min()}, max={d_before.max()}")

        if args.dry_run:
            logger.info("  [DRY RUN] No se modifica")
            continue

        df_utc = convert_to_utc(df)
        d_after = df_utc["date"]

        logger.info(f"  Después: dtype={d_after.dtype}, tz={d_after.dt.tz}, "
                    f"min={d_after.min()}, max={d_after.max()}")

        df_utc.to_parquet(path, index=False)
        logger.info(f"  Guardado: {path}")


if __name__ == "__main__":
    main()