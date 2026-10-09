# SPDX-License-Identifier: MIT
"""Single source of truth for the VALVET version.

This module is the ONLY place where the version string is written by hand.
``app.constants.APP_VERSION``, the Qt application version, the window title and
the release zip name are all derived from ``__version__`` (see ``tools/version.py``).

Version format ``X.Y.Z.B`` (four numeric segments, PEP 440 compatible because
the PEP 440 release segment allows any number of components, so the value is
also usable on PyPI and in a winget manifest):

===========  ==========================  ==========================================
Position     Meaning                     Increment when
===========  ==========================  ==========================================
``X``        Release line. The first     first battle-tested release after a year
             ``1`` is the first stable    of work on the line
             (production) release
``Y``        Major feature               a significant capability is added
``Z``        Minor feature               a button, a small feature/code change
``B``        Bug fixes                   a bug is fixed
===========  ==========================  ==========================================

Reset rule: incrementing any component resets every lower component to ``0``.
``0.5.1.1`` -> fix another bug = ``0.5.1.2``; new minor feature = ``0.5.2.0``;
new major feature = ``0.6.0.0``; first production release = ``1.0.0.0``.
"""

from __future__ import annotations

import re

__version__ = "0.5.2.1"

#: Four numeric segments, in order, no suffixes and no leading/trailing junk.
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")

#: Component names accepted by :func:`bump`, ordered from the highest component.
BUMP_PARTS = ("X", "Y", "Z", "B")

#: Aliases for the BETA-era vocabulary used in the release plan.
BUMP_ALIASES = {
    "release": "X",
    "major": "Y",
    "feature": "Z",
    "minor": "Z",
    "bugfix": "B",
    "patch": "B",
}


class VersionError(ValueError):
    """Raised when a version string does not follow the ``X.Y.Z.B`` rules."""


def validate_version(version: str) -> str:
    """Return *version* unchanged, or raise :class:`VersionError`.

    Enforces exactly four numeric segments. When ``packaging`` is importable the
    value is additionally checked as a PEP 440 version.
    """
    if not isinstance(version, str):
        raise VersionError(f"version must be a str, got {type(version).__name__}")
    if not VERSION_RE.match(version):
        raise VersionError(
            f"malformed version {version!r}: expected X.Y.Z.B "
            f"(four numeric segments), e.g. {__version__}"
        )
    try:  # PEP 440 is a nice-to-have, not a hard dependency of tools/version.py.
        from packaging.version import InvalidVersion, Version
    except ImportError:  # pragma: no cover - packaging absent
        return version
    try:
        Version(version)
    except InvalidVersion as exc:  # pragma: no cover - unreachable for a regex hit
        raise VersionError(
            f"{version!r} is not a valid PEP 440 version: {exc}"
        ) from exc
    return version


def parse_version(version: str = __version__) -> tuple[int, int, int, int]:
    """Split a validated version into its four integer components."""
    validate_version(version)
    major, minor, patch, build = version.split(".")
    return int(major), int(minor), int(patch), int(build)


def normalise_part(part: str) -> str:
    """Map ``part`` (``X``/``Y``/``Z``/``B`` or an alias, any case) to ``X``-``B``."""
    key = str(part).strip().upper()
    if key in BUMP_PARTS:
        return key
    alias = BUMP_ALIASES.get(key.lower())
    if alias is None:
        raise VersionError(
            f"unknown version component {part!r}: use one of {'|'.join(BUMP_PARTS)}"
        )
    return alias


def bump(part: str, version: str = __version__) -> str:
    """Return *version* with *part* incremented and every lower part reset to 0.

    >>> bump("Y", "0.5.1.1")
    '0.6.0.0'
    >>> bump("Z", "0.5.1.1")
    '0.5.2.0'
    >>> bump("B", "0.5.1.1")
    '0.5.1.2'
    """
    index = BUMP_PARTS.index(normalise_part(part))
    parts = list(parse_version(version))
    parts[index] += 1
    for lower in range(index + 1, len(parts)):
        parts[lower] = 0
    return ".".join(str(value) for value in parts)


validate_version(__version__)
