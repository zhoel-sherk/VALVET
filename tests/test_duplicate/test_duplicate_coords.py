"""Duplicate XY detection via SMTDataProcessor.cross_check() (same stack as the GUI)."""

from __future__ import annotations

import os
import sys

import pytest

tests_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

import smt_processor


def _asset(name: str) -> str:
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), name)


def _processor_for_csv_pair(
    bom_name: str, pnp_name: str
) -> smt_processor.SMTDataProcessor:
    bom_df = smt_processor.read_file(_asset(bom_name), separator=",")
    pnp_df = smt_processor.read_file(_asset(pnp_name), separator=",")
    bom_cfg = smt_processor.ColumnConfig(
        designator="Designator",
        comment="Comment",
        separator=",",
    )
    pnp_cfg = smt_processor.ColumnConfig(
        designator="Designator",
        comment="Comment",
        coord_x="Mid-X",
        coord_y="Mid-Y",
        layer="Layer",
        footprint="Footprint",
        rotation="Rotation",
        separator=",",
    )
    return smt_processor.SMTDataProcessor(
        smt_processor.ProcessorConfig()
    ).set_dataframes(bom_df, pnp_df, bom_cfg, pnp_cfg)


def test_duplicate_coords_absent_for_normal_pnp():
    proc = _processor_for_csv_pair("test_bom.csv", "test_pnp1.csv")
    df = proc.cross_check()
    dups = df[df["IssueType"] == "duplicate_coord"]
    assert dups.empty


def test_duplicate_coords_detect_exact_xy_match():
    proc = _processor_for_csv_pair("test_bom.csv", "test_pnp2.csv")
    df = proc.cross_check()
    dups = df[df["IssueType"] == "duplicate_coord"]
    assert len(dups) >= 1
    des = " ".join(dups["Designator"].astype(str))
    assert "C1" in des and "C2" in des
    pv = str(dups.iloc[0]["PnP_Value"])
    assert "50" in pv and "60" in pv and "layer" in pv.lower()


def test_cross_check_requires_pnp_when_bom_loaded():
    proc = smt_processor.SMTDataProcessor()
    bom_df = __import__("pandas").DataFrame({"Designator": ["R1"], "Comment": ["x"]})
    bom_cfg = smt_processor.ColumnConfig(designator="Designator", comment="Comment")
    proc.set_dataframes(
        bom_df, None, bom_cfg, smt_processor.ColumnConfig(designator="Designator")
    )
    with pytest.raises(smt_processor.SMTEmptyDataError, match="PnP"):
        proc.cross_check()
