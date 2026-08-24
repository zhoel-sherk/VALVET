#!/usr/bin/env python3
"""Download Inter UI TTFs into src/fonts/ (SIL OFL 1.1).

Run from the ``boomer`` repository root:

    source venv/bin/activate
    python tools/fetch_inter.py

Requires network access. Uses only the Python standard library.
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

# Pinned release (update tag when bumping fonts).
_ZIP_URL = "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"
_WANTED = (
    "extras/ttf/Inter-Regular.ttf",
    "extras/ttf/Inter-Bold.ttf",
    "extras/ttf/Inter-Italic.ttf",
    "extras/ttf/Inter-BoldItalic.ttf",
)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    dest_dir = root / "src" / "fonts"
    dest_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {_ZIP_URL!r} …", file=sys.stderr)
    req = urllib.request.Request(
        _ZIP_URL,
        headers={"User-Agent": "boomer-fetch-fonts/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        for arc in _WANTED:
            if arc not in names:
                print(f"Missing {arc!r} in ZIP; archive layout may have changed.", file=sys.stderr)
                return 1
            out = dest_dir / Path(arc).name
            out.write_bytes(zf.read(arc))
            print(f"Wrote {out.relative_to(root)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
