# SPDX-License-Identifier: MIT
"""Main-window tab bar: each tab sized to its label (no equal-width stretch)."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

# Total left+right content pad; keep in sync with QSS padding on #valvetMainTabs tabs.
TAB_H_PAD_PX = 20
TAB_ICON_GAP_PX = 6
TAB_WIDTH_SLACK_PX = 2
TAB_MIN_WIDTH_PX = 48
TAB_MIN_HEIGHT_DEFAULT = 22
TAB_MIN_HEIGHT_LO = 18
TAB_MIN_HEIGHT_HI = 48


def clamp_tab_min_height(h: int) -> int:
    return max(TAB_MIN_HEIGHT_LO, min(TAB_MIN_HEIGHT_HI, int(h)))


class EqualWidthTabBar(QtWidgets.QTabBar):
    """Tab widths follow text + icon; not stretched to the longest sibling."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._widths: list[int] = []
        self._min_tab_height = TAB_MIN_HEIGHT_DEFAULT
        self._h_pad = TAB_H_PAD_PX
        self.setDrawBase(False)
        self.setAutoFillBackground(False)

    def set_min_tab_height(self, h: int) -> None:
        self._min_tab_height = clamp_tab_min_height(h)
        self.recompute_uniform_width()

    def set_horizontal_padding(self, px: int) -> None:
        self._h_pad = max(0, int(px))
        self.recompute_uniform_width()

    def _metrics_font(self) -> QtGui.QFont:
        font = QtGui.QFont(self.font())
        font.setBold(True)
        return font

    def _width_for_index(self, index: int, fm: QtGui.QFontMetrics) -> int:
        text = self.tabText(index)
        text_w = max(fm.horizontalAdvance(text), fm.boundingRect(text).width())
        extra = 0
        if not self.tabIcon(index).isNull():
            extra = self.iconSize().width() + TAB_ICON_GAP_PX
        return max(TAB_MIN_WIDTH_PX, text_w + extra + self._h_pad + TAB_WIDTH_SLACK_PX)

    def recompute_uniform_width(self) -> None:
        fm = QtGui.QFontMetrics(self._metrics_font())
        self._widths = [self._width_for_index(i, fm) for i in range(self.count())]
        self.updateGeometry()
        self.update()

    def tabSizeHint(self, index: int) -> QtCore.QSize:
        base = super().tabSizeHint(index)
        h = max(base.height(), self._min_tab_height)
        if 0 <= index < len(self._widths):
            w = self._widths[index]
        else:
            w = self._width_for_index(index, QtGui.QFontMetrics(self._metrics_font()))
        return QtCore.QSize(w, h)

    def minimumTabSizeHint(self, index: int) -> QtCore.QSize:
        return self.tabSizeHint(index)


def recompute_equal_tab_widths(tab_widget: QtWidgets.QTabWidget) -> None:
    bar = tab_widget.tabBar()
    if isinstance(bar, EqualWidthTabBar):
        bar.recompute_uniform_width()
