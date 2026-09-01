# SPDX-License-Identifier: MIT
"""SQLite store for VSPD packages, aliases, and component links."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from package_vspd.catalog import iter_seed_packages, load_aliases
from package_vspd.parse import normalize_package_key, parse_package

SCHEMA = """
CREATE TABLE IF NOT EXISTS package (
    vspd_id TEXT PRIMARY KEY,
    class TEXT NOT NULL,
    family TEXT NOT NULL,
    display_name TEXT NOT NULL,
    notes TEXT,
    body_l REAL,
    body_w REAL,
    body_h REAL,
    outline_json TEXT
);
CREATE TABLE IF NOT EXISTS alias (
    norm_key TEXT PRIMARY KEY,
    raw TEXT NOT NULL,
    standard TEXT NOT NULL,
    vspd_id TEXT NOT NULL,
    FOREIGN KEY (vspd_id) REFERENCES package(vspd_id)
);
CREATE TABLE IF NOT EXISTS component_link (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    vspd_id TEXT NOT NULL,
    UNIQUE (kind, value),
    FOREIGN KEY (vspd_id) REFERENCES package(vspd_id)
);
CREATE TABLE IF NOT EXISTS preset (
    name TEXT PRIMARY KEY,
    spec_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alias_vspd ON alias(vspd_id);
CREATE INDEX IF NOT EXISTS idx_link_vspd ON component_link(vspd_id);
"""


class PackageStore:
    def __init__(self, db_path: Path | str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._ensure_catalog()
        self._compact_alias_keys()

    def close(self) -> None:
        self._conn.close()

    def commit(self) -> None:
        self._conn.commit()

    def _ensure_catalog(self) -> None:
        for row in iter_seed_packages():
            self._conn.execute(
                """INSERT OR IGNORE INTO package
                   (vspd_id, class, family, display_name, notes, body_l, body_w, body_h)
                   VALUES (?, ?, ?, ?, '', ?, ?, ?)""",
                (
                    row["vspd_id"],
                    row["class"],
                    row["family"],
                    row["display_name"],
                    row["body_l"],
                    row["body_w"],
                    row["body_h"],
                ),
            )
        for raw, vid in load_aliases().items():
            if vid.strip().upper() == "OTHER":
                continue
            self.add_alias(raw, vid, "catalog", commit=False)
        self._conn.commit()

    def clear_other_noise(self) -> int:
        n = int(
            self._conn.execute(
                "SELECT COUNT(*) FROM alias WHERE vspd_id = 'OTHER'"
            ).fetchone()[0]
        )
        self._conn.execute("DELETE FROM alias WHERE vspd_id = 'OTHER'")
        self._conn.execute("DELETE FROM component_link WHERE vspd_id = 'OTHER'")
        self._conn.commit()
        return n

    def _compact_alias_keys(self) -> None:
        rows = list(
            self._conn.execute("SELECT raw, standard, vspd_id, norm_key FROM alias")
        )
        if not rows:
            return
        if all(str(r["norm_key"]) == normalize_package_key(r["raw"]) for r in rows):
            return
        merged: dict[str, tuple[str, str, str]] = {}
        for r in rows:
            key = normalize_package_key(r["raw"])
            if not key:
                continue
            merged[key] = (str(r["raw"]), str(r["standard"]), str(r["vspd_id"]))
        self._conn.execute("DELETE FROM alias")
        for key, (raw, std, vid) in merged.items():
            self._conn.execute(
                """INSERT INTO alias (norm_key, raw, standard, vspd_id)
                   VALUES (?, ?, ?, ?)""",
                (key, raw, std, vid),
            )
        self._conn.commit()

    def add_alias(
        self, raw: str, vspd_id: str, standard: str, *, commit: bool = True
    ) -> None:
        key = normalize_package_key(raw)
        if not key:
            return
        if vspd_id.strip().upper() == "OTHER":
            return
        self.ensure_package(vspd_id)
        self._conn.execute(
            """INSERT INTO alias (norm_key, raw, standard, vspd_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(norm_key) DO UPDATE SET
                 raw=excluded.raw, standard=excluded.standard, vspd_id=excluded.vspd_id""",
            (key, raw.strip(), standard, vspd_id),
        )
        if commit:
            self._conn.commit()

    def add_link(
        self, kind: str, value: str, vspd_id: str, *, commit: bool = True
    ) -> None:
        self.ensure_package(vspd_id)
        self._conn.execute(
            """INSERT INTO component_link (kind, value, vspd_id)
               VALUES (?, ?, ?)
               ON CONFLICT(kind, value) DO UPDATE SET vspd_id=excluded.vspd_id""",
            (kind, value.strip(), vspd_id),
        )
        if commit:
            self._conn.commit()

    def ensure_package(
        self,
        vspd_id: str,
        *,
        class_name: str = "ODD-FORM",
        family: str = "OTHER",
    ) -> None:
        vid = vspd_id.strip()
        if not vid:
            return
        cur = self._conn.execute("SELECT 1 FROM package WHERE vspd_id = ?", (vid,))
        if cur.fetchone() is None:
            self._conn.execute(
                """INSERT INTO package (vspd_id, class, family, display_name, notes)
                   VALUES (?, ?, ?, ?, '')""",
                (vid, class_name, family, vid),
            )
            self._conn.commit()

    def has_outline(self, vspd_id: str) -> bool:
        row = self.get_package(vspd_id)
        if row is None:
            return False
        raw = row["outline_json"]
        return bool(raw and str(raw).strip())

    def set_outline_json(self, vspd_id: str, outline_json: str) -> None:
        self._conn.execute(
            "UPDATE package SET outline_json = ? WHERE vspd_id = ?",
            (outline_json, vspd_id),
        )
        self._conn.commit()

    def lookup_vspd(self, text: str) -> Optional[str]:
        """Resolve a part/package string via alias.norm_key or component_link.value.

        Does not call parse_package. Never returns OTHER.
        """
        s = (text or "").strip()
        if not s or s.lower() in {"nan", "none"}:
            return None
        key = normalize_package_key(s)
        if key:
            row = self._conn.execute(
                "SELECT vspd_id FROM alias WHERE norm_key = ?", (key,)
            ).fetchone()
            if row is not None:
                vid = str(row["vspd_id"]).strip()
                if vid and vid.upper() != "OTHER":
                    return vid
        row = self._conn.execute(
            """SELECT vspd_id FROM component_link
               WHERE value = ? COLLATE NOCASE
               LIMIT 1""",
            (s,),
        ).fetchone()
        if row is not None:
            vid = str(row["vspd_id"]).strip()
            if vid and vid.upper() != "OTHER":
                return vid
        return None

    def get_package(self, vspd_id: str) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM package WHERE vspd_id = ?", (vspd_id,)
        ).fetchone()

    def list_packages(self) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                """SELECT p.*,
                    (SELECT COUNT(*) FROM alias a WHERE a.vspd_id = p.vspd_id) AS alias_n,
                    (SELECT COUNT(*) FROM component_link c WHERE c.vspd_id = p.vspd_id) AS link_n
                   FROM package p ORDER BY p.class, p.family, p.vspd_id"""
            )
        )

    def aliases_for(self, vspd_id: str) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                "SELECT * FROM alias WHERE vspd_id = ? ORDER BY raw", (vspd_id,)
            )
        )

    def links_for(self, vspd_id: str) -> list[sqlite3.Row]:
        return list(
            self._conn.execute(
                "SELECT * FROM component_link WHERE vspd_id = ? ORDER BY kind, value",
                (vspd_id,),
            )
        )

    def import_name(self, raw: str, *, kind: str, standard: str) -> str:
        hit = parse_package(raw)
        vid = hit.vspd_id or "OTHER"
        self.add_alias(raw, vid, standard)
        self.add_link(kind, raw, vid)
        return vid

    def rename_package(self, old_id: str, new_id: str) -> None:
        new_id = new_id.strip()
        if not new_id or new_id == old_id:
            return
        self.ensure_package(new_id)
        self._conn.execute(
            "UPDATE alias SET vspd_id = ? WHERE vspd_id = ?", (new_id, old_id)
        )
        self._conn.execute(
            "UPDATE component_link SET vspd_id = ? WHERE vspd_id = ?",
            (new_id, old_id),
        )
        self._conn.commit()
