# SPDX-License-Identifier: MIT
"""EqualWidthTabBar size hints."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from themes.equal_tab_bar import (
    TAB_H_PAD_PX,
    TAB_ICON_GAP_PX,
    TAB_WIDTH_SLACK_PX,
    EqualWidthTabBar,
    recompute_equal_tab_widths,
)


def _qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_equal_tab_bar_content_width() -> None:
    _qapp()
    tabs = QtWidgets.QTabWidget()
    bar = EqualWidthTabBar()
    tabs.setTabBar(bar)
    tabs.addTab(QtWidgets.QWidget(), "A")
    tabs.addTab(QtWidgets.QWidget(), "MUCH LONGER LABEL")
    tabs.addTab(QtWidgets.QWidget(), "Mid")
    bar.recompute_uniform_width()
    widths = [bar.tabSizeHint(i).width() for i in range(3)]
    assert widths[0] < widths[1]
    assert widths[2] < widths[1]
    font = QtGui.QFont(bar.font())
    font.setBold(True)
    fm = QtGui.QFontMetrics(font)
    longest = "MUCH LONGER LABEL"
    need = fm.horizontalAdvance(longest) + TAB_H_PAD_PX + TAB_WIDTH_SLACK_PX
    assert widths[1] >= need


def test_equal_tab_bar_recompute_after_text_change() -> None:
    _qapp()
    tabs = QtWidgets.QTabWidget()
    bar = EqualWidthTabBar()
    tabs.setTabBar(bar)
    tabs.addTab(QtWidgets.QWidget(), "X")
    bar.recompute_uniform_width()
    narrow = bar.tabSizeHint(0).width()
    tabs.setTabText(0, "XXXXXXXXXXXXXXXX")
    recompute_equal_tab_widths(tabs)
    assert bar.tabSizeHint(0).width() >= narrow


def test_equal_tab_bar_min_height() -> None:
    _qapp()
    tabs = QtWidgets.QTabWidget()
    bar = EqualWidthTabBar()
    tabs.setTabBar(bar)
    tabs.addTab(QtWidgets.QWidget(), "Hi")
    bar.set_min_tab_height(40)
    assert bar.tabSizeHint(0).height() >= 40


def test_equal_tab_bar_fits_merge_export_with_icon() -> None:
    _qapp()
    tabs = QtWidgets.QTabWidget()
    bar = EqualWidthTabBar()
    tabs.setTabBar(bar)
    bar.setIconSize(QtCore.QSize(16, 16))
    pix = QtGui.QPixmap(16, 16)
    pix.fill(QtGui.QColor("white"))
    icon = QtGui.QIcon(pix)
    label = "MERGE / EXPORT"
    tabs.addTab(QtWidgets.QWidget(), icon, label)
    bar.recompute_uniform_width()
    font = QtGui.QFont(bar.font())
    font.setBold(True)
    fm = QtGui.QFontMetrics(font)
    need = (
        max(fm.horizontalAdvance(label), fm.boundingRect(label).width())
        + 16
        + TAB_ICON_GAP_PX
        + TAB_H_PAD_PX
        + TAB_WIDTH_SLACK_PX
    )
    assert bar.tabSizeHint(0).width() >= need


def test_equal_tab_bar_draw_base_off() -> None:
    _qapp()
    bar = EqualWidthTabBar()
    assert bar.drawBase() is False
