# Data Contract — Football Pipeline v2

**Fecha:** 2026-11-07
**Fase:** 0 (Contrato de datos y reproducción de la base)
**Estado:** Activo
**Última revisión:** 2026-11-13

---

## 1. Fuentes de datos

| Fuente                  | Proporciona                             | URL/API                                                      | Frecuencia                           |
| ----------------------- | --------------------------------------- | ------------------------------------------------------------ | ------------------------------------ |
| **football-data.co.uk** | Resultados históricos, cuotas de cierre | `https://www.football-data.co.uk/mmz4281/{season}/{div}.csv` | 1 vez/día (temporada actual)         |
| **football-data.org**   | Fixtures futuros, equipos               | `https://api.football-data.org/v4`                           | 1 vez/día                            |
| **The Odds API**        | Cuotas de apertura (h2h)                | `https://api.the-odds-api.com/v4/sports`                     | 1 vez/día                            |
| **Understat**           | xG, xGA (solo 5 ligas)                  | `https://understat.com`                                      | **NO USADO** (librería rota, ver §6) |

---

## 2. Archivos de datos procesados

### 2.1 `data/processed/history.parquet` (RAW)

**Propósito:** histórico sin enriquecer, tal como viene de football-data.co.uk.

**Shape actual:** 8111 partidos × 183 columnas
**Rango actual:** 2023-08-11 → 2026-11-02
**Generado por:** `main.py --mode download` (inicial) + `scripts/refresh_history.py` (incremental)
**Consumido por:** `scripts/enrich_history_with_xg.py`

**Columnas clave (aliases internos):**
| Columna | Tipo | Descripción |
|---|---|---|
| `match_id` | object | ID determinístico: `{liga}_{YYYYMMDD}_{hash12}` |
| `date` | datetime64[ns] | Fecha del partido (naive UTC, ver §10) |
| `competition` | object | Código de liga (PL, BL1, PD, SA, FL1, DED, PPL, CL) |
| `season` | int64 | Año de inicio (2023, 2024, 2025, 2026) |
| `home_team` | object | Nombre del equipo local |
| `away_team` | object | Nombre del equipo visitante |
| `home_goals` | int64 | Goles del local |
| `away_goals` | int64 | Goles del visitante |
| `total_goals` | int64 | home_goals + away_goals |
| `odds_home`, `odds_draw`, `odds_away` | float64 | Cuotas de apertura |
| `AvgCD`, `PSCD`, `B365CD` | float64 | Cuotas de cierre (Avg, Pinnacle, Bet365) |

**Columnas raw adicionales:** ~160 columnas con los nombres originales de football-data.co.uk (`Date`, `HomeTeam`, `FTHG`, `FTAG`, `B365H`, etc.).

### 2.2 `data/processed/history_with_xg.parquet` (ENRICHED)

**Propósito:** RAW + features xG. **Fuente única de verdad para predicciones.**

**Shape actual:** 8111 partidos × 187 columnas (183 del RAW + 4 de xG)
**Rango actual:** 2023-08-11 → 2026-11-02
**Generado por:** `scripts/enrich_history_with_xg.py`
**Consumido por:** `scripts/send_alerts.py`, `scripts/update_clv_history.py`

**Columnas adicionales sobre el RAW:**
| Columna | Tipo | Descripción |
|---|---|---|
| `home_xg` | float64 | xG del local |
| `away_xg` | float64 | xG del visitante |
| `home_np_xg` | float64 | xG sin penaltis del local |
| `away_np_xg` | float64 | xG sin penaltis del visitante |

**Nota sobre `date`:** este parquet se guarda como `datetime64[ns, UTC]` (aware) por `fix_timestamps_utc.py` en Fase 1. **Los scripts DEBEN normalizar a naive antes de comparar** (ver §10).

### 2.3 `data/processed/upcoming_fixtures.parquet`

**Propósito:** fixtures futuros con cuotas de empate y metadatos de procedencia.

**Shape actual:** ~74 partidos (variable)
**Rango actual:** próximos 7-15 días
**Generado por:** `scripts/fetch_upcoming.py`
**Consumido por:** `scripts/send_alerts.py`

**Columnas:**
| Columna | Tipo | Descripción |
|---|---|---|
| `competition` | object | Código de liga |
| `date` | datetime64[ns] | Fecha UTC del partido (**naive**, ver §10) |
| `home_team`, `away_team` | object | Nombres normalizados |
| `status` | object | Estado del partido (`SCHEDULED`, etc.) |
| `odds_draw` | float64 | Cuota de empate (apertura) |
| `bookmaker_key` | object | Bookmaker real (`pinnacle`, `bet365`, ...) |
| `market` | object | Mercado (`h2h`) |
| `capture_timestamp` | object | ISO UTC de captura de la cuota |
| `season` | object | Temporada (año actual) |

### 2.4 `output/alerts_history.csv`

**Propósito:** log persistente de alertas enviadas a Telegram. Base del paper trading y CLV tracking.

**Columnas:**
| Columna | Tipo | Descripción |
|---|---|---|
| `timestamp_sent` | ISO datetime | Cuándo se envió la alerta |
| `competition` | str | Liga |
| `match_date` | str | Fecha del partido (YYYY-MM-DD) |
| `home_team`, `away_team` | str | Equipos |
| `prob_D` | float | P(D) del modelo |
| `odds_open` | float | Cuota de apertura |
| `odds_source` | str | Bookmaker real (`pinnacle`, `bet365`, ...) o `Pinnacle (unverified)` para alertas pre-Fase 0 |
| `market` | str | Mercado (`h2h`) |
| `capture_timestamp` | str | ISO UTC de captura de la cuota (vacío para alertas pre-Fase 0) |
| `ev` | float | EV calculado |
| `tier` | str | `PICK` o `INFO` |
| `is_validated` | int | 1 si liga validada (PL/BL1), 0 si no |
| `odds_close` | float | Cuota de cierre (rellenado por `update_clv_history.py`) |
| `result` | str | `W` (empate) o `L` (no empate) |
| `clv_pct` | float | CLV % (solo si odds_close comparable) |
| `pnl` | float | PnL con stake 1 unidad |

**Nota sobre `FIELDS`:** cualquier cambio en la lista `FIELDS` de `src/alerts_logger.py` requiere:

1. Migrar el CSV existente (con `scripts/_fix_alerts_csv.py` o similar).
2. Ampliar `verify_gate0.py` con un check de header.

---

## 3. Flujo diario de actualización

RUTINA DIARIA (daily_run.py)
│
├─► 1. refresh_history.py
│ ├─► Descarga CSVs 2026-27 de football-data.co.uk
│ ├─► Añade partidos nuevos a history.parquet
│ └─► Genera match_id determinísticos (apply_match_id)
│
├─► 2. enrich_history_with_xg.py
│ ├─► Lee history.parquet
│ ├─► Añade columnas xG (hasta mayo 2026)
│ └─► Escribe history_with_xg.parquet
│
├─► 3. fetch_upcoming.py
│ ├─► Descarga fixtures de football-data.org (7 ligas)
│ ├─► Descarga cuotas de The Odds API
│ └─► Escribe upcoming_fixtures.parquet (con bookmaker/market/capture_timestamp)
│
├─► 4. update_clv_history.py
│ └─► Rellena resultados/CLV de alertas pasadas
│
└─► 5. send_alerts.py
├─► Lee upcoming_fixtures.parquet + history_with_xg.parquet
├─► Normaliza fechas a naive UTC (ver §10)
├─► Predice con Dixon-Coles (rho por liga)
├─► Filtra EV/cuota
├─► Envía a Telegram (con retry)
└─► Registra en alerts_history.csv (siempre, aunque Telegram falle)

---

## 4. Invariantes del contrato de datos

Estas reglas **deben cumplirse siempre**. Si alguna se rompe, es un bug de Fase 0:

| #   | Invariante                                                                              | Verificación                                                                  |
| --- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| I1  | `match_id` único por partido                                                            | `df['match_id'].duplicated().sum() == 0`                                      |
| I2  | `match_id` no nulo                                                                      | `df['match_id'].isna().sum() == 0`                                            |
| I3  | `date` sin nulos                                                                        | `df['date'].isna().sum() == 0`                                                |
| I4  | `home_goals` y `away_goals` sin nulos en partidos jugados                               | `df[df['status']=='FINISHED'][['home_goals','away_goals']].isna().sum() == 0` |
| I5  | No duplicados por (date, home_team, away_team)                                          | `df.duplicated(subset=['date','home_team','away_team']).sum() == 0`           |
| I6  | `history_with_xg.parquet` ⊇ `history.parquet` (mismo nº de filas + columnas xG)         | `len(enriched) == len(raw) and (set(raw.columns) ⊂ set(enriched.columns))`    |
| I7  | `alerts_history.csv` sin duplicados por (competition, home_team, away_team, match_date) | `df.duplicated(...).sum() == 0`                                               |
| I8  | `alerts_history.csv` header coincide con `FIELDS` de `alerts_logger.py`                 | `header_csv == FIELDS`                                                        |
| I9  | `date` de history y upcoming normalizables a naive UTC                                  | ver §10                                                                       |

---

## 5. Comandos de verificación

//bash

# Verificar invariantes

python scripts/verify_invariants.py

# Verificar Gate 0 (7 checks)

python scripts/verify_gate0.py

# Reporte de cobertura

python scripts/data_coverage_report.py

---

# 6. Limitaciones aceptadas

L1: xG 2026-27 no disponible
Problema: los ficheros xg\_\*.csv de Understat solo llegan hasta mayo 2026. Los partidos de agosto-noviembre 2026 tienen xG = NaN.

Intentos de arreglo (2026-11-07):

Librería understat (pip, v0.1.14, 2022) → falla con JSONDecodeError (Understat cambió su HTML/JSON).

Scraping manual → descartado (mantenimiento perpetuo, fragilidad alta).

Impacto:

Fase 1 (Dixon-Coles): ninguno — DC usa goles, no xG.

Fase 2 (LightGBM): moderado — LightGBM usará xG hasta 2025 + goles + Elo + forma para 2026.

Decisión: aceptar limitación. Documentar. Si aparece fuente fiable en el futuro, añadir.

L2: PSCD (Pinnacle close) no disponible para 2026-27
Problema: football-data.co.uk no publica PSCD para la temporada 2026-27 (2190 de 8111 partidos sin PSCD).

Impacto: CLV no medible para esos partidos. update_clv_history.py marca clv_pct como vacío cuando no hay PSCD.

Decisión: usar AvgCD como cierre cuando PSCD no está disponible, pero marcando clv_source='Avg' (indicativo, no concluyente).

L3: DED y PPL sin xG nunca
Problema: Understat no cubre Eredivisie ni Primeira Liga. xG siempre es NaN para esas ligas.

Impacto: si LightGBM usa xG como feature, DED y PPL tendrán cobertura parcial.

Decisión: entrenar LightGBM con o sin xG según disponibilidad. Documentar.

L4: Timestamps naive (resuelto con §10)
Problema original: history.parquet tenía fechas naive, history_with_xg.parquet aware (UTC). La inconsistencia causaba Invalid comparison between dtype=datetime64[ns, UTC] and Timestamp en enrich_fixture.

Decisión: ver §10. Convención adoptada: naive UTC consistente en todos los scripts, con normalización obligatoria al cargar.

# 7. Bugs conocidos y estado

Bug Estado Commit Notas
B1: refresh_history.py no actualizaba parquet ✅ Resuelto 813c48e Reescrito para escribir en history.parquet
B2: match_id 95% nulos ✅ Resuelto f98d977 Generado determinísticamente para 7733 partidos
B3: xG 100% nulos en 2026-27 ✅ Documentado — Ver §6 L1
B4: Timestamps naive / TZ inconsistente ✅ Resuelto Bloque 2+3 Ver §10. send_alerts.py normaliza ambas fechas
B5: PSCD 100% nulos en 2026-27 📝 Documentado — Ver §6 L2
B6: Sin odds_source en alerts_history.csv ✅ Resuelto 9ef73ff Columna añadida en Bloque 2
B7: refresh_history.py no generaba match_id para partidos nuevos ✅ Resuelto 0f7145c apply_match_id en refresh_history.py
B8: Telegram timeout al enviar 5 seguidos ✅ Resuelto 9ef73ff Retry + backoff + sleep(2)
B9: log_alert() no se ejecutaba si Telegram fallaba ✅ Resuelto 9ef73ff Movido fuera del if
B10: Header de alerts_history.csv desalineado ✅ Resuelto 9ef73ff Script one-time \_fix_alerts_csv.py

# 8. Changelog

Fecha Cambio
2026-11-07 Creación inicial del contrato
2026-11-07 B1 resuelto: refresh_history reescrito
2026-11-07 B2 resuelto: fix_match_id aplicado
2026-11-07 B3 documentado: xG 2026 no disponible
2026-11-08 B6 resuelto: odds_source en alerts_history.csv (Fase 0 retomada, Bloque 2 inicial)
2026-11-08 B7 resuelto: refresh_history.py genera match_id (Bloque 1)
2026-11-13 B4 resuelto: TZ normalizada en send_alerts.py (Bloque 2)
2026-11-13 B8, B9, B10 resueltos: retry Telegram, log independiente, header CSV (Bloque 2)
2026-11-13 §10 añadida: semántica de fechas (Bloque 3)
2026-11-13 §4 ampliada: invariantes I8, I9 (Bloques 3+4)
2026-11-13 §6 L4 actualizada, §7 ampliada con B7-B10

# 9. Glosario

Aware (TZ): datetime64[ns, UTC] — con etiqueta TZ.

Naive (TZ): datetime64[ns] — sin etiqueta TZ (pero representa UTC por convención, ver §10).

PICK: alerta que cumple EV ≥ 8% AND cuota ≤ 3.80 y liga validada (PL/BL1).

INFO: alerta que cumple EV ≥ 8% AND cuota ≤ 5.50 pero no es PICK.

rho: parámetro de Dixon-Coles (correlación de marcadores bajos).

CLV: Closing Line Value — movimiento de cuota a favor.

# 10. Semantica de fechas

---

## 10. Semántica de fechas

**Esta sección es crítica para evitar bugs silenciosos de comparación de TZ.**

### 10.1 Convención adoptada

Ambos parquets (`history_with_xg.parquet` y `upcoming_fixtures.parquet`) usan:

- **Dtype:** `datetime64[ns]` cuando están normalizados (naive, sin TZ).
- **Zona horaria:** UTC, pero **sin etiqueta TZ**.

**Traducción:** `date = 2026-11-08 15:00:00` significa **15:00 UTC**, no hora local.

### 10.2 Por qué naive y no aware

- `football-data.co.uk` devuelve fechas sin TZ → no podemos verificar zona origen.
- `fix_timestamps_utc.py` (Fase 1) dejó `history_with_xg.parquet` como `datetime64[ns, UTC]` (aware).
- `fetch_upcoming.py` escribe `upcoming_fixtures.parquet` como `datetime64[ns]` (naive).
- **La inconsistencia causó el bug de Bloque 2:** `enrich_fixture` fallaba con `Invalid comparison between dtype=datetime64[ns, UTC] and Timestamp`.

### 10.3 Regla obligatoria para scripts

**Cualquier script que cargue estos parquets DEBE normalizar antes de comparar:**

```python
df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

10.4 Hora real del partido
date representa el día del partido, no la hora exacta del kickoff. football-data.co.uk solo provee día (00:00 UTC en el parquet). football-data.org provee hora UTC real para fixtures futuros, pero se normaliza al comparar por fecha.

No interpretes date = 2026-11-08 00:00:00 como "kickoff a medianoche UTC". Es solo el día.

10.5 Tests que protegen esta convención
tests/test_date_semantics.py: verifica que history_with_xg (aware) y upcoming (naive) pueden normalizarse y compararse.

scripts/verify_gate0.py check #6: falla si TZ es inconsistente entre parquets.

```
