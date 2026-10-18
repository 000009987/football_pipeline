"""
Análisis de paper trading tras 4 semanas.

Agrupa alerts_history.csv por tier/liga y calcula:
  - n apuestas
  - % acierto (empates reales)
  - CLV medio
  - Yield simulado

Uso: python scripts/analyze_paper_trading.py
"""
import sys
from pathlib import Path

# ── sys.path ANTES de cualquier import de src ────────────────────────
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from src.config import OUTPUT_DIR
from src.logger import get_logger

logger = get_logger("analyze_paper")

ALERTS_LOG = OUTPUT_DIR / "alerts_history.csv"


def _summarize(df: pd.DataFrame, label: str):
    """Imprime un resumen de métricas para un subconjunto de alertas."""
    n = len(df)
    if n == 0:
        print(f"{label:30s} n=0")
        return

    wins = (df["result"] == "W").sum()
    hit_rate = wins / n * 100

    clv = df["clv_pct"].dropna()
    pnl = df["pnl"].dropna()

    yield_pct = pnl.mean() * 100 if len(pnl) > 0 else np.nan
    clv_mean = clv.mean() if len(clv) > 0 else np.nan
    clv_pos = (clv > 0).mean() * 100 if len(clv) > 0 else np.nan

    print(
        f"{label:30s} n={n:4d}  hit={hit_rate:5.1f}%  "
        f"CLV={clv_mean:+7.3f}%  CLV+={clv_pos:5.1f}%  yield={yield_pct:+7.2f}%"
    )


def main():
    if not ALERTS_LOG.exists():
        logger.error(f"No existe {ALERTS_LOG}")
        return

    df = pd.read_csv(ALERTS_LOG)

    # Filtrar solo alertas con resultado (partidos ya jugados)
    df = df[df["result"].notna() & (df["result"] != "")].copy()

    if df.empty:
        logger.warning(
            "Sin resultados aún. Ejecuta update_clv_history.py primero."
        )
        return

    print("=" * 95)
    print(f"ANÁLISIS PAPER TRADING — {len(df)} alertas con resultado")
    print("=" * 95)
    print()

    print("── Resumen global ──")
    _summarize(df, "TOTAL")

    print()
    print("── Por tier ──")
    for tier in sorted(df["tier"].unique()):
        _summarize(df[df["tier"] == tier], f"tier={tier}")

    print()
    print("── Por liga ──")
    for league in sorted(df["competition"].unique()):
        _summarize(df[df["competition"] == league], f"liga={league}")

    print()
    print("── Solo PICK VALIDADOS (PL+BL1, is_validated=1) ──")
    validated = df[(df["tier"] == "PICK") & (df["is_validated"] == 1)]
    _summarize(validated, "PICK VALIDADO")

    print()
    print("── Solo PICK sin validar (resto de ligas) ──")
    unvalidated = df[(df["tier"] == "PICK") & (df["is_validated"] == 0)]
    _summarize(unvalidated, "PICK sin validar")

    print()
    print("── INFO (cuota alta) ──")
    info = df[df["tier"] == "INFO"]
    _summarize(info, "INFO")

    print()
    print("=" * 95)
    print("CRITERIOS DE DECISIÓN:")
    print("  ✅ Éxito:   PICK VALIDADO yield > +10% AND CLV > +1% AND n >= 30")
    print("  ⚠️ Neutro:  PICK VALIDADO yield entre 0% y +10% (extender paper trading)")
    print("  ❌ Fallo:   PICK VALIDADO yield < 0% (cerrar Draw)")
    print("=" * 95)


if __name__ == "__main__":
    main()