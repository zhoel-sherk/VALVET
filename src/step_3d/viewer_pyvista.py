"""PyVista Qt embed: trackball rotate / wheel zoom (VTK defaults)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtGui, QtWidgets

if TYPE_CHECKING:
    pass


class PyVistaViewPane(QtWidgets.QWidget):
    """
    Hosts a ``pyvistaqt.QtInteractor`` with stretch-friendly layout.

    VTK defaults: left drag = rotate, wheel = zoom, shift+left / middle = pan.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        from pyvistaqt import QtInteractor  # lazy: heavy import chain

        self._plotter = QtInteractor(self)
        self._plotter.setMinimumHeight(280)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._plotter, stretch=1)

    def plotter(self):
        return self._plotter

    def load_mesh_path(self, mesh_path: str) -> None:
        import pyvista as pv

        mesh = pv.read(mesh_path)
        self._plotter.clear()
        self._plotter.add_mesh(
            mesh, color="lightgray", show_edges=True, smooth_shading=True
        )
        self._plotter.reset_camera()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        try:
            self._plotter.close()
        except Exception:
            pass
        super().closeEvent(event)
