ROADMAP COMPLETO — Football Pipeline

1. Principios rectores (no negociables)
1. Un cambio → backtest → commit → siguiente. Nunca dos cambios sin medir el impacto del anterior.
1. Criterios de salida predefinidos. No se cambian después de ver los resultados. Si se cambian, se documenta el motivo y se re-mide.
1. Datos antes que modelos. Sin contrato de datos verificado, todo lo demás es ruido.
1. Backtest vs validación separados. Los filtros se optimizan en un periodo y se evalúan en otro distinto.
1. ML no es prioridad. LightGBM se prueba como viabilidad, no como objetivo. Si no supera los controles, se conserva Dixon-Coles.
1. Pivote ≠ cierre. Si no hay edge, el proyecto sigue como dashboard informativo.
1. Nunca se apuesta dinero real sin pasar el Gate Final.
1. Nunca se borra el baseline. \_baseline_pre_fase1/ se conserva para comparar.

1. Estructura de trabajo
   Branches
   text
   main (producción)
   ├── Código estable con el modelo validado
   ├── Escribe en output/alerts_history_final.csv
   └── Solo recibe cambios tras pasar el gate de la fase

dev-faseN (desarrollo)
├── Código en desarrollo para cada fase
├── NO escribe en alerts_history_final.csv
└── Se mergea a main solo tras pasar el gate

Archivos de paper trading (separados por modelo)
Archivo Qué contiene Periodo
\_baseline_pre_fase1/alerts_history.csv Baseline contaminado (backup) 18/10 - 07/11
output/alerts_history_dc_clean.csv DC con datos limpios (Fase 1-3) 12/11 - Fase 4
output/alerts_history_final.csv Modelo ganador (Fase 4+) Tras Gate 4

Estado del paper trading
Periodo Estado Modelo
07/11 - Fase 1 terminada ⏸ Pausado —
Fase 1 → Gate 4 ▶ Reanudado DC limpio
Gate 4 → Gate Final ▶ Activo Modelo ganador
Gate Final ⏸ Decisión —

3. Timeline consolidado
   Semana Fecha Fase Entregable principal Gate
   S1 07-13/11 Fase 0 + inicio Fase 1 Contrato de datos + tests invariancia Gate 0
   S2 14-20/11 Fase 1 + Fase 2 Backtest limpio + liquidaciones Gate 1, Gate 2
   S3 21-27/11 Fase 3 Backtest temporal reproducible Gate 3 (crítico)
   S4 28/11-04/12 Fase 4 Viabilidad ML Gate 4 (crítico)
   S5 05-11/12 Fase 5 + inicio Fase 6 Ensemble + primeros mercados Gate 5
   S6 12-18/12 Fase 6 Integración dashboard + alertas Gate 6
   S7-S8 19/12-01/01 Paper trading final n ≥ 30 por liga Gate Final
   Estimación total: 8 semanas. Con margen hasta 08/01/2027.

4. Fases
   FASE 0 — Contrato de datos y reproducción de la base
   Duración estimada: 4-6h (S1)
   Objetivo: garantizar que los datos que consume el pipeline son únicos, trazables y reproducibles.
   Tareas:
5. Unificar ruta y esquema de histórico: data/processed/history_with_xg.parquet es la fuente única de verdad.
6. Verificar timestamps UTC en columna date (sin naive, sin duplicados de zona horaria).
7. Verificar match_id única por partido (sin duplicados por nombre de equipo).
8. Verificar que el refresco diario actualiza lo consumido por send_alerts.py (no otro archivo).
9. Persistir metadatos de cuota: fuente (Pinnacle, Avg, B365), mercado (h2h, ou25), timestamp de captura.
10. Generar reporte reproducible de cobertura por liga, temporada y campo (con script scripts/data_coverage_report.py).
    Entregables:
    • docs/data_contract.md con el esquema definitivo.
    • scripts/data_coverage_report.py que genera output/coverage_report_YYYYMMDD.csv.
    • Verificación de que daily_run.py actualiza la fuente correcta.
    ✅ Criterio de terminado (del roadmap técnico):
    • La ejecución diaria deja registrada la fecha máxima nueva.
    • No duplica partidos al repetirse.
    • Cada cuota queda vinculada a evento, mercado, casa y hora de captura.
    • Reporte reproducible de cobertura por liga, temporada y campo.
    🚦 Gate 0:
    Escenario Acción
    Todos los puntos del criterio se cumplen ✅ Avanzar a Fase 1
    Alguno falla ⚠️ Iterar Fase 0 hasta cumplirlo
    Imposible con las fuentes actuales 🚨 Documentar limitación, evaluar fuente alternativa, o aceptar y ajustar expectativas de Fase 1
    ⚠️ Contingencia:
    • Si Pinnacle (PSCD) no existe para 2026-27, usar AvgCD como cierre documentando que CLV es solo indicativo.
    • Si hay partidos sin match_id, generarlo determinísticamente con hash(liga + fecha + local + visitante).

FASE 1 — Corrección estadística y prevención de fugas
Duración estimada: 8-10h (S1-S2)
Objetivo: garantizar que Dixon-Coles es matemáticamente correcto y no hay data leakage.
Tareas:

1. Corregir filtros as_of: verificar que enrich_fixture con as_of_date no usa partidos futuros.
2. Ratings por competición: verificar que compute_ratings_for_team no mezcla partidos de distintas ligas.
3. Estimación de rho solo con datos de train: reemplazar rho = -0.13 hardcoded por estimate_rho(train_df).
4. Ajuste de ventaja local dinámico: calcular HOME_ADVANTAGE por temporada desde el histórico.
5. Precisión de la matriz: verificar que suma 1.0, no negativa, clipping de lambdas correcto.
6. Pruebas de invariancia temporal: agregar resultados posteriores no debe cambiar predicciones históricas.
   Entregables:
   • tests/test_dixon_coles_math.py (16 tests matemáticos).
   • tests/test_temporal_invariance.py (test de invariancia).
   • src/config.py con LEAGUE_PARAMS (rho, home_adv, decay por liga).
   • scripts/send_alerts.py usando estimate_rho() walk-forward.
   • docs/baseline_clean.md con parámetros óptimos y backtest limpio.
   • output/baseline_clean_YYYYMMDD.csv (backtest reproducible).
   ✅ Criterio de terminado (del roadmap técnico):
   • Agregar resultados posteriores no cambia ninguna predicción histórica.
   • Los lambdas y probabilidades son finitos y no negativos.
   • La matriz suma 1 dentro de tolerancia.
   • Las probabilidades de mercados son coherentes entre sí.
   • Las excepciones/skips del backtest se contabilizan, no desaparecen silenciosamente.
   🚦 Gate 1:
   Escenario Acción
   Todos los tests pasan + backtest limpio reproducible ✅ Avanzar a Fase 2
   Algún test falla ⚠️ Diagnosticar y arreglar antes de Fase 2
   Data leakage estructural imposible de eliminar 🚨 Parar y rediseñar el pipeline de features
   ⚠️ Contingencia:
   • Si HOME_ADVANTAGE dinámico empeora el backtest vs fijo, mantener el fijo pero documentar por qué.
   • Si estimate_rho es muy lento (>5 min por temporada), cachear el resultado por liga-temporada.

FASE 2 — Cuotas, EV y liquidación
Duración estimada: 8-10h (S2)
Objetivo: garantizar que las cuotas y liquidaciones son correctas antes de añadir mercados.
Tareas:

1. Persistir fuente real de apertura/cierre: columna odds_source en alerts_history.csv (Pinnacle, Avg, B365).
2. Desvig para comparación de mercado: eliminar overround al comparar probabilidades modelo vs cuotas.
3. Validación de cuota y probabilidad: verificar que 1 ≤ cuota ≤ 100 y 0 ≤ prob ≤ 1.
4. Política de stake única: fijar stake base (1 unidad) y Kelly fraccionado (0.25x).
5. Implementar liquidaciones antes de añadir DNB/AH:
   o 1X2 (sin push, sin media)
   o O/U 2.5 (sin push)
   o BTTS (sin push)
   o AH asiático (con push y medias liquidaciones)
6. CLV solo para precios comparables (misma casa, misma fuente, misma línea).
   Entregables:
   • src/markets.py con funciones de liquidación por mercado.
   • tests/test_settlement.py con casos: win, loss, push, half-win, half-loss.
   • src/alerts_logger.py con columnas odds_source, stake, clv_source.
   • scripts/update_clv_history.py actualizado con lógica de comparabilidad.
   ✅ Criterio de terminado (del roadmap técnico):
   • Las pruebas cubren todos los casos de liquidación (incluyendo push y medias liquidaciones).
   • Cada apuesta se puede reconstruir desde el precio original.
   • CLV solo se calcula para precios comparables de la misma casa/fuente/línea.
   🚦 Gate 2:
   Escenario Acción
   Todos los tests de liquidación pasan + CLV comparable ✅ Avanzar a Fase 3
   Liquidaciones parciales incompletas ⚠️ Completar antes de Fase 3
   No hay fuente de cuotas comparables 🚨 Aceptar limitación, documentar, no usar CLV como criterio de decisión
   ⚠️ Contingencia:
   • Si Pinnacle no existe para 2026-27, usar AvgCD como cierre con clv_source="Avg" y documentar que el CLV es indicativo, no concluyente.
   • Si no se puede verificar la hora de captura de las cuotas, marcarlas como clv_unreliable=True.

FASE 3 — Backtest temporal fiable
Duración estimada: 10-12h (S3) — CRÍTICO
Objetivo: backtest honesto que compare Dixon-Coles, Poisson y mercado en folds temporales.
Tareas:

1. Ampliar evaluación existente a predicción rolling por fecha o jornada (no por temporada entera).
2. Comparar Dixon-Coles, Poisson y referencia de mercado (probabilidades implícitas de cuotas).
3. Fijar filtros en una etapa de validación distinta de la evaluación final.
4. Reportar métricas completas:
   o Log Loss 1X2
   o Brier Score
   o Log Loss de goles
   o Calibración de probabilidades (reliability curve)
   o ROI
   o Yield
   o CLV
   o Número de apuestas
   o Variabilidad por temporada y liga
   Entregables:
   • scripts/compare_models.py con comparativa DC/Poisson/Mercado.
   • scripts/optimize_filters_v2.py con validación separada.
   • docs/backtest_temporal.md con todos los resultados.
   • output/backtest_rolling_YYYYMMDD.csv reproducible.
   ✅ Criterio de terminado (del roadmap técnico):
   • Cada predicción usa únicamente información disponible antes del kickoff.
   • Una ejecución reproduce el mismo CSV de predicciones/métricas.
   • La estrategia se evalúa en periodos no usados para seleccionar umbrales.
   🚦 Gate 3 — CRÍTICO:
   Este es el gate que decide si merece la pena seguir.
   Escenario Acción
   DC bate a Poisson en Brier/LogLoss Y yield > 0% en ≥3 ligas con n ≥ 30 ✅ Avanzar a Fase 4 (ML como viabilidad)
   DC bate a Poisson pero yield ~0% en todas ⚠️ Avanzar a Fase 4 con expectativas bajas
   DC no bate a Poisson O yield negativo en todas 🚨 Reconsiderar Fase 4. ML como último intento con criterio de cierre rápido (n≥100 en backtest). Si no mejora → pivotar a dashboard.
   DC no bate ni a Poisson ni a mercado 🚨 Pivotar a dashboard sin pasar por Fase 4
   ⚠️ Contingencia:
   • Si el mercado bate a DC en todas las ligas, documentar como "no hay edge" y pivotar.
   • Si DC bate a Poisson solo en algunas ligas, evaluar por liga (tiering).

FASE 4 — Probar viabilidad de ML
Duración estimada: 16-20h (S4)
Objetivo: probar si LightGBM mejora Dixon-Coles. No asumir que lo hará.
Tareas:

1. Construir features prepartido auditables:
   o Elo de ambos equipos
   o xG/xGA rolling (últimos 5 y 10 partidos)
   o Forma local/visitante
   o Descanso desde último partido
   o competition como categórica
2. Medir cobertura por liga de cada feature (DED y PPL no tienen xG).
3. Entrenar dos modelos independientes de goles esperados (lgbm_home, lgbm_away) con objective="poisson".
4. Comparar LGBM vs DC vs mercado en folds temporales.
   Entregables:
   • scripts/download_xg.py (descarga xG actualizado de Understat).
   • src/features.py (nuevas features auditables).
   • src/lightgbm_models.py (2 modelos).
   • docs/lightgbm_results.md con comparativa.
   ✅ Criterio de seguir (del roadmap técnico):
   • Mejora fuera de muestra en métricas probabilísticas predefinidas.
   • Estabilidad en varias temporadas.
   • Sin degradación material frente al baseline de mercado.
   • Si no supera esos controles, conservar Dixon-Coles.
   🚦 Gate 4 — CRÍTICO:
   Escenario Acción
   LGBM bate a DC en Brier en ≥4 de 7 ligas, estable entre temporadas ✅ Avanzar a Fase 5 (ensemble)
   LGBM bate a DC en 1-3 ligas ⚠️ Avanzar a Fase 5 solo con las ligas ganadas
   LGBM no bate a DC en ninguna liga 🚨 No hacer ensemble. Usar DC. Saltar a Fase 6. Documentar como "ML no mejora DC".
   ⚠️ Contingencia:
   • Si DED y PPL no tienen xG, entrenar solo para PL/BL1/PD/SA/FL1.
   • Si LGBM overfittea (train >> test), reducir hiperparámetros, aumentar regularización.

FASE 5 — Ensemble Dixon-Coles + ML
Duración estimada: 6-8h (S5)
Objetivo: combinar lo mejor de ambos modelos si mejora las métricas.
Tareas:

1. Aprender el peso del ensemble en folds internos temporales.
2. Reservar periodos externos para la comparación final.
3. Calibrar solo con predicciones out-of-fold (nunca con train).
4. Comparar ensemble vs DC vs LGBM en el holdout.
   Entregables:
   • src/ensemble.py.
   • scripts/optimize_ensemble_weight.py.
   • docs/ensemble_results.md.
   ✅ Criterio de terminado (del roadmap técnico):
   • El ensemble mejora fuera de muestra a ambos componentes O se descarta.
   • No basta con una mejora en el periodo usado para elegir el peso.
   🚦 Gate 5:
   Escenario Acción
   Ensemble mejora a DC y LGBM en holdout ✅ Avanzar con ensemble
   Ensemble empata con el mejor individual ✅ Avanzar con el individual (más simple)
   Ensemble peor que el mejor individual 🚨 Descartar ensemble. Documentar.
   ⚠️ Contingencia:
   • Si el ensemble solo mejora en el periodo de optimización pero no en el holdout, descartar.

FASE 6 — Mercados e integración
Duración estimada: 12-16h (S5-S6)
Objetivo: ampliar mercados solo si hay cuotas históricas y liquidación fiable. Integrar en dashboard y alertas.
Tareas:

1. Ampliar mercados en orden de prioridad:
   o 1X2 ✅ (ya existe)
   o Doble oportunidad
   o Draw No Bet
   o Total goles (O/U 1.5, 2.5, 3.5)
   o BTTS ✅ (ya existe)
   o AH asiático
   o (Después, si hay cobertura: tarjetas, córners, tiros)
2. Conectar predicciones versionadas con dashboard, alertas, historial y reportes.
3. Verificar que cada alerta tiene: precio, fuente, timestamp.
   Entregables:
   • src/markets.py con nuevas funciones de derivación.
   • dashboard_server.py con nuevos endpoints.
   • alerts_logger.py con model_used, market, odds_source.
   • docs/markets_comparison.md.
   ✅ Criterio de terminado (del roadmap técnico):
   • Pruebas de liquidación pasan por mercado.
   • Alertas tienen precio/fuente/timestamp.
   • La deduplicación es estable.
   • El paper trading puede reproducir resultado, yield y CLV a partir del histórico.
   🚦 Gate 6:
   Escenario Acción
   ≥3 mercados nuevos con yield > 0% validado ✅ Incluir todos
   1-2 mercados nuevos con yield > 0% ⚠️ Incluir solo los validados
   Ningún mercado nuevo validado 🚨 Mantener solo 1X2 + O/U + BTTS ya validados
   ⚠️ Contingencia:
   • Si AH no se puede liquidar correctamente sin cuotas históricas detalladas, postponerlo hasta tener datos.

4. Gate Final (tras paper trading del modelo ganador)
   Se ejecuta cuando se cumplen las 3 condiciones (sin fecha fija):
   Condición 1: Fase 4 completada
   • Comparativa de modelos documentada.
   • Modelo ganador en producción.
   Condición 2: Paper trading con n ≥ 30 por liga promovida
   • 2-4 semanas de ejecución (19/12 - 08/01 estimado).
   • Al menos 30 alertas con resultado por liga promovida.
   Condición 3: Métricas del paper trading confirman el backtest
   • Hit rate ≥ 27% (baseline del fútbol)
   • Yield > 0% en las ligas promovidas
   • Brier < 0.65 (mejor que azar)
   • CLV positivo (si es medible con datos consistentes)

Decisión final:
Escenario Acción
Yield > +5% en ≥5 de 7 ligas ✅ Dinero real con stakes 0.5u
Yield > +5% solo en PL+BL1 ✅ Mantener tiering, dinero real solo en PL+BL1
Yield entre 0% y +5% en PL+BL1 ⚠️ Extender paper trading 4 semanas más. Si sigue igual → dashboard.
Yield negativo en todas 🚨 Pivotar a dashboard informativo (NO cierre del proyecto)

---

6. Trabajo paralelizable (del roadmap técnico)
   Tras acordar el contrato común de partido y cuotas (Fase 0), se pueden avanzar en paralelo:
   • Reparación de ingesta/histórico y archivo de cuotas.
   • Pruebas de liquidación y diseño de métricas.
   • Dashboard y alertas pueden adaptarse en paralelo una vez fijado el formato de predicción.
   Lo que NO se paraleliza:
   • Ajuste de ML y ensemble no deberían adelantarse a las fases de datos y backtest.
   • Fase 4 (ML) no empieza hasta que Fase 3 (backtest fiable) esté cerrada.

7. Reglas de contingencia globales
   Si una fase se retrasa
   • No comprimir las siguientes. Mejor extender 1 semana que saltarse una validación.
   • Comunicar el retraso, no ocultarlo.
   Si un criterio de salida no se cumple
   • Iterar la fase. No avanzar con datos incompletos.
   • Si tras 2 iteraciones no se cumple → Gate de emergencia: evaluar si la fase es viable o si hay que pivotar el enfoque.
   Si Fase 1 es peor que el baseline contaminado
   • Buena noticia disfrazada: ahora sabes la verdad.
   • Decisión: continuar a Fase 2-3, pero con expectativas realistas.
   • Nunca volver al baseline contaminado para "tener números mejores".
   Si Fase 3 (gate crítico) muestra que DC no tiene edge
   • No saltar a Fase 4 con optimismo ciego. Fase 4 es el último intento, con criterio de cierre rápido (n≥100).
   • Si LGBM no mejora → pivotar a dashboard sin pasar por Fase 5-6.
   Si Fase 4 (gate crítico) muestra que LGBM no mejora DC
   • Conservar DC. El roadmap técnico es explícito: "Si no supera esos controles, conservar Dixon-Coles."
   Si el modelo no supera el azar en Fase 4
   • Pivotar a dashboard informativo sin Fase 5-6.
   • Documentar como "negative result" en docs/findings.md.

8. Calendario consolidado
   Semana Fecha Fase Esfuerzo Gate
   S1 07-13/11 Fase 0 + inicio Fase 1 12-16h Gate 0
   S2 14-20/11 Cierre Fase 1 + Fase 2 10-12h Gate 1, Gate 2
   S3 21-27/11 Fase 3 10-12h Gate 3 (crítico)
   S4 28/11-04/12 Fase 4 16-20h Gate 4 (crítico)
   S5 05-11/12 Fase 5 + inicio Fase 6 12-14h Gate 5
   S6 12-18/12 Fase 6 12-16h Gate 6
   S7-S8 19/12-01/01 Paper trading final 2-4 semanas Gate Final
   Estimación total: 8 semanas. Con margen hasta 08/01/2027.

9. Documentos de referencia
   Documento Fase Contenido
   docs/roadmap.md Ahora Este documento
   docs/data_contract.md Fase 0 Esquema definitivo de datos
   docs/baseline_clean.md Fase 1 Parámetros óptimos, backtest limpio
   docs/backtest_temporal.md Fase 3 Comparativa DC vs Poisson vs mercado
   docs/lightgbm_results.md Fase 4 Comparativa DC vs LGBM
   docs/ensemble_results.md Fase 5 Comparativa ensemble
   docs/markets_comparison.md Fase 6 Mercados validados
   docs/findings.md Continuo Hallazgos, negative results, decisiones

10. Checklist de inicio de Fase 0 (hoy, 07/11)
    □ git status → working tree clean
    □ git log --oneline -3 → último commit docs: parcial paper trading 2026-11-07
    □ Backup creado en \_baseline_pre_fase1/
    □ \_baseline_pre_fase1/ añadido a .gitignore
    □ Paper trading pausado (no ejecutar daily_run.py durante Fase 0-1)
    □ docs/roadmap.md guardado (este documento)
    □ Comenzar Fase 0: auditoría del contrato de datos actual

11. Regla de oro final
    Si en algún momento sientes la tentación de saltarte un criterio de salida "porque los números van bien", recuerda: los números con duplicados también iban "bien" (+16.68% yield) y resultaron ser -33.77% con datos limpios. La disciplina de los criterios es la única protección contra el sesgo de confirmación.
    Y si el resultado final es "no hay edge", el proyecto no fracasa: pivota a dashboard informativo. Documentar un negative result es más valioso que seguir apostando dinero real en algo que no funciona.
