"""
Tests de cálculo de PnL respetando el stake.

Bug real (Fase 2): update_clv_history.py calculaba PnL como si todas las
apuestas fueran de 1 unidad, ignorando stake=0 (INFO) y stake variable (Kelly).

Estos tests verifican que calculate_pnl respeta el stake.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from src.evaluation_helpers import calculate_pnl


# ─── PICK con stake 1.0 ──────────────────────────────────────────────

def test_pick_win():
    """PICK stake=1.0, gana con cuota 2.5 → pnl = 1.5."""
    assert calculate_pnl(2.5, 1.0, True) == pytest.approx(1.5)


def test_pick_loss():
    """PICK stake=1.0, pierde con cuota 2.5 → pnl = -1.0."""
    assert calculate_pnl(2.5, 1.0, False) == pytest.approx(-1.0)


def test_pick_win_low_odds():
    """PICK stake=1.0, gana con cuota 1.5 → pnl = 0.5."""
    assert calculate_pnl(1.5, 1.0, True) == pytest.approx(0.5)


# ─── INFO con stake 0.0 ──────────────────────────────────────────────

def test_info_win_zero_pnl():
    """INFO stake=0.0, gana → pnl = 0.0 (no se apostó)."""
    assert calculate_pnl(2.5, 0.0, True) == 0.0


def test_info_loss_zero_pnl():
    """INFO stake=0.0, pierde → pnl = 0.0 (no se apostó)."""
    assert calculate_pnl(2.5, 0.0, False) == 0.0


# ─── Kelly fraccionado (stake variable) ──────────────────────────────

def test_kelly_win():
    """Kelly stake=0.06, gana con cuota 2.5 → pnl = 0.09."""
    assert calculate_pnl(2.5, 0.06, True) == pytest.approx(0.09)


def test_kelly_loss():
    """Kelly stake=0.06, pierde con cuota 2.5 → pnl = -0.06."""
    assert calculate_pnl(2.5, 0.06, False) == pytest.approx(-0.06)


def test_kelly_win_high_odds():
    """Kelly stake=0.15, gana con cuota 4.0 → pnl = 0.45."""
    assert calculate_pnl(4.0, 0.15, True) == pytest.approx(0.45)


# ─── Edge cases ──────────────────────────────────────────────────────

def test_negative_stake_treated_as_zero():
    """Stake negativo (inválido): tratado como 0.0."""
    assert calculate_pnl(2.5, -0.5, True) == 0.0


def test_odds_at_one():
    """Cuota 1.0, gana → pnl = 0.0 (sin ganancia)."""
    assert calculate_pnl(1.0, 1.0, True) == pytest.approx(0.0)


def test_odds_below_one_win():
    """Cuota 0.9 (inválida, gana): pnl = -0.1 (pierde dinero aunque gane)."""
    assert calculate_pnl(0.9, 1.0, True) == pytest.approx(-0.1)