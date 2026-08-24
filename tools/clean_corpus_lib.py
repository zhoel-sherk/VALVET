"""
Shared logic for Clean BOM golden corpus (harvest, profile, validate, LLM report).

Import with repo root on PYTHONPATH and ``src`` for clean_component.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

# Repo layout: tools/ sibling to src/
_BOOMER_ROOT = Path(__file__).resolve().parents[1]
_SRC = _BOOMER_ROOT / "src"
if str(_SRC) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_SRC))

from clean_component import clean_one  # noqa: E402
from clean_alerts import analyze_token_alert  # noqa: E402
from clean_types import CleanConfig, default_clean_config  # noqa: E402
from machine_library.hanwha_partnames import load_partnames_snapshot  # noqa: E402
from parsers.bom_text_utils import DEFAULT_DOUBLE_COMMENT_JOIN, merge_clean_comment_cell_parts  # noqa: E402

FIXTURES_DIR = _BOOMER_ROOT / "tests" / "fixtures" / "clean_corpus"
DEFAULT_PROFILE = FIXTURES_DIR / "profile.json"
DEFAULT_GOLDEN = FIXTURES_DIR / "golden.xlsx"
DEFAULT_MANIFEST = FIXTURES_DIR / "manifest.jsonl"
DEFAULT_DRAFT = FIXTURES_DIR / "draft.xlsx"
DEFAULT_USER_TEMP = _BOOMER_ROOT / "user_temp"
DEFAULT_CURATED_XLSX = DEFAULT_USER_TEMP / "component_test.xlsx"

TSV_COLUMNS = [
    "id",
    "source_file",
    "source_kind",
    "original",
    "cleaned_auto",
    "type_auto",
    "source_auto",
    "alert_auto",
    "expected_cleaned",
    "expected_type",
    "expected_source",
    "status",
    "notes",
]

GOLDEN_COLUMNS = [
    "id",
    "source_file",
    "source_kind",
    "original",
    "expected_cleaned",
    "expected_type",
    "expected_source",
    "status",
    "notes",
]

# Excel-friendly superset (auto columns help while reviewing in Excel).
GOLDEN_EDITOR_COLUMNS = [
    "id",
    "source_file",
    "source_kind",
    "original",
    "cleaned_auto",
    "type_auto",
    "source_auto",
    "alert_auto",
    "expected_cleaned",
    "expected_type",
    "expected_source",
    "status",
    "notes",
]


class _AllegroTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_tr = False
        self._in_td = False
        self._cells: list[str] = []
        self._row: list[str] = []
        self.rows: list[list[str]] = []
        self.header: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "tr":
            self._in_tr = True
            self._row = []
        elif t == "td" and self._in_tr:
            self._in_td = True
            self._cells = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "td" and self._in_td:
            self._in_td = False
            self._row.append("".join(self._cells).strip())
        elif t == "tr" and self._in_tr:
            self._in_tr = False
            if self._row:
                if not self.header:
                    self.header = [c.upper() for c in self._row]
                else:
                    self.rows.append(self._row)

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._cells.append(data)


def _stable_id(original: str, source_file: str) -> str:
    h = hashlib.sha256(f"{source_file}\0{original}".encode("utf-8")).hexdigest()
    return h[:12]


def _normalize_original(s: str) -> str:
    t = str(s).strip()
    t = re.sub(r"\s*<[gG]>\s*$", "", t).strip()
    return t


def harvest_from_allegro_html(path: Path, rel: str) -> Iterator[dict[str, str]]:
    parser = _AllegroTableParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    idx_type = idx_val = -1
    for i, h in enumerate(parser.header):
        if h == "COMP_DEVICE_TYPE":
            idx_type = i
        elif h == "COMP_VALUE":
            idx_val = i
    for row in parser.rows:
        if idx_type >= 0 and idx_type < len(row):
            v = _normalize_original(row[idx_type])
            if len(v) >= 2:
                yield {
                    "source_file": rel,
                    "source_kind": "allegro_html",
                    "original": v,
                }
        if idx_val >= 0 and idx_val < len(row):
            v = _normalize_original(row[idx_val])
            if len(v) >= 2 and (idx_type < 0 or v != _normalize_original(row[idx_type])):
                yield {
                    "source_file": rel,
                    "source_kind": "allegro_html_value",
                    "original": v,
                }


def harvest_from_cmp_report(path: Path, rel: str) -> Iterator[dict[str, str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "device type" not in text.lower() and "COMPONENT" not in text:
        return
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("-") or "refdes" in line.lower():
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", parts[0]):
            continue
        device = parts[1]
        if len(device) < 4:
            continue
        yield {
            "source_file": rel,
            "source_kind": "cmp_report",
            "original": _normalize_original(device),
        }


def _excel_cell_str(val: object) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and pd.isna(val):
        return ""
    return str(val).strip()


_TABULAR_EXCLUDE_COL_HINTS = (
    "reference",
    "refdes",
    "ref des",
    "designator",
    "位号",
    "позиц",
    "ref#",
)

_TABULAR_INCLUDE_COL_HINTS = (
    "comment",
    "value",
    "description",
    "desc",
    "component",
    "device",
    "spec",
    "物料",
    "描述",
    "备注",
    "规格",
    "comment1",
    "comment2",
    "partname",
    "part name",
    "name of material",
    "mfr",
    "manufacturer",
    "mpn",
)

_NOT_REFDES_LITERALS = frozenset(
    s.upper()
    for s in (
        "RES",
        "CAP",
        "IND",
        "SMD",
        "OTHER",
        "NA",
        "N/A",
        "TBD",
        "DNP",
    )
)


def _single_reference_designator_token(tok: str) -> bool:
    """True if ``tok`` looks like one PCB reference (R1, RP1054, SATA_1, HDMI)."""
    t = tok.strip()
    if not t or len(t) > 16:
        return False
    if re.search(r"[\s./\\]", t):
        return False
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", t):
        return False
    u = t.upper()
    if u in _NOT_REFDES_LITERALS:
        return False
    if re.search(r"\d", t):
        if len(t) > 11:
            return False
        return bool(
            re.fullmatch(
                r"[A-Z]{1,4}[A-Z0-9]*\d+[A-Z0-9]*(?:[-_][A-Z0-9]+)*|"
                r"[A-Z]{2,8}_\d+|"
                r"[A-Z]{1,4}\d+[-_][A-Z0-9]+",
                u,
            )
        )
    return 2 <= len(u) <= 12


_PROCUREMENT_CODE_RE = re.compile(
    r"^(?:"
    r"E(?:\.[A-Z]{1,3})+\.\d{4,}|"
    r"\d{2}(?:\.\d+)+[-\w]*|"
    r"\d{2}\.\d+\.\d+\.\d+-Y\d{2}"
    r")$",
    re.I,
)

_NON_SMT_TEXT_RE = re.compile(
    r"(?:"
    r"\bassembly\b|\bpackaging\b|through[\s-]?hole|\btht\b|\bdip\b|"
    r"press[\s-]?fit|wire[\s-]?harness|warning\s+label|battery\s+warning|"
    r"foam\s+pad|screen\s+pressing|english\s+manual|trading\s+manual|"
    r"\bwasher\b|\bscrew\b|standoff|heat[\s-]?sink\s+paste|"
    r"wave\s+solder|insertion|pcbdip|label\s+un\d|newtrading"
    r")",
    re.I,
)

_SMT_MOUNT_RE = re.compile(r"\b(?:SMD|SMT)\b", re.I)
_NON_SMT_MOUNT_RE = re.compile(
    r"\b(?:DIP|THT|THRU|THROUGH|INSERT|WAVE|HAND|PRESS|ASSY)\b",
    re.I,
)

_COMPONENT_HINT_RE = re.compile(
    r"\b(?:RES|CAP|OHM|UF|PF|NH|UH|SMD|SMT|BGA|QFN|MOSFET|DIODE|LED|CONN|"
    r"CRYSTAL|LEAD|IC|LDO|REG|USB|HDMI|DRAM|FLASH|INDUCTOR|BEAD)\b",
    re.I,
)


def is_procurement_or_internal_code(s: str) -> bool:
    """Foxconn-style part numbers, E.R.T.* codes, dotted procurement IDs."""
    t = _normalize_original(s)
    if not t or " " in t:
        return False
    return bool(_PROCUREMENT_CODE_RE.fullmatch(t))


def is_non_smt_bom_text(s: str) -> bool:
    """PCB/DIP/assembly/packaging lines — not SMT component descriptions."""
    t = _normalize_original(s)
    if not t:
        return False
    return bool(_NON_SMT_TEXT_RE.search(t))


def is_vendor_only_label(s: str) -> bool:
    """Manufacturer name only (no electrical spec)."""
    t = _normalize_original(s)
    if not t or len(t) > 48:
        return False
    if _COMPONENT_HINT_RE.search(t) or is_procurement_or_internal_code(t):
        return False
    if re.search(r"\d", t):
        return False
    if re.fullmatch(r"[\u4e00-\u9fff()（）A-Za-z.\s&-]+", t):
        return True
    return False


def should_harvest_original(s: str, *, source_file: str = "") -> bool:
    """Keep SMT-relevant component text; drop refdes, codes, assembly junk."""
    t = _normalize_original(s)
    if len(t) < 4 or t.lower() == "nan":
        return False
    if is_reference_designator_text(t):
        return False
    if is_procurement_or_internal_code(t):
        return False
    if is_vendor_only_label(t):
        return False
    if is_non_smt_bom_text(t):
        return False
    return True


def is_reference_designator_text(s: str) -> bool:
    """True if the whole field is refdes token(s), not a component description."""
    t = _normalize_original(s)
    if not t:
        return False
    if "," in t:
        parts = [p.strip() for p in t.split(",") if p.strip()]
        return bool(parts) and all(_single_reference_designator_token(p) for p in parts)
    return _single_reference_designator_token(t)


def _tabular_column_excluded(cn: str) -> bool:
    return any(h in cn for h in _TABULAR_EXCLUDE_COL_HINTS)


def _tabular_column_included(cn: str) -> bool:
    if _tabular_column_excluded(cn):
        return False
    if any(h in cn for h in _TABULAR_INCLUDE_COL_HINTS):
        return True
    return False


def _tabular_comment_columns(df: pd.DataFrame) -> list[object]:
    """Columns likely holding BOM comment / value text (incl. common CN headers)."""
    found: list[object] = []
    for c in df.columns:
        cn = _excel_cell_str(c).lower()
        if not cn or cn.startswith("unnamed"):
            continue
        if _tabular_column_included(cn):
            found.append(c)
    if found:
        return found
    best = ""
    best_c: object | None = None
    for c in df.columns:
        ser = df[c].head(30)
        sample = " ".join(_excel_cell_str(x) for x in ser.tolist())
        if len(sample) > len(best):
            best = sample
            best_c = c
    return [best_c] if best_c is not None else []


def _iter_tabular_frames(path: Path) -> Iterator[pd.DataFrame]:
    suf = path.suffix.lower()
    if suf in (".xlsx", ".xls"):
        engine = "openpyxl" if suf == ".xlsx" else "xlrd"
        xl = pd.ExcelFile(path, engine=engine)
        for sheet in xl.sheet_names:
            for header in (0, 1):
                df = pd.read_excel(path, sheet_name=sheet, header=header, engine=engine)
                if _tabular_comment_columns(df):
                    yield df
                    break
        return
    if suf == ".csv":
        yield pd.read_csv(path)


def _tabular_mount_column(df: pd.DataFrame) -> object | None:
    for c in df.columns:
        cn = _excel_cell_str(c).lower()
        if cn in ("methods", "method", "mount", "mounting", "process") or "贴装" in cn:
            return c
    return None


def _row_mounting_is_smt(method_val: object) -> bool | None:
    m = _excel_cell_str(method_val).upper()
    if not m:
        return None
    if _NON_SMT_MOUNT_RE.search(m):
        return False
    if _SMT_MOUNT_RE.search(m):
        return True
    return False


def _skip_harvest_source_file(rel: str) -> bool:
    low = rel.casefold()
    if "assembly" in low and "packaging" in low:
        return True
    if "packaging bom" in low:
        return True
    return False


def _yield_tabular_originals(df: pd.DataFrame, rel: str) -> Iterator[dict[str, str]]:
    target_cols = _tabular_comment_columns(df)
    if not target_cols:
        return
    mount_col = _tabular_mount_column(df)
    for _, row in df.iterrows():
        if mount_col is not None:
            smt = _row_mounting_is_smt(row[mount_col])
            if smt is False:
                continue
        for col in target_cols:
            v = _normalize_original(_excel_cell_str(row[col]))
            if not should_harvest_original(v, source_file=rel):
                continue
            yield {
                "source_file": rel,
                "source_kind": "tabular",
                "original": v,
            }


def harvest_from_tabular(path: Path, rel: str) -> Iterator[dict[str, str]]:
    suf = path.suffix.lower()
    if suf not in (".xlsx", ".xls", ".csv"):
        return
    seen: set[str] = set()
    for df in _iter_tabular_frames(path):
        for rec in _yield_tabular_originals(df, rel):
            key = rec["original"].casefold()
            if key in seen:
                continue
            seen.add(key)
            yield rec


def _curated_header_row(cells: tuple[object, ...]) -> bool:
    labels = {_excel_cell_str(c).lower() for c in cells[:3] if _excel_cell_str(c)}
    if not labels:
        return False
    header_words = {
        "original",
        "description",
        "comment",
        "comment1",
        "comment2",
        "value",
        "component",
        "mpn",
        "part",
        "vendor",
    }
    return labels.issubset(header_words) or (
        len(labels) == 1 and next(iter(labels)) in header_words
    )


def _curated_original_from_row(
    row: tuple[object, ...],
    *,
    join_mode: bool,
    join_columns: int,
    join_separator: str,
    col_idx: int,
) -> str:
    cells = list(row) if row else []
    if join_mode:
        parts = cells[: max(1, join_columns)]
        merged = merge_clean_comment_cell_parts(parts, join_separator)
        return _normalize_original(merged)
    if col_idx >= len(cells):
        return ""
    return _normalize_original(_excel_cell_str(cells[col_idx]))


def harvest_curated_xlsx(
    path: Path,
    *,
    rel: str | None = None,
    filter_junk: bool = False,
    join_mode: bool = True,
    join_columns: int = 3,
    join_separator: str = DEFAULT_DOUBLE_COMMENT_JOIN,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """
    Load operator-curated SMT strings (e.g. ``user_temp/component_test.xlsx``).

    **join_mode** (default): merge the first ``join_columns`` cells per row with
    ``join_separator`` (same helper as Clean BOM «Double Comment import»).

    Single-column mode: first column only (or a column named ``original`` / ``description``).
    """
    path = path.resolve()
    rel_s = rel or path.relative_to(_BOOMER_ROOT).as_posix()
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError("openpyxl required for curated xlsx import") from exc

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()
    stats = {"raw_rows": 0, "empty_skipped": 0, "junk_skipped": 0, "duplicate_skipped": 0}

    if not all_rows:
        return [], stats

    col_idx = 0
    data_rows = all_rows
    if not join_mode:
        headers = [_excel_cell_str(c).lower() for c in all_rows[0]]
        if any(h in ("original", "description", "comment", "value", "component") for h in headers):
            for i, h in enumerate(headers):
                if h in ("original", "description", "comment", "value", "component"):
                    col_idx = i
                    break
            data_rows = all_rows[1:]
    elif _curated_header_row(all_rows[0]):
        data_rows = all_rows[1:]

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for row in data_rows:
        if not row:
            continue
        stats["raw_rows"] += 1
        v = _curated_original_from_row(
            row,
            join_mode=join_mode,
            join_columns=join_columns,
            join_separator=join_separator,
            col_idx=col_idx,
        )
        if len(v) < 2 or v.lower() == "nan":
            stats["empty_skipped"] += 1
            continue
        if filter_junk and not should_harvest_original(v, source_file=rel_s):
            stats["junk_skipped"] += 1
            continue
        key = v.casefold()
        if key in seen:
            stats["duplicate_skipped"] += 1
            continue
        seen.add(key)
        out.append(
            {
                "source_file": rel_s,
                "source_kind": "curated",
                "original": v,
            }
        )
    for rec in out:
        rec["id"] = _stable_id(rec["original"], rec["source_file"])
    stats["unique"] = len(out)
    stats["join_mode"] = int(join_mode)
    return out, stats


def bootstrap_golden_from_draft(draft_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Build golden editor rows: auto-filled expected_*; ok if clean_one already matches."""
    out: list[dict[str, str]] = []
    for row in draft_rows:
        out.append(
            {
                "id": row["id"],
                "source_file": row["source_file"],
                "source_kind": row["source_kind"],
                "original": row["original"],
                "cleaned_auto": row.get("cleaned_auto", ""),
                "type_auto": row.get("type_auto", ""),
                "source_auto": row.get("source_auto", ""),
                "alert_auto": row.get("alert_auto", ""),
                "expected_cleaned": row.get("cleaned_auto", ""),
                "expected_type": row.get("type_auto", ""),
                "expected_source": row.get("source_auto", ""),
                "status": "wip",
                "notes": "curated import — проверить expected_*",
            }
        )
    return out


def harvest_from_line_txt(path: Path, rel: str) -> Iterator[dict[str, str]]:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        v = _normalize_original(line)
        if len(v) > 500:
            continue
        if re.fullmatch(r"[\d.\s]+", v):
            continue
        if not should_harvest_original(v, source_file=rel):
            continue
        yield {
            "source_file": rel,
            "source_kind": "line_txt",
            "original": v,
        }


def sample_records_stratified_by_file(
    records: list[dict[str, str]],
    *,
    limit: int,
    seed: int = 0,
    min_per_file: int = 1,
    max_per_file: int | None = None,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """
  Pick up to ``limit`` rows with fair representation per ``source_file``.

  1. Take up to ``min_per_file`` from each file (shuffled within file).
  2. Round-robin across files until ``limit`` or no file can contribute.
  3. Never exceed ``max_per_file`` per file (default: ceil(limit / n_files)).
    """
    by_file: dict[str, list[dict[str, str]]] = {}
    for r in records:
        by_file.setdefault(r["source_file"], []).append(r)
    files = sorted(by_file.keys())
    if not files:
        return [], {}
    rng = random.Random(seed)
    for f in files:
        rng.shuffle(by_file[f])
    cap = max_per_file
    if cap is None:
        cap = max(min_per_file, (limit + len(files) - 1) // len(files))
    counts: dict[str, int] = {f: 0 for f in files}
    picked: list[dict[str, str]] = []

    for f in files:
        while counts[f] < min_per_file and by_file[f] and len(picked) < limit:
            picked.append(by_file[f].pop(0))
            counts[f] += 1

    fi = 0
    while len(picked) < limit:
        progressed = False
        for _ in range(len(files)):
            f = files[fi % len(files)]
            fi += 1
            if not by_file[f] or counts[f] >= cap:
                continue
            picked.append(by_file[f].pop(0))
            counts[f] += 1
            progressed = True
            if len(picked) >= limit:
                break
        if not progressed:
            break
    return picked[:limit], counts


def harvest_directory(
    root: Path,
    *,
    limit: int = 500,
    seed: int = 0,
    min_per_file: int = 1,
    max_per_file: int | None = None,
) -> list[dict[str, str]]:
    root = root.resolve()
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(rec: dict[str, str]) -> None:
        orig = rec["original"]
        key = orig.casefold()
        if key in seen:
            return
        seen.add(key)
        rec["id"] = _stable_id(orig, rec["source_file"])
        records.append(rec)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(_BOOMER_ROOT).as_posix()
        if _skip_harvest_source_file(rel):
            continue
        suf = path.suffix.lower()
        try:
            if suf in (".htm", ".html"):
                for r in harvest_from_allegro_html(path, rel):
                    if should_harvest_original(r["original"], source_file=rel):
                        add(r)
            elif "cmp" in path.name.lower() or (
                suf == ".txt" and "device type" in path.read_text(encoding="utf-8", errors="ignore")[:8000].lower()
            ):
                for r in harvest_from_cmp_report(path, rel):
                    if should_harvest_original(r["original"], source_file=rel):
                        add(r)
            elif suf in (".xlsx", ".xls", ".csv"):
                for r in harvest_from_tabular(path, rel):
                    add(r)
            elif suf in (".txt", ".tab"):
                for r in harvest_from_line_txt(path, rel):
                    add(r)
        except Exception:
            continue

    n_files = len({r["source_file"] for r in records})
    eff_min = min_per_file
    if eff_min <= 0:
        eff_min = max(1, limit // max(n_files, 1))
    picked, _counts = sample_records_stratified_by_file(
        records,
        limit=limit,
        seed=seed,
        min_per_file=eff_min,
        max_per_file=max_per_file,
    )
    return picked


def harvest_directory_stats(rows: list[dict[str, str]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get("source_file", ""))
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda x: (-x[1], x[0])))


def write_manifest(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_manifest(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_corpus_profile(path: Path | None = None) -> CleanConfig:
    p = path or DEFAULT_PROFILE
    data = json.loads(p.read_text(encoding="utf-8"))
    snap_name = data.pop("hanwha_partnames_snapshot", None)
    partnames = None
    if data.get("use_hanwha_mdb") and snap_name:
        snap_path = p.parent / str(snap_name)
        if snap_path.is_file():
            partnames = load_partnames_snapshot(snap_path)
    tpl_keys = ("resistor_template", "cap_template", "inductor_template")
    for k in tpl_keys:
        if k in data and isinstance(data[k], list):
            data[k] = tuple(data[k])
    pipe = data.get("clean_pipeline_order")
    if isinstance(pipe, list):
        data["clean_pipeline_order"] = tuple(pipe)
    dis = data.get("clean_pipeline_disabled")
    if isinstance(dis, list):
        data["clean_pipeline_disabled"] = tuple(dis)
    cfg = CleanConfig(**data, hanwha_partnames=partnames)
    return default_clean_config(cfg)


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    return _dataframe_to_row_dicts(df)


def write_tsv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _rows_to_dataframe(rows, columns)
    df.to_csv(path, sep="\t", index=False, encoding="utf-8")


def _dataframe_to_row_dicts(df: pd.DataFrame) -> list[dict[str, str]]:
    df = df.fillna("")
    return [{str(k): str(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _rows_to_dataframe(rows: list[dict[str, str]], columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns]


def read_corpus_table(path: Path) -> list[dict[str, str]]:
    """Load golden/draft from ``.xlsx`` or legacy ``.tsv``."""
    if not path.is_file():
        return []
    suf = path.suffix.lower()
    if suf in (".xlsx", ".xls"):
        engine = "openpyxl" if suf == ".xlsx" else "xlrd"
        df = pd.read_excel(path, dtype=str, engine=engine)
        return _dataframe_to_row_dicts(df)
    return read_tsv(path)


def write_corpus_table(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = _rows_to_dataframe(rows, columns)
    suf = path.suffix.lower()
    if suf in (".xlsx", ".xls"):
        try:
            df.to_excel(path, index=False, engine="openpyxl")
            return
        except PermissionError:
            tsv_path = path.with_suffix(".tsv")
            df.to_csv(tsv_path, sep="\t", index=False, encoding="utf-8")
            print(
                f"Warning: could not write {path} (file locked/open). "
                f"Wrote to {tsv_path} instead.",
                file=sys.stderr,
            )
            return
    df.to_csv(path, sep="\t", index=False, encoding="utf-8")


def resolve_golden_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    if DEFAULT_GOLDEN.is_file():
        return DEFAULT_GOLDEN
    legacy = FIXTURES_DIR / "golden.tsv"
    if legacy.is_file():
        return legacy
    return DEFAULT_GOLDEN


def run_clean_row(original: str, cfg: CleanConfig) -> tuple[str, str, str]:
    cleaned, typ, _pc, src = clean_one(original, cfg)
    return cleaned, typ, src


def build_draft(manifest: list[dict[str, str]], cfg: CleanConfig) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for r in manifest:
        cleaned, typ, src = run_clean_row(r["original"], cfg)
        alert = analyze_token_alert(cleaned, typ).as_text()
        out.append(
            {
                "id": r["id"],
                "source_file": r["source_file"],
                "source_kind": r["source_kind"],
                "original": r["original"],
                "cleaned_auto": cleaned,
                "type_auto": typ,
                "source_auto": src,
                "alert_auto": alert,
                "expected_cleaned": "",
                "expected_type": "",
                "expected_source": "",
                "status": "wip",
                "notes": "",
            }
        )
    return out


@dataclass(frozen=True)
class CorpusFailure:
    id: str
    source_file: str
    source_kind: str
    original: str
    field: str
    got: str
    want: str
    notes: str


def validate_golden(
    golden_rows: list[dict[str, str]],
    cfg: CleanConfig,
    *,
    id_prefix: str = "",
    max_rows: int | None = None,
) -> list[CorpusFailure]:
    failures: list[CorpusFailure] = []
    n = 0
    for row in golden_rows:
        status = str(row.get("status", "")).strip().lower()
        if status not in ("ok", ""):
            continue
        rid = str(row.get("id", ""))
        if id_prefix and not rid.startswith(id_prefix):
            continue
        orig = str(row.get("original", ""))
        cleaned, typ, src = run_clean_row(orig, cfg)
        n += 1
        if max_rows is not None and n > max_rows:
            break
        exp_c = str(row.get("expected_cleaned", "")).strip()
        exp_t = str(row.get("expected_type", "")).strip()
        exp_s = str(row.get("expected_source", "")).strip()
        notes = str(row.get("notes", ""))
        if cleaned != exp_c:
            failures.append(
                CorpusFailure(
                    rid,
                    row.get("source_file", ""),
                    row.get("source_kind", ""),
                    orig,
                    "cleaned",
                    cleaned,
                    exp_c,
                    notes,
                )
            )
        if typ != exp_t:
            failures.append(
                CorpusFailure(
                    rid,
                    row.get("source_file", ""),
                    row.get("source_kind", ""),
                    orig,
                    "type",
                    typ,
                    exp_t,
                    notes,
                )
            )
        if src != exp_s:
            failures.append(
                CorpusFailure(
                    rid,
                    row.get("source_file", ""),
                    row.get("source_kind", ""),
                    orig,
                    "source",
                    src,
                    exp_s,
                    notes,
                )
            )
    return failures


def format_failure_report(
    failures: list[CorpusFailure],
    *,
    total_ok_rows: int,
) -> str:
    if not failures:
        return f"clean_corpus: all {total_ok_rows} row(s) match golden.\n"
    by_id: dict[str, list[CorpusFailure]] = {}
    for f in failures:
        by_id.setdefault(f.id, []).append(f)
    lines = [
        f"=== clean_corpus FAIL ({len(by_id)} row(s), {len(failures)} field mismatch(es)) ===",
        "",
    ]
    for i, (rid, flist) in enumerate(sorted(by_id.items()), 1):
        f0 = flist[0]
        lines.append(f"--- [{i}/{len(by_id)}] id: {rid} ---")
        lines.append(f"source: {f0.source_file} ({f0.source_kind})")
        lines.append("original:")
        for part in _wrap_text(f0.original, 100):
            lines.append(f"  {part}")
        for f in flist:
            if f.field == "cleaned":
                lines.append("cleaned:")
                lines.append(f"  - got:  {f.got}")
                lines.append(f"  + want: {f.want}")
            else:
                lines.append(f"{f.field}: got={f.got!r} want={f.want!r}")
        if f0.notes.strip():
            lines.append(f"notes: {f0.notes}")
        lines.append("")
    counts: dict[str, int] = {}
    for f in failures:
        counts[f.field] = counts.get(f.field, 0) + 1
    lines.append("summary by field: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    lines.append("filter: pytest -k <id> or: python tools/clean_corpus.py report --id <prefix>")
    return "\n".join(lines) + "\n"


def _wrap_text(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]
    out: list[str] = []
    while text:
        out.append(text[:width])
        text = text[width:]
    return out
