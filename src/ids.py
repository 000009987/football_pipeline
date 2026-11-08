"""
Generación determinística de match_id.

Formato: {liga}_{YYYYMMDD}_{hash12}
Ejemplo: PL_20260815_a3f8b2c1d4e5

Compartido entre scripts/fix_match_id.py y scripts/refresh_history.py
para garantizar IDs consistentes.
"""
import hashlib

import pandas as pd


def make_match_id(row) -> str:
    """Genera un ID determinístico para un partido."""
    comp = str(row["competition"]).strip().upper()
    date = pd.to_datetime(row["date"]).strftime("%Y%m%d")
    home = str(row["home_team"]).strip().lower()
    away = str(row["away_team"]).strip().lower()
    key = f"{comp}|{date}|{home}|{away}"
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    return f"{comp}_{date}_{h}"


def apply_match_id(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rellena match_id solo donde es nulo.
    Preserva IDs existentes para no romper referencias históricas.
    """
    df = df.copy()
    if "match_id" not in df.columns:
        df["match_id"] = None

    mask = df["match_id"].isna() | (df["match_id"] == "")
    if mask.sum() == 0:
        return df

    new_ids = []
    for idx in df.index:
        if mask.loc[idx]:
            new_ids.append(make_match_id(df.loc[idx]))
        else:
            val = df.loc[idx, "match_id"]
            if isinstance(val, (int, float)) and pd.notna(val):
                new_ids.append(str(int(val)))
            else:
                new_ids.append(str(val))
    df["match_id"] = new_ids
    return df