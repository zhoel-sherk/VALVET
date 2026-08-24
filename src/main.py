"""VALVET desktop entry (Validator And Line-Verified Export Tool)."""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from PySide6 import QtWidgets  # noqa: E402

from app.constants import APP_NAME, APP_VERSION, SETTINGS_ORG  # noqa: E402
from app.window import MainWindow  # noqa: E402
from themes.fonts_loader import register_bundled_fonts  # noqa: E402


def main() -> None:
    import parsers  # noqa: F401

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(SETTINGS_ORG)
    register_bundled_fonts()
    win = MainWindow()
    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
