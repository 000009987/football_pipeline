"""
Verificación del Gate 2 de Fase 2 (Cuotas, EV y Liquidación).

Comprueba 6 condiciones:
  1. src/markets.py existe y exporta las 4 funciones de liquidación.
  2. tests/test_settlement.py existe con >= 20 tests.
  3. FIELDS incluye odds_source, stake, clv_source.
  4. determine_clv_source existe en evaluation_helpers.
  5. update_clv_history.py escribe clv_source.
  6. alerts_history.csv (si existe) tiene las 19 columnas de FIELDS.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import ast

from src.alerts_logger import ALERTS_LOG, FIELDS
from src.logger import get_logger

logger = get_logger("verify_gate2")

ROOT = Path(__file__).resolve().parent.parent
MARKETS = ROOT / "src" / "markets.py"
TEST_SETTLEMENT = ROOT / "tests" / "test_settlement.py"
EVAL_HELPERS = ROOT / "src" / "evaluation_helpers.py"
UPDATE_CLV = ROOT / "scripts" / "update_clv_history.py"


def check_1_markets_module():
    logger.info("Check 1: src/markets.py con 4 funciones")
    if not MARKETS.exists():
        return False, "no existe src/markets.py"
    tree = ast.parse(MARKETS.read_text(encoding="utf-8"))
    funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    required = {"settle_1x2", "settle_ou25", "settle_btts", "settle_ah"}
    missing = required - funcs
    if missing:
        return False, f"faltan funciones: {missing}"
    return True, f"4/4 funciones presentes"


def check_2_settlement_tests():
    logger.info("Check 2: tests de liquidación >= 20")
    if not TEST_SETTLEMENT.exists():
        return False, "no existe tests/test_settlement.py"
    tree = ast.parse(TEST_SETTLEMENT.read_text(encoding="utf-8"))
    tests = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    if len(tests) < 20:
        return False, f"solo {len(tests)} tests (esperados >= 20)"
    return True, f"{len(tests)} tests"


def check_3_fields():
    logger.info("Check 3: FIELDS con odds_source, stake, clv_source")
    required = {"odds_source", "stake", "clv_source"}
    missing = required - set(FIELDS)
    if missing:
        return False, f"faltan en FIELDS: {missing}"
    return True, f"{len(FIELDS)} columnas, las 3 requeridas presentes"


def check_4_determine_clv_source():
    logger.info("Check 4: determine_clv_source importable")
    try:
        from src.evaluation_helpers import determine_clv_source
        # Sanity check
        assert determine_clv_source(2.5, 2.6) == ("Pinnacle", True)
        assert determine_clv_source(None, 2.6) == ("Avg", False)
        assert determine_clv_source(None, None) == ("", False)
    except Exception as e:
        return False, f"error: {e}"
    return True, "importable y funcional"


def check_5_update_clv_writes_clv_source():
    logger.info("Check 5: update_clv_history escribe clv_source")
    if not UPDATE_CLV.exists():
        return False, "no existe scripts/update_clv_history.py"
    content = UPDATE_CLV.read_text(encoding="utf-8")
    if 'at[idx, "clv_source"]' not in content and "at[idx, 'clv_source']" not in content:
        return False, "no escribe clv_source en el CSV"
    if "determine_clv_source" not in content:
        return False, "no usa determine_clv_source"
    return True, "escribe clv_source y usa determine_clv_source"


def check_6_alerts_csv_columns():
    logger.info("Check 6: alerts_history.csv con las 19 columnas")
    if not ALERTS_LOG.exists():
        return False, "no existe output/alerts_history.csv"
    import pandas as pd
    df = pd.read_csv(ALERTS_LOG, nrows=0)
    missing = set(FIELDS) - set(df.columns)
    if missing:
        return False, f"faltan columnas en CSV: {missing}"
    return True, f"{len(df.columns)} columnas == FIELDS"


def main():
    logger.info("=" * 60)
    logger.info("VERIFICACIÓN GATE 2")
    logger.info("=" * 60)

    checks = [
        ("1. markets.py con 4 funciones", check_1_markets_module),
        ("2. tests liquidación >= 20", check_2_settlement_tests),
        ("3. FIELDS con odds_source/stake/clv_source", check_3_fields),
        ("4. determine_clv_source", check_4_determine_clv_source),
        ("5. update_clv escribe clv_source", check_5_update_clv_writes_clv_source),
        ("6. alerts_history.csv con 19 cols", check_6_alerts_csv_columns),
    ]

    passed = 0
    failed = 0
    for name, fn in checks:
        try:
            ok, msg = fn()
            logger.info(f"[{'PASS' if ok else 'FAIL'}] {name}: {msg}")
            passed += 1 if ok else 0
            failed += 0 if ok else 1
        except Exception as e:
            logger.error(f"[ERROR] {name}: {e}")
            failed += 1

    logger.info("=" * 60)
    logger.info(f"Resultado: {passed} PASS, {failed} FAIL")
    logger.info("GATE 2: APROBADO" if failed == 0 else "GATE 2: NO APROBADO")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()