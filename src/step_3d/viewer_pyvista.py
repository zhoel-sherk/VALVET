"""PyVista Qt embed: trackball rotate / wheel zoom (VTK defaults)."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from step_3d.occ_load import TessellatedPart

DEFAULT_BG_RGB = (0.753, 0.753, 0.784)
_HIDDEN_CELL = 2


class PyVistaViewPane(QtWidgets.QWidget):
    """
    Hosts a ``pyvistaqt.QtInteractor`` with stretch-friendly layout.

    VTK defaults: left drag = rotate, wheel = zoom, shift+left / middle = pan.
    """

    part_picked = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        from pyvistaqt import QtInteractor  # lazy: heavy import chain

        self._plotter = QtInteractor(self)
        self._plotter.setMinimumHeight(280)
        self._bg_rgb = DEFAULT_BG_RGB
        self.set_background_rgb(DEFAULT_BG_RGB)
        self._actors: dict[str, object] = {}
        self._colors: dict[str, tuple[float, float, float]] = {}
        self._highlighted: str | None = None
        self._picking_ready = False
        self._merged: object | None = None
        self._cell_part: object | None = None
        self._idx_to_id: list[str] = []
        self._id_to_idx: dict[str, int] = {}
        self._hidden: set[str] = set()
        self._base_cell_rgb: object | None = None
        self._rgba: object | None = None
        self._ghost: object | None = None
        self._vtk_ghost: object | None = None
        self._cell_ranges: list[tuple[int, int]] = []
        self._applied_hidden: set[str] = set()
        self._applied_highlight: str | None = None
        self._vtk_colors: object | None = None
        self._display_timer = QtCore.QTimer(self)
        self._display_timer.setSingleShot(True)
        self._display_timer.setInterval(20)
        self._display_timer.timeout.connect(self._apply_display_colors)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._plotter, stretch=1)

    def set_background_rgb(self, rgb: tuple[float, float, float]) -> None:
        self._bg_rgb = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
        r, g, b = self._bg_rgb
        try:
            self._plotter.set_background([r, g, b])
        except Exception:
            try:
                self._plotter.set_background(color=[r, g, b])
            except Exception:
                pass
        try:
            self._plotter.render()
        except Exception:
            pass

    def plotter(self):
        return self._plotter

    def load_mesh_path(self, mesh_path: str, *, show_edges: bool = False) -> None:
        import pyvista as pv

        mesh = pv.read(mesh_path)
        self._plotter.clear()
        self.set_background_rgb(self._bg_rgb)
        self._actors.clear()
        self._colors.clear()
        self._highlighted = None
        self._merged = None
        self._cell_part = None
        self._idx_to_id = []
        self._id_to_idx = {}
        self._hidden = set()
        self._base_cell_rgb = None
        self._rgba = None
        self._ghost = None
        self._vtk_ghost = None
        self._cell_ranges = []
        self._applied_hidden = set()
        self._applied_highlight = None
        self._vtk_colors = None
        self._display_timer.stop()
        actor = self._plotter.add_mesh(
            mesh,
            color="lightgray",
            show_edges=show_edges,
            smooth_shading=True,
            name="cli_mesh",
            pickable=True,
        )
        self._actors["cli_mesh"] = actor
        self._colors["cli_mesh"] = (0.72, 0.72, 0.72)
        self._plotter.reset_camera()
        self.set_background_rgb(self._bg_rgb)
        self._setup_picking()

    def load_parts(
        self, parts: list[TessellatedPart], *, show_edges: bool = False
    ) -> None:
        import numpy as np
        import pyvista as pv

        self._plotter.clear()
        self.set_background_rgb(self._bg_rgb)
        self._actors.clear()
        self._colors.clear()
        self._highlighted = None
        self._merged = None
        self._cell_part = None
        self._idx_to_id = []
        self._id_to_idx = {}
        self._hidden = set()
        self._base_cell_rgb = None
        self._rgba = None
        self._ghost = None
        self._vtk_ghost = None
        self._cell_ranges = []
        self._applied_hidden = set()
        self._applied_highlight = None
        self._vtk_colors = None
        self._display_timer.stop()
        self._picking_ready = False

        pt_chunks: list = []
        face_chunks: list = []
        rgb_chunks: list = []
        idx_chunks: list = []
        offset = 0
        cell_offset = 0
        for part in parts:
            if not part.has_mesh:
                continue
            pts = np.asarray(part.vertices, dtype=np.float32)
            tris = np.asarray(part.faces, dtype=np.int64)
            if pts.size == 0 or tris.size == 0:
                continue
            n_tri = int(tris.shape[0])
            pi = len(self._idx_to_id)
            self._idx_to_id.append(part.id)
            self._id_to_idx[part.id] = pi
            rgb_t = part.color
            self._colors[part.id] = rgb_t
            pt_chunks.append(pts)
            faces = np.empty((n_tri, 4), dtype=np.int64)
            faces[:, 0] = 3
            faces[:, 1:] = tris + offset
            face_chunks.append(faces.ravel())
            rgb = np.asarray(rgb_t, dtype=np.float32)
            rgb_chunks.append(np.broadcast_to(rgb, (n_tri, 3)).copy())
            idx_chunks.append(np.full(n_tri, pi, dtype=np.int32))
            self._cell_ranges.append((cell_offset, cell_offset + n_tri))
            cell_offset += n_tri
            offset += int(pts.shape[0])
            part.vertices.clear()
            part.faces.clear()

        if not pt_chunks:
            return

        points = np.concatenate(pt_chunks, axis=0)
        faces = np.concatenate(face_chunks)
        cell_rgb = np.concatenate(rgb_chunks, axis=0)
        cell_part = np.concatenate(idx_chunks)
        del pt_chunks, face_chunks, rgb_chunks, idx_chunks

        mesh = pv.PolyData(points, faces)
        del points, faces
        mesh.cell_data["part_idx"] = cell_part
        rgb_u8 = np.clip(cell_rgb * 255.0, 0, 255).astype(np.uint8)
        mesh.cell_data["colors"] = rgb_u8
        ghost = np.zeros(rgb_u8.shape[0], dtype=np.uint8)
        mesh.cell_data["vtkGhostType"] = ghost
        self._merged = mesh
        self._cell_part = cell_part
        self._base_cell_rgb = cell_rgb
        self._rgba = rgb_u8
        self._ghost = ghost

        add_kw = dict(
            scalars="colors",
            rgb=True,
            opacity=1.0,
            show_edges=show_edges,
            smooth_shading=True,
            lighting=True,
            ambient=0.28,
            diffuse=0.72,
            specular=0.08,
            name="assembly",
            pickable=True,
        )
        try:
            actor = self._plotter.add_mesh(mesh, preference="cell", **add_kw)
        except TypeError:
            actor = self._plotter.add_mesh(mesh, **add_kw)
        self._actors["assembly"] = actor
        self._force_opaque_actor(actor)
        try:
            src = actor.GetMapper().GetInput()
            bind_mesh = src if src is not None else mesh
        except Exception:
            bind_mesh = mesh
        self._bind_vtk_colors(bind_mesh, rgb_u8)
        self._bind_vtk_ghost(bind_mesh, ghost)
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.processEvents()
        self._plotter.reset_camera()
        self.set_background_rgb(self._bg_rgb)
        self._setup_picking()
        try:
            self._plotter.render()
        except Exception:
            pass

    def _force_opaque_actor(self, actor: object) -> None:
        try:
            prop = actor.GetProperty() if hasattr(actor, "GetProperty") else actor.prop
            prop.SetOpacity(1.0)
            prop.SetLighting(True)
        except Exception:
            pass
        try:
            mapper = actor.GetMapper() if hasattr(actor, "GetMapper") else actor.mapper
            mapper.SetScalarModeToUseCellFieldData()
            mapper.SelectColorArray("colors")
            mapper.SetColorModeToDirectScalars()
            mapper.SetResolveCoincidentTopologyToPolygonOffset()
        except Exception:
            pass

    def _bind_vtk_colors(self, mesh: object, rgb_u8: object) -> None:
        try:
            from vtkmodules.util.numpy_support import vtk_to_numpy

            vtk_arr = mesh.GetCellData().GetArray("colors")
            view = vtk_to_numpy(vtk_arr)
            n = int(rgb_u8.shape[0])
            if int(view.size) == n * 3:
                self._rgba = view.reshape(n, 3)
                self._vtk_colors = vtk_arr
                return
        except Exception:
            pass
        self._vtk_colors = None

    def _bind_vtk_ghost(self, mesh: object, ghost: object) -> None:
        import numpy as np

        try:
            from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy

            cd = mesh.GetCellData()
            vtk_arr = cd.GetArray("vtkGhostType")
            n = int(np.asarray(ghost).shape[0])
            if vtk_arr is None:
                vtk_arr = numpy_to_vtk(np.ascontiguousarray(ghost), deep=True)
                vtk_arr.SetName("vtkGhostType")
                cd.AddArray(vtk_arr)
            view = vtk_to_numpy(vtk_arr)
            if int(view.size) == n:
                self._ghost = view.reshape(n)
                self._vtk_ghost = vtk_arr
                return
        except Exception:
            pass
        self._vtk_ghost = None

    def _push_colors(self, mesh: object, rgb_u8: object) -> None:
        if self._vtk_colors is not None:
            try:
                self._vtk_colors.Modified()
            except Exception:
                mesh.cell_data["colors"] = rgb_u8
        else:
            mesh.cell_data["colors"] = rgb_u8
        if self._vtk_ghost is not None:
            try:
                self._vtk_ghost.Modified()
            except Exception:
                pass
        elif self._ghost is not None:
            mesh.cell_data["vtkGhostType"] = self._ghost

    def _hidden_cell_flag(self) -> int:
        try:
            from vtkmodules.vtkCommonDataModel import vtkDataSetAttributes

            return int(vtkDataSetAttributes.HIDDENCELL)
        except Exception:
            return _HIDDEN_CELL

    def set_part_visible(self, part_id: str, visible: bool) -> None:
        self.set_parts_visible((part_id,), visible)

    def set_parts_visible(self, part_ids: object, visible: bool) -> None:
        ids = [str(p) for p in part_ids]
        if not ids:
            return
        if self._merged is not None:
            if visible:
                self._hidden.difference_update(ids)
            else:
                self._hidden.update(ids)
            self._schedule_display()
            return
        for pid in ids:
            actor = self._actors.get(pid)
            if actor is None:
                continue
            try:
                actor.SetVisibility(1 if visible else 0)
            except Exception:
                try:
                    actor.visibility = visible
                except Exception:
                    pass
        try:
            self._plotter.render()
        except Exception:
            pass

    def highlight_part(self, part_id: str | None) -> None:
        self._highlighted = part_id
        if self._merged is not None:
            self._schedule_display()
            return
        for pid, actor in self._actors.items():
            base = self._colors.get(pid, (0.72, 0.72, 0.72))
            try:
                prop = actor.prop
            except Exception:
                prop = actor.GetProperty() if hasattr(actor, "GetProperty") else None
            if prop is None:
                continue
            if part_id is None:
                self._set_prop_color(prop, base)
                self._set_prop_opacity(prop, 1.0)
            elif pid == part_id:
                self._set_prop_color(prop, (1.0, 0.85, 0.15))
                self._set_prop_opacity(prop, 1.0)
            else:
                self._set_prop_color(prop, base)
                self._set_prop_opacity(prop, 0.22)
        try:
            self._plotter.render()
        except Exception:
            pass

    def _schedule_display(self) -> None:
        self._display_timer.start()

    def _slice_for_part(self, part_id: str) -> tuple[int, int] | None:
        i = self._id_to_idx.get(part_id)
        if i is None or i >= len(self._cell_ranges):
            return None
        return self._cell_ranges[i]

    def _apply_display_colors(self) -> None:
        import numpy as np

        mesh = self._merged
        rgb_u8 = self._rgba
        ghost = self._ghost
        base = self._base_cell_rgb
        if mesh is None or rgb_u8 is None or base is None:
            return
        flag = self._hidden_cell_flag()
        hide = self._hidden - self._applied_hidden
        show = self._applied_hidden - self._hidden
        if ghost is not None:
            for pid in hide:
                sl = self._slice_for_part(pid)
                if sl is not None:
                    ghost[sl[0] : sl[1]] = flag
            for pid in show:
                sl = self._slice_for_part(pid)
                if sl is not None:
                    ghost[sl[0] : sl[1]] = 0
        self._applied_hidden = set(self._hidden)

        old_h = self._applied_highlight
        new_h = self._highlighted
        if old_h != new_h:
            if old_h:
                sl = self._slice_for_part(old_h)
                if sl is not None:
                    a, b = sl
                    rgb_u8[a:b] = np.clip(base[a:b] * 255.0, 0, 255).astype(np.uint8)
            if new_h:
                sl = self._slice_for_part(new_h)
                if sl is not None:
                    a, b = sl
                    rgb_u8[a:b] = np.array((255, 217, 38), dtype=np.uint8)
            self._applied_highlight = new_h

        self._push_colors(mesh, rgb_u8)
        try:
            mapper = self._actors.get("assembly")
            if mapper is not None:
                m = mapper.GetMapper() if hasattr(mapper, "GetMapper") else None
                if m is not None:
                    m.Update()
        except Exception:
            pass
        try:
            self._plotter.render()
        except Exception:
            pass

    @staticmethod
    def _set_prop_color(prop: object, rgb: tuple[float, float, float]) -> None:
        try:
            prop.color = rgb
            return
        except Exception:
            pass
        try:
            prop.SetColor(*rgb)
        except Exception:
            pass

    @staticmethod
    def _set_prop_opacity(prop: object, opacity: float) -> None:
        try:
            prop.opacity = opacity
            return
        except Exception:
            pass
        try:
            prop.SetOpacity(opacity)
        except Exception:
            pass

    def _setup_picking(self) -> None:
        if self._picking_ready:
            return
        if self._merged is not None:
            try:
                self._plotter.enable_cell_picking(
                    callback=self._on_cell_picked,
                    through=False,
                    show=False,
                    show_message=False,
                )
                self._picking_ready = True
                return
            except TypeError:
                try:
                    self._plotter.enable_cell_picking(callback=self._on_cell_picked)
                    self._picking_ready = True
                    return
                except Exception:
                    pass
            except Exception:
                pass
        try:
            self._plotter.enable_mesh_picking(
                callback=self._on_mesh_picked,
                use_actor=True,
                show=False,
                show_message=False,
            )
            self._picking_ready = True
        except TypeError:
            try:
                self._plotter.enable_mesh_picking(
                    callback=self._on_mesh_picked,
                    show=False,
                )
                self._picking_ready = True
            except Exception:
                self._picking_ready = False
        except Exception:
            self._picking_ready = False

    def _on_cell_picked(self, *args) -> None:
        part_id = None
        for arg in args:
            part_id = self._part_id_from_cell_pick(arg)
            if part_id:
                break
        if part_id is None:
            try:
                picked = getattr(self._plotter, "picked_cell", None)
                part_id = self._part_id_from_cell_pick(picked)
            except Exception:
                part_id = None
        if part_id:
            self.part_picked.emit(part_id)

    def _part_id_from_cell_pick(self, obj: object) -> str | None:
        if obj is None:
            return None
        try:
            data = obj.cell_data["part_idx"]
            raw = data[0] if hasattr(data, "__len__") and len(data) else data
            idx = int(raw)
            if 0 <= idx < len(self._idx_to_id):
                return self._idx_to_id[idx]
        except Exception:
            pass
        return None

    def _on_mesh_picked(self, *args) -> None:
        part_id = None
        for arg in args:
            part_id = self._part_id_from_picked(arg)
            if part_id:
                break
        if part_id is None:
            try:
                picked = getattr(self._plotter, "picked_mesh", None)
                part_id = self._part_id_from_picked(picked)
            except Exception:
                part_id = None
        if part_id:
            self.part_picked.emit(part_id)

    def _part_id_from_picked(self, obj: object) -> str | None:
        if obj is None:
            return None
        try:
            fd = obj.field_data
            val = fd["valvet_part"]
            if hasattr(val, "__len__") and len(val) >= 1:
                raw = val[0]
            else:
                raw = val
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace")
            return str(raw)
        except Exception:
            pass
        name = getattr(obj, "name", None)
        if isinstance(name, str) and name in self._actors:
            return name
        for pid, actor in self._actors.items():
            try:
                if actor is obj:
                    return pid
            except Exception:
                continue
        return None

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        try:
            self._plotter.close()
        except Exception:
            pass
        super().closeEvent(event)
