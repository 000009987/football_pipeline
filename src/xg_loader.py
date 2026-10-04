"""
xg_loader.py
Descarga datos de xG desde Understat (vía soccerdata) y los guarda en data/raw/.
Solo cubre las 5 grandes ligas: PL, PD, BL1, SA, FL1.
"""

import time
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Mapeo: competición interna -> nombre de liga en soccerdata/Understat
LEAGUE_MAP = {
    "PL":  "ENG-Premier League",
    "PD":  "ESP-La Liga",
    "BL1": "GER-Bundesliga",
    "SA":  "ITA-Serie A",
    "FL1": "FRA-Ligue 1",
}

# Temporadas en formato Understat: "2425" = 2024-25
SEASONS_XG = ["2324", "2425", "2526"]


# ============================================================
#  Descarga
# ============================================================
def fetch_xg_for_league(comp: str, seasons: list = None) -> pd.DataFrame:
    """Descarga xG de Understat para una competición y temporadas dadas."""
    import soccerdata as sd

    if comp not in LEAGUE_MAP:
        return pd.DataFrame()

    seasons = seasons or SEASONS_XG
    league_name = LEAGUE_MAP[comp]

    print(f"  [xG {comp}] descargando {league_name} {seasons}...")

    try:
        us = sd.Understat(leagues=league_name, seasons=seasons)
        raw = us.read_team_match_stats()
    except Exception as e:
        print(f"  [xG {comp}] ERROR: {e}")
        return pd.DataFrame()

    if raw.empty:
        return pd.DataFrame()

    raw = raw.reset_index()

    keep_cols = [
        "date", "home_team", "away_team",
        "home_goals", "away_goals",
        "home_xg", "away_xg",
        "home_np_xg", "away_np_xg",
        "home_ppda", "away_ppda",
    ]
    keep_cols = [c for c in keep_cols if c in raw.columns]
    df = raw[keep_cols].copy()

    df["competition"] = comp
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "home_xg", "away_xg"])
    df = df.sort_values("date").reset_index(drop=True)

    print(f"  [xG {comp}] {len(df)} partidos con xG")
    return df


def fetch_all_xg(competitions: list = None, seasons: list = None) -> pd.DataFrame:
    """Descarga xG de todas las ligas y temporadas configuradas."""
    competitions = competitions or list(LEAGUE_MAP.keys())
    seasons = seasons or SEASONS_XG

    all_dfs = []
    for comp in competitions:
        csv_path = RAW_DIR / f"xg_{comp}.csv"

        if csv_path.exists():
            age_days = (time.time() - csv_path.stat().st_mtime) / 86400
            if age_days < 7:
                print(f"  [xG {comp}] usando caché CSV ({age_days:.1f} días)")
                df = pd.read_csv(csv_path, parse_dates=["date"])
                all_dfs.append(df)
                continue

        df = fetch_xg_for_league(comp, seasons)
        if not df.empty:
            df.to_csv(csv_path, index=False)
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)
    print(f"\nTotal partidos con xG: {len(combined):,}")
    return combined


# ============================================================
#  Merge xG  <->  history
# ============================================================
def _normalize_team_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza home_team / away_team usando el mapeo central."""
    from src.feature_engineering import normalize_team_name  # lazy import

    df = df.copy()
    for c in ("home_team", "away_team"):
        df[c] = df[c].map(normalize_team_name)
    return df


def _normalize_date(series: pd.Series) -> pd.Series:
    """datetime64[ns] sin tz, a nivel de día."""
    s = pd.to_datetime(series, utc=True, errors="coerce")
    return s.dt.tz_convert(None).dt.normalize()


def merge_xg_with_history(history: pd.DataFrame, xg: pd.DataFrame) -> pd.DataFrame:
    """
    Añade home_xg, away_xg, home_np_xg, away_np_xg a `history`.
    Merge por (date, home_team, away_team) tras normalizar nombres y fechas.
    """
    hist = history.copy()
    xgdf = xg.copy()

    hist["date"] = _normalize_date(hist["date"])
    xgdf["date"] = _normalize_date(xgdf["date"])

    xgdf = _normalize_team_names(xgdf)

    xg_cols = ["home_xg", "away_xg", "home_np_xg", "away_np_xg"]
    missing = [c for c in xg_cols if c not in xgdf.columns]
    if missing:
        raise ValueError(f"Faltan columnas en xG: {missing}. "
                         f"Disponibles: {list(xgdf.columns)}")

    xg_slim = (xgdf[["date", "home_team", "away_team"] + xg_cols]
               .drop_duplicates(subset=["date", "home_team", "away_team"]))

    merged = hist.merge(xg_slim,
                        on=["date", "home_team", "away_team"],
                        how="left")

    n = len(hist)
    matched = merged["home_xg"].notna().sum()
    print(f"[merge_xg] {matched}/{n} partidos con xG ({matched/n:.1%})")
    return merged


if __name__ == "__main__":
    df = fetch_all_xg()
    print()
    print(df.head(10))
    print()
    print("Por competición:")
    print(df.groupby("competition").size())