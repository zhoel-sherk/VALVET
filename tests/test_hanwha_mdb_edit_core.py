"""Qt-free tests for hanwha_mdb_edit core."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from hanwha_mdb_edit.core.errors import HanwhaSaveError, HanwhaValidationError
from hanwha_mdb_edit.core.part_det_model import MAX_PARTNAME_LEN, EditablePartDetRow
from hanwha_mdb_edit.core.save import (
    SaveResult,
    format_part_det_csv,
    save_enriched_library,
    save_part_det,
)
from mdb_paths import resolve_upd_mdb, skip_if_mdb_unreadable

_UPD_MDB = resolve_upd_mdb()


def test_editable_row_validates_partname_length() -> None:
    long_name = "x" * (MAX_PARTNAME_LEN + 1)
    row = EditablePartDetRow(long_name, "p", "d", 0, 0)
    with pytest.raises(HanwhaValidationError):
        row.validate()


def test_format_part_det_csv_headers() -> None:
    df = pd.DataFrame(
        {
            "PARTNAME": ["A"],
            "PROFILENAME": ["A"],
            "PARTDESC": [" "],
            "CONFIDENCE_LEVEL": [0],
            "USED_MACHINE_SET": [0],
            "VENDORID": [0],
        }
    )
    text = format_part_det_csv(df)
    lines = text.strip().splitlines()
    assert lines[0].startswith("PARTNAME,")
    assert "A" in lines[1]


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_save_creates_backup_and_csv_sidecar(tmp_path: Path) -> None:
    import shutil

    from hanwha_mdb_edit.core.part_det_repository import load_part_det_dataframe

    skip_if_mdb_unreadable(_UPD_MDB)
    mdb_copy = tmp_path / "lib.mdb"
    shutil.copy2(_UPD_MDB, mdb_copy)
    df = load_part_det_dataframe(mdb_copy)
    csv_path = mdb_copy.with_name(f"{mdb_copy.stem}_PART_Det_saved.csv")
    try:
        result = save_part_det(mdb_copy, df)
    except HanwhaSaveError:
        # Windows ACE ODBC may reject in-place writes; CSV sidecar is still written.
        assert csv_path.is_file()
        assert csv_path.read_text(encoding="utf-8").startswith("PARTNAME,")
        return
    assert isinstance(result, SaveResult)
    assert result.mode in ("csv_sidecar", "mdb_pyodbc")
    assert result.backup_path.is_file()
    assert result.exported_paths
    assert result.exported_paths[0].name.endswith("_PART_Det_saved.csv")
    assert result.exported_paths[0].read_text(encoding="utf-8").startswith("PARTNAME,")


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_load_wide_has_at_least_enriched_columns() -> None:
    from hanwha_mdb_edit.core.part_enriched import (
        load_enriched_parts_dataframe,
        load_wide_editor_dataframe,
    )

    skip_if_mdb_unreadable(_UPD_MDB)
    wide = load_wide_editor_dataframe(_UPD_MDB)
    base = load_enriched_parts_dataframe(_UPD_MDB)
    assert len(wide.columns) >= len(base.columns)
    for c in base.columns:
        assert c in wide.columns


@pytest.mark.skipif(_UPD_MDB is None, reason="UPD.MDB not present")
def test_save_enriched_writes_four_sidecars(tmp_path: Path) -> None:
    import shutil

    from hanwha_mdb_edit.core.part_enriched import load_enriched_parts_dataframe

    skip_if_mdb_unreadable(_UPD_MDB)
    mdb_copy = tmp_path / "lib.mdb"
    shutil.copy2(_UPD_MDB, mdb_copy)
    df = load_enriched_parts_dataframe(mdb_copy)
    try:
        result = save_enriched_library(mdb_copy, df)
    except HanwhaSaveError:
        names = {p.name for p in mdb_copy.parent.glob(f"{mdb_copy.stem}_*_saved.csv")}
        assert any("PART_Det_saved" in n for n in names)
        assert any("PROFILE_Det_saved" in n for n in names)
        return
    assert len(result.exported_paths) == 4
    names = {p.name for p in result.exported_paths}
    assert any("PART_Det_saved" in n for n in names)
    assert any("PROFILE_Det_saved" in n for n in names)


def test_bulk_paren_updates_rows() -> None:
    from hanwha_mdb_edit.core.part_bulk import bulk_update_paren_profile

    df = pd.DataFrame(
        {
            "PARTNAME": ["a", "b"],
            "PROFILENAME": ["p", "p"],
            "PARENTPROFILE": ["old", "old"],
        }
    )
    out = bulk_update_paren_profile(df, "old", "new")
    assert list(out["PARENTPROFILE"]) == ["new", "new"]
