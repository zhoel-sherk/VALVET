"""Headless Textual TUI tests for ValvetTui."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import Button, Input, Log

from cli.tui_app import ValvetTui


def _run_tui(coro):
    """Run an async TUI coroutine inside a headless Textual app."""

    async def _runner():
        app = ValvetTui()
        async with app.run_test(size=(120, 40)) as pilot:
            await coro(app, pilot)

    return asyncio.run(_runner())


def _press(app, button_id: str) -> None:
    app.on_button_pressed(Button.Pressed(app.query_one(f"#{button_id}", Button)))


def _log_text(app) -> list[str]:
    return list(app.query_one("#log", Log).lines)


def test_tui_app_instantiates() -> None:
    async def _act(app, pilot):
        assert app.query_one("#bom_path", Input) is not None
        assert app.query_one("#pnp_path", Input) is not None
        assert app.query_one("#table") is not None
        assert app.query_one("#log", Log) is not None

    _run_tui(_act)


def test_tui_load_empty_paths_logs_message() -> None:
    async def _act(app, pilot):
        _press(app, "load")
        await pilot.pause()
        assert any("Enter a BOM" in line for line in _log_text(app))

    _run_tui(_act)


def test_tui_load_missing_bom_path_logs_error(tmp_path: Path) -> None:
    missing = tmp_path / "valvet_missing_bom.csv"

    async def _act(app, pilot):
        app.query_one("#bom_path", Input).value = str(missing)
        _press(app, "load")
        await pilot.pause()
        logs = "\n".join(_log_text(app))
        assert "BOM not found" in logs or "Load failed" in logs

    _run_tui(_act)


def test_tui_load_missing_pnp_path_logs_error(tmp_path: Path) -> None:
    missing = tmp_path / "valvet_missing_pnp.csv"

    async def _act(app, pilot):
        app.query_one("#pnp_path", Input).value = str(missing)
        _press(app, "load")
        await pilot.pause()
        logs = "\n".join(_log_text(app))
        assert "PnP not found" in logs or "Load failed" in logs

    _run_tui(_act)


def test_tui_load_bom_csv(tmp_path: Path) -> None:
    csv = tmp_path / "bom.csv"
    csv.write_text("Ref,Comment\nR1,10k\nC1,100n", encoding="utf-8")

    async def _act(app, pilot):
        app.query_one("#bom_path", Input).value = str(csv)
        _press(app, "load")
        await pilot.pause()
        logs = "\n".join(_log_text(app))
        assert "Loaded BOM" in logs
        assert app.session.bom_df is not None
        assert len(app.session.bom_df) == 2

    _run_tui(_act)


def test_tui_mdb_empty_path_logs_message() -> None:
    async def _act(app, pilot):
        _press(app, "mdb_tables")
        await pilot.pause()
        assert any("Enter a .mdb path" in line for line in _log_text(app))

    _run_tui(_act)


def test_tui_mdb_missing_path_logs_error(tmp_path: Path) -> None:
    missing = tmp_path / "valvet_missing.mdb"

    async def _act(app, pilot):
        app.query_one("#mdb_path", Input).value = str(missing)
        _press(app, "mdb_tables")
        await pilot.pause()
        logs = "\n".join(_log_text(app))
        assert "MDB not found" in logs or "Not a file" in logs

    _run_tui(_act)


def test_tui_clean_without_bom_logs_error() -> None:
    async def _act(app, pilot):
        _press(app, "clean")
        await pilot.pause()
        logs = "\n".join(_log_text(app))
        assert "Clean failed" in logs or "BOM is not loaded" in logs

    _run_tui(_act)


def test_tui_merge_without_data_logs_error() -> None:
    async def _act(app, pilot):
        _press(app, "merge")
        await pilot.pause()
        logs = "\n".join(_log_text(app))
        assert "Merge failed" in logs or "BOM and PnP must be loaded" in logs

    _run_tui(_act)


def test_tui_save_default_path_is_relative_filename() -> None:
    async def _act(app, pilot):
        save_input = app.query_one("#save_path", Input)
        assert save_input.value == "merge.xlsx"

    _run_tui(_act)


def test_tui_no_pyside6_imports() -> None:
    src = Path(__file__).resolve().parents[1] / "src" / "cli" / "tui_app.py"
    text = src.read_text(encoding="utf-8")
    assert "PySide6" not in text
    assert "pcb_preview_tab" not in text
    assert "step_3d" not in text
