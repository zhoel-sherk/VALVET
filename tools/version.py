# SPDX-License-Identifier: MIT
"""Version bookkeeping for VALVET: the single place that rewrites copies.

Qt-free on purpose — this runs in CI and locally on a bare interpreter.

    python tools/version.py show
    python tools/version.py check
    python tools/version.py bump X|Y|Z|B
    python tools/version.py sync

``src/__version__.py`` is the single source of truth; ``sync`` regenerates the
derived copies (READMEs, TODO, locale window titles, release workflow input) and
``check`` fails when a tracked file drifts away from it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from __version__ import (  # noqa: E402
    VersionError,
    __version__,
    bump as _bump,
    normalise_part,
    validate_version,
)

VERSION_FILE = _SRC / "__version__.py"
WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release-windows.yml"
LANG_DIR = _REPO_ROOT / "lang"
README_MD = _REPO_ROOT / "README.md"
README_RU = _REPO_ROOT / "README.ru.md"
TODO_MD = _REPO_ROOT / "doc" / "TODO.md"

#: Files that must not carry a hand-written version literal. ``src/__version__.py``
#: itself is deliberately absent (it is the source, not a copy).
STALE_FILES = (
    README_MD,
    README_RU,
    TODO_MD,
    WORKFLOW,
    *sorted(LANG_DIR.glob("*.json")),
)

#: Historical/foreign version numbers that are legitimate inside tracked files
#: (the newest published download predates this tree). ``check`` ignores these.
ALLOWED_OTHER_VERSIONS = frozenset({"0.2.0"})

#: A version literal is three or four numeric segments (``0.5.1`` / ``0.5.1.1``).
VERSION_LITERAL_RE = re.compile(r"\d+\.\d+\.\d+(?:\.\d+)?")


def _rel(path: Path) -> str:
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def current_version() -> str:
    """Validated version read from ``src/__version__.py``."""
    return validate_version(__version__)


def _rewrite_version_file(version: str) -> None:
    source = VERSION_FILE.read_text(encoding="utf-8")
    new_source, count = re.subn(
        r'^__version__ = "[^"]+"$',
        f'__version__ = "{version}"',
        source,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit(
            f"could not rewrite the __version__ assignment in {VERSION_FILE}"
        )
    VERSION_FILE.write_text(new_source, encoding="utf-8", newline="\n")


def _sub(
    path: Path,
    pattern: re.Pattern[str],
    replacement: str | Callable[[re.Match[str]], str],
    version: str,
) -> bool:
    """Apply *pattern* -> *replacement* inside *path*; True when the file changed.

    A ``{version}`` token inside a string replacement is filled with *version*;
    callables receive the match (and may close over *version*).
    """
    if not path.exists():
        return False
    source = path.read_text(encoding="utf-8")
    if isinstance(replacement, str):
        expanded = replacement.replace("{version}", version)
        new_source, count = pattern.subn(expanded, source)
    else:
        new_source, count = pattern.subn(replacement, source)
    if count == 0 or new_source == source:
        return False
    path.write_text(new_source, encoding="utf-8", newline="")
    return True


# (pattern, replacement) pairs applied to each README.
def _readme_rules() -> list[tuple[re.Pattern[str], str]]:
    return [
        # ``# VALVET — BETA v0.5.1``
        (
            re.compile(
                r"^(#\s*VALVET\s*—\s*BETA\s+v)\d+\.\d+\.\d+(?:\.\d+)?\r?$",
                re.MULTILINE,
            ),
            r"\g<1>{version}",
        ),
        # ``VALVET-0.5.1-windows-x64.zip``
        (
            re.compile(r"VALVET-\d+\.\d+\.\d+(?:\.\d+)?-windows-x64\.zip"),
            "VALVET-{version}-windows-x64.zip",
        ),
        (
            re.compile(r"/releases/download/v\d+\.\d+\.\d+(?:\.\d+)?/"),
            "/releases/download/v{version}/",
        ),
        (
            re.compile(r"/releases/tag/v\d+\.\d+\.\d+(?:\.\d+)?"),
            "/releases/tag/v{version}",
        ),
        # Link labels: ``[release v0.5.1]`` / ``[релиза v0.5.1]`` (label word kept).
        (
            re.compile(r"(\[[^\]\[\n]*?v)\d+\.\d+\.\d+(?:\.\d+)?(\])"),
            r"\g<1>{version}\g<2>",
        ),
        # ``**0.5.1 BETA**`` (the historical ``**0.2.0**`` note is left alone).
        (
            re.compile(r"\*\*\d+\.\d+\.\d+(?:\.\d+)? BETA\*\*"),
            "**{version} BETA**",
        ),
    ]


def _sync_readmes(version: str) -> list[str]:
    touched: list[str] = []
    for readme in (README_MD, README_RU):
        changed = [
            _sub(readme, pattern, replacement, version)
            for pattern, replacement in _readme_rules()
        ]
        if any(changed):
            touched.append(_rel(readme))
    return touched


def _sync_todo(version: str) -> list[str]:
    pattern = re.compile(r"BETA \*\*v\d+\.\d+\.\d+(?:\.\d+)?\*\*")
    return (
        [_rel(TODO_MD)] if _sub(TODO_MD, pattern, "BETA **{version}**", version) else []
    )


def _sync_workflow(version: str) -> list[str]:
    pattern = re.compile(
        r'^(?P<indent>\s*)default:\s*"v?\d+\.\d+\.\d+(?:\.\d+)?"', re.MULTILINE
    )
    replacement = lambda match: f'{match.group("indent")}default: "{version}"'  # noqa: E731
    if _sub(WORKFLOW, pattern, replacement, version):
        return [_rel(WORKFLOW)]
    return []


def _sync_lang(version: str) -> list[str]:
    # ``"app.window_title": "VALVET — BETA v0.5.1"`` -> ``... v{version}"``
    pattern = re.compile(
        r'("app\.window_title":\s*"VALVET[^"]*?)v\d+\.\d+\.\d+(?:\.\d+)?"'
    )
    touched: list[str] = []
    for path in sorted(LANG_DIR.glob("*.json")):
        if "app.window_title" not in path.read_text(encoding="utf-8"):
            continue
        if _sub(path, pattern, r'\1v{version}"', version):
            touched.append(_rel(path))
    return touched


def do_sync(version: str | None = None) -> list[str]:
    """Rewrite every derived copy so it carries *version*. Returns touched files."""
    version = validate_version(version or current_version())
    touched: list[str] = []
    for step in (_sync_readmes, _sync_todo, _sync_workflow, _sync_lang):
        touched.extend(step(version))
    return touched


def stale_hits(version: str | None = None) -> list[str]:
    """Lines of tracked files that still hardcode a version other than *version*."""
    version = validate_version(version or current_version())
    hits: list[str] = []
    for path in STALE_FILES:
        if not path.exists():
            hits.append(f"{_rel(path)}: missing")
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in VERSION_LITERAL_RE.finditer(line):
                found = match.group(0)
                if found == version or found in ALLOWED_OTHER_VERSIONS:
                    continue
                hits.append(f"{_rel(path)}:{lineno}: {found} in {line.strip()}")
    return hits


def cmd_show(_args: argparse.Namespace) -> int:
    print(current_version())
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    version = current_version()
    hits = stale_hits(version)
    if hits:
        print(
            f"version {version}: hardcoded copies found (run 'tools/version.py sync'):",
            file=sys.stderr,
        )
        for hit in hits:
            print(f"  {hit}", file=sys.stderr)
        return 1
    print(f"version {version}: ok ({len(STALE_FILES)} tracked files in sync)")
    return 0


def cmd_bump(args: argparse.Namespace) -> int:
    version = _bump(normalise_part(args.part), current_version())
    _rewrite_version_file(version)
    do_sync(version)
    print(version)
    return 0


def cmd_sync(_args: argparse.Namespace) -> int:
    version = current_version()
    touched = do_sync(version)
    print(f"version {version}: synced {len(touched)} file(s)")
    for name in sorted(set(touched)):
        print(f"  {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="version", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show", help="print the current version").set_defaults(func=cmd_show)
    check_parser = sub.add_parser(
        "check", help="validate the format and look for stale hardcoded copies"
    )
    check_parser.set_defaults(func=cmd_check)
    bump_parser = sub.add_parser("bump", help="bump X|Y|Z|B (resets lower parts to 0)")
    bump_parser.add_argument(
        "part", help="X (release), Y (major feature), Z (minor feature), B (bug fix)"
    )
    bump_parser.set_defaults(func=cmd_bump)
    sub.add_parser("sync", help="rewrite derived copies").set_defaults(func=cmd_sync)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except VersionError as exc:
        print(f"version error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
