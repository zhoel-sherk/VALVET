"""Bundled Inter / JetBrains Mono + QSettings-driven UI and table fonts."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from themes import load_tokens

MONO_FONT_FAMILY = "JetBrains Mono"

FONT_POINT_SETTINGS_KEY = "ui/font_point_size"
FONT_BOLD_SETTINGS_KEY = "ui/font_bold"  # legacy; migrated into ui/font_style

FONT_UI_FAMILY_KEY = "ui/font_family"
FONT_UI_STYLE_KEY = "ui/font_style"

FONT_TABLE_FAMILY_KEY = "ui/table_font_family"
FONT_TABLE_POINT_KEY = "ui/table_font_point_size"
FONT_TABLE_STYLE_KEY = "ui/table_font_style"

FONT_TAB_FAMILY_KEY = "ui/tab_font_family"
FONT_TAB_POINT_KEY = "ui/tab_font_point_size"
FONT_TAB_STYLE_KEY = "ui/tab_font_style"

UI_FAMILY_INTER = "inter"
UI_FAMILY_SYSTEM = "system"

TABLE_FAMILY_JETBRAINS = "jetbrains"
TABLE_FAMILY_INTER = "inter"
TABLE_FAMILY_SYSTEM = "system"

STYLE_REGULAR = "regular"
STYLE_BOLD = "bold"
STYLE_ITALIC = "italic"
STYLE_BOLDITALIC = "bolditalic"

_FONT_STYLES = (STYLE_REGULAR, STYLE_BOLD, STYLE_ITALIC, STYLE_BOLDITALIC)

_SYSTEM_SANS_ORDER = (
    "Segoe UI",
    "Noto Sans",
    "Ubuntu",
    "Cantarell",
    "Helvetica Neue",
    "Arial",
)


def _first_available_family(names: tuple[str, ...]) -> str:
    for name in names:
        if QtGui.QFontDatabase.hasFamily(name):
            return name
    return QtGui.QFont().defaultFamily()


def resolve_system_sans_family() -> str:
    """Platform UI sans without preferring bundled Inter."""
    return _first_available_family(_SYSTEM_SANS_ORDER)


def resolve_inter_sans_family() -> str:
    """Prefer Inter when registered; else system sans stack."""
    return _first_available_family(("Inter",) + _SYSTEM_SANS_ORDER)


def resolve_jetbrains_mono_family() -> str:
    if QtGui.QFontDatabase.hasFamily(MONO_FONT_FAMILY):
        return MONO_FONT_FAMILY
    for fb in ("Consolas", "DejaVu Sans Mono", "Liberation Mono", "Courier New"):
        if QtGui.QFontDatabase.hasFamily(fb):
            return fb
    return QtGui.QFont().defaultFamily()


def bundled_fonts_dir() -> Path:
    """Dev: ``src/fonts/``; frozen: ``<MEIPASS>/fonts``."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "fonts"
    return Path(__file__).resolve().parent.parent / "fonts"


def register_bundled_fonts() -> int:
    """Load every ``*.ttf`` from the bundle dir (Inter + JetBrains Mono). Returns count of successful loads."""
    d = bundled_fonts_dir()
    if not d.is_dir():
        return 0
    n = 0
    for p in sorted(d.glob("*.ttf")):
        if QtGui.QFontDatabase.addApplicationFont(str(p)) >= 0:
            n += 1
    return n


def default_font_point_size() -> int:
    t = load_tokens()
    raw = t.get("font_ui_pt", 10)
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 10
    return max(6, min(36, v))


def _clamp_ui_pt(pt: int) -> int:
    return max(7, min(24, int(pt)))


def read_ui_family(settings: QtCore.QSettings | None) -> str:
    if settings is None:
        return UI_FAMILY_INTER
    v = settings.value(FONT_UI_FAMILY_KEY)
    if v in (UI_FAMILY_INTER, UI_FAMILY_SYSTEM):
        return str(v)
    return UI_FAMILY_INTER


def read_ui_style(settings: QtCore.QSettings | None) -> str:
    if settings is None:
        return STYLE_REGULAR
    v = settings.value(FONT_UI_STYLE_KEY)
    if v and str(v) in _FONT_STYLES:
        return str(v)
    if bool(settings.value(FONT_BOLD_SETTINGS_KEY, False)):
        return STYLE_BOLD
    return STYLE_REGULAR


def read_table_family(settings: QtCore.QSettings | None) -> str:
    if settings is None:
        return TABLE_FAMILY_JETBRAINS
    v = settings.value(FONT_TABLE_FAMILY_KEY)
    if v in (TABLE_FAMILY_JETBRAINS, TABLE_FAMILY_INTER, TABLE_FAMILY_SYSTEM):
        return str(v)
    return TABLE_FAMILY_JETBRAINS


def read_table_style(settings: QtCore.QSettings | None) -> str:
    if settings is None:
        return STYLE_REGULAR
    v = settings.value(FONT_TABLE_STYLE_KEY)
    if v and str(v) in _FONT_STYLES:
        return str(v)
    return STYLE_REGULAR


def read_tab_family(settings: QtCore.QSettings | None) -> str:
    if settings is None:
        return UI_FAMILY_INTER
    v = settings.value(FONT_TAB_FAMILY_KEY)
    if v in (UI_FAMILY_INTER, UI_FAMILY_SYSTEM):
        return str(v)
    return UI_FAMILY_INTER


def read_tab_style(settings: QtCore.QSettings | None) -> str:
    if settings is None:
        return STYLE_REGULAR
    v = settings.value(FONT_TAB_STYLE_KEY)
    if v and str(v) in _FONT_STYLES:
        return str(v)
    return STYLE_REGULAR


def font_tab_point_size_for_editor(settings: QtCore.QSettings) -> int:
    """Persisted tab-bar pt in 7–24; falls back to UI pt if unset."""
    v = settings.value(FONT_TAB_POINT_KEY)
    if v is None or str(v).strip() == "":
        return font_point_size_for_editor(settings)
    try:
        return _clamp_ui_pt(int(v))
    except (TypeError, ValueError):
        return font_point_size_for_editor(settings)


def _apply_style_to_font(f: QtGui.QFont, style: str) -> None:
    st = style if style in _FONT_STYLES else STYLE_REGULAR
    f.setBold(st in (STYLE_BOLD, STYLE_BOLDITALIC))
    f.setItalic(st in (STYLE_ITALIC, STYLE_BOLDITALIC))


def _resolve_table_family_key(kind: str) -> str:
    if kind == TABLE_FAMILY_JETBRAINS:
        return resolve_jetbrains_mono_family()
    if kind == TABLE_FAMILY_INTER:
        return resolve_inter_sans_family()
    return resolve_system_sans_family()


def font_point_size_for_editor(settings: QtCore.QSettings) -> int:
    """Persisted UI pt in 7–24."""
    default_pt = default_font_point_size()
    v = settings.value(FONT_POINT_SETTINGS_KEY)
    if v is None or str(v).strip() == "":
        return _clamp_ui_pt(default_pt)
    try:
        return _clamp_ui_pt(int(v))
    except (TypeError, ValueError):
        return _clamp_ui_pt(default_pt)


def font_table_point_size_for_editor(settings: QtCore.QSettings) -> int:
    """Persisted table pt in 7–24; falls back to UI pt if unset."""
    v = settings.value(FONT_TABLE_POINT_KEY)
    if v is None or str(v).strip() == "":
        return font_point_size_for_editor(settings)
    try:
        return _clamp_ui_pt(int(v))
    except (TypeError, ValueError):
        return font_point_size_for_editor(settings)


def build_ui_font(
    settings: QtCore.QSettings | None,
    *,
    override_point: int | None = None,
    override_family: str | None = None,
    override_style: str | None = None,
) -> QtGui.QFont:
    """Sans for chrome, combos, line edits (not data tables, not project console)."""
    default_pt = default_font_point_size()
    if settings is not None:
        pt = font_point_size_for_editor(settings)
        fam_key = read_ui_family(settings)
        style = read_ui_style(settings)
    else:
        pt = _clamp_ui_pt(default_pt)
        fam_key = UI_FAMILY_INTER
        style = STYLE_REGULAR
    if override_point is not None:
        pt = _clamp_ui_pt(int(override_point))
    if override_family is not None:
        if override_family in (UI_FAMILY_INTER, UI_FAMILY_SYSTEM):
            fam_key = override_family
    if override_style is not None:
        if override_style in _FONT_STYLES:
            style = override_style
    family = (
        resolve_inter_sans_family()
        if fam_key == UI_FAMILY_INTER
        else resolve_system_sans_family()
    )
    f = QtGui.QFont(family, pt)
    _apply_style_to_font(f, style)
    return f


def build_table_font(
    settings: QtCore.QSettings | None,
    *,
    override_point: int | None = None,
    override_family: str | None = None,
    override_style: str | None = None,
) -> QtGui.QFont:
    """Font for QTableView / QTreeView and similar data grids."""
    default_pt = default_font_point_size()
    if settings is not None:
        pt = font_table_point_size_for_editor(settings)
        fam_key = read_table_family(settings)
        style = read_table_style(settings)
    else:
        pt = _clamp_ui_pt(default_pt)
        fam_key = TABLE_FAMILY_JETBRAINS
        style = STYLE_REGULAR
    if override_point is not None:
        pt = _clamp_ui_pt(int(override_point))
    if override_family is not None:
        if override_family in (
            TABLE_FAMILY_JETBRAINS,
            TABLE_FAMILY_INTER,
            TABLE_FAMILY_SYSTEM,
        ):
            fam_key = override_family
    if override_style is not None:
        if override_style in _FONT_STYLES:
            style = override_style
    family = _resolve_table_family_key(fam_key)
    f = QtGui.QFont(family, pt)
    _apply_style_to_font(f, style)
    if fam_key == TABLE_FAMILY_JETBRAINS:
        f.setFixedPitch(True)
    else:
        f.setFixedPitch(False)
    return f


def build_mono_font(settings: QtCore.QSettings | None) -> QtGui.QFont:
    """Monospace for project console — JetBrains Mono when registered, else common fallbacks."""
    pt = default_font_point_size()
    if settings is not None:
        pt = font_point_size_for_editor(settings)
    pt = max(9, min(14, pt))
    family = resolve_jetbrains_mono_family()
    f = QtGui.QFont(family, pt)
    f.setFixedPitch(True)
    f.setBold(False)
    f.setItalic(False)
    return f


def build_tab_font(
    settings: QtCore.QSettings | None,
    *,
    override_point: int | None = None,
    override_family: str | None = None,
    override_style: str | None = None,
) -> QtGui.QFont:
    """Sans for the main window tab bar only."""
    default_pt = default_font_point_size()
    if settings is not None:
        pt = font_tab_point_size_for_editor(settings)
        fam_key = read_tab_family(settings)
        style = read_tab_style(settings)
    else:
        pt = _clamp_ui_pt(default_pt)
        fam_key = UI_FAMILY_INTER
        style = STYLE_REGULAR
    if override_point is not None:
        pt = _clamp_ui_pt(int(override_point))
    if override_family is not None:
        if override_family in (UI_FAMILY_INTER, UI_FAMILY_SYSTEM):
            fam_key = override_family
    if override_style is not None:
        if override_style in _FONT_STYLES:
            style = override_style
    family = (
        resolve_inter_sans_family()
        if fam_key == UI_FAMILY_INTER
        else resolve_system_sans_family()
    )
    f = QtGui.QFont(family, pt)
    _apply_style_to_font(f, style)
    return f


def apply_tab_bar_font(
    tab_bar: QtWidgets.QTabBar | None,
    settings: QtCore.QSettings | None,
) -> None:
    if tab_bar is None:
        return
    tab_bar.setFont(build_tab_font(settings))


def _is_table_like_widget(w: QtWidgets.QWidget) -> bool:
    return isinstance(
        w,
        (
            QtWidgets.QTableView,
            QtWidgets.QTableWidget,
            QtWidgets.QTreeView,
            QtWidgets.QTreeWidget,
            QtWidgets.QHeaderView,
        ),
    )


def _is_project_console(w: QtWidgets.QWidget) -> bool:
    return w.objectName() == "project_console"


def _is_main_tab_bar(w: QtWidgets.QWidget) -> bool:
    if not isinstance(w, QtWidgets.QTabBar):
        return False
    parent = w.parentWidget()
    return parent is not None and parent.objectName() == "valvetMainTabs"


def apply_app_font(settings: QtCore.QSettings | None) -> None:
    """Set QApplication default UI font; table-like widgets get table font; console skipped here."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    ui_font = build_ui_font(settings)
    table_font = build_table_font(settings)
    app.setFont(ui_font)
    for w in app.allWidgets():
        if _is_project_console(w):
            continue
        if _is_main_tab_bar(w):
            continue
        if _is_table_like_widget(w):
            w.setFont(table_font)
        else:
            w.setFont(ui_font)


def font_bold_for_editor(settings: QtCore.QSettings) -> bool:
    """Legacy helper: whether UI style is a bold variant."""
    return read_ui_style(settings) in (STYLE_BOLD, STYLE_BOLDITALIC)
