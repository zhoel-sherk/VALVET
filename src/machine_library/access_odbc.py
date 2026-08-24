"""
Windows ODBC access to Microsoft Access ``.mdb`` / ``.accdb`` via pyodbc.

Uses the same ODBC driver family as the Office **Access Database Engine (ACE)**
redistributable (often exposed as ``Microsoft Access Driver (*.mdb, *.accdb)``).
This is the practical counterpart to OLEDB providers (ACE/Jet) when using Python
+ pandas + PyInstaller.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Microsoft Access Database Engine 2016 Redistributable (ACE); user must match bitness to Python.
ACCESS_ENGINE_2016_REDIST_URL = (
    "https://www.microsoft.com/en-us/download/details.aspx?id=54920"
)

# Prefer newer ACE driver names first (English locale; other locales matched fuzzily).
_PREFERRED_ACCESS_ODBC_DRIVERS: tuple[str, ...] = (
    "Microsoft Access Driver (*.mdb, *.accdb)",
    "Microsoft Access Driver (*.mdb)",
)


class AccessOdbcError(RuntimeError):
    """Missing pyodbc, no suitable ODBC driver, or connection/query failure."""


def pick_access_odbc_driver() -> str | None:
    """
    Return the first usable Microsoft Access ODBC driver name installed locally.

    ``None`` means no driver was found — user should install ACE redistributable.
    """
    try:
        import pyodbc  # type: ignore[import-untyped]
    except ImportError:
        return None

    installed = list(pyodbc.drivers())
    for preferred in _PREFERRED_ACCESS_ODBC_DRIVERS:
        if preferred in installed:
            return preferred

    for d in installed:
        dl = d.lower()
        if "microsoft access" in dl and "mdb" in dl:
            return d
    return None


def format_access_odbc_connection_string(mdb_path: Path, *, driver: str | None = None) -> str:
    """Build a classic ODBC connection string for a file-backed Access database."""
    drv = driver if driver is not None else pick_access_odbc_driver()
    if not drv:
        raise AccessOdbcError(
            "No Microsoft Access ODBC driver found. Install the "
            "Microsoft Access Database Engine 2016 Redistributable (match 64-bit vs 32-bit to your Python build), "
            "then retry."
        )
    # Braces wrap driver name (may contain parentheses/spaces).
    return (
        f"DRIVER={{{drv}}};"
        f"DBQ={mdb_path.resolve()};"
        r"ExtendedAnsiSQL=1;"
    )


def connect_mdb(mdb_path: str | Path) -> Any:
    """Open a read/write pyodbc connection to ``mdb_path``."""
    try:
        import pyodbc  # type: ignore[import-untyped]
    except ImportError as e:
        raise AccessOdbcError(
            "pyodbc is not installed. Install dependencies (``pip install pyodbc``) for Windows .mdb access."
        ) from e

    p = Path(mdb_path)
    if not p.is_file():
        raise AccessOdbcError(f"Not a file: {p}")
    try:
        conn_str = format_access_odbc_connection_string(p)
        return pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        raise AccessOdbcError(
            "Could not open the .mdb via ODBC. Install the Microsoft Access Database Engine "
            "(ACE) redistributable and ensure its bitness matches this Boomer build."
        ) from e


def driver_status_message(driver: str | None) -> str:
    """Human-readable status for UI dialogs."""
    if driver:
        return (
            f"Found ODBC driver:\n{driver}\n\n"
            "You should be able to open Hanwha .mdb libraries from this app on Windows."
        )
    return (
        "No Microsoft Access ODBC driver was detected.\n\n"
        "Install the **Microsoft Access Database Engine 2016 Redistributable** "
        "(same bitness as Boomer — 64-bit Python needs 64-bit ACE).\n\n"
        "If Access or Office is already installed with a different bitness, "
        "Windows may block the other ACE installer — see Microsoft documentation "
        "for the /quiet layout workaround or use a matching Boomer build.\n\n"
        f"Download page:\n{ACCESS_ENGINE_2016_REDIST_URL}"
    )


def list_mdb_tables_odbc(mdb_path: str | Path) -> list[str]:
    """List user tables (excludes MSys* and Access temp names starting with '~')."""
    p = Path(mdb_path)
    conn = connect_mdb(p)
    try:
        cur = conn.cursor()
        names: list[str] = []
        for row in cur.tables(tableType="TABLE"):
            tname = getattr(row, "table_name", None) or (
                row[2] if len(row) > 2 else None
            )
            if not tname:
                continue
            if tname.startswith("MSys") or tname.startswith("~"):
                continue
            names.append(tname)
        return sorted(set(names))
    finally:
        conn.close()


def read_table_dataframe_odbc(mdb_path: str | Path, table: str) -> pd.DataFrame:
    """Read a whole table into a DataFrame (same table-name rules as ``mdb-export``)."""
    if not re.fullmatch(r"[A-Za-z0-9_~]+", table):
        raise AccessOdbcError(f"Refusing unsafe table name: {table!r}")
    p = Path(mdb_path)
    conn = connect_mdb(p)
    try:
        return pd.read_sql_query(f"SELECT * FROM [{table}]", conn)
    finally:
        conn.close()


def export_table_csv_odbc(mdb_path: str | Path, table: str) -> str:
    """CSV text compatible with downstream ``pd.read_csv`` (editor / previews)."""
    df = read_table_dataframe_odbc(mdb_path, table)
    buf = io.StringIO()
    df.to_csv(buf, index=False, lineterminator="\n")
    return buf.getvalue()


def assert_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("access_odbc is only for Windows")
