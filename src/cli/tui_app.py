"""Minimal Textual TUI: load, map, preview, clean, merge, save. No Step / PCB."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Static,
)

from cli.hanwha import HanwhaMdbToolsError, format_part_det, format_tables
from cli.pipeline import (
    clean_comments,
    export_merge,
    load_bom,
    load_pnp,
    merge_and_check,
)
from cli.session import CliSession

_PREVIEW_ROWS = 40


class ValvetTui(App):
    """Single-screen BOM/PnP helper."""

    CSS = """
    Screen { layout: vertical; }

    #main { height: 1fr; padding: 1 2; overflow-y: auto; }

    .section-title { color: $accent; text-style: bold; height: 1; margin: 0 0 1 0; }

    .panel {
        border: round $primary;
        height: auto;
        padding: 1;
        margin-bottom: 1;
    }

    .toolbar { height: 3; align-vertical: middle; margin-bottom: 1; }
    .panel > .toolbar:last-child { margin-bottom: 0; }

    .field-label {
        width: 11;
        color: $text-muted;
        text-style: bold;
        padding: 0 0 0 1;
    }
    .toolbar Input { width: 1fr; height: 3; }
    .toolbar Button { height: 3; min-width: 12; margin: 0 0 0 1; }

    #preview_host { height: 1fr; border: round $primary; margin-bottom: 1; }
    #preview_host > * { width: 100%; height: 100%; }
    #preview-empty {
        content-align: center middle;
        color: $text-muted;
        text-style: italic;
    }
    DataTable { border: none; }

    #log { height: 8; border: round $primary; }
    """

    TITLE = "VALVET CLI"
    SUB_TITLE = "BOM / PnP quick tools"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+s", "save", "Save xlsx"),
        ("ctrl+m", "merge", "Merge"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session = CliSession()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Static("Load files", classes="section-title"),
            Vertical(
                Horizontal(
                    Label("BOM", classes="field-label"),
                    Input(placeholder="path to BOM", id="bom_path"),
                    Label("PnP", classes="field-label"),
                    Input(placeholder="path to PnP", id="pnp_path"),
                    Button("Load", id="load", variant="primary"),
                    classes="toolbar",
                ),
                classes="panel",
            ),
            Static("Column mapping", classes="section-title"),
            Vertical(
                Horizontal(
                    Label("BOM REF", classes="field-label"),
                    Input(placeholder="REF column", id="bom_ref"),
                    Label("Comment", classes="field-label"),
                    Input(placeholder="Comment column", id="bom_comment"),
                    classes="toolbar",
                ),
                Horizontal(
                    Label("PnP REF", classes="field-label"),
                    Input(placeholder="Designator", id="pnp_ref"),
                    Label("X", classes="field-label"),
                    Input(placeholder="X column", id="pnp_x"),
                    Label("Y", classes="field-label"),
                    Input(placeholder="Y column", id="pnp_y"),
                    Label("Rot", classes="field-label"),
                    Input(placeholder="Rotation", id="pnp_rot"),
                    classes="toolbar",
                ),
                Horizontal(
                    Label("Layer", classes="field-label"),
                    Input(placeholder="Layer column", id="pnp_layer"),
                    Label("Footprint", classes="field-label"),
                    Input(placeholder="Footprint column", id="pnp_foot"),
                    classes="toolbar",
                ),
                classes="panel",
            ),
            Static("Actions", classes="section-title"),
            Vertical(
                Horizontal(
                    Button("Clean", id="clean"),
                    Button("Merge", id="merge", variant="primary"),
                    Button("Save xlsx", id="save", variant="success"),
                    Label("Save as", classes="field-label"),
                    Input(value="merge.xlsx", id="save_path"),
                    classes="toolbar",
                ),
                Horizontal(
                    Label("Hanwha .mdb", classes="field-label"),
                    Input(placeholder="path to UPD.MDB", id="mdb_path"),
                    Button("MDB tables", id="mdb_tables"),
                    Button("PART_Det", id="mdb_parts"),
                    classes="toolbar",
                ),
                classes="panel",
            ),
            Static("Preview", id="preview-title", classes="section-title"),
            ContentSwitcher(
                Static(
                    "Nothing loaded yet — enter a BOM / PnP path and press Load.",
                    id="preview-empty",
                ),
                DataTable(id="table", zebra_stripes=True),
                id="preview_host",
            ),
            Log(id="log", highlight=True),
            id="main",
        )
        yield Footer()

    def _log(self, msg: str) -> None:
        self.query_one("#log", Log).write_line(msg)

    def _set_preview_title(self, text: str) -> None:
        self.query_one("#preview-title", Static).update(text)

    def _read_maps(self) -> None:
        s = self.session

        def _put(dest: dict, role: str, widget_id: str) -> None:
            val = self.query_one(f"#{widget_id}", Input).value.strip()
            if val:
                dest[role] = val

        s.bom_mappings.clear()
        s.pnp_mappings.clear()
        _put(s.bom_mappings, "REF", "bom_ref")
        _put(s.bom_mappings, "Comment", "bom_comment")
        _put(s.pnp_mappings, "REF", "pnp_ref")
        _put(s.pnp_mappings, "X", "pnp_x")
        _put(s.pnp_mappings, "Y", "pnp_y")
        _put(s.bom_mappings, "Rotation", "pnp_rot")
        _put(s.bom_mappings, "Layer", "pnp_layer")
        _put(s.pnp_mappings, "Footprint", "pnp_foot")

    def _show_df(self, df, *, title: str = "Preview") -> None:
        switcher = self.query_one("#preview_host", ContentSwitcher)
        if df is None or df.empty:
            self._set_preview_title(title)
            switcher.current = "preview-empty"
            return
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        cols = [str(c) for c in df.columns]
        table.add_columns(*cols)
        for _, row in df.head(_PREVIEW_ROWS).iterrows():
            table.add_row(*[str(row[c]) if c in row.index else "" for c in df.columns])
        n = len(df)
        shown = min(n, _PREVIEW_ROWS)
        suffix = f" — {n - shown} more not shown" if n > shown else ""
        self._set_preview_title(f"{title}: {shown} of {n} rows{suffix}")
        switcher.current = "table"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "load":
            self._do_load()
        elif bid == "clean":
            self._do_clean()
        elif bid == "merge":
            self._do_merge()
        elif bid == "save":
            self._do_save()
        elif bid == "mdb_tables":
            self._do_mdb(tables=True)
        elif bid == "mdb_parts":
            self._do_mdb(tables=False)

    def action_save(self) -> None:
        self._do_save()

    def action_merge(self) -> None:
        self._do_merge()

    def _validate_path(self, raw: str, label: str) -> Path | None:
        p = Path(raw.strip())
        if not p.is_file():
            self._log(f"{label} not found or not a file: {p}")
            return None
        return p

    def _do_load(self) -> None:
        bom = self.query_one("#bom_path", Input).value.strip()
        pnp = self.query_one("#pnp_path", Input).value.strip()
        if not bom and not pnp:
            self._log("Enter a BOM and/or PnP path")
            return
        try:
            if bom:
                bom_path = self._validate_path(bom, "BOM")
                if bom_path is not None:
                    load_bom(self.session, str(bom_path))
                    self._log(
                        f"Loaded BOM {bom_path} ({len(self.session.bom_df)} rows)"
                    )
                    self._show_df(self.session.bom_df, title="BOM")
            if pnp:
                pnp_path = self._validate_path(pnp, "PnP")
                if pnp_path is not None:
                    load_pnp(self.session, str(pnp_path))
                    self._log(
                        f"Loaded PnP {pnp_path} ({len(self.session.pnp_df)} rows)"
                    )
                    if self.session.bom_df is None:
                        self._show_df(self.session.pnp_df, title="PnP")
        except Exception as exc:
            self._log(f"Load failed: {exc}")

    def _do_clean(self) -> None:
        self._read_maps()
        try:
            preview = clean_comments(self.session, apply=True)
            self._log(f"Clean applied ({len(preview)} rows)")
            self._show_df(self.session.bom_df, title="BOM")
        except Exception as exc:
            self._log(f"Clean failed: {exc}")

    def _do_merge(self) -> None:
        self._read_maps()
        try:
            merge_df, report_df = merge_and_check(self.session)
            self._log(
                f"Merge {len(merge_df)} rows; cross-check {len(report_df)} issue(s)"
            )
            self._show_df(merge_df, title="Merge")
        except Exception as exc:
            self._log(f"Merge failed: {exc}")

    def _do_save(self) -> None:
        path = self.query_one("#save_path", Input).value.strip() or "merge.xlsx"
        if not path.lower().endswith((".xlsx", ".xls", ".csv")):
            path = str(Path(path).with_suffix(".xlsx"))
        try:
            if self.session.merge_df is None:
                self._read_maps()
                merge_and_check(self.session)
            export_merge(self.session, path)
            self._log(f"Wrote {path}")
        except Exception as exc:
            self._log(f"Save failed: {exc}")

    def _do_mdb(self, *, tables: bool) -> None:
        raw = self.query_one("#mdb_path", Input).value.strip()
        if not raw:
            self._log("Enter a .mdb path")
            return
        path = self._validate_path(raw, "MDB")
        if path is None:
            return
        try:
            text = (
                format_tables(str(path))
                if tables
                else format_part_det(str(path), limit=40)
            )
            for line in text.splitlines():
                self._log(line)
        except HanwhaMdbToolsError as exc:
            self._log(str(exc))
        except Exception as exc:
            self._log(f"Hanwha failed: {exc}")


def run_tui() -> int:
    ValvetTui().run()
    return 0
