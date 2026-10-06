"""Regression cover for the release 0.5.1.1 Phase-4 audit fixes.

Each test names the work item it protects. Items that live in modules owned by
other agents (4.15's ``type`` shadowing and the SIM114 merges) are covered in
their own files instead.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import pytest

pytest.importorskip("PySide6")

from PySide6 import QtCore, QtGui, QtWidgets


def _qapp() -> QtWidgets.QApplication:
    """There is no ``qapp`` fixture in conftest; mirror the other model tests."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _func_ast(module: str, dotted: str) -> ast.FunctionDef:
    """Locate a function (or method) in a repo module and return its AST node.

    Parsing the whole file avoids the indentation problem of ``inspect.getsource``
    on a method, and lets one helper serve every structural assertion below.
    """
    src_root = Path(__file__).resolve().parent.parent / "src"
    tree = ast.parse((src_root / f"{module.replace('.', '/')}.py").read_text("utf-8"))
    parts = dotted.split(".")
    node: ast.AST = tree
    for part in parts:
        found = None
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if child.name == part:
                    found = child
                    break
        assert found is not None, f"{dotted}: {part} not found in {module}"
        node = found
    assert isinstance(node, ast.FunctionDef), f"{dotted} is not a function"
    return node


# ======================================================================
# 4.3  clean_import: single column must reuse the bom_text_utils NaN guard
# ======================================================================


def _nan_bom() -> pd.DataFrame:
    return pd.DataFrame({"C": ["R1", float("nan"), "R3"]})


def test_4_3_single_column_float_nan_becomes_empty() -> None:
    """A float NaN cell used to reach the parser as the string "nan"."""
    from services.clean_import import import_bom_comments_for_clean

    got = import_bom_comments_for_clean(_nan_bom(), ["C"], [0, 1, 2])
    assert got == ["R1", "", "R3"]


def test_4_3_single_column_and_two_column_treat_nan_alike() -> None:
    """A NaN must collapse to "" in both the single- and two-column paths."""
    from services.clean_import import import_bom_comments_for_clean

    one = import_bom_comments_for_clean(_nan_bom(), ["C"], [0, 1, 2])
    two = import_bom_comments_for_clean(
        _nan_bom(), ["C", "C"], [0, 1, 2], double_comment_separator=" "
    )
    assert one == ["R1", "", "R3"]
    assert two == ["R1 R1", "", "R3 R3"]
    assert one[1] == two[1] == ""


@pytest.mark.parametrize("bad", [None, "", "   ", "nan", "NaN", float("nan")])
def test_4_3_single_column_empty_like_values_are_blank(bad: object) -> None:
    from services.clean_import import import_bom_comments_for_clean

    bom = pd.DataFrame({"C": [bad]})
    assert import_bom_comments_for_clean(bom, ["C"], [0]) == [""]


def test_4_3_single_column_keeps_real_values() -> None:
    from services.clean_import import import_bom_comments_for_clean

    bom = pd.DataFrame({"C": ["0402_10K", "CAP 1uF", "0"]})
    assert import_bom_comments_for_clean(bom, ["C"], [0, 1, 2]) == [
        "0402_10K",
        "CAP 1uF",
        "0",
    ]


# ======================================================================
# 4.5  cell_text() replaces the str(x or "") family
# ======================================================================


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" 0402 ", "0402"),
        (None, ""),
        (float("nan"), ""),
        (float("inf"), "inf"),
        ("nan", ""),
        ("None", ""),
        # The bug the idiom hides: 0 / 0.0 must survive as text, not become "".
        (0, "0"),
        (0.0, "0.0"),
        (-0.0, "-0.0"),
        (10, "10"),
        (10.5, "10.5"),
    ],
)
def test_4_5_cell_text_keeps_zero_and_drops_nan(raw: object, expected: str) -> None:
    from package_vspd.resolve import cell_text

    assert cell_text(raw) == expected


def test_4_5_cell_text_is_the_resolve_private_helper() -> None:
    """The public alias must stay the same function, not a re-implementation."""
    from package_vspd import resolve

    assert resolve.cell_text is resolve._cell


def test_4_5_zero_ref_is_not_dropped_from_the_group_key() -> None:
    """A ref/value of 0 used to collapse to '' and merge unrelated rows."""
    from package_vspd.resolve import group_key

    assert group_key(0, "", "") == "0"
    assert group_key("", "", 0) == "\x1fref:0"


# ======================================================================
# 4.7  clean_apply logs a length mismatch instead of guessing silently
# ======================================================================


def test_4_7_length_mismatch_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from services.clean_apply import apply_clean_preview_to_bom

    bom = pd.DataFrame({"Comment": ["a", "b", "c"]})
    preview = [(1, "a", "A1", "CAP", "regex")] * 3
    with caplog.at_level(logging.WARNING):
        out = apply_clean_preview_to_bom(bom, preview, [0], "Comment")
    assert out.at[0, "comment"] == "A1"
    assert any(
        "3 preview rows vs 1 source indices" in r.getMessage() for r in caplog.records
    )


def test_4_7_matching_lengths_are_not_warned_about(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from services.clean_apply import apply_clean_preview_to_bom

    bom = pd.DataFrame({"Comment": ["a", "b"]})
    preview = [(1, "a", "A1", "CAP", "regex"), (2, "b", "B1", "CAP", "regex")]
    with caplog.at_level(logging.WARNING):
        apply_clean_preview_to_bom(bom, preview, [0, 1], "Comment")
    assert not [r for r in caplog.records if "source indices" in r.getMessage()]


def test_4_7_out_of_range_row_is_logged_and_skipped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from services.clean_apply import apply_clean_preview_to_bom

    bom = pd.DataFrame({"Comment": ["a"]})
    preview = [(1, "a", "A1", "CAP", "regex")]
    with caplog.at_level(logging.WARNING):
        out = apply_clean_preview_to_bom(bom, preview, [99], "Comment")
    assert out.at[0, "comment"] == ""
    assert any("out of range" in r.getMessage() for r in caplog.records)


def test_4_7_positional_fallback_still_applies() -> None:
    """The fallback behaviour is unchanged - only the silence is gone."""
    from services.clean_apply import apply_clean_preview_to_bom

    bom = pd.DataFrame({"Comment": ["a", "b"]})
    preview = [(1, "a", "A1", "CAP", "regex"), (2, "b", "B1", "CAP", "regex")]
    out = apply_clean_preview_to_bom(bom, preview, [0], "Comment")
    assert out.at[0, "comment"] == "A1"
    assert out.at[1, "comment"] == "B1"


def test_4_7_row_label_is_resolved_once_per_row() -> None:
    """df.index[df_i] is positional; hoisting it keeps the loop O(n)."""
    node = _func_ast("services.clean_apply", "apply_clean_preview_to_bom")
    index_lookups = [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Subscript)
        and isinstance(n.value, ast.Attribute)
        and n.value.attr == "index"
    ]
    assert len(index_lookups) == 1


# ======================================================================
# 4.8  pcb_preview_bridge uses the shared tolerant coordinate parser
# ======================================================================


def _pnp(x: object, y: object, rot: object = 0.0) -> tuple:
    from pcb_preview_bridge import placements_from_pnp_dataframe

    df = pd.DataFrame(
        [["R1", x, y, rot, "0402"]], columns=["Ref", "X", "Y", "Rotation", "Footprint"]
    )
    return placements_from_pnp_dataframe(
        df,
        designator_col="Ref",
        x_col="X",
        y_col="Y",
        rot_col="Rotation",
        footprint_col="Footprint",
        coord_unit_mm=True,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1234.5, 1234.5),
        ("1234.5", 1234.5),
        ("1234.5mil", 1234.5),
        ("1,234.5", 1234.5),
        (1234, 1234.0),
    ],
)
def test_4_8_unit_suffixed_and_thousands_separated_coords_parse(
    raw: object, expected: float
) -> None:
    """These used to drop the part out of the PCB overlay via ValueError."""
    placements, warns = _pnp(raw, 10.0)
    assert len(placements) == 1
    assert abs(placements[0].x_mm - expected) < 1e-6
    assert warns == []


def test_4_8_nan_coord_is_reported_and_dropped() -> None:
    """NaN used to reach the overlay as a NaN coordinate."""
    placements, warns = _pnp(float("nan"), 10.0)
    assert placements == []
    assert any("non-numeric X/Y for R1" in w for w in warns)


def test_4_8_nan_coord_by_name_is_reported_and_dropped() -> None:
    placements, warns = _pnp("nan", 10.0)
    assert placements == []
    assert warns


def test_4_8_infinite_coord_is_dropped() -> None:
    """coord_cell_float_for_math passes inf through, so it needs its own guard."""
    placements, warns = _pnp(float("inf"), 10.0)
    assert placements == []
    assert any("non-finite" in w for w in warns)


def test_4_8_missing_coord_is_reported_and_dropped() -> None:
    placements, warns = _pnp(None, 10.0)
    assert placements == []
    assert any("non-numeric" in w for w in warns)


def test_4_8_unparseable_coord_keeps_the_original_warning() -> None:
    placements, warns = _pnp("abc", "def")
    assert placements == []
    assert any("non-numeric X/Y for R1" in w for w in warns)


def test_4_8_mil_conversion_still_applies() -> None:
    from pcb_preview_bridge import placements_from_pnp_dataframe

    df = pd.DataFrame(
        [["R1", 1000.0, 2000.0, 0.0, "0402"]],
        columns=["Ref", "X", "Y", "Rotation", "Footprint"],
    )
    placements, _ = placements_from_pnp_dataframe(
        df,
        designator_col="Ref",
        x_col="X",
        y_col="Y",
        rot_col="Rotation",
        footprint_col="Footprint",
        coord_unit_mm=False,
    )
    assert abs(placements[0].x_mm - 25.4) < 1e-9
    assert abs(placements[0].y_mm - 50.8) < 1e-9


def test_4_8_bad_rotation_falls_back_to_zero() -> None:
    placements, _ = _pnp(1.0, 2.0, rot=float("nan"))
    assert placements[0].rotation_deg == 0.0


# ======================================================================
# 4.10  working_copy: the sort key must survive a truncated meta file
# ======================================================================


def _write_snapshot(base: Path, src: Path, kind: str, saved_at: str) -> None:
    import working_copy

    df = pd.DataFrame({"a": [saved_at]})
    working_copy.save_snapshot(df, str(src), kind, base, dirty=False)
    meta, _ = working_copy._snapshot_paths(base, src, kind)
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["saved_at"] = saved_at
    meta.write_text(json.dumps(data), encoding="utf-8")


def test_4_10_truncated_meta_among_candidates_does_not_raise(
    tmp_path: Path,
) -> None:
    """The sort key re-parsed JSON without a guard; a truncated file raised."""
    import working_copy

    base = tmp_path / "autosave"
    base.mkdir()
    src = tmp_path / "bom.csv"
    src.write_text("x\n", encoding="utf-8")

    _write_snapshot(base, src, "bom", "2026-01-01T00:00:00+00:00")
    meta, _ = working_copy._snapshot_paths(base, src, "bom")
    # Simulate the non-atomic meta write described in 5.2.8.
    meta.write_text('{"kind": "bom", "source"', encoding="utf-8")

    snap = working_copy.find_snapshot(str(src), "bom", base)
    # No JSONDecodeError; the unreadable candidate is simply not usable.
    assert snap is None or snap.meta.get("kind") == "bom"


def test_4_10_sort_key_tolerates_a_non_string_saved_at(tmp_path: Path) -> None:
    import working_copy

    base = tmp_path / "autosave"
    base.mkdir()
    src = tmp_path / "bom.csv"
    src.write_text("x\n", encoding="utf-8")
    _write_snapshot(base, src, "bom", "2026-01-01T00:00:00+00:00")

    meta, _ = working_copy._snapshot_paths(base, src, "bom")
    data = json.loads(meta.read_text(encoding="utf-8"))
    data["saved_at"] = 12345
    meta.write_text(json.dumps(data), encoding="utf-8")

    snap = working_copy.find_snapshot(str(src), "bom", base)
    assert snap is not None


# ======================================================================
# 4.11  window.py: closeEvent and the main-tab int()
# ======================================================================


def test_4_11_settings_int_accepts_usable_values() -> None:
    from app.window import _settings_int

    assert _settings_int("3") == 3
    assert _settings_int(3) == 3
    assert _settings_int(" 4 ") == 4
    assert _settings_int("-1") == -1
    assert _settings_int(None, default=2) == 2


@pytest.mark.parametrize("bad", ["", "  ", "abc", "3.5.1", "tab2", [1], object()])
def test_4_11_settings_int_falls_back_instead_of_raising(bad: object) -> None:
    """int() on a hand-edited .ini value used to take the window down."""
    from app.window import _settings_int

    assert _settings_int(bad, default=0) == 0


def test_4_11_close_event_has_an_except_before_the_finally() -> None:
    """super().closeEvent() in a bare finally let save errors escape."""
    node = _func_ast("app.window", "MainWindow.closeEvent")
    with_finally = [n for n in ast.walk(node) if isinstance(n, ast.Try) and n.finalbody]
    assert with_finally, "closeEvent no longer uses try/finally"
    assert all(t.handlers for t in with_finally), "finally without except"


# ======================================================================
# 4.14  machine_library_tab: an unexpected sender must not be a silent no-op
# ======================================================================


def test_4_14_unrecognised_sender_is_logged_and_still_applied() -> None:
    """Returning early would swallow the signal; staying silent is what broke."""
    node = _func_ast("machine_library_tab", "MachineLibraryTab._on_mdb_load_finished")
    text = ast.unparse(node)
    assert "unrecognised sender" in text
    assert "gen != self._mdb_load_gen" in text
    # The log must be on the untagged-sender path, before any early return.
    logs = [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "_host_log"
    ]
    assert len(logs) >= 2, "both the unrecognised and the stale path must log"


def test_4_14_stale_generation_still_discards() -> None:
    node = _func_ast("machine_library_tab", "MachineLibraryTab._on_mdb_load_finished")
    text = ast.unparse(node)
    assert "Discarding stale MDB load result" in text
    # A bare `gen is not None and gen != ...` guard self-disables on a None sender.
    assert "gen is not None and" not in text


# ======================================================================
# 4.15  the low-severity items that live in my files
# ======================================================================


def test_4_15_clean_apply_has_no_dead_branch() -> None:
    """5.3.3: the `df.columns` probe was dead - all branches returned one constant."""
    node = _func_ast("services.clean_apply", "_resolve_clean_target_column")
    text = ast.unparse(node)
    assert "in df.columns" not in text
    assert text.count("return") == 2  # replace_source path + the shared constant


def test_4_15_clean_target_column_resolution_behaviour() -> None:
    from services.clean_apply import _resolve_clean_target_column

    df = pd.DataFrame({"Comment": ["a"], "comment": [""]})
    assert _resolve_clean_target_column(df, "Comment", replace_source=True) == "Comment"
    assert (
        _resolve_clean_target_column(df, "Comment", replace_source=False) == "comment"
    )
    # Even with no comment column at all - the caller creates it.
    assert (
        _resolve_clean_target_column(
            pd.DataFrame({"Part": ["a"]}), "Part", replace_source=False
        )
        == "comment"
    )


def test_4_15_no_dead_if_pass_in_qt_models() -> None:
    """5.3.2: `if old_rows != ...: pass` left over from an earlier refactor."""
    node = _func_ast("qt_models", "PandasTableModel.update_dataframe")
    for inner in ast.walk(node):
        if isinstance(inner, ast.If) and len(inner.body) == 1:
            assert not isinstance(inner.body[0], ast.Pass)


def test_4_15_nan_win_percent_is_not_treated_as_full_score() -> None:
    """5.3.7: min(100.0, nan) is 100.0, so NaN painted a full-intensity fill."""
    _qapp()
    from qt_models import CleanPreviewTableModel

    df = pd.DataFrame({"Cleaned": ["a", "b"], "Win%": ["nan", "nan"]})
    model = CleanPreviewTableModel(df, arbiter_score_highlight=True)
    for row in (0, 1):
        idx = model.index(row, 0)
        bg = model.data(idx, QtCore.Qt.ItemDataRole.BackgroundRole)
        fg = model.data(idx, QtCore.Qt.ItemDataRole.ForegroundRole)
        assert bg is None
        assert fg is None
    # And the score itself must not survive as 100.0 anywhere.
    assert model._clean_tint_color(0, 0) is None


def test_4_15_nan_win_percent_out_of_column_position() -> None:
    """A float NaN that reaches the clamp must not colour the cell either."""
    pytest.importorskip("PySide6")
    from qt_models import CleanPreviewTableModel

    _qapp()
    df = pd.DataFrame({"Cleaned": ["a"], "Win%": [float("nan")]})
    model = CleanPreviewTableModel(df, arbiter_score_highlight=True)
    assert model._clean_tint_color(0, 0) is None


# ======================================================================
# 4.20  SortableTableModel amber highlight: fill/foreground contrast
# ======================================================================

WCAG_AA = 4.5

#: The two amber shades the model hardcodes, per row parity.
AMBER_SHADES = {
    "even": (126, 95, 29),
    "odd": (112, 84, 26),
}


def _relative_luminance(color: QtGui.QColor) -> float:
    total = 0.0
    for value, weight in zip(
        (color.red(), color.green(), color.blue()),
        (0.2126, 0.7152, 0.0722),
    ):
        channel = value / 255.0
        linear = (
            channel / 12.92
            if channel <= 0.03928
            else ((channel + 0.055) / 1.055) ** 2.4
        )
        total += weight * linear
    return total


def _contrast(a: QtGui.QColor, b: QtGui.QColor) -> float:
    la = _relative_luminance(a)
    lb = _relative_luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _highlight_model():
    from qt_models import SortableTableModel

    _qapp()
    df = pd.DataFrame(
        {
            "Ref": ["R1", "R2", "R3", "R4"],
            "Value": ["10K", "10K", "1uF", "1uF"],
        }
    )
    model = SortableTableModel(df)
    model.set_highlight_tokens("10K")
    return model


def _roles(
    model: "object", row: int, col_name: str
) -> tuple[Optional[QtGui.QBrush], Optional[QtGui.QBrush]]:
    col = list(model.get_dataframe().columns).index(col_name)
    idx = model.index(row, col)
    return (
        model.data(idx, QtCore.Qt.ItemDataRole.BackgroundRole),
        model.data(idx, QtCore.Qt.ItemDataRole.ForegroundRole),
    )


def test_4_20_amber_foreground_contrast_meets_wcag_aa() -> None:
    """Both amber shades, both row parities, must clear 4.5:1."""
    model = _highlight_model()
    for row in (0, 1):  # the two highlighted rows = even and odd parity
        bg, fg = _roles(model, row, "Ref")
        assert isinstance(bg, QtGui.QBrush), f"row {row} lost its fill"
        assert isinstance(fg, QtGui.QBrush), f"row {row} has no paired foreground"
        assert bg.color().alpha() == 255
        ratio = _contrast(fg.color(), bg.color())
        parity = "odd" if row % 2 == 1 else "even"
        assert ratio >= WCAG_AA, (
            f"{parity} row {row}: contrast {ratio:.2f} for fill {AMBER_SHADES[parity]}"
        )


def test_4_20_contrast_clears_aa_for_every_amber_shade() -> None:
    """Independent of row parity: both hardcoded shades are checked directly."""
    for parity, rgb in AMBER_SHADES.items():
        bg = QtGui.QColor(*rgb)
        fg = _readable_foreground(bg)
        ratio = _contrast(fg, bg)
        assert ratio >= WCAG_AA, f"{parity} {rgb}: {ratio:.2f}"


def _readable_foreground(background: QtGui.QColor) -> QtGui.QColor:
    from qt_models import _readable_foreground as impl

    return impl(background)


def test_4_20_amber_shades_are_the_hardcoded_pair() -> None:
    model = _highlight_model()
    assert model._highlight_color(0) is not None
    assert (
        model._highlight_color(0).red(),
        model._highlight_color(0).green(),
        model._highlight_color(0).blue(),
    ) == AMBER_SHADES["even"]
    assert (
        model._highlight_color(1).red(),
        model._highlight_color(1).green(),
        model._highlight_color(1).blue(),
    ) == AMBER_SHADES["odd"]


def test_4_20_non_highlighted_row_stays_theme_coloured() -> None:
    model = _highlight_model()
    for row in (2, 3):
        bg, fg = _roles(model, row, "Ref")
        assert bg is None
        assert fg is None


def test_4_20_highlight_off_leaves_no_foreground_override() -> None:
    model = _highlight_model()
    model.set_highlight_tokens("")
    for row in (0, 1):
        bg, fg = _roles(model, row, "Ref")
        assert bg is None
        assert fg is None


def test_4_20_highlight_repaint_covers_both_colour_roles() -> None:
    """Tinting now also changes text colour, so the repaint must say so."""
    model = _highlight_model()
    seen: list[list[int]] = []
    model.dataChanged.connect(lambda _tl, _br, roles: seen.append(list(roles)))
    model.set_highlight_tokens("1uF")
    assert seen, "no repaint emitted"
    for batch in seen:
        assert QtCore.Qt.ItemDataRole.BackgroundRole in batch
        assert QtCore.Qt.ItemDataRole.ForegroundRole in batch


def test_4_20_every_tinted_cell_in_a_column_gets_a_foreground() -> None:
    """Every column of a highlighted row is tinted, so all must pair a colour."""
    model = _highlight_model()
    for row in (0, 1):
        for col_name in ("Ref", "Value"):
            bg, fg = _roles(model, row, col_name)
            assert isinstance(bg, QtGui.QBrush)
            assert isinstance(fg, QtGui.QBrush)
            assert _contrast(fg.color(), bg.color()) >= WCAG_AA


def test_4_20_foreground_is_one_of_two_fixed_candidates() -> None:
    model = _highlight_model()
    for row in (0, 1):
        _, fg = _roles(model, row, "Ref")
        assert fg.color() in (
            QtGui.QColor(26, 26, 26),
            QtGui.QColor(255, 255, 255),
        )


def test_4_20_out_of_range_row_is_safe() -> None:
    model = _highlight_model()
    assert model._highlight_color(-1) is None
    assert model._highlight_color(99) is None
    assert model._get_background(99, 0, "x") is None
    assert model._get_foreground(99, 0, "x") is None
