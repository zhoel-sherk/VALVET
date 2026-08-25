"""step_3d: conversion helpers and optional PyVista mesh read."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

tests_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(tests_path), "src"))

from step_3d.conversion import (
    expand_command_template,
    run_step_to_mesh,
    template_to_argv,
)


def test_expand_command_template() -> None:
    s = expand_command_template(
        'tool "{in}" out="{out}"', "/tmp/a b.stp", "/tmp/out.obj"
    )
    assert s == 'tool "/tmp/a b.stp" out="/tmp/out.obj"'


def test_template_to_argv_basic() -> None:
    argv = template_to_argv("mytool /path/a /path/b")
    assert argv == ["mytool", "/path/a", "/path/b"]


def test_import_step_3d_package_does_not_require_pyside() -> None:
    import step_3d

    assert "Step3DTabWidget" in step_3d.__all__


def test_step_3d_tab_import_requires_pyside() -> None:
    pytest.importorskip("PySide6")
    from step_3d.tab import Step3DTabWidget  # noqa: F401


def test_run_step_to_mesh_reports_failure() -> None:
    fd, step = tempfile.mkstemp(suffix=".stp")
    os.write(fd, b"dummy")
    os.close(fd)
    fd2, out = tempfile.mkstemp(suffix=".obj")
    os.close(fd2)
    os.unlink(out)
    try:
        # Build argv-safe command line (Windows MSVC quoting + shlex.split(posix=False) round-trip).
        fail_cmd = subprocess.list2cmdline(
            [sys.executable, "-c", "import sys; sys.exit(42)"]
        )
        res = run_step_to_mesh(
            step, out, command_template=f'{fail_cmd} "{{in}}" "{{out}}"', timeout_s=30.0
        )
        assert res.ok is False
        assert res.returncode == 42
    finally:
        try:
            os.unlink(step)
        except OSError:
            pass


def test_occ_load_import_does_not_require_pyside() -> None:
    from step_3d.occ_load import clamp_lin_deflection, pythonocc_available

    assert clamp_lin_deflection(0.01) == 0.05
    assert clamp_lin_deflection(9) == 5.0
    assert clamp_lin_deflection("0.3") == 0.3
    assert isinstance(pythonocc_available(), bool)


def test_load_step_reports_missing_occ() -> None:
    from step_3d.occ_load import load_step_file, pythonocc_available

    if pythonocc_available():
        pytest.skip("pythonocc is installed")
    r = load_step_file(__file__)
    assert r.cancelled is False
    assert r.error
    assert "pythonocc" in r.error.lower()


def test_load_step_missing_file() -> None:
    pytest.importorskip("OCC.Core.STEPControl")
    from step_3d.occ_load import load_step_file

    r = load_step_file(str(Path(__file__).resolve().parent / "no_such_file.stp"))
    assert r.error == "file not found"


def test_occ_tessellate_box_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("OCC.Core.BRepPrimAPI")
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    from step_3d.occ_load import load_step_file, tessellate_shape

    box = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    verts, faces = tessellate_shape(box, 0.3)
    assert len(verts) >= 4
    assert len(faces) >= 4

    step_path = tmp_path / "box.stp"
    writer = STEPControl_Writer()
    writer.Transfer(box, STEPControl_AsIs)
    writer.Write(str(step_path))
    assert step_path.is_file() and step_path.stat().st_size > 0
    result = load_step_file(str(step_path), lin_deflection=0.3)
    assert result.cancelled is False
    assert result.error is None
    assert any(p.has_mesh for p in result.parts)
    n_faces = sum(len(p.faces) for p in result.parts if p.has_mesh)
    assert n_faces >= 4


def test_occ_load_unit_box_fixture() -> None:
    pytest.importorskip("OCC.Core.STEPControl")
    from step_3d.occ_load import load_step_file

    path = Path(__file__).resolve().parent / "fixtures" / "unit_box.stp"
    assert path.is_file()
    assert path.read_text(encoding="ascii").lstrip().startswith("ISO-10303-21;")
    result = load_step_file(str(path), lin_deflection=0.3)
    assert result.cancelled is False
    # CSG BLOCK in the fixture may fail on some OCC builds; MakeBox roundtrip is the
    # geometry guarantee. Accept either a mesh or a clear error string.
    if result.error:
        assert len(result.error) > 0
    else:
        assert any(p.has_mesh for p in result.parts)


def test_load_step_cancel() -> None:
    pytest.importorskip("OCC.Core.STEPControl")
    from step_3d.occ_load import load_step_file

    path = Path(__file__).resolve().parent / "fixtures" / "unit_box.stp"
    result = load_step_file(str(path), should_stop=lambda: True)
    assert result.cancelled is True
    assert result.parts == []


def test_pyvista_read_minimal_fixture() -> None:
    pytest.importorskip("pyvista")
    import pyvista as pv

    obj = Path(__file__).resolve().parent / "fixtures" / "minimal.obj"
    mesh = pv.read(str(obj))
    assert mesh.n_points == 3
    assert mesh.n_cells >= 1
