"""One-shot Hanwha UPD dump: whitelist tables → SQLite + optional MDB copy.

ODBC / mdbtools only during import. Preview lookups are SQLite-only.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd

import logger
import machine_library.hanwha_mdbtools as mdbtools
import machine_library.upd_geometry_load as upd_geom
import pcb_preview.upd_footprint_builder as upd_fp
from machine_library.hanwha_preview import attach_part_group_type
from pcb_preview.types import FootprintOutlineMM

ProgressFn = Callable[[int, str], None]

SQLITE_NAME = "vision.sqlite"
MDB_COPY_NAME = "library.mdb"
META_NAME = "meta.json"


def sqlite_path(cache_dir: Path) -> Path:
    return Path(cache_dir) / SQLITE_NAME


def mdb_copy_path(cache_dir: Path) -> Path:
    return Path(cache_dir) / MDB_COPY_NAME


def meta_path(cache_dir: Path) -> Path:
    return Path(cache_dir) / META_NAME


def file_sha256(path: Path, *, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def cache_is_fresh(source_mdb: str | Path, cache_dir: str | Path) -> bool:
    """True when vision.sqlite exists and meta matches source path + mtime."""
    dest = Path(cache_dir)
    src = Path(source_mdb)
    if (
        not src.is_file()
        or not sqlite_path(dest).is_file()
        or not meta_path(dest).is_file()
    ):
        return False
    try:
        meta = json.loads(meta_path(dest).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return False
    if str(src.resolve()) != str(meta.get("source_path") or ""):
        return False
    st = src.stat()
    try:
        stored_size = int(meta.get("source_size", -1))
    except (TypeError, ValueError):
        stored_size = -1
    if stored_size >= 0 and stored_size != st.st_size:
        return False
    stored_ns = meta.get("source_mtime_ns")
    if stored_ns is not None:
        try:
            return int(stored_ns) == st.st_mtime_ns
        except (TypeError, ValueError):
            return False
    try:
        stored = float(meta.get("source_mtime") or 0)
    except (TypeError, ValueError):
        return False
    return abs(st.st_mtime - stored) < 0.001


def _progress(cb: ProgressFn | None, pct: int, msg: str) -> None:
    if cb is not None:
        cb(pct, msg)


def _read_mdb_table_odbc(
    odbc_conn: Any,
    table: str,
    columns: tuple[str, ...],
) -> pd.DataFrame | None:
    """Return a frame on success, or ``None`` when ODBC cannot read the table."""
    from machine_library.access_odbc import AccessOdbcError, fetch_named_columns

    try:
        df = fetch_named_columns(odbc_conn, table, columns)
    except AccessOdbcError as e:
        if table == "PART_Det":
            try:
                df = fetch_named_columns(odbc_conn, table, columns[:-1])
                df["VENDORID"] = 0
            except AccessOdbcError as e2:
                logger.warning(
                    "ODBC read of %s failed (%s); using mdbtools export",
                    table,
                    e2,
                )
                return None
        else:
            logger.warning(
                "ODBC read of %s failed (%s); using mdbtools export",
                table,
                e,
            )
            return None
    keep = [c for c in columns if c in df.columns]
    return df[keep] if keep else pd.DataFrame(columns=list(columns))


def _read_mdb_table(
    mdb_path: Path,
    table: str,
    columns: tuple[str, ...],
    odbc_conn: Any | None,
) -> pd.DataFrame:
    if odbc_conn is not None:
        df = _read_mdb_table_odbc(odbc_conn, table, columns)
        if df is not None:
            return df
    try:
        raw = mdbtools.export_table_csv(mdb_path, table)
    except mdbtools.HanwhaMdbToolsError as e:
        logger.warning(
            "mdbtools export of %s failed (%s); empty frame",
            table,
            e,
        )
        return pd.DataFrame(columns=list(columns))
    df = pd.read_csv(io.StringIO(raw))
    keep = [c for c in columns if c in df.columns]
    return df[keep] if keep else pd.DataFrame(columns=list(columns))


def _write_df_sqlite(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
    safe = table.replace('"', "")
    conn.execute(f'DROP TABLE IF EXISTS "{safe}"')
    out = df.copy()
    out.columns = [str(c) for c in out.columns]
    out.to_sql(safe, conn, if_exists="replace", index=False)
    if "PROFILENAME" in out.columns:
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS "idx_{safe}_PROFILENAME" ON "{safe}" (PROFILENAME)'
        )
    if table == "PARTGROUP_Map" and "UPDPARTGROUPID" in out.columns:
        conn.execute(
            f'CREATE INDEX IF NOT EXISTS "idx_{safe}_GID" ON "{safe}" (UPDPARTGROUPID)'
        )


def import_mdb_to_cache(
    source_mdb: str | Path,
    cache_dir: str | Path,
    *,
    progress: ProgressFn | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Copy ``source_mdb`` → ``library.mdb`` and dump whitelist tables to ``vision.sqlite``.

    Returns meta dict written to ``meta.json``. Skip ODBC when the cache is fresh
    unless ``force`` (Reload / editor save).
    """
    src = Path(source_mdb)
    dest = Path(cache_dir)
    dest.mkdir(parents=True, exist_ok=True)
    if not src.is_file():
        raise mdbtools.HanwhaMdbToolsError(f"Not a file: {src}")
    if not force and cache_is_fresh(src, dest):
        _progress(progress, 100, "SQLite cache unchanged")
        try:
            return json.loads(meta_path(dest).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            pass

    _progress(progress, 5, "Copying library.mdb…")
    copy = mdb_copy_path(dest)
    if src.resolve() != copy.resolve():
        shutil.copy2(src, copy)

    _progress(progress, 8, "Hashing source…")
    digest = file_sha256(src)
    st = src.stat()
    mtime = st.st_mtime

    spec: list[tuple[str, tuple[str, ...]]] = [
        ("PART_Det", upd_geom.PART_DET_DUMP_COLS)
    ]
    spec.extend(upd_geom.VISION_DUMP_TABLES.items())
    n_tables = len(spec)

    sql_path = sqlite_path(dest)
    if sql_path.is_file():
        sql_path.unlink()

    odbc_conn = None
    if sys.platform == "win32":
        from machine_library.access_odbc import AccessOdbcError, connect_mdb

        try:
            odbc_conn = connect_mdb(src, read_only=True)
        except AccessOdbcError as e:
            logger.warning(
                "ODBC connect failed (%s); using mdbtools for SQLite import from %s",
                e,
                src,
            )
            odbc_conn = None

    sconn = sqlite3.connect(str(sql_path))
    try:
        for i, (table, cols) in enumerate(spec):
            pct = 10 + int(80 * (i / max(n_tables, 1)))
            _progress(progress, pct, f"Import {table} ({i + 1}/{n_tables})…")
            df = _read_mdb_table(src, table, cols, odbc_conn)
            _write_df_sqlite(sconn, table, df)
        sconn.commit()
    finally:
        sconn.close()
        if odbc_conn is not None:
            odbc_conn.close()

    meta = {
        "source_path": str(src.resolve()),
        "source_mtime": mtime,
        "source_mtime_ns": st.st_mtime_ns,
        "source_size": st.st_size,
        "source_sha256": digest,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "tables": [t for t, _ in spec],
    }
    meta_path(dest).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _progress(progress, 100, "SQLite cache ready")
    return meta


def load_preview_dataframe_from_sqlite(cache_dir: str | Path) -> pd.DataFrame:
    path = sqlite_path(Path(cache_dir))
    if not path.is_file():
        return pd.DataFrame()
    conn = sqlite3.connect(str(path))
    try:
        parts = pd.read_sql_query("SELECT * FROM PART_Det", conn)
        try:
            profile = pd.read_sql_query(
                "SELECT PROFILENAME, UPDPARTGROUPID FROM PROFILE_Det", conn
            )
        except Exception:
            profile = pd.DataFrame(columns=["PROFILENAME", "UPDPARTGROUPID"])
        try:
            gmap = pd.read_sql_query(
                "SELECT UPDPARTGROUPID, UPDPARTGROUPNAME FROM PARTGROUP_Map", conn
            )
        except Exception:
            gmap = pd.DataFrame(columns=["UPDPARTGROUPID", "UPDPARTGROUPNAME"])
    finally:
        conn.close()
    return attach_part_group_type(parts, profile, gmap)


def _sqlite_table(
    conn: sqlite3.Connection,
    table: str,
    name: str,
    *,
    all_rows: bool = False,
) -> pd.DataFrame:
    safe = table.replace('"', "")
    try:
        if all_rows:
            return pd.read_sql_query(f'SELECT * FROM "{safe}"', conn)
        return pd.read_sql_query(
            f'SELECT * FROM "{safe}" WHERE PROFILENAME = ?',
            conn,
            params=(name,),
        )
    except Exception:
        return pd.DataFrame()


def load_profile_snapshot_from_sqlite(cache_dir: str | Path, profilename: str) -> Any:
    dest = Path(cache_dir)
    name = (profilename or "").strip()
    if not name or not sqlite_path(dest).is_file():
        return upd_fp.UpdProfileSnapshot(profilename="")
    conn = sqlite3.connect(str(sqlite_path(dest)))
    try:
        tables: dict[str, pd.DataFrame] = {}
        for table in upd_geom.VISION_DUMP_TABLES:
            tables[table] = _sqlite_table(
                conn, table, name, all_rows=(table == "PARTGROUP_Map")
            )
        snap = upd_geom.snapshot_from_table_map(tables, name)
        parent = snap.parentprofile
        vt = snap.vision_type
        missing_ll = vt == 1 and snap.ll_whole is None
        missing_chip = vt == 3 and snap.chip_whole is None
        if (missing_ll or missing_chip) and parent and parent != name:
            return load_profile_snapshot_from_sqlite(dest, parent)
        return snap
    finally:
        conn.close()


def build_outline_from_sqlite(
    cache_dir: str | Path, profilename: str, *, partdesc: str = ""
) -> upd_fp.FootprintBuildResult:
    name = (profilename or "").strip()
    if not name:
        return upd_fp.FootprintBuildResult(
            outline=FootprintOutlineMM(source="none"),
            vision_type=0,
            partgroup_name="",
            partdesc=partdesc,
            size_x_mm=0.0,
            size_y_mm=0.0,
            size_z_mm=0.0,
            pin1_x_mm=0.0,
            pin1_y_mm=0.0,
            warnings=(),
            error="empty profile name",
        )
    snap = load_profile_snapshot_from_sqlite(cache_dir, name)
    if partdesc:
        snap.partdesc = partdesc
    return upd_fp.build_from_snapshot(snap)
