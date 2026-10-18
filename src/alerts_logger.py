"""Registro persistente de alertas enviadas para paper trading y CLV tracking."""
import csv
from datetime import datetime

from src.config import OUTPUT_DIR
from src.logger import get_logger

logger = get_logger("alerts_logger")

ALERTS_LOG = OUTPUT_DIR / "alerts_history.csv"

FIELDS = [
    "timestamp_sent", "competition", "match_date", "home_team", "away_team",
    "prob_D", "odds_open", "ev", "tier", "is_validated",
    "odds_close", "result", "clv_pct", "pnl",
]


def log_alert(alert: dict):
    """Añade una alerta al CSV. Crea el archivo con cabecera si no existe."""
    ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    file_exists = ALERTS_LOG.exists()

    try:
        with open(ALERTS_LOG, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            if not file_exists:
                writer.writeheader()
            row = {k: alert.get(k, "") for k in FIELDS}
            row["timestamp_sent"] = datetime.now().isoformat(timespec="seconds")
            writer.writerow(row)
    except Exception as e:
        logger.error(f"No se pudo escribir en {ALERTS_LOG}: {e}")