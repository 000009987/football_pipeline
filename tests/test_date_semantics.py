"""
Test de consistencia de TZ entre history y upcoming.

Bug real de Bloque 2: history_with_xg.parquet estaba como datetime64[ns, UTC]
(aware), upcoming_fixtures.parquet como datetime64[ns] (naive). enrich_fixture
fallaba con "Invalid comparison between dtype=datetime64[ns, UTC] and Timestamp".

Estos tests previenen la regresión.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest

from src.config import PROCESSED_DATA_DIR, UPCOMING_PARQUET

HISTORY_WITH_XG = PROCESSED_DATA_DIR / "history_with_xg.parquet"
HISTORY_RAW = PROCESSED_DATA_DIR / "history.parquet"


@pytest.fixture(scope="module")
def history_with_xg():
    if not HISTORY_WITH_XG.exists():
        pytest.skip(f"No existe {HISTORY_WITH_XG}")
    return pd.read_parquet(HISTORY_WITH_XG)


@pytest.fixture(scope="module")
def history_raw():
    if not HISTORY_RAW.exists():
        pytest.skip(f"No existe {HISTORY_RAW}")
    return pd.read_parquet(HISTORY_RAW)


@pytest.fixture(scope="module")
def upcoming():
    if not UPCOMING_PARQUET.exists():
        pytest.skip(f"No existe {UPCOMING_PARQUET}")
    return pd.read_parquet(UPCOMING_PARQUET)


def test_history_with_xg_is_naive_utc(history_with_xg):
    """history_with_xg.parquet es naive UTC (normalizado con _normalize_dates_to_naive.py)."""
    d = pd.to_datetime(history_with_xg["date"])
    assert d.dt.tz is None, f"Esperado naive, tiene tz={d.dt.tz}. dtype={d.dtype}"
    

def test_history_raw_is_naive_utc(history_raw):
    """history.parquet es naive (sin TZ). refresh_history.py lo escribe así."""
    d = pd.to_datetime(history_raw["date"])
    assert d.dt.tz is None, f"Esperado naive, tiene tz={d.dt.tz}. dtype={d.dtype}"


def test_upcoming_is_naive_utc(upcoming):
    """upcoming_fixtures.parquet es naive. fetch_upcoming.py lo escribe así."""
    d = pd.to_datetime(upcoming["date"])
    assert d.dt.tz is None, f"Esperado naive, tiene tz={d.dt.tz}. dtype={d.dtype}"


def test_normalization_makes_both_naive(history_with_xg, upcoming):
    """El fix de send_alerts.py: normalizar ambos y comparar."""
    h = history_with_xg.copy()
    u = upcoming.copy()
    h["date"] = pd.to_datetime(h["date"]).dt.tz_localize(None)
    u["date"] = pd.to_datetime(u["date"]).dt.tz_localize(None)
    assert h["date"].dt.tz is None
    assert u["date"].dt.tz is None
    # Comparación no debe fallar
    _ = u["date"].min() > h["date"].max()


def test_enrich_fixture_works_after_normalization(history_with_xg, upcoming):
    """Smoke test: enrich_fixture funciona con ambos normalizados."""
    if upcoming.empty:
        pytest.skip("upcoming_fixtures.parquet está vacío")

    from src.feature_engineering import enrich_fixture

    h = history_with_xg.copy()
    u = upcoming.copy()
    h["date"] = pd.to_datetime(h["date"]).dt.tz_localize(None)
    u["date"] = pd.to_datetime(u["date"]).dt.tz_localize(None)

    row = u.iloc[0]
    f = enrich_fixture(row, h, as_of_date=row["date"])
    assert "lambda_home" in f
    assert "lambda_away" in f
    assert f["lambda_home"] > 0
    assert f["lambda_away"] > 0
