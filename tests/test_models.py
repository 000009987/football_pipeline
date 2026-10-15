import pytest
import numpy as np
from src.models import predict_match

def test_score_matrix_sum_to_one():
    """Verifica que la suma de probabilidades 1X2 sea aproximadamente 1.0."""
    lambda_home = 1.45
    mu_away = 1.10
    
    res = predict_match(lambda_home, mu_away, rho=-0.13)
    
    if isinstance(res, dict):
        prob_sum = res["prob_home"] + res["prob_draw"] + res["prob_away"]
        assert prob_sum == pytest.approx(1.0, abs=1e-3)
    elif isinstance(res, np.ndarray):
        assert res.sum() == pytest.approx(1.0, abs=1e-3)

def test_dixon_coles_rho_effect():
    """Verifica que un rho negativo modifique las probabilidades respecto a rho=0.0."""
    lambda_home, mu_away = 1.2, 0.9
    
    res_no_rho = predict_match(lambda_home, mu_away, rho=0.0)
    res_with_rho = predict_match(lambda_home, mu_away, rho=-0.13)
    
    if isinstance(res_no_rho, dict) and isinstance(res_with_rho, dict):
        assert res_no_rho["prob_draw"] != res_with_rho["prob_draw"]