from __future__ import annotations

import os
import pickle
import sys

import pandas as pd

tests_path = os.path.dirname(os.path.realpath(__file__))
_repo_root = os.path.dirname(tests_path)
sys.path.append(os.path.join(_repo_root, "src"))

import working_copy


def test_working_copy_snapshot_roundtrip(tmp_path):
    src = tmp_path / "bom.xlsx"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Comment": ["100R", "10nF"], "Extra": ["A", "B"]})

    meta_path = working_copy.save_snapshot(df, src, "bom", autosave, dirty=True)
    assert meta_path.exists()

    snap = working_copy.find_snapshot(src, "bom", autosave)
    assert snap is not None
    assert snap.meta["kind"] == "bom"
    assert snap.meta["dirty"] is True
    pd.testing.assert_frame_equal(snap.dataframe, df)


def test_working_copy_exact_snapshot_can_be_marked_clean(tmp_path):
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})

    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=False)
    snap = working_copy.find_snapshot(src, "pnp", autosave)
    assert snap is not None
    assert snap.meta["dirty"] is False


def test_find_snapshot_skips_unreadable_pickle(tmp_path, monkeypatch):
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})
    meta_path = working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    pkl = meta_path.with_suffix(".pkl")
    pkl.write_bytes(b"not-a-valid-pickle")
    warnings: list[str] = []
    monkeypatch.setattr(
        working_copy.logger,
        "warning",
        lambda msg, *args, **kwargs: warnings.append(msg % args if args else str(msg)),
    )
    snap = working_copy.find_snapshot(src, "pnp", autosave)
    assert snap is None
    assert warnings
    assert any("unreadable" in w.lower() or "pickle" in w.lower() for w in warnings)


def test_save_snapshot_strips_string_dtype(tmp_path):
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": pd.Series(["MHT1", "F2"], dtype="string")})
    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    snap = working_copy.find_snapshot(src, "pnp", autosave)
    assert snap is not None
    assert list(snap.dataframe["Designator"]) == ["MHT1", "F2"]
    assert not isinstance(snap.dataframe["Designator"].dtype, pd.StringDtype)


def test_find_snapshot_notimplementederror_from_read_pickle(tmp_path, monkeypatch):
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})
    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    warnings: list[str] = []

    def _boom(*_a: object, **_k: object) -> None:
        raise NotImplementedError("StringDtype")

    monkeypatch.setattr(working_copy.pd, "read_pickle", _boom)
    monkeypatch.setattr(
        working_copy.logger,
        "warning",
        lambda msg, *args, **kwargs: warnings.append(msg % args if args else str(msg)),
    )
    snap = working_copy.find_snapshot(src, "pnp", autosave)
    assert snap is None
    assert any("NotImplementedError" in w for w in warnings)


def test_find_snapshot_skips_non_dataframe_pickle(tmp_path, monkeypatch):
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})
    meta_path = working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    pkl = meta_path.with_suffix(".pkl")
    pkl.write_bytes(pickle.dumps(["not", "a", "frame"]))
    warnings: list[str] = []
    monkeypatch.setattr(
        working_copy.logger,
        "warning",
        lambda msg, *args, **kwargs: warnings.append(msg % args if args else str(msg)),
    )
    snap = working_copy.find_snapshot(src, "pnp", autosave)
    assert snap is None
    assert any("DataFrame" in w for w in warnings)


def test_find_snapshot_legacy_path_after_mtime_change(tmp_path):
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["MHT1", "F2"]})
    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    src.write_text("source-changed", encoding="utf-8")
    snap = working_copy.find_snapshot(src, "pnp", autosave)
    assert snap is not None
    assert snap.meta["dirty"] is True
    pd.testing.assert_frame_equal(snap.dataframe, df)


def test_list_snapshot_indices_skips_tmp_and_orphans(tmp_path):
    src = tmp_path / "pnp.csv"
    src.write_text("source", encoding="utf-8")
    autosave = tmp_path / "autosave"
    df = pd.DataFrame({"Designator": ["R1"]})
    working_copy.save_snapshot(df, src, "pnp", autosave, dirty=True)
    (autosave / "foo.json.tmp").write_text("{}", encoding="utf-8")
    (autosave / "orphan.json").write_text(
        '{"kind": "pnp", "saved_at": "z"}', encoding="utf-8"
    )
    indices = working_copy.list_snapshot_indices(autosave)
    assert len(indices) == 1
    assert indices[0].meta_path.suffix == ".json"
    assert not indices[0].meta_path.name.endswith(".tmp")
