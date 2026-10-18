# Protocolo de Paper Trading — 4 semanas

**Fecha de inicio:** 2026-10-18
**Fecha de análisis final:** 2026-11-15
**Objetivo:** Validar si el edge detectado en el backtest (PL+BL1: yield +19% / +18.9%) se sostiene en vivo, y medir si las demás ligas tienen señal real o son ruido.

---

## 📌 Contexto

Este experimento no busca "ganar dinero". Busca **validar un modelo** antes de arriesgar dinero real. El sistema envía alertas a Telegram con tres niveles de confianza:

| Tier                      | Filtro                                          | Qué significa                           |
| ------------------------- | ----------------------------------------------- | --------------------------------------- |
| 📌 **PICK VALIDADO**      | EV ≥ 8% + cuota ≤ 3.80 + liga PL/BL1            | Apuesta respaldada por backtest         |
| 📌 **PICK (sin validar)** | EV ≥ 8% + cuota ≤ 3.80 + liga distinta a PL/BL1 | Value detectado, sin respaldo histórico |
| 🔍 **INFO**               | EV ≥ 8% + cuota ≤ 5.50                          | Solo tracking. NO apostar               |

**Regla de oro durante las 4 semanas:** ningún stake real. Todo es simulado. Se registra en `output/alerts_history.csv` para medir resultados.

---

## 🗓️ Rutina DIARIA (0 minutos, automático)

El bot corre solo:

- **07:00** → `FootballPipeline_Daily` ejecuta `fetch_upcoming.py` (descarga cuotas frescas de las 7 ligas).
- **07:15** → `FootballPipeline_Alerts` ejecuta `send_alerts.py` (predice, filtra y envía alertas a Telegram).

**Tú no haces nada.** Solo recibes las alertas en Telegram si hay value.

### Si el PC estaba apagado a las 07:00 (tareas no se ejecutaron)

Ejecuta manualmente cuando enciendas el PC:

```cmd
schtasks /run /tn "FootballPipeline_Daily"
timeout /t 30
schtasks /run /tn "FootballPipeline_Alerts"
```
