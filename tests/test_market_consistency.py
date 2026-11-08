"""
Tests de coherencia entre mercados derivados de la matriz de marcadores.

Verifica que:
  - market_probabilities() sume 1.0
  - _ou_btts_from_matrix() sume coherente con market_probabilities()
  - Over/Under son complementarios y monótonos
  - BTTS es coherente con Over 1.5
  - Resultados exactos suman lo mismo que los agregados
  - Casos extremos (lambdas bajos/altos) no rompen las invariantes
"""
import numpy as np
import pytest

from src.models import score_matrix_dixon_coles
from src.evaluation import _ou_btts_from_matrix


@pytest.fixture
def matrix_default():
    """Matriz típica de partido equilibrado."""
    return score_matrix_dixon_coles(1.5, 1.2, rho=-0.13)


@pytest.fixture
def matrix_high_goals():
    """Matriz con lambdas altos (partido ofensivo)."""
    return score_matrix_dixon_coles(3.5, 2.5, rho=-0.13)


@pytest.fixture
def matrix_low_goals():
    """Matriz con lambdas bajos (partido defensivo)."""
    return score_matrix_dixon_coles(0.5, 0.6, rho=-0.13)


# ─── Coherencia global ───────────────────────────────────────────────

def test_market_probs_sum_to_one(matrix_default):
    """P(H) + P(D) + P(A) = 1.0."""
    from src.models import market_probabilities
    p = market_probabilities(matrix_default)
    total = p["prob_home"] + p["prob_draw"] + p["prob_away"]
    assert np.isclose(total, 1.0, atol=1e-6)


def test_ou_btts_sum_to_one(matrix_default):
    """Over + Under = 1.0 y BTTS + no-BTTS = 1.0."""
    p = _ou_btts_from_matrix(matrix_default)
    assert np.isclose(p["prob_over_25"] + p["prob_under_25"], 1.0, atol=1e-6)
    assert np.isclose(p["prob_btts_yes"] + p["prob_btts_no"], 1.0, atol=1e-6)


def test_market_and_ou_consistent(matrix_default):
    """P(D) del mercado debe ser compatible con los resultados exactos."""
    from src.models import market_probabilities
    n = matrix_default.shape[0]
    p_draw_from_matrix = sum(matrix_default[i, i] for i in range(n))
    p_market = market_probabilities(matrix_default)
    assert np.isclose(p_draw_from_matrix, p_market["prob_draw"], atol=1e-6)


# ─── Monotonicidad de Over/Under ─────────────────────────────────────

def test_over_monotonic_decreasing(matrix_default):
    """P(Over 0.5) >= P(Over 1.5) >= P(Over 2.5) >= P(Over 3.5)."""
    n = matrix_default.shape[0]
    over = {}
    for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
        over[line] = sum(
            matrix_default[i, j]
            for i in range(n) for j in range(n)
            if i + j > line
        )
    assert over[0.5] >= over[1.5] >= over[2.5] >= over[3.5] >= over[4.5]


def test_over_05_high(matrix_default):
    """P(Over 0.5) debe ser > 0.9 en un partido normal."""
    n = matrix_default.shape[0]
    p_00 = matrix_default[0, 0]
    p_over_05 = 1 - p_00
    assert p_over_05 > 0.9


# ─── Coherencia BTTS con Over 1.5 ────────────────────────────────────

def test_btts_le_over_15(matrix_default):
    """P(BTTS) <= P(Over 1.5), porque BTTS implica al menos 2 goles."""
    n = matrix_default.shape[0]
    p_over_15 = sum(
        matrix_default[i, j]
        for i in range(n) for j in range(n)
        if i + j >= 2
    )
    p_btts = _ou_btts_from_matrix(matrix_default)["prob_btts_yes"]
    assert p_btts <= p_over_15 + 1e-6


def test_btts_manual_computation(matrix_default):
    """P(BTTS) calculado manualmente = P(BTTS) de _ou_btts_from_matrix."""
    n = matrix_default.shape[0]
    p_btts_manual = sum(
        matrix_default[i, j]
        for i in range(1, n) for j in range(1, n)
    )
    p_btts = _ou_btts_from_matrix(matrix_default)["prob_btts_yes"]
    assert np.isclose(p_btts_manual, p_btts, atol=1e-6)


def test_btts_complement(matrix_default):
    """P(BTTS no) debe ser compatible con P(0-0) + P(1-0) + P(0-1) + ... (sin goles en ambos)."""
    n = matrix_default.shape[0]
    p_no_btts_manual = sum(
        matrix_default[i, j]
        for i in range(n) for j in range(n)
        if i == 0 or j == 0
    )
    p_no_btts = _ou_btts_from_matrix(matrix_default)["prob_btts_no"]
    assert np.isclose(p_no_btts_manual, p_no_btts, atol=1e-6)


# ─── Casos extremos: matrices con lambdas altos/bajos ────────────────

def test_consistency_high_goals(matrix_high_goals):
    """Las invariantes deben mantenerse con lambdas altos."""
    from src.models import market_probabilities
    p_mkt = market_probabilities(matrix_high_goals)
    total = p_mkt["prob_home"] + p_mkt["prob_draw"] + p_mkt["prob_away"]
    assert np.isclose(total, 1.0, atol=1e-6)

    p_ou = _ou_btts_from_matrix(matrix_high_goals)
    assert np.isclose(p_ou["prob_over_25"] + p_ou["prob_under_25"], 1.0, atol=1e-6)
    assert np.isclose(p_ou["prob_btts_yes"] + p_ou["prob_btts_no"], 1.0, atol=1e-6)

    # Con lambdas altos, Over 2.5 debe ser alto
    assert p_ou["prob_over_25"] > 0.7


def test_consistency_low_goals(matrix_low_goals):
    """Las invariantes deben mantenerse con lambdas bajos."""
    from src.models import market_probabilities
    p_mkt = market_probabilities(matrix_low_goals)
    total = p_mkt["prob_home"] + p_mkt["prob_draw"] + p_mkt["prob_away"]
    assert np.isclose(total, 1.0, atol=1e-6)

    p_ou = _ou_btts_from_matrix(matrix_low_goals)
    assert np.isclose(p_ou["prob_over_25"] + p_ou["prob_under_25"], 1.0, atol=1e-6)

    # Con lambdas bajos, Under 2.5 debe ser alto
    assert p_ou["prob_under_25"] > 0.7


# ─── Suma de resultados exactos = 1.0 ────────────────────────────────

def test_exact_scores_sum_to_one(matrix_default):
    """La suma de P(i,j) para todos los marcadores = 1.0."""
    total = matrix_default.sum()
    assert np.isclose(total, 1.0, atol=1e-6)


def test_exact_scores_match_market_aggregates(matrix_default):
    """P(H) desde la matriz = P(H) desde market_probabilities."""
    from src.models import market_probabilities
    n = matrix_default.shape[0]

    p_home_manual = sum(matrix_default[i, j] for i in range(n) for j in range(n) if i > j)
    p_away_manual = sum(matrix_default[i, j] for i in range(n) for j in range(n) if i < j)

    p = market_probabilities(matrix_default)
    assert np.isclose(p_home_manual, p["prob_home"], atol=1e-6)
    assert np.isclose(p_away_manual, p["prob_away"], atol=1e-6)


# ─── Over 0.5 = 1 - P(0-0) ───────────────────────────────────────────

def test_over_05_equals_one_minus_draw_00(matrix_default):
    """P(Over 0.5) = 1 - P(0-0)."""
    n = matrix_default.shape[0]
    p_over_05_manual = sum(
        matrix_default[i, j]
        for i in range(n) for j in range(n)
        if i + j > 0.5
    )
    p_00 = matrix_default[0, 0]
    assert np.isclose(p_over_05_manual, 1 - p_00, atol=1e-6)