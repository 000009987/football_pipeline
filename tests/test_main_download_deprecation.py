import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_download_mode_is_deprecated_and_exits_nonzero():
    result = subprocess.run(
        [sys.executable, str(ROOT / "main.py"), "--mode", "download"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout.strip() == (
        "⚠️ DEPRECADO: usa 'python scripts/refresh_history.py' en su lugar"
    )
