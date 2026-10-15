import pytest

def calculate_ev(prob: float, odds: float) -> float:
    """Cálculo estándar de Expected Value."""
    return (prob * odds) - 1.0

def calculate_kelly(prob: float, odds: float, fraction: float = 0.25) -> float:
    """Criterio de Kelly fraccional."""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    ev = (prob * odds) - 1.0
    if ev <= 0:
        return 0.0
    f_star = (prob * b - (1.0 - prob)) / b
    return max(0.0, f_star * fraction)

def test_ev_calculation():
    """Verifica que el cálculo de EV sea exacto."""
    # Probabilidad 40% (0.40) y cuota 3.00 => EV = 0.40 * 3.00 - 1 = +0.20 (+20%)
    assert calculate_ev(0.40, 3.00) == pytest.approx(0.20, abs=1e-4)
    # Probabilidad 25% (0.25) y cuota 3.50 => EV = 0.25 * 3.50 - 1 = -0.125 (-12.5%)
    assert calculate_ev(0.25, 3.50) == pytest.approx(-0.125, abs=1e-4)

def test_kelly_fractional_safety():
    """Asegura que Kelly no sugiera apostar cuando el EV es negativo o cero."""
    # EV Negativo -> Stake debe ser 0.0
    assert calculate_kelly(prob=0.20, odds=3.00) == 0.0
    
    # EV Positivo -> Stake debe ser un valor positivo razonable
    stake = calculate_kelly(prob=0.35, odds=3.50, fraction=0.25)
    assert stake > 0.0
    assert stake < 0.10  # No debería arriesgar más del 10% del bankroll en Kelly fraccional 1/4