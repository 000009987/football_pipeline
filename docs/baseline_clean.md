# Baseline limpio de Fase 1 — Dixon-Coles

**Fecha:** 2026-11-07
**Fase:** 1 (Corrección estadística y prevención de fugas)
**Estado:** Completado

---

## 1. Objetivo

Documentar el baseline honesto de Dixon-Coles después de:

- Reemplazar `rho = -0.13` hardcoded por `rho` por liga (estimado con MLE).
- Reemplazar `HOME_ADVANTAGE = 1.12` por `1.0` (elimina doble conteo de localía).
- Verificar ausencia de data leakage (test de invariancia temporal).
- Verificar corrección matemática (17 tests de Dixon-Coles).

Este baseline es el **punto de partida oficial de Fase 2 (LightGBM)**.

---

## 2. Parámetros finales

### `rho` por liga (estimado con MLE, últimos 300 partidos)

| Liga | rho     | n partidos | Rango histórico literatura   |
| ---- | ------- | ---------- | ---------------------------- |
| FL1  | -0.0822 | 288        | [-0.15, -0.05] ✅            |
| PL   | -0.1256 | 290        | [-0.15, -0.10] ✅            |
| PD   | -0.0280 | 290        | [-0.10, 0.00] ✅             |
| PPL  | +0.0896 | 289        | [0.00, +0.10] ⚠️ (positivo)  |
| DED  | -0.1381 | 288        | [-0.15, -0.10] ✅            |
| BL1  | -0.0676 | 288        | [-0.10, -0.05] ✅            |
| SA   | +0.0398 | 290        | [-0.05, +0.05] ⚠️ (positivo) |

**Nota:** PPL y SA tienen `rho > 0`, lo cual es plausible (ligas de muchos goles). El bound original `(-0.5, 0.0)` enmascaraba este hecho; se amplió a `(-0.5, 0.3)` en Fase 1.

### `HOME_ADVANTAGE = 1.0`

**Justificación:** `compute_ratings_for_team` calcula `att_home = goles_local_equipo / lg_avg_home`, donde `lg_avg_home = media de goles de locales en la liga`. Esa normalización **ya incluye la localía**. Multiplicar por `HOME_ADVANTAGE > 1` duplicaba el efecto.

**Evidencia:** con `HA = 1.12`, el bias P(H) era **+7.24 pp** (sobreestimaba al local). Con `HA = 1.0`, el bias bajó a **+2.9 pp**. HA por liga no generaliza (diferencias < 0.002 Brier, dentro del ruido con n=150).

---

## 3. Métricas walk-forward (temporadas 2025 y 2026)

Ver `output/baseline_clean_metrics_20261107.csv` para la tabla completa.

### Resumen por liga (agregado)

| Liga | n   | Brier(DC) | Brier(Poisson) | Brier(Mercado) | Gap vs Mercado |
| ---- | --- | --------- | -------------- | -------------- | -------------- |
| BL1  | 378 | 0.1976    | 0.1977         | 0.1904         | +0.0072        |
| DED  | 405 | 0.2016    | 0.2021         | 0.1953         | +0.0063        |
| FL1  | 387 | 0.2032    | 0.2030         | 0.1927         | +0.0105        |
| PD   | 489 | 0.1971    | 0.1971         | 0.1873         | +0.0098        |
| PL   | 470 | 0.2105    | 0.2110         | 0.2037         | +0.0068        |
| PPL  | 396 | 0.1907    | 0.1902         | 0.1814         | +0.0093        |
| SA   | 480 | 0.2002    | 0.2003         | 0.1913         | +0.0089        |

### Conclusión clave

**El mercado bate al modelo en 13 de 14 combinaciones liga/temporada.** Solo BL1 2026 tiene DC marginalmente mejor (gap de -0.0063, dentro del ruido con n=72).

**DC ≈ Poisson en 1X2.** El `rho` por liga aporta mejoras de ~0.0005 en Brier (marginal). La corrección DC brilla en marcadores exactos y mercados de goles bajos, no en 1X2.

---

## 4. Limitaciones conocidas (heredadas de Fase 0)

| Limitación                     | Impacto en Fase 1                        |
| ------------------------------ | ---------------------------------------- |
| xG 2026-27 = NaN               | ❌ Ninguno (DC usa goles)                |
| PSCD 2026-27 = NaN             | ❌ Ninguno (CLV se mide en Fase 3)       |
| DED/PPL sin xG (crónico)       | ❌ Ninguno (DC usa goles)                |
| `status=None` en 7733 partidos | ❌ Ninguno (modelo no filtra por status) |

**Fase 1 completada sin depender de datos que no tenemos.**

---

## 5. Test de invariancia temporal

3 tests implementados en `tests/test_temporal_invariance.py`:

1. **`test_predict_is_stable_when_adding_future_data`:** predecir un partido con train que excluye datos futuros vs train que los incluye → predicciones idénticas.
2. **`test_predict_uses_only_past_data`:** `as_of_date=D` filtra `date < D`, no `date <= D`.
3. **`test_no_future_leakage_across_seasons`:** añadir temporada 2026 no cambia predicciones de 2025.

**Los 3 tests pasan.** No hay data leakage.

---

## 6. Entregables de Fase 1

| Archivo                                   | Propósito                          |
| ----------------------------------------- | ---------------------------------- |
| `scripts/verify_invariants.py`            | 7 invariantes del contrato (I1-I7) |
| `tests/test_invariants.py`                | Tests de las 7 invariantes         |
| `tests/test_dixon_coles_math.py`          | 17 tests matemáticos de DC         |
| `tests/test_temporal_invariance.py`       | 3 tests de data leakage            |
| `scripts/compute_league_rho.py`           | Cálculo de rho por liga            |
| `output/rho_cache.json`                   | Caché de rho por liga              |
| `scripts/baseline_clean.py`               | Walk-forward reproducible          |
| `output/baseline_clean_predictions_*.csv` | 3005 predicciones walk-forward     |
| `output/baseline_clean_metrics_*.csv`     | Métricas por liga/temporada        |

---

## 7. Decisión para Fase 2

**El baseline limpio NO tiene edge en 1X2 contra el mercado.** Es una conclusión honesta, no un fracaso.

**Implicaciones para Fase 2 (LightGBM):**

- LightGBM debe batir a DC **y** acercarse al mercado para justificar su complejidad.
- Si LightGBM con FBref no bate a DC en Brier, **conservar DC** (regla del roadmap).
- Si DC no tiene edge, LightGBM probablemente tampoco → considerar pivotar a dashboard.

**Criterio de Gate 2 (modificado con la evidencia actual):**

- ✅ Avanzar si: LightGBM bate a DC en Brier en ≥4 de 7 ligas **Y** su Brier se acerca al mercado (gap < 0.005).
- ⚠️ Conservar DC si: LightGBM ≈ DC en Brier (diferencia < 0.002).
- 🚨 Pivotar a dashboard si: LightGBM y DC pierden contra el mercado por gap > 0.010.

---

## 8. Reproducibilidad

```bash
# 1. Recalcular rho por liga (2-4 min)
python scripts/compute_league_rho.py

# 2. Regenerar baseline limpio (3-5 min)
python scripts/baseline_clean.py

# 3. Ver métricas
python -c "import pandas as pd; from pathlib import Path; f = sorted(Path('output').glob('baseline_clean_metrics_*.csv'))[-1]; print(pd.read_csv(f).round(4).to_string())"

# 4. Verificar invariantes
python scripts/verify_invariants.py

# 5. Todos los tests
pytest -v
```

**Guarda el archivo.**

---

## 📋 Bloque 3: Update `data_contract.md`

**Añade al final de `docs/data_contract.md`:**

```markdown
---

## 9. Parámetros del modelo Dixon-Coles (Fase 1)

### 9.1 `rho` por liga

Estimado con MLE sobre los últimos 300 partidos de cada liga (ver `output/rho_cache.json`):

| Liga | rho | n |
|---|---|---|
| FL1 | -0.0822 | 288 |
| PL | -0.1256 | 290 |
| PD | -0.0280 | 290 |
| PPL | +0.0896 | 289 |
| DED | -0.1381 | 288 |
| BL1 | -0.0676 | 288 |
| SA | +0.0398 | 290 |

**Nota:** PPL y SA tienen `rho > 0`. El bound original `(-0.5, 0.0)` enmascaraba este hecho; se amplió a `(-0.5, 0.3)` en Fase 1.

### 9.2 `HOME_ADVANTAGE = 1.0`

Se elimina el factor `1.12` porque `compute_ratings_for_team` ya normaliza por localía (`att_home = goles_local / lg_avg_home`). Multiplicar por `HOME_ADVANTAGE > 1` duplicaba el efecto → P(H) sobreestimada en +7.24 pp.

### 9.3 Recalcular parámetros

```bash
python scripts/compute_league_rho.py

```bash
python scripts/compute_league_rho.py
Genera output/rho_cache.json. send_alerts.py lo carga al inicio.


---

## 📋 Bloque 4: Commit + merge a main

```cmd
REM 1. Verificar cambios
git status

REM 2. Añadir todo
git add scripts/baseline_clean.py docs/baseline_clean.md docs/data_contract.md output/baseline_clean_predictions_20261107.csv output/baseline_clean_metrics_20261107.csv

REM 3. Commit
git commit -m "feat(fase1): baseline limpio DC + documentacion de parametros finales"

REM 4. Push
git push -u origin dev-fase1

REM 5. Merge a main
git checkout main
git pull origin main
git merge dev-fase1
git push origin main
git checkout dev-fase1

REM 6. Verificar
git log --oneline -6
git branch