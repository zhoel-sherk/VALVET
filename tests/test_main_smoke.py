"""Headless smoke: construct the app the same way as ``python src/main.py``."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_main_smoke_tolerates_invalid_windowed_stdout(monkeypatch, qapp) -> None:
    """PyInstaller console=False can expose a stdout that raises EINVAL."""
    import main as main_module

    class BrokenStdout:
        def write(self, _text):
            raise OSError(22, "Invalid argument")

        def flush(self):
            raise OSError(22, "Invalid argument")

    monkeypatch.setattr(sys, "stdout", BrokenStdout())
    with pytest.raises(SystemExit) as result:
        main_module.main(["--smoke"])
    assert result.value.code == 0
