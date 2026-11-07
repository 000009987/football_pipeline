"""
Tests del caché de rho por liga.
"""
import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pytest

from src.config import OUTPUT_DIR, EVAL_LEAGUES

RHO_CACHE = OUTPUT_DIR / "rho_cache.json"


@pytest.fixture(scope="module")
def cache():
    if not RHO_CACHE.exists():
        pytest.skip(f"No existe {RHO_CACHE}. Ejecuta compute_league_rho.py primero.")
    with RHO_CACHE.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_cache_has_all_leagues(cache):
    """El caché debe tener todas las ligas de EVAL_LEAGUES."""
    leagues = cache.get("leagues", {})
    for league in EVAL_LEAGUES:
        assert league in leagues, f"Falta liga {league} en el caché"


def test_rho_in_valid_range(cache):
    """Cada rho debe estar en [-0.5, 0.3] (bound ampliado)."""
    for league, data in cache["leagues"].items():
        rho = data["rho"]
        # Bound ampliado: [-0.5, 0.3]. Algunas ligas (SA, PPL) pueden
        # tener rho > 0 si son de muchos goles.
        assert -0.5 <= rho <= 0.3, f"{league}: rho={rho} fuera de rango"


def test_rho_cache_has_enough_matches(cache):
    """Cada liga debe tener >= 50 partidos (umbral de estimate_rho)."""
    for league, data in cache["leagues"].items():
        assert data["n_matches"] >= 50, (
            f"{league}: solo {data['n_matches']} partidos (min 50)"
        )


def test_rho_status_ok(cache):
    """El status debe ser 'ok' para todas las ligas."""
    for league, data in cache["leagues"].items():
        assert data["status"] == "ok", (
            f"{league}: status={data['status']}"
        )


def test_rho_differ_across_leagues(cache):
    """Los rho de las 7 ligas NO deben ser todos idénticos."""
    rhos = [data["rho"] for data in cache["leagues"].values()]
    # Al menos 2 valores distintos (si todos son -0.13, algo falló)
    unique_rhos = set(round(r, 4) for r in rhos)
    assert len(unique_rhos) > 1, (
        f"Todos los rho son iguales: {unique_rhos}. "
        f"Probablemente estimate_rho falló y devolvió el default."
    )