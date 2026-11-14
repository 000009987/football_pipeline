"""
Tests de desvig, validación, Kelly fraccionado y determinación de fuente CLV.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from src.evaluation_helpers import (
    remove_overround,
    validate_odds,
    validate_prob,
    kelly_fraction,
    determine_clv_source,
)


# ─── remove_overround ────────────────────────────────────────────────

def test_remove_overround_sums_to_one():
    probs = remove_overround([2.5, 3.4, 2.9])
    assert sum(probs) == pytest.approx(1.0, abs=1e-6)


def test_remove_overround_implied_values():
    """Con cuotas 2.5/3.4/2.9, el overround es ~3.9%, las probs normalizadas son 38.5%/28.3%/33.2%."""
    probs = remove_overround([2.5, 3.4, 2.9])
    assert probs[0] == pytest.approx(0.385, abs=0.005)
    assert probs[1] == pytest.approx(0.283, abs=0.005)
    assert probs[2] == pytest.approx(0.332, abs=0.005)


def test_remove_overround_invalid_odds_out_of_range():
    assert remove_overround([0.5, 3.0, 3.0]) == []
    assert remove_overround([101.0, 3.0, 3.0]) == []


def test_remove_overround_empty():
    assert remove_overround([]) == []


def test_remove_overround_invalid_types():
    assert remove_overround(["2.0", 3.0, 3.0]) == []
    assert remove_overround([None, 3.0, 3.0]) == []


# ─── validate_odds ───────────────────────────────────────────────────

def test_validate_odds_boundaries():
    assert validate_odds(1.0) is True
    assert validate_odds(100.0) is True
    assert validate_odds(0.99) is False
    assert validate_odds(101.0) is False


def test_validate_odds_invalid():
    assert validate_odds(-1) is False
    assert validate_odds(0) is False
    assert validate_odds("2.0") is False
    assert validate_odds(None) is False


# ─── validate_prob ───────────────────────────────────────────────────

def test_validate_prob_boundaries():
    assert validate_prob(0.0) is True
    assert validate_prob(1.0) is True
    assert validate_prob(0.5) is True


def test_validate_prob_invalid():
    assert validate_prob(-0.1) is False
    assert validate_prob(1.1) is False
    assert validate_prob("0.5") is False
    assert validate_prob(None) is False


# ─── kelly_fraction ──────────────────────────────────────────────────

def test_kelly_positive_ev():
    """p=0.5, o=3.0 → ev=0.5, kelly_full=0.25, kelly_frac=0.25*0.25=0.0625 → 0.06."""
    k = kelly_fraction(0.5, 3.0, fraction=0.25)
    assert k == pytest.approx(0.06, abs=0.01)


def test_kelly_zero_ev():
    """p=0.33, o=3.0 → ev≈-0.01 → 0."""
    k = kelly_fraction(0.33, 3.0)
    assert k == 0.0


def test_kelly_negative_ev():
    """p=0.2, o=3.0 → ev=-0.4 → 0."""
    k = kelly_fraction(0.2, 3.0)
    assert k == 0.0


def test_kelly_cap_at_one():
    """Con fraction=2.0 (por encima de 1.0), el stake se capa a 1.0."""
    # p=0.9, o=10, fraction=2.0: kelly_full=0.889, kelly_frac=1.777 → cap 1.0
    k = kelly_fraction(0.9, 10.0, fraction=2.0)
    assert k == 1.0


def test_kelly_invalid_inputs():
    assert kelly_fraction(-0.5, 3.0) == 0.0
    assert kelly_fraction(0.5, 0.9) == 0.0
    assert kelly_fraction(0.5, "3.0") == 0.0


def test_kelly_fraction_half():
    """Con fraction=0.5, el stake debe ser el doble que con 0.25."""
    k25 = kelly_fraction(0.5, 3.0, fraction=0.25)
    k50 = kelly_fraction(0.5, 3.0, fraction=0.5)
    assert k50 == pytest.approx(k25 * 2, abs=0.01)


# ─── determine_clv_source ────────────────────────────────────────────

def test_determine_clv_source_pinnacle_match():
    """Pinnacle open + PSCD close: comparable."""
    src, comp = determine_clv_source(2.5, 2.6, "pinnacle")
    assert src == "Pinnacle"
    assert comp is True


def test_determine_clv_source_pinnacle_mismatch():
    """Bet365 open + PSCD close: NO comparable (fuente distinta)."""
    src, comp = determine_clv_source(2.5, 2.6, "bet365")
    assert src == "Pinnacle"
    assert comp is False


def test_determine_clv_source_avg_match():
    """Avg open + AvgCD close: comparable."""
    src, comp = determine_clv_source(None, 2.6, "avg")
    assert src == "Avg"
    assert comp is True


def test_determine_clv_source_avg_mismatch():
    """Pinnacle open + AvgCD close: NO comparable."""
    src, comp = determine_clv_source(None, 2.6, "pinnacle")
    assert src == "Avg"
    assert comp is False


def test_determine_clv_source_none():
    """Sin cierre: vacío, no comparable."""
    src, comp = determine_clv_source(None, None, "")
    assert src == ""
    assert comp is False


def test_determine_clv_source_nan():
    """NaN en PSCD: fallback a Avg si apertura es avg/vacío."""
    import pandas as pd
    src, comp = determine_clv_source(pd.NA, 2.6, "avg")
    assert src == "Avg"
    assert comp is True


def test_determine_clv_source_pscd_zero():
    """PSCD=0: fallback a Avg si apertura es avg."""
    src, comp = determine_clv_source(0.0, 2.6, "avg")
    assert src == "Avg"
    assert comp is True


def test_determine_clv_source_pscd_negative():
    """PSCD negativo: fallback a Avg."""
    src, comp = determine_clv_source(-1.0, 2.6, "avg")
    assert src == "Avg"
    assert comp is True


def test_determine_clv_source_empty_open_matches_avg():
    """Open vacío (pre-fix) + AvgCD: asumir Avg como comparable."""
    src, comp = determine_clv_source(None, 2.6, "")
    assert src == "Avg"
    assert comp is True