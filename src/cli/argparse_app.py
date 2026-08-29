"""stdlib argparse entry for ``python -m cli``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cli.hanwha import HanwhaMdbToolsError, format_part_det, format_tables
from cli.pipeline import (
    apply_map_json,
    clean_comments,
    export_merge,
    export_mmd,
    load_bom,
    load_pnp,
    merge_and_check,
    reload_tables,
    write_report_html,
)
from cli.session import (
    DEFAULT_SESSION_PATH,
    CliSession,
    load_session_file,
    save_session_file,
)
import logger


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cli",
        description="VALVET headless BOM/PnP tools (no Qt, no Step 3D / PCB Preview).",
    )
    p.add_argument(
        "--session",
        default=DEFAULT_SESSION_PATH,
        help=f"JSON session path (paths + mappings only). Default: {DEFAULT_SESSION_PATH}",
    )
    p.add_argument(
        "--debug",
        action="store_true",
        help="Enable logger.config (logs/ file + stderr). Also VALVET_DEBUG=1.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    lb = sub.add_parser("load-bom", help="Load a BOM file into the session")
    lb.add_argument("path")
    lb.add_argument(
        "--sep", default="auto", help="Delimiter: auto, comma, tab, spaces, …"
    )

    lp = sub.add_parser("load-pnp", help="Load a PnP file into the session")
    lp.add_argument("path")
    lp.add_argument("--sep", default="auto")

    mp = sub.add_parser("map", help="Set column role mappings")
    mp.add_argument(
        "--map-json", help="JSON file with {bom: {REF, Comment}, pnp: {REF, X, Y, …}}"
    )
    mp.add_argument("--bom-ref")
    mp.add_argument("--bom-comment")
    mp.add_argument("--pnp-ref")
    mp.add_argument("--pnp-comment")
    mp.add_argument("--pnp-x")
    mp.add_argument("--pnp-y")
    mp.add_argument("--pnp-rot")
    mp.add_argument("--pnp-layer")
    mp.add_argument("--pnp-footprint")
    mp.add_argument("--coord-mils", action="store_true", help="Treat PnP X/Y as mils")
    mp.add_argument(
        "--coord-mm", action="store_true", help="Treat PnP X/Y as millimetres"
    )

    cl = sub.add_parser("clean", help="Clean BOM Comment column")
    cl.add_argument(
        "--apply", action="store_true", help="Write cleaned values into the BOM frame"
    )
    cl.add_argument("--limit", type=int, default=20, help="Preview rows to print")

    mg = sub.add_parser("merge", help="Merge BOM + PnP and optionally export")
    mg.add_argument("--overlap", action="store_true")
    mg.add_argument("--out", help="Write merge table (.xlsx / .csv)")
    mg.add_argument("--coord-mils", action="store_true")
    mg.add_argument("--coord-mm", action="store_true")

    rp = sub.add_parser("report", help="Cross-check report (run merge first)")
    rp.add_argument("--html", help="Write HTML report")

    em = sub.add_parser("export-mmd", help="Export merge as Mercury .mmd")
    em.add_argument("out")
    em.add_argument("--layer", default="", help="Filter Layer column (e.g. TOP)")

    hw = sub.add_parser("hanwha", help="Read-only Hanwha .mdb (tables / PART_Det)")
    hw_sub = hw.add_subparsers(dest="hanwha_cmd", required=True)
    ht = hw_sub.add_parser("tables", help="List tables")
    ht.add_argument("path")
    hp = hw_sub.add_parser("parts", help="Print PART_Det PARTNAME rows")
    hp.add_argument("path")
    hp.add_argument("--limit", type=int, default=50)

    sub.add_parser("tui", help="Minimal Textual TUI (requires requirements-cli.txt)")
    return p


def _open_session(path: str) -> CliSession:
    session = load_session_file(path)
    if session.bom_path or session.pnp_path:
        try:
            reload_tables(session)
        except Exception as exc:
            logger.warning("Could not reload tables from %s: %s", path, exc)
    return session


def _apply_coord_flags(session: CliSession, args: argparse.Namespace) -> None:
    if getattr(args, "coord_mils", False):
        session.coord_unit_mm = False
    if getattr(args, "coord_mm", False):
        session.coord_unit_mm = True


def _print_df_head(df, *, rows: int = 8) -> None:
    print(df.head(rows).to_string(index=False))
    extra = len(df) - rows
    if extra > 0:
        print(f"… {extra} more row(s), {len(df.columns)} column(s)")


def _cmd_load_bom(session: CliSession, args: argparse.Namespace) -> int:
    load_bom(session, args.path, separator=args.sep)
    assert session.bom_df is not None
    print(f"BOM {args.path}: {len(session.bom_df)} row(s)")
    print("columns:", ", ".join(str(c) for c in session.bom_df.columns))
    _print_df_head(session.bom_df)
    return 0


def _cmd_load_pnp(session: CliSession, args: argparse.Namespace) -> int:
    load_pnp(session, args.path, separator=args.sep)
    assert session.pnp_df is not None
    print(f"PnP {args.path}: {len(session.pnp_df)} row(s)")
    print("columns:", ", ".join(str(c) for c in session.pnp_df.columns))
    _print_df_head(session.pnp_df)
    return 0


def _cmd_map(session: CliSession, args: argparse.Namespace) -> int:
    if args.map_json:
        raw = json.loads(Path(args.map_json).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            print("map-json must be an object", file=sys.stderr)
            return 1
        apply_map_json(session, raw)
    pairs = (
        ("REF", args.bom_ref, session.bom_mappings),
        ("Comment", args.bom_comment, session.bom_mappings),
        ("REF", args.pnp_ref, session.pnp_mappings),
        ("Comment", args.pnp_comment, session.pnp_mappings),
        ("X", args.pnp_x, session.pnp_mappings),
        ("Y", args.pnp_y, session.pnp_mappings),
        ("Rotation", args.pnp_rot, session.pnp_mappings),
        ("Layer", args.pnp_layer, session.pnp_mappings),
        ("Footprint", args.pnp_footprint, session.pnp_mappings),
    )
    for role, value, dest in pairs:
        if value:
            dest[role] = value
    _apply_coord_flags(session, args)
    print("bom_mappings:", json.dumps(session.bom_mappings, ensure_ascii=False))
    print("pnp_mappings:", json.dumps(session.pnp_mappings, ensure_ascii=False))
    print("coord_unit_mm:", session.coord_unit_mm)
    return 0


def _cmd_clean(session: CliSession, args: argparse.Namespace) -> int:
    if session.bom_df is None:
        print("load a BOM first (load-bom)", file=sys.stderr)
        return 1
    preview = clean_comments(session, apply=args.apply)
    n = max(0, args.limit)
    print(
        f"clean preview: {len(preview)} row(s)" + (" (applied)" if args.apply else "")
    )
    for row in preview[:n]:
        orig = row[1] if len(row) > 1 else ""
        cleaned = row[2] if len(row) > 2 else ""
        tag = row[3] if len(row) > 3 else ""
        print(f"{orig}\t→\t{cleaned}\t[{tag}]")
    if len(preview) > n:
        print(f"… {len(preview) - n} more")
    return 0


def _cmd_merge(session: CliSession, args: argparse.Namespace) -> int:
    if session.bom_df is None or session.pnp_df is None:
        print("load BOM and PnP first", file=sys.stderr)
        return 1
    _apply_coord_flags(session, args)
    merge_df, report_df = merge_and_check(session, overlap=args.overlap)
    print(f"merge: {len(merge_df)} row(s); cross-check: {len(report_df)} issue(s)")
    _print_df_head(merge_df)
    if args.out:
        export_merge(session, args.out)
        print(f"wrote {args.out}")
    return 0


def _cmd_report(session: CliSession, args: argparse.Namespace) -> int:
    if session.report_df is None:
        print("run merge first", file=sys.stderr)
        return 1
    if args.html:
        write_report_html(session, args.html)
        print(f"wrote {args.html}")
        return 0
    print(session.report_df.to_string(index=False))
    return 0


def _cmd_export_mmd(session: CliSession, args: argparse.Namespace) -> int:
    if session.merge_df is None:
        print("run merge first", file=sys.stderr)
        return 1
    export_mmd(session, args.out, layer=args.layer)
    print(f"wrote {args.out}")
    return 0


def _cmd_hanwha(args: argparse.Namespace) -> int:
    try:
        if args.hanwha_cmd == "tables":
            print(format_tables(args.path))
            return 0
        print(format_part_det(args.path, limit=args.limit))
        return 0
    except HanwhaMdbToolsError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _cmd_tui() -> int:
    try:
        from cli.tui_app import run_tui
    except ImportError:
        print(
            "Textual is not installed. pip install -r requirements-cli.txt",
            file=sys.stderr,
        )
        return 1
    return run_tui()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logger.configure_if_debug(argv_debug=args.debug)
    if args.cmd == "hanwha":
        return _cmd_hanwha(args)
    if args.cmd == "tui":
        return _cmd_tui()

    session = _open_session(args.session)
    handlers = {
        "load-bom": _cmd_load_bom,
        "load-pnp": _cmd_load_pnp,
        "map": _cmd_map,
        "clean": _cmd_clean,
        "merge": _cmd_merge,
        "report": _cmd_report,
        "export-mmd": _cmd_export_mmd,
    }
    try:
        code = handlers[args.cmd](session, args)
    except Exception as exc:
        logger.error("Command %s failed: %s", args.cmd, exc, exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    save_session_file(session, args.session)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
