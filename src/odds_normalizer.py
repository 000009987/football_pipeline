"""
odds_normalizer.py
Normaliza las respuestas JSON de The Odds API al formato que consume BET_MAP.
"""

import re
import unicodedata
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

TEAM_SYNONYMS = {
    "munchen": "munich",
    "münchen": "munich",
    "roma": "as roma",
    "inter": "inter milan",
    "internazionale": "inter milan",
    "athletic": "athletic bilbao",
    "atletico": "atletico madrid",
}


def normalize_string(name: str) -> str:
    """Elimina acentos, diacríticos y prefijos/sufijos comunes."""
    if not name:
        return ""
    s = name.lower()
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    s = re.sub(r"\b(fc|cf|sc|afc|cd|ud|rcd|vfb|fsv|tsv|rb|us|ss|ac|as)\b", "", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    words = s.split()
    normalized_words = [TEAM_SYNONYMS.get(w, w) for w in words]
    return " ".join(normalized_words)


def match_teams(team_a: str, team_b: str) -> bool:
    """Compara si dos nombres de equipos corresponden al mismo club."""
    norm_a = normalize_string(team_a)
    norm_b = normalize_string(team_b)
    if norm_a == norm_b:
        return True
    if len(norm_a) > 3 and len(norm_b) > 3:
        if norm_a in norm_b or norm_b in norm_a:
            return True
    return False


def normalize_odds_api_response(
    event_data: Dict[str, Any],
    home_team: str,
    away_team: str,
    preferred_bookmaker: str = "onexbet"
) -> Dict[str, float]:
    """
    Toma un evento de The Odds API y extrae las cuotas para BET_MAP:
    {'1': float, 'X': float, '2': float, 'O2.5': float, 'U2.5': float}
    """
    normalized_odds = {}
    bookmakers = event_data.get("bookmakers", [])
    if not bookmakers:
        return normalized_odds

    # Buscar la casa de apuestas preferida o usar la primera disponible
    selected_bk = None
    for bk in bookmakers:
        if bk.get("key", "").lower() == preferred_bookmaker.lower():
            selected_bk = bk
            break
    if not selected_bk and bookmakers:
        selected_bk = bookmakers[0]

    api_home = event_data.get("home_team", "")
    api_away = event_data.get("away_team", "")

    for market in selected_bk.get("markets", []):
        m_key = market.get("key")
        outcomes = market.get("outcomes", [])

        # 1. Ganador del Partido (h2h)
        if m_key == "h2h":
            for o in outcomes:
                name = o.get("name")
                price = float(o.get("price", 0.0))
                if price <= 1.0:
                    continue

                if name == "Draw":
                    normalized_odds["X"] = price
                elif match_teams(name, api_home):
                    normalized_odds["1"] = price
                elif match_teams(name, api_away):
                    normalized_odds["2"] = price

        # 2. Totales Over/Under (totals)
        elif m_key == "totals":
            for o in outcomes:
                name = o.get("name")      # 'Over' o 'Under'
                point = o.get("point")    # e.g. 2.5
                price = float(o.get("price", 0.0))
                if price <= 1.0 or point is None:
                    continue

                direction = "O" if name.lower() == "over" else "U"
                key = f"{direction}{point}"
                normalized_odds[key] = price

    return normalized_odds