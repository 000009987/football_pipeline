"""
Fase 0 — Reporte reproducible de cobertura por liga, temporada y campo.

Detecta:
  - Cobertura de cada campo clave por liga/temporada.
  - Duplicados por match_id y por (date, home_team, away_team).
  - Timestamps naive vs UTC.
  - Fuentes de cuota disponibles (PSCD, AvgCD, B365CD).

Genera:
  - output/coverage_report_YYYYMMDD.csv
  - output/coverage_summary_YYYYMMDD.txt

Uso:
  python scripts/data_coverage_report.py
"""
import sys
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import HISTORY_PARQUET, UPCOMING_PARQUET, OUTPUT_DIR
from src.logger import get_logger

logger = get_logger("data_coverage")
ROOT = Path(__file__).resolve().parent.parent


# Columnas clave a auditar
KEY_COLUMNS = [
    ("home_goals", "goles local"),
    ("away_goals", "goles visitante"),
    ("home_xg", "xG local"),
    ("away_xg", "xG visitante"),
    ("odds_home", "cuota local apertura"),
    ("odds_draw", "cuota empate apertura"),
    ("odds_away", "cuota visitante apertura"),
    ("AvgCD", "cuota empate cierre Avg"),
    ("PSCD", "cuota empate cierre Pinnacle"),
    ("B365CD", "cuota empate cierre Bet365"),
]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit_short() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    return result.stdout.strip() or "unknown"


def coverage_by_league_season(df: pd.DataFrame) -> pd.DataFrame:
    """Cobertura por liga y temporada de cada campo clave."""
    if df.empty:
        return pd.DataFrame()

    present = [(c, label) for c, label in KEY_COLUMNS if c in df.columns]

    rows = []
    for (league, season), g in df.groupby(["competition", "season"], observed=True):
        row = {"competition": league, "season": season, "n_partidos": len(g)}
        for c, _ in present:
            row[f"pct_nulos_{c}"] = round(g[c].isna().mean() * 100, 2)
        rows.append(row)
    return pd.DataFrame(rows)


def write_summary(df: pd.DataFrame, cov: pd.DataFrame, out_path: Path):
    """Escribe el resumen legible en .txt."""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Parquet SHA256: {_sha256_file(HISTORY_PARQUET)}\n")
        f.write(f"Git commit: {_git_commit_short()}\n")
        f.write("Schema: 2.0\n")
        f.write(f"REPORTE DE COBERTURA — {datetime.now().isoformat()}\n")
        f.write("=" * 70 + "\n\n")

        # Info general
        f.write(f"Total partidos: {len(df)}\n")
        f.write(f"Rango fechas: {df['date'].min()} -> {df['date'].max()}\n")
        f.write(f"Ligas: {sorted(df['competition'].unique().tolist())}\n")
        f.write(f"Temporadas: {sorted(df['season'].astype(str).unique().tolist())}\n\n")

        # Timestamps
        d = pd.to_datetime(df["date"])
        f.write(f"Tipo timestamp: {d.dtype}\n")
        f.write(f"Timezone: {d.dt.tz if d.dt.tz is not None else 'NAIVE (no UTC)'}\n\n")

        # Duplicados
        f.write("DUPLICADOS\n" + "-" * 70 + "\n")
        if "match_id" in df.columns:
            dup_id = df["match_id"].duplicated().sum()
            id_nulls = df["match_id"].isna().sum()
            id_unique = df["match_id"].nunique()
            f.write(f"  match_id: {id_nulls} nulos, {id_unique} únicos, {dup_id} duplicados\n")
        dup_key = df.duplicated(subset=["date", "home_team", "away_team"]).sum()
        f.write(f"  (date, home, away): {dup_key} duplicados\n\n")

        # Cobertura por columna global
        f.write("COBERTURA GLOBAL POR COLUMNA\n" + "-" * 70 + "\n")
        for c, label in KEY_COLUMNS:
            if c in df.columns:
                nulos = df[c].isna().sum()
                pct = nulos / len(df) * 100
                f.write(f"  {label:35s} ({c:12s}): {nulos:5d} nulos ({pct:5.1f}%)\n")
            else:
                f.write(f"  {label:35s} ({c:12s}): NO EXISTE\n")
        f.write("\n")

        # Cobertura por liga/temporada
        f.write("COBERTURA POR LIGA/TEMPORADA\n" + "-" * 70 + "\n")
        if not cov.empty:
            f.write(cov.to_string(index=False))
            f.write("\n\n")

        # Upcoming fixtures
        if UPCOMING_PARQUET.exists():
            upcoming = pd.read_parquet(UPCOMING_PARQUET)
            f.write("UPCOMING FIXTURES\n" + "-" * 70 + "\n")
            f.write(f"  Total: {len(upcoming)} partidos\n")
            if "odds_draw" in upcoming.columns:
                f.write(f"  Con cuota de empate: {upcoming['odds_draw'].notna().sum()}\n")
            if "date" in upcoming.columns:
                ud = pd.to_datetime(upcoming["date"])
                f.write(f"  Rango: {ud.min()} -> {ud.max()}\n")


def main():
    if not HISTORY_PARQUET.exists():
        logger.error(f"No existe {HISTORY_PARQUET}")
        return

    logger.info(f"Cargando {HISTORY_PARQUET.name}")
    df = pd.read_parquet(HISTORY_PARQUET)
    df["date"] = pd.to_datetime(df["date"])

    today = datetime.now().strftime("%Y%m%d")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. CSV de coverage por liga/temporada
    cov = coverage_by_league_season(df)
    if not cov.empty:
        out_csv = OUTPUT_DIR / f"coverage_report_{today}.csv"
        cov.to_csv(out_csv, index=False)
        logger.info(f"Guardado: {out_csv}")

    # 2. TXT de resumen
    out_txt = OUTPUT_DIR / f"coverage_summary_{today}.txt"
    write_summary(df, cov, out_txt)
    logger.info(f"Guardado: {out_txt}")

    # 3. Log de resumen
    logger.info(f"Total partidos: {len(df)}")
    if "match_id" in df.columns:
        logger.info(f"match_id: {df['match_id'].isna().sum()} nulos / {len(df)}")
    logger.info(f"Duplicados (date,home,away): {df.duplicated(subset=['date','home_team','away_team']).sum()}")


if __name__ == "__main__":
    main()