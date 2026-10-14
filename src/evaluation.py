"""
Evaluación walk-forward por temporada para el modelo Dixon-Coles.

Reemplaza el split 70/30 único de _calibracion.py por una evaluación
más honesta: entrena con temporadas pasadas, predice la siguiente,
y mide Brier / Log Loss / Accuracy por temporada.
"""
import numpy as np
import pandas as pd
from typing import Iterable

from src.feature_engineering import enrich_fixture
from src.models import predict_match


def _actual_result(row) -> str:
    """Devuelve H/D/A desde goles (ignora FTR para evitar discrepancias)."""
    if row["home_goals"] > row["away_goals"]:
        return "H"
    if row["home_goals"] == row["away_goals"]:
        return "D"
    return "A"


def brier_multiclass(y_idx: np.ndarray, probs: np.ndarray, n_classes: int = 3) -> float:
    """Brier multiclase = media del Brier binario por clase."""
    total = 0.0
    for k in range(n_classes):
        y_bin = (y_idx == k).astype(float)
        total += np.mean((probs[:, k] - y_bin) ** 2)
    return total / n_classes


def log_loss_multiclass(y_idx: np.ndarray, probs: np.ndarray, eps: float = 1e-12) -> float:
    probs = np.clip(probs, eps, 1 - eps)
    n = len(y_idx)
    return -np.mean(np.log(probs[np.arange(n), y_idx]))


def walk_forward_by_season(
    df: pd.DataFrame,
    seasons: Iterable[str | int],
    *,
    competition: str | None = None,
    rho: float = -0.13,
    model: str = "dixon_coles",
    min_train_matches: int = 200,
) -> pd.DataFrame:
    """
    Para cada temporada S en `seasons`:
      - train = partidos con season < S (opcionalmente filtrado por competition)
      - test  = partidos de la temporada S
      - predicción por partido con enrich_fixture(row, train, as_of_date=row['date'])

    Devuelve un DataFrame con predicciones y metadatos por partido.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["season"] = df["season"].astype(str)
    df = df.sort_values("date").reset_index(drop=True)

    if competition is not None:
        df = df[df["competition"] == competition].reset_index(drop=True)

    seasons = [str(s) for s in seasons]
    rows = []

    for season in seasons:
        train = df[df["season"] < season]
        test = df[df["season"] == season]

        if len(train) < min_train_matches or len(test) == 0:
            continue

        for _, row in test.iterrows():
            try:
                f = enrich_fixture(row, train, as_of_date=row["date"])
                p = predict_match(f["lambda_home"], f["lambda_away"], rho=rho, model=model)
            except Exception:
                continue

            rows.append({
                "season": season,
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "prob_H": p["prob_home"],
                "prob_D": p["prob_draw"],
                "prob_A": p["prob_away"],
                "actual": _actual_result(row),
                "odds_home": row.get("odds_home"),
                "odds_draw": row.get("odds_draw"),
                "odds_away": row.get("odds_away"),
            })

    return pd.DataFrame(rows)


def metrics_by_season(preds: pd.DataFrame) -> pd.DataFrame:
    """Agrega Brier, Log Loss y Accuracy por temporada."""
    order = {"H": 0, "D": 1, "A": 2}
    out = []
    for season, g in preds.groupby("season"):
        y_idx = g["actual"].map(order).values
        probs = g[["prob_H", "prob_D", "prob_A"]].values
        out.append({
            "season": season,
            "n": len(g),
            "brier": brier_multiclass(y_idx, probs),
            "log_loss": log_loss_multiclass(y_idx, probs),
            "accuracy": (probs.argmax(axis=1) == y_idx).mean(),
        })
    return pd.DataFrame(out).sort_values("season").reset_index(drop=True)


def reliability_curve(
    probs: np.ndarray,
    y_true_bin: np.ndarray,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Curva de fiabilidad para una clase binaria (ej. P(H) vs frecuencia real)."""
    bins = np.linspace(0, 1, n_bins + 1)
    rows = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (probs >= lo) & (probs < hi) if i < n_bins - 1 else (probs >= lo) & (probs <= hi)
        n = int(mask.sum())
        rows.append({
            "bin_center": (lo + hi) / 2,
            "predicted": probs[mask].mean() if n > 0 else np.nan,
            "observed": y_true_bin[mask].mean() if n > 0 else np.nan,
            "n": n,
        })
    return pd.DataFrame(rows)


def walk_forward_with_calibration(
    df: pd.DataFrame,
    seasons: Iterable[str | int],
    calibrator_factory,
    **walk_kwargs,
) -> pd.DataFrame:
    """
    Walk-forward con calibración honesta:
      1. Predice OOS sin calibrar todas las temporadas (walk_forward_by_season).
      2. Para cada temporada T (a partir de la 2ª), ajusta el calibrador
         SOLO con las predicciones OOS de temporadas < T.
      3. Aplica el calibrador a las predicciones de T.

    Devuelve el DataFrame de walk_forward_by_season con columnas extra
    prob_H_cal, prob_D_cal, prob_A_cal (y NaN en la primera temporada).
    """
    order = {"H": 0, "D": 1, "A": 2}
    seasons = [str(s) for s in seasons]

    preds_raw = walk_forward_by_season(df, seasons=seasons, **walk_kwargs)
    if preds_raw.empty:
        return preds_raw

    out_frames = []
    for i, season in enumerate(seasons):
        season_preds = preds_raw[preds_raw["season"] == season].copy()
        if season_preds.empty:
            continue

        # Primera temporada: no hay datos previos OOS para calibrar
        if i == 0:
            season_preds["prob_H_cal"] = np.nan
            season_preds["prob_D_cal"] = np.nan
            season_preds["prob_A_cal"] = np.nan
            out_frames.append(season_preds)
            continue

        train_cal = preds_raw[preds_raw["season"].isin(seasons[:i])]
        if len(train_cal) < 50:
            season_preds["prob_H_cal"] = np.nan
            season_preds["prob_D_cal"] = np.nan
            season_preds["prob_A_cal"] = np.nan
            out_frames.append(season_preds)
            continue

        X_cal = train_cal[["prob_H", "prob_D", "prob_A"]].values
        y_cal = train_cal["actual"].map(order).values

        cal = calibrator_factory()
        cal.fit(X_cal, y_cal)

        X_test = season_preds[["prob_H", "prob_D", "prob_A"]].values
        cal_probs = cal.predict_proba(X_test)

        season_preds["prob_H_cal"] = cal_probs[:, 0]
        season_preds["prob_D_cal"] = cal_probs[:, 1]
        season_preds["prob_A_cal"] = cal_probs[:, 2]
        out_frames.append(season_preds)

    return pd.concat(out_frames, ignore_index=True)


def metrics_calibrated_vs_raw(preds_with_cal: pd.DataFrame) -> pd.DataFrame:
    """
    Compara Brier/LogLoss antes/después de calibrar, por temporada.
    Solo evalúa en temporadas donde la calibración está disponible.
    """
    order = {"H": 0, "D": 1, "A": 2}
    rows = []

    valid = preds_with_cal.dropna(subset=["prob_H_cal", "prob_D_cal", "prob_A_cal"])
    for season, g in valid.groupby("season"):
        y_idx = g["actual"].map(order).values
        probs_raw = g[["prob_H", "prob_D", "prob_A"]].values
        probs_cal = g[["prob_H_cal", "prob_D_cal", "prob_A_cal"]].values
        rows.append({
            "season": season,
            "n": len(g),
            "brier_raw": brier_multiclass(y_idx, probs_raw),
            "brier_cal": brier_multiclass(y_idx, probs_cal),
            "log_loss_raw": log_loss_multiclass(y_idx, probs_raw),
            "log_loss_cal": log_loss_multiclass(y_idx, probs_cal),
            "acc_raw": (probs_raw.argmax(axis=1) == y_idx).mean(),
            "acc_cal": (probs_cal.argmax(axis=1) == y_idx).mean(),
        })
    return pd.DataFrame(rows).sort_values("season").reset_index(drop=True)


# ── Evaluación de mercados de goles (O/U 2.5 y BTTS) ────────────────────

def _ou_btts_from_matrix(matrix: np.ndarray) -> dict:
    """Extrae P(over 2.5), P(under 2.5), P(BTTS yes), P(BTTS no) de la matriz de marcadores."""
    n = matrix.shape[0]
    over_25 = 0.0
    btts_yes = 0.0
    for i in range(n):
        for j in range(n):
            p = matrix[i, j]
            if i + j >= 3:
                over_25 += p
            if i >= 1 and j >= 1:
                btts_yes += p
    return {
        "prob_over_25": over_25,
        "prob_under_25": 1.0 - over_25,
        "prob_btts_yes": btts_yes,
        "prob_btts_no": 1.0 - btts_yes,
    }


def walk_forward_markets(
    df: pd.DataFrame,
    seasons: Iterable[str | int],
    *,
    competition: str | None = None,
    rho: float = -0.13,
    min_train_matches: int = 200,
) -> pd.DataFrame:
    """
    Walk-forward que devuelve, para cada partido, probabilidades de:
      1X2, O/U 2.5 y BTTS
    además de las cuotas disponibles y el resultado real en goles.
    """
    from src.models import score_matrix_dixon_coles, market_probabilities

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["season"] = df["season"].astype(str)
    df = df.sort_values("date").reset_index(drop=True)
    if competition is not None:
        df = df[df["competition"] == competition].reset_index(drop=True)

    seasons = [str(s) for s in seasons]
    rows = []

    for season in seasons:
        train = df[df["season"] < season]
        test = df[df["season"] == season]
        if len(train) < min_train_matches or len(test) == 0:
            continue

        for _, row in test.iterrows():
            try:
                f = enrich_fixture(row, train, as_of_date=row["date"])
                matrix = score_matrix_dixon_coles(
                    f["lambda_home"], f["lambda_away"],
                    rho=rho,
                )
                p1x2 = market_probabilities(matrix)
                pou = _ou_btts_from_matrix(matrix)
            except Exception:
                continue

            def _get(primary, fallback):
                v = row.get(primary)
                if v is None or pd.isna(v):
                    v = row.get(fallback)
                return v if v is not None and not pd.isna(v) else None

            rows.append({
                "season": season,
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "prob_H": p1x2["prob_home"],
                "prob_D": p1x2["prob_draw"],
                "prob_A": p1x2["prob_away"],
                "prob_over_25": pou["prob_over_25"],
                "prob_under_25": pou["prob_under_25"],
                "prob_btts_yes": pou["prob_btts_yes"],
                "prob_btts_no": pou["prob_btts_no"],
                "home_goals": row["home_goals"],
                "away_goals": row["away_goals"],
                "total_goals": int(row["home_goals"] + row["away_goals"]),
                "btts_actual": int(row["home_goals"] > 0 and row["away_goals"] > 0),
                "actual_1x2": _actual_result(row),
                "odds_over_25": _get("AvgC>2.5", "Avg>2.5"),
                "odds_under_25": _get("AvgC<2.5", "Avg<2.5"),
                "odds_over_25_close": row.get("AvgC>2.5"),
                "odds_under_25_close": row.get("AvgC<2.5"),
            })

    return pd.DataFrame(rows)


def metrics_ou_market(preds: pd.DataFrame) -> pd.DataFrame:
    """Brier y LogLoss de O/U 2.5 (modelo vs cuotas), por temporada."""
    eps = 1e-12
    rows = []
    for season, g in preds.groupby("season"):
        y_over = (g["total_goals"].values >= 3).astype(int)
        p_over = np.clip(g["prob_over_25"].values, eps, 1 - eps)

        brier_model = np.mean((p_over - y_over) ** 2)
        ll_model = -np.mean(y_over * np.log(p_over) + (1 - y_over) * np.log(1 - p_over))

        o_over = g["odds_over_25_close"].fillna(g["odds_over_25"])
        o_under = g["odds_under_25_close"].fillna(g["odds_under_25"])
        mask = o_over.notna() & o_under.notna()

        if mask.sum() > 0:
            p_over_mkt = 1.0 / o_over[mask].values
            p_under_mkt = 1.0 / o_under[mask].values
            total = p_over_mkt + p_under_mkt
            p_over_mkt = p_over_mkt / total  # quitar vig
            y_ov_mkt = y_over[mask.values]
            p_over_mkt = np.clip(p_over_mkt, eps, 1 - eps)

            brier_mkt = np.mean((p_over_mkt - y_ov_mkt) ** 2)
            ll_mkt = -np.mean(
                y_ov_mkt * np.log(p_over_mkt) + (1 - y_ov_mkt) * np.log(1 - p_over_mkt)
            )
            n_mkt = int(mask.sum())
        else:
            brier_mkt = np.nan
            ll_mkt = np.nan
            n_mkt = 0

        rows.append({
            "season": season,
            "n": len(g),
            "n_con_cuotas": n_mkt,
            "brier_model": brier_model,
            "brier_cuotas": brier_mkt,
            "ll_model": ll_model,
            "ll_cuotas": ll_mkt,
        })
    return pd.DataFrame(rows).sort_values("season").reset_index(drop=True)


def metrics_btts_market(preds: pd.DataFrame) -> pd.DataFrame:
    """Brier y LogLoss de BTTS (modelo). No hay cuotas BTTS en el parquet."""
    eps = 1e-12
    rows = []
    for season, g in preds.groupby("season"):
        y_btts = g["btts_actual"].values.astype(int)
        p_btts = np.clip(g["prob_btts_yes"].values, eps, 1 - eps)

        brier = np.mean((p_btts - y_btts) ** 2)
        ll = -np.mean(
            y_btts * np.log(p_btts) + (1 - y_btts) * np.log(1 - p_btts)
        )
        base = y_btts.mean()
        brier_base = np.mean((base - y_btts) ** 2)
        ll_base = -np.mean(
            y_btts * np.log(base) + (1 - y_btts) * np.log(1 - base)
        )

        rows.append({
            "season": season,
            "n": len(g),
            "freq_btts": base,
            "brier_model": brier,
            "brier_base": brier_base,
            "ll_model": ll,
            "ll_base": ll_base,
        })
    return pd.DataFrame(rows).sort_values("season").reset_index(drop=True)