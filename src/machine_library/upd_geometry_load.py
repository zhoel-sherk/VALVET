"""Load one Hanwha UPD profile's vision tables into an UpdProfileSnapshot."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd

import logger
import machine_library.hanwha_mdbtools as mdbtools
import pcb_preview.upd_footprint_builder as upd_fp
from pcb_preview.types import FootprintOutlineMM

_PROFILE_COLS = (
    "PROFILENAME",
    "UPDPARTGROUPID",
    "FUNCTIONAL_TYPE_ID",
    "PARENTPROFILE",
)
_COMDATA_COLS = (
    "PROFILENAME",
    "SIZEX",
    "SIZEY",
    "SIZEZ",
    "PIN1XPOS",
    "PIN1YPOS",
    "POLARIZED",
)
_GROUP_COLS = ("UPDPARTGROUPID", "UPDPARTGROUPNAME", "VISIONTYPE")
_COMMON_COLS = ("PROFILENAME", "PIN1INDICATOR", "PIN2INDICATOR")
_CHIP_COLS = (
    "PROFILENAME",
    "TYPSIZEX",
    "TYPSIZEY",
    "EXPARAM11",
    "EXPARAM12",
    "EXPARAM13",
    "EXPARAM14",
    "EXPARAM15",
    "EXPARAM16",
    "EXPARAM18",
    "EXPARAM19",
)
_LL_WHOLE_COLS = (
    "PROFILENAME",
    "TYPSIZEX",
    "TYPSIZEY",
    "LEADTYPE",
    "LEADPARAMNUM",
    "LEADGROUPNUM",
)
_LL_GROUP_COLS = (
    "PROFILENAME",
    "INDEX",
    "ANGLE",
    "RADCENTER",
    "TANCENTER",
    "LEADNUM",
    "LEADPARAMNO",
    "GAPNUM",
)
_LL_PARAM_COLS = (
    "PROFILENAME",
    "INDEX",
    "TYPWIDTH",
    "TYPLENGTH",
    "TYPPITCH",
    "TYPFOOT",
)
_LL_GAP_COLS = ("PROFILENAME", "LGINDEX", "INDEX", "STARTNO", "MISSLEADNUM")
_BGA_WHOLE_COLS = (
    "PROFILENAME",
    "TYPSIZEX",
    "TYPSIZEY",
    "BALLPARAMCOUNT",
    "BALLGROUPCOUNT",
    "APPEARBALLSIZE",
)
_BGA_PARAM_COLS = (
    "PROFILENAME",
    "INDEX",
    "TYPBALLDIA",
    "TYPBALLPITCHR",
    "TYPBALLPITCHT",
)
_BGA_GROUP_COLS = (
    "PROFILENAME",
    "INDEX",
    "PARAMINDEX",
    "GRIDTYPE",
    "GRIDANGLE",
    "NUMBALLSR",
    "NUMBALLST",
    "NUMMISSING",
)
_BGA_GAP_COLS = (
    "PROFILENAME",
    "BGINDEX",
    "INDEX",
    "MISSBLOCKR",
    "MISSBLOCKT",
    "NUMMISSINGR",
    "NUMMISSINGT",
)
_POLY_WHOLE_COLS = (
    "PROFILENAME",
    "VERTEXNUM",
    "BODYSIZEX",
    "BODYSIZEY",
    "USESUB",
)
_POLY_VERT_COLS = (
    "PROFILENAME",
    "INDEX",
    "VERTEXPOINTX",
    "VERTEXPOINTY",
    "CONTROLBIT",
    "POLYGONGROUPINDEX",
)
_FLIP_WHOLE_COLS = ("PROFILENAME", "TYPSIZEX", "TYPSIZEY", "APPEARBALLSIZE")
_FLIP_PARAM_COLS = (
    "PROFILENAME",
    "INDEX",
    "TYPBALLDIA",
    "TYPBALLPITCHR",
    "TYPBALLPITCHT",
)
_FLIP_BALL_COLS = ("PROFILENAME", "INDEX", "POSITIONX", "POSITIONY")

_CSV_CACHE: dict[tuple[str, float, str], pd.DataFrame] = {}

PART_DET_DUMP_COLS = (
    "PARTNAME",
    "PROFILENAME",
    "PARTDESC",
    "CONFIDENCE_LEVEL",
    "USED_MACHINE_SET",
    "VENDORID",
)

VISION_DUMP_TABLES: dict[str, tuple[str, ...]] = {
    "PROFILE_Det": _PROFILE_COLS,
    "PROFILECOMDATA_Det": _COMDATA_COLS,
    "VISION_COMMONDATA_Det": _COMMON_COLS,
    "PARTGROUP_Map": _GROUP_COLS,
    "VISION_CHIP_WHOLE_Det": _CHIP_COLS,
    "VISION_LL_WHOLE_Det": _LL_WHOLE_COLS,
    "VISION_LL_GROUP_Det": _LL_GROUP_COLS,
    "VISION_LL_PARAM_Det": _LL_PARAM_COLS,
    "VISION_LL_GAP_Det": _LL_GAP_COLS,
    "VISION_BGA_WHOLE_Det": _BGA_WHOLE_COLS,
    "VISION_BGA_PARAM_Det": _BGA_PARAM_COLS,
    "VISION_BGA_GROUP_Det": _BGA_GROUP_COLS,
    "VISION_BGA_GAP_Det": _BGA_GAP_COLS,
    "VISION_POLYGON_WHOLE_Det": _POLY_WHOLE_COLS,
    "VISION_POLYGON_POLY_Det": _POLY_VERT_COLS,
    "VISION_FLIPCHIP_WHOLE_Det": _FLIP_WHOLE_COLS,
    "VISION_FLIPCHIP_PARAM_Det": _FLIP_PARAM_COLS,
    "VISION_FLIPCHIP_BALL_Det": _FLIP_BALL_COLS,
}


def _sql_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return [{str(k): v for k, v in rec.items()} for rec in df.to_dict("records")]


def _first_row(df: pd.DataFrame) -> dict[str, Any] | None:
    recs = _df_records(df)
    return recs[0] if recs else None


def _filter_csv(
    mdb_path: Path, table: str, columns: tuple[str, ...], name: str
) -> pd.DataFrame:
    key = (str(mdb_path.resolve()), mdb_path.stat().st_mtime, table)
    cached = _CSV_CACHE.get(key)
    if cached is None:
        raw = mdbtools.export_table_csv(mdb_path, table)
        cached = pd.read_csv(io.StringIO(raw))
        _CSV_CACHE[key] = cached
        if len(_CSV_CACHE) > 24:
            _CSV_CACHE.pop(next(iter(_CSV_CACHE)))
    if "PROFILENAME" not in cached.columns:
        return pd.DataFrame(columns=list(columns))
    hit = cached[cached["PROFILENAME"].astype(str) == name]
    keep = [c for c in columns if c in hit.columns]
    if not keep:
        return pd.DataFrame(columns=list(columns))
    return hit[keep]


def _odbc_where(
    conn: Any,
    table: str,
    columns: tuple[str, ...],
    name: str,
) -> pd.DataFrame:
    import re

    from machine_library.access_odbc import AccessOdbcError, fetch_named_columns

    if not re.fullmatch(r"[A-Za-z0-9_~]+", table):
        return pd.DataFrame(columns=list(columns))
    try:
        sql = (
            "SELECT "
            + ", ".join(f"[{c}]" for c in columns)
            + f" FROM [{table}] WHERE [PROFILENAME] = {_sql_quote(name)}"
        )
        cur = conn.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            names = [str(d[0]) for d in (cur.description or ())]
        finally:
            cur.close()
        return pd.DataFrame.from_records(list(rows), columns=names or list(columns))
    except Exception:
        try:
            df = fetch_named_columns(conn, table, columns)
        except AccessOdbcError as e:
            logger.warning(
                "ODBC fetch_named_columns for %s failed (%s); empty frame",
                table,
                e,
            )
            return pd.DataFrame(columns=list(columns))
        if "PROFILENAME" not in df.columns:
            return pd.DataFrame(columns=list(columns))
        return df[df["PROFILENAME"].astype(str) == name]


def _load_tables(mdb_path: Path, name: str) -> dict[str, pd.DataFrame]:
    import sys

    tables = dict(VISION_DUMP_TABLES)
    out: dict[str, pd.DataFrame] = {}
    if sys.platform == "win32":
        from machine_library.access_odbc import AccessOdbcError, connect_mdb

        try:
            conn = connect_mdb(mdb_path, read_only=True)
        except AccessOdbcError as e:
            logger.warning(
                "ODBC connect failed (%s); using mdbtools for geometry in %s",
                e,
                mdb_path,
            )
            conn = None
        if conn is not None:
            try:
                from machine_library.access_odbc import fetch_named_columns

                for table, cols in tables.items():
                    if table == "PARTGROUP_Map":
                        try:
                            out[table] = fetch_named_columns(conn, table, cols)
                        except AccessOdbcError as e:
                            logger.warning(
                                "ODBC read of %s failed (%s); empty frame",
                                table,
                                e,
                            )
                            out[table] = pd.DataFrame(columns=list(cols))
                    else:
                        out[table] = _odbc_where(conn, table, cols, name)
                return out
            finally:
                conn.close()
    for table, cols in tables.items():
        try:
            if table == "PARTGROUP_Map":
                raw = mdbtools.export_table_csv(mdb_path, table)
                df = pd.read_csv(io.StringIO(raw))
                keep = [c for c in cols if c in df.columns]
                out[table] = df[keep] if keep else pd.DataFrame(columns=list(cols))
            else:
                out[table] = _filter_csv(mdb_path, table, cols, name)
        except mdbtools.HanwhaMdbToolsError as e:
            logger.warning(
                "mdbtools export of %s failed (%s); empty frame",
                table,
                e,
            )
            out[table] = pd.DataFrame(columns=list(cols))
    return out


def _vision_type(
    profile: dict[str, Any] | None, gmap: pd.DataFrame
) -> tuple[int, str]:
    if not profile:
        return 0, ""
    gid = upd_fp._int(upd_fp._row_get(profile, "UPDPARTGROUPID"))
    if gmap is None or gmap.empty or "UPDPARTGROUPID" not in gmap.columns:
        return 0, ""
    hit = gmap[gmap["UPDPARTGROUPID"].apply(lambda x: upd_fp._int(x) == gid)]
    if hit.empty:
        return 0, ""
    row = hit.iloc[0].to_dict()
    return upd_fp._int(upd_fp._row_get(row, "VISIONTYPE")), str(
        upd_fp._row_get(row, "UPDPARTGROUPNAME", default="") or ""
    )


def snapshot_from_table_map(
    tables: dict[str, pd.DataFrame], name: str
) -> upd_fp.UpdProfileSnapshot:
    """Build a snapshot from already-filtered (or full) table frames."""
    profile = _first_row(tables.get("PROFILE_Det", pd.DataFrame()))
    parent = str(upd_fp._row_get(profile or {}, "PARENTPROFILE", default="") or "").strip()
    vt, gname = _vision_type(profile, tables.get("PARTGROUP_Map", pd.DataFrame()))
    com = _first_row(tables.get("PROFILECOMDATA_Det", pd.DataFrame())) or {}
    return upd_fp.UpdProfileSnapshot(
        profilename=name,
        parentprofile=parent,
        vision_type=vt,
        partgroup_name=gname,
        size_x_um=upd_fp._int(upd_fp._row_get(com, "SIZEX")),
        size_y_um=upd_fp._int(upd_fp._row_get(com, "SIZEY")),
        size_z_um=upd_fp._int(upd_fp._row_get(com, "SIZEZ")),
        pin1_x_um=upd_fp._int(upd_fp._row_get(com, "PIN1XPOS")),
        pin1_y_um=upd_fp._int(upd_fp._row_get(com, "PIN1YPOS")),
        polarized=upd_fp._polarized(upd_fp._row_get(com, "POLARIZED", default=None)),
        pin1_indicator=upd_fp._int(
            upd_fp._row_get(
                _first_row(tables.get("VISION_COMMONDATA_Det", pd.DataFrame())) or {},
                "PIN1INDICATOR",
                default=0,
            )
        ),
        chip_whole=_first_row(tables.get("VISION_CHIP_WHOLE_Det", pd.DataFrame())),
        ll_whole=_first_row(tables.get("VISION_LL_WHOLE_Det", pd.DataFrame())),
        ll_groups=_df_records(tables.get("VISION_LL_GROUP_Det", pd.DataFrame())),
        ll_params=_df_records(tables.get("VISION_LL_PARAM_Det", pd.DataFrame())),
        ll_gaps=_df_records(tables.get("VISION_LL_GAP_Det", pd.DataFrame())),
        bga_whole=_first_row(tables.get("VISION_BGA_WHOLE_Det", pd.DataFrame())),
        bga_params=_df_records(tables.get("VISION_BGA_PARAM_Det", pd.DataFrame())),
        bga_groups=_df_records(tables.get("VISION_BGA_GROUP_Det", pd.DataFrame())),
        bga_gaps=_df_records(tables.get("VISION_BGA_GAP_Det", pd.DataFrame())),
        poly_whole=_first_row(tables.get("VISION_POLYGON_WHOLE_Det", pd.DataFrame())),
        poly_verts=_df_records(tables.get("VISION_POLYGON_POLY_Det", pd.DataFrame())),
        flip_whole=_first_row(tables.get("VISION_FLIPCHIP_WHOLE_Det", pd.DataFrame())),
        flip_params=_df_records(tables.get("VISION_FLIPCHIP_PARAM_Det", pd.DataFrame())),
        flip_balls=_df_records(tables.get("VISION_FLIPCHIP_BALL_Det", pd.DataFrame())),
    )


def load_profile_snapshot(
    mdb_path: str | Path, profilename: str
) -> upd_fp.UpdProfileSnapshot:
    p = Path(mdb_path)
    name = (profilename or "").strip()
    if not name:
        return upd_fp.UpdProfileSnapshot(profilename="")
    tables = _load_tables(p, name)
    snap = snapshot_from_table_map(tables, name)
    parent = snap.parentprofile
    vt = snap.vision_type
    missing_ll = vt == 1 and snap.ll_whole is None
    missing_chip = vt == 3 and snap.chip_whole is None
    if (missing_ll or missing_chip) and parent and parent != name:
        return load_profile_snapshot(p, parent)
    return snap


def build_outline_from_mdb(
    mdb_path: str | Path, profilename: str, *, partdesc: str = ""
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
    snap = load_profile_snapshot(mdb_path, name)
    if partdesc:
        snap.partdesc = partdesc
    return upd_fp.build_from_snapshot(snap)
