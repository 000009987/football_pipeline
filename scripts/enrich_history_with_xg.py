# scripts/enrich_history_with_xg.py
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.xg_loader import merge_xg_with_history  # noqa: E402

HIST = Path("data/processed/history.parquet")
XG   = Path("data/raw/xg_PL.csv")
OUT  = Path("data/processed/history_with_xg.parquet")


def main():
    hist = pd.read_parquet(HIST)
    xg   = pd.read_csv(XG)

    print("history cols:", list(hist.columns))
    print("xg cols     :", list(xg.columns))
    print("history shape:", hist.shape, "| xg shape:", xg.shape)

    enriched = merge_xg_with_history(hist, xg)

    # Diagnóstico por competición
    print("\nCobertura xG por competición:")
    cov = (enriched.assign(has_xg=enriched["home_xg"].notna())
                   .groupby("competition")["has_xg"]
                   .agg(["sum", "size"]))
    cov["pct"] = (cov["sum"] / cov["size"] * 100).round(1)
    print(cov)

    # Partidos PL SIN xG (los que nos interesan)
    sin = enriched[(enriched["competition"] == "PL") & enriched["home_xg"].isna()]
    if len(sin):
        print(f"\n⚠️  {len(sin)} partidos PL sin xG. Muestra:")
        print(sin[["date", "home_team", "away_team"]].head(15).to_string(index=False))
    else:
        print("\n✅ Todos los partidos PL tienen xG.")

    enriched.to_parquet(OUT, index=False)
    print(f"\n💾 Guardado: {OUT}  shape={enriched.shape}")


if __name__ == "__main__":
    main()