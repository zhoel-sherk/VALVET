"""Missing/empty/corrupt path validation for legacy TextGrid readers."""

from __future__ import annotations

import os
import sys

import pytest

tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

import ods_reader
import xls_reader
import xlsx_reader


@pytest.mark.parametrize(
    "reader",
    [
        xls_reader.read_xls_sheet,
        xlsx_reader.read_xlsx_sheet,
        ods_reader.read_ods_sheet,
    ],
)
def test_reader_rejects_missing_file(reader, tmp_path) -> None:
    missing = tmp_path / "missing.bin"
    with pytest.raises(FileNotFoundError):
        reader(str(missing))


@pytest.mark.parametrize(
    "reader",
    [
        xls_reader.read_xls_sheet,
        xlsx_reader.read_xlsx_sheet,
        ods_reader.read_ods_sheet,
    ],
)
def test_reader_rejects_empty_path(reader) -> None:
    with pytest.raises(FileNotFoundError, match="Empty file path"):
        reader("")


def test_xlsx_reader_rejects_corrupt_bytes(tmp_path) -> None:
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(Exception):
        xlsx_reader.read_xlsx_sheet(str(bad))
