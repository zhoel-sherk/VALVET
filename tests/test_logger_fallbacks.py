"""GUI-free tests for --debug and P0 fallback logging."""

from __future__ import annotations

from pathlib import Path

import logger
from pcb_preview.engine import load_gerber_layer
from pcb_preview.types import BBoxMM, GerberSvgPayload


def test_configure_if_debug_off(monkeypatch) -> None:
    monkeypatch.delenv("VALVET_DEBUG", raising=False)
    called: list = []
    monkeypatch.setattr(logger, "config", lambda *a, **k: called.append(True))
    assert logger.configure_if_debug(argv_debug=False) is False
    assert called == []


def test_configure_if_debug_flag_and_env(monkeypatch) -> None:
    monkeypatch.delenv("VALVET_DEBUG", raising=False)
    monkeypatch.setattr(logger, "_debug_mode", False)
    called: list = []
    monkeypatch.setattr(logger, "config", lambda color: called.append(color))
    assert logger.configure_if_debug(argv_debug=True) is True
    monkeypatch.setattr(logger, "_debug_mode", False)
    monkeypatch.setenv("VALVET_DEBUG", "1")
    assert logger.configure_if_debug(argv_debug=False) is True
    assert called == [True, True]


def test_cli_debug_flag_calls_logger_config(monkeypatch, tmp_path: Path) -> None:
    called: list = []
    monkeypatch.setattr(logger, "_debug_mode", False)
    monkeypatch.setattr(logger, "config", lambda color: called.append(color))
    from cli.argparse_app import _parser, main

    ns = _parser().parse_args(["--debug", "map"])
    assert ns.debug is True
    sess = tmp_path / "sess.json"
    assert main(["--debug", "--session", str(sess), "map"]) == 0
    assert called == [True]


def test_main_parse_args_debug() -> None:
    from main import _parse_args

    args, _rest = _parse_args(["--debug", "--smoke"])
    assert args.debug is True
    assert args.smoke is True


def test_gerber_gerbonara_fallback_logs_warning(monkeypatch) -> None:
    empty = GerberSvgPayload(
        source_path="x.gbr",
        svg="",
        bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
        errors=("parse failed",),
        backend_name="pygerber",
    )
    ok = GerberSvgPayload(
        source_path="x.gbr",
        svg="<svg xmlns='http://www.w3.org/2000/svg'/>",
        bbox_mm=BBoxMM(0.0, 0.0, 1.0, 1.0),
        backend_name="gerbonara",
    )
    import pcb_preview.engine as eng

    monkeypatch.setattr(eng, "load_via_pygerber", lambda p: empty)
    monkeypatch.setattr(eng, "load_via_gerbonara", lambda p: ok)
    logs: list[str] = []

    def _warn(msg, *args, **kwargs):
        logs.append(msg % args if args else str(msg))

    monkeypatch.setattr(logger, "warning", _warn)
    payload = load_gerber_layer("x.gbr")
    assert payload.backend_name == "gerbonara"
    assert payload.svg
    assert logs
    assert "gerbonara" in logs[0].lower() or "pygerber" in logs[0].lower()


def test_hanwha_odbc_fallback_logs_warning(monkeypatch, tmp_path: Path) -> None:
    import machine_library.hanwha_mdbtools as mdb
    from machine_library.access_odbc import AccessOdbcError

    fake = tmp_path / "lib.mdb"
    fake.write_bytes(b"mdb")
    monkeypatch.setattr(mdb.sys, "platform", "win32")
    monkeypatch.setattr(mdb, "_mdb_tools_fallback_allowed", lambda: True)

    def _odbc_fail(_path):
        raise AccessOdbcError("no ACE")

    monkeypatch.setattr(
        "machine_library.access_odbc.list_mdb_tables_odbc", _odbc_fail
    )
    monkeypatch.setattr(mdb, "_list_mdb_tables_cli", lambda _p: ["PART_Det"])
    logs: list[str] = []

    def _warn(msg, *args, **kwargs):
        logs.append(msg % args if args else str(msg))

    monkeypatch.setattr(logger, "warning", _warn)
    names = mdb.list_mdb_tables(fake)
    assert names == ["PART_Det"]
    assert logs
    assert "mdbtools" in logs[0].lower() or "ODBC" in logs[0]
