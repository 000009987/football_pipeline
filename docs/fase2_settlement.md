# Fase 2 — Cuotas, EV y Liquidación

**Fecha de inicio:** 2026-11-14
**Fecha de cierre:** 2026-11-14
**Fase:** 2 (Cuotas, EV y Liquidación)
**Estado:** ✅ Cerrada (reconciliada con B2.7-B2.17)
**Commits:** `09e2fc3`, `b9bc2fd`, `2bd4d12`, `e8d28c4`, `4d9ee28`, `ef7f641`, `9725a38`, `8d487b5`, `92a25c8`, `697df67`, `eb40f84`, `e89746f`, `44e2217`, `cca81b1`, `e1a0b8d`, B2.16+17

---

## 1. Objetivo

Garantizar que las cuotas y liquidaciones son correctas antes de añadir mercados.

---

## 2. Qué se implementó

### 2.1 Liquidación de mercados (`src/markets.py`)

| Mercado     | Función       | Casos soportados                                                     |
| ----------- | ------------- | -------------------------------------------------------------------- |
| 1X2         | `settle_1x2`  | win, loss (sin push, sin media)                                      |
| O/U 2.5     | `settle_ou25` | win, loss (sin push)                                                 |
| BTTS        | `settle_btts` | win, loss (sin push)                                                 |
| AH asiático | `settle_ah`   | win, loss, push, half-win, half-loss, void (líneas .0, .25, .5, .75) |

**28 tests** en `tests/test_settlement.py`. **Cubren los 5 casos de liquidación** (win, loss, push, half-win, half-loss) + void + invalid pick.

**Nota sobre integración:** `markets.py` es una **biblioteca de liquidación**, no está conectada al cálculo de PnL del paper trading. El PnL de `alerts_history.csv` se calcula con `calculate_pnl` (basado en `result=W/L` de 1X2 Draw), no con `settle_*`. La integración de `markets.py` al backtest se decidirá en Fase 3 (ver §9).

### 2.2 Stake y `clv_source` en `alerts_history.csv`

- `FIELDS` ampliado de 17 a **19 columnas**:
  - `stake` (Kelly 0.25x para PICK, 0.0 para INFO)
  - `clv_source` (`Pinnacle`/`Avg`/`""`)
- Migración one-time: 25 alerts pre-fix con `stake=1.0` (PICKs) y `0.0` (INFOs).
- **`send_alerts.py` calcula Kelly 0.25x** para PICKs y lo guarda en `stake` + lo muestra en el mensaje Telegram (B2.15).
- **`update_clv_history.py` respeta el stake real** al calcular `pnl` (B2.7). INFOs con `stake=0.0` tienen `pnl=0.0`. Kelly fractional tiene `pnl=stake*(odds-1)` o `-stake`.

**Total: 19 columnas, PnL correcto desde B2.7.**

### 2.3 Desvig, validación y Kelly (`src/evaluation_helpers.py`)

- `remove_overround(odds_list)`: elimina overround, normaliza a 1.0.
- `validate_odds(odds)`: 1 ≤ cuota ≤ 100.
- `validate_prob(prob)`: 0 ≤ prob ≤ 1.
- `kelly_fraction(prob, odds, fraction=0.25)`: Kelly fraccionado con cap a 1.0.
- `calculate_pnl(odds, stake, is_win)`: PnL respetando el stake (B2.7).

**24 tests** en `tests/test_evaluation_helpers.py` + **11 tests** en `tests/test_update_clv.py`.

**Uso en producción:**

- `remove_overround`: **no usado en live**. El EV live (`p * odds - 1`) no requiere desvig. Se usará en Fase 3 para comparar modelo vs mercado.
- `validate_odds`/`validate_prob`: **usados en `send_alerts.py`** antes de predecir (B2.10). Si cuota/prob inválidas → skip. **2 tests** en `test_send_alerts.py` (B2.14).
- `kelly_fraction`: **usado en `send_alerts.py`** para calcular `stake` de PICKs (B2.15). **1 test** en `test_send_alerts.py`.
- `calculate_pnl`: **usado en `update_clv_history.py`** para PnL real (B2.7). **11 tests** en `test_update_clv.py`.

### 2.4 Comparabilidad CLV (`determine_clv_source`)

`determine_clv_source(pscd, avgcd, odds_source_open)` con 3 argumentos:

| Apertura           | Cierre       | Resultado             | ¿CLV?                      |
| ------------------ | ------------ | --------------------- | -------------------------- |
| `"pinnacle"`       | PSCD válido  | `("Pinnacle", True)`  | ✅ Sí                      |
| `"bet365"`         | PSCD válido  | `("Pinnacle", False)` | ❌ No (fuente distinta)    |
| `"avg"`            | AvgCD válido | `("Avg", True)`       | ✅ Sí                      |
| `"pinnacle"`       | AvgCD válido | `("Avg", False)`      | ❌ No (fuente distinta)    |
| `""` (desconocida) | AvgCD válido | `("Avg", False)`      | ❌ No (fuente desconocida) |
| cualquiera         | sin cierre   | `("", False)`         | ❌ No                      |

**9 tests** en `tests/test_evaluation_helpers.py`.

**`update_clv_history.py` escribe `clv_source` y `clv_pct`** solo si `comparable=True`.

---

## 3. Criterios de Gate 2

| #   | Criterio                                                                  | Estado                                                         |
| --- | ------------------------------------------------------------------------- | -------------------------------------------------------------- |
| 1   | Pruebas cubren todos los casos de liquidación (push, half-win, half-loss) | ✅ 28 tests                                                    |
| 2   | Cada apuesta reconstruible desde el precio original                       | ✅ `odds_open` + `odds_source` + `capture_timestamp` + `stake` |
| 3   | CLV solo para precios comparables (misma casa/fuente/línea)               | ✅ `determine_clv_source` + `clv_source`                       |

**Gate 2 formalmente cumplido con 8 checks en `verify_gate2.py`.**

---

## 4. Limitaciones conocidas

### L2 de Fase 0: PSCD 2026-27 no disponible

- Los partidos de la temporada actual solo tienen `AvgCD` como cierre.
- `clv_source="Avg"`, `clv_pct` calculado solo si apertura es `"avg"`.
- **CLV de 2026-27 es parcial/no concluyente** para el análisis de Fase 3.
- Ver §8 para más detalle.

### AH asiático limitado a líneas `.0`, `.25`, `.5`, `.75`

- Líneas exóticas (`.125`, `.375`) devuelven `void`.
- **No hay líneas exóticas en el mercado de fútbol estándar**, así que no afecta.

### `markets.py` no integrado al backtest (decisión diferida a Fase 3)

- `settle_*` está testeado pero **no se llama en `update_clv_history.py`**.
- El PnL de `alerts_history.csv` usa `calculate_pnl` (1X2 Draw), no `settle_1x2`.
- Ver §9 para la decisión sobre integrar en Fase 3.

---

## 5. Cómo reproducir

``bash

# 1. Verificar Gate 2 (8 checks)

python scripts/verify_gate2.py

# 2. Tests de liquidación

pytest tests/test_settlement.py -v

# 3. Tests de desvig/validación/Kelly/CLV/PnL

pytest tests/test_evaluation_helpers.py -v
pytest tests/test_update_clv.py -v

# 4. Todos los tests

pytest -v

# 6. Desviaciones del roadmap

Tarea Estado Nota
Persistir fuente apertura/cierre ✅ 100% odds_source (Fase 0) + clv_source (Fase 2)
Desvig ⚠️ Implementado, no integrado en live EV live no requiere desvig; se usa en Fase 3
Validación cuota/prob ✅ 100% Validadores usados en send_alerts.py (B2.10) + 2 tests (B2.14)
Stake base + Kelly 0.25x ✅ 100% Calculado en send_alerts.py + mostrado en Telegram + PnL respeta stake (B2.7 + B2.15)
Liquidaciones 4 mercados ✅ 100% 28 tests, cubre los 5 casos
CLV comparable ✅ 100% determine_clv_source con 3 args + 9 tests (B2.8 + B2.13)
Solo 1 desviación: desvig implementado pero no integrado en live. Se integra en Fase 3 cuando haya comparativa modelo vs mercado.

# 7. Compatibilidad con futuras resoluciones de L1-L3

7.1 L1 (xG 2026) y L3 (DED/PPL sin xG)
Impacto en Fase 2: 0. markets.py, evaluation_helpers.py, update_clv_history.py no leen xG.

Resolución: cuando aparezca fuente de xG, solo se regenera enrich_history_with_xg.py. 0 cambios de código en Fase 2.

7.2 L2 (PSCD 2026 no disponible)
Impacto: parcial, manejado por diseño. determine_clv_source marca clv_source="Avg" cuando solo hay AvgCD.

Resolución: cuando football-data.co.uk publique PSCD, se re-ejecuta update_clv_history.py. clv_source cambia de "Avg" a "Pinnacle" automáticamente. 0 cambios de código en Fase 2.

# 8. Alertas pre-fix (pre-2026-11-14)

8.1 Qué son
Las 21 alertas generadas antes de los fixes de Fase 2 tienen:

odds_source = "Pinnacle (unverified)" (no verificable)

capture_timestamp vacío

clv_source vacío

Las 13 alertas con result=W/L fueron recalculadas con calculate_pnl en B2.12:

PnL correcto desde B2.12. INFOs con stake=0.0 tienen pnl=0.0.

Antes de B2.12, los 8 INFOs tenían pnl=-1.00 o +4.00 (falso). Suma inflada: -4.390. Suma correcta: -1.390. Delta: +3.000.

8.2 Qué se puede usar
Métrica ¿Usable? Nota
PnL ✅ Sí (post B2.12) Recalculado con calculate_pnl
Hit rate ✅ Sí W/L del CSV
Yield ✅ Sí PnL / stake total (stake correcto)
CLV ❌ NO Sin fuente de apertura verificable, clv_source=""

8.3 Segmentación para Fase 3
Para el análisis de Fase 3, segmentar alerts_history.csv por odds_source:
import pandas as pd

df = pd.read_csv("output/alerts_history.csv")
pre_fix = df[df["odds_source"] == "Pinnacle (unverified)"]
post_fix = df[df["odds_source"] != "Pinnacle (unverified)"]

# CLV agregado: solo post_fix

clv_agregado = post_fix["clv_pct"].mean()

# PnL y yield: ambos (pero con PnL recalculado en B2.12)

pnl_total = df["pnl"].sum()
yield_total = df["pnl"].sum() / df["stake"].sum()

8.4 Impacto en Gate Final
PnL y yield: usables para ambos grupos.

CLV: solo para post_fix. Si no hay suficientes alertas post_fix con CLV válido, el criterio "CLV positivo (si es medible)" se marca como no concluyente, no como fallo.

8.5 Alertas nuevas (post 2026-11-14)
Todas las nuevas alertas tienen:

odds_source real (pinnacle, bet365, ...).

capture_timestamp real (ISO UTC).

stake calculado con Kelly 0.25x.

clv_source rellenado por update_clv_history.py.

Usables para todas las métricas, incluido CLV.

# 9. Decisión sobre integrar markets.py al backtest

9.1 Contexto
src/markets.py contiene 4 funciones de liquidación (settle_1x2, settle_ou25, settle_btts, settle_ah) con 28 tests. Pero update_clv_history.py no las usa. Calcula pnl directamente con calculate_pnl(odds, stake, is_win) donde is_win = (home_goals == away_goals).

9.2 ¿Es un problema?
No, es una decisión de scope. El PnL de alerts_history.csv es para el mercado "1X2 Draw" (empate). calculate_pnl lo maneja correctamente. settle_1x2(home_goals, away_goals, pick="DRAW", odds) haría lo mismo, pero no aporta valor adicional para este mercado específico.

9.3 ¿Cuándo se integrará?
Fase 3 (Backtest temporal fiable). Razones:

Fase 3 evaluará DC vs Poisson vs mercado en múltiples mercados (1X2, O/U, BTTS, AH).

Para O/U y BTTS, calculate_pnl no sirve (no sabe liquidar Over/Under ni BTTS).

La integración de markets.py es prerequisito de Fase 3, no de Fase 2.

En Fase 2, el único mercado de producción es 1X2 Draw, y calculate_pnl lo maneja.

9.4 Criterio de Fase 3
La integración de markets.py al backtest se considerará completa cuando:

scripts/backtest.py (nuevo) use settle\_\* para liquidar cada mercado.

Los 4 mercados tengan métricas separadas (Brier, yield, CLV) por mercado.

alerts*history.csv tenga columna market (ya existe) y settle*\* se use para PnL de cada mercado.

Esto se implementará en Fase 3, no en Fase 2.

# 10. Próximos pasos

Fase 3 (Backtest temporal fiable) puede empezar. La integración de markets.py al backtest es tarea de Fase 3.

No se añaden mercados nuevos a producción hasta que Fase 3 valide el modelo en 1X2 con CLV completo.

**Guarda el archivo.**

## Paso 2: Verificar

```cmd
findstr /c:"## 9. Decisión" docs\fase2_settlement.md
findstr /c:"B2.12" docs\fase2_settlement.md
findstr /c:"B2.15" docs\fase2_settlement.md
findstr /c:"137 passed" docs\fase2_settlement.md

```
