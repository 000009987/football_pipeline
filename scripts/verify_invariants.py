"""
Verificación de las 7 invariantes del contrato de datos (I1-I7).

Se ejecuta antes de cualquier test, backtest o entrenamiento de modelo.
Si alguna invariante falla, el pipeline está en estado inconsistente y
cualquier resultado derivado es sospechoso.

Invariantes (del docs/data_contract.md §4):
  I1: match_id único por partido
  I2: match_id no nulo
  I3: date sin nulos
  I4: home_goals y away_goals sin nulos en partidos FINISHED
  I5: No duplicados por (date, home_team, away_team)
  I6: history_with_xg.parquet ⊇ history.parquet (mismo nº filas + 4 columnas xG)
  I7: alerts_history.csv sin duplicados por (competition, home_team, away_team, match_date)

Uso:
  python scripts/verify_invariants.py
  python scripts/verify_invariants.py --strict    # exit code 1 si falla alguna
  python scripts/verify_invariants.py --json      # salida JSON para CI
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR
from src.logger import get_logger

logger = get_logger("verify_invariants")

RAW_HISTORY = PROCESSED_DATA_DIR / "history.parquet"
ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"
ALERTS_LOG = OUTPUT_DIR / "alerts_history.csv"

# Columnas que solo existen en el enriquecido (añadidas por enrich_history_with_xg.py)
ENRICHED_ONLY_COLUMNS = {"home_xg", "away_xg", "home_np_xg", "away_np_xg"}


def _load_parquet(path: Path) -> pd.DataFrame:
    """Carga un parquet y normaliza date a datetime."""
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ─── Invariantes ──────────────────────────────────────────────────────────

def i1_match_id_unique(df: pd.DataFrame) -> tuple[bool, str]:
    """I1: match_id único por partido."""
    if "match_id" not in df.columns:
        return False, "falta columna match_id"
    dup = int(df["match_id"].duplicated().sum())
    if dup > 0:
        return False, f"{dup} match_id duplicados"
    return True, f"{len(df)} match_id únicos"


def i2_match_id_not_null(df: pd.DataFrame) -> tuple[bool, str]:
    """I2: match_id no nulo."""
    if "match_id" not in df.columns:
        return False, "falta columna match_id"
    nulls = int(df["match_id"].isna().sum())
    if nulls > 0:
        return False, f"{nulls} match_id nulos"
    return True, f"0 match_id nulos"


def i3_date_not_null(df: pd.DataFrame) -> tuple[bool, str]:
    """I3: date sin nulos."""
    if "date" not in df.columns:
        return False, "falta columna date"
    nulls = int(df["date"].isna().sum())
    if nulls > 0:
        return False, f"{nulls} date nulos"
    return True, f"0 date nulos"


def i4_goals_not_null_on_finished(df: pd.DataFrame) -> tuple[bool, str]:
    """I4: home_goals y away_goals sin nulos en partidos FINISHED."""
    if "status" in df.columns:
        finished = df[df["status"] == "FINISHED"]
    else:
        # Si no hay status, asumimos que todos son FINISHED
        finished = df

    missing_cols = [c for c in ["home_goals", "away_goals"] if c not in df.columns]
    if missing_cols:
        return False, f"faltan columnas: {missing_cols}"

    null_home = int(finished["home_goals"].isna().sum())
    null_away = int(finished["away_goals"].isna().sum())
    if null_home > 0 or null_away > 0:
        return False, f"home_goals nulos: {null_home}, away_goals nulos: {null_away}"
    return True, f"{len(finished)} partidos FINISHED sin nulos en goles"


def i5_no_dup_by_key(df: pd.DataFrame) -> tuple[bool, str]:
    """I5: No duplicados por (date, home_team, away_team)."""
    missing = [c for c in ["date", "home_team", "away_team"] if c not in df.columns]
    if missing:
        return False, f"faltan columnas: {missing}"
    dup = int(df.duplicated(subset=["date", "home_team", "away_team"]).sum())
    if dup > 0:
        return False, f"{dup} duplicados por (date, home_team, away_team)"
    return True, "0 duplicados por (date, home_team, away_team)"


def i6_enriched_superset_of_raw() -> tuple[bool, str]:
    """I6: history_with_xg.parquet ⊇ history.parquet (mismo nº filas + 4 cols xG)."""
    if not RAW_HISTORY.exists():
        return False, f"no existe {RAW_HISTORY.name}"
    if not ENRICHED.exists():
        return False, f"no existe {ENRICHED.name}"

    raw = pd.read_parquet(RAW_HISTORY)
    enriched = pd.read_parquet(ENRICHED)

    # 1. Mismo nº de filas
    if len(raw) != len(enriched):
        return False, f"raw={len(raw)} filas, enriched={len(enriched)} filas"

    # 2. El enriquecido debe tener las 4 columnas xG
    missing_xg = ENRICHED_ONLY_COLUMNS - set(enriched.columns)
    if missing_xg:
        return False, f"enriched le faltan columnas xG: {missing_xg}"

    # 3. Las columnas del raw deben ser subset de las del enriched
    raw_cols = set(raw.columns)
    enriched_cols = set(enriched.columns)
    missing_cols = raw_cols - enriched_cols
    if missing_cols:
        return False, f"enriched le faltan {len(missing_cols)} columnas del raw"

    return True, f"{len(raw)} filas, {len(raw_cols)} cols raw + 4 cols xG"


def i7_alerts_no_dups() -> tuple[bool, str]:
    """I7: alerts_history.csv sin duplicados por (competition, home_team, away_team, match_date)."""
    if not ALERTS_LOG.exists():
        return False, f"no existe {ALERTS_LOG.name}"

    df = pd.read_csv(ALERTS_LOG)
    missing = [c for c in ["competition", "home_team", "away_team", "match_date"] if c not in df.columns]
    if missing:
        return False, f"faltan columnas: {missing}"

    dup = int(df.duplicated(subset=["competition", "home_team", "away_team", "match_date"]).sum())
    if dup > 0:
        return False, f"{dup} duplicados en alerts_history.csv"
    return True, f"{len(df)} alertas sin duplicados"


# ─── Main ─────────────────────────────────────────────────────────────────

def run_all() -> dict:
    """Ejecuta las 7 invariantes y devuelve dict con resultados."""
    results = {}

    # I1-I5 se ejecutan sobre el enriquecido (es la fuente de verdad)
    if ENRICHED.exists():
        enriched = _load_parquet(ENRICHED)
    else:
        logger.error(f"No existe {ENRICHED}")
        return {"error": "enriched parquet no existe"}

    checks = [
        ("I1", "match_id único", lambda: i1_match_id_unique(enriched)),
        ("I2", "match_id no nulo", lambda: i2_match_id_not_null(enriched)),
        ("I3", "date no nulo", lambda: i3_date_not_null(enriched)),
        ("I4", "goles no nulos en FINISHED", lambda: i4_goals_not_null_on_finished(enriched)),
        ("I5", "sin duplicados por (date, teams)", lambda: i5_no_dup_by_key(enriched)),
        ("I6", "enriched ⊇ raw", lambda: i6_enriched_superset_of_raw()),
        ("I7", "alerts sin duplicados", lambda: i7_alerts_no_dups()),
    ]

    for inv_id, desc, fn in checks:
        try:
            ok, msg = fn()
            results[inv_id] = {"ok": ok, "desc": desc, "msg": msg}
        except Exception as e:
            results[inv_id] = {"ok": False, "desc": desc, "msg": f"EXCEPTION: {e}"}

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Exit code 1 si alguna invariante falla")
    parser.add_argument("--json", action="store_true",
                        help="Salida en JSON (para CI)")
    args = parser.parse_args()

    results = run_all()

    if "error" in results:
        logger.error(f"Error fatal: {results['error']}")
        if args.json:
            print(json.dumps(results, indent=2))
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        logger.info("=" * 60)
        logger.info("VERIFICACIÓN DE INVARIANTES I1-I7")
        logger.info("=" * 60)
        for inv_id, data in results.items():
            status = "PASS" if data["ok"] else "FAIL"
            logger.info(f"[{status}] {inv_id}: {data['desc']} → {data['msg']}")
        logger.info("=" * 60)

    n_pass = sum(1 for d in results.values() if d["ok"])
    n_fail = len(results) - n_pass
    logger.info(f"Resultado: {n_pass} PASS, {n_fail} FAIL")

    if n_fail > 0:
        logger.error("Invariantes rotas. NO ejecutar backtests ni modelos.")
        if args.strict:
            sys.exit(1)
    else:
        logger.info("Todas las invariantes se cumplen. Pipeline consistente.")


if __name__ == "__main__":
    main()