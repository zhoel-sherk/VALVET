"""
BOM comment parsers for Clean BOM (inferit presets + R/C/L/OTHER regex).

On `import parsers`, built-in modules under this directory and optional user scripts
(see `parsers.registry.user_parsers_help_text()`) are discovered automatically.
"""

from __future__ import annotations

from parsers.registry import (
    ensure_discovered,
    iter_parser_module_infos,
    loaded_parser_catalog_text,
)

ensure_discovered()

__all__ = [
    "ensure_discovered",
    "iter_parser_module_infos",
    "loaded_parser_catalog_text",
]
