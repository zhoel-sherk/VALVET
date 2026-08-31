"""Golden MERCURY .mmd export vs examples/mmd (see module docstring for TXT↔MMD pairing)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

tests_dir = Path(__file__).resolve().parent
boomer_dir = tests_dir.parent
sys.path.insert(0, str(boomer_dir / "src"))

from mmd_export import (
    merge_dataframe_to_mmd_mercury,
    mm_to_mmd_coord,
    pnp_raw_xy_to_board_mm,
)  # noqa: E402
from pnp_coord import convert_xy_mil_to_mm_row, convert_xy_mm_to_mil_row  # noqa: E402

EXAMPLES = boomer_dir / "examples" / "mmd"


def _norm_mmd(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_mercury_placement_txt(path: Path) -> pd.DataFrame:
    """Tab-separated placement list (Ref, X_mm, Y_mm, Rot, …, Value, Footprint)."""
    rows: list[dict[str, str | float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) == 6:
            ref, xs, ys, rot, val, fp = parts
        elif len(parts) == 7:
            ref, xs, ys, rot, _empty, val, fp = parts
        else:
            raise ValueError(f"{path}: expected 6 or 7 tab columns, got {len(parts)}")
        rows.append(
            {
                "Ref": ref,
                "X": float(xs),
                "Y": float(ys),
                "Rotation": rot,
                "Value": val,
                "Footprint": fp,
                "Layer": "Top",
            }
        )
    return pd.DataFrame(rows)


def _apply_one_gui_mm_mil_mm_cycle(df: pd.DataFrame) -> pd.DataFrame:
    """
    One round-trip like PnP tab **MM→MIL** then **MIL→MM** (`pnp_coord`, four fractional digits).

    Matches ``MainWindow._pnp_convert_xy_mm_to_mil`` + ``_pnp_convert_xy_mil_to_mm`` logic on X/Y columns.
    """
    out = df.copy()
    for idx in out.index:
        xs, ys = convert_xy_mm_to_mil_row(out.at[idx, "X"], out.at[idx, "Y"])
        if not xs or not ys:
            continue
        xmm, ymm = convert_xy_mil_to_mm_row(xs, ys)
        out.at[idx, "X"] = float(xmm)
        out.at[idx, "Y"] = float(ymm)
    return out


def _df_after_mm_mil_mm_cycles(df: pd.DataFrame, n_cycles: int) -> pd.DataFrame:
    cur = df.copy()
    for _ in range(n_cycles):
        cur = _apply_one_gui_mm_mil_mm_cycle(cur)
    return cur


def _mmd_body_xy_pairs(mmd_text: str) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for line in _norm_mmd(mmd_text).splitlines():
        line = line.strip()
        if not line.startswith("#") or "=" not in line:
            continue
        rhs = line.split("=", 1)[1]
        parts = rhs.split("\t")
        if len(parts) < 2:
            continue
        pairs.append((float(parts[0]), float(parts[1])))
    return pairs


def _max_abs_drift_mmd_xy(golden_mmd: str, candidate_mmd: str) -> float:
    """Max |ΔX|, |ΔY| over placement lines (MERCURY numeric fields before rotation tab)."""
    g = _mmd_body_xy_pairs(golden_mmd)
    c = _mmd_body_xy_pairs(candidate_mmd)
    assert len(g) == len(c), (len(g), len(c))
    worst = 0.0
    for (gx, gy), (cx, cy) in zip(g, c):
        worst = max(worst, abs(gx - cx), abs(gy - cy))
    return worst


def test_mm_to_mmd_coord_matches_golden_ra1() -> None:
    assert abs(mm_to_mmd_coord(1130.766) - 28721.4564) < 0.001
    assert abs(mm_to_mmd_coord(1262.571) - 32069.3034) < 0.001


def test_mmd_export_matches_mercury_top_mmd_from_bot_txt() -> None:
    """152 rows: ``MERCURY_USB_BOT.txt`` → same body as ``MERCURY_USB_TOP.mmd``."""
    df = _parse_mercury_placement_txt(EXAMPLES / "MERCURY_USB_BOT.txt")
    expected = _norm_mmd((EXAMPLES / "MERCURY_USB_TOP.mmd").read_text(encoding="utf-8"))
    assert merge_dataframe_to_mmd_mercury(df) == expected


def test_mmd_export_matches_mercury_bot_mmd_from_top_txt() -> None:
    """73 rows: ``MERCURY_USB_TOP.txt`` → same body as ``MERCURY_USB_BOT.mmd``."""
    df = _parse_mercury_placement_txt(EXAMPLES / "MERCURY_USB_TOP.txt")
    expected = _norm_mmd((EXAMPLES / "MERCURY_USB_BOT.mmd").read_text(encoding="utf-8"))
    assert merge_dataframe_to_mmd_mercury(df) == expected


def test_mmd_export_mils_input_matches_mm_golden() -> None:
    """Same board: coordinates stored as mils → identical .mmd as mm storage."""
    df_mm = _parse_mercury_placement_txt(EXAMPLES / "MERCURY_USB_BOT.txt")
    df_mils = df_mm.copy()
    df_mils["X"] = df_mm["X"] / 0.0254
    df_mils["Y"] = df_mm["Y"] / 0.0254
    expected = merge_dataframe_to_mmd_mercury(df_mm, pnp_xy_are_mm=True)
    assert merge_dataframe_to_mmd_mercury(df_mils, pnp_xy_are_mm=False) == expected


def test_pnp_raw_xy_to_board_mm() -> None:
    x, y = pnp_raw_xy_to_board_mm(1000.0, 2000.0, pnp_xy_are_mm=False)
    assert abs(x - 25.4) < 1e-9
    assert abs(y - 50.8) < 1e-9
    assert pnp_raw_xy_to_board_mm(3.0, 4.0, pnp_xy_are_mm=True) == (3.0, 4.0)


def test_mmd_export_empty_dataframe() -> None:
    out = merge_dataframe_to_mmd_mercury(pd.DataFrame())
    assert "Part Count=0\n" in out
    assert "#00000001=" not in out


@pytest.mark.parametrize("n_cycles", [0, 1, 2, 5, 10, 20])
def test_mmd_matches_golden_after_gui_mm_mil_mm_cycles_mercury_bot_txt(
    n_cycles: int,
) -> None:
    """`MERCURY_USB_BOT.txt` mm rows → repeated MM→MIL→MM (same as PnP buttons / `pnp_coord`) → export vs `MERCURY_USB_TOP.mmd`.

    On this fixture numeric drift in MMD fields stays zero: quantization stabilizes under ×25.4 scaling.
    """
    golden = _norm_mmd((EXAMPLES / "MERCURY_USB_TOP.mmd").read_text(encoding="utf-8"))
    base = _parse_mercury_placement_txt(EXAMPLES / "MERCURY_USB_BOT.txt")
    df = _df_after_mm_mil_mm_cycles(base, n_cycles)
    cand = merge_dataframe_to_mmd_mercury(df, pnp_xy_are_mm=True)
    drift = _max_abs_drift_mmd_xy(golden, cand)
    assert drift == 0.0, f"n_cycles={n_cycles}, max_abs_drift_mmd_units={drift}"
    if n_cycles == 0:
        assert cand == golden


@pytest.mark.parametrize("n_cycles", [0, 1, 2, 5, 10])
def test_mmd_matches_golden_after_gui_mm_mil_mm_cycles_mercury_top_txt(
    n_cycles: int,
) -> None:
    """`MERCURY_USB_TOP.txt` → MM→MIL→MM cycles → export vs `MERCURY_USB_BOT.mmd` (same drift check)."""
    golden = _norm_mmd((EXAMPLES / "MERCURY_USB_BOT.mmd").read_text(encoding="utf-8"))
    base = _parse_mercury_placement_txt(EXAMPLES / "MERCURY_USB_TOP.txt")
    df = _df_after_mm_mil_mm_cycles(base, n_cycles)
    cand = merge_dataframe_to_mmd_mercury(df, pnp_xy_are_mm=True)
    drift = _max_abs_drift_mmd_xy(golden, cand)
    assert drift == 0.0, f"n_cycles={n_cycles}, max_abs_drift_mmd_units={drift}"
