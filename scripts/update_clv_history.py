"""
Rellena results/CLV en alerts_history.csv para partidos ya terminados.

Para cada alerta sin resultado:
  - Busca el partido en history_with_xg.parquet (por equipos + fecha ±1 día)
  - Si lo encuentra: rellena odds_close, result, clv_pct, pnl
  - Si no: deja los campos vacíos (el partido aún no ha terminado)

Uso: python scripts/update_clv_history.py
"""
import sys
from pathlib import Path

# ── sys.path ANTES de cualquier import de src ────────────────────────
sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
from datetime import timedelta
import unicodedata

from src.config import OUTPUT_DIR, HISTORY_PARQUET
from src.logger import get_logger

logger = get_logger("update_clv")

ALERTS_LOG = OUTPUT_DIR / "alerts_history.csv"

_STOPWORDS = {
    "fc", "cf", "afc", "sc", "ac", "and", "de", "the", "club", "cd", "ud",
    "sv", "fsv", "tsg", "vfb", "vfl", "bsc", "spvgg", "1899", "07", "04", "05",
    "1", "2", "3",
}

_ALIASES = {
    "munchen": "munich",
    "koln": "cologne",
    "gladbach": "monchengladbach",
    "moenchengladbach": "monchengladbach",
}


def _normalize(name: str) -> str:
    """Normaliza nombre: minúsculas, sin acentos, sin '&', sin guiones/puntos."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = name.replace("&", " and ").replace("-", " ").replace(".", " ").replace("'", " ")
    return " ".join(name.split())


def _tokens(name: str) -> set:
    """Tokens significativos con alias aplicados."""
    raw = _normalize(name).split()
    return {_ALIASES.get(t, t) for t in raw if t not in _STOPWORDS}


def _teams_match(team_a: str, team_b: str) -> bool:
    """Match de equipos: 2+ tokens comunes, subset, o 1 token común."""
    ta, tb = _tokens(team_a), _tokens(team_b)
    if not ta or not tb:
        return False
    if len(ta & tb) >= 2:
        return True
    if ta.issubset(tb) or tb.issubset(ta):
        return True
    return False


def main():
    if not ALERTS_LOG.exists():
        logger.error(f"No existe {ALERTS_LOG}")
        return
    if not HISTORY_PARQUET.exists():
        logger.error(f"No existe {HISTORY_PARQUET}")
        return

    alerts = pd.read_csv(ALERTS_LOG)
    history = pd.read_parquet(HISTORY_PARQUET)
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)

    # Asegurar que las columnas de resultado existen
    for col in ["odds_close", "result", "clv_pct", "pnl"]:
        if col not in alerts.columns:
            alerts[col] = ""

    # Solo alertas sin resultado aún
    pending_mask = alerts["result"].isna() | (alerts["result"].astype(str) == "")
    pending_idx = alerts.index[pending_mask]
    logger.info(f"Alertas pendientes: {len(pending_idx)} / {len(alerts)}")

    updated = 0
    for idx in pending_idx:
        alert = alerts.loc[idx]
        match_date = pd.to_datetime(alert["match_date"])
        window = history[
            (history["date"] >= match_date - timedelta(days=1))
            & (history["date"] <= match_date + timedelta(days=1))
        ]
        if window.empty:
            continue

        candidate = window[
            window["home_team"].apply(lambda x: _teams_match(x, alert["home_team"]))
            & window["away_team"].apply(lambda x: _teams_match(x, alert["away_team"]))
        ]
        if candidate.empty:
            continue

        row = candidate.iloc[0]
        is_draw = int(row["home_goals"] == row["away_goals"])
        result = "W" if is_draw else "L"

        # Cuota de cierre: preferir AvgCD, fallback AvgD
        odds_close_val = row.get("AvgCD") if pd.notna(row.get("AvgCD")) else row.get("AvgD")

        # PnL con stake 1 unidad
        pnl = (float(alert["odds_open"]) - 1) if is_draw else -1.0

        # CLV: (odds_open / odds_close - 1) * 100
        clv_pct = None
        if pd.notna(odds_close_val) and odds_close_val > 0:
            clv_pct = (float(alert["odds_open"]) / float(odds_close_val) - 1) * 100

        alerts.at[idx, "odds_close"] = odds_close_val if pd.notna(odds_close_val) else ""
        alerts.at[idx, "result"] = result
        alerts.at[idx, "clv_pct"] = round(clv_pct, 3) if clv_pct is not None else ""
        alerts.at[idx, "pnl"] = round(pnl, 3)
        updated += 1

    alerts.to_csv(ALERTS_LOG, index=False)
    logger.info(f"Actualizadas {updated} alertas. Guardado en {ALERTS_LOG}")


if __name__ == "__main__":
    main()