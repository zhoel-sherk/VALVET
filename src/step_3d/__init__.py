"""Optional STEP → mesh preview tab (PyVista / VTK)."""

from __future__ import annotations

__all__ = ["Step3DTabWidget"]


def __getattr__(name: str):
    if name == "Step3DTabWidget":
        from .tab import Step3DTabWidget as _Step3DTabWidget

        return _Step3DTabWidget
    raise AttributeError(name)
