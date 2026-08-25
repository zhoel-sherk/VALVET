"""Read-only Hanwha UPD .mdb helpers for the CLI."""

from __future__ import annotations

from machine_library.hanwha_mdbtools import (
    HanwhaMdbToolsError,
    list_mdb_tables,
    load_part_det_from_mdb,
)


def format_tables(mdb_path: str) -> str:
    names = list_mdb_tables(mdb_path)
    if not names:
        return "(no tables)"
    return "\n".join(names)


def format_part_det(mdb_path: str, *, limit: int = 50) -> str:
    rows = load_part_det_from_mdb(mdb_path)
    if not rows:
        return "(empty PART_Det)"
    lines = [f"PART_Det: {len(rows)} row(s)", "PARTNAME\tPROFILENAME\tPARTDESC"]
    for r in rows[: max(0, limit)]:
        lines.append(f"{r.partname}\t{r.profilename}\t{r.partdesc}")
    if len(rows) > limit:
        lines.append(f"… {len(rows) - limit} more")
    return "\n".join(lines)


__all__ = [
    "HanwhaMdbToolsError",
    "format_part_det",
    "format_tables",
    "list_mdb_tables",
    "load_part_det_from_mdb",
]
