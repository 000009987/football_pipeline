import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import main


class AnalyzeDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.predictions_path = Path(self.temp_dir.name) / "predictions.json"
        self.config_patch = patch.object(main, "OUTPUT_JSON", self.predictions_path)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_analyze_saves_every_fixture_and_prediction(self):
        fixtures = pd.DataFrame([
            {
                "match_id": 11,
                "date": pd.Timestamp("2026-10-14"),
                "competition": "PL",
                "home_team": "Team A",
                "away_team": "Team B",
            },
            {
                "match_id": 12,
                "date": pd.Timestamp("2026-10-15"),
                "competition": "PD",
                "home_team": "Team C",
                "away_team": "Team D",
            },
        ])
        prediction = {
            "prob_home": 0.5,
            "prob_draw": 0.25,
            "prob_away": 0.25,
            "over_2.5": 0.55,
            "btts_yes": 0.6,
            "exact_scores": {"1-0": 0.14},
            "model": "dixon_coles",
        }

        with (
            patch.object(main, "get_history", return_value=pd.DataFrame({"x": [1]})),
            patch.object(main, "get_rho", return_value=-0.13),
            patch.object(main, "fetch_all_upcoming", return_value=fixtures),
            patch.object(main, "enrich_fixture", side_effect=lambda fixture, history: {
                "date": str(fixture["date"].date()),
                "competition": fixture["competition"],
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "lambda_home": 1.4,
                "lambda_away": 1.1,
                "confianza": "ALTA",
                "n_partidos": 30,
            }),
            patch.object(main, "predict_match", return_value=prediction),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main.run_analyze(days_ahead=3)

        saved = json.loads(self.predictions_path.read_text(encoding="utf-8"))
        self.assertEqual(len(result), 2)
        self.assertEqual(saved["count"], 2)
        self.assertEqual([match["match_id"] for match in saved["matches"]], [11, 12])
        self.assertEqual(saved["matches"][0]["exact_scores"], {"1-0": 0.14})
        self.assertEqual(saved["days_ahead"], 3)

    def test_empty_fixture_list_replaces_stale_results(self):
        with (
            patch.object(main, "get_history", return_value=pd.DataFrame({"x": [1]})),
            patch.object(main, "get_rho", return_value=-0.13),
            patch.object(main, "fetch_all_upcoming", return_value=pd.DataFrame()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = main.run_analyze(days_ahead=2)

        saved = json.loads(self.predictions_path.read_text(encoding="utf-8"))
        self.assertTrue(result.empty)
        self.assertEqual(saved["count"], 0)
        self.assertEqual(saved["matches"], [])


if __name__ == "__main__":
    unittest.main()
