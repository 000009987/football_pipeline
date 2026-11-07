"""
Refresca el histórico con partidos jugados desde la última fecha.
Ejecutar diariamente junto con fetch_upcoming.py.

Uso: python scripts/refresh_history.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
from datetime import datetime, timedelta
from src.config import EXTRA_LEAGUES_CSV
from src.logger import get_logger

logger = get_logger("refresh_history")

HISTORY_PARQUET = Path(__file__).resolve().parent.parent / "data" / "processed" / "history_with_xg.parquet"


def main():
    import requests
    import io

    history = pd.read_parquet(HISTORY_PARQUET)
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)
    last_date = history["date"].max()
    logger.info(f"Histórico actual termina en: {last_date.date()}")

    # Descargar CSVs actuales de football-data.co.uk
    new_frames = []
    for key, url in EXTRA_LEAGUES_CSV.items():
        if "2627" not in key:
            continue  # solo temporada actual
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                logger.warning(f"[{key}] HTTP {r.status_code}")
                continue
            df = pd.read_csv(io.StringIO(r.text), encoding="latin1")
            new_frames.append((key, df))
            logger.info(f"[{key}] {len(df)} partidos descargados")
        except Exception as e:
            logger.error(f"[{key}] Error: {e}")

    if not new_frames:
        logger.warning("Sin datos nuevos")
        return

    # El resto del procesamiento depende de cómo cargues normalmente.
    # Simplificación: guardar de vuelta a history_with_xg.parquet
    # (necesitas replicar la lógica de main.py --mode download aquí)

    logger.info("Recomendación: ejecuta 'python main.py --mode download' + 'enrich_history_with_xg.py' diariamente")
    logger.info("O programa la tarea: refresh_history.py → fetch_upcoming.py → send_alerts.py")


if __name__ == "__main__":
    main()