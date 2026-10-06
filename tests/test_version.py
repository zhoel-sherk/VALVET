# SPDX-License-Identifier: MIT
"""``src/__version__.py`` is the only place a version may be written by hand.

The release zip is named from the workflow input while About shows
``APP_VERSION``; when those drift the user gets a ``VALVET-0.5.1-...zip`` whose
About says 0.5.0. These tests keep the format honest and fail when a tracked
copy stops matching the single source of truth.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = REPO_ROOT / "src" / "__version__.py"
TOOLS = REPO_ROOT / "tools"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import version as version_tool  # noqa: E402

from __version__ import (  # noqa: E402
    BUMP_PARTS,
    VersionError,
    __version__,
    bump,
    normalise_part,
    parse_version,
    validate_version,
)

# Format cases from the release plan 1.1: four numeric segments, nothing else.
VALID_VERSIONS = ["0.5.1.1", "1.0.0.0", "0.0.0.0", "10.20.30.40"]
INVALID_VERSIONS = [
    "",
    "0.5.1",  # three segments
    "0.5.1.1.1",  # five segments
    "v0.5.1.1",  # leading v
    "0.5.1.1-beta",  # suffix
    "0.5.x.1",  # non-digit
    "0.5.1.1 ",
    "0.5..1",
]


@pytest.mark.parametrize("version", VALID_VERSIONS)
def test_validate_accepts_four_numeric_segments(version: str) -> None:
    assert validate_version(version) == version
    assert parse_version(version) == tuple(int(part) for part in version.split("."))


@pytest.mark.parametrize("version", INVALID_VERSIONS)
def test_validate_rejects_malformed_versions(version: str) -> None:
    with pytest.raises(VersionError):
        validate_version(version)


def test_current_version_is_valid() -> None:
    assert validate_version(__version__) == __version__
    assert parse_version(__version__) == (0, 5, 1, 1)


def test_constants_reexports_the_single_source_of_truth() -> None:
    """``app.constants.APP_VERSION`` must be derived, never hand-written."""
    from app.constants import APP_VERSION

    assert APP_VERSION == __version__
    assert f'"{__version__}"' in VERSION_FILE.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("part", "expected"),
    [
        ("B", "0.5.1.2"),
        ("Z", "0.5.2.0"),
        ("Y", "0.6.0.0"),
        ("X", "1.0.0.0"),
        ("b", "0.5.1.2"),
        ("bugfix", "0.5.1.2"),
        ("minor", "0.5.2.0"),
        ("major", "0.6.0.0"),
        ("release", "1.0.0.0"),
    ],
)
def test_bump_resets_lower_components(part: str, expected: str) -> None:
    assert bump(part, "0.5.1.1") == expected
    assert validate_version(expected)


def test_bump_leaves_lower_components_untouched_below_the_target() -> None:
    """Only components *below* the bumped one reset."""
    assert bump("B", "0.5.1.7") == "0.5.1.8"
    assert bump("Z", "0.5.9.7") == "0.5.10.0"


def test_bump_rejects_unknown_component() -> None:
    with pytest.raises(VersionError):
        bump("W", "0.5.1.1")
    with pytest.raises(VersionError):
        normalise_part("nope")
    assert normalise_part("y") == "Y"
    assert BUMP_PARTS == ("X", "Y", "Z", "B")


def test_no_hardcoded_versions_in_tracked_files() -> None:
    """The CI gate: every tracked copy must carry ``__version__``, nothing else."""
    hits = version_tool.stale_hits(__version__)
    assert not hits, "run 'python tools/version.py sync':\n" + "\n".join(hits)


def test_window_title_uses_a_version_placeholder() -> None:
    """``app.window_title`` must not carry a version literal in any locale."""
    window_title = version_tool.LANG_DIR.glob("*.json")
    catalogs = sorted(window_title)
    assert catalogs, "no locale catalogs found"
    for path in catalogs:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        title = catalog["app.window_title"]
        assert "{version}" in title, f"{path.name}: {title!r}"
        assert not version_tool.VERSION_LITERAL_RE.search(title), (
            f"{path.name}: {title!r}"
        )


@pytest.mark.parametrize(
    "command",
    (
        [sys.executable, "-m", "tools.version", "show"],
        [sys.executable, "tools/version.py", "show"],
    ),
    ids=["module", "script"],
)
def test_tool_runs_as_module_and_as_script(command: list[str]) -> None:
    """Both documented invocations work and print the same version."""
    result = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == __version__


def test_check_subcommand_passes_on_a_clean_tree() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.version", "check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_bump_subcommand_rewrites_the_version_file(tmp_path: Path, monkeypatch) -> None:
    """``bump Z`` on 0.5.1.1 yields 0.5.2.0 and keeps the derived copies in sync."""
    version_file = tmp_path / "__version__.py"
    version_file.write_text(VERSION_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(version_tool, "VERSION_FILE", version_file)
    monkeypatch.setattr(version_tool, "do_sync", lambda _version: [])
    monkeypatch.setattr(version_tool, "current_version", lambda: __version__)

    assert version_tool.main(["bump", "Z"]) == 0
    assert '__version__ = "0.5.2.0"' in version_file.read_text(encoding="utf-8")


def test_sync_is_idempotent() -> None:
    """A second ``sync`` must find nothing left to rewrite."""
    version_tool.do_sync(__version__)
    assert version_tool.do_sync(__version__) == []
