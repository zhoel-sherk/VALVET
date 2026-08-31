# SPDX-License-Identifier: MIT
"""VSPD package-name parser and electrical classify (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass

from package_vspd.catalog import load_aliases, normalize_package_key
from parsers import regex_api as re

_CHIP_IMPERIAL = (
    "01005",
    "0201",
    "0402",
    "0603",
    "0805",
    "1206",
    "1210",
    "2010",
    "2512",
    "1812",
)

_IPC = re.compile(
    r"(?i)\b([A-Z]+?)(\d{2,4})P(\d{2,4})X(\d{2,4})-(\d{1,3})([NLM])?\b"
)
_KLC = re.compile(
    r"(?i)\b(SOIC|SSOP|TSSOP|MSOP|LQFP|TQFP|QFN|DFN|LGA|SOT|BGA|WLCSP)"
    r"-(\d+)(W)?(?:_EP)?(?:_[0-9.]+x[0-9.]+mm)?"
    r"(?:_P(?:itch)?[0-9.]+mm)?(?:_[NL])?\b"
)
_KLC_QFN_SIZE = re.compile(
    r"(?i)\b(QFN|DFN)-(\d+)_(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\b"
)
_HANWHA_CHIP = re.compile(r"(?i)\bChip-[RCL](\d{4,5})\b")
_HANWHA_PAREN = re.compile(r"(?i)Chip-[RCL]\d+\((\d{4,5})\)")
_PLCC = re.compile(r"(?i)(?<![A-Z0-9])PLCC[\s_-]*(\d{2,3})(?![0-9])")
_LQFP = re.compile(r"(?i)(?<![A-Z0-9])(?:L|T)?QFP[\s_-]*(\d{2,3})(?![0-9])")
_SOT_LOOSE = re.compile(
    r"(?i)(?<![A-Z0-9])SOT[\s_-]*(\d{2,3})(?:[\s_-]*([5-8]))?(?![0-9A-Z])"
)
_SOD_LOOSE = re.compile(r"(?i)(?<![A-Z0-9])SOD[\s_-]*(\d{3})(?![0-9])")
_METRIC_EIA = re.compile(r"(?i)\b(?:CAPC|RESC|INDC)(\d{4})\b")
_BGA = re.compile(r"(?i)\bBGA[_-]?(\d+(?:\.\d+)?)[_-](\d{2,4})\b")
_TI_D0008A = re.compile(r"(?i)\bD0008A\b")
_MC_SN = re.compile(r"(?i)(?:^|[^A-Z])SN(?:$|[^A-Z0-9])")
_MC_SM = re.compile(r"(?i)(?:^|[^A-Z])SM(?:$|[^A-Z0-9])")
_RES = re.compile(
    r"(?i)\b(resistor|res\b|ohm|\d+\s*[kKmM]?[oO]hm|chip-r|r\d{3,4})\b"
)
_CAP = re.compile(r"(?i)\b(capacitor|cap\b|mlcc|nf\b|uf\b|pf\b|chip-c)\b")
_IND = re.compile(r"(?i)\b(inductor|bead|ferrite|chip-l|\bL\d{3,4}\b)\b")


@dataclass(frozen=True)
class VspdHit:
    vspd_id: str
    confidence: str
    warnings: tuple[str, ...] = ()
    standard: str = ""


def classify_electrical(text: str) -> str:
    t = text or ""
    if _IND.search(t):
        return "ind"
    if _CAP.search(t):
        return "cap"
    if _RES.search(t):
        return "res"
    return "other"


def _alias_hit(key: str) -> VspdHit | None:
    aliases = load_aliases()
    vid = aliases.get(key)
    if vid:
        return VspdHit(vspd_id=vid, confidence="alias", standard="catalog")
    return None


def _ipc_hit(text: str) -> VspdHit | None:
    m = _IPC.search(text.replace(" ", ""))
    if not m:
        m = _IPC.search(text)
    if not m:
        return None
    fam = m.group(1).upper()
    pitch_c = int(m.group(2))
    span_c = int(m.group(3))
    pins = int(m.group(5))
    dens = (m.group(6) or "N").upper()
    warn: list[str] = []
    if dens != "N":
        warn.append(f"IPC density {dens} folded into same VSPD package")
    pitch_mm = pitch_c / 100.0
    span_mm = span_c / 100.0
    if fam == "SOIC" and pins == 8 and 1.2 <= pitch_mm <= 1.35 and span_mm < 7.0:
        return VspdHit("SOIC-8", "ipc", tuple(warn), "ipc")
    if fam == "SOIC" and pins == 16 and span_mm >= 7.0:
        return VspdHit("SOIC-16W", "ipc", tuple(warn), "ipc")
    if fam == "SOIC" and pins == 16:
        return VspdHit("SOIC-16", "ipc", tuple(warn), "ipc")
    if fam == "SOIC" and pins == 14:
        return VspdHit("SOIC-14", "ipc", tuple(warn), "ipc")
    if fam == "QFN" and pins == 32:
        return VspdHit("QFN-32_5x5", "ipc", tuple(warn), "ipc")
    return VspdHit("OTHER", "ipc-weak", tuple(warn) + (f"unmapped IPC {fam}-{pins}",), "ipc")


def _klc_hit(text: str) -> VspdHit | None:
    q = _KLC_QFN_SIZE.search(text)
    if q:
        fam, pins, lx, ly = q.group(1).upper(), int(q.group(2)), q.group(3), q.group(4)
        cand = f"{fam}-{pins}_{lx}x{ly}"
        aliases = load_aliases()
        if normalize_package_key(cand) in {
            normalize_package_key(v) for v in aliases.values()
        }:
            return VspdHit(cand, "klc", (), "kicad")
        from package_vspd.catalog import iter_seed_packages

        ids = {r["vspd_id"] for r in iter_seed_packages()}
        if cand in ids:
            return VspdHit(cand, "klc", (), "kicad")
    m = _KLC.search(text)
    if not m:
        return None
    fam = m.group(1).upper()
    pins = int(m.group(2))
    wide = bool(m.group(3))
    if fam == "SOIC" and pins == 8:
        return VspdHit("SOIC-8", "klc", (), "kicad")
    if fam == "SOIC" and pins == 16 and (wide or "7.5" in text):
        return VspdHit("SOIC-16W", "klc", (), "kicad")
    if fam == "SOIC" and pins == 16:
        return VspdHit("SOIC-16", "klc", (), "kicad")
    if fam == "SOIC" and pins == 14:
        return VspdHit("SOIC-14", "klc", (), "kicad")
    if fam == "SOT" and pins == 23:
        return VspdHit("SOT-23", "klc", (), "kicad")
    if fam == "MSOP" and pins == 8:
        return VspdHit("MSOP-8", "klc", (), "kicad")
    if fam == "TSSOP" and pins == 16:
        return VspdHit("TSSOP-16", "klc", (), "kicad")
    if fam == "LQFP" and pins == 48:
        return VspdHit("LQFP-48", "klc", (), "kicad")
    if fam == "QFN" and pins == 32:
        return VspdHit("QFN-32_5x5", "klc", (), "kicad")
    if fam == "WLCSP" and pins == 16:
        return VspdHit("WLCSP-16", "klc", (), "kicad")
    from package_vspd.catalog import iter_seed_packages

    ids = {r["vspd_id"] for r in iter_seed_packages()}
    wide_id = f"{fam}-{pins}W"
    plain = f"{fam}-{pins}"
    if wide and wide_id in ids:
        return VspdHit(wide_id, "klc", (), "kicad")
    if plain in ids:
        return VspdHit(plain, "klc", (), "kicad")
    return None


def _sot_sod_hit(text: str) -> VspdHit | None:
    s = _SOT_LOOSE.search(text)
    if s:
        n = int(s.group(1))
        extra = s.group(2)
        if extra:
            cand = f"SOT-23-{extra}"
        elif n == 23:
            cand = "SOT-23"
        elif n == 223:
            cand = "SOT-223"
        elif n == 323:
            cand = "SOT-323"
        elif n == 363:
            cand = "SOT-363"
        elif n == 563:
            cand = "SOT-563"
        elif n == 353:
            cand = "SOT-353"
        elif n == 523:
            cand = "SOT-523"
        elif n == 143:
            cand = "SOT-143"
        elif n == 89:
            cand = "SOT-89"
        else:
            cand = ""
        if cand:
            from package_vspd.catalog import iter_seed_packages

            ids = {r["vspd_id"] for r in iter_seed_packages()}
            if cand in ids:
                return VspdHit(cand, "loose", (), "jedec")
    d = _SOD_LOOSE.search(text)
    if d:
        cand = f"SOD-{d.group(1)}"
        from package_vspd.catalog import iter_seed_packages

        ids = {r["vspd_id"] for r in iter_seed_packages()}
        if cand in ids:
            return VspdHit(cand, "loose", (), "jedec")
    return None


def _imperial_code(code: str) -> str | None:
    if code == "03015":
        return "01005"
    if code in _CHIP_IMPERIAL:
        return code
    return None


def _chip_hit(text: str) -> VspdHit | None:
    paren = _HANWHA_PAREN.search(text)
    if paren:
        mapped = _imperial_code(paren.group(1))
        if mapped:
            return VspdHit(f"CHIP-{mapped}", "hanwha-paren", (), "hanwha")
    h = _HANWHA_CHIP.search(text)
    if h and not paren:
        mapped = _imperial_code(h.group(1))
        if mapped:
            return VspdHit(f"CHIP-{mapped}", "hanwha", (), "hanwha")
    compact = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    if compact.isdigit() and len(compact) >= 6:
        return None
    met = _METRIC_EIA.search(text)
    if met:
        d = met.group(1)
        lx, wy = int(d[:2]), int(d[2:])
        if lx == 10 and wy == 5:
            return VspdHit("CHIP-0402", "metric-eia", (), "metric")
        if lx == 16 and wy == 8:
            return VspdHit("CHIP-0603", "metric-eia", (), "metric")
        if lx == 20 and wy == 12:
            return VspdHit("CHIP-0805", "metric-eia", (), "metric")
        if lx == 32 and wy == 16:
            return VspdHit("CHIP-1206", "metric-eia", (), "metric")
    for code in sorted(_CHIP_IMPERIAL, key=len, reverse=True):
        if code == "1005":
            continue
        if code in compact:
            return VspdHit(f"CHIP-{code}", "imperial", (), "imperial")
    return None


def _lead_family_hit(text: str) -> VspdHit | None:
    from package_vspd.catalog import iter_seed_packages

    ids = {r["vspd_id"] for r in iter_seed_packages()}
    p = _PLCC.search(text)
    if p:
        n = int(p.group(1))
        for cand in (f"PLCC-{n}", "PLCC-44" if n >= 32 else "PLCC-28" if n >= 24 else "PLCC-20"):
            if cand in ids:
                return VspdHit(cand, "loose", (), "jedec")
    q = _LQFP.search(text)
    if q and "QFN" not in text.upper():
        n = int(q.group(1))
        for cand in (f"LQFP-{n}", f"TQFP-{n}"):
            if cand in ids:
                return VspdHit(cand, "loose", (), "jedec")
    return None


def _vendor_hit(text: str) -> VspdHit | None:
    if _TI_D0008A.search(text):
        return VspdHit("SOIC-8", "vendor", (), "vendor")
    if _MC_SM.search(text) and not _MC_SN.search(text):
        return VspdHit("SOIC-16W", "vendor", ("Microchip SM ≈ 208 mil wide SO",), "vendor")
    if _MC_SN.search(text):
        return VspdHit("SOIC-8", "vendor", ("Microchip SN ≈ 150 mil narrow SOIC",), "vendor")
    return None


def _bga_hit(text: str) -> VspdHit | None:
    m = _BGA.search(text.replace(" ", ""))
    if not m:
        return None
    pitch, balls = m.group(1), m.group(2)
    cand = f"BGA-{pitch}-{balls}"
    from package_vspd.catalog import iter_seed_packages

    ids = {r["vspd_id"] for r in iter_seed_packages()}
    if cand in ids:
        return VspdHit(cand, "bga", (), "jedec")
    return None


def parse_package(text: str) -> VspdHit:
    """Map a free-form package / footprint string to a VSPD id."""
    raw = (text or "").strip()
    if not raw:
        return VspdHit("OTHER", "empty", ("empty input",), "")
    raw = raw.replace("\\", "/")
    if raw.lower().endswith(".kicad_mod"):
        raw = raw.rsplit("/", 1)[-1][:-10]
    if ":" in raw:
        raw = raw.rsplit(":", 1)[-1].strip()
    key = normalize_package_key(raw)
    hit = _alias_hit(key)
    if hit:
        if hit.vspd_id == "SOIC-8" and normalize_package_key(raw) == "sop8":
            return VspdHit(
                hit.vspd_id,
                hit.confidence,
                ("JEITA SOP-8 may be 208 mil wide; VSPD SOIC-8 is 150 mil narrow",),
                hit.standard,
            )
        return hit
    for fn in (
        _ipc_hit,
        _klc_hit,
        _sot_sod_hit,
        _lead_family_hit,
        _chip_hit,
        _vendor_hit,
        _bga_hit,
    ):
        h = fn(raw)
        if h is None:
            continue
        if h.vspd_id != "OTHER":
            return h
        if h.confidence == "ipc-weak":
            return h
    return VspdHit("OTHER", "unmatched", (), "")


def apply_preset(text: str, preset: str) -> str:
    """Built-in string rewrite then caller should ``parse_package``."""
    t = text or ""
    p = (preset or "").strip().lower()
    if p in ("kicad", "klc", "kicad klc name→vspd", "kicad klc"):
        if ":" in t:
            t = t.split(":")[-1]
        t = t.replace(".kicad_mod", "")
        return t.strip()
    if p in ("ipc", "ipc→vspd"):
        return t.replace(" ", "")
    if p in ("hanwha", "hanwha partgroup→vspd"):
        return t.replace("_", "-")
    return t
