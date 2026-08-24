"""Mercury-style ``.mmd`` (INI-like) placement export for merge DataFrames.

Coordinates follow the convention seen in ``examples/mmd/MERCURY_USB_*.mmd``:
machine X/Y = **board millimetres** × 25.4. Merge rows hold raw PnP numbers; pass
``pnp_xy_are_mm=False`` when those columns are **mils** (×0.0254 to mm first).
"""

from __future__ import annotations

import math

import pandas as pd


def pnp_raw_xy_to_board_mm(
    x: float, y: float, *, pnp_xy_are_mm: bool
) -> tuple[float, float]:
    """Interpret merge/PnP numeric columns as board mm, or as mils converted to mm."""
    try:
        fx = float(x)
    except (TypeError, ValueError):
        fx = float("nan")
    try:
        fy = float(y)
    except (TypeError, ValueError):
        fy = float("nan")
    if not pnp_xy_are_mm:
        if math.isfinite(fx):
            fx *= 0.0254
        if math.isfinite(fy):
            fy *= 0.0254
    return fx, fy


def mm_to_mmd_coord(mm: float) -> float:
    """Convert board millimetres to numeric units stored in MERCURY ``.mmd`` files."""
    return float(mm) * 25.4


def _fmt_coord(v: float) -> str:
    if not math.isfinite(v):
        return "0"
    s = f"{v:.10f}".rstrip("0").rstrip(".")
    return s if s else "0"


def _rotation_mmd(rot: object) -> str:
    if rot is None or (isinstance(rot, float) and math.isnan(rot)):
        return "0"
    s = str(rot).strip()
    if not s:
        return "0"
    try:
        f = float(s)
    except (TypeError, ValueError):
        return s
    if math.isfinite(f) and abs(f - round(f)) < 1e-6:
        return str(int(round(f)))
    s2 = f"{f:.10f}".rstrip("0").rstrip(".")
    return s2 if s2 else "0"


def merge_dataframe_to_mmd_mercury(
    df: pd.DataFrame, *, pnp_xy_are_mm: bool = True
) -> str:
    """
    Build ``.mmd`` text from a merge-style DataFrame.

    Expected columns (subset used): ``Ref``, ``X``, ``Y``, ``Rotation``, ``Value``,
    ``Footprint`` — same names as ``SMTDataProcessor.merge_bom_pnp`` output.
    Row order is preserved as in ``df``.
    ``pnp_xy_are_mm``: True if ``X``/``Y`` are already millimetres; False if they are mils.
    """
    if df.empty:
        n = 0
        body: list[str] = []
    else:
        missing = [c for c in ("Ref", "X", "Y") if c not in df.columns]
        if missing:
            raise ValueError(f"merge DataFrame missing columns: {missing}")
        n = len(df)
        body = []
        for i, (_, row) in enumerate(df.iterrows(), start=1):
            ref = str(row.get("Ref", "") or "").strip()
            xmm, ymm = pnp_raw_xy_to_board_mm(
                row["X"], row["Y"], pnp_xy_are_mm=pnp_xy_are_mm
            )
            xm = mm_to_mmd_coord(xmm) if math.isfinite(xmm) else 0.0
            ym = mm_to_mmd_coord(ymm) if math.isfinite(ymm) else 0.0
            rot = _rotation_mmd(row.get("Rotation", ""))
            value = str(row.get("Value", "") or "").strip()
            line = (
                f"#{i:08d}={_fmt_coord(xm)}\t{_fmt_coord(ym)}\t{rot}\t{value}\t{ref}\t"
            )
            body.append(line)

    header = (
        "[Fiducial]\n"
        "Fid1_X= 0\n"
        "Fid1_Y= 0\n"
        "Fid2_X= 0\n"
        "Fid2_Y= 0\n"
        "[Part Info]\n"
        "Coordinate Transform=NO\n"
        f"Part Count={n}\n"
    )
    return header + ("\n".join(body) + ("\n" if body else ""))
