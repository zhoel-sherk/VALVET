# SPDX-License-Identifier: MIT
"""Minimal MIT KiCad ``.kicad_mod`` reader (pads + F.Fab lines)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from package_vspd.parse import parse_package
from pcb_preview.types import (
    BBoxMM,
    FootprintOutlineMM,
    PadRectMM,
    StrokeLineMM,
    union_bbox,
)


@dataclass(frozen=True)
class KicadModImport:
    name: str
    vspd_id: str
    outline: FootprintOutlineMM


def _tokenize(src: str) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
            continue
        if c in "()":
            out.append(c)
            i += 1
            continue
        if c == '"':
            i += 1
            buf: list[str] = []
            while i < n and src[i] != '"':
                if src[i] == "\\" and i + 1 < n:
                    buf.append(src[i + 1])
                    i += 2
                    continue
                buf.append(src[i])
                i += 1
            out.append("".join(buf))
            i += 1
            continue
        j = i
        while j < n and src[j] not in "()\" \t\r\n":
            j += 1
        out.append(src[i:j])
        i = j
    return out


def _parse_list(toks: list[str], i: int) -> tuple[object, int]:
    if i >= len(toks) or toks[i] != "(":
        raise ValueError("expected '('")
    i += 1
    items: list[object] = []
    while i < len(toks) and toks[i] != ")":
        if toks[i] == "(":
            node, i = _parse_list(toks, i)
            items.append(node)
        else:
            items.append(toks[i])
            i += 1
    if i >= len(toks):
        raise ValueError("unclosed s-expression")
    return items, i + 1


def _head(node: object) -> str:
    if isinstance(node, list) and node and isinstance(node[0], str):
        return node[0]
    return ""


def _find_named(root: list[object], name: str) -> list[list[object]]:
    found: list[list[object]] = []
    if _head(root) == name:
        found.append(root)

    def walk(n: object) -> None:
        if not isinstance(n, list):
            return
        if _head(n) == name:
            found.append(n)
        for ch in n[1:]:
            walk(ch)

    for ch in root[1:]:
        walk(ch)
    return found


def _floats(seq: list[object], start: int, count: int) -> list[float]:
    out: list[float] = []
    for k in range(count):
        out.append(float(seq[start + k]))
    return out


def _layer_is_fab(node: list[object]) -> bool:
    for ch in node:
        if isinstance(ch, list) and _head(ch) == "layer":
            ly = str(ch[1] if len(ch) > 1 else "")
            return ly in ("F.Fab", "Dwgs.User")
    return False


def parse_kicad_mod_text(src: str) -> KicadModImport:
    toks = _tokenize(src)
    i = 0
    while i < len(toks) and toks[i] != "(":
        i += 1
    tree, _ = _parse_list(toks, i)
    if not isinstance(tree, list):
        raise ValueError("not a kicad_mod tree")
    name = ""
    if _head(tree) in ("footprint", "module") and len(tree) > 1:
        name = str(tree[1])
    pads: list[PadRectMM] = []
    lines: list[StrokeLineMM] = []
    for pad in _find_named(tree, "pad"):
        at = next((x for x in pad if _head(x) == "at"), None)
        size = next((x for x in pad if _head(x) == "size"), None)
        if not isinstance(at, list) or not isinstance(size, list):
            continue
        try:
            cx, cy = _floats(at, 1, 2)
            rot = float(at[3]) if len(at) > 3 else 0.0
            w, h = _floats(size, 1, 2)
        except (ValueError, IndexError, TypeError):
            continue
        num = str(pad[1]) if len(pad) > 1 else ""
        pads.append(PadRectMM(cx, cy, w, h, rot, num))
    for fl in _find_named(tree, "fp_line"):
        if not _layer_is_fab(fl):
            continue
        st = next((x for x in fl if _head(x) == "start"), None)
        en = next((x for x in fl if _head(x) == "end"), None)
        if not isinstance(st, list) or not isinstance(en, list):
            continue
        try:
            x1, y1 = _floats(st, 1, 2)
            x2, y2 = _floats(en, 1, 2)
        except (ValueError, IndexError, TypeError):
            continue
        lines.append(StrokeLineMM(x1, y1, x2, y2, 0.1))
    boxes = []
    if pads:
        xs = [p.cx - p.width_mm / 2 for p in pads] + [
            p.cx + p.width_mm / 2 for p in pads
        ]
        ys = [p.cy - p.height_mm / 2 for p in pads] + [
            p.cy + p.height_mm / 2 for p in pads
        ]
        boxes.append(BBoxMM(min(xs), min(ys), max(xs), max(ys)))
    if lines:
        xs = [ln.x1 for ln in lines] + [ln.x2 for ln in lines]
        ys = [ln.y1 for ln in lines] + [ln.y2 for ln in lines]
        boxes.append(BBoxMM(min(xs), min(ys), max(xs), max(ys)))
    bbox = union_bbox(boxes) if boxes else BBoxMM(0.0, 0.0, 0.0, 0.0)
    outline = FootprintOutlineMM(
        lines=tuple(lines),
        pads=tuple(pads),
        bbox=bbox,
        source="kicad_mod",
    )
    hit = parse_package(name)
    return KicadModImport(name=name, vspd_id=hit.vspd_id, outline=outline)


def parse_kicad_mod_file(path: Path | str) -> KicadModImport:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    imp = parse_kicad_mod_text(text)
    if not imp.name:
        return KicadModImport(
            name=p.stem, vspd_id=parse_package(p.stem).vspd_id, outline=imp.outline
        )
    return imp
