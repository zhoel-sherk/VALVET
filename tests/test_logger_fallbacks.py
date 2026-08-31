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


def test_gerber_gerbonara_fallback_logs_warning(monkeypatch, mocker, tmp_path: Path) -> None:
    gbr = tmp_path / "x.gbr"
    gbr.write_text("G04 test*", encoding="ascii")
    empty = GerberSvgPayload(
        source_path=str(gbr),
        svg="",
        bbox_mm=BBoxMM(0.0, 0.0, 0.0, 0.0),
        errors=("parse failed",),
        backend_name="pygerber",
    )
    ok = GerberSvgPayload(
        source_path=str(gbr),
        svg="<svg xmlns='http://www.w3.org/2000/svg'/>",
        bbox_mm=BBoxMM(0.0, 0.0, 1.0, 1.0),
        backend_name="gerbonara",
    )
    import pcb_preview.engine as eng

    monkeypatch.setattr(eng, "load_via_pygerber", lambda p: empty)
    monkeypatch.setattr(eng, "load_via_gerbonara", lambda p: ok)
    warn_spy = mocker.spy(logger, "warning")
    payload = load_gerber_layer(str(gbr))
    assert payload.backend_name == "gerbonara"
    assert payload.svg
    assert warn_spy.called
    msg = str(warn_spy.call_args.args[0]).lower()
    assert "gerbonara" in msg or "pygerber" in msg


def test_gerber_missing_file_logs_error(mocker, tmp_path: Path) -> None:
    missing = tmp_path / "nope.gbr"
    err_spy = mocker.spy(logger, "error")
    payload = load_gerber_layer(str(missing))
    assert not payload.svg
    assert err_spy.called
    blob = " ".join(str(a) for a in err_spy.call_args.args).lower()
    assert "not found" in blob or "gerber" in blob


def test_gerber_corrupt_file_logs_error(mocker, tmp_path: Path) -> None:
    bad = tmp_path / "bad.gbr"
    bad.write_bytes(b"not gerber content")
    err_spy = mocker.spy(logger, "error")
    payload = load_gerber_layer(str(bad))
    assert not payload.svg
    assert payload.errors
    assert err_spy.called


def test_hanwha_odbc_fallback_logs_warning(monkeypatch, mocker, tmp_path: Path) -> None:
    import machine_library.hanwha_mdbtools as mdbtools
    from machine_library.access_odbc import AccessOdbcError

    fake = tmp_path / "lib.mdb"
    fake.write_bytes(b"mdb")
    monkeypatch.setattr(mdbtools.sys, "platform", "win32")
    monkeypatch.setattr(mdbtools, "_mdb_tools_fallback_allowed", lambda: True)

    def _odbc_fail(_path):
        raise AccessOdbcError("no ACE")

    monkeypatch.setattr(
        "machine_library.access_odbc.list_mdb_tables_odbc", _odbc_fail
    )
    monkeypatch.setattr(mdbtools, "_list_mdb_tables_cli", lambda _p: ["PART_Det"])
    warn_spy = mocker.spy(logger, "warning")
    names = mdbtools.list_mdb_tables(fake)
    assert names == ["PART_Det"]
    assert warn_spy.called
    blob = str(warn_spy.call_args.args[0])
    assert "mdbtools" in blob.lower() or "ODBC" in blob
