"""
PN Original — Vendor-specific part number parsers

Package layout (same idea as e.g. ``samsung_capacitor.py`` module headers):

Part Number Format:
Each vendor module documents its own PN pattern (MLCC CL/GRM/CC…, resistors RC/RM/WR…).

Examples:
- Vendor ``parse()`` returns normalized underscore tokens (e.g. ``0402_100nF_50V_X7R_10%``, ``0402_10K_1%``); optional ``CAP_`` / ``RES_`` prefixes in docs are illustrative only.

Each converter module must define:
- VENDOR_NAME: str — unique registry key (two modules must not share the same name)
- COMPONENT_TYPES: list[str] — supported types (CAP, RES, IND, …)
- parse(pn: str, component_type: str) -> str | None — normalize PN for Clean BOM / vendor step
- PARSER_PRIORITY: int (optional, default 0) — higher runs first in ``parse_pn``
"""

import importlib
import os
import sys

from parsers.regex_api import sub

# ``src/`` is on PYTHONPATH in tests/CI; keep a fallback when this package is
# imported without that (parent of ``pn_original`` is ``src``).
_src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src not in sys.path:
    sys.path.insert(0, _src)

try:
    import logger
except Exception:
    # Fallback if logger not available
    class MockLogger:
        def debug(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

        def warning(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            pass

        def exception(self, *args, **kwargs):
            pass

    logger = MockLogger()

CONVERTERS = {}


def load_converters():
    """Load all converter modules from this package"""
    global CONVERTERS

    CONVERTERS.clear()
    converters_dir = os.path.dirname(__file__)
    for filename in sorted(os.listdir(converters_dir)):
        if filename.startswith("_") or not filename.endswith(".py"):
            continue
        if filename == "__init__.py":
            continue

        module_name = filename[:-3]
        try:
            module = importlib.import_module(f"pn_original.{module_name}")
            vendor = getattr(module, "VENDOR_NAME", module_name.upper())
            types = getattr(module, "COMPONENT_TYPES", [])

            CONVERTERS[vendor] = {"module": module, "types": types}
            logger.info("Loaded PN converter: %s %s", vendor, types)
        except Exception:
            logger.exception("Failed to load PN converter module %s", module_name)


def _normalize_part_number_for_vendors(pn: str) -> str:
    """
    BOM fields are often 'VENDOR/MPN' or 'MFR/RC0603...'; converters expect the bare MPN.
    Strips tags like <G> from the end.
    """
    s = str(pn).strip()
    s = sub(r"\s*<[gG]>\s*$", "", s).strip()
    s = sub(r"^[\"'`]+|[\"'`]+$", "", s).strip()
    s = (
        s.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )
    # e.g. TA-I/ RM04… → last segment is parseable (same as "TA-I/RM04…" after this)
    s = sub(r"/\s+", "/", s)
    if "/" in s:
        s = s.split("/")[-1].strip()
    # Deterministic normalization only: no guessing, no cross-vendor mutation.
    s = sub(r"[;,]+$", "", s).strip()
    s = sub(r"\s+", "", s)
    # Common vendor code variant: RC0402-JR... -> RC0402JR...
    s = sub(r"^([A-Z]{2}\d{4})-([A-Z0-9].*)$", r"\1\2", s)
    return s


def normalize_mpn_bare(pn: str) -> str:
    """Public: bare MPN from «VENDOR/MPN <G>» for web lookup."""
    return _normalize_part_number_for_vendors(pn)


def parse_pn(pn: str, component_type: str, config) -> str | None:
    """
    Parse original PN using vendor-specific converters.

    Vendor parsers are consulted in ``PARSER_PRIORITY`` order (highest first) and the
    first non-empty result wins.

    Arbiter contract for a vendor whose ``parse()`` **raises**:
      the exception is recorded (``logger.exception``, deduplicated per
      ``(pn, vendor)``), the vendor is skipped, and the loop continues to the next
      vendor. Returning a *different* vendor's part is the historical behaviour and
      is kept because most BOM rows are not the raising vendor's format at all — but
      the raise is now logged at exception level with a traceback so the substituted
      value is never silent again. A vendor that legitimately returns ``None`` is
      indistinguishable in outcome and simply falls through.

    Args:
        pn: Original part number
        component_type: Expected component type (CAP, RES, IND)
        config: CleanConfig instance

    Returns:
        Parsed component in standard format, or None if no converter matched
    """
    if not CONVERTERS:
        load_converters()

    s = _normalize_part_number_for_vendors(pn)

    ordered = sorted(
        (
            (vendor, converter)
            for vendor, converter in CONVERTERS.items()
            if component_type in converter["types"]
        ),
        key=lambda vc: -getattr(vc[1]["module"], "PARSER_PRIORITY", 0),
    )

    for vendor, converter in ordered:
        module = converter["module"]
        parse_func = getattr(module, "parse", None)
        if not parse_func:
            continue
        try:
            result = parse_func(s, component_type)
        except Exception:
            # Deduped: a systematic parser bug repeats per BOM row, and one
            # traceback per row floods the log (see 2.8).
            _log_vendor_failure_once(pn, vendor, component_type)
            continue
        if result:
            logger.debug("Parsed %r -> %r (%s)", pn, result, vendor)
            return result

    return None


# Raised-vendor pairs already reported this run, so a systemic parser bug emits one
# traceback instead of one per BOM row. Bounded so a long session cannot grow it.
_MAX_REPORTED_VENDOR_FAILURES = 200
_REPORTED_VENDOR_FAILURES: set[tuple[str, str, str]] = set()


def _log_vendor_failure_once(pn: str, vendor: str, component_type: str) -> None:
    """``logger.exception`` for a raising vendor, once per ``(pn, vendor, type)``."""
    key = (str(pn), str(vendor), str(component_type))
    if key in _REPORTED_VENDOR_FAILURES:
        return
    _REPORTED_VENDOR_FAILURES.add(key)
    if len(_REPORTED_VENDOR_FAILURES) > _MAX_REPORTED_VENDOR_FAILURES:
        logger.error(
            "Vendor PN parser failures exceeded %d; further per-PN failure "
            "reports suppressed",
            _MAX_REPORTED_VENDOR_FAILURES,
        )
        _REPORTED_VENDOR_FAILURES.clear()
        return
    logger.exception(
        "Vendor %s parser raised on %s (%s); falling through to the next vendor — "
        "the resulting PN may not belong to %s",
        vendor,
        pn,
        component_type,
        vendor,
    )


def _reset_vendor_failure_log() -> None:
    """Test hook: forget which vendor failures were already reported."""
    _REPORTED_VENDOR_FAILURES.clear()


def get_supported_vendors() -> list[str]:
    """Return list of supported vendor names"""
    if not CONVERTERS:
        load_converters()
    return list(CONVERTERS.keys())
