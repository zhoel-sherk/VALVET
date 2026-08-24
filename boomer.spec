# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build. From the VALVET project root:
   pip install -r requirements-dev.txt
   pyinstaller boomer.spec
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ("lang", "lang"),
    ("src/themes/design_tokens.json", "themes"),
]
_font_dir = Path("src/fonts")
if _font_dir.is_dir():
    for _p in sorted(_font_dir.glob("*.ttf")):
        datas.append((str(_p), "fonts"))
binaries: list = []
hiddenimports: list = []

tmp_ret = collect_all("PySide6")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

tmp_qd = collect_all("qdarkstyle")
datas += tmp_qd[0]
binaries += tmp_qd[1]
hiddenimports += tmp_qd[2]

try:
    tmp_vc = collect_all("vcolorpicker")
    datas += tmp_vc[0]
    binaries += tmp_vc[1]
    hiddenimports += tmp_vc[2]
except Exception:
    hiddenimports += [
        "vcolorpicker",
        "vcolorpicker.vcolorpicker",
        "vcolorpicker.ui_dark",
        "qtpy",
        "qtpy.QtCore",
        "qtpy.QtGui",
        "qtpy.QtWidgets",
    ]

try:
    tmp_po = collect_all("pyodbc")
    datas += tmp_po[0]
    binaries += tmp_po[1]
    hiddenimports += tmp_po[2]
except Exception:
    hiddenimports += ["pyodbc"]

try:
    tmp_rf = collect_all("rapidfuzz")
    datas += tmp_rf[0]
    binaries += tmp_rf[1]
    hiddenimports += tmp_rf[2]
except Exception:
    hiddenimports += ["rapidfuzz", "rapidfuzz.fuzz", "rapidfuzz.utils"]

# Optional Step 3D tab (install requirements-step3d.txt before building with 3D).
for _pkg in ("pyvista", "pyvistaqt"):
    try:
        _tmp = collect_all(_pkg)
        datas += _tmp[0]
        binaries += _tmp[1]
        hiddenimports += _tmp[2]
    except Exception:
        pass

hiddenimports += ["app.window", "main"]

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BoomerTools",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BoomerTools",
)
