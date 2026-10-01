"""BOM row highlight: model roles, cache invalidation, and dirty-state safety."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtGui, QtWidgets

from qt_models import SortableTableModel

_ROOT = Path(__file__).resolve().parents[1]
_BOM_CSV = _ROOT / "tests" / "fixtures" / "clean_corpus" / "tabular_sample.csv"


def _qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _bg(model: SortableTableModel, row: int) -> object:
    return model.data(model.index(row, 0), QtCore.Qt.ItemDataRole.BackgroundRole)


def _bg_rows(model: SortableTableModel) -> list[int]:
    return [i for i in range(model.rowCount()) if _bg(model, i) is not None]


def _model() -> SortableTableModel:
    _qapp()
    return SortableTableModel(
        pd.DataFrame(
            {
                "ref": ["C1", "PC6501", "C2", "JUMP2"],
                "desc": [
                    "MLCC_10uF_SMD",
                    "SCAP_100uF_PL_25V_DIP_2",
                    "MLCC_1uF_SMD",
                    "Short circuit cap_2PIN_DIP",
                ],
                "pn": ["0402", "250AREP101M06X5", "0603", "PH2.54-2P"],
            }
        )
    )


# ------------------------------------------------------------------ matching


def test_highlight_matches_substring_in_any_column() -> None:
    m = _model()
    assert m.set_highlight_tokens("DIP") == 2


def test_highlight_is_case_insensitive() -> None:
    m = _model()
    m.set_highlight_tokens("dip")
    assert _bg_rows(m) == [1, 3]
    m.set_highlight_tokens("DiP")
    assert _bg_rows(m) == [1, 3]


def test_highlight_multiple_tokens_are_or() -> None:
    m = _model()
    assert m.set_highlight_tokens("DIP 0603") == 3


def test_highlight_token_inside_description_matches() -> None:
    """'DIP' appears as a fragment ('..._DIP_2'), not as a whole cell value."""
    m = _model()
    m.set_highlight_tokens("DIP")
    assert _bg_rows(m) == [1, 3]


def test_highlight_whole_cell_only_would_not_match() -> None:
    """Guards the mode: substring, not exact cell equality."""
    m = _model()
    assert m.set_highlight_tokens("250AREP101M06X5") == 1


def test_highlight_no_tokens_clears() -> None:
    m = _model()
    m.set_highlight_tokens("DIP")
    assert _bg_rows(m)
    m.set_highlight_tokens("   ")
    assert _bg_rows(m) == []
    assert m.highlighted_row_count() == 0


def test_highlight_single_character_token_ignored() -> None:
    """One letter would match nearly every row and be useless."""
    m = _model()
    assert m.set_highlight_tokens("C") == 0


def test_highlight_deduplicates_tokens() -> None:
    m = _model()
    m.set_highlight_tokens("DIP dip DIP")
    assert m.highlight_tokens() == ("dip",)


def test_highlight_background_is_a_brush() -> None:
    m = _model()
    m.set_highlight_tokens("DIP")
    assert isinstance(_bg(m, 1), QtGui.QBrush)


def test_highlight_background_is_none_on_non_match() -> None:
    m = _model()
    m.set_highlight_tokens("DIP")
    assert _bg(m, 0) is None


def test_highlight_amber_colour() -> None:
    m = _model()
    m.set_highlight_tokens("DIP")
    colour = _bg(m, 1).color()
    assert colour.red() > colour.blue()  # amber is warm


def test_highlight_empty_dataframe_is_safe() -> None:
    _qapp()
    m = SortableTableModel(pd.DataFrame())
    assert m.set_highlight_tokens("DIP") == 0


def test_highlight_on_nan_cells_does_not_crash() -> None:
    _qapp()
    m = SortableTableModel(pd.DataFrame({"a": [1.0, None], "b": ["DIP", "x"]}))
    assert m.set_highlight_tokens("DIP") == 1


# ------------------------------------------------------------ cache lifecycle


def _highlighted_refs(model: SortableTableModel) -> list[str]:
    """Value of column 0 for every tinted row - position independent."""
    df = model.get_dataframe().reset_index(drop=True)
    return [str(df.iloc[i, 0]) for i in _bg_rows(model)]


def test_highlight_survives_sort() -> None:
    """sort_values shuffles index labels; rows are addressed positionally."""
    m = _model()
    m.set_highlight_tokens("DIP")
    assert sorted(_highlighted_refs(m)) == ["JUMP2", "PC6501"]
    m.sort(0, QtCore.Qt.SortOrder.DescendingOrder)
    assert sorted(_highlighted_refs(m)) == ["JUMP2", "PC6501"]
    assert m.highlighted_row_count() == 2


def test_highlight_recomputed_after_sort_reorders_content() -> None:
    m = _model()
    m.set_highlight_tokens("0603")
    assert _highlighted_refs(m) == ["C2"]
    m.sort(0, QtCore.Qt.SortOrder.DescendingOrder)
    # The content check is the real assertion: a stale positional cache would
    # keep tinting the row that used to hold C2.
    assert _highlighted_refs(m) == ["C2"]
    assert m.highlighted_row_count() == 1


def test_highlight_invalidated_by_update_dataframe() -> None:
    m = _model()
    assert m.set_highlight_tokens("DIP") == 2
    m.update_dataframe(pd.DataFrame({"ref": ["DIP a", "DIP b"], "desc": ["", ""]}))
    assert m.highlighted_row_count() == 2


def test_highlight_update_dataframe_to_empty_clears() -> None:
    m = _model()
    m.set_highlight_tokens("DIP")
    m.update_dataframe(pd.DataFrame())
    assert m.highlighted_row_count() == 0
    assert _bg_rows(m) == []


# --------------------------------------------------------------- dirty safety


def _window(settings: QtCore.QSettings):
    from app.window import MainWindow

    win = MainWindow(settings=settings)
    return win


def _tmp_settings(tmp_path: Path) -> QtCore.QSettings:
    return QtCore.QSettings(str(tmp_path / "hl.ini"), QtCore.QSettings.Format.IniFormat)


def test_highlight_does_not_mark_bom_dirty(tmp_path: Path) -> None:
    """Toggling the highlight must not edit the working copy or trigger autosave."""
    _qapp()
    win = _window(_tmp_settings(tmp_path))
    try:
        win._load_bom(str(_BOM_CSV), force_original=True)
        assert win._bom_dirty is False
        win.chk_bom_highlight.setChecked(True)
        win.edit_bom_highlight.setText("DIP")
        win._apply_bom_highlight(log=False)
        assert win._bom_dirty is False
        win._apply_bom_highlight(log=False)
        assert win._bom_dirty is False
    finally:
        win.close()


def test_real_cell_edit_still_marks_bom_dirty(tmp_path: Path) -> None:
    """The role gate must not swallow genuine edits."""
    _qapp()
    win = _window(_tmp_settings(tmp_path))
    try:
        win._load_bom(str(_BOM_CSV), force_original=True)
        win._bom_dirty = False
        model = win.bom_model
        model.setData(model.index(0, 0), "EDITED", QtCore.Qt.ItemDataRole.EditRole)
        assert win._bom_dirty is True
    finally:
        win.close()


def test_highlight_tokens_roundtrip_in_qsettings(tmp_path: Path) -> None:
    _qapp()
    from settings_paths import path_settings_hash

    s = _tmp_settings(tmp_path)
    path = str(_BOM_CSV)
    group = f"bom/ui/{path_settings_hash(path)}"

    win = _window(_tmp_settings(tmp_path))
    try:
        win._load_bom(path, force_original=True)
        win.chk_bom_highlight.setChecked(True)
        win.edit_bom_highlight.setText("DIP THT")
        win._save_bom_tab_settings_to_disk()
    finally:
        win.close()

    s.beginGroup(group)
    assert s.value("highlight_on", False, type=bool) is True
    assert str(s.value("highlight_tokens", "")) == "DIP THT"
    s.endGroup()


def test_highlight_restored_for_same_file(tmp_path: Path) -> None:
    _qapp()
    win = _window(_tmp_settings(tmp_path))
    try:
        win._load_bom(str(_BOM_CSV), force_original=True)
        win.chk_bom_highlight.setChecked(True)
        win.edit_bom_highlight.setText("DIP")
        # Typing is debounced in the UI; drive the apply directly here.
        win._apply_bom_highlight(log=False)
        win._save_bom_tab_settings_to_disk()
        assert win.bom_model.highlight_tokens() == ("dip",)

        win._load_bom(str(_BOM_CSV), force_original=True)
        assert win.chk_bom_highlight.isChecked() is True
        assert win.edit_bom_highlight.text() == "DIP"
        assert win.bom_model.highlight_tokens() == ("dip",)
    finally:
        win.close()


def test_clear_workspace_resets_highlight(tmp_path: Path) -> None:
    _qapp()
    win = _window(_tmp_settings(tmp_path))
    try:
        win._load_bom(str(_BOM_CSV), force_original=True)
        win.chk_bom_highlight.setChecked(True)
        win.edit_bom_highlight.setText("DIP")
        win._apply_bom_highlight(log=False)
        win._clear_bom_workspace()
        assert win.chk_bom_highlight.isChecked() is False
        assert win.edit_bom_highlight.text() == ""
        assert win.bom_model.highlight_tokens() == ()
    finally:
        win.close()
