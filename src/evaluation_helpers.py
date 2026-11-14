import pandas as pd
import numpy as np
from src.config import DRAW_FILTER_CONFIG
from src.logger import get_logger

logger = get_logger(__name__)

def calculate_ev(prob: float | pd.Series, odds: float | pd.Series) -> float | pd.Series:
    """Calcula el Valor Esperado (EV = P * Cuota - 1)."""
    return (prob * odds) - 1.0

def calculate_profit(is_win: bool | pd.Series, odds: float | pd.Series) -> float | pd.Series:
    """Calcula el rendimiento numérico por unidad apostada (1 unidad)."""
    return np.where(is_win, odds - 1.0, -1.0)

def calculate_clv(opening_odds: float | pd.Series, closing_odds: float | pd.Series) -> float | pd.Series:
    """Calcula el Closing Line Value (CLV = Cuota_Apertura / Cuota_Cierre - 1)."""
    return (opening_odds / closing_odds) - 1.0

def apply_production_draw_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica la regla de producción global (EV >= 8% y Cuota <= 3.80)."""
    ev_min = DRAW_FILTER_CONFIG["ev_min"]
    max_odds = DRAW_FILTER_CONFIG["max_odds"]
    
    initial_len = len(df)
    filtered_df = df[(df["ev"] >= ev_min) & (df["odds"] <= max_odds)].copy()
    
    logger.info(
        f"Filtro de Producción 1X2 Draw: EV >= {ev_min*100:.0f}%, Cuota <= {max_odds:.2f}. "
        f"Picks filtrados: {initial_len} -> {len(filtered_df)}"
    )
    return filtered_df

def apply_relaxed_draw_filters(data: pd.DataFrame) -> pd.DataFrame:
    """
    Filtro relajado para paper trading: EV >= 8% y cuota <= 5.50.
    Captura partidos con value alto pero cuota que el backtest marcó como negativa.
    NO se usa para PICK; solo para INFO y tracking.
    """
    if data.empty:
        return data
    ev_min = DRAW_FILTER_CONFIG["ev_min"]
    relaxed_max_odds = 5.50
    return data[(data["ev"] >= ev_min) & (data["odds"] <= relaxed_max_odds)].copy()



# ─── Desvig (eliminación de overround) ───────────────────────────────

def remove_overround(odds_list: list) -> list:
    """
    Elimina el overround de una lista de cuotas.

    Convierte cuotas a probabilidades implícitas (1/odds), calcula el total
    (que es >1.0 por el margen de la casa) y normaliza para que sumen 1.0.

    Uso:
        probs = remove_overround([2.5, 3.4, 2.9])
        # → [0.39, 0.29, 0.33] (aproximado, suman 1.0)

    Devuelve [] si:
        - lista vacía
        - alguna cuota fuera de [1, 100]
        - suma de implícitas <= 0
    """
    if not odds_list or any(
        (not isinstance(o, (int, float))) or o <= 1.0 or o > 100.0
        for o in odds_list
    ):
        return []
    implied = [1.0 / float(o) for o in odds_list]
    total = sum(implied)
    if total <= 0:
        return []
    return [p / total for p in implied]


# ─── Validación de cuota y probabilidad ──────────────────────────────

def validate_odds(odds) -> bool:
    """Valida que una cuota esté en rango [1, 100]."""
    return isinstance(odds, (int, float)) and 1.0 <= float(odds) <= 100.0


def validate_prob(prob) -> bool:
    """Valida que una probabilidad esté en [0, 1]."""
    return isinstance(prob, (int, float)) and 0.0 <= float(prob) <= 1.0


# ─── Kelly fraccionado ───────────────────────────────────────────────

def kelly_fraction(prob: float, odds: float, fraction: float = 0.25) -> float:
    """
    Fracción de banca a apostar con Kelly fraccionado.

    kelly_full = (p * o - 1) / (o - 1)
    kelly_frac = fraction * kelly_full
    Cap a [0.0, 1.0] (stake base máximo = 1 unidad).

    Devuelve 0.0 si:
        - prob o odds no válidos
        - odds <= 1.0
        - EV <= 0 (no hay valor)

    Ejemplo:
        kelly_fraction(0.5, 3.0, fraction=0.25)
        # ev = 0.5*3-1 = 0.5; kelly_full = 0.5/2 = 0.25; kelly_frac = 0.0625
        # → 0.06 (redondeado a 2 decimales)
    """
    if not validate_prob(prob) or not validate_odds(odds):
        return 0.0
    odds = float(odds)
    prob = float(prob)
    if odds <= 1.0:
        return 0.0
    ev = prob * odds - 1.0
    if ev <= 0:
        return 0.0
    kelly_full = ev / (odds - 1.0)
    kelly_frac = fraction * kelly_full
    return round(min(max(kelly_frac, 0.0), 1.0), 2)