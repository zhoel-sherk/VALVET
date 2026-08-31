"""Qt-free VSPD package catalog (names, aliases, outlines)."""

from package_vspd.parse import VspdHit, apply_preset, classify_electrical, parse_package
from package_vspd.resolve import ResolveHit, resolve_unique_packages
from package_vspd.store import PackageStore, normalize_package_key

__all__ = [
    "PackageStore",
    "ResolveHit",
    "VspdHit",
    "apply_preset",
    "classify_electrical",
    "normalize_package_key",
    "parse_package",
    "resolve_unique_packages",
]
