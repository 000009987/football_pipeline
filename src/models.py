"""
models.py
Implementa:
  1. Poisson estándar
  2. Dixon-Coles (corrección para resultados de baja puntuación 0-0, 1-0, 0-1, 1-1)

Referencia: Dixon & Coles (1997) "Modelling Association Football Scores 
            and Inefficiencies in the Football Betting Market"
"""

import numpy as np
from scipy.stats  import poisson
from scipy.optimize import minimize
import warnings
warnings.filterwarnings("ignore")


MAX_GOALS = 7   # matriz hasta 7x7


# ── Corrección Dixon-Coles ─────────────────────────────────────────────────────

def _tau(x: int, y: int, lh: float, la: float, rho: float) -> float:
    """
    Factor de corrección para baja puntuación.
    Solo aplica para (0,0), (1,0), (0,1), (1,1).
    """
    if   x == 0 and y == 0: return 1 - lh * la * rho
    elif x == 1 and y == 0: return 1 + la * rho
    elif x == 0 and y == 1: return 1 + lh * rho
    elif x == 1 and y == 1: return 1 - rho
    else:                   return 1.0


# ── Matrices de probabilidad ───────────────────────────────────────────────────

def score_matrix_poisson(lambda_home: float, lambda_away: float) -> np.ndarray:
    """
    Matriz [home_goals x away_goals] de probabilidades con Poisson estándar.
    shape: (MAX_GOALS+1, MAX_GOALS+1)
    """
    goals = np.arange(MAX_GOALS + 1)
    ph    = poisson.pmf(goals, lambda_home)
    pa    = poisson.pmf(goals, lambda_away)
    return np.outer(ph, pa)


def score_matrix_dixon_coles(lambda_home: float, lambda_away: float,
                              rho: float = -0.13) -> np.ndarray:
    """
    Matriz de probabilidades con corrección Dixon-Coles.
    rho ≈ -0.13 es el valor típico estimado en la literatura.
    """
    goals  = np.arange(MAX_GOALS + 1)
    ph     = poisson.pmf(goals, lambda_home)
    pa     = poisson.pmf(goals, lambda_away)
    matrix = np.outer(ph, pa)

    for i in range(min(2, MAX_GOALS + 1)):
        for j in range(min(2, MAX_GOALS + 1)):
            tau = _tau(i, j, lambda_home, lambda_away, rho)
            # clamp para evitar probabilidades negativas
            matrix[i, j] *= max(tau, 1e-6)

    # Renormalizar
    matrix /= matrix.sum()
    return matrix


# ── Probabilidades de mercados ─────────────────────────────────────────────────

def market_probabilities(matrix: np.ndarray) -> dict:
    """
    A partir de la matriz de resultados calcula probabilidades
    para todos los mercados principales.
    """
    n = matrix.shape[0]
    g = np.arange(n)

    # 1X2
    prob_home = float(np.tril(matrix, -1).sum())   # home_goals > away_goals
    prob_draw = float(np.trace(matrix))
    prob_away = float(np.triu(matrix, 1).sum())

    # Over/Under
    total_matrix = np.add.outer(g, g)   # [i+j] matrix
    ou = {}
    for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
        ou[f"over_{line}"]  = float(matrix[total_matrix > line].sum())
        ou[f"under_{line}"] = float(matrix[total_matrix < line].sum())

    # BTTS (ambos marcan)
    btts_yes = float(matrix[1:, 1:].sum())   # home>=1 AND away>=1
    btts_no  = 1.0 - btts_yes

    # Marcadores exactos (top 12)
    flat_idx  = np.argsort(matrix.ravel())[::-1][:15]
    exact     = {}
    for idx in flat_idx:
        i, j = divmod(idx, n)
        exact[f"{i}-{j}"] = round(float(matrix[i, j]), 5)

    # Asian Handicap aprox (±0.5, ±1.0)
    ah = {}
    for hcap in [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]:
        win = 0.0
        for i in range(n):
            for j in range(n):
                if (i - j) + hcap > 0:
                    win += matrix[i, j]
        ah[f"ah_home_{hcap:+.1f}"] = round(win, 5)

    return {
        "prob_home":  round(prob_home, 5),
        "prob_draw":  round(prob_draw, 5),
        "prob_away":  round(prob_away, 5),
        **{k: round(v, 5) for k, v in ou.items()},
        "btts_yes":   round(btts_yes, 5),
        "btts_no":    round(btts_no, 5),
        "exact_scores": exact,
        **ah,
    }


# ── Estimación de rho (Dixon-Coles) con MLE ───────────────────────────────────

def estimate_rho(df_matches) -> float:
    """
    Estima el parámetro rho óptimo usando máxima verosimilitud
    sobre un DataFrame histórico que ya tenga columnas
    lambda_home y lambda_away (pre-calculadas).
    Si no están disponibles, devuelve -0.13 (default literatura).
    """
    if "lambda_home" not in df_matches.columns:
        return -0.13

    sample = df_matches.dropna(subset=["lambda_home", "lambda_away",
                                        "home_goals", "away_goals"]).copy()
    if len(sample) < 50:
        return -0.13

    def neg_log_likelihood(rho_arr):
        rho = rho_arr[0]
        ll  = 0.0
        for _, row in sample.iterrows():
            lh = row["lambda_home"]
            la = row["lambda_away"]
            x  = int(row["home_goals"])
            y  = int(row["away_goals"])
            tau = _tau(x, y, lh, la, rho)
            p   = (poisson.pmf(x, lh) * poisson.pmf(y, la) * max(tau, 1e-9))
            ll -= np.log(max(p, 1e-12))
        return ll

    res = minimize(neg_log_likelihood, x0=[-0.13],
                   bounds=[(-0.5, 0.0)], method="L-BFGS-B")
    return float(res.x[0]) if res.success else -0.13


# ── Convenience function ───────────────────────────────────────────────────────

def predict_match(lambda_home: float, lambda_away: float,
                  rho: float = -0.13,
                  model: str = "dixon_coles") -> dict:
    """
    Entrada:  lambdas estimados, rho, modelo
    Salida:   dict completo con todas las probabilidades de mercado
    """
    if model == "dixon_coles":
        matrix = score_matrix_dixon_coles(lambda_home, lambda_away, rho)
    else:
        matrix = score_matrix_poisson(lambda_home, lambda_away)

    probs = market_probabilities(matrix)
    probs["lambda_home"] = round(lambda_home, 4)
    probs["lambda_away"] = round(lambda_away, 4)
    probs["model"]       = model
    return probs


# ── Demo ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    lh, la = 1.65, 1.10
    print("=== Poisson ===")
    p1 = predict_match(lh, la, model="poisson")
    print(f"1X2: {p1['prob_home']:.1%} / {p1['prob_draw']:.1%} / {p1['prob_away']:.1%}")
    print(f"O2.5: {p1['over_2.5']:.1%}   BTTS: {p1['btts_yes']:.1%}")

    print("\n=== Dixon-Coles ===")
    p2 = predict_match(lh, la, rho=-0.13, model="dixon_coles")
    print(f"1X2: {p2['prob_home']:.1%} / {p2['prob_draw']:.1%} / {p2['prob_away']:.1%}")
    print(f"O2.5: {p2['over_2.5']:.1%}   BTTS: {p2['btts_yes']:.1%}")

    print("\nTop marcadores exactos:")
    for score, prob in sorted(p2["exact_scores"].items(),
                               key=lambda x: -x[1])[:8]:
        print(f"  {score}: {prob:.2%}")
