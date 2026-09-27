import pandas as pd
import numpy as np
from src.feature_engineering import enrich_fixture
from src.models import predict_match

df = pd.read_parquet("data/processed/history.parquet")
pl = df[df["competition"] == "PL"].sort_values("date").reset_index(drop=True)
split_idx = int(len(pl) * 0.7)
df_train = pl.iloc[:split_idx].copy()
df_test = pl.iloc[split_idx:].copy()

rows = []
for _, row in df_test.iterrows():
    try:
        f = enrich_fixture(row, df_train, as_of_date=row["date"])
        p = predict_match(f["lambda_home"], f["lambda_away"], rho=-0.13, model="dixon_coles")
    except Exception:
        continue
    actual = "H" if row["home_goals"] > row["away_goals"] else ("D" if row["home_goals"] == row["away_goals"] else "A")
    rows.append({
        "prob_H": p["prob_home"], "prob_D": p["prob_draw"], "prob_A": p["prob_away"],
        "actual": actual,
    })

pred = pd.DataFrame(rows)
print("Predicciones medias del modelo:")
print(f"  P(H) media: {pred['prob_H'].mean():.3f}")
print(f"  P(D) media: {pred['prob_D'].mean():.3f}")
print(f"  P(A) media: {pred['prob_A'].mean():.3f}")
print()
print("Frecuencias reales:")
print(f"  H: {(pred['actual']=='H').mean():.3f}")
print(f"  D: {(pred['actual']=='D').mean():.3f}")
print(f"  A: {(pred['actual']=='A').mean():.3f}")
print()
pred["bin"] = pd.qcut(pred["prob_H"], 10, labels=False, duplicates="drop")
calib = pred.groupby("bin").apply(
    lambda g: pd.Series({
        "prob_media": g["prob_H"].mean(),
        "freq_real": (g["actual"] == "H").mean(),
        "n": len(g),
    }),
    include_groups=False,
)
print("Calibración de P(H) por deciles:")
print(calib.round(3).to_string())
print()
print("Diferencia media (prob_media - freq_real):",
      (calib["prob_media"] - calib["freq_real"]).mean().round(4))