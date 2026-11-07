"""
Orquestador del pipeline diario.

Ejecuta en orden:
  1. refresh_history.py       → actualiza histórico con partidos jugados
  2. enrich_history_with_xg   → añade xG a partidos nuevos
  3. fetch_upcoming.py        → descarga fixtures y cuotas
  4. update_clv_history.py    → rellena CLV de alertas ya jugadas
  5. send_alerts.py           → envía alertas a Telegram

Uso:
  python scripts\\daily_run.py              # ejecución completa
  python scripts\\daily_run.py --skip-refresh  # solo alertas (más rápido)
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import subprocess
import time
from datetime import datetime
import os
from pathlib import Path

from src.logger import get_logger

logger = get_logger("daily_run")

PYTHON = sys.executable
ROOT = Path(__file__).resolve().parent.parent

# (nombre, script, args, obligatorio)
STEPS = [
    ("Refresh histórico",    "scripts/refresh_history.py",         [],      False),
    ("Enriquecer xG",        "scripts/enrich_history_with_xg.py",  [],      False),
    ("Fetch fixtures+cuotas","scripts/fetch_upcoming.py",          [],      True),
    ("Actualizar CLV",       "scripts/update_clv_history.py",      [],      False),
    ("Enviar alertas",       "scripts/send_alerts.py",             [],      True),
]


def run_step(name: str, script: str, args: list, required: bool) -> bool:
    """Ejecuta un paso del pipeline. Devuelve True si tuvo éxito."""
    logger.info(f"{'=' * 60}")
    logger.info(f"▶  {name}: {script}")
    logger.info(f"{'=' * 60}")

    cmd = [PYTHON, str(ROOT / script)] + args
    start = time.time()

    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},  # ← añade esta línea
    )

    elapsed = time.time() - start

    # Loguear stdout del subproceso
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            logger.info(f"  {line}")
    if result.stderr:
        for line in result.stderr.strip().splitlines():
            logger.warning(f"  {line}")

    if result.returncode != 0:
        logger.error(f"❌ {name} falló (exit code {result.returncode}) en {elapsed:.1f}s")
        if required:
            logger.error(f"Paso obligatorio fallido. Abortando pipeline.")
            return False
        else:
            logger.warning(f"Paso opcional fallido. Continuando...")
            return True  # continuar

    logger.info(f"✅ {name} OK ({elapsed:.1f}s)")
    return True


def main():
    skip_refresh = "--skip-refresh" in sys.argv

    start_time = datetime.now()
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + f"  PIPELINE DIARIO — {start_time.strftime('%Y-%m-%d %H:%M:%S'):<33}" + "║")
    logger.info("╚" + "═" * 58 + "╝")

    if skip_refresh:
        logger.info("Modo --skip-refresh: omitiendo refresh_history + enrich_xg")
        steps_to_run = [s for s in STEPS if s[0] not in ("Refresh histórico", "Enriquecer xG")]
    else:
        steps_to_run = STEPS

    for name, script, args, required in steps_to_run:
        if not (ROOT / script).exists():
            logger.error(f"❌ No existe {script}. Saltando.")
            if required:
                logger.error("Paso obligatorio no existe. Abortando.")
                return
            continue

        ok = run_step(name, script, args, required)
        if not ok:
            return
        time.sleep(2)  # pequeña pausa entre pasos

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + f"  PIPELINE COMPLETADO en {elapsed:.1f}s".ljust(58) + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("Revisa Telegram para ver si hay picks nuevos.")
    logger.info(f"Log completo: {ROOT / 'logs' / 'pipeline.log'}")


if __name__ == "__main__":
    main()