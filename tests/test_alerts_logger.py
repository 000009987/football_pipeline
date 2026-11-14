"""Tests del logger de alertas: verificar FIELDS incluye stake y clv_source."""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.alerts_logger import FIELDS


def test_fields_include_stake():
    assert "stake" in FIELDS, f"Falta 'stake' en FIELDS: {FIELDS}"


def test_fields_include_clv_source():
    assert "clv_source" in FIELDS, f"Falta 'clv_source' en FIELDS: {FIELDS}"


def test_fields_count_is_19():
    """FIELDS debe tener 19 columnas tras añadir stake y clv_source."""
    assert len(FIELDS) == 19, f"FIELDS tiene {len(FIELDS)} cols, esperadas 19"


def test_fields_no_duplicates():
    assert len(FIELDS) == len(set(FIELDS)), f"FIELDS tiene duplicados: {FIELDS}"