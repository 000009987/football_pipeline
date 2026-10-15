import pytest
import pandas as pd
import numpy as np

def test_rolling_xg_no_data_leakage():
    """Verifica que las medias móviles de xG no utilicen datos del partido actual (shift == 1)."""
    data = pd.DataFrame({
        "team": ["TeamA", "TeamA", "TeamA"],
        "match_date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15"]),
        "xg_for": [1.5, 2.0, 0.5]
    })
    
    # Cálculo de media móvil con shift(1)
    data["rolling_xg"] = data.groupby("team")["xg_for"].transform(lambda x: x.shift(1).rolling(2, min_periods=1).mean())
    
    # El primer partido no debe tener historial anterior
    assert pd.isna(data["rolling_xg"].iloc[0])
    # El segundo partido debe usar solo el dato del primer partido (1.5)
    assert data["rolling_xg"].iloc[1] == pytest.approx(1.5)
    # El tercer partido debe usar la media de los dos anteriores ((1.5 + 2.0) / 2 = 1.75)
    assert data["rolling_xg"].iloc[2] == pytest.approx(1.75)