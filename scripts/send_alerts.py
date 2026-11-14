import json
import sys
from pathlib import Path

# ── sys.path ANTES de cualquier import de src ────────────────────────
sys.path.append(str(Path(__file__).resolve().parent.parent))

import time
import requests
import pandas as pd

from src.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    UPCOMING_PARQUET,
    HISTORY_PARQUET,
    DRAW_FILTER_CONFIG,
    DEFAULT_RHO,
    PRODUCTION_LEAGUES,
    OUTPUT_DIR,
)
from src.feature_engineering import enrich_fixture
from src.models import predict_match
from src.evaluation_helpers import (
    calculate_ev,
    apply_production_draw_filters,
    apply_relaxed_draw_filters,
)
from src.alerts_logger import log_alert, ALERTS_LOG
from src.logger import get_logger

logger = get_logger("send_alerts")

# ─── Ligas con edge validado (solo aquí el tag dirá "VALIDADO") ──────
VALIDATED_LEAGUES = ["PL", "BL1"]

# ─── Caché de rho por liga (generado por compute_league_rho.py) ──────
RHO_CACHE = OUTPUT_DIR / "rho_cache.json"


# ─── Telegram ────────────────────────────────────────────────────────

def send_telegram_message(message: str, max_retries: int = 3) -> bool:
    """
    Envía un mensaje formateado a Telegram con retry y backoff exponencial.

    - Timeout 20s (vs 10s antes) para redes lentas.
    - 3 reintentos con backoff 2s → 4s → 8s.
    - Reintenta solo en errores transitorios (timeout, 429, 5xx).
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Credenciales de Telegram no configuradas en .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code == 200:
                return True
            # 429 = rate limit; 5xx = error servidor Telegram
            if response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait = 2 ** attempt  # 2, 4, 8s
                logger.warning(
                    f"Telegram {response.status_code} (intento {attempt}/{max_retries}). "
                    f"Reintentando en {wait}s..."
                )
                time.sleep(wait)
                continue
            logger.error(f"Error de Telegram API ({response.status_code}): {response.text[:200]}")
            return False
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(
                    f"Telegram timeout (intento {attempt}/{max_retries}). "
                    f"Reintentando en {wait}s..."
                )
                time.sleep(wait)
                continue
            logger.error(f"Telegram timeout tras {max_retries} intentos")
            return False
        except Exception as e:
            logger.error(f"Excepción al conectar con Telegram: {e}")
            return False

    return False


# ─── Rho por liga (walk-forward con caché) ──────────────────────────

def load_rho_cache() -> dict:
    """Carga el caché de rho por liga. Si no existe, devuelve {}."""
    if not RHO_CACHE.exists():
        logger.warning(
            f"No existe {RHO_CACHE}. Usando DEFAULT_RHO={DEFAULT_RHO} para todas las ligas."
        )
        return {}
    try:
        with RHO_CACHE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        leagues = data.get("leagues", {})
        logger.info(
            f"rho cache cargado: {len(leagues)} ligas "
            f"(generado {data.get('generated_at', 'N/A')})"
        )
        return leagues
    except Exception as e:
        logger.error(f"Error cargando {RHO_CACHE}: {e}")
        return {}


def get_rho_for_league(league: str, cache: dict) -> float:
    """Devuelve rho para una liga, o DEFAULT_RHO si no está en caché."""
    if league in cache:
        return float(cache[league]["rho"])
    return DEFAULT_RHO


# ─── Predicciones live ──────────────────────────────────────────────

def compute_live_predictions(
    upcoming_df: pd.DataFrame,
    history_df: pd.DataFrame,
    rho_cache: dict,
) -> pd.DataFrame:
    """
    Calcula P(D) para cada partido futuro usando el histórico como train.

    El rho se selecciona por liga desde el caché. Si una liga no está en el
    caché, se usa DEFAULT_RHO.

    Propaga bookmaker_key, market y capture_timestamp desde upcoming_fixtures
    para que log_alert() pueda registrar la procedencia real de la cuota.
    """
    rows = []
    for _, row in upcoming_df.iterrows():
        league = row.get("competition", "")
        rho = get_rho_for_league(league, rho_cache)
        try:
            history_league = history_df[history_df["competition"] == league]
            f = enrich_fixture(row, history_league, as_of_date=row["date"])
            p = predict_match(
                f["lambda_home"], f["lambda_away"], rho=rho, model="dixon_coles"
            )
            rows.append({
                "competition": league,
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "prob_D": p["prob_draw"],
                "odds": row["odds_draw"],
                "bookmaker_key": row.get("bookmaker_key", "unknown"),
                "market": row.get("market", "h2h"),
                "capture_timestamp": row.get("capture_timestamp", ""),
            })
        except Exception as e:
            logger.warning(
                f"Error prediciendo {row.get('home_team')} vs "
                f"{row.get('away_team')}: {e}"
            )
    return pd.DataFrame(rows)


# ─── Pipeline principal ─────────────────────────────────────────────

def run_draw_alerts(max_alerts: int = 5):
    if not UPCOMING_PARQUET.exists():
        logger.error(
            f"No existe {UPCOMING_PARQUET}. "
            f"Ejecuta `python scripts/fetch_upcoming.py` primero."
        )
        return
    if not HISTORY_PARQUET.exists():
        logger.error(f"No existe {HISTORY_PARQUET}. No hay histórico para entrenar.")
        return

    logger.info(f"Cargando fixtures desde: {UPCOMING_PARQUET.name}")
    upcoming = pd.read_parquet(UPCOMING_PARQUET)
    logger.info(f"Cargando histórico desde: {HISTORY_PARQUET.name}")
    history = pd.read_parquet(HISTORY_PARQUET)

    # ── Normalizar fechas a naive UTC (consistencia con baseline_clean) ──
    # history_with_xg.parquet está como datetime64[ns, UTC] desde Fase 1.
    # upcoming_fixtures.parquet está como datetime64[ns] (naive UTC).
    # enrich_fixture compara as_of_date con history["date"], así que ambos
    # deben estar en el mismo formato para evitar:
    #   "Invalid comparison between dtype=datetime64[ns, UTC] and Timestamp"
    history["date"] = pd.to_datetime(history["date"]).dt.tz_localize(None)
    upcoming["date"] = pd.to_datetime(upcoming["date"]).dt.tz_localize(None)

    if upcoming.empty:
        logger.warning("Sin partidos futuros.")
        return
    if upcoming["odds_draw"].isna().all():
        logger.warning("Ningún partido tiene cuota de empate.")
        return

    # Distribución de bookmakers (transparencia)
    if "bookmaker_key" in upcoming.columns:
        bm_dist = upcoming["bookmaker_key"].value_counts().to_dict()
        logger.info(f"Bookmakers en upcoming: {bm_dist}")

    # Cargar caché de rho una sola vez
    rho_cache = load_rho_cache()
    if rho_cache:
        for liga, info in rho_cache.items():
            logger.info(
                f"  rho[{liga}] = {info['rho']:+.4f} "
                f"(n={info['n_matches']}, status={info['status']})"
            )

    logger.info(f"Calculando predicciones live ({len(upcoming)} partidos)...")
    data = compute_live_predictions(upcoming, history, rho_cache)

    if data.empty:
        logger.warning("No se pudo predecir ningún partido.")
        return

    data["ev"] = calculate_ev(data["prob_D"], data["odds"])
    data = data.dropna(subset=["ev", "odds", "prob_D"]).copy()
    logger.info(f"Predicciones válidas: {len(data)}")

    # ── Filtro ESTRICTO (PICK) ───────────────────────────────────────
    picks_df = apply_production_draw_filters(data)
    logger.info(f"PICKs (EV>=8%, odds<=3.80): {len(picks_df)}")

    # ── Filtro RELAJADO (INFO) ───────────────────────────────────────
    relaxed_df = apply_relaxed_draw_filters(data)
    if not picks_df.empty and not relaxed_df.empty:
        pick_keys = set(zip(picks_df["home_team"], picks_df["away_team"]))
        relaxed_df = relaxed_df[
            ~relaxed_df.apply(
                lambda r: (r["home_team"], r["away_team"]) in pick_keys, axis=1
            )
        ]
    logger.info(f"INFOs (EV>=8%, odds<=5.50): {len(relaxed_df)}")

    if picks_df.empty and relaxed_df.empty:
        logger.info("Sin alertas hoy: ningún partido con EV alto y cuota razonable.")
        return

    # ── Combinar y ordenar por EV descendente ────────────────────────
    all_alerts = []
    for _, row in picks_df.iterrows():
        all_alerts.append((row, "PICK"))
    for _, row in relaxed_df.iterrows():
        all_alerts.append((row, "INFO"))
    # Prioridad: PICKs primero, luego INFOs; dentro de cada tier por EV desc
    all_alerts.sort(key=lambda x: (0 if x[1] == "PICK" else 1, -x[0]["ev"]))

    alerts_to_send = all_alerts[:max_alerts]
    logger.info(
        f"Enviando {len(alerts_to_send)} alertas a Telegram "
        f"(límite: {max_alerts})..."
    )

    for row, tier in alerts_to_send:
        league = row.get("competition", "N/A")
        home = row.get("home_team", "Local")
        away = row.get("away_team", "Visitante")
        prob_d = row["prob_D"] * 100
        odds = row["odds"]
        ev = row["ev"] * 100
        date = str(row.get("date", "Por definir"))[:10]
        bookmaker = row.get("bookmaker_key", "unknown")
        market = row.get("market", "h2h")
        capture_ts = row.get("capture_timestamp", "")

        # ── Comprobar duplicado ─────────────────────────────────────
        if ALERTS_LOG.exists():
            _existing = pd.read_csv(ALERTS_LOG)
            _dup = _existing[
                (_existing["home_team"] == home)
                & (_existing["away_team"] == away)
                & (_existing["match_date"] == date)
            ]
            if len(_dup) > 0:
                logger.info(f"Saltando duplicado: {home} vs {away} ({date})")
                continue

        is_pick = (tier == "PICK")
        is_validated = league in VALIDATED_LEAGUES

        if is_pick and is_validated:
            prefix = "📌 PICK VALIDADO"
            stake = "1 Unidad"
            tag = f"✅ Liga {league} validada (edge confirmado)"
        elif is_pick:
            prefix = "📌 PICK (sin validar)"
            stake = "1 Unidad"
            tag = f"⚠️ Liga {league} sin edge validado — backtest negativo"
        else:
            prefix = "🔍 INFO (cuota alta)"
            stake = "0 (solo track)"
            tag = (
                f"⚠️ Cuota {odds:.2f} > 3.80 — backtest no respalda, "
                "solo registro"
            )

        msg = (
            f"🎯 *ALERTA DE VALOR DE PRODUCCIÓN*\n\n"
            f"🏆 *Liga:* {league}\n"
            f"📅 *Fecha:* {date}\n"
            f"⚔️ *Partido:* {home} vs {away}\n"
            f"*{prefix}:* Empate (X)\n"
            f"💰 *Stake Sugerido:* {stake}\n\n"
            f"📊 *Prob. Modelo:* {prob_d:.1f}%\n"
            f"📈 *Cuota:* {odds:.2f}\n"
            f"💡 *EV Calculado:* +{ev:.1f}%\n"
            f"🏦 *Bookmaker:* {bookmaker}\n\n"
            f"🏷️ *{tag}*"
        )

        # ── Enviar a Telegram con retry interno (3 intentos, backoff 2/4/8s)
        telegram_ok = send_telegram_message(msg)
        if telegram_ok:
            logger.info(
                f"Alerta enviada: {home} vs {away} ({league}) "
                f"[{tier}] [{bookmaker}]"
            )
        else:
            logger.warning(
                f"Alerta NO enviada a Telegram (registrada igualmente): "
                f"{home} vs {away} ({league}) [{tier}] [{bookmaker}]"
            )

        # ── Registrar SIEMPRE en alerts_history.csv (paper trading honesto)
        # Aunque Telegram falle, la alerta se acumula para el análisis de Fase 3.
        log_alert({
            "competition": league,
            "match_date": date,
            "home_team": home,
            "away_team": away,
            "prob_D": row["prob_D"],
            "odds_open": odds,
            "odds_source": bookmaker,
            "market": market,
            "capture_timestamp": capture_ts,
            "ev": row["ev"],
            "tier": tier,
            "is_validated": int(is_validated),
        })

        # ── Sleep más largo entre mensajes (2s) para evitar rate limiting.
        # Telegram permite ~1 msg/seg por chat, pero bots nuevos necesitan margen.
        time.sleep(2)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        logger.info("Enviando mensaje de prueba a Telegram...")
        if send_telegram_message(
            "🤖 *Bot 1X2 Draw*: Conexión activa y lista para emitir señales."
        ):
            logger.info("Mensaje de prueba enviado con éxito.")
    else:
        run_draw_alerts(max_alerts=5)