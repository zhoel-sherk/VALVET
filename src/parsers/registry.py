"""
Discovery and registration of BOM parser modules.

Built-in modules live in this package (`*.py` except helpers). Optional user scripts
are loaded from:

  • `$VALVET_USER_PARSERS_DIR/*.py` (legacy: `$BOOMER_USER_PARSERS_DIR`)
  • Otherwise: under the same per-user app folder as autosave (see ``app_paths.user_parsers_dir()``),
    e.g. Linux ``~/.local/share/VALVET/user_parsers``,
    Windows ``%APPDATA%\\VALVET\\VALVET\\user_parsers``.

Each user file should call `register_parser_module(...)` like the built-ins (see
`res_pars.py` as a template).
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import logger

# ---------------------------------------------------------------------------
# Display metadata (GUI / CLI catalog)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParserModuleInfo:
    """One loadable parser unit shown in Clean BOM → Debug settings."""

    module_stem: str
    role: str
    gui_name: str
    cli_name: str
    summary: str


_REGISTRY: list[ParserModuleInfo] = []

_BUILTIN_SKIP = frozenset(
    {
        "registry",
        "constants",
        "bom_text_utils",
        "regex_api",
        "vendor_context_merge",
        "formatting",
        "__init__",
    }
)


def register_parser_module(info: ParserModuleInfo) -> None:
    """Called from parser modules at import time."""
    for existing in _REGISTRY:
        if (
            existing.module_stem == info.module_stem
            and existing.role == info.role
            and existing.cli_name == info.cli_name
        ):
            return
    _REGISTRY.append(info)


def iter_parser_module_infos() -> tuple[ParserModuleInfo, ...]:
    return tuple(_REGISTRY)


def default_builtin_parsers_dir() -> Path:
    return Path(__file__).resolve().parent


def default_user_parsers_dir() -> Path:
    env = (
        os.environ.get("VALVET_USER_PARSERS_DIR", "").strip()
        or os.environ.get("BOOMER_USER_PARSERS_DIR", "").strip()
    )
    if env:
        return Path(env).expanduser()
    from app_paths import user_parsers_dir

    canonical = user_parsers_dir()
    if sys.platform == "win32":
        legacy = (
            Path(os.environ.get("APPDATA", "") or str(Path.home()))
            / "boomer"
            / "user_parsers"
        )
    else:
        legacy = Path.home() / ".local/share/boomer/user_parsers"
    if legacy.is_dir() and not any(canonical.glob("*.py")) and any(legacy.glob("*.py")):
        return legacy
    return canonical


def user_parsers_help_text() -> str:
    u = default_user_parsers_dir()
    return (
        "User parsers: drop `.py` files that call `register_parser_module(...)` into:\n"
        f"  • {u}\n"
        "  • or set VALVET_USER_PARSERS_DIR (legacy: BOOMER_USER_PARSERS_DIR) to a folder of `.py` scripts.\n"
        "Built-in parsers live next to the app in `…/src/parsers/` — copy a file like "
        "`res_pars.py` as a starting point. Restart the app after adding scripts."
    )


def loaded_parser_catalog_text() -> str:
    """Human-readable list for the debug dialog."""
    lines = ["Loaded BOM parser modules (inferit + R/C/L + OTHER):"]
    if not _REGISTRY:
        lines.append(
            "  (none registered yet — call parsers.registry.ensure_discovered())"
        )
        return "\n".join(lines)
    by_role: dict[str, list[ParserModuleInfo]] = {}
    for info in sorted(_REGISTRY, key=lambda x: (x.role, x.cli_name)):
        by_role.setdefault(info.role, []).append(info)
    for role in sorted(by_role):
        lines.append(f"  [{role}]")
        for info in by_role[role]:
            lines.append(f"    • {info.gui_name}")
            lines.append(f"      CLI: {info.cli_name}  ({info.module_stem})")
            if info.summary:
                lines.append(f"      {info.summary}")
    lines.append("")
    lines.append(user_parsers_help_text())
    return "\n".join(lines)


def _import_builtin_modules() -> None:
    pkg_dir = default_builtin_parsers_dir()
    pkg = __package__ or "parsers"
    for path in sorted(pkg_dir.glob("*.py")):
        stem = path.stem
        if stem.startswith("_") or stem in _BUILTIN_SKIP:
            continue
        mod_name = f"{pkg}.{stem}"
        if mod_name not in sys.modules:
            importlib.import_module(mod_name)


def _load_user_scripts(user_dir: Path) -> None:
    if not user_dir.is_dir():
        return
    for path in sorted(user_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        mod_name = f"parsers._user_{path.stem}"
        if mod_name in sys.modules:
            continue
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            logger.info("Loaded user parser script %s", path)
        except Exception as e:
            logger.warning("User parser %s failed to load: %s", path, e)


def ensure_discovered() -> None:
    """Import every built-in parser module once, then optional user scripts."""
    if getattr(ensure_discovered, "_done", False):
        return
    try:
        _import_builtin_modules()
        _load_user_scripts(default_user_parsers_dir())
    finally:
        ensure_discovered._done = True  # type: ignore[attr-defined]
