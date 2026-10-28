"""Dump a Hanwha T-OLP export folder (machines, feeder slots, warnings).

Reads ``.mfb`` (machine feeder base) first and falls back to ``.eoj`` + ``.PCB``.

Usage:
    python tools/tolp_probe.py C:\\PCB
    python tools/tolp_probe.py C:\\PCB --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from parsers.tolp_export import TolpExportError, load_tolp_export  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "folder", help="Folder with the .eoj and per-machine .PCB files"
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument(
        "--rear-first",
        action="store_true",
        help="Treat side byte 1 as Rear (when T-OLP numbers the rear base first)",
    )
    args = parser.parse_args(argv)

    try:
        export = load_tolp_export(args.folder, front_is_one=not args.rear_first)
    except TolpExportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "folder": str(export.folder),
                    "machines": export.machines,
                    "warnings": list(export.warnings),
                    "feeders": [
                        {
                            "machine": f.machine,
                            "model": f.model,
                            "side": f.side,
                            "slot": f.slot,
                            "part": f.part,
                        }
                        for f in export.feeders
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"Folder: {export.folder}")
    print(f"Source: {export.source.upper() or '?'}")
    print(f"Machines: {export.machines}")
    print(f"Feeders: {len(export.feeders)}")
    for warning in export.warnings:
        print(f"  warning: {warning}")
    print()
    current = None
    for feeder in export.feeders:
        if (feeder.machine, feeder.side) != current:
            current = (feeder.machine, feeder.side)
            model = f" · {feeder.model}" if feeder.model else ""
            print(f"[{feeder.machine}{model} · {feeder.side}]")
        print(f"  {feeder.slot:>3}  {feeder.part}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
