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
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

import logger

try:
    import pyodbc as _pyodbc_mod  # type: ignore[import-untyped]

    _pyodbc_mod.pooling = False
except ImportError:
    _pyodbc_mod = None  # type: ignore[assignment]

# Microsoft Access Database Engine 2016 Redistributable (ACE); user must match bitness to Python.
ACCESS_ENGINE_2016_REDIST_URL = (
    "https://www.microsoft.com/en-us/download/details.aspx?id=54920"
)

_PREFERRED_ACE: tuple[str, ...] = (
    "Microsoft Access Driver (*.mdb, *.accdb)",
    "Microsoft Access Driver (*.mdb)",
)
_PREFERRED_JET_FIRST: tuple[str, ...] = (
    "Microsoft Access Driver (*.mdb)",
    "Microsoft Access Driver (*.mdb, *.accdb)",
)

PART_DET_SELECT_COLS = (
    "PARTNAME",
    "PROFILENAME",
    "PARTDESC",
    "CONFIDENCE_LEVEL",
    "USED_MACHINE_SET",
    "VENDORID",
)
PART_DET_SELECT_COLS_NO_VENDOR = PART_DET_SELECT_COLS[:-1]


class AccessOdbcError(RuntimeError):
    """Missing pyodbc, no suitable ODBC driver, or connection/query failure."""


def ensure_com_sta() -> None:
    """ACE/Jet is STA COM. QThread must initialize an apartment or the driver hangs."""
    if sys.platform != "win32":
        return
    import ctypes

    # COINIT_APARTMENTTHREADED = 0x2
    hr = ctypes.windll.ole32.CoInitializeEx(None, 0x2)
    # S_OK / S_FALSE / RPC_E_CHANGED_MODE — ignore; we only need an apartment.
    del hr


def pick_access_odbc_driver(*, prefer_jet: bool = False) -> str | None:
    """
    Return the first usable Microsoft Access ODBC driver name installed locally.

    ``None`` means no driver was found — user should install ACE redistributable.
    Jet-era ``.mdb`` (Hanwha UPD) often behaves better with the older ``*.mdb`` driver.
    """
    try:
        import pyodbc  # type: ignore[import-untyped]
    except ImportError:
        return None

    installed = list(pyodbc.drivers())
    preferred = _PREFERRED_JET_FIRST if prefer_jet else _PREFERRED_ACE
    for name in preferred:
        if name in installed:
            return name

    for d in installed:
        dl = d.lower()
        if "microsoft access" in dl and "mdb" in dl:
            return d
    return None


def format_access_odbc_connection_string(
    mdb_path: Path,
    *,
    driver: str | None = None,
    read_only: bool = False,
) -> str:
    """Build a classic ODBC connection string for a file-backed Access database."""
    prefer_jet = mdb_path.suffix.lower() == ".mdb"
    drv = (
        driver if driver is not None else pick_access_odbc_driver(prefer_jet=prefer_jet)
    )
    if not drv:
        raise AccessOdbcError(
            "No Microsoft Access ODBC driver found. Install the "
            "Microsoft Access Database Engine 2016 Redistributable (match 64-bit vs 32-bit to your Python build), "
            "then retry."
        )
    extra = ""
    if read_only:
        extra += "ReadOnly=1;"
    return f"DRIVER={{{drv}}};DBQ={mdb_path.resolve()};{extra}"


def _short_win_path(path: Path) -> Path | None:
    if sys.platform != "win32":
        return None
    import ctypes

    GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    buf = ctypes.create_unicode_buffer(520)
    n = GetShortPathNameW(str(path.resolve()), buf, 520)
    if n and buf.value:
        return Path(buf.value)
    return None


def _try_unlink_stale_lock(mdb_path: Path) -> None:
    for suf in (".ldb", ".LDB"):
        lock = mdb_path.with_suffix(suf)
        if not lock.is_file():
            continue
        try:
            lock.unlink()
            logger.info("Removed stale Access lock file %s", lock.name)
        except OSError:
            logger.warning("Could not remove lock file %s (still in use)", lock.name)


def _odbc_driver_candidates(mdb_path: Path) -> list[str]:
    prefer_jet = mdb_path.suffix.lower() == ".mdb"
    names: list[str] = []
    for flag in (prefer_jet, not prefer_jet):
        d = pick_access_odbc_driver(prefer_jet=flag)
        if d and d not in names:
            names.append(d)
    return names


def connect_mdb(
    mdb_path: str | Path,
    *,
    read_only: bool = False,
    timeout: int = 8,
) -> Any:
    """Open a pyodbc connection.

    ``timeout`` is accepted for callers but ignored: Jet/Access ODBC returns
    HYC00 if pyodbc sets login/query timeout via ``SQLSetConnectAttr``.
    """
    _ = timeout
    try:
        import pyodbc  # type: ignore[import-untyped]
    except ImportError as e:
        raise AccessOdbcError(
            "pyodbc is not installed. Install dependencies (``pip install pyodbc``) for Windows .mdb access."
        ) from e

    ensure_com_sta()
    pyodbc.pooling = False

    p = Path(mdb_path)
    if not p.is_file():
        raise AccessOdbcError(f"Not a file: {p}")
    _try_unlink_stale_lock(p)

    drivers = _odbc_driver_candidates(p)
    if not drivers:
        raise AccessOdbcError(
            "No Microsoft Access ODBC driver found. Install the "
            "Microsoft Access Database Engine 2016 Redistributable "
            "(same bitness as this Python / VALVET build)."
        )

    paths = [p]
    short = _short_win_path(p)
    if short is not None and short != p:
        paths.append(short)

    extras = ["", "Exclusive=0;"]
    if read_only:
        extras.append("ReadOnly=1;")
    errors: list[str] = []
    for drv in drivers:
        for dbq in paths:
            for extra in extras:
                conn_str = f"DRIVER={{{drv}}};DBQ={dbq.resolve()};{extra}"
                try:
                    # Do not pass timeout= or set conn.timeout: Access driver
                    # SQLSetConnectAttr is unimplemented (HYC00 / native 106).
                    conn = pyodbc.connect(conn_str, autocommit=True)
                    logger.info("ODBC connected with driver %s extra=%r", drv, extra)
                    return conn
                except pyodbc.Error as e:
                    errors.append(f"{drv} extra={extra!r}: {e}")
                    logger.warning("ODBC connect failed: %s", errors[-1])
                    if "HYC00" in str(e):
                        try:
                            conn = pyodbc.connect(conn_str)
                            logger.info(
                                "ODBC connected (no autocommit) driver %s extra=%r",
                                drv,
                                extra,
                            )
                            return conn
                        except pyodbc.Error as e2:
                            errors.append(f"{drv} extra={extra!r} no-autocommit: {e2}")
                            logger.warning("ODBC connect failed: %s", errors[-1])
    detail = " | ".join(errors[-6:]) if errors else "unknown"
    raise AccessOdbcError(
        "Could not open the .mdb via ODBC.\n"
        f"{detail}\n\n"
        "If the message is 'already in use', close Microsoft Access and Cursor Access MCP, "
        "then delete a leftover .ldb next to the file. "
        "If it is IM002 / driver, install ACE matching 64-bit vs 32-bit of VALVET."
    )


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
        "(same bitness as VALVET — 64-bit Python needs 64-bit ACE).\n\n"
        "If Access or Office is already installed with a different bitness, "
        "Windows may block the other ACE installer — see Microsoft documentation "
        "for the /quiet layout workaround or use a matching VALVET build.\n\n"
        f"Download page:\n{ACCESS_ENGINE_2016_REDIST_URL}"
    )


def list_mdb_tables_odbc(mdb_path: str | Path) -> list[str]:
    """List user tables (excludes MSys* and Access temp names starting with '~')."""
    p = Path(mdb_path)
    conn = connect_mdb(p, read_only=False)
    try:
        cur = conn.cursor()
        try:
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
            cur.close()
    finally:
        conn.close()


def fetch_named_columns(
    conn: Any, table: str, columns: tuple[str, ...]
) -> pd.DataFrame:
    """SELECT listed columns from one Access table on an open connection."""
    import pyodbc  # type: ignore[import-untyped]

    if not re.fullmatch(r"[A-Za-z0-9_~]+", table):
        raise AccessOdbcError(f"Refusing unsafe table name: {table!r}")
    sql = "SELECT " + ", ".join(f"[{c}]" for c in columns) + f" FROM [{table}]"
    cur = conn.cursor()
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        names = [str(d[0]) for d in (cur.description or ())]
    except pyodbc.Error as e:
        raise AccessOdbcError(f"{table} query failed: {e}") from e
    finally:
        cur.close()
    return pd.DataFrame.from_records(list(rows), columns=names or list(columns))


def load_part_det_on_connection(conn: Any) -> pd.DataFrame:
    last: Exception | None = None
    for cols in (PART_DET_SELECT_COLS, PART_DET_SELECT_COLS_NO_VENDOR):
        try:
            df = fetch_named_columns(conn, "PART_Det", cols)
        except AccessOdbcError as e:
            last = e
            continue
        if "VENDORID" not in df.columns:
            df["VENDORID"] = 0
        return df
    raise AccessOdbcError(f"PART_Det query failed: {last}") from last


def load_part_det_dataframe_odbc(mdb_path: str | Path) -> pd.DataFrame:
    """
    Load only PART_Det matching columns (no SELECT *, no temp-file copy).

    Copies of a locked UPD often hang ACE; SELECT * pulls memo/OLE columns.
    """
    p = Path(mdb_path)
    t0 = time.perf_counter()
    conn = connect_mdb(p, read_only=False)
    try:
        df = load_part_det_on_connection(conn)
        logger.info(
            "ODBC PART_Det: %s rows from %s in %.1fs",
            len(df),
            p.name,
            time.perf_counter() - t0,
        )
        return df
    finally:
        conn.close()


def load_machine_lib_join_tables_odbc(
    mdb_path: str | Path,
    *,
    progress: Callable[[int, str], None] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One ODBC session: PART_Det + PROFILE_Det ids + PARTGROUP_Map names."""

    def _progress(pct: int, msg: str) -> None:
        if progress is not None:
            progress(pct, msg)

    p = Path(mdb_path)
    t0 = time.perf_counter()
    _progress(10, "Connecting ODBC…")
    conn = connect_mdb(p, read_only=False)
    try:
        _progress(25, "Reading PART_Det…")
        parts = load_part_det_on_connection(conn)
        _progress(50, "Reading PROFILE_Det…")
        try:
            profile = fetch_named_columns(
                conn, "PROFILE_Det", ("PROFILENAME", "UPDPARTGROUPID")
            )
        except AccessOdbcError as e:
            logger.warning("ODBC PROFILE_Det query failed (%s); empty frame", e)
            profile = pd.DataFrame(columns=["PROFILENAME", "UPDPARTGROUPID"])
        _progress(70, "Reading PARTGROUP_Map…")
        try:
            gmap = fetch_named_columns(
                conn, "PARTGROUP_Map", ("UPDPARTGROUPID", "UPDPARTGROUPNAME")
            )
        except AccessOdbcError as e:
            logger.warning("ODBC PARTGROUP_Map query failed (%s); empty frame", e)
            gmap = pd.DataFrame(columns=["UPDPARTGROUPID", "UPDPARTGROUPNAME"])
        logger.info(
            "ODBC machine lib: %s PART_Det rows from %s in %.1fs",
            len(parts),
            p.name,
            time.perf_counter() - t0,
        )
        return parts, profile, gmap
    finally:
        conn.close()


def read_table_dataframe_odbc(mdb_path: str | Path, table: str) -> pd.DataFrame:
    """Read a whole table into a DataFrame (same table-name rules as ``mdb-export``)."""
    if not re.fullmatch(r"[A-Za-z0-9_~]+", table):
        raise AccessOdbcError(f"Refusing unsafe table name: {table!r}")
    if table.upper() == "PART_DET":
        return load_part_det_dataframe_odbc(mdb_path)
    p = Path(mdb_path)
    conn = connect_mdb(p, read_only=False)
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
