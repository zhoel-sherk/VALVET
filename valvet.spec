# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build. From the VALVET project root:
   pip install -r requirements-dev.txt
   pyinstaller valvet.spec
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# App icons only (not README screenshots / readme.svg).
datas = [
    ("lang", "lang"),
    ("img/icon.ico", "img"),
    ("img/icon-256.png", "img"),
    ("src/themes/design_tokens.json", "themes"),
]
_font_dir = Path("src/fonts")
if _font_dir.is_dir():
    for _p in sorted(_font_dir.glob("*.ttf")):
        datas.append((str(_p), "fonts"))
binaries: list = []
hiddenimports: list = []

# Qt modules VALVET does not import (grep src/). Keep Widgets/Gui/Core/Network/Svg/PrintSupport/OpenGL.
_PYSIDE_EXCLUDES = [
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtHelp",
    "PySide6.QtHttpServer",
    "PySide6.QtLocation",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

_PYSIDE_DROP_SUBSTR = (
    "QtWebEngine",
    "Qt6WebEngine",
    "Qt3D",
    "Qt63D",
    "Quick3D",
    "QtCharts",
    "Qt6Charts",
    "DataVisualization",
    "QtBluetooth",
    "Qt6Bluetooth",
    "QtNfc",
    "Qt6Nfc",
    "QtSensors",
    "Qt6Sensors",
    "SerialBus",
    "RemoteObjects",
    "QtPdf",
    "Qt6Pdf",
    "HttpServer",
    "QtDesigner",
    "designer.exe",
    "QtQuick",
    "Qt6Quick",
    "QtQml",
    "Qt6Qml",
    "QtLocation",
    "QtPositioning",
    "QtMultimedia",
    "QtWebChannel",
    "QtWebSockets",
    "QtTextToSpeech",
    "QtScxml",
    "QtStateMachine",
    "QtHelp",
    "QtUiTools",
    "lupdate",
    "lrelease",
    "linguist",
)


def _keep_pyside_item(item) -> bool:
    path = item[0] if isinstance(item, (tuple, list)) else str(item)
    low = str(path).replace("\\", "/").lower()
    return not any(x.lower() in low for x in _PYSIDE_DROP_SUBSTR)


tmp_ret = collect_all("PySide6")
datas += [x for x in tmp_ret[0] if _keep_pyside_item(x)]
binaries += [x for x in tmp_ret[1] if _keep_pyside_item(x)]
hiddenimports += [h for h in tmp_ret[2] if _keep_pyside_item(h)]

tmp_qd = collect_all("qdarkstyle")
datas += tmp_qd[0]
binaries += tmp_qd[1]
hiddenimports += tmp_qd[2]

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

try:
    tmp_cal = collect_all("python_calamine")
    datas += tmp_cal[0]
    binaries += tmp_cal[1]
    hiddenimports += tmp_cal[2]
except Exception:
    hiddenimports += ["python_calamine"]

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


def _not_repo_examples(item) -> bool:
    """Keep tests/dev fixtures (examples/) out of the WinGet zip."""
    parts = item if isinstance(item, (tuple, list)) else (item,)
    blob = " ".join(str(p).replace("\\", "/") for p in parts).lower()
    if blob == "examples" or blob.endswith("/examples"):
        return False
    return "/examples/" not in blob


datas = [x for x in datas if _not_repo_examples(x)]
binaries = [x for x in binaries if _not_repo_examples(x)]

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_PYSIDE_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a.datas = [e for e in a.datas if _not_repo_examples(e)]
a.binaries = [e for e in a.binaries if _not_repo_examples(e)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VALVET",
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
    icon="img/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VALVET",
)
