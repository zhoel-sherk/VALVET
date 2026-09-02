"""Non-modal Project console window."""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class ProjectConsoleWindow(QtWidgets.QWidget):
    """Hides on close so the QTextEdit keeps receiving log lines."""

    def __init__(
        self, *, console: QtWidgets.QTextEdit, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Console")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.Window)
        self.resize(720, 420)
        root = QtWidgets.QVBoxLayout(self)
        console.setParent(self)
        console.show()
        root.addWidget(console, 1)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        event.ignore()
        self.hide()
