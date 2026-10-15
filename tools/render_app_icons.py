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
    from PIL import Image
    from PySide6 import QtSvg, QtWidgets
    import tempfile
    import os

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    renderer = QtSvg.QSvgRenderer(str(SVG))
    
    # Generate PNG files for distribution
    for size in (256, 512):
        path = OUT_DIR / f"icon-{size}.png"
        _qimage(renderer, size).save(str(path), "PNG")
        print("wrote", path)
    
    # Generate ICO file with multiple sizes for better quality
    # Render each size separately from SVG for optimal quality
    ico_path = OUT_DIR / "icon.ico"
    temp_pngs = []
    
    try:
        # Render each required size as PNG
        for size in (256, 48, 32, 16):
            temp_path = OUT_DIR / f"icon-{size}-temp.png"
            _qimage(renderer, size).save(str(temp_path), "PNG")
            temp_pngs.append(temp_path)
        
        # Open the 256x256 PNG as the base image
        base_img = Image.open(temp_pngs[0])
        
        # Open other sizes as append images
        append_imgs = [Image.open(p) for p in temp_pngs[1:]]
        
        # Save as ICO with multiple sizes
        base_img.save(
            str(ico_path),
            format="ICO",
            sizes=[(256, 256), (48, 48), (32, 32), (16, 16)],
            append_images=append_imgs
        )
        print("wrote", ico_path)
        
    finally:
        # Clean up temporary files
        for temp_path in temp_pngs:
            if temp_path.exists():
                temp_path.unlink()
    
    if QtWidgets.QApplication.instance() is app:
        app.quit()


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    render()
