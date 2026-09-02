from __future__ import annotations

from datetime import datetime
from pathlib import Path

from session_file_log import append_session_line, new_session_log_path


def test_append_session_line_info_and_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("session_file_log.repo_logs_dir", lambda: tmp_path / "logs")
    path = new_session_log_path(now=datetime(2026, 9, 1, 23, 30, 5))
    assert path.name == "sessionlog2026-09-01_233005.txt"
    append_session_line(
        path, "info", "Opened MDB C:\\lib\\UPD.MDB", now=datetime(2026, 9, 1, 23, 30, 6)
    )
    append_session_line(path, "error", "boom", now=datetime(2026, 9, 1, 23, 30, 7))
    text = path.read_text(encoding="utf-8")
    assert "INFO Opened MDB" in text
    assert "ERROR boom" in text
    assert text.startswith("23:30:06")


def test_lang_session_log_keys() -> None:
    import json

    root = Path(__file__).resolve().parents[1] / "lang"
    for path in root.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "project.session_log" in data, path.name
        assert "project.session_log_hint" in data, path.name
