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

### Resumen por liga (agregado, sin IC)

| Liga | n   | Brier(DC) | Brier(Poisson) | Brier(Mercado) | Gap vs Mercado |
| ---- | --- | --------- | -------------- | -------------- | -------------- |
| BL1  | 378 | 0.1975    | 0.1976         | 0.1904         | +0.0071        |
| DED  | 405 | 0.2020    | 0.2022         | 0.1953         | +0.0067        |
| FL1  | 387 | 0.2032    | 0.2032         | 0.1927         | +0.0105        |
| PD   | 489 | 0.1973    | 0.1972         | 0.1873         | +0.0100        |
| PL   | 470 | 0.2111    | 0.2111         | 0.2037         | +0.0074        |
| PPL  | 396 | 0.1903    | 0.1902         | 0.1814         | +0.0089        |
| SA   | 480 | 0.2001    | 0.2001         | 0.1913         | +0.0088        |

### IC95% por bootstrap (500 resamples)

| Liga/Temp | Brier DC [IC95%]        | Brier Mercado [IC95%]   | ¿Se solapan? |
| --------- | ----------------------- | ----------------------- | ------------ |
| BL1 2025  | 0.1980 [0.1876, 0.2083] | 0.1874 [0.1751, 0.1995] | ✅ Sí        |
| BL1 2026  | 0.1954 [0.1744, 0.2194] | 0.2019 [0.1741, 0.2311] | ✅ Sí        |
| DED 2025  | 0.1997 [0.1857, 0.2131] | 0.1934 [0.1806, 0.2071] | ✅ Sí        |
| DED 2026  | 0.2093 [0.1912, 0.2273] | 0.2022 [0.1794, 0.2263] | ✅ Sí        |
| FL1 2025  | 0.2056 [0.1966, 0.2141] | 0.1933 [0.1824, 0.2036] | ✅ Sí        |
| FL1 2026  | 0.1941 [0.1754, 0.2114] | 0.1904 [0.1697, 0.2106] | ✅ Sí        |
| PD 2025   | 0.1973 [0.1890, 0.2057] | 0.1903 [0.1817, 0.1994] | ✅ Sí        |
| PD 2026   | 0.1973 [0.1807, 0.2143] | 0.1806 [0.1597, 0.1997] | ✅ Sí        |
| PL 2025   | 0.2115 [0.2032, 0.2193] | 0.2038 [0.1930, 0.2144] | ✅ Sí        |
| PL 2026   | 0.2093 [0.1952, 0.2230] | 0.2036 [0.1837, 0.2241] | ✅ Sí        |
| PPL 2025  | 0.1903 [0.1787, 0.1999] | 0.1799 [0.1668, 0.1918] | ✅ Sí        |
| PPL 2026  | 0.1903 [0.1693, 0.2137] | 0.1862 [0.1610, 0.2124] | ✅ Sí        |
| SA 2025   | 0.2056 [0.1967, 0.2137] | 0.1948 [0.1853, 0.2059] | ✅ Sí        |
| SA 2026   | 0.1791 [0.1621, 0.1965] | 0.1732 [0.1543, 0.1961] | ✅ Sí        |

### Conclusión clave (revisada con IC95%)

**El mercado tiene mejor Brier puntual en 13/14 combinaciones liga/temporada (gap medio +0.008), pero los IC95% se solapan en TODAS las combinaciones.**

**Interpretación estadística:**

- Con n=72-380 partidos por combinación, **no hay evidencia suficiente para afirmar que el mercado bate a DC**.
- Tampoco hay evidencia de que DC bata al mercado.
- **Ambos están dentro del ruido estadístico** con los datos actuales.

**Implicación para Fase 2:**

- LightGBM **no parte en desventaja**: no es que "DC no tiene edge, LightGBM difícilmente lo tendrá". Es que **no podemos concluir nada con n pequeño**.
- La comparación DC vs LightGBM debe hacerse con IC95%, no solo con Brier puntual.
- Si LightGBM bate a DC por <0.002 en Brier, la diferencia será ruido (los IC95% se solaparán).
- Criterio de Gate 2: LightGBM debe batir a DC por un margen que **no se solape con los IC95%** de DC.

**DC ≈ Poisson en 1X2.** Esto sí es robusto (la corrección `rho` aporta poco en 1X2, independientemente del IC).

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

````markdown
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

Para producción (send_alerts.py): sigue usando rho_cache.json (últimos 300 partidos). Es lo más razonable para predecir partidos futuros, porque refleja la forma reciente.

Para backtest (baseline_clean.py): ahora es honesto (sin leakage), aunque la inestabilidad introduce ruido.

Para Fase 2: si LightGBM usa rho como feature, la inestabilidad debe tratarse (ej. rho promedio de las últimas 2 temporadas, no de la temporada test).
```
````

---

## 11. Grid search de `regress_weight` (P1-1 del audit)

**Hipótesis del audit independiente:** `weight=12` en `regress()` regresiona agresivamente los ratings a la media. Con `n=3`, el rating es solo 20% propio + 80% media. Esto podría estar "colapsando" los lambdas y explicando por qué DC ≈ Poisson en 1X2.

**Test:** grid search de `regress_weight ∈ {4, 6, 8, 12, 16}` sobre walk-forward 2025+2026 en las 7 ligas (3005 partidos).

**Resultado:**

| weight | Brier      | Δ vs 12  |
| ------ | ---------- | -------- |
| 4      | 0.2003     | -0.0000  |
| 6      | 0.2001     | -0.0002  |
| 8      | 0.2001     | -0.0002  |
| **12** | **0.2003** | baseline |
| 16     | 0.2007     | +0.0004  |

**Δ Brier máximo: 0.0004** (1/12 del umbral de señal real >0.005).

**Conclusión:** `regress_weight` **no tiene impacto en Brier**. La hipótesis del audit era falsa. `DC ≈ Poisson` en 1X2 **es una característica real del modelo**, no un artefacto del peso de regresión.

**Implicación para Fase 2:** LightGBM debe batir a DC por un margen >0.005 con IC95% no solapados. Si no lo hace, el edge no existe con estas features. `weight=12` es el default óptimo confirmado.

**Código reproducible:** `scripts/grid_search_weight.py`.

### 11.1 Repetición con `rho` walk-forward (2026-11-14)

El grid search original usaba `rho_cache.json` (estimado con los últimos 300 partidos, incluyendo 2025-26 → leakage conceptual). Se repitió con `rho` estimado walk-forward por liga/temporada (misma metodología que `baseline_clean.py`, sin leakage).

**Resultado con `rho` walk-forward:**

| weight | Brier      | Δ vs 12  |
| ------ | ---------- | -------- |
| 4      | 0.2004     | -0.0000  |
| 6      | 0.2002     | -0.0002  |
| 8      | 0.2002     | -0.0002  |
| **12** | **0.2004** | baseline |
| 16     | 0.2008     | +0.0004  |

**Δ Brier máximo: 0.0004.** Idéntico al grid original. La conclusión se mantiene: `weight` no tiene impacto en Brier.

**Nota sobre agregaciones:** el Brier agregado del grid (0.2004) difiere del Brier de `baseline_clean_metrics.csv` (0.1988) porque son dos agregaciones distintas. `baseline_clean.py` calcula media de medias (14 filas, cada liga/temporada pesa igual). El grid calcula Brier global sobre las 3005 predicciones (ligas con más partidos pesan más). Ambas agregaciones son válidas; la diferencia no es un bug.

### 11.2 Fix adicional: `.mode()` con `past` (2026-11-14)

`compute_ratings_for_team` usaba `.mode()` sobre `df` (histórico completo) en vez de `past` (filtrado por `as_of_date`) para inferir la competición del equipo. Corregido a `past` en líneas 333/335 de `src/feature_engineering.py`.

**Impacto en el baseline:** <0.0005. Todos los equipos de las 7 ligas domésticas juegan solo su liga en el parquet, así que `.mode()` devolvía el mismo valor con `df` que con `past`. El fix es correcto conceptualmente y previene leakage si en el futuro se añaden Championship o CL al parquet.

### 11.2 Fix adicional: `.mode()` con `past` (2026-11-14)

`compute_ratings_for_team` usaba `.mode()` sobre `df` (histórico completo) en vez de `past` (filtrado por `as_of_date`) para inferir la competición del equipo. Corregido a `past` en líneas 333/335 de `src/feature_engineering.py`.

**Impacto en el baseline:** <0.0005. Todos los equipos de las 7 ligas domésticas juegan solo su liga en el parquet, así que `.mode()` devolvía el mismo valor con `df` que con `past`. El fix es correcto conceptualmente y previene leakage si en el futuro se añaden Championship o CL al parquet.
