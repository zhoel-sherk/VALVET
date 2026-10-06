# SPDX-License-Identifier: MIT
"""The PyInstaller bundle must ship every data file the frozen app reads.

Frozen modules resolve data relative to ``__file__``, which lands under
``_MEIPASS``. A ``datas`` entry therefore has to place the file at exactly the
path the module computes, or startup crashes (a missing VSPD ``tree.json``
aborts MainWindow before the window is shown) or the UI silently degrades
(missing tab icons / switch states).

``doc/info/TESTING.md`` requires loaders to fail loudly rather than silently,
so the cheapest guard is to keep ``valvet.spec`` in step with the modules.
"""

from __future__ import annotations

import ast
import re
import shutil
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = REPO_ROOT / "valvet.spec"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release-windows.yml"

# A frozen run creates logs/ next to VALVET.exe (session_file_log resolves
# ``Path(__file__).parent.parent / "logs"`` -> dist/VALVET/logs) and that folder
# carries the user's absolute file paths, so it must never ship. The release
# workflow zips before the smoke test for exactly this reason (plan variant A).
LOGS_ENTRY_RE = re.compile(r"(?:^|/)logs/")

# (source relative to repo root, destination inside _MEIPASS, consuming module).
# The destination is what the module computes from __file__ when frozen.
REQUIRED_DATA: list[tuple[str, str, str]] = [
    ("lang", "lang", "src/ui_i18n.py"),
    (
        "src/themes/design_tokens.json",
        "themes",
        "src/themes/__init__.py",
    ),
    (
        "src/themes/assets",
        "themes/assets",
        "src/themes/tab_icons.py",
    ),
    (
        "src/package_vspd/catalog",
        "package_vspd/catalog",
        "src/package_vspd/catalog.py",
    ),
]

# Bundled by a glob loop instead of the literal list, so it is asserted apart.
FONT_GLOB_SOURCE = "src/fonts"
FONT_DEST = "fonts"
FONT_CONSUMER = "src/themes/fonts_loader.py"


def _spec_datas() -> list[tuple[str, str]]:
    """Static ``datas`` pairs from valvet.spec (font globs are appended later)."""
    tree = ast.parse(SPEC_PATH.read_text(encoding="utf-8"), filename=str(SPEC_PATH))
    for node in tree.body:
        targets = (
            [t.id for t in node.targets if isinstance(t, ast.Name)]
            if isinstance(node, ast.Assign)
            else []
        )
        if "datas" in targets and isinstance(node.value, ast.List):
            return [
                (ast.literal_eval(pair.elts[0]), ast.literal_eval(pair.elts[1]))
                for pair in node.value.elts
                if isinstance(pair, ast.Tuple) and len(pair.elts) == 2
            ]
    pytest.fail("valvet.spec no longer assigns a literal `datas` list")


def _norm(value: str) -> str:
    return value.replace("\\", "/").strip("/")


@pytest.mark.parametrize(("source", "dest", "consumer"), REQUIRED_DATA)
def test_required_data_is_declared_in_spec(
    source: str, dest: str, consumer: str
) -> None:
    """Each data file a frozen module reads is declared with the right dest."""
    assert (REPO_ROOT / source).exists(), f"missing source data: {source}"
    assert (REPO_ROOT / consumer).exists(), f"missing consumer module: {consumer}"
    declared = {(_norm(s), _norm(d)) for s, d in _spec_datas()}
    assert (_norm(source), _norm(dest)) in declared, (
        f"{consumer} reads {source!r}, which must ship as _MEIPASS/{dest}. "
        "Add it to the `datas` list in valvet.spec."
    )


def test_catalog_json_files_are_not_filtered_out() -> None:
    """``_not_repo_examples`` must not strip the VSPD catalog from datas."""
    spec_src = SPEC_PATH.read_text(encoding="utf-8")
    for source, dest, _ in REQUIRED_DATA:
        assert "examples" not in _norm(source).lower(), source
        assert "examples" not in _norm(dest).lower(), dest
    assert "datas = [x for x in datas if _not_repo_examples(x)]" in spec_src


def _workflow_step_order() -> dict[str, int]:
    """Step name -> index, for the release workflow's ``windows-zip`` job."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    return {
        name: index
        for index, name in enumerate(
            re.findall(r"^\s*- name:\s*(.+?)\s*$", text, re.MULTILINE)
        )
    }


def test_zip_is_built_before_the_smoke_test() -> None:
    """Smoke must run on the unpacked zip, or logs/ lands in the shipped archive.

    ``--smoke`` reaches MainWindow, which creates ``dist/VALVET/logs``. Zipping
    first keeps that folder out of the artifact (plan variant A).
    """
    order = _workflow_step_order()
    assert "Zip onedir folder" in order, order
    assert "Smoke unpacked zip" in order, order
    assert order["Zip onedir folder"] < order["Smoke unpacked zip"], (
        "zip after smoke => the logs/ folder created by the smoke run ships"
    )
    workflow_src = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "unzip -q" in workflow_src, "smoke must run on the unpacked zip"
    assert "./smoke/VALVET/VALVET.exe --smoke" in workflow_src
    assert "VALVET/logs/" in workflow_src, "the zip step must reject a logs/ entry"


def test_release_takes_the_version_from_the_version_file() -> None:
    """``inputs.version`` is validation only; src/__version__.py ships."""
    workflow_src = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "python tools/version.py show" in workflow_src
    assert "python tools/version.py check" in workflow_src
    assert 'echo "VERSION=${VERSION}" >> "$GITHUB_ENV"' in workflow_src
    assert "${{ inputs.version }}-windows-x64.zip" not in workflow_src, (
        "artifact paths must use the resolved version, not the dispatch input"
    )


def test_logs_entry_is_detected_in_a_built_zip(tmp_path: Path) -> None:
    """The guard's rule: any ``logs/`` entry in the archive is a failure.

    Focuses on the check itself (a real zip round-trip is cheap; a PyInstaller
    build is not) so a regression in the pattern cannot ship silently.
    """
    onedir = tmp_path / "VALVET"
    (onedir / "_internal").mkdir(parents=True)
    (onedir / "VALVET.exe").write_bytes(b"MZ")
    (onedir / "logs").mkdir()
    (onedir / "logs" / "sessionlog.txt").write_text(
        "C:\\Users\\Someone", encoding="utf-8"
    )

    archive = tmp_path / "dirty"
    shutil.make_archive(str(archive), "zip", tmp_path, "VALVET")
    with zipfile.ZipFile(archive.with_suffix(".zip")) as zf:
        polluted = [name for name in zf.namelist() if LOGS_ENTRY_RE.search(name)]
    assert polluted, "the guard must flag a logs/ entry"

    shutil.rmtree(onedir / "logs")
    shutil.make_archive(str(archive), "zip", tmp_path, "VALVET")
    with zipfile.ZipFile(archive.with_suffix(".zip")) as zf:
        assert not [name for name in zf.namelist() if LOGS_ENTRY_RE.search(name)]


def test_fonts_are_globbed_not_hardcoded() -> None:
    """Fonts ship via the spec's ``*.ttf`` glob loop, each to ``_MEIPASS/fonts``."""
    spec_src = SPEC_PATH.read_text(encoding="utf-8")
    assert '_font_dir = Path("src/fonts")' in spec_src
    assert '_font_dir.glob("*.ttf")' in spec_src
    assert 'datas.append((str(_p), "fonts"))' in spec_src
    assert not any(_norm(s).endswith(".ttf") for s, _ in _spec_datas()), (
        "a hardcoded .ttf would rot when the font set changes"
    )
    assert (REPO_ROOT / FONT_GLOB_SOURCE).is_dir(), FONT_GLOB_SOURCE
    assert list((REPO_ROOT / FONT_GLOB_SOURCE).glob("*.ttf")), "no fonts to bundle"
    assert (REPO_ROOT / FONT_CONSUMER).exists(), FONT_CONSUMER
    assert FONT_DEST == "fonts", (
        "fonts_loader.bundled_fonts_dir() expects _MEIPASS/fonts"
    )
