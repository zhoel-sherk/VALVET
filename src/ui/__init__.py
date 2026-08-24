"""PySide6 presentation modules (thin UI — wiring only, logic in facades / core).

Tab mixins: bom_tab, clean_tab, files, mapping, merge_tab, pnp_tab, profiles,
report_tab, session, table_actions. Project tab helpers live in project_tab.
"""

from ui.project_tab import setup_project_tab

__all__ = ["setup_project_tab"]
