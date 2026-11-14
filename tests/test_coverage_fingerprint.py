import hashlib
import subprocess

import pandas as pd

from scripts import data_coverage_report


def test_coverage_summary_starts_with_parquet_fingerprint(tmp_path, monkeypatch):
    parquet = tmp_path / "history_with_xg.parquet"
    parquet.write_bytes(b"test parquet content")
    output = tmp_path / "coverage_summary.txt"
    monkeypatch.setattr(data_coverage_report, "HISTORY_PARQUET", parquet)
    monkeypatch.setattr(
        data_coverage_report,
        "UPCOMING_PARQUET",
        tmp_path / "missing_upcoming.parquet",
    )
    monkeypatch.setattr(data_coverage_report, "_git_commit_short", lambda: "abc1234")
    df = pd.DataFrame({
        "date": [pd.Timestamp("2026-11-14")],
        "competition": ["PL"],
        "season": ["2026"],
        "home_team": ["Home"],
        "away_team": ["Away"],
    })

    data_coverage_report.write_summary(df, pd.DataFrame(), output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[:3] == [
        f"Parquet SHA256: {hashlib.sha256(parquet.read_bytes()).hexdigest()}",
        "Git commit: abc1234",
        "Schema: 2.0",
    ]


def test_git_fingerprint_falls_back_to_unknown(monkeypatch):
    def failed_git(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(data_coverage_report.subprocess, "run", failed_git)

    assert data_coverage_report._git_commit_short() == "unknown"
