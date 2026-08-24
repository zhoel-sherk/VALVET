"""Unit tests for cross-platform paths and session-link facades."""

from __future__ import annotations

import os
import sys

tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

from app_paths import autosave_root, user_state_dir
from facades.session_links import apply_session_links_payload, session_links_to_pairs


def test_user_state_dir_is_absolute_under_tmp_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    d = user_state_dir()
    assert d.is_absolute()
    assert "VALVET" in str(d) or d.name == "VALVET"


def test_autosave_root_child_of_user_state() -> None:
    assert autosave_root().parent == user_state_dir()


def test_session_links_roundtrip() -> None:
    bom_to_pnp: dict[str, set[str]] = {"a": {"x", "y"}, "b": {"x"}}
    payload = session_links_to_pairs(bom_to_pnp)
    assert len(payload) == 3
    b2p, p2b = apply_session_links_payload(payload)
    assert dict(b2p) == {"a": {"x", "y"}, "b": {"x"}}
    assert dict(p2b) == {"x": {"a", "b"}, "y": {"a"}}


def test_session_links_empty_payload() -> None:
    b2p, p2b = apply_session_links_payload(None)
    assert dict(b2p) == {}
    assert dict(p2b) == {}
