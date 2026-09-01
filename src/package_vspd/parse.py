# SPDX-License-Identifier: MIT
"""VSPD package-name parser and electrical classify (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass

from package_vspd.catalog import load_aliases, normalize_package_key
from parsers import regex_api

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

_IPC = regex_api.compile(
    r"(?i)\b([A-Z]+?)(\d{2,4})P(\d{2,4})X(\d{2,4})-(\d{1,3})([NLM])?\b"
)
_KLC = regex_api.compile(
    r"(?i)\b(SOIC|SSOP|TSSOP|MSOP|LQFP|TQFP|QFN|DFN|LGA|SOT|BGA|WLCSP)"
    r"-(\d+)(W)?(?:_EP)?(?:_[0-9.]+x[0-9.]+mm)?"
    r"(?:_P(?:itch)?[0-9.]+mm)?(?:_[NL])?\b"
)
_KLC_QFN_SIZE = regex_api.compile(
    r"(?i)\b(QFN|DFN|WQFN)-(\d+)_(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\b"
)
_QFN_PAREN = regex_api.compile(
    r"(?i)\b(?:W)?QFN-?(\d+)\s*[\(\[]\s*(\d+(?:\.\d+)?)\s*(?:mm)?\s*[xX×]\s*(\d+(?:\.\d+)?)"
)
_DFN_LOOSE = regex_api.compile(
    r"(?i)\b(?:DFN|PDFN|UTDFN|TDFN)(\d+)?[\s_-]*(?:\d+)?[xX×](\d+(?:\.\d+)?)"
    r"[\s_-]*(?:\d+)?[xX×](\d+(?:\.\d+)?)"
)
_QFN_LOOSE = regex_api.compile(
    r"(?i)\b(?:W)?QFN-?(\d+)(?:[\s_]+(\d+(?:\.\d+)?)[xX×](\d+(?:\.\d+)?))?"
)
_WSON = regex_api.compile(r"(?i)\bWSON-?(\d+)\b")
_XTAL_CODE = regex_api.compile(r"(?i)\b(?:XTAL|CRYSTAL|CRY)[\s_-]*(\d{4})\b")
_XTAL_MM = regex_api.compile(
    r"(?i)(?:\bXTAL\b|\bCRYSTAL\b|\bCRY\b|MHZ|KHZ).{0,40}?"
    r"(\d(?:\.\d+)?)\s*[*×xX]\s*(\d(?:\.\d+)?)"
)
_CIRCLE_D = regex_api.compile(
    r"(?i)(?:CIRCLE|NUT|WASHER).{0,30}?[dD](?:=|ia\.?)?\s*(\d+(?:\.\d+)?)"
)
_CIRCLE_NUT_DIM = regex_api.compile(r"(?i)\bM\d+(?:\.\d+)?[xX](\d+(?:\.\d+)?)")
_CIRCLE_CHIP = regex_api.compile(r"(?i)\bCHIP[\s_-]*CIRCLE\b")
_POSCAP_CASE = regex_api.compile(r"(?i)(?:3528|7343)[/\(]")
_HANWHA_CHIP = regex_api.compile(r"(?i)\bChip-[RCL](\d{4,5})\b")
_HANWHA_PAREN = regex_api.compile(r"(?i)Chip-[RCL]\d+\((\d{4,5})\)")
_PLCC = regex_api.compile(r"(?i)(?<![A-Z0-9])PLCC[\s_-]*(\d{2,3})(?![0-9])")
_LQFP = regex_api.compile(r"(?i)(?<![A-Z0-9])(?:L|T)?QFP[\s_-]*(\d{2,3})(?![0-9])")
_SOT_LOOSE = regex_api.compile(
    r"(?i)(?<![A-Z0-9])SOT[\s_-]*(\d{2,3})(?:[\s_-]*([5-8]))?(?![0-9A-Z])"
)
_SOD_LOOSE = regex_api.compile(r"(?i)(?<![A-Z0-9])SOD[\s_-]*(\d{3})(?![0-9])")
_METRIC_EIA = regex_api.compile(r"(?i)\b(?:CAPC|RESC|INDC)(\d{4})\b")
_BGA = regex_api.compile(r"(?i)\bBGA[_-]?(\d+(?:\.\d+)?)[_-](\d{2,4})\b")
_TI_D0008A = regex_api.compile(r"(?i)\bD0008A\b")
_MC_SN = regex_api.compile(r"(?i)(?:^|[^A-Z])SN(?:$|[^A-Z0-9])")
_MC_SM = regex_api.compile(r"(?i)(?:^|[^A-Z])SM(?:$|[^A-Z0-9])")
_RES = regex_api.compile(
    r"(?i)\b(resistor|res\b|ohm|\d+\s*[kKmM]?[oO]hm|chip-r|r\d{3,4})\b"
)
_CAP = regex_api.compile(r"(?i)\b(capacitor|cap\b|mlcc|nf\b|uf\b|pf\b|chip-c)\b")
_IND = regex_api.compile(r"(?i)\b(inductor|bead|ferrite|chip-l|\bL\d{3,4}\b)\b")


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


def _catalog_ids() -> set[str]:
    from package_vspd.catalog import iter_seed_packages

    return {r["vspd_id"] for r in iter_seed_packages()}


def _best_qfn(pins: int, lx: float, ly: float) -> str | None:
    ids = _catalog_ids()
    lx_s, ly_s = f"{lx:g}", f"{ly:g}"
    for cand in (
        f"QFN-{pins}_{lx_s}x{ly_s}",
        f"QFN-{pins}_{int(lx)}x{int(ly)}",
        f"QFN-{pins}_{int(lx)}x{int(ly)}" if lx == ly else "",
    ):
        if cand and cand in ids:
            return cand
    for vid in ids:
        if not vid.startswith("QFN-"):
            continue
        head = vid.split("-", 1)[1]
        pin_s = ""
        for ch in head:
            if ch.isdigit():
                pin_s += ch
            else:
                break
        if pin_s and int(pin_s) == pins:
            return vid
    return None


def _best_dfn(pins: int, lx: float, ly: float) -> str | None:
    ids = _catalog_ids()
    lx_s, ly_s = f"{lx:g}", f"{ly:g}"
    for cand in (
        f"DFN-{pins}_{lx_s}x{ly_s}",
        f"DFN-{pins}_{int(lx)}x{int(ly)}",
    ):
        if cand in ids:
            return cand
    if pins == 56 and "DFN-56_5x6" in ids:
        return "DFN-56_5x6"
    return None


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
    return VspdHit(
        "OTHER", "ipc-weak", tuple(warn) + (f"unmapped IPC {fam}-{pins}",), "ipc"
    )


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
        elif n == 723:
            cand = "SOT-723"
        elif n == 143:
            cand = "SOT-143"
        elif n == 89:
            cand = "SOT-89"
        else:
            cand = ""
        if cand and cand in _catalog_ids():
            return VspdHit(cand, "loose", (), "jedec")
    ts = regex_api.search(r"(?i)\bTSOT[\s_-]*23[\s_-]*([5-8])\b", text)
    if ts:
        cand = f"TSOT-23-{ts.group(1)}"
        if cand in _catalog_ids():
            return VspdHit(cand, "loose", (), "jedec")
    sc = regex_api.search(r"(?i)\bSC[\s_-]*70(?:[\s_-]*([5-8]))?\b", text)
    if sc:
        cand = "SOT-323"
        if cand in _catalog_ids():
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
    compact = regex_api.sub(r"[^A-Za-z0-9]", "", text).upper()
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


def _xtal_code_to_id(code: str) -> str | None:
    mapping = {
        "1612": "XTAL-1612",
        "2016": "XTAL-2016",
        "2520": "XTAL-2520",
        "3215": "XTAL-3215",
        "3225": "XTAL-3225",
        "5032": "XTAL-5032",
    }
    vid = mapping.get(code)
    return vid if vid in _catalog_ids() else None


def _xtal_hit(text: str) -> VspdHit | None:
    c = _XTAL_CODE.search(text)
    if c:
        vid = _xtal_code_to_id(c.group(1))
        if vid:
            return VspdHit(vid, "xtal", (), "jedec")
    m = _XTAL_MM.search(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        lx, wy = max(a, b), min(a, b)
        vid = None
        if abs(lx - 3.2) < 0.2 and abs(wy - 2.5) < 0.2:
            vid = "XTAL-3225"
        elif abs(lx - 3.2) < 0.2 and abs(wy - 1.5) < 0.2:
            vid = "XTAL-3215"
        elif abs(lx - 2.5) < 0.2 and abs(wy - 2.0) < 0.2:
            vid = "XTAL-2520"
        elif abs(lx - 2.0) < 0.2 and abs(wy - 1.6) < 0.2:
            vid = "XTAL-2016"
        else:
            vid = None
        if vid and vid in _catalog_ids():
            return VspdHit(vid, "xtal-mm", (), "jedec")
    return None


def _circle_hit(text: str) -> VspdHit | None:
    if _CIRCLE_CHIP.search(text):
        return VspdHit("CIRCLE-GENERIC", "hanwha", (), "hanwha")

    def _match_dia(dia: float) -> VspdHit | None:
        ids = _catalog_ids()
        best = ""
        best_delta = 999.0
        for vid in ids:
            if not vid.startswith("CIRCLE-D"):
                continue
            try:
                catalog_d = float(vid.split("D", 1)[1])
            except ValueError:
                continue
            delta = abs(catalog_d - dia)
            if delta < best_delta:
                best_delta = delta
                best = vid
        if best and best_delta < 0.25:
            return VspdHit(best, "circle", (), "catalog")
        if "CIRCLE-GENERIC" in ids:
            return VspdHit("CIRCLE-GENERIC", "circle", (), "catalog")
        return None

    nd = _CIRCLE_NUT_DIM.search(text)
    if nd:
        hit = _match_dia(float(nd.group(1)))
        if hit:
            return hit
    d = _CIRCLE_D.search(text)
    if d:
        hit = _match_dia(float(d.group(1)))
        if hit:
            return hit
    if regex_api.search(r"(?i)\b(?:copper\s+)?nut\b", text):
        if "CIRCLE-GENERIC" in _catalog_ids():
            return VspdHit("CIRCLE-GENERIC", "circle", (), "catalog")
    return None


def _leadless_hit(text: str) -> VspdHit | None:
    w = _WSON.search(text)
    if w:
        cand = f"WSON-{w.group(1)}"
        if cand in _catalog_ids():
            return VspdHit(cand, "loose", (), "jedec")
    qp = _QFN_PAREN.search(text)
    if qp:
        pins, lx, ly = int(qp.group(1)), float(qp.group(2)), float(qp.group(3))
        vid = _best_qfn(pins, lx, ly)
        if vid:
            return VspdHit(vid, "loose", (), "jedec")
    q = _KLC_QFN_SIZE.search(text)
    if q:
        fam, pins, lx, ly = (
            q.group(1).upper(),
            int(q.group(2)),
            float(q.group(3)),
            float(q.group(4)),
        )
        if fam in {"QFN", "WQFN"}:
            vid = _best_qfn(pins, lx, ly)
        else:
            vid = _best_dfn(pins, lx, ly)
        if vid:
            return VspdHit(vid, "loose", (), "jedec")
    ql = _QFN_LOOSE.search(text)
    if ql:
        pins = int(ql.group(1))
        lx = float(ql.group(2)) if ql.group(2) else 0.0
        ly = float(ql.group(3)) if ql.group(3) else lx
        vid = _best_qfn(pins, lx, ly) if lx else _best_qfn(pins, 3.0, 3.0)
        if vid:
            return VspdHit(vid, "loose", (), "jedec")
    dl = _DFN_LOOSE.search(text)
    if dl:
        pins = int(dl.group(1) or 8)
        lx, ly = float(dl.group(2)), float(dl.group(3))
        vid = _best_dfn(pins, lx, ly)
        if vid:
            return VspdHit(vid, "loose", (), "jedec")
    if (
        regex_api.search(r"(?i)\bDFN[\s_-]*56\b", text)
        and "DFN-56_5x6" in _catalog_ids()
    ):
        return VspdHit("DFN-56_5x6", "loose", (), "jedec")
    return None


def _poscap_hit(text: str) -> VspdHit | None:
    if _POSCAP_CASE.search(text):
        if "7343" in text.upper() and "TANT-D" in _catalog_ids():
            return VspdHit("TANT-D", "poscap", (), "vendor")
        if "3528" in text.upper() and "TANT-B" in _catalog_ids():
            return VspdHit("TANT-B", "poscap", (), "vendor")
    if regex_api.search(r"(?i)\bPOSCAP\b", text):
        if "TANT-B" in _catalog_ids():
            return VspdHit("TANT-B", "poscap", (), "vendor")
    if regex_api.search(r"(?i)\bSP[\s_-]*CAP\b", text) and "TANT-E" in _catalog_ids():
        return VspdHit("TANT-E", "poscap", (), "vendor")
    return None


def _lead_family_hit(text: str) -> VspdHit | None:
    from package_vspd.catalog import iter_seed_packages

    ids = {r["vspd_id"] for r in iter_seed_packages()}
    p = _PLCC.search(text)
    if p:
        n = int(p.group(1))
        for cand in (
            f"PLCC-{n}",
            "PLCC-44" if n >= 32 else "PLCC-28" if n >= 24 else "PLCC-20",
        ):
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
        return VspdHit(
            "SOIC-16W", "vendor", ("Microchip SM ≈ 208 mil wide SO",), "vendor"
        )
    if _MC_SN.search(text):
        return VspdHit(
            "SOIC-8", "vendor", ("Microchip SN ≈ 150 mil narrow SOIC",), "vendor"
        )
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
        _leadless_hit,
        _sot_sod_hit,
        _xtal_hit,
        _circle_hit,
        _poscap_hit,
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
