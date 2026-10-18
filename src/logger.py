"""
Logger estándar del proyecto: escribe a consola Y a archivo con rotación diaria.

- Consola: para ejecución manual.
- Archivo: logs/pipeline.log (con rotación automática a medianoche, retiene 30 días).
"""
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Directorio de logs en la raíz del proyecto
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline.log"

# Formato común
_FORMATTER = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    """Retorna un logger con handlers de consola y archivo (sin duplicar)."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Handler de consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_FORMATTER)
    logger.addHandler(console_handler)

    # Handler de archivo con rotación diaria
    # - Rota a medianoche
    # - Retiene 30 días de logs
    # - El archivo activo es pipeline.log; los rotados son pipeline.log.YYYY-MM-DD
    try:
        file_handler = TimedRotatingFileHandler(
            LOG_FILE,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
            delay=False,
        )
        file_handler.setFormatter(_FORMATTER)
        file_handler.suffix = "%Y-%m-%d"
        logger.addHandler(file_handler)
    except Exception as e:
        # Si falla el file handler, al menos que la consola funcione
        logger.warning(f"No se pudo crear file handler: {e}")

    return logger