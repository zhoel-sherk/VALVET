"""Horizontal header with per-section mapping QComboBox widgets."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

_HEADER_COMBO_HEIGHT = 26
# Leave the section's right edge free so QHeaderView can start a column resize.
_SECTION_RESIZE_HANDLE_PX = 8


class MappingComboBox(QtWidgets.QComboBox):
    """Combo whose popup width matches the combo (column) width."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.setMinimumContentsLength(0)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)

    def showPopup(self) -> None:  # type: ignore[override]
        super().showPopup()
        w = max(int(self.width()), 1)
        view = self.view()
        view.setFixedWidth(w)
        popup = view.window()
        if popup is not None and popup is not self:
            popup.setFixedWidth(w)


class MappingHeaderView(QtWidgets.QHeaderView):
    """QHeaderView that hosts one mapping combo per section on the viewport."""

    def __init__(
        self,
        orientation: QtCore.Qt.Orientation,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(orientation, parent)
        self._combos: list[QtWidgets.QComboBox] = []
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setStretchLastSection(False)
        grip = self.style().pixelMetric(
            QtWidgets.QStyle.PixelMetric.PM_HeaderGripMargin, None, self
        )
        if grip > 0:
            self._handle_px = max(_SECTION_RESIZE_HANDLE_PX, int(grip))
        else:
            self._handle_px = _SECTION_RESIZE_HANDLE_PX
        self.setFixedHeight(_HEADER_COMBO_HEIGHT)
        self.setMinimumHeight(_HEADER_COMBO_HEIGHT)
        self.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.sectionResized.connect(self._on_section_resized)
        self.geometriesChanged.connect(self.relayout_combos)

    def combos(self) -> list[QtWidgets.QComboBox]:
        return self._combos

    def attach_table(self, table: QtWidgets.QTableView) -> None:
        table.horizontalScrollBar().valueChanged.connect(
            lambda *_a: self.relayout_combos()
        )

    def set_mapping_combos(self, combos: list[QtWidgets.QComboBox]) -> None:
        for old in self._combos:
            old.hide()
            old.setParent(None)
            old.deleteLater()
        self._combos = list(combos)
        vp = self.viewport()
        for combo in self._combos:
            combo.setParent(vp)
            combo.show()
        self.relayout_combos()

    def clear_mapping_combos(self) -> None:
        self.set_mapping_combos([])

    def relayout_combos(self) -> None:
        vp = self.viewport()
        vw = vp.width()
        h = vp.height() if vp.height() > 0 else self.height()
        n = min(len(self._combos), self.count())
        for i in range(n):
            combo = self._combos[i]
            x = int(self.sectionViewportPosition(i))
            w = int(self.sectionSize(i))
            visible = w > 0 and (x + w) > 0 and x < vw
            combo.setVisible(visible)
            if visible:
                handle = min(self._handle_px, max(0, w - 16))
                combo.setGeometry(x, 0, max(1, w - handle), h)
        for i in range(n, len(self._combos)):
            self._combos[i].setVisible(False)

    def paintSection(
        self,
        painter: QtGui.QPainter,
        rect: QtCore.QRect,
        logicalIndex: int,
    ) -> None:
        opt = QtWidgets.QStyleOptionHeader()
        self.initStyleOption(opt)
        opt.rect = rect
        opt.section = logicalIndex
        opt.text = ""
        self.style().drawControl(
            QtWidgets.QStyle.ControlElement.CE_Header, opt, painter, self
        )

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # type: ignore[override]
        super().scrollContentsBy(dx, dy)
        self.relayout_combos()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.relayout_combos()

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.relayout_combos()

    def _on_section_resized(self, _logical: int, _old: int, _new: int) -> None:
        self.relayout_combos()
