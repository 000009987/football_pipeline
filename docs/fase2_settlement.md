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

| Mercado | Funciones | Casos soportados |
|---|---|---|
| 1X2 | `settle_1x2` | win, loss (sin push, sin media) |
| O/U 2.5 | `settle_ou25` | win, loss (sin push) |
| BTTS | `settle_btts` | win, loss (sin push) |
| AH asiático | `settle_ah` | win, loss, push, half-win, half-loss, void (líneas .0, .25, .5, .75) |

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

| # | Criterio | Estado |
|---|---|---|
| 1 | Pruebas cubren todos los casos de liquidación (push, half-win, half-loss) | ✅ 28 tests |
| 2 | Cada apuesta reconstruible desde el precio original | ✅ `odds_open` + `capture_timestamp` + `odds_source` en CSV |
| 3 | CLV solo para precios comparables (misma casa/fuente/línea) | ✅ `determine_clv_source` + `clv_source` en CSV |

**Gate 2 formalmente cumplido.**

---

## 4. Limitaciones conocidas

- **PSCD 2026-27 no disponible** (L2 de Fase 0). Los partidos de la temporada actual solo tienen `AvgCD` como cierre. `clv_source="Avg"`, CLV marcado como no concluyente.
- **AH asiático**: soporta líneas `.0`, `.25`, `.5`, `.75`. Líneas exóticas (`.125`, `.375`) no soportadas — devuelven `void`.
- **`stake=1.0` uniforme en PICKs**: el Kelly 0.25x se calcula dinámicamente en `send_alerts.py` para nuevas alertas, pero las 12 PICKs pre-fix usan 1.0 fijo (nominal).

---

## 5. Cómo reproducir

```bash
# 1. Verificar Gate 2
python scripts/verify_gate2.py

# 2. Tests de liquidación
pytest tests/test_settlement.py -v

# 3. Tests de desvig/validación/Kelly/CLV
pytest tests/test_evaluation_helpers.py -v

# 4. Todos los tests
pytest -v