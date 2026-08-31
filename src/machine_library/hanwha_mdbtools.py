"""
Read Hanwha/Samsung-style UPD Microsoft Access .mdb.

- **Windows:** ODBC via **pyodbc** and the Microsoft Access Database Engine (ACE)
  driver (same stack as in-place saves in ``hanwha_mdb_edit``). PyInstaller-frozen
  builds do **not** fall back to mdbtools — ship ACE on the machine.
- **Linux / dev:** ``mdb-tables`` / ``mdb-export`` from **mdbtools** on ``PATH``
  (Fedora: ``dnf install mdbtools``). On Windows, mdbtools is used only as a
  **non-frozen** fallback when ODBC is unavailable.

Primary table for machine component names: PART_Det
  PARTNAME, PROFILENAME, PARTDESC, CONFIDENCE_LEVEL, USED_MACHINE_SET, VENDORID
"""

from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

import logger


class HanwhaMdbToolsError(RuntimeError):
    """Could not read .mdb (ODBC or mdbtools)."""


@dataclass(frozen=True)
class HanwhaPartDetRow:
    """One row of PART_Det — machine library part name + vision profile link."""

    partname: str
    profilename: str
    partdesc: str
    confidence_level: int
    used_machine_set: int
    vendor_id: int = 0


def _is_pyinstaller_bundle() -> bool:
    return bool(getattr(sys, "frozen", False))


def _mdb_tools_fallback_allowed() -> bool:
    """Frozen Windows exe should rely on ODBC only (no bundled mdb-export)."""
    return not _is_pyinstaller_bundle()


def _which_or_raise(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise HanwhaMdbToolsError(f"{binary} not found on PATH; install mdbtools.")
    return path


def _list_mdb_tables_cli(mdb_path: Path) -> list[str]:
    exe = _which_or_raise("mdb-tables")
    r = subprocess.run(
        [exe, str(mdb_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise HanwhaMdbToolsError(err or f"mdb-tables failed with code {r.returncode}")
    line = (r.stdout or "").strip()
    if not line:
        return []
    return line.split()


def _export_table_csv_cli(mdb_path: Path, table: str) -> str:
    exe = _which_or_raise("mdb-export")
    r = subprocess.run(
        [exe, str(mdb_path), table],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        raise HanwhaMdbToolsError(err or f"mdb-export failed for table {table!r}")
    return r.stdout or ""


def list_mdb_tables(mdb_path: str | Path) -> list[str]:
    """Table names (user tables; excludes MSys* on ODBC path)."""
    p = Path(mdb_path)
    if not p.is_file():
        raise HanwhaMdbToolsError(f"Not a file: {p}")

    if sys.platform == "win32":
        odbc_msg: str | None = None
        try:
            from machine_library.access_odbc import (
                AccessOdbcError,
                list_mdb_tables_odbc,
            )

            return list_mdb_tables_odbc(p)
        except AccessOdbcError as e:
            odbc_msg = str(e)
        except Exception as e:
            odbc_msg = f"Windows ODBC: {e}"

        if _mdb_tools_fallback_allowed():
            try:
                names = _list_mdb_tables_cli(p)
                logger.warning(
                    "ODBC failed (%s); using mdbtools for tables in %s",
                    odbc_msg,
                    p,
                )
                return names
            except HanwhaMdbToolsError as e2:
                raise HanwhaMdbToolsError(
                    f"{odbc_msg}\n\nFallback (mdbtools) also failed:\n{e2}"
                ) from e2

        raise HanwhaMdbToolsError(
            f"{odbc_msg}\n\n"
            "Install the Microsoft Access Database Engine (ACE) ODBC driver "
            "(same bitness as VALVET). mdbtools is not used inside the frozen Windows build."
        )

    return _list_mdb_tables_cli(p)


def export_table_csv(mdb_path: str | Path, table: str) -> str:
    """Raw CSV text for one table (mdb-export compatible layout)."""
    p = Path(mdb_path)
    if not p.is_file():
        raise HanwhaMdbToolsError(f"Not a file: {p}")
    if not re.fullmatch(r"[A-Za-z0-9_~]+", table):
        raise HanwhaMdbToolsError(f"Refusing unsafe table name: {table!r}")

    if sys.platform == "win32":
        odbc_msg: str | None = None
        try:
            from machine_library.access_odbc import (
                AccessOdbcError,
                export_table_csv_odbc,
            )

            return export_table_csv_odbc(p, table)
        except AccessOdbcError as e:
            odbc_msg = str(e)
        except Exception as e:
            odbc_msg = f"Windows ODBC: {e}"

        if _mdb_tools_fallback_allowed():
            try:
                csv_text = _export_table_csv_cli(p, table)
                logger.warning(
                    "ODBC failed (%s); using mdbtools export for %s.%s",
                    odbc_msg,
                    p,
                    table,
                )
                return csv_text
            except HanwhaMdbToolsError as e2:
                raise HanwhaMdbToolsError(
                    f"{odbc_msg}\n\nFallback (mdbtools) also failed:\n{e2}"
                ) from e2

        raise HanwhaMdbToolsError(
            f"{odbc_msg}\n\n"
            "Install the Microsoft Access Database Engine (ACE) ODBC driver "
            "(same bitness as VALVET). mdbtools is not used inside the frozen Windows build."
        )

    return _export_table_csv_cli(p, table)


def parse_part_det_csv(csv_text: str) -> list[HanwhaPartDetRow]:
    """Parse mdb-export CSV for PART_Det."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return []
    fields = {n.upper(): n for n in reader.fieldnames}
    need = (
        "PARTNAME",
        "PROFILENAME",
        "PARTDESC",
        "CONFIDENCE_LEVEL",
        "USED_MACHINE_SET",
    )
    for k in need:
        if k not in fields:
            raise HanwhaMdbToolsError(
                f"PART_Det CSV missing column {k}; got {reader.fieldnames!r}"
            )

    def col(name: str) -> str:
        return fields[name.upper()]

    has_vendor = "VENDORID" in fields
    vend_col = fields.get("VENDORID")

    out: list[HanwhaPartDetRow] = []
    for d in reader:
        raw_conf = (d.get(col("CONFIDENCE_LEVEL")) or "").strip()
        raw_used = (d.get(col("USED_MACHINE_SET")) or "").strip()
        try:
            conf = int(raw_conf) if raw_conf else 0
        except ValueError:
            conf = 0
        try:
            used = int(raw_used) if raw_used else 0
        except ValueError:
            used = 0
        vid = 0
        if has_vendor and vend_col:
            raw_v = (d.get(vend_col) or "").strip()
            try:
                vid = int(raw_v) if raw_v else 0
            except ValueError:
                vid = 0
        out.append(
            HanwhaPartDetRow(
                partname=(d.get(col("PARTNAME")) or "").strip(),
                profilename=(d.get(col("PROFILENAME")) or "").strip(),
                partdesc=(d.get(col("PARTDESC")) or "").strip(),
                confidence_level=conf,
                used_machine_set=used,
                vendor_id=vid,
            )
        )
    return out


def part_det_rows_to_dataframe(rows: Sequence[HanwhaPartDetRow]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "PARTNAME",
                "PROFILENAME",
                "PARTDESC",
                "CONFIDENCE_LEVEL",
                "USED_MACHINE_SET",
                "VENDORID",
            ]
        )
    return pd.DataFrame(
        {
            "PARTNAME": [r.partname for r in rows],
            "PROFILENAME": [r.profilename for r in rows],
            "PARTDESC": [r.partdesc for r in rows],
            "CONFIDENCE_LEVEL": [r.confidence_level for r in rows],
            "USED_MACHINE_SET": [r.used_machine_set for r in rows],
            "VENDORID": [r.vendor_id for r in rows],
        }
    )


def load_part_det_from_mdb(mdb_path: str | Path) -> list[HanwhaPartDetRow]:
    """Load PART_Det (Windows: direct ODBC column select, not SELECT * / CSV)."""
    if sys.platform == "win32":
        try:
            from machine_library.access_odbc import (
                AccessOdbcError,
                load_part_det_dataframe_odbc,
            )

            df = load_part_det_dataframe_odbc(mdb_path)
            return _part_det_dataframe_to_rows(df)
        except AccessOdbcError as e:
            raise HanwhaMdbToolsError(str(e)) from e
    csv_text = export_table_csv(mdb_path, "PART_Det")
    return parse_part_det_csv(csv_text)


def _csv_table_columns(
    mdb_path: str | Path, table: str, columns: tuple[str, ...]
) -> pd.DataFrame:
    try:
        raw = export_table_csv(mdb_path, table)
    except HanwhaMdbToolsError:
        return pd.DataFrame(columns=list(columns))
    df = pd.read_csv(io.StringIO(raw))
    keep = [c for c in columns if c in df.columns]
    if not keep:
        return pd.DataFrame(columns=list(columns))
    return df[keep]


def load_hanwha_machine_lib_dataframe(
    mdb_path: str | Path,
    *,
    progress: Callable[[int, str], None] | None = None,
) -> pd.DataFrame:
    """PART_Det plus Type (``UPDPARTGROUPNAME``). Extra PART_Det columns stay in memory."""
    from machine_library.hanwha_preview import attach_part_group_type

    def _progress(pct: int, msg: str) -> None:
        if progress is not None:
            progress(pct, msg)

    if sys.platform == "win32":
        try:
            from machine_library.access_odbc import (
                AccessOdbcError,
                load_machine_lib_join_tables_odbc,
            )

            parts, profile, gmap = load_machine_lib_join_tables_odbc(
                mdb_path, progress=progress
            )
        except AccessOdbcError as e:
            raise HanwhaMdbToolsError(str(e)) from e
        _progress(90, "Joining Type (PARTGROUP)…")
        out = attach_part_group_type(parts, profile, gmap)
        _progress(100, "Done")
        return out

    _progress(15, "Reading PART_Det…")
    parts = part_det_rows_to_dataframe(load_part_det_from_mdb(mdb_path))
    _progress(50, "Reading PROFILE_Det…")
    profile = _csv_table_columns(
        mdb_path, "PROFILE_Det", ("PROFILENAME", "UPDPARTGROUPID")
    )
    _progress(70, "Reading PARTGROUP_Map…")
    gmap = _csv_table_columns(
        mdb_path, "PARTGROUP_Map", ("UPDPARTGROUPID", "UPDPARTGROUPNAME")
    )
    _progress(90, "Joining Type (PARTGROUP)…")
    out = attach_part_group_type(parts, profile, gmap)
    _progress(100, "Done")
    return out


def _part_det_dataframe_to_rows(df: pd.DataFrame) -> list[HanwhaPartDetRow]:
    has_vendor = "VENDORID" in df.columns
    out: list[HanwhaPartDetRow] = []

    def _int(raw: object) -> int:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return 0
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def _str(raw: object) -> str:
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            return ""
        return str(raw).strip()

    for rec in df.to_dict("records"):
        out.append(
            HanwhaPartDetRow(
                partname=_str(rec.get("PARTNAME")),
                profilename=_str(rec.get("PROFILENAME")),
                partdesc=_str(rec.get("PARTDESC")),
                confidence_level=_int(rec.get("CONFIDENCE_LEVEL")),
                used_machine_set=_int(rec.get("USED_MACHINE_SET")),
                vendor_id=_int(rec.get("VENDORID")) if has_vendor else 0,
            )
        )
    return out
