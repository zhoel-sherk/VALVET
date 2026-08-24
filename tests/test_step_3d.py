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


def test_pyvista_read_minimal_fixture() -> None:
    pytest.importorskip("pyvista")
    import pyvista as pv

    obj = Path(__file__).resolve().parent / "fixtures" / "minimal.obj"
    mesh = pv.read(str(obj))
    assert mesh.n_points == 3
    assert mesh.n_cells >= 1
