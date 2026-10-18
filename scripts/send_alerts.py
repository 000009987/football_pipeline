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
)
from src.feature_engineering import enrich_fixture
from src.models import predict_match
from src.evaluation_helpers import (
    calculate_ev,
    apply_production_draw_filters,
    apply_relaxed_draw_filters,
)
from src.alerts_logger import log_alert
from src.logger import get_logger

logger = get_logger("send_alerts")

# ─── Ligas con edge validado (solo aquí el tag dirá "VALIDADO") ──────
VALIDATED_LEAGUES = ["PL", "BL1"]


def send_telegram_message(message: str) -> bool:
    """Envía un mensaje formateado a Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Credenciales de Telegram no configuradas en .env")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        logger.error(f"Error de Telegram API ({response.status_code}): {response.text}")
        return False
    except Exception as e:
        logger.error(f"Excepción al conectar con Telegram: {e}")
        return False


def compute_live_predictions(
    upcoming_df: pd.DataFrame,
    history_df: pd.DataFrame,
    rho: float,
) -> pd.DataFrame:
    """Calcula P(D) para cada partido futuro usando el histórico como train."""
    rows = []
    for _, row in upcoming_df.iterrows():
        try:
            f = enrich_fixture(row, history_df, as_of_date=row["date"])
            p = predict_match(
                f["lambda_home"], f["lambda_away"], rho=rho, model="dixon_coles"
            )
            rows.append({
                "competition": row["competition"],
                "date": row["date"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "prob_D": p["prob_draw"],
                "odds": row["odds_draw"],
            })
        except Exception as e:
            logger.warning(
                f"Error prediciendo {row.get('home_team')} vs "
                f"{row.get('away_team')}: {e}"
            )
    return pd.DataFrame(rows)


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

    if upcoming.empty:
        logger.warning("Sin partidos futuros.")
        return
    if upcoming["odds_draw"].isna().all():
        logger.warning("Ningún partido tiene cuota de empate.")
        return

    logger.info(f"Calculando predicciones live ({len(upcoming)} partidos)...")
    data = compute_live_predictions(upcoming, history, rho=DEFAULT_RHO)

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
    all_alerts.sort(key=lambda x: x[0]["ev"], reverse=True)

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
            f"💡 *EV Calculado:* +{ev:.1f}%\n\n"
            f"🏷️ *{tag}*"
        )

        if send_telegram_message(msg):
            logger.info(f"Alerta enviada: {home} vs {away} ({league}) [{tier}]")
            log_alert({
                "competition": league,
                "match_date": date,
                "home_team": home,
                "away_team": away,
                "prob_D": row["prob_D"],
                "odds_open": odds,
                "ev": row["ev"],
                "tier": tier,
                "is_validated": int(is_validated),
            })
            time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        logger.info("Enviando mensaje de prueba a Telegram...")
        if send_telegram_message(
            "🤖 *Bot 1X2 Draw*: Conexión activa y lista para emitir señales."
        ):
            logger.info("Mensaje de prueba enviado con éxito.")
    else:
        run_draw_alerts(max_alerts=3)