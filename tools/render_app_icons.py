"""Rasterize img/icon.svg to PNG + multi-size ICO (PySide6 + Pillow)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "img" / "icon.svg"
OUT_DIR = ROOT / "img"


def _qimage(renderer, size: int):
    from PySide6 import QtCore, QtGui

    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def render() -> None:
    from PySide6 import QtSvg, QtWidgets
    from PIL import Image

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    renderer = QtSvg.QSvgRenderer(str(SVG))
    for size in (256, 512):
        path = OUT_DIR / f"icon-{size}.png"
        _qimage(renderer, size).save(str(path), "PNG")
        print("wrote", path)
    ico_path = OUT_DIR / "icon.ico"
    Image.open(OUT_DIR / "icon-256.png").convert("RGBA").save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
    )
    print("wrote", ico_path)
    if QtWidgets.QApplication.instance() is app:
        app.quit()


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    render()
