"""Load datasheet/*.md sample tables and emit Clean/parse cases.

Run: python tools/gen_parser_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASHEET = ROOT / "datasheet"
OUT_JSON = ROOT / "tests" / "fixtures" / "parser_generated_samples.json"


def parse_md_tables(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_samples = False
    header: list[str] = []
    for line in text.splitlines():
        if line.strip().lower().startswith("## samples"):
            in_samples = True
            header = []
            continue
        if in_samples and line.startswith("## "):
            break
        if not in_samples or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= {"-", ":"}:
            continue
        if cells[0] == "mpn_or_bom":
            header = cells
            continue
        if not header:
            continue
        rec = {header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))}
        rows.append(rec)
    return rows


def load_all_samples() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for path in sorted(DATASHEET.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        for rec in parse_md_tables(path.read_text(encoding="utf-8")):
            rec["file"] = path.name
            out.append(rec)
    return out


def noise_variants(bom: str) -> list[str]:
    """Corpus-like noise around a regex BOM line (no extra MPN join)."""
    variants = [bom, bom.replace("+/-", "±"), f"{bom} "]
    if "SMD" not in bom.upper():
        variants.append(f"{bom} SMD")
    return list(dict.fromkeys(variants))


def main() -> None:
    samples = load_all_samples()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(samples, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(samples)} samples -> {OUT_JSON}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    main()
