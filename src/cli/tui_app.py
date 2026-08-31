"""Minimal Textual TUI: load, map, preview, clean, merge, save. No Step / PCB."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Log, Static

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
    #paths { height: auto; }
    #maps { height: auto; }
    #buttons { height: auto; }
    DataTable { height: 1fr; }
    #log { height: 10; }
    """
    TITLE = "VALVET CLI"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.session = CliSession()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Horizontal(
                Label("BOM"),
                Input(placeholder="path to BOM", id="bom_path"),
                Label("PnP"),
                Input(placeholder="path to PnP", id="pnp_path"),
                Button("Load", id="load", variant="primary"),
                id="paths",
            ),
            Horizontal(
                Label("BOM REF"),
                Input(placeholder="Ref", id="bom_ref"),
                Label("Comment"),
                Input(placeholder="Comment", id="bom_comment"),
                Label("PnP REF"),
                Input(placeholder="Designator", id="pnp_ref"),
                Label("X"),
                Input(placeholder="X", id="pnp_x"),
                Label("Y"),
                Input(placeholder="Y", id="pnp_y"),
                Label("Rot"),
                Input(placeholder="Rotation", id="pnp_rot"),
                Label("Layer"),
                Input(placeholder="Layer", id="pnp_layer"),
                Label("Footprint"),
                Input(placeholder="Footprint", id="pnp_foot"),
                id="maps",
            ),
            Horizontal(
                Button("Clean", id="clean"),
                Button("Merge", id="merge"),
                Button("Save xlsx", id="save"),
                Input(placeholder="merge.xlsx", id="save_path", value="merge.xlsx"),
                Label("Hanwha .mdb"),
                Input(placeholder="UPD.MDB", id="mdb_path"),
                Button("MDB tables", id="mdb_tables"),
                Button("PART_Det", id="mdb_parts"),
                id="buttons",
            ),
            Static("Preview", id="preview_label"),
            DataTable(id="table", zebra_stripes=True),
            Log(id="log"),
        )
        yield Footer()

    def _log(self, msg: str) -> None:
        self.query_one("#log", Log).write_line(msg)

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
        _put(s.pnp_mappings, "Rotation", "pnp_rot")
        _put(s.pnp_mappings, "Layer", "pnp_layer")
        _put(s.pnp_mappings, "Footprint", "pnp_foot")

    def _show_df(self, df) -> None:
        table = self.query_one("#table", DataTable)
        table.clear(columns=True)
        if df is None or df.empty:
            table.add_columns("(empty)")
            return
        cols = [str(c) for c in df.columns]
        table.add_columns(*cols)
        for _, row in df.head(_PREVIEW_ROWS).iterrows():
            table.add_row(*[str(row[c]) if c in row.index else "" for c in df.columns])
        extra = len(df) - _PREVIEW_ROWS
        label = f"Preview ({min(len(df), _PREVIEW_ROWS)} of {len(df)} rows)"
        if extra > 0:
            label += f" — {extra} more not shown"
        self.query_one("#preview_label", Static).update(label)

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
                    self._show_df(self.session.bom_df)
            if pnp:
                pnp_path = self._validate_path(pnp, "PnP")
                if pnp_path is not None:
                    load_pnp(self.session, str(pnp_path))
                    self._log(
                        f"Loaded PnP {pnp_path} ({len(self.session.pnp_df)} rows)"
                    )
                    if self.session.bom_df is None:
                        self._show_df(self.session.pnp_df)
        except Exception as exc:
            self._log(f"Load failed: {exc}")

    def _do_clean(self) -> None:
        self._read_maps()
        try:
            preview = clean_comments(self.session, apply=True)
            self._log(f"Clean applied ({len(preview)} rows)")
            self._show_df(self.session.bom_df)
        except Exception as exc:
            self._log(f"Clean failed: {exc}")

    def _do_merge(self) -> None:
        self._read_maps()
        try:
            merge_df, report_df = merge_and_check(self.session)
            self._log(
                f"Merge {len(merge_df)} rows; cross-check {len(report_df)} issue(s)"
            )
            self._show_df(merge_df)
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
