"""
Test de invariancia temporal: agregar resultados posteriores NO debe
cambiar predicciones históricas.

Esto detecta data leakage. Si `as_of_date` en `enrich_fixture` no filtra
correctamente, las predicciones del pasado cambiarán al añadir datos futuros.

Diseño del test:
  1. Tomar un partido P en fecha D del histórico.
  2. Predecir P usando train = partidos con fecha < D.
  3. Añadir al train partidos con fecha > D (simulando "datos futuros").
  4. Volver a predecir P.
  5. Verificar que las predicciones son idénticas (tolerancia 1e-12).
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest

from src.config import PROCESSED_DATA_DIR, DEFAULT_RHO
from src.feature_engineering import enrich_fixture
from src.models import predict_match

ENRICHED = PROCESSED_DATA_DIR / "history_with_xg.parquet"


@pytest.fixture(scope="module")
def history():
    """Carga el histórico completo."""
    if not ENRICHED.exists():
        pytest.skip(f"No existe {ENRICHED}")
    df = pd.read_parquet(ENRICHED)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.sort_values("date").reset_index(drop=True)


@pytest.fixture(scope="module")
def test_match(history):
    """
    Selecciona un partido de PL de la temporada 2025 (con datos suficientes antes
    y después) para usar como caso de prueba.
    """
    pl = history[history["competition"] == "PL"].copy()
    # Buscar un partido de 2025 con al menos 20 partidos antes y 20 después
    candidates = []
    for idx in range(20, len(pl) - 20):
        row = pl.iloc[idx]
        if pd.to_datetime(row["date"]).year == 2025:
            candidates.append(row)
    if not candidates:
        pytest.skip("No se encontró partido candidato en PL 2025")
    return candidates[0]


def test_predict_is_stable_when_adding_future_data(history, test_match):
    """
    Predicción de un partido debe ser idéntica independientemente de si
    el train incluye datos posteriores al partido.
    """
    match_date = test_match["date"]

    # ── Escenario A: train = partidos ANTERIORES al partido ──────────
    train_before = history[history["date"] < match_date].copy()
    f_before = enrich_fixture(test_match, train_before, as_of_date=match_date)
    p_before = predict_match(
        f_before["lambda_home"], f_before["lambda_away"],
        rho=DEFAULT_RHO, model="dixon_coles",
    )

    # ── Escenario B: train = partidos ANTERIORES + POSTERIORES ───────
    # Añadir 50 partidos inmediatamente después del partido
    after = history[history["date"] > match_date].head(50)
    train_after = pd.concat([train_before, after], ignore_index=True)
    f_after = enrich_fixture(test_match, train_after, as_of_date=match_date)
    p_after = predict_match(
        f_after["lambda_home"], f_after["lambda_away"],
        rho=DEFAULT_RHO, model="dixon_coles",
    )

    # ── Verificación: predicciones deben ser IDÉNTICAS ───────────────
    assert np.isclose(
        f_before["lambda_home"], f_after["lambda_home"], atol=1e-12
    ), (
        f"lambda_home cambió: {f_before['lambda_home']} → {f_after['lambda_home']}\n"
        f"Esto indica DATA LEAKAGE: `as_of_date` no filtra correctamente."
    )

    assert np.isclose(
        f_before["lambda_away"], f_after["lambda_away"], atol=1e-12
    ), (
        f"lambda_away cambió: {f_before['lambda_away']} → {f_after['lambda_away']}\n"
        f"Esto indica DATA LEAKAGE: `as_of_date` no filtra correctamente."
    )

    assert np.isclose(p_before["prob_home"], p_after["prob_home"], atol=1e-12)
    assert np.isclose(p_before["prob_draw"], p_after["prob_draw"], atol=1e-12)
    assert np.isclose(p_before["prob_away"], p_after["prob_away"], atol=1e-12)


def test_predict_uses_only_past_data(history):
    """
    Verifica que `enrich_fixture` con `as_of_date=D` usa solo partidos
    con `date < D`, no `date <= D` (el partido en sí no debe estar en train).
    """
    # Seleccionar un partido de PL 2025
    pl = history[history["competition"] == "PL"].copy()
    pl_2025 = pl[pd.to_datetime(pl["date"]).dt.year == 2025]
    if len(pl_2025) == 0:
        pytest.skip("No hay partidos de PL 2025")

    test_match = pl_2025.iloc[20]  # uno con datos previos suficientes
    match_date = test_match["date"]

    # ── Escenario A: train sin el partido, as_of = match_date ───────
    train_without = history[history["date"] < match_date].copy()
    f_a = enrich_fixture(test_match, train_without, as_of_date=match_date)

    # ── Escenario B: train CON el partido, as_of = match_date ───────
    # Si as_of_date funciona, el partido en sí NO debe incluirse aunque
    # esté en train (porque date == as_of_date, no < as_of_date)
    train_with = history[history["date"] <= match_date].copy()
    f_b = enrich_fixture(test_match, train_with, as_of_date=match_date)

    # Las predicciones deben ser idénticas: el partido en sí no debe contar
    assert np.isclose(
        f_a["lambda_home"], f_b["lambda_home"], atol=1e-12
    ), (
        f"El partido en sí se está incluyendo en train.\n"
        f"Con as_of_date={match_date}, un partido con date={match_date} NO debe incluirse.\n"
        f"lambda_home: {f_a['lambda_home']} → {f_b['lambda_home']}"
    )
    assert np.isclose(f_a["lambda_away"], f_b["lambda_away"], atol=1e-12)


def test_no_future_leakage_across_seasons(history):
    """
    Predicción de un partido de la temporada 2025 NO debe verse afectada
    por datos de la temporada 2026.
    """
    # Partido de PL 2025
    pl = history[history["competition"] == "PL"].copy()
    pl_2025 = pl[pd.to_datetime(pl["date"]).dt.year == 2025]
    if len(pl_2025) == 0:
        pytest.skip("No hay partidos de PL 2025")

    test_match = pl_2025.iloc[50]  # uno con datos previos suficientes
    match_date = test_match["date"]

    # Train = solo 2025 (más antiguo)
    train_2025 = history[history["date"] < match_date].copy()
    f_2025 = enrich_fixture(test_match, train_2025, as_of_date=match_date)

    # Train = 2025 + 2026 (simula añadir temporada futura completa)
    train_with_2026 = pd.concat(
        [train_2025, history[pd.to_datetime(history["date"]).dt.year == 2026]],
        ignore_index=True,
    )
    f_with_2026 = enrich_fixture(test_match, train_with_2026, as_of_date=match_date)

    # Predicciones deben ser IDÉNTICAS
    assert np.isclose(f_2025["lambda_home"], f_with_2026["lambda_home"], atol=1e-12), (
        f"Data leakage entre temporadas: añadir 2026 cambió predicción de 2025."
    )
    assert np.isclose(f_2025["lambda_away"], f_with_2026["lambda_away"], atol=1e-12)