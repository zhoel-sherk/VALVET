"""Non-modal Cross-check window smoke."""

from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("PySide6")


def _qapp():
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_cross_check_result_window_present_clean_and_issues() -> None:
    _qapp()

    from qt_models import SortableTableModel
    from ui.cross_check_window import CrossCheckResultWindow

    model = SortableTableModel(pd.DataFrame())
    copies: list[int] = []
    win = CrossCheckResultWindow(
        model=model,
        on_copy=lambda: copies.append(1),
        on_save=lambda: copies.append(2),
        parent=None,
    )
    try:
        win.present(clean=True, filtered=pd.DataFrame(), has_html=False)
        assert win.isVisible()
        assert not win.btn_proceed.isVisible()
        df = pd.DataFrame(
            {
                "Designator": ["C1"],
                "IssueType": ["missing_in_pnp"],
                "Severity": ["critical"],
            }
        )
        model.update_dataframe(df)
        win.present(clean=False, filtered=df, has_html=True)
        assert win.btn_proceed.isVisible()
        assert win.btn_copy_html.isEnabled()
        win.btn_copy_html.click()
        assert copies == [1]
    finally:
        win.hide()


def test_cross_check_close_event_emits_return_once() -> None:
    from unittest.mock import MagicMock

    _qapp()
    from qt_models import SortableTableModel
    from ui.cross_check_window import CrossCheckResultWindow

    win = CrossCheckResultWindow(
        model=SortableTableModel(pd.DataFrame()),
        on_copy=lambda: None,
        on_save=lambda: None,
        parent=None,
    )
    returns: list[int] = []
    ev = MagicMock()

    def _on_return() -> None:
        returns.append(1)
        win.closeEvent(ev)

    win.returnRequested.connect(_on_return)
    try:
        win.closeEvent(ev)
        ev.ignore.assert_called()
        assert returns == [1]
    finally:
        win.hide()
