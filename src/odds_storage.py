"""
odds_storage.py
Persistencia de snapshots históricos de cuotas en SQLite.
Garantiza auditoría inmutable de cuotas, marcas de tiempo y auditoría de respuesta.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ODDS_DB_PATH

ROOT_DIR = Path(__file__).parent.parent
DB_FILE = ROOT_DIR / ODDS_DB_PATH


def init_db():
    """Inicializa la tabla odds_snapshots en SQLite si no existe."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS odds_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            internal_match_id TEXT,
            api_football_fixture_id INTEGER,
            competition TEXT,
            home_team TEXT,
            away_team TEXT,
            bookmaker TEXT,
            market TEXT,
            selection TEXT,
            line REAL,
            odd REAL,
            captured_at TEXT,
            provider_updated_at TEXT,
            raw_response TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_odds_snapshot(
    internal_match_id: str,
    api_football_fixture_id: int,
    competition: str,
    home_team: str,
    away_team: str,
    bookmaker: str,
    normalized_odds: Dict[str, float],
    provider_updated_at: str,
    raw_response: Optional[Dict[str, Any]] = None
):
    """Guarda las cuotas capturadas en una nueva fila por selección sin sobrescribir existentes."""
    init_db()
    captured_at = datetime.now(timezone.utc).isoformat()
    raw_str = json.dumps(raw_response) if raw_response else ""

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    rows_to_insert = []
    for bet_key, odd in normalized_odds.items():
        market = "1X2" if bet_key in ["1", "X", "2"] else ("OU" if bet_key.startswith(("O", "U")) else "BTTS")
        line = None
        if market == "OU":
            try:
                line = float(bet_key[1:])
            except ValueError:
                line = None

        rows_to_insert.append((
            internal_match_id,
            api_football_fixture_id,
            competition,
            home_team,
            away_team,
            bookmaker,
            market,
            bet_key,
            line,
            odd,
            captured_at,
            provider_updated_at,
            raw_str
        ))

    cursor.executemany("""
        INSERT INTO odds_snapshots (
            internal_match_id, api_football_fixture_id, competition,
            home_team, away_team, bookmaker, market, selection,
            line, odd, captured_at, provider_updated_at, raw_response
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows_to_insert)

    conn.commit()
    conn.close()


def get_latest_stored_odds(home_team: str, away_team: str, max_age_hours: int = 24) -> Optional[Dict[str, float]]:
    """Recupera el último snapshot válido almacenado para un partido dado."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT selection, odd, captured_at
        FROM odds_snapshots
        WHERE home_team = ? AND away_team = ?
        ORDER BY captured_at DESC
    """, (home_team, away_team))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return None

    # Verificar antigüedad del snapshot más reciente
    latest_captured_str = rows[0][2]
    try:
        latest_dt = datetime.fromisoformat(latest_captured_str)
        age_hours = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 3600.0
        if age_hours > max_age_hours:
            return None
    except Exception:
        pass

    latest_odds = {}
    target_captured_at = rows[0][2]
    for row in rows:
        selection, odd, captured_at = row
        if captured_at == target_captured_at:
            latest_odds[selection] = odd

    return latest_odds if latest_odds else None