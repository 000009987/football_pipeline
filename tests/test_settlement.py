"""
Tests de liquidación de mercados.

Cubre:
  - 1X2: win, loss (sin push, sin media)
  - O/U 2.5: win, loss (sin push)
  - BTTS: win, loss (sin push)
  - AH: win, loss, push, half-win, half-loss, void
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from src.markets import (
    settle_1x2,
    settle_ou25,
    settle_btts,
    settle_ah,
    SettlementResult,
)


# ─── 1X2 ─────────────────────────────────────────────────────────────

def test_1x2_home_win():
    r = settle_1x2(2, 1, "HOME", odds=2.00)
    assert r.result == "win"
    assert r.pnl == pytest.approx(1.00)  # stake*(odds-1) = 1*(2-1) = 1
    assert r.stake_returned == 1.0


def test_1x2_home_loss():
    r = settle_1x2(0, 1, "HOME", odds=2.00)
    assert r.result == "loss"
    assert r.pnl == pytest.approx(-1.0)
    assert r.stake_returned == 0.0


def test_1x2_draw_win():
    r = settle_1x2(1, 1, "DRAW", odds=3.50)
    assert r.result == "win"
    assert r.pnl == pytest.approx(2.50)  # 1*(3.5-1) = 2.5


def test_1x2_away_win():
    r = settle_1x2(0, 1, "AWAY", odds=4.00)
    assert r.result == "win"
    assert r.pnl == pytest.approx(3.00)


def test_1x2_invalid_pick():
    r = settle_1x2(1, 1, "INVALID", odds=2.00)
    assert r.result == "void"
    assert r.stake_returned == 1.0


# ─── O/U 2.5 ─────────────────────────────────────────────────────────

def test_ou25_over_win():
    r = settle_ou25(2, 1, "OVER", odds=1.90)  # total 3 > 2.5
    assert r.result == "win"
    assert r.pnl == pytest.approx(0.90)


def test_ou25_over_loss():
    r = settle_ou25(1, 1, "OVER", odds=1.90)  # total 2 < 2.5
    assert r.result == "loss"
    assert r.pnl == pytest.approx(-1.0)


def test_ou25_under_win():
    r = settle_ou25(1, 1, "UNDER", odds=1.90)  # total 2 < 2.5
    assert r.result == "win"


def test_ou25_under_loss():
    r = settle_ou25(3, 1, "UNDER", odds=1.90)  # total 4 > 2.5
    assert r.result == "loss"


def test_ou25_exactly_25_no_push():
    """Con línea 2.5 no hay push (total 2.5 no es posible)."""
    r = settle_ou25(2, 0, "OVER", odds=1.90)  # total 2 < 2.5 → loss
    assert r.result == "loss"


# ─── BTTS ────────────────────────────────────────────────────────────

def test_btts_yes_win():
    r = settle_btts(1, 1, "YES", odds=1.80)
    assert r.result == "win"
    assert r.pnl == pytest.approx(0.80)


def test_btts_yes_loss():
    r = settle_btts(2, 0, "YES", odds=1.80)
    assert r.result == "loss"


def test_btts_no_win():
    r = settle_btts(2, 0, "NO", odds=2.10)
    assert r.result == "win"
    assert r.pnl == pytest.approx(1.10)


def test_btts_no_loss():
    r = settle_btts(1, 2, "NO", odds=2.10)
    assert r.result == "loss"


# ─── AH asiático ─────────────────────────────────────────────────────

def test_ah_0_win():
    r = settle_ah(2, 1, handicap=0.0, pick="HOME", odds=1.90)
    assert r.result == "win"


def test_ah_0_loss():
    r = settle_ah(1, 2, handicap=0.0, pick="HOME", odds=1.90)
    assert r.result == "loss"


def test_ah_0_push():
    r = settle_ah(1, 1, handicap=0.0, pick="HOME", odds=1.90)
    assert r.result == "push"
    assert r.pnl == 0.0
    assert r.stake_returned == 1.0


def test_ah_minus_05_win():
    r = settle_ah(2, 1, handicap=-0.5, pick="HOME", odds=1.90)
    assert r.result == "win"


def test_ah_minus_05_loss():
    r = settle_ah(1, 1, handicap=-0.5, pick="HOME", odds=1.90)
    assert r.result == "loss"


def test_ah_plus_05_win_draw():
    """AH +0.5 con empate: home no pierde, gana."""
    r = settle_ah(1, 1, handicap=0.5, pick="HOME", odds=1.90)
    assert r.result == "win"


def test_ah_minus_025_win():
    """AH -0.25 con victoria por 1: ambas mitades ganan."""
    r = settle_ah(2, 1, handicap=-0.25, pick="HOME", odds=1.90)
    assert r.result == "win"


def test_ah_minus_025_half_loss_with_draw():
    """AH -0.25 con empate: mitad 0 (push), mitad -0.5 (loss) → half_loss."""
    r = settle_ah(1, 1, handicap=-0.25, pick="HOME", odds=1.90)
    assert r.result == "half_loss"
    assert r.pnl == pytest.approx(-0.5)
    assert r.stake_returned == 0.5


def test_ah_minus_025_loss():
    """AH -0.25 con derrota: ambas mitades pierden."""
    r = settle_ah(0, 1, handicap=-0.25, pick="HOME", odds=1.90)
    assert r.result == "loss"


def test_ah_plus_025_half_win_with_draw():
    """AH +0.25 con empate: mitad 0 (push), mitad +0.5 (win) → half_win."""
    r = settle_ah(1, 1, handicap=0.25, pick="HOME", odds=1.90)
    assert r.result == "half_win"
    assert r.pnl == pytest.approx(0.45)  # 1*(1.9-1)/2 = 0.45
    assert r.stake_returned == 1.0


def test_ah_plus_075_half_win_with_draw():
    """AH +0.75 con empate: mitad +0.5 (win), mitad +1.0 (win) → win."""
    r = settle_ah(1, 1, handicap=0.75, pick="HOME", odds=1.90)
    assert r.result == "win"


def test_ah_minus_075_loss_with_draw():
    """AH -0.75 con empate: mitad -0.5 (loss), mitad -1.0 (loss) → loss."""
    r = settle_ah(1, 1, handicap=-0.75, pick="HOME", odds=1.90)
    assert r.result == "loss"


def test_ah_away_side():
    """AH desde el lado AWAY: invertir signo y handicap."""
    r = settle_ah(1, 1, handicap=0.0, pick="AWAY", odds=1.90)
    assert r.result == "push"


def test_ah_invalid_pick():
    r = settle_ah(1, 1, handicap=0.0, pick="DRAW", odds=1.90)
    assert r.result == "void"