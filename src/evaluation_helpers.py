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