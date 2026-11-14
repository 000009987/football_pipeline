import os

import pandas as pd

from scripts import daily_run, send_alerts


def test_alerts_stop_when_raw_history_is_newer(tmp_path, monkeypatch):
    upcoming = tmp_path / "upcoming.parquet"
    raw = tmp_path / "history.parquet"
    enriched = tmp_path / "history_with_xg.parquet"
    upcoming.touch()
    raw.touch()
    enriched.touch()
    os.utime(enriched, (100, 100))
    os.utime(raw, (200, 200))

    monkeypatch.setattr(send_alerts, "UPCOMING_PARQUET", upcoming)
    monkeypatch.setattr(send_alerts, "RAW_HISTORY_PARQUET", raw)
    monkeypatch.setattr(send_alerts, "HISTORY_PARQUET", enriched)
    errors = []
    monkeypatch.setattr(send_alerts.logger, "error", errors.append)
    monkeypatch.setattr(
        pd,
        "read_parquet",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Parquet should not be loaded when enriched data is stale")
        ),
    )

    send_alerts.run_draw_alerts()

    assert any("enrich_history_with_xg.py" in message for message in errors)


def test_enrichment_step_is_required_in_daily_run():
    enrich_step = next(step for step in daily_run.STEPS if step[0] == "Enriquecer xG")

    assert enrich_step[3] is True
