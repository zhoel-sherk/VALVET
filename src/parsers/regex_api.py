"""
PyPI ``regex`` with VERSION1 merged into flags for BOM / MPN parsers.

Use this module instead of stdlib ``re`` in ``parsers/`` and ``pn_original/`` so
patterns can rely on V1 syntax and Unicode-aware behaviour consistently.
"""

from __future__ import annotations

import regex as _r

V1 = _r.VERSION1
VERSION1 = V1

# re-compatible flag names
I = _r.I
IGNORECASE = _r.I
M = _r.M
MULTILINE = _r.M
S = _r.S
DOTALL = _r.S
X = _r.X
VERBOSE = _r.X
A = _r.A
ASCII = _r.A
U = _r.U
UNICODE = _r.U


def _f(flags: int = 0) -> int:
    return int(flags) | V1


def compile(pattern, flags: int = 0):  # noqa: A001 — mirrors ``re.compile``
    if not isinstance(pattern, str):
        return _r.compile(pattern, flags)
    return _r.compile(pattern, _f(flags))


def search(pattern, string, flags: int = 0, pos: int = 0, endpos=None, **kwargs):
    if not isinstance(pattern, str):
        return pattern.search(string, pos, endpos)
    if endpos is None:
        return _r.search(pattern, string, pos=pos, flags=_f(flags), **kwargs)
    return _r.search(pattern, string, pos=pos, endpos=endpos, flags=_f(flags), **kwargs)


def match(pattern, string, flags: int = 0, pos: int = 0, endpos=None, **kwargs):
    if not isinstance(pattern, str):
        return pattern.match(string, pos, endpos)
    if endpos is None:
        return _r.match(pattern, string, pos=pos, flags=_f(flags), **kwargs)
    return _r.match(pattern, string, pos=pos, endpos=endpos, flags=_f(flags), **kwargs)


def fullmatch(pattern, string, flags: int = 0, pos: int = 0, endpos=None, **kwargs):
    if not isinstance(pattern, str):
        return pattern.fullmatch(string, pos, endpos)
    if endpos is None:
        return _r.fullmatch(pattern, string, pos=pos, flags=_f(flags), **kwargs)
    return _r.fullmatch(
        pattern, string, pos=pos, endpos=endpos, flags=_f(flags), **kwargs
    )


def sub(pattern, repl, string, count=0, flags: int = 0, **kwargs):
    if isinstance(pattern, str):
        return _r.sub(pattern, repl, string, count=count, flags=_f(flags), **kwargs)
    return _r.sub(pattern, repl, string, count=count, **kwargs)


def subn(pattern, repl, string, count=0, flags: int = 0, **kwargs):
    if isinstance(pattern, str):
        return _r.subn(pattern, repl, string, count=count, flags=_f(flags), **kwargs)
    return _r.subn(pattern, repl, string, count=count, **kwargs)


def split(pattern, string, maxsplit=0, flags: int = 0, **kwargs):
    if isinstance(pattern, str):
        return _r.split(pattern, string, maxsplit=maxsplit, flags=_f(flags), **kwargs)
    return _r.split(pattern, string, maxsplit=maxsplit, **kwargs)


def findall(pattern, string, flags: int = 0, pos: int = 0, endpos=None, **kwargs):
    if not isinstance(pattern, str):
        return pattern.findall(string, pos, endpos, **kwargs)
    if endpos is None:
        return _r.findall(pattern, string, pos=pos, flags=_f(flags), **kwargs)
    return _r.findall(
        pattern, string, pos=pos, endpos=endpos, flags=_f(flags), **kwargs
    )


def finditer(pattern, string, flags: int = 0, pos: int = 0, endpos=None, **kwargs):
    if not isinstance(pattern, str):
        return pattern.finditer(string, pos, endpos, **kwargs)
    if endpos is None:
        return _r.finditer(pattern, string, pos=pos, flags=_f(flags), **kwargs)
    return _r.finditer(
        pattern, string, pos=pos, endpos=endpos, flags=_f(flags), **kwargs
    )


def escape(pattern):
    return _r.escape(pattern)
