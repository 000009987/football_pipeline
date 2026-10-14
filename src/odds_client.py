"""
odds_client.py
Cliente HTTP para The Odds API (v4).
"""

import time
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import ODDS_API_KEY, ODDS_API_BASE_URL, ODDS_API_SPORT_KEYS


class OddsAPIClient:
    def __init__(self, api_key: str = ODDS_API_KEY):
        self.api_key = api_key
        self.base_url = ODDS_API_BASE_URL

    def fetch_odds_for_league(
        self,
        league_code: str,
        regions: str = "eu",
        markets: str = "h2h,totals"
    ) -> List[Dict[str, Any]]:
        """
        Consulta cuotas próximas de una liga en The Odds API.
        """
        sport_key = ODDS_API_SPORT_KEYS.get(league_code)
        if not sport_key:
            return []

        url = f"{self.base_url}/{sport_key}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "dateFormat": "iso",
            "oddsFormat": "decimal",
        }

        for attempt in range(3):
            try:
                resp = requests.get(url, params=params, timeout=15)
                
                remaining = resp.headers.get("x-requests-remaining")
                used = resp.headers.get("x-requests-used")
                if remaining is not None:
                    print(f"ℹ️  The Odds API créditos - Usados: {used} | Restantes: {remaining}")

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    print("⚠️ Créditos agotados o rate limit alcanzado en The Odds API.")
                    return []
                elif resp.status_code == 401:
                    print("⚠️ Error 401: API Key de The Odds API inválida o no configurada.")
                    return []
                else:
                    print(f"⚠️ Error {resp.status_code} en {url}, intento {attempt + 1}/3")
                    time.sleep(2)
            except requests.RequestException as e:
                print(f"⚠️ Excepción de red: {e}, intento {attempt + 1}/3")
                time.sleep(2)

        return []