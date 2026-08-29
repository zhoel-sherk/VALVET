"""Headless smoke: construct the app the same way as ``python src/main.py``."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_main_py_smoke_exits_zero() -> None:
    env = {**os.environ, "PYTHONPATH": "src", "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "src" / "main.py"), "--smoke"],
        cwd=str(_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    assert proc.returncode == 0, out
    assert "VALVET" in out or proc.returncode == 0
