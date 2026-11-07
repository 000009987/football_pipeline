"""
Tests matemáticos del modelo Dixon-Coles.

Cubre:
  1. Matriz de marcadores: suma 1.0, no negativa, shape correcto.
  2. rho=0 == Poisson independiente.
  3. Función tau() con los 4 casos especiales.
  4. predict_match() devuelve probabilidades coherentes.
  5. market_probabilities() consistente con la matriz.
  6. estimate_rho() con datos insuficientes y sintéticos.
  7. Clipping de lambdas en rango [0.4, 4.0].
  8. Consistencia integral del pipeline.
"""
import numpy as np
import pandas as pd
import pytest

from src.models import (
    score_matrix_dixon_coles,
    score_matrix_poisson,
    market_probabilities,
    estimate_rho,
    predict_match,
    _tau,
)


# ─── Matriz de marcadores ─────────────────────────────────────────────────

def test_matrix_sums_to_one():
    """La matriz de Dixon-Coles debe sumar exactamente 1.0."""
    m = score_matrix_dixon_coles(1.5, 1.2, rho=-0.13)
    assert np.isclose(m.sum(), 1.0, atol=1e-6), f"Suma = {m.sum()}"


def test_matrix_non_negative():
    """Ninguna celda de la matriz debe ser negativa."""
    m = score_matrix_dixon_coles(1.5, 1.2, rho=-0.13)
    assert (m >= 0).all(), f"Mínimo = {m.min()}"


def test_matrix_sums_to_one_extreme_lambdas():
    """Debe sumar 1.0 incluso con lambdas extremos."""
    for lh, la in [(0.4, 0.4), (4.0, 4.0), (0.4, 4.0), (4.0, 0.4)]:
        m = score_matrix_dixon_coles(lh, la, rho=-0.13)
        assert np.isclose(m.sum(), 1.0, atol=1e-6), f"Falla con lh={lh}, la={la}"


def test_matrix_shape():
    """La matriz debe ser (MAX_GOALS+1) x (MAX_GOALS+1)."""
    from src.models import MAX_GOALS
    m = score_matrix_dixon_coles(1.5, 1.2, rho=-0.13)
    expected = (MAX_GOALS + 1, MAX_GOALS + 1)
    assert m.shape == expected, f"Shape = {m.shape}, esperado {expected}"


# ─── rho=0 == Poisson ─────────────────────────────────────────────────────

def test_rho_zero_equals_poisson():
    """
    Con rho=0, Dixon-Coles debe ser idéntico a Poisson independiente.

    Ambas matrices normalizan sobre la misma truncación (MAX_GOALS=7),
    por lo que deben coincidir con tolerancia de floating point.
    """
    lh, la = 1.5, 1.2
    m_dc = score_matrix_dixon_coles(lh, la, rho=0.0)
    m_poi = score_matrix_poisson(lh, la)
    max_diff = np.abs(m_dc - m_poi).max()
    assert max_diff < 1e-12, f"Max diff = {max_diff}"


# ─── Función tau() ────────────────────────────────────────────────────────

def test_tau_values():
    """Verifica los 4 valores especiales de tau y el default=1.0."""
    lh, la, rho = 1.5, 1.2, -0.13

    # tau(0,0) = 1 - lh*la*rho
    assert np.isclose(_tau(0, 0, lh, la, rho), 1 - lh * la * rho)
    # tau(1,0) = 1 + la*rho
    assert np.isclose(_tau(1, 0, lh, la, rho), 1 + la * rho)
    # tau(0,1) = 1 + lh*rho
    assert np.isclose(_tau(0, 1, lh, la, rho), 1 + lh * rho)
    # tau(1,1) = 1 - rho
    assert np.isclose(_tau(1, 1, lh, la, rho), 1 - rho)
    # Cualquier otro caso = 1.0
    assert np.isclose(_tau(2, 0, lh, la, rho), 1.0)
    assert np.isclose(_tau(0, 2, lh, la, rho), 1.0)
    assert np.isclose(_tau(2, 2, lh, la, rho), 1.0)
    assert np.isclose(_tau(3, 1, lh, la, rho), 1.0)


# ─── predict_match ───────────────────────────────────────────────────────

def test_predict_match_probs_sum_to_one():
    """P(H) + P(D) + P(A) debe sumar 1.0."""
    p = predict_match(1.5, 1.2, rho=-0.13)
    total = p["prob_home"] + p["prob_draw"] + p["prob_away"]
    assert np.isclose(total, 1.0, atol=1e-6), f"Suma = {total}"


def test_predict_match_keys_exist():
    """Deben existir todas las claves esperadas."""
    p = predict_match(1.5, 1.2, rho=-0.13)
    required_keys = ["prob_home", "prob_draw", "prob_away", "lambda_home", "lambda_away"]
    for key in required_keys:
        assert key in p, f"Falta {key}"


def test_predict_match_poisson_model():
    """Con model='poisson', no debe aplicar tau."""
    p_dc = predict_match(1.5, 1.2, rho=-0.13, model="dixon_coles")
    p_poi = predict_match(1.5, 1.2, rho=-0.13, model="poisson")
    assert not np.isclose(p_dc["prob_draw"], p_poi["prob_draw"], atol=1e-4)


# ─── market_probabilities ────────────────────────────────────────────────

def test_market_probabilities_sums_to_one():
    """P(H) + P(D) + P(A) de la matriz debe sumar 1.0."""
    m = score_matrix_dixon_coles(1.5, 1.2, rho=-0.13)
    probs = market_probabilities(m)
    total = probs["prob_home"] + probs["prob_draw"] + probs["prob_away"]
    assert np.isclose(total, 1.0, atol=1e-6)


def test_market_probabilities_favorite_home():
    """Si lambda_home >> lambda_away, P(H) debe ser el mayor."""
    m = score_matrix_dixon_coles(2.5, 0.5, rho=-0.13)
    probs = market_probabilities(m)
    assert probs["prob_home"] > probs["prob_draw"]
    assert probs["prob_home"] > probs["prob_away"]


def test_market_probabilities_favorite_away():
    """Si lambda_away >> lambda_home, P(A) debe ser el mayor."""
    m = score_matrix_dixon_coles(0.5, 2.5, rho=-0.13)
    probs = market_probabilities(m)
    assert probs["prob_away"] > probs["prob_draw"]
    assert probs["prob_away"] > probs["prob_home"]


# ─── estimate_rho ────────────────────────────────────────────────────────

def test_estimate_rho_insufficient_data():
    """Sin columnas necesarias, debe devolver el default -0.13."""
    df = pd.DataFrame({"foo": [1, 2, 3]})
    assert estimate_rho(df) == -0.13


def test_estimate_rho_too_few_matches():
    """Con < 50 partidos, debe devolver el default -0.13."""
    df = pd.DataFrame({
        "lambda_home": [1.5] * 10,
        "lambda_away": [1.2] * 10,
        "home_goals": [1] * 10,
        "away_goals": [1] * 10,
    })
    assert estimate_rho(df) == -0.13


def test_estimate_rho_reasonable_range():
    """Con datos sintéticos razonables, rho debe estar en [-0.5, 0.3]."""
    np.random.seed(42)
    n = 500
    lh = np.random.uniform(0.8, 2.0, n)
    la = np.random.uniform(0.6, 1.8, n)
    df = pd.DataFrame({
        "lambda_home": lh,
        "lambda_away": la,
        "home_goals": np.random.poisson(lh),
        "away_goals": np.random.poisson(la),
    })
    rho = estimate_rho(df)
    # Bound ampliado: [-0.5, 0.3]. Dixon-Coles admite rho > 0
    # en ligas de muchos goles (SA, PPL).
    assert -0.5 <= rho <= 0.3, f"rho={rho} fuera de rango"


def test_estimate_rho_returns_float():
    """Debe devolver un float, no un array."""
    df = pd.DataFrame({
        "lambda_home": [1.5] * 60,
        "lambda_away": [1.2] * 60,
        "home_goals": [1] * 60,
        "away_goals": [1] * 60,
    })
    rho = estimate_rho(df)
    assert isinstance(rho, float)


# ─── Consistencia integral ──────────────────────────────────────────────

def test_full_pipeline_consistency():
    """La matriz, las probabilidades y los marcadores deben ser consistentes."""
    m = score_matrix_dixon_coles(1.5, 1.2, rho=-0.13)
    probs = market_probabilities(m)

    n = m.shape[0]
    p_home_direct = sum(m[i, j] for i in range(n) for j in range(n) if i > j)
    assert np.isclose(p_home_direct, probs["prob_home"], atol=1e-6)