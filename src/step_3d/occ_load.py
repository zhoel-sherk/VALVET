"""Qt-free STEP load + tessellation via optional pythonocc-core (XDE/XCAF)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Iterator

import logger

DEFAULT_LIN_DEFLECTION = 0.8
MIN_LIN_DEFLECTION = 0.05
MAX_LIN_DEFLECTION = 5.0
DEFAULT_COLOR = (0.72, 0.72, 0.72)

ProgressCb = Callable[[int, int, str], None]
StopCb = Callable[[], bool]


class StepLoadError(Exception):
    """STEP could not be read or tessellated."""


class StepLoadCancelled(Exception):
    """Caller requested stop during load."""


@dataclass
class TessellatedPart:
    """One assembly node; mesh may be empty for grouping-only labels."""

    id: str
    name: str
    parent_id: str | None
    vertices: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[tuple[int, int, int]] = field(default_factory=list)
    color: tuple[float, float, float] = DEFAULT_COLOR

    @property
    def has_mesh(self) -> bool:
        return bool(self.faces) and bool(self.vertices)


@dataclass
class StepLoadResult:
    parts: list[TessellatedPart]
    source_path: str
    cancelled: bool = False
    error: str | None = None


def _occt_bin_candidates() -> list[str]:
    paths: list[str] = []
    env = os.environ.get("VALVET_OCCT_BIN") or os.environ.get("OCCT_ESSENTIALS_ROOT")
    if env:
        paths.append(env)
        paths.append(os.path.join(env, "win64", "vc14", "bin"))
    casroot = os.environ.get("CASROOT")
    if casroot:
        paths.append(os.path.join(casroot, "win64", "vc14", "bin"))
        paths.append(os.path.join(casroot, "bin"))
    home = os.path.expanduser("~")
    paths.append(os.path.join(home, "occ-src", "occt-install", "win64", "vc14", "bin"))
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        ap = os.path.abspath(p)
        if ap not in seen and os.path.isdir(ap):
            seen.add(ap)
            out.append(ap)
    return out


def _ensure_occt_dlls() -> None:
    """Windows Python 3.8+ does not load OCCT DLLs from PATH for .pyd imports."""
    add = getattr(os, "add_dll_directory", None)
    if add is None:
        return
    for folder in _occt_bin_candidates():
        try:
            add(folder)
        except OSError:
            continue


def pythonocc_available() -> bool:
    _ensure_occt_dlls()
    try:
        from OCC.Core.STEPControl import STEPControl_Reader  # noqa: F401
    except ImportError:
        return False
    return True


def clamp_lin_deflection(value: object) -> float:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        v = DEFAULT_LIN_DEFLECTION
    if v != v:  # NaN
        v = DEFAULT_LIN_DEFLECTION
    return min(MAX_LIN_DEFLECTION, max(MIN_LIN_DEFLECTION, v))


def _raise_if_stopped(should_stop: StopCb | None) -> None:
    if should_stop is not None and should_stop():
        raise StepLoadCancelled()


def _rgb_from_quantity(color: object) -> tuple[float, float, float]:
    try:
        return (
            float(color.Red()),  # type: ignore[attr-defined]
            float(color.Green()),  # type: ignore[attr-defined]
            float(color.Blue()),  # type: ignore[attr-defined]
        )
    except Exception:
        return DEFAULT_COLOR


def _label_name(label: object) -> str:
    try:
        gn = getattr(label, "GetLabelName", None)
        if gn is not None:
            s = str(gn()).strip()
            if s and s.lower() not in ("unnamed", "none", ""):
                return s
    except Exception:
        pass
    try:
        from OCC.Core.TDataStd import TDataStd_Name

        attr = TDataStd_Name()
        if not label.FindAttribute(TDataStd_Name.GetID(), attr):
            return ""
        ext = attr.Get()
        for method in ("ToAscii", "ToExtString"):
            fn = getattr(ext, method, None)
            if fn is None:
                continue
            try:
                s = str(fn()).strip()
            except Exception:
                continue
            if s:
                return s
        s = str(ext).strip()
        if s and s not in ("None",):
            return s
    except Exception:
        return ""
    return ""


def _part_color(
    color_tool: object, label: object, shape: object
) -> tuple[float, float, float]:
    from OCC.Core.Quantity import Quantity_Color

    color = Quantity_Color()
    kinds: list[object] = [0, 1, 2]
    try:
        from OCC.Core.XCAFDoc import (
            XCAFDoc_ColorCurv,
            XCAFDoc_ColorGen,
            XCAFDoc_ColorSurf,
        )

        kinds = [XCAFDoc_ColorSurf, XCAFDoc_ColorGen, XCAFDoc_ColorCurv]
    except ImportError:
        pass
    gic = getattr(color_tool, "GetInstanceColor", None)
    if gic is not None and shape is not None:
        for kind in kinds:
            try:
                if gic(shape, kind, color):
                    return _rgb_from_quantity(color)
            except Exception:
                continue
    gc = getattr(color_tool, "GetColor", None)
    if gc is None:
        return DEFAULT_COLOR
    for kind in kinds:
        for target in (label, shape):
            if target is None:
                continue
            try:
                if gc(target, kind, color):
                    return _rgb_from_quantity(color)
            except Exception:
                continue
    for target in (shape, label):
        if target is None:
            continue
        try:
            if gc(target, color):
                return _rgb_from_quantity(color)
        except Exception:
            continue
    return DEFAULT_COLOR


def _iter_faces(shape: object) -> Iterator[object]:
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer

    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        yield exp.Current()
        exp.Next()


def _has_faces(shape: object) -> bool:
    for _ in _iter_faces(shape):
        return True
    return False


def tessellate_shape(
    shape: object, lin_deflection: float
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Face triangles only (skip draughting edges / wires)."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopAbs import TopAbs_REVERSED
    from OCC.Core.TopLoc import TopLoc_Location

    BRepMesh_IncrementalMesh(shape, float(lin_deflection), False, 0.5, True)
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    for face in _iter_faces(shape):
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(face, loc)
        if tri is None:
            continue
        try:
            n_tri = int(tri.NbTriangles())
            n_nodes = int(tri.NbNodes())
        except Exception:
            continue
        if n_tri < 1 or n_nodes < 3:
            continue
        base = len(vertices)
        identity = True
        try:
            identity = bool(loc.IsIdentity())
        except Exception:
            identity = True
        trsf = loc.Transformation()
        for i in range(1, n_nodes + 1):
            try:
                pnt = tri.Node(i)
            except Exception:
                try:
                    pnt = tri.Nodes().Value(i)
                except Exception:
                    continue
            if not identity:
                try:
                    pnt.Transform(trsf)
                except Exception:
                    pass
            vertices.append((float(pnt.X()), float(pnt.Y()), float(pnt.Z())))
        reversed_face = False
        try:
            reversed_face = face.Orientation() == TopAbs_REVERSED
        except Exception:
            reversed_face = False
        for i in range(1, n_tri + 1):
            t = tri.Triangle(i)
            n1, n2, n3 = t.Get()
            a, b, c = base + n1 - 1, base + n2 - 1, base + n3 - 1
            if reversed_face:
                faces.append((a, c, b))
            else:
                faces.append((a, b, c))
    return vertices, faces


def _new_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"p{counter[0]}"


def _compose_loc(parent_loc: object, extra: object) -> object:
    try:
        if extra is None:
            return parent_loc
        return parent_loc.Multiplied(extra)
    except Exception:
        return parent_loc


def _apply_loc(shape: object, loc: object) -> object:
    try:
        if loc is None or loc.IsIdentity():
            return shape
        moved = getattr(shape, "Moved", None)
        if moved is not None:
            return moved(loc)
        located = getattr(shape, "Located", None)
        if located is not None:
            return located(loc)
    except Exception:
        return shape
    return shape


def _walk_xde(
    shape_tool: object,
    color_tool: object,
    label: object,
    loc: object,
    parent_id: str | None,
    parts: list[TessellatedPart],
    counter: list[int],
    lin_deflection: float,
    should_stop: StopCb | None,
    progress: ProgressCb | None,
    totals: list[int],
    name_override: str | None = None,
) -> None:
    from OCC.Core.TDF import TDF_Label, TDF_LabelSequence
    from OCC.Core.TopLoc import TopLoc_Location

    _raise_if_stopped(should_stop)
    try:
        if shape_tool.IsReference(label):
            ref = TDF_Label()
            if shape_tool.GetReferredShape(label, ref):
                extra = None
                try:
                    extra = shape_tool.GetLocation(label)
                except Exception:
                    extra = None
                child_name = _label_name(label) or _label_name(ref) or None
                _walk_xde(
                    shape_tool,
                    color_tool,
                    ref,
                    _compose_loc(loc, extra),
                    parent_id,
                    parts,
                    counter,
                    lin_deflection,
                    should_stop,
                    progress,
                    totals,
                    name_override=child_name,
                )
                return
    except StepLoadCancelled:
        raise
    except Exception:
        pass

    name = name_override or _label_name(label) or "Unnamed"
    pid = _new_id(counter)
    is_asm = False
    try:
        is_asm = bool(shape_tool.IsAssembly(label))
    except Exception:
        is_asm = False

    if is_asm:
        parts.append(
            TessellatedPart(id=pid, name=name, parent_id=parent_id, color=DEFAULT_COLOR)
        )
        seq = TDF_LabelSequence()
        shape_tool.GetComponents(label, seq)
        n = int(seq.Length())
        for i in range(1, n + 1):
            _walk_xde(
                shape_tool,
                color_tool,
                seq.Value(i),
                loc,
                pid,
                parts,
                counter,
                lin_deflection,
                should_stop,
                progress,
                totals,
            )
        return

    if loc is None:
        loc = TopLoc_Location()
    shape = _apply_loc(shape_tool.GetShape(label), loc)
    color = _part_color(color_tool, label, shape)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    if shape is not None and _has_faces(shape):
        if progress:
            progress(totals[0], max(totals[1], totals[0] + 1), name)
        verts, faces = tessellate_shape(shape, lin_deflection)
        totals[0] += 1
    parts.append(
        TessellatedPart(
            id=pid,
            name=name,
            parent_id=parent_id,
            vertices=verts,
            faces=faces,
            color=color,
        )
    )


def _load_via_names_colors(
    path: str,
    lin_deflection: float,
    should_stop: StopCb | None,
    progress: ProgressCb | None,
) -> list[TessellatedPart]:
    from OCC.Extend.DataExchange import read_step_file_with_names_colors

    _raise_if_stopped(should_stop)
    if progress:
        progress(0, 1, "read")
    mapping = read_step_file_with_names_colors(path)
    if not mapping:
        raise StepLoadError("STEP names/colors map is empty")
    parts: list[TessellatedPart] = []
    n = len(mapping)
    i = 0
    for shape, info in mapping.items():
        _raise_if_stopped(should_stop)
        i += 1
        name = "Unnamed"
        color = DEFAULT_COLOR
        if isinstance(info, (list, tuple)) and len(info) >= 1:
            if info[0]:
                name = str(info[0])
            if len(info) >= 2 and info[1] is not None:
                color = _rgb_from_quantity(info[1])
        verts: list[tuple[float, float, float]] = []
        faces: list[tuple[int, int, int]] = []
        if shape is not None and _has_faces(shape):
            if progress:
                progress(i - 1, n, name)
            verts, faces = tessellate_shape(shape, lin_deflection)
        if not faces:
            continue
        parts.append(
            TessellatedPart(
                id=f"p{i}",
                name=name,
                parent_id=None,
                vertices=verts,
                faces=faces,
                color=color,
            )
        )
    if not parts:
        raise StepLoadError("No tessellated faces from names/colors map")
    return parts


def _load_via_xde(
    path: str,
    lin_deflection: float,
    should_stop: StopCb | None,
    progress: ProgressCb | None,
) -> list[TessellatedPart]:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
    from OCC.Core.TDF import TDF_LabelSequence
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFApp import XCAFApp_Application
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

    _raise_if_stopped(should_stop)
    if progress:
        progress(0, 1, "read")
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-XCAF")
    try:
        app.NewDocument("MDTV-XCAF", doc)
    except Exception:
        pass
    reader = STEPCAFControl_Reader()
    try:
        reader.SetColorMode(True)
        reader.SetNameMode(True)
        reader.SetLayerMode(True)
        reader.SetPropsMode(True)
    except Exception:
        pass
    status = reader.ReadFile(path)
    if int(status) != int(IFSelect_RetDone):
        raise StepLoadError(f"STEPCAF ReadFile failed (status={status})")
    _raise_if_stopped(should_stop)
    if not reader.Transfer(doc):
        raise StepLoadError("STEPCAF Transfer failed")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool(doc.Main())
    free = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free)
    n_free = int(free.Length())
    if n_free < 1:
        raise StepLoadError("STEPCAF: no free shapes")
    from OCC.Core.TopLoc import TopLoc_Location

    parts: list[TessellatedPart] = []
    counter = [0]
    totals = [0, n_free]
    identity = TopLoc_Location()
    for i in range(1, n_free + 1):
        _walk_xde(
            shape_tool,
            color_tool,
            free.Value(i),
            identity,
            None,
            parts,
            counter,
            lin_deflection,
            should_stop,
            progress,
            totals,
        )
    return parts


def _load_via_step_control(
    path: str,
    lin_deflection: float,
    should_stop: StopCb | None,
    progress: ProgressCb | None,
) -> list[TessellatedPart]:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader

    _raise_if_stopped(should_stop)
    if progress:
        progress(0, 1, "read")
    reader = STEPControl_Reader()
    status = reader.ReadFile(path)
    if int(status) != int(IFSelect_RetDone):
        raise StepLoadError(f"STEP ReadFile failed (status={status})")
    _raise_if_stopped(should_stop)
    reader.TransferRoots()
    shape = reader.OneShape()
    if shape is None or shape.IsNull():
        raise StepLoadError("STEP file has no shape")
    name = os.path.splitext(os.path.basename(path))[0] or "STEP"
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    if _has_faces(shape):
        if progress:
            progress(0, 1, name)
        verts, faces = tessellate_shape(shape, lin_deflection)
    if not faces:
        raise StepLoadError("No tessellated faces (wireframe-only or empty STEP)")
    return [
        TessellatedPart(
            id="p1",
            name=name,
            parent_id=None,
            vertices=verts,
            faces=faces,
            color=DEFAULT_COLOR,
        )
    ]


def load_step_file(
    path: str,
    *,
    lin_deflection: float | None = None,
    should_stop: StopCb | None = None,
    progress: ProgressCb | None = None,
) -> StepLoadResult:
    """
    Read ``path`` with pythonocc XDE when possible; fall back to a single compound.

    Qt-free. ``should_stop`` is checked between assembly nodes. On cancel, returns
    ``cancelled=True`` and no parts.
    """
    if not pythonocc_available():
        return StepLoadResult(
            parts=[],
            source_path=path,
            error="pythonocc-core is not installed",
        )
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        return StepLoadResult(
            parts=[],
            source_path=abs_path,
            error="file not found",
        )
    deflection = clamp_lin_deflection(
        DEFAULT_LIN_DEFLECTION if lin_deflection is None else lin_deflection
    )
    try:
        loader = "xde"
        try:
            parts = _load_via_xde(abs_path, deflection, should_stop, progress)
            if not any(p.has_mesh for p in parts):
                raise StepLoadError("XDE produced no meshes")
        except StepLoadCancelled:
            raise
        except Exception as e1:
            logger.info("STEP XDE failed (%s); trying names/colors: %s", e1, abs_path)
            try:
                parts = _load_via_names_colors(
                    abs_path, deflection, should_stop, progress
                )
                loader = "names_colors"
            except StepLoadCancelled:
                raise
            except Exception as e2:
                logger.info(
                    "STEP names/colors failed (%s); using STEPControl: %s",
                    e2,
                    abs_path,
                )
                parts = _load_via_step_control(
                    abs_path, deflection, should_stop, progress
                )
                loader = "step_control"
        if not any(p.has_mesh for p in parts):
            return StepLoadResult(
                parts=[],
                source_path=abs_path,
                error="No tessellated faces (wireframe-only or empty STEP)",
            )
        if progress:
            n = len(parts)
            progress(n, n, "done")
        logger.info("STEP loaded via %s: %s (%s part(s))", loader, abs_path, len(parts))
        return StepLoadResult(parts=parts, source_path=abs_path)
    except StepLoadCancelled:
        return StepLoadResult(parts=[], source_path=abs_path, cancelled=True)
    except StepLoadError as e:
        return StepLoadResult(parts=[], source_path=abs_path, error=str(e))
    except Exception as e:
        return StepLoadResult(parts=[], source_path=abs_path, error=str(e))
