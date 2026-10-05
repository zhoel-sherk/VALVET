"""Mechanical guard: no ``logger.error(...)`` of a caught exception inside ``except``.

The audit replaced hand-rolled ``logger.error(str(e))`` calls with
``logger.exception(...)`` so the traceback survives. ``logger.exception``
defaults to ERROR level (see ``src/logger.py``), so the only behavioural
difference is ``exc_info=True``. This module pins that down so a new
``error(str(e))`` inside an ``except`` cannot creep back in.
"""

import ast
import pathlib
import re
from contextlib import contextmanager

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"

# Scoped to the modules audited in this change. Other modules are being edited
# concurrently, so they are deliberately not gated here: a failure in one of
# those must not look like a regression in this one.
AUDITED_FILES = (
    "app/workers.py",
    "app/window.py",
    "clean_component.py",
    "machine_library/hanwha_sqlite_cache.py",
    "machine_library_tab.py",
    "pcb_preview_load_thread.py",
    "step_3d/worker.py",
    "ui/merge_tab.py",
    "ui/settings_pages.py",
)

# ``logger.error``, ``log.error``, bare ``error(...)`` from ``from logger import error``.
_ERROR_NAME = re.compile(r"(?:^|\.)error$")


def _dotted(node):
    """Render a call target as ``logger.error`` / ``self.log.error`` / ``error``."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return None
    return ".".join(reversed(parts))


def _enclosing_handler(node, parents):
    """Nearest ``except`` handler ancestor of ``node``, or None.

    Walks the whole parent chain, so it also catches calls nested inside a
    function or ``with`` written directly under the handler.
    """
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, ast.ExceptHandler):
            return cur
        cur = parents.get(cur)
    return None


def _parent_map(tree):
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _local_aliases(handler):
    """Names the handler binds from the caught exception.

    Handles the one-hop form used in the codebase, where the message is built
    first and then logged:

        except Exception as e:
            msg = str(e)
            logger.error("Gerber load failed for %s: %s", path, msg)

    Only assignments appearing directly in the handler body count, and only one
    hop, so this stays a bounded check rather than a dataflow analysis.
    """
    caught = handler.name
    if not caught:
        return set()
    aliases = set()
    for stmt in handler.body:
        targets = []
        value = None
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets, value = [stmt.target], stmt.value
        if value is None:
            continue
        uses_caught = any(
            isinstance(n, ast.Name) and n.id == caught for n in ast.walk(value)
        )
        if not uses_caught:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                aliases.add(target.id)
    return aliases


def _mentions_exception(call, handler):
    """True when any logged argument is the caught exception or an alias of it.

    Catches ``error("...", e)``, ``error(f"... {e}")``, ``error(str(e))`` and the
    ``msg = str(e)`` / ``logger.error(..., msg)`` variant, since the f-string case
    leaves the name inside a ``FormattedValue`` node.
    """
    names = {handler.name} if handler.name else set()
    names |= _local_aliases(handler)
    if not names:
        return False
    for arg in call.args:
        for node in ast.walk(arg):
            if isinstance(node, ast.Name) and node.id in names:
                return True
    return False


def _passes_exc_info(call):
    """True when the call explicitly asks for the traceback.

    ``logger.error(..., exc_info=True)`` inside an ``except`` keeps the stack and
    is an acceptable alternative to ``logger.exception``, so it is not flagged.
    """
    for kw in call.keywords:
        if kw.arg == "exc_info":
            value = kw.value
            if isinstance(value, ast.Constant):
                return bool(value.value)
            # exc_info=some_expression / exc_info=sys.exc_info(): assume the
            # author meant it and do not guess.
            return True
    return False


def _find_offenders(path):
    """Return ``(lineno, source_line)`` for each in-``except`` error logging."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    parents = _parent_map(tree)
    lines = source.splitlines()
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        if name is None or not _ERROR_NAME.search(name):
            continue
        handler = _enclosing_handler(node, parents)
        if handler is None:
            # Outside an ``except`` there is no active exception to report.
            continue
        if _passes_exc_info(node):
            # Keeps the traceback via an explicit exc_info; not a defect.
            continue
        if not _mentions_exception(node, handler):
            # Either not an ``except``, or an ``except`` that logs something
            # other than the exception it caught (a config message, say).
            continue
        text = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        found.append((node.lineno, text))
    return sorted(found)


def test_guard_detects_violations(tmp_path):
    """Self-check: the AST guard must fire on each shape of violation.

    Without this, a bug in the guard (a mis-built parent map, an unreachable
    except detection) would silently pass every audited file.
    """
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import logger\n"
        "\n"
        "def a():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as e:\n"
        "        logger.error('positional: %s', e)\n"
        "\n"
        "def b():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as exc:\n"
        "        logger.error('fstring: %s', f'{exc}')\n"
        "\n"
        "def c():\n"
        "    try:\n"
        "        pass\n"
        "    except OSError as err:\n"
        "        msg = str(err)\n"
        "        logger.error('aliased: %s', msg)\n"
        "\n"
        "def d():\n"
        "    try:\n"
        "        pass\n"
        "    except KeyError as e:\n"
        "        logger.error('str() wrapped: %s', str(e))\n"
        "\n"
        "def ok_direct():\n"
        "    logger.error('outside any except')\n"
        "\n"
        "def ok_converted():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception:\n"
        "        logger.exception('already converted')\n"
        "\n"
        "def ok_no_exception_object():\n"
        "    try:\n"
        "        pass\n"
        "    except Exception:\n"
        "        logger.error('bare handler, nothing caught to log')\n"
        "\n"
        "def ok_explicit_exc_info():\n"
        "    try:\n"
        "        pass\n"
        "    except ValueError as e:\n"
        "        logger.error('keeps the stack: %s', e, exc_info=True)\n",
        encoding="utf-8",
    )
    offenders = _find_offenders(probe)
    # Exactly the four sites that drop the traceback. The legitimate
    # logger.error calls (outside any except, already converted, bare handler,
    # explicit exc_info=True) are not flagged.
    assert [lineno for lineno, _text in offenders] == [7, 13, 20, 26], offenders


@pytest.mark.parametrize("relpath", AUDITED_FILES)
def test_no_error_logging_of_caught_exception(relpath):
    """``logger.error(str(e))`` inside ``except`` discards the traceback.

    ``logger.error(..., exc_info=True)`` is allowed: it keeps the stack and is
    what several earlier tests assert on.
    """
    path = _SRC / relpath
    if not path.exists():
        pytest.skip(f"{relpath} not present")
    offenders = _find_offenders(path)
    assert not offenders, (
        f"{relpath}: log caught exceptions with logger.exception(...), not "
        f"logger.error(...): {offenders}"
    )


@contextmanager
def _capture_records():
    """Attach a capturing handler to the root logger for the duration."""
    import logging

    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = Capture()
    root = logging.getLogger()
    old_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield records
    finally:
        root.removeHandler(handler)
        root.setLevel(old_level)


def _traceback_text(record):
    """Render a record's captured exception, independent of any formatter.

    ``record.exc_text`` is only populated once a Formatter has run, which
    depends on which handlers happen to be attached. The ``exc_info`` tuple is
    set at emission time, so format it directly and assert on that.
    """
    import traceback

    if not record.exc_info:
        return ""
    return "".join(traceback.format_exception(*record.exc_info))


def test_logger_exception_defaults_to_error_level():
    """``exception()`` must not raise the severity of the site it replaces."""
    import logging

    import logger as logger_facade

    with _capture_records() as records:
        logger_facade.error("plain")
        try:
            raise ValueError("boom")
        except ValueError:
            logger_facade.exception("with traceback")

    assert [r.levelno for r in records] == [logging.ERROR, logging.ERROR]
    assert records[0].exc_info is None
    text = _traceback_text(records[1])
    assert "Traceback (most recent call last)" in text
    assert "ValueError: boom" in text


def test_converted_site_emits_record_with_exc_info(monkeypatch):
    """A converted site must reach a handler with a populated ``exc_info``.

    ``StepLoadThread.run`` is the smallest converted site: a single ``except``
    around ``load_step_file``. ``load_step_file`` reports a missing file or a
    missing pythonocc by *returning* a result rather than raising, so the
    loader is replaced with one that raises to drive the handler deliberately.
    """
    import logging

    pytest.importorskip("PySide6.QtCore")
    from step_3d import worker as worker_mod

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated STEP loader failure")

    monkeypatch.setattr(worker_mod, "load_step_file", _boom)

    emitted = []

    class _Signal:
        """Stand-in for a bound Qt signal: records what would have been emitted."""

        def emit(self, *args, **kwargs):
            emitted.append((args, kwargs))

    thread = worker_mod.StepLoadThread.__new__(worker_mod.StepLoadThread)
    thread._path = "part.step"
    thread._lin_deflection = 0.05
    import threading

    thread._cancel = threading.Event()
    thread.progress = _Signal()
    thread.result_ready = _Signal()

    with _capture_records() as records:
        thread.run()

    failures = [r for r in records if "STEP load failed" in r.getMessage()]
    assert failures, f"no STEP failure record; got {[r.getMessage() for r in records]}"
    record = failures[0]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.exc_info[0] is not None
    text = _traceback_text(record)
    assert "Traceback (most recent call last)" in text
    assert "RuntimeError: simulated STEP loader failure" in text

    # Control flow unchanged: the failure still produces an emitted result.
    assert emitted, "result_ready must still be emitted after the failure"
    result = emitted[0][0][0]
    assert result.error == "simulated STEP loader failure"
    assert result.parts == []
