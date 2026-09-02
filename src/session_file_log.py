# SPDX-License-Identifier: MIT
"""Append GUI session lines to logs/sessionlogYYYY-MM-DD_HHMMSS.txt (Qt-free)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def repo_logs_dir() -> Path:
    """``<repo>/logs`` — same tree as logger dated files (parent of ``src/``)."""
    return Path(__file__).resolve().parent.parent / "logs"


def new_session_log_path(*, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    return repo_logs_dir() / f"sessionlog{stamp}.txt"


def append_session_line(
    path: Path | None, level: str, message: str, *, now: datetime | None = None
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = (now or datetime.now()).strftime("%H:%M:%S")
    lvl = (level or "info").strip().upper() or "INFO"
    text = (message or "").replace("\r\n", "\n").replace("\r", "\n")
    line = f"{ts} {lvl} {text}\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
