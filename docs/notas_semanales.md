## Semana 1 (2026-10-18 a 2026-10-25)

- Alertas acumuladas: N
- PICKs validados (PL/BL1): N
- Anomalías: [ej. "3 días sin ninguna alerta", "el log muestra error X"]
- Observaciones: [ej. "muchos INFO de cuota 5.0, EVs >40%"]

## Regla: un partido = una alerta

A partir de 2026-11-07, `send_alerts.py` tiene deduplicación:
un partido solo se envía una vez, aunque se reejecute el pipeline.

Para el análisis:

- Cada partido cuenta UNA vez.
- Se usa la PRIMERA alerta (timestamp más antiguo).
- El `odds_open` de la primera alerta es el que "apostaste".
- Las reevaluaciones posteriores se ignoran.

Comando de verificación:
`df.drop_duplicates(subset=['competition','home_team','away_team','match_date'])`


## Resultado parcial paper trading (2026-11-07, n=13)

- Hit rate: 15.4% (vs baseline esperado 27-30%) ❌
- Yield: -33.77% ❌
- CLV: +2.60% (pero 100% CLV+ en PICK → sesgo metodológico, no fiable)
- PICK VALIDADO con resultado: 0
- PICK sin validar con resultado: 5 (hit 20%, yield -27.8%)
- INFO con resultado: 8 (hit 12.5%, yield -37.5%)

**Conclusión preliminar:** señal negativa. Hit rate muy por debajo del baseline.
n=13 insuficiente para concluir. Necesario extender 4 semanas más.

**Riesgo:** si el patrón se mantiene con n≥30, el edge del backtest no existe
en vivo y hay que cerrar el mercado Draw.
