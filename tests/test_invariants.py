"""
Tests automáticos de las invariantes del contrato de datos.

Estos tests son el "safety net" de Fase 1: si cualquier cambio rompe
una invariante, el test falla en CI antes de mergear.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd

from src.config import PROCESSED_DATA_DIR, OUTPUT_DIR

RAW_HISTORY = PROCESSED_DATA_DIR / "history.parquet"
ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"
ALERTS_LOG = OUTPUT_DIR / "alerts_history.csv"

ENRICHED_ONLY_COLUMNS = {"home_xg", "away_xg", "home_np_xg", "away_np_xg"}


@pytest.fixture(scope="module")
def enriched():
    if not ENRICHED.exists():
        pytest.skip(f"No existe {ENRICHED}")
    df = pd.read_parquet(ENRICHED)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture(scope="module")
def raw():
    if not RAW_HISTORY.exists():
        pytest.skip(f"No existe {RAW_HISTORY}")
    df = pd.read_parquet(RAW_HISTORY)
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_i1_match_id_unique(enriched):
    assert "match_id" in enriched.columns
    assert enriched["match_id"].duplicated().sum() == 0


def test_i2_match_id_not_null(enriched):
    assert "match_id" in enriched.columns
    assert enriched["match_id"].isna().sum() == 0


def test_i3_date_not_null(enriched):
    assert enriched["date"].isna().sum() == 0


def test_i4_goals_not_null_on_finished(enriched):
    finished = enriched[enriched["status"] == "FINISHED"] if "status" in enriched.columns else enriched
    assert finished["home_goals"].isna().sum() == 0
    assert finished["away_goals"].isna().sum() == 0


def test_i5_no_dup_by_key(enriched):
    assert enriched.duplicated(subset=["date", "home_team", "away_team"]).sum() == 0


def test_i6_enriched_superset_of_raw(raw, enriched):
    assert len(raw) == len(enriched), f"raw={len(raw)}, enriched={len(enriched)}"
    assert ENRICHED_ONLY_COLUMNS.issubset(set(enriched.columns))
    missing = set(raw.columns) - set(enriched.columns)
    assert not missing, f"enriched le faltan columnas: {missing}"


def test_i7_alerts_no_dups():
    if not ALERTS_LOG.exists():
        pytest.skip("No existe alerts_history.csv")
    df = pd.read_csv(ALERTS_LOG)
    dup = df.duplicated(subset=["competition", "home_team", "away_team", "match_date"]).sum()
    assert dup == 0, f"{dup} duplicados en alerts_history.csv"