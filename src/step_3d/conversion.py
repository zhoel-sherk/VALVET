"""Run an optional external STEP → mesh converter via subprocess."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class ConversionResult:
    ok: bool
    returncode: int
    command_display: str
    stdout: str
    stderr: str

    @property
    def combined_log(self) -> str:
        parts = []
        if self.stdout.strip():
            parts.append(self.stdout.strip())
        if self.stderr.strip():
            parts.append(self.stderr.strip())
        return "\n".join(parts) if parts else "(no process output)"


def expand_command_template(template: str, in_path: str, out_path: str) -> str:
    """Replace ``{in}`` / ``{out}`` placeholders (paths are not shell-escaped here)."""
    return template.replace("{in}", in_path).replace("{out}", out_path)


def template_to_argv(expanded: str) -> list[str]:
    """Split a full command line into argv (POSIX vs Windows rules)."""
    posix = os.name != "nt"
    argv = shlex.split(expanded, posix=posix)
    if not posix:
        # shlex.split(posix=False) can leave a redundant pair of " around -c payloads
        # (so Python sees -c '"import sys"' instead of -c 'import sys'). Strip one outer
        # MSVC-style quote layer from each token to match typical CreateProcess argv.
        argv = [_strip_outer_double_quotes(a) for a in argv]
    return argv


def _strip_outer_double_quotes(s: str) -> str:
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def run_step_to_mesh(
    step_path: str,
    mesh_out_path: str,
    *,
    command_template: str,
    timeout_s: float = 300.0,
    cwd: str | None = None,
) -> ConversionResult:
    """
    Run ``command_template`` after substituting ``{in}`` and ``{out}``.

    The template must expand to a single shell-style command line, e.g.::

        mystepconv "{in}" "{out}"
    """
    step_path = os.path.abspath(step_path)
    mesh_out_path = os.path.abspath(mesh_out_path)
    expanded = expand_command_template(
        command_template.strip(), step_path, mesh_out_path
    )
    if not expanded.strip():
        return ConversionResult(
            ok=False,
            returncode=-1,
            command_display="",
            stdout="",
            stderr="empty command template",
        )
    argv = template_to_argv(expanded)
    if not argv:
        return ConversionResult(
            ok=False,
            returncode=-1,
            command_display=expanded,
            stdout="",
            stderr="command parses to empty argv",
        )
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        err = (e.stderr or "") if isinstance(e.stderr, str) else str(e)
        return ConversionResult(
            ok=False,
            returncode=-9,
            command_display=expanded,
            stdout=out,
            stderr=err + "\n(timeout)",
        )
    except OSError as e:
        return ConversionResult(
            ok=False,
            returncode=-1,
            command_display=expanded,
            stdout="",
            stderr=str(e),
        )
    ok = (
        proc.returncode == 0
        and os.path.isfile(mesh_out_path)
        and os.path.getsize(mesh_out_path) > 0
    )
    return ConversionResult(
        ok=ok,
        returncode=int(proc.returncode),
        command_display=expanded,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )
