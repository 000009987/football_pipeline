# Fase 2 — Cuotas, EV y Liquidación

**Fecha:** 2026-11-14
**Fase:** 2 (Cuotas, EV y Liquidación)
**Estado:** Cerrada
**Commits:** `09e2fc3`, `b9bc2fd`, `2bd4d12`, `e8d28c4`

---

## 1. Objetivo

Garantizar que las cuotas y liquidaciones son correctas antes de añadir mercados.

---

## 2. Qué se implementó

### 2.1 Liquidación de mercados (`src/markets.py`)

| Mercado     | Funciones     | Casos soportados                                                     |
| ----------- | ------------- | -------------------------------------------------------------------- |
| 1X2         | `settle_1x2`  | win, loss (sin push, sin media)                                      |
| O/U 2.5     | `settle_ou25` | win, loss (sin push)                                                 |
| BTTS        | `settle_btts` | win, loss (sin push)                                                 |
| AH asiático | `settle_ah`   | win, loss, push, half-win, half-loss, void (líneas .0, .25, .5, .75) |

**28 tests** en `tests/test_settlement.py`.

### 2.2 Stake y `clv_source` en `alerts_history.csv`

- `FIELDS` ampliado de 17 a 19 columnas:
  - `stake` (1.0 PICK, 0.0 INFO)
  - `clv_source` (Pinnacle/Avg/"" — rellena por `update_clv_history.py`)
- Migración one-time: 25 alertas pre-fix con `stake=1.0` (12 PICKs) y `0.0` (13 INFOs).
- `send_alerts.py`: Kelly 0.25x para PICKs, cap a 1 unidad.

### 2.3 Desvig, validación y Kelly (`src/evaluation_helpers.py`)

- `remove_overround(odds_list)`: elimina overround, normaliza a 1.0.
- `validate_odds(odds)`: 1 ≤ cuota ≤ 100.
- `validate_prob(prob)`: 0 ≤ prob ≤ 1.
- `kelly_fraction(prob, odds, fraction=0.25)`: Kelly fraccionado con cap.

**15 tests** en `tests/test_evaluation_helpers.py`.

### 2.4 Comparabilidad CLV (`determine_clv_source`)

- `("Pinnacle", True)`: PSCD válido → CLV comparable con apertura Pinnacle.
- `("Avg", False)`: solo AvgCD → CLV no concluyente.
- `("", False)`: sin cierre → sin CLV.

`update_clv_history.py` escribe `clv_source` en el CSV.

**6 tests** adicionales en `tests/test_evaluation_helpers.py`.

---

## 3. Criterios de Gate 2

| #   | Criterio                                                                  | Estado                                                      |
| --- | ------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 1   | Pruebas cubren todos los casos de liquidación (push, half-win, half-loss) | ✅ 28 tests                                                 |
| 2   | Cada apuesta reconstruible desde el precio original                       | ✅ `odds_open` + `capture_timestamp` + `odds_source` en CSV |
| 3   | CLV solo para precios comparables (misma casa/fuente/línea)               | ✅ `determine_clv_source` + `clv_source` en CSV             |

**Gate 2 formalmente cumplido.**

---

## 4. Limitaciones conocidas

- **PSCD 2026-27 no disponible** (L2 de Fase 0). Los partidos de la temporada actual solo tienen `AvgCD` como cierre. `clv_source="Avg"`, CLV marcado como no concluyente.
- **AH asiático**: soporta líneas `.0`, `.25`, `.5`, `.75`. Líneas exóticas (`.125`, `.375`) no soportadas — devuelven `void`.
- **`stake=1.0` uniforme en PICKs**: el Kelly 0.25x se calcula dinámicamente en `send_alerts.py` para nuevas alertas, pero las 12 PICKs pre-fix usan 1.0 fijo (nominal).

---

## 5. Cómo reproducir

//bash

# 1. Verificar Gate 2

python scripts/verify_gate2.py

# 2. Tests de liquidación

pytest tests/test_settlement.py -v

# 3. Tests de desvig/validación/Kelly/CLV

pytest tests/test_evaluation_helpers.py -v

# 4. Todos los tests

pytest -v

---

## 7. Compatibilidad con futuras resoluciones de L1-L3

**Fase 2 está diseñada para que las limitaciones L1-L3 de Fase 0 se resuelvan sin cambios de código.**

### 7.1 L1 — xG 2026-27 no disponible

**Qué afecta a Fase 2:** nada. `src/markets.py`, `evaluation_helpers.py`, `update_clv_history.py` **no leen xG**. La liquidación usa `home_goals`/`away_goals`. El CLV usa `odds_open`/`PSCD`/`AvgCD`.

**Cómo se resolverá:** cuando aparezca fuente de xG fresco (API nueva, Understat arreglado, datos de pago):
1. Añadir xG de 2026-27 a `data/raw/xg_*.csv`.
2. `python scripts/enrich_history_with_xg.py` → `history_with_xg.parquet` con `home_xg`/`away_xg` rellenos para 2026-27.
3. `python scripts/verify_invariants.py` → 7/7 PASS.
4. `python scripts/verify_gate0.py` → 7/7 PASS.
5. Actualizar `data_contract.md` §6 L1 → "resuelta (fecha)".

**Código de Fase 2 que cambia:** **0 líneas.**

### 7.2 L2 — PSCD 2026-27 no disponible

**Qué afecta a Fase 2:** parcialmente, pero **manejado por diseño**.

`determine_clv_source` ya cubre los 3 casos:
- `("Pinnacle", True)` si `PSCD` válido → CLV comparable.
- `("Avg", False)` si solo `AvgCD` → CLV no concluyente, `clv_pct` vacío.
- `("", False)` si ninguno → sin CLV.

**Estado actual (2026-11-14):** los 25 alerts pre-fix tienen `clv_source=""` y `clv_pct` vacío. Cuando se liquiden partidos 2026-27, se marcarán `clv_source="Avg"` (no concluyente) porque `PSCD` no existe.

**Cómo se resolverá:** cuando football-data.co.uk publique `PSCD` para 2026-27 (o aparezca otra fuente):
1. `python scripts/refresh_history.py` → `history.parquet` con `PSCD` poblado.
2. `python scripts/enrich_history_with_xg.py` → propaga `PSCD`.
3. `python scripts/update_clv_history.py` → rellena `clv_source="Pinnacle"` + `clv_pct` numérico para partidos con PSCD.
4. Actualizar `data_contract.md` §6 L2 → "resuelta (fecha)".

**Código de Fase 2 que cambia:** **0 líneas.** `determine_clv_source` ya devuelve `("Pinnacle", True)` cuando `PSCD` es válido (test `test_determine_clv_source_pinnacle` lo verifica).

**Nota:** las 25 alertas pre-fix que ya tienen `result` relleno no se re-procesan automáticamente. Si se quiere forzar re-liquidación:
``python
# Script one-time (opcional)
df = pd.read_csv("output/alerts_history.csv")
df.loc[df["result"].notna(), "result"] = ""  # forzar re-liquidación
df.to_csv("output/alerts_history.csv", index=False)
# Luego: python scripts/update_clv_history.py

---

## 8. Alertas pre-fix (pre-2026-11-14)

### 8.1 Qué son

Las **21 alertas** generadas antes de los fixes de Fase 2 (commits `b9bc2fd` y posteriores) tienen:

- `odds_source = "Pinnacle (unverified)"` (no verificable)
- `capture_timestamp` vacío (sin hora de captura)
- `clv_source` vacío
- `stake` fijo (1.0 para PICKs, 0.0 para INFOs)

### 8.2 Qué se puede usar

| Métrica | ¿Usable? | Nota |
|---|---|---|
| **PnL** | ✅ Sí (desde B2.7) | PnL se calcula con stake real |
| **Hit rate** | ✅ Sí | W/L del CSV |
| **Yield** | ✅ Sí | PnL / stake total |
| **CLV** | ❌ **NO** | Sin fuente de apertura verificable, CLV es inválido |

### 8.3 Cómo segmentar el CSV

Para el análisis de Fase 3, segmentar `alerts_history.csv` por `odds_source`:

```python
import pandas as pd

df = pd.read_csv("output/alerts_history.csv")
pre_fix = df[df["odds_source"] == "Pinnacle (unverified)"]
post_fix = df[df["odds_source"] != "Pinnacle (unverified)"]

# CLV agregado: solo post_fix
clv_agregado = post_fix["clv_pct"].mean()

# PnL y yield: ambos
pnl_total = df["pnl"].sum()
yield_total = df["pnl"].sum() / df["stake"].sum()