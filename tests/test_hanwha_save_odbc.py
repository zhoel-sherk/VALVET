"""Qt-free ODBC save paths: connection cleanup on failure."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from hanwha_mdb_edit.core.errors import HanwhaSaveError
from hanwha_mdb_edit.core.save import _save_part_pyodbc, _save_profiles_pyodbc
from machine_library.access_odbc import AccessOdbcError


def _part_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "PARTNAME": ["A"],
            "PROFILENAME": ["A"],
            "PARTDESC": [" "],
            "CONFIDENCE_LEVEL": [0],
            "USED_MACHINE_SET": [0],
            "VENDORID": [0],
        }
    )


def test_save_part_pyodbc_closes_on_insert_failure(mocker, tmp_path: Path) -> None:
    mdb = tmp_path / "lib.mdb"
    mdb.write_bytes(b"x")
    conn = mocker.Mock()
    cur = mocker.Mock()
    conn.cursor.return_value = cur
    cur.execute.side_effect = [None, RuntimeError("insert failed")]
    mocker.patch(
        "hanwha_mdb_edit.core.save.connect_mdb",
        return_value=conn,
    )
    with pytest.raises(HanwhaSaveError, match="insert failed"):
        _save_part_pyodbc(mdb, _part_df())
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_save_part_pyodbc_closes_when_connect_fails(mocker, tmp_path: Path) -> None:
    mdb = tmp_path / "lib.mdb"
    mdb.write_bytes(b"x")
    conn = mocker.Mock()
    mocker.patch(
        "hanwha_mdb_edit.core.save.connect_mdb",
        side_effect=AccessOdbcError("no ACE"),
    )
    with pytest.raises(HanwhaSaveError, match="no ACE"):
        _save_part_pyodbc(mdb, _part_df())
    conn.close.assert_not_called()


def test_save_profiles_pyodbc_closes_on_update_failure(mocker, tmp_path: Path) -> None:
    mdb = tmp_path / "lib.mdb"
    mdb.write_bytes(b"x")
    conn = mocker.Mock()
    cur = mocker.Mock()
    conn.cursor.return_value = cur
    cur.execute.side_effect = RuntimeError("update failed")
    mocker.patch(
        "hanwha_mdb_edit.core.save.connect_mdb",
        return_value=conn,
    )
    enriched = pd.DataFrame(
        {
            "PARTNAME": ["A"],
            "PROFILENAME": ["P1"],
            "PARTDESC": [" "],
            "CONFIDENCE_LEVEL": [0],
            "USED_MACHINE_SET": [0],
            "VENDORID": [0],
            "PARENTPROFILE": ["parent"],
        }
    )
    with pytest.raises(HanwhaSaveError, match="update failed"):
        _save_profiles_pyodbc(mdb, enriched)
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()
