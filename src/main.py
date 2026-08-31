"""VALVET desktop entry (Validator And Line-Verified Export Tool)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from PySide6 import QtGui, QtWidgets  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402

import logger  # noqa: E402
from app.constants import (  # noqa: E402
    APP_EXPANSION,
    APP_NAME,
    APP_VERSION,
    SETTINGS_ORG,
)
from app.icons import application_icon_path  # noqa: E402
from app.window import MainWindow  # noqa: E402
from themes.fonts_loader import register_bundled_fonts  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    p = argparse.ArgumentParser(prog="VALVET")
    p.add_argument(
        "--smoke",
        action="store_true",
        help="Show the main window, then quit (for CI / headless smoke).",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Same as Project 'Debug logs': write logs/YYYY-MM-DD.log and verbose stderr. "
        "Does not open the Debug / advanced dialog.",
    )
    return p.parse_known_args(argv)


def main(argv: list[str] | None = None) -> None:
    args, rest = _parse_args(argv)
    logger.configure_if_debug(argv_debug=args.debug)
    import parsers  # noqa: F401

    qt_argv = [sys.argv[0], *rest] if argv is None else rest
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(qt_argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(SETTINGS_ORG)
    icon_path = application_icon_path()
    if icon_path is not None:
        icon = QtGui.QIcon(str(icon_path))
        app.setWindowIcon(icon)
    register_bundled_fonts()
    win = MainWindow(debug=bool(args.debug or logger.env_debug_enabled()))
    if icon_path is not None:
        win.setWindowIcon(QtGui.QIcon(str(icon_path)))
    win.show()
    print(f"{APP_NAME} - {APP_EXPANSION}", flush=True)
    if args.smoke or os.environ.get("VALVET_SMOKE", "").strip() in ("1", "true", "yes"):
        QTimer.singleShot(400, app.quit)
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
