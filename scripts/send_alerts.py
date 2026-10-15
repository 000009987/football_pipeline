import sys
from pathlib import Path

# Añadir la raíz al sys.path
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
    EVAL_LEAGUES,
    DEFAULT_RHO,
)
from src.evaluation import walk_forward_markets
from src.evaluation_helpers import calculate_ev, apply_production_draw_filters
from src.logger import get_logger

logger = get_logger("send_alerts")


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


def run_draw_alerts(max_alerts: int = 5):
    """Carga los partidos, genera predicciones y envía un máximo de alertas recientes."""
    file_path = UPCOMING_PARQUET if UPCOMING_PARQUET.exists() else HISTORY_PARQUET
    if not file_path.exists():
        logger.error(f"No se encontró archivo de datos en {file_path}")
        return

    logger.info(f"Cargando partidos desde: {file_path.name}")
    df = pd.read_parquet(file_path)

    odds_col = next((c for c in ["odds_draw", "odds_D", "PSD", "AvgD", "B365D"] if c in df.columns), None)
    if not odds_col:
        logger.error("No se encontró la columna de cuota de empate.")
        return

    if "prob_D" not in df.columns and "prob_draw" not in df.columns:
        logger.info("Calculando probabilidades del modelo con Walk-Forward...")
        seasons = sorted(df["season"].unique()) if "season" in df.columns else [2025]
        comp_col = "competition" if "competition" in df.columns else "league"
        leagues = [l for l in df[comp_col].unique() if pd.notna(l) and l in EVAL_LEAGUES] if comp_col in df.columns else EVAL_LEAGUES

        all_preds = []
        for league in leagues:
            try:
                preds = walk_forward_markets(df, seasons=seasons, competition=str(league), rho=DEFAULT_RHO)
                if preds is not None and not preds.empty:
                    preds["league"] = league
                    all_preds.append(preds)
            except Exception as e:
                logger.error(f"Error prediciendo ligas {league}: {e}")

        if not all_preds:
            logger.warning("No se pudieron generar predicciones.")
            return

        preds_df = pd.concat(all_preds, ignore_index=True)
        merge_keys = [k for k in ["season", "date", "home_team", "away_team"] if k in preds_df.columns and k in df.columns]
        df_temp = df.copy()
        for key in merge_keys:
            preds_df[key] = preds_df[key].astype(str)
            df_temp[key] = df_temp[key].astype(str)

        data = preds_df.merge(df_temp[merge_keys + [odds_col]].drop_duplicates(), on=merge_keys, how="left") if odds_col not in preds_df.columns else preds_df
    else:
        data = df.copy()
        if "prob_draw" in data.columns and "prob_D" not in data.columns:
            data["prob_D"] = data["prob_draw"]

    data["odds"] = data[odds_col]
    data["ev"] = calculate_ev(data["prob_D"], data["odds"])
    data = data.dropna(subset=["ev", "odds"]).copy()

    # Aplicar filtro de producción
    alerts_df = apply_production_draw_filters(data)

    if alerts_df.empty:
        logger.info("No hay partidos que cumplan el criterio de alerta.")
        return

    if "date" in alerts_df.columns:
        alerts_df = alerts_df.sort_values(by="date", ascending=False)
    
    alerts_to_send = alerts_df.head(max_alerts)
    logger.info(f"Enviando {len(alerts_to_send)} alertas a Telegram (límite: {max_alerts})...")

    for _, row in alerts_to_send.iterrows():
        league = row.get("league", row.get("competition", "N/A"))
        home = row.get("home_team", "Local")
        away = row.get("away_team", "Visitante")
        prob_d = row.get("prob_D", 0.0) * 100
        odds = row.get("odds", 0.0)
        ev = row.get("ev", 0.0) * 100
        date = str(row.get("date", "Por definir"))[:10]

        # Formato claro y explícito del Pick
        msg = (
            f"🎯 *ALERTA DE VALOR DE PRODUCCIÓN*\n\n"
            f"🏆 *Liga:* {league}\n"
            f"📅 *Fecha:* {date}\n"
            f"⚔️ *Partido:* {home} vs {away}\n"
            f"📌 *PICK:* Empate (X)\n"
            f"💰 *Stake Sugerido:* 1 Unidad\n\n"
            f"📊 *Prob. Modelo:* {prob_d:.1f}%\n"
            f"📈 *Cuota:* {odds:.2f}\n"
            f"💡 *EV Calculado:* +{ev:.1f}%\n\n"
            f"⚠️ *Filtro:* EV ≥ {DRAW_FILTER_CONFIG['ev_min']*100:.0f}% | Cuota ≤ {DRAW_FILTER_CONFIG['max_odds']:.2f}"
        )

        if send_telegram_message(msg):
            logger.info(f"Alerta enviada: {home} vs {away}")
            time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        logger.info("Enviando mensaje de prueba a Telegram...")
        if send_telegram_message("🤖 *Bot 1X2 Draw*: Conexión activa y lista para emitir señales."):
            logger.info("Mensaje de prueba enviado con éxito.")
    else:
        run_draw_alerts(max_alerts=3)