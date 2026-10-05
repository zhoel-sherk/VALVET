# SPDX-License-Identifier: MIT
"""Append GUI session lines to logs/sessionlogYYYY-MM-DD_HHMMSS.txt (Qt-free)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import logger

# Console lines at these levels never reach the file. The GUI filters ``debug``
# for *display* only; letting that double as the file filter is what put debug
# chatter (including raw BOM comment text) into a file users attach to bug
# reports.
_FILE_DROP_LEVELS = frozenset({"DEBUG", "TRACE"})

_write_failed_warned = False


def repo_logs_dir() -> Path:
    """``<repo>/logs`` — same tree as logger dated files (parent of ``src/``)."""
    return Path(__file__).resolve().parent.parent / "logs"


def new_session_log_path(*, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    return repo_logs_dir() / f"sessionlog{stamp}.txt"


def append_session_line(
    path: Path | None, level: str, message: str, *, now: datetime | None = None
) -> None:
    """Append one console line. Never raises: logging must not break a run.

    Read-only install, full disk or a locked file used to propagate an OSError
    out of the GUI log slot and take the message path down with it.
    """
    global _write_failed_warned
    if path is None:
        return
    lvl = (level or "info").strip().upper() or "INFO"
    if lvl in _FILE_DROP_LEVELS:
        return
    ts = (now or datetime.now()).strftime("%H:%M:%S")
    text = (message or "").replace("\r\n", "\n").replace("\r", "\n")
    line = f"{ts} {lvl} {text}\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        if not _write_failed_warned:
            _write_failed_warned = True
            logger.warning("session log write failed, continuing: %s", exc)
