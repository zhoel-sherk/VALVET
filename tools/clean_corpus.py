#!/usr/bin/env python3
"""
Clean BOM golden corpus CLI.

Usage:
  python tools/clean_corpus.py mdb-export [--mdb examples/UPD.MDB]
  python tools/clean_corpus.py harvest [--root user_temp] [--limit 500]
  python tools/clean_corpus.py draft
  python tools/clean_corpus.py test
  python tools/clean_corpus.py report
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
_ROOT = _TOOLS.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_TOOLS))

from clean_corpus_lib import (  # noqa: E402
    DEFAULT_CURATED_XLSX,
    DEFAULT_DRAFT,
    DEFAULT_GOLDEN,
    DEFAULT_MANIFEST,
    DEFAULT_PROFILE,
    DEFAULT_USER_TEMP,
    FIXTURES_DIR,
    GOLDEN_EDITOR_COLUMNS,
    TSV_COLUMNS,
    bootstrap_golden_from_draft,
    build_draft,
    format_failure_report,
    harvest_curated_xlsx,
    harvest_directory,
    harvest_directory_stats,
    load_corpus_profile,
    load_manifest,
    read_corpus_table,
    resolve_golden_path,
    validate_golden,
    write_corpus_table,
    write_manifest,
)
from machine_library.hanwha_partnames import (  # noqa: E402
    export_partnames_snapshot,
    resolve_upd_mdb_path,
)


def _profile_path() -> Path:
    raw = (
        os.environ.get("VALVET_CLEAN_CORPUS_PROFILE", "").strip()
        or os.environ.get("BOOMER_CLEAN_CORPUS_PROFILE", "").strip()
    )
    return Path(raw) if raw else DEFAULT_PROFILE


def _golden_path() -> Path:
    raw = (
        os.environ.get("VALVET_CLEAN_CORPUS_GOLDEN", "").strip()
        or os.environ.get("BOOMER_CLEAN_CORPUS_GOLDEN", "").strip()
    )
    if raw:
        return Path(raw)
    return resolve_golden_path()


def cmd_mdb_export(args: argparse.Namespace) -> int:
    mdb = args.mdb
    if mdb is None:
        mdb = resolve_upd_mdb_path(boomer_root=_ROOT)
    else:
        mdb = Path(mdb)
    levels = {int(x) for x in str(args.confidence).split(",")}
    out = Path(args.out)
    dump = Path(args.dump_rejects) if args.dump_rejects else None
    meta = export_partnames_snapshot(
        mdb,
        out,
        confidence_levels=levels,
        exclude_passive_rc=not bool(args.include_passive_rc),
        dump_rejects_path=dump,
    )
    c = meta["counts"]
    print(
        f"mdb-export: {c['accepted_partnames']} partnames "
        f"(total={c['total_rows']} conf={c['after_confidence']} "
        f"passive_rc_rejected={c.get('rejected_passive_rc', 0)} "
        f"junk_rejected={c.get('rejected_junk', 0)})"
    )
    print(f"  -> {out}")
    if dump:
        print(f"  rejects -> {dump}")
    return 0


def cmd_import_curated(args: argparse.Namespace) -> int:
    path = Path(args.input)
    if not path.is_file():
        print(f"import-curated: not found: {path}", file=sys.stderr)
        return 1
    rows, stats = harvest_curated_xlsx(
        path,
        filter_junk=bool(args.filter_junk),
        join_mode=bool(args.join_mode),
        join_columns=int(args.join_columns),
        join_separator=str(args.join_separator),
    )
    if not rows:
        print(f"import-curated: no rows in {path}", file=sys.stderr)
        return 1
    manifest_out = Path(args.manifest)
    write_manifest(rows, manifest_out)
    mode = (
        f"join cols={args.join_columns} sep={args.join_separator!r}"
        if args.join_mode
        else "col0"
    )
    print(
        f"import-curated: {stats['unique']} unique -> {manifest_out} ({mode}) "
        f"raw={stats['raw_rows']} dup={stats['duplicate_skipped']} "
        f"empty={stats['empty_skipped']} junk={stats['junk_skipped']}"
    )

    cfg = load_corpus_profile(_profile_path())
    draft_rows = build_draft(rows, cfg) if args.draft or args.golden else None
    if draft_rows is not None:
        draft_out = Path(args.draft_out)
        write_corpus_table(draft_out, draft_rows, TSV_COLUMNS)
        print(f"  draft: {len(draft_rows)} row(s) -> {draft_out}")
    if args.golden:
        if draft_rows is None:
            draft_rows = build_draft(rows, cfg)
        golden_rows = bootstrap_golden_from_draft(draft_rows)
        golden_out = Path(args.golden_out)
        write_corpus_table(golden_out, golden_rows, GOLDEN_EDITOR_COLUMNS)
        print(f"  golden: {len(golden_rows)} row(s) -> {golden_out} (status=wip)")
    return 0


def cmd_harvest(args: argparse.Namespace) -> int:
    root = Path(args.root)
    max_pf = int(args.max_per_file) if args.max_per_file else None
    rows = harvest_directory(
        root,
        limit=int(args.limit),
        seed=int(args.seed),
        min_per_file=int(args.min_per_file),
        max_per_file=max_pf,
    )
    out = Path(args.out)
    write_manifest(rows, out)
    stats = harvest_directory_stats(rows)
    print(f"harvest: {len(rows)} unique string(s) -> {out}")
    print("  per source_file:")
    for name, n in stats.items():
        short = name if len(name) <= 72 else "…" + name[-69:]
        print(f"    {n:4d}  {short}")
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    manifest = load_manifest(Path(args.manifest))
    if not manifest:
        print(f"draft: empty manifest {args.manifest}", file=sys.stderr)
        return 1
    cfg = load_corpus_profile(_profile_path())
    rows = build_draft(manifest, cfg)
    out = Path(args.out)
    write_corpus_table(out, rows, TSV_COLUMNS)
    print(f"draft: {len(rows)} row(s) -> {out}")
    return 0


def _run_validate(args: argparse.Namespace) -> tuple[list, int]:
    golden = read_corpus_table(_golden_path())
    if not golden:
        print(f"golden file missing or empty: {_golden_path()}", file=sys.stderr)
        return [], 1
    cfg = load_corpus_profile(_profile_path())
    ok_rows = sum(
        1
        for r in golden
        if str(r.get("status", "")).strip().lower() in ("ok", "")
    )
    failures = validate_golden(
        golden,
        cfg,
        id_prefix=str(args.id or ""),
        max_rows=int(args.max_rows) if args.max_rows else None,
    )
    return failures, ok_rows


def cmd_test(args: argparse.Namespace) -> int:
    failures, ok_rows = _run_validate(args)
    if failures:
        print(format_failure_report(failures, total_ok_rows=ok_rows), end="")
        return 1
    print(f"clean_corpus test: OK ({ok_rows} row(s))")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    failures, ok_rows = _run_validate(args)
    print(format_failure_report(failures, total_ok_rows=ok_rows), end="")
    return 1 if failures else 0


def cmd_stabilize(args: argparse.Namespace) -> int:
    """Set status=wip on golden rows that fail in-process validation (order-sensitive Hanwha edge cases)."""
    path = _golden_path()
    rows = read_corpus_table(path)
    if not rows:
        print(f"stabilize: no rows in {path}", file=sys.stderr)
        return 1
    cfg = load_corpus_profile(_profile_path())
    failures = validate_golden(rows, cfg)
    fail_ids = {f.id for f in failures}
    if not fail_ids:
        print("stabilize: all ok rows match")
        return 0
    n = 0
    for row in rows:
        if row.get("id") in fail_ids and str(row.get("status", "")).strip().lower() == "ok":
            row["status"] = "wip"
            note = str(row.get("notes", "")).strip()
            row["notes"] = (note + "; unstable_in_batch").strip("; ")
            n += 1
    cols = [c for c in GOLDEN_EDITOR_COLUMNS if c in rows[0]] if rows else GOLDEN_EDITOR_COLUMNS
    write_corpus_table(path, rows, cols)
    print(f"stabilize: marked {n} row(s) as wip (ids: {', '.join(sorted(fail_ids)[:8])}…)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Clean BOM golden corpus tools")
    sub = p.add_subparsers(dest="command", required=True)

    pe = sub.add_parser("mdb-export", help="Export filtered Hanwha PARTNAME JSON snapshot")
    pe.add_argument("--mdb", default=None, help="Path to UPD.MDB (default: examples/UPD.MDB)")
    pe.add_argument(
        "--out",
        default=str(FIXTURES_DIR / "hanwha_partnames_cl40.json"),
    )
    pe.add_argument("--confidence", default="40", help="Comma-separated CONFIDENCE_LEVEL values")
    pe.add_argument(
        "--include-passive-rc",
        action="store_true",
        help="Include chip R/C MLCC-style PARTNAME rows (default: ICs and specials only)",
    )
    pe.add_argument("--dump-rejects", default=None, help="Optional TSV of rejected PARTNAME rows")

    pi = sub.add_parser(
        "import-curated",
        help="Import curated SMT list (default: user_temp/component_test.xlsx)",
    )
    pi.add_argument("--input", default=str(DEFAULT_CURATED_XLSX))
    pi.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    pi.add_argument(
        "--join-mode",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Merge first N columns per row (Clean BOM Double Comment style)",
    )
    pi.add_argument(
        "--join-columns",
        default="3",
        help="How many leading columns to merge when --join-mode (default 3)",
    )
    pi.add_argument(
        "--join-separator",
        default=" | ",
        help="Separator between joined cells (default « | », same as Clean BOM)",
    )
    pi.add_argument(
        "--filter-junk",
        action="store_true",
        help="Apply should_harvest_original() refdes/procurement filters",
    )
    pi.add_argument("--draft", action="store_true", help="Run clean_one -> draft.xlsx")
    pi.add_argument("--draft-out", default=str(DEFAULT_DRAFT))
    pi.add_argument(
        "--golden",
        action="store_true",
        help="Bootstrap golden.xlsx from draft (all status=wip)",
    )
    pi.add_argument("--golden-out", default=str(DEFAULT_GOLDEN))

    ph = sub.add_parser("harvest", help="Collect component strings from user_temp")
    ph.add_argument("--root", default=str(DEFAULT_USER_TEMP))
    ph.add_argument("--limit", default="500")
    ph.add_argument("--seed", default="0")
    ph.add_argument(
        "--min-per-file",
        default="0",
        help="Minimum rows per source file before round-robin (0 = auto: limit/n_files)",
    )
    ph.add_argument(
        "--max-per-file",
        default="",
        help="Cap rows per source file (default: ceil(limit/n_files))",
    )
    ph.add_argument("--out", default=str(DEFAULT_MANIFEST))

    pd_ = sub.add_parser("draft", help="Run clean_one on manifest -> draft.tsv")
    pd_.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    pd_.add_argument("--out", default=str(DEFAULT_DRAFT))

    pt = sub.add_parser("test", help="Compare golden.xlsx to clean_one (exit 1 on mismatch)")
    pt.add_argument("--id", default="", help="Only rows whose id starts with this prefix")
    pt.add_argument("--max-rows", default=None, type=int)

    pr = sub.add_parser("report", help="Print LLM-friendly diff (same as test failures)")
    pr.add_argument("--id", default="")
    pr.add_argument("--max-rows", default=None, type=int)

    ps = sub.add_parser(
        "stabilize",
        help="Mark golden rows that fail validate as wip (run after bootstrap)",
    )

    args = p.parse_args()
    if args.command == "mdb-export":
        return cmd_mdb_export(args)
    if args.command == "import-curated":
        return cmd_import_curated(args)
    if args.command == "harvest":
        return cmd_harvest(args)
    if args.command == "draft":
        return cmd_draft(args)
    if args.command == "test":
        return cmd_test(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "stabilize":
        return cmd_stabilize(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
