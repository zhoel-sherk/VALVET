"""SPACES / *sp production reader (replaces legacy csv_reader TextGrid tests)."""

from __future__ import annotations

import os

import pytest

import smt_processor

tests_path = os.path.dirname(os.path.realpath(__file__))


def test_whitespace_sp_spaces_asset() -> None:
    path = os.path.join(tests_path, "assets", "spaces.csv")
    df = smt_processor.read_text_whitespace_sp(path)
    assert not df.empty
    flat = df.astype(str).values.ravel().tolist()
    assert any(v == "Fid6" for v in flat)


def test_read_file_tabs_asset() -> None:
    path = os.path.join(tests_path, "assets", "tabs.csv")
    df = smt_processor.read_file(path, separator="\t")
    assert not df.empty
    flat = df.astype(str).values.ravel().tolist()
    assert any("SOT23" in v for v in flat)


def test_read_file_comma_asset() -> None:
    path = os.path.join(tests_path, "assets", "comma.csv")
    df = smt_processor.read_file(path, separator=",")
    assert "R52" in df.astype(str).values.ravel().tolist() or "R52" in str(
        df.iloc[0].tolist()
    )


def test_whitespace_missing_file(tmp_path) -> None:
    with pytest.raises(smt_processor.SMTFileNotFoundError):
        smt_processor.read_text_whitespace_sp(str(tmp_path / "nope.txt"))
