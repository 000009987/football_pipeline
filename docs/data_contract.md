# Data Contract — Football Pipeline v2

**Fecha:** 2026-11-07
**Fase:** 0 (Contrato de datos y reproducción de la base)
**Estado:** Activo
**Última revisión:** 2026-11-07

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
| `date` | datetime64[ns] | Fecha del partido (naive, sin TZ) |
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

### 2.3 `data/processed/upcoming_fixtures.parquet`

**Propósito:** fixtures futuros con cuotas de empate.

**Shape actual:** ~96 partidos (variable)
**Rango actual:** próximos 7-15 días
**Generado por:** `scripts/fetch_upcoming.py`
**Consumido por:** `scripts/send_alerts.py`

**Columnas:**
| Columna | Tipo | Descripción |
|---|---|---|
| `competition` | object | Código de liga |
| `date` | datetime64[ns, UTC] | Fecha UTC del partido |
| `home_team`, `away_team` | object | Nombres normalizados |
| `odds_draw` | float64 | Cuota de empate (apertura) |
| `season` | object | Temporada (año actual) |

### 2.4 `output/alerts_history.csv`

**Propósito:** log persistente de alertas enviadas a Telegram. Base del paper trading.

**Columnas:**
| Columna | Tipo | Descripción |
|---|---|---|
| `timestamp_sent` | ISO datetime | Cuándo se envió la alerta |
| `competition` | str | Liga |
| `match_date` | str | Fecha del partido (YYYY-MM-DD) |
| `home_team`, `away_team` | str | Equipos |
| `prob_D` | float | P(D) del modelo |
| `odds_open` | float | Cuota de apertura |
| `ev` | float | EV calculado |
| `tier` | str | `PICK` o `INFO` |
| `is_validated` | int | 1 si liga validada (PL/BL1), 0 si no |
| `odds_close` | float | Cuota de cierre (rellenado por `update_clv_history.py`) |
| `result` | str | `W` (empate) o `L` (no empate) |
| `clv_pct` | float | CLV % (solo si odds_close comparable) |
| `pnl` | float | PnL con stake 1 unidad |

---

## 3. Flujo diario de actualización

RUTINA DIARIA (daily_run.py) │
└─────────────────────────────────────────────────────────────────┘
│
▼

refresh_history.py
└─► Descarga CSVs 2026-27 de football-data.co.uk
└─► Añade partidos nuevos a history.parquet
│
▼

enrich_history_with_xg.py
└─► Lee history.parquet
└─► Añade columnas xG (hasta mayo 2026)
└─► Escribe history_with_xg.parquet
│
▼

fetch_upcoming.py
└─► Descarga fixtures de football-data.org (7 ligas)
└─► Descarga cuotas de The Odds API
└─► Escribe upcoming_fixtures.parquet
│
▼

update_clv_history.py
└─► Rellena resultados/CLV de alertas pasadas
│
▼

send_alerts.py
└─► Lee upcoming_fixtures.parquet
└─► Predice con history_with_xg.parquet
└─► Filtra EV/cuota
└─► Envía a Telegram + registra en alerts_history.csv

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
| I6  | `history_with_xg.parquet` ⊇ `history.parquet` (mismo nº de filas + columnas xG)         | `len(enriched) == len(raw) and enriched.shape[1] == raw.shape[1] + 4`         |
| I7  | `alerts_history.csv` sin duplicados por (competition, home_team, away_team, match_date) | `df.duplicated(...).sum() == 0`                                               |

---

## 5. Comandos de verificación

```bash
# Verificar invariantes
python scripts/check_invariants.py

# Reporte de cobertura
python scripts/data_coverage_report.py

6. Limitaciones aceptadas
L1: xG 2026-27 no disponible
Problema: los ficheros xg_*.csv de Understat solo llegan hasta mayo 2026. Los partidos de agosto-noviembre 2026 tienen xG = NaN.

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

L4: Timestamps naive (sin UTC)
Problema: history.parquet tiene fechas naive (sin TZ).

Impacto: bajo. enrich_fixture compara as_of_date con date como naive, sin problema. Los partidos de football-data.co.uk son del mismo día en hora UK.

Decisión: ver §7. Se evalúa arreglar en Fase 0 o documentar.

7. Bugs conocidos y estado
Bug	Estado	Commit	Notas
B1: refresh_history.py no actualizaba parquet	✅ Resuelto	813c48e	Reescrito para escribir en history.parquet
B2: match_id 95% nulos	✅ Resuelto	f98d977	Generado determinísticamente para 7733 partidos
B3: xG 100% nulos en 2026-27	✅ Documentado	—	Ver §6 L1
B4: Timestamps naive	⏳ Pendiente	—	Ver §7.1
B5: PSCD 100% nulos en 2026-27	📝 Documentar	—	Ver §6 L2
B6: Sin columna odds_source en alerts_history.csv	⏳ Pendiente	—	Ver §7.2
7.1 B4: Timestamps naive
Estado: pendiente de decisión (arreglar o documentar como limitación aceptada).

Plan: ver Sub-bloque B del trabajo de Fase 0.

7.2 B6: Sin odds_source
Estado: pendiente.

Plan: añadir columna odds_source a alerts_history.csv para identificar la fuente (Pinnacle, Avg, B365).

8. Changelog
Fecha	Cambio
2026-11-07	Creación inicial del contrato
2026-11-07	B1 resuelto: refresh_history reescrito
2026-11-07	B2 resuelto: fix_match_id aplicado
2026-11-07	B3 documentado: xG 2026 no disponible
```
