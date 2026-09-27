# Football Betting Pipeline

Pipeline completo para análisis estadístico de partidos de fútbol y detección de value bets.

## Modelos implementados
- **Poisson estándar** — baseline clásico
- **Dixon-Coles** — corrección para resultados de baja puntuación (0-0, 1-0, 0-1, 1-1)
- **Estimación de rho** — optimización MLE sobre datos históricos

## Ligas soportadas
| Código | Liga |
|--------|------|
| PL  | Premier League (Inglaterra) |
| PD  | LaLiga (España) |
| BL1 | Bundesliga (Alemania) |
| FL1 | Ligue 1 (Francia) |
| DED | Eredivisie (Países Bajos) |
| PPL | Primeira Liga (Portugal) |
| CL  | UEFA Champions League |
| EL  | UEFA Europa League |
| — | Eliteserien (Noruega) — vía CSV |
| — | Liga Saudí — vía CSV |

---

## Setup rápido

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Obtener API Key (GRATIS)
Regístrate en https://www.football-data.org/client/register
Copia tu API key y pégala en `config.py`:
```python
API_KEY = "tu_key_aqui"
```

### 3. Descargar datos históricos
```bash
python main.py --mode download
```
Primera ejecución descarga ~3 temporadas de cada liga. Tarda ~5-10 minutos por el rate limit del plan gratuito (10 req/min). Los datos se cachean en `data/processed/history.parquet`.

---

## Uso

### Analizar próximos partidos
```bash
python main.py --mode analyze
python main.py --mode analyze --days 3
```

### Analizar un partido específico con tus cuotas
```bash
python main.py --mode single \
    --home "Arsenal" --away "Chelsea" \
    --comp "PL" \
    --odds "1:2.10,X:3.40,2:3.60,O2.5:1.85,BTTS_Y:1.75"
```

**Claves de mercados:**
- `1` = victoria local · `X` = empate · `2` = victoria visitante
- `O0.5`, `O1.5`, `O2.5`, `O3.5`, `O4.5` = over
- `U0.5`, `U1.5`, `U2.5`, `U3.5` = under
- `BTTS_Y` = ambos marcan sí · `BTTS_N` = no

### Backtest (validación histórica)
```bash
python main.py --mode backtest --comp PL
```

### Dashboard interactivo
Abre `dashboard.html` en tu navegador. Permite calcular probabilidades y value bets directamente en el browser ingresando los lambdas estimados.

---

## Estructura del proyecto

```
football_pipeline/
├── config.py               ← API key y parámetros del modelo
├── main.py                 ← Orquestador principal (CLI)
├── requirements.txt
├── dashboard.html          ← Dashboard interactivo (browser)
├── src/
│   ├── data_loader.py      ← Descarga de football-data.org
│   ├── feature_engineering.py ← Ratings, forma, lambdas
│   ├── models.py           ← Poisson + Dixon-Coles + mercados
│   ├── value_bet_detector.py ← EV, Kelly, filtros
│   └── backtester.py       ← ROI, log-loss, Brier score
└── data/
    ├── raw/                ← Cache JSON/CSV de descargas
    └── processed/          ← history.parquet (datos limpios)
```

---

## Flujo de cálculo

```
datos históricos → ratings (att/def) → lambdas (xG esperados)
                                              ↓
                            matriz Dixon-Coles (7x7)
                                              ↓
                    1X2 · O/U · BTTS · marcadores exactos · AH
                                              ↓
                    comparar con cuotas → EV → Kelly → VALUE BETS
```

---

## Parámetros clave en config.py

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `DECAY_FACTOR` | 0.03 | Mayor = más peso a partidos recientes |
| `HOME_ADVANTAGE` | 0.25 | Boost de 25% al λ del equipo local |
| `MIN_EV` | 0.04 | EV mínimo para reportar apuesta (4%) |
| `MIN_ODDS` | 1.30 | Cuota mínima (evitar favoritos extremos) |
| `MAX_ODDS` | 8.00 | Cuota máxima (evitar lotería) |

---

## Fuentes de datos

- **football-data.org** — API gratuita, plan Free cubre todas las ligas top
- **football-data.co.uk** — CSV históricos para ligas no cubiertas (Noruega, Arabia)

---

## Notas importantes

1. **El modelo necesita datos** — con menos de ~50 partidos por equipo los ratings son poco confiables
2. **Las cuotas las ingresas tú** — el pipeline no scraping casas de apuestas en tiempo real (cambiaría constantemente)
3. **EV positivo no garantiza ganancia por partido** — garantiza ganancia a largo plazo con volumen suficiente
4. **Kelly fraccionario** (0.25x) — el script usa Quarter Kelly para reducir volatilidad
5. **Backtest honesto** — el walk-forward split evita data leakage

---

## Extensiones posibles

- Integrar xG de Understat con scraping de `understat.com`
- Añadir modelo ELO como feature adicional
- Monte Carlo para simulación de temporada completa
- Alertas automáticas por Telegram/email cuando aparece value bet
