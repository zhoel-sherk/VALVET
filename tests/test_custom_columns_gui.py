"""Custom role in the BOM/PnP mapping dropdowns and the Merge plumbing."""

from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from app.constants import _BOM_MAPPING_ROLES, _PNP_MAPPING_ROLES  # noqa: E402
from services.column_mapping import (  # noqa: E402
    CUSTOM_ROLE,
    PNP_EXCLUSIVE_ROLES,
)


def test_custom_is_offered_in_both_tabs() -> None:
    assert CUSTOM_ROLE == "Custom"
    assert CUSTOM_ROLE in _BOM_MAPPING_ROLES
    assert CUSTOM_ROLE in _PNP_MAPPING_ROLES


def test_pnp_custom_is_not_exclusive() -> None:
    """Every other PnP role is exclusive; Custom must not be."""
    assert CUSTOM_ROLE not in PNP_EXCLUSIVE_ROLES
    assert "REF" in PNP_EXCLUSIVE_ROLES
    assert "Rotation" in PNP_EXCLUSIVE_ROLES


def test_two_pnp_custom_columns_can_coexist(main_window) -> None:
    pnp = pd.DataFrame(
        [["R1", "1", "2", "0", "0603"]], columns=["0", "1", "2", "3", "4"]
    )
    main_window._pnp_df = pnp
    main_window.pnp_model.update_dataframe(pnp)
    main_window._fill_pnp_combos(
        preserved_roles=["Custom", "Custom", "X", "Y", "Rotation"]
    )

    roles = [main_window._mapping_combo_role(c) for c in main_window.pnp_col_combos]
    assert roles[:2] == ["Custom", "Custom"]

    # Re-picking Custom on another column must not clear the first one.
    main_window._on_pnp_col_mapping_changed(1, "Custom")
    roles = [main_window._mapping_combo_role(c) for c in main_window.pnp_col_combos]
    assert roles[0] == "Custom"


def test_two_bom_custom_columns_can_coexist(main_window) -> None:
    bom = pd.DataFrame([["IN-1", "PN", "-", "R1"]], columns=["0", "1", "2", "3"])
    main_window._bom_df = bom
    main_window.bom_model.update_dataframe(bom)
    main_window._fill_bom_combos(preserved_roles=["Custom", "Comment", "-", "REF"])

    roles = [main_window._mapping_combo_role(c) for c in main_window.bom_col_combos]
    assert roles[0] == "Custom"
    assert roles[3] == "REF"


def test_merge_config_receives_custom_columns(main_window) -> None:
    bom = pd.DataFrame(
        [
            ["IN-00004817", "PN-A", "R1,R2"],
            ["IN-00004818", "PN-B", "R3"],
        ],
        columns=["0", "1", "2"],
    )
    pnp = pd.DataFrame(
        [["R1", "1", "2", "0", "0603"], ["R3", "3", "4", "0", "0402"]],
        columns=["0", "1", "2", "3", "4"],
    )
    main_window._bom_df = bom
    main_window._pnp_df = pnp
    main_window.bom_model.update_dataframe(bom)
    main_window.pnp_model.update_dataframe(pnp)
    main_window._fill_bom_combos(preserved_roles=["Custom", "Comment", "REF"])
    main_window._fill_pnp_combos(
        preserved_roles=["REF", "X", "Y", "Rotation", "Footprint"]
    )

    proc = main_window._configure_processor_from_ui()
    assert proc is not None
    assert proc._bom_config.custom == [("Custom 1", "0")]
    assert proc._pnp_config.custom == []

    merged = proc.merge_bom_pnp()
    assert "Custom 1" in merged.columns
    assert merged.set_index("Ref").at["R1", "Custom 1"] == "IN-00004817"


def test_cross_check_custom_toggle_defaults_off_and_persists(main_window) -> None:
    main_window.chk_custom.setChecked(False)
    main_window._save_report_filter_settings()
    assert (
        main_window._settings.value("report/compare_custom", False, type=bool) is False
    )

    main_window.chk_custom.setChecked(True)
    main_window._save_report_filter_settings()
    assert (
        main_window._settings.value("report/compare_custom", False, type=bool) is True
    )
    main_window.chk_custom.setChecked(False)
    main_window._save_report_filter_settings()
