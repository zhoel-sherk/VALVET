"""Golden Clean BOM corpus — regression vs tests/fixtures/clean_corpus/golden.xlsx."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

tests_dir = Path(__file__).resolve().parent
_boomer_root = tests_dir.parent


def _golden_path() -> Path:
    raw = os.environ.get("BOOMER_CLEAN_CORPUS_GOLDEN", "").strip()
    if raw:
        return Path(raw)
    return _boomer_root / "tests" / "fixtures" / "clean_corpus" / "golden.xlsx"


def test_clean_corpus_golden_matches_clean_one() -> None:
    if not _golden_path().is_file():
        pytest.skip(f"golden corpus missing: {_golden_path()}")
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [sys.executable, str(_boomer_root / "tools" / "clean_corpus.py"), "test"],
        cwd=str(_boomer_root),
        env=env,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        pytest.fail(out or "clean_corpus test failed")
