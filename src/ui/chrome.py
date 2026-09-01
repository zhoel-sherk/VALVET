"""Shared Qt 6 chrome: rails, equal action buttons, help, wide combo popups."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6 import QtWidgets

LEFT_RAIL_W = 200
ACTION_BTN_MIN_H = 32
ACTION_BTN_MIN_W = 128
# Clean BOM toolbar: Learn/Save −10% vs 40×152, then Import/Convert/Apply match.
CLEAN_PRIMARY_BTN_MIN_H = 32
CLEAN_PRIMARY_BTN_MIN_W = 137
CLEAN_SECONDARY_BTN_MIN_H = 32
CHROME_MARGIN = 6
CHROME_SPACING = 8


def left_rail_widget(parent: QtWidgets.QWidget | None = None) -> QtWidgets.QWidget:
    rail = QtWidgets.QWidget(parent)
    rail.setFixedWidth(LEFT_RAIL_W)
    rail.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Fixed,
        QtWidgets.QSizePolicy.Policy.Preferred,
    )
    return rail


def action_button(
    text: str = "",
    *,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QPushButton:
    btn = QtWidgets.QPushButton(text, parent)
    btn.setMinimumHeight(ACTION_BTN_MIN_H)
    btn.setMinimumWidth(ACTION_BTN_MIN_W)
    btn.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Fixed,
    )
    return btn


def size_toolbar_button(btn: QtWidgets.QPushButton) -> None:
    hint_w = int(btn.sizeHint().width())
    btn.setMinimumWidth(max(ACTION_BTN_MIN_W, hint_w))


def toolbar_button(
    text: str = "",
    *,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QPushButton:
    btn = QtWidgets.QPushButton(text, parent)
    btn.setMinimumHeight(ACTION_BTN_MIN_H)
    btn.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Minimum,
        QtWidgets.QSizePolicy.Policy.Fixed,
    )
    size_toolbar_button(btn)
    return btn


def switch_checkbox(
    text: str = "",
    *,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QCheckBox:
    chk = QtWidgets.QCheckBox(text, parent)
    return chk


def segmented_control(
    labels: Sequence[str],
    *,
    parent: QtWidgets.QWidget | None = None,
    ids: Sequence[int] | None = None,
) -> tuple[
    QtWidgets.QFrame,
    QtWidgets.QButtonGroup,
    tuple[QtWidgets.QPushButton, ...],
]:
    """Exclusive checkable buttons in a row (iOS segmented control)."""
    texts = [str(x) for x in labels]
    if not texts:
        raise ValueError("segmented_control requires at least one label")
    if ids is not None and len(ids) != len(texts):
        raise ValueError("ids length must match labels")
    frame = QtWidgets.QFrame(parent)
    frame.setObjectName("segmented")
    frame.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Expanding,
        QtWidgets.QSizePolicy.Policy.Fixed,
    )
    row = QtWidgets.QHBoxLayout(frame)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    group = QtWidgets.QButtonGroup(frame)
    group.setExclusive(True)
    buttons: list[QtWidgets.QPushButton] = []
    n = len(texts)
    for i, text in enumerate(texts):
        btn = QtWidgets.QPushButton(text, frame)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        btn.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        btn.setMinimumWidth(0)
        if i == 0:
            role = "first"
        elif i == n - 1:
            role = "last"
        else:
            role = "mid"
        btn.setProperty("seg", role)
        if ids is not None:
            group.addButton(btn, int(ids[i]))
        else:
            group.addButton(btn)
        row.addWidget(btn, 1)
        buttons.append(btn)
    return frame, group, tuple(buttons)


def help_button(
    slot: object,
    *,
    parent: QtWidgets.QWidget | None = None,
) -> QtWidgets.QToolButton:
    btn = QtWidgets.QToolButton(parent)
    btn.setText("?")
    btn.setAutoRaise(True)
    btn.setToolTip("Help")
    btn.clicked.connect(slot)
    return btn


def apply_equal_widths(buttons: Sequence[QtWidgets.QWidget]) -> None:
    if not buttons:
        return
    w = ACTION_BTN_MIN_W
    for b in buttons:
        w = max(w, int(b.sizeHint().width()))
    for b in buttons:
        b.setMinimumWidth(w)


class WidePopupComboBox(QtWidgets.QComboBox):
    """Combo whose popup is at least as wide as the longest item (not the combo)."""

    def showPopup(self) -> None:  # type: ignore[override]
        super().showPopup()
        view = self.view()
        fm = view.fontMetrics()
        w = max(int(self.width()), 1)
        for i in range(self.count()):
            w = max(w, fm.horizontalAdvance(self.itemText(i)) + 36)
        view.setMinimumWidth(w)
        popup = view.window()
        if popup is not None and popup is not self:
            popup.setMinimumWidth(w)
