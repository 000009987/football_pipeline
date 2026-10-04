# scripts/diagnostico_ha.py
import pandas as pd
from config import HOME_ADVANTAGE, DECAY_FACTOR

df = pd.read_parquet("data/processed/history_with_xg.parquet")
df = df[df["competition"] == "PL"].dropna(subset=["home_xg"])

print(f"HOME_ADVANTAGE actual: {HOME_ADVANTAGE}")
print(f"DECAY_FACTOR actual:   {DECAY_FACTOR}\n")

# HA empírico = (goles local / goles visitante) ajustado por enfrentamientos
print("=== Empírico (PL 2023-25) ===")
print(f"Media goles local:    {df['home_goals'].mean():.3f}")
print(f"Media goles visit.:   {df['away_goals'].mean():.3f}")
print(f"Ratio goles H/A:      {df['home_goals'].mean() / df['away_goals'].mean():.3f}")
print(f"Ratio xG H/A:         {df['home_xg'].mean() / df['away_xg'].mean():.3f}")
print(f"\nSi HOME_ADVANTAGE ≠ ratio empírico, está mal.")

# ──────────────────────────────────────────────────────────
#  Diagnóstico HOME_ADVANTAGE
# ──────────────────────────────────────────────────────────
from config import HOME_ADVANTAGE, DECAY_FACTOR

print("\n" + "=" * 60)
print("DIAGNÓSTICO HOME_ADVANTAGE / DECAY_FACTOR")
print("=" * 60)
print(f"HOME_ADVANTAGE actual: {HOME_ADVANTAGE}")
print(f"DECAY_FACTOR actual:   {DECAY_FACTOR}")

print("\nEmpírico (mismos partidos PL arriba):")
print(f"  Ratio goles H/A: {df['home_goals'].mean() / df['away_goals'].mean():.3f}")
print(f"  Ratio xG    H/A: {df['home_xg'].mean()    / df['away_xg'].mean():.3f}")
print("\nEsperado en PL: ratio ≈ 1.10 - 1.20")
print("Si HOME_ADVANTAGE está fuera de ese rango → bug de config.")