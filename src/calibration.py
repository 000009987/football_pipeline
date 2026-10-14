"""
Calibración multiclase 1X2 con estrategia One-vs-Rest.

- Platt scaling: regresión logística sobre logit(p_cruda)
- Isotonic regression: función monótona no paramétrica
- Temperature scaling: 1 parámetro, más robusto con pocos datos

Todos normalizan las 3 probabilidades para que sumen 1.
"""
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from scipy.optimize import minimize_scalar
from scipy.special import softmax

EPS = 1e-6


def _logit(p, eps=EPS):
    p = np.clip(p, eps, 1 - eps)
    return np.log(p / (1 - p))


class PlattCalibrator:
    """Platt scaling multiclase con One-vs-Rest."""

    def __init__(self):
        self.models = []
        self.classes_ = None

    def fit(self, probs, y):
        """
        probs: array (n, 3) con probabilidades crudas del modelo
        y: array (n,) con etiquetas 0/1/2 (0=H, 1=D, 2=A)
        """
        self.classes_ = np.unique(y)
        self.models = []
        for k in self.classes_:
            y_bin = (y == k).astype(int)
            X = _logit(probs[:, k]).reshape(-1, 1)
            lr = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
            lr.fit(X, y_bin)
            self.models.append(lr)
        return self

    def predict_proba(self, probs):
        raw = np.zeros_like(probs, dtype=float)
        for i, _ in enumerate(self.classes_):
            X = _logit(probs[:, i]).reshape(-1, 1)
            raw[:, i] = self.models[i].predict_proba(X)[:, 1]
        row_sums = raw.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        return raw / row_sums

    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path):
        return joblib.load(path)


class IsotonicCalibrator:
    """Isotonic regression multiclase con One-vs-Rest."""

    def __init__(self):
        self.models = []
        self.classes_ = None

    def fit(self, probs, y):
        self.classes_ = np.unique(y)
        self.models = []
        for k in self.classes_:
            y_bin = (y == k).astype(int)
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(probs[:, k], y_bin)
            self.models.append(iso)
        return self

    def predict_proba(self, probs):
        raw = np.zeros_like(probs, dtype=float)
        for i, _ in enumerate(self.classes_):
            raw[:, i] = self.models[i].predict(probs[:, i])
        row_sums = raw.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1.0
        return raw / row_sums

    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path):
        return joblib.load(path)


class TemperatureCalibrator:
    """
    Temperature scaling multiclase (1 solo parámetro).
    Mucho más robusto que Platt/Isotonic cuando hay pocos datos.
    T > 1 suaviza probabilidades; T < 1 las agudiza.
    """

    def __init__(self):
        self.T = 1.0

    def fit(self, probs, y):
        probs = np.clip(probs, 1e-12, 1.0)

        def nll(log_T):
            T = np.exp(log_T)
            logits = np.log(probs) / T
            p = softmax(logits, axis=1)
            return -np.mean(np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1.0)))

        res = minimize_scalar(nll, bounds=(-2.0, 2.0), method="bounded")
        self.T = float(np.exp(res.x))
        return self

    def predict_proba(self, probs):
        probs = np.clip(probs, 1e-12, 1.0)
        logits = np.log(probs) / self.T
        return softmax(logits, axis=1)

    def save(self, path):
        joblib.dump(self, path)

    @staticmethod
    def load(path):
        return joblib.load(path)