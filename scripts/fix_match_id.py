"""
Fase 0 — Genera match_id determinístico para partidos sin ID.

El problema: 7733 de 8111 partidos tienen match_id = NaN.
La solución: generar un ID estable a partir de (liga + fecha + equipos)
             usando MD5 truncado a 12 caracteres.

Formato: {liga}_{YYYYMMDD}_{hash12}
Ejemplo: PL_20260815_a3f8b2c1d4e5

Uso:
  python scripts/fix_match_id.py            # aplica el fix
  python scripts/fix_match_id.py --dry-run  # solo muestra, no modifica
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import hashlib
import argparse

import pandas as pd

from src.config import PROCESSED_DATA_DIR
from src.logger import get_logger

logger = get_logger("fix_match_id")

RAW_HISTORY_PARQUET = PROCESSED_DATA_DIR / "history.parquet"
ENRICHED_PARQUET = PROCESSED_DATA_DIR / "history_with_xg.parquet"


def make_match_id(row) -> str:
    """Genera un ID determinístico para un partido."""
    comp = str(row["competition"]).strip().upper()
    date = pd.to_datetime(row["date"]).strftime("%Y%m%d")
    home = str(row["home_team"]).strip().lower()
    away = str(row["away_team"]).strip().lower()
    key = f"{comp}|{date}|{home}|{away}"
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    return f"{comp}_{date}_{h}"


def apply_fix(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica el fix a un DataFrame."""
    df = df.copy()
    if "match_id" not in df.columns:
        df["match_id"] = None

    mask = df["match_id"].isna()
    n_missing = mask.sum()
    if n_missing == 0:
        logger.info("Todos los partidos ya tienen match_id")
        return df

    logger.info(f"Aplicando fix a {n_missing} partidos sin match_id")

    # Construir nueva columna COMO LISTA DE STRINGS (sin mezclar tipos)
    new_ids = []
    for idx in df.index:
        if mask.loc[idx]:
            new_ids.append(make_match_id(df.loc[idx]))
        else:
            val = df.loc[idx, "match_id"]
            # Los originales son floats (ej. 12345.0) → convertir a "12345"
            if isinstance(val, (int, float)):
                new_ids.append(str(int(val)))
            else:
                new_ids.append(str(val))

    # Asignar la columna nueva (TODOS strings, sin NaN ni floats)
    df["match_id"] = new_ids

    # Verificar unicidad
    dup = df["match_id"].duplicated().sum()
    if dup > 0:
        logger.warning(f"Después del fix hay {dup} duplicados. Investigar.")
    else:
        logger.info("✅ match_id único para todos los partidos")

    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo muestra qué se haría, no modifica")
    args = parser.parse_args()

    for path in [RAW_HISTORY_PARQUET, ENRICHED_PARQUET]:
        if not path.exists():
            logger.warning(f"No existe {path}, saltando")
            continue

        logger.info(f"Procesando {path.name}")
        df = pd.read_parquet(path)

        if args.dry_run:
            mask = df["match_id"].isna() if "match_id" in df.columns else pd.Series([True] * len(df))
            logger.info(f"[DRY RUN] {mask.sum()} partidos necesitan fix")
            if mask.sum() > 0:
                sample = df[mask].head(3).apply(make_match_id, axis=1)
                logger.info("Ejemplos de IDs que se generarían:")
                for sid in sample:
                    logger.info(f"  {sid}")
            continue

        df_fixed = apply_fix(df)
        df_fixed.to_parquet(path, index=False)
        logger.info(f"Guardado: {path}")


if __name__ == "__main__":
    main()