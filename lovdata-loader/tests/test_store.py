"""Snapshot generations must agree with their manifest and survive failed writes."""
import json
import sqlite3
from pathlib import Path

import pytest

from lovdata_loader.models import Amendment, AmendmentActData, LawData
from lovdata_loader.store import read_manifest, write_snapshot


def law(refid="lov/2024-01-01-1", title="Test law"):
    return LawData(refid, title, "", "", "", "", "", "")


def act(refid="lov/2024-02-01-2", text="New text"):
    return AmendmentActData(
        refid, "test.xml", "Amendment", "", "2024-03-01", "2024-02-01",
        "", ["lov/2024-01-01-1"],
        [Amendment("change", "lov/2024-01-01-1/§1", "§ 1", text)], "", "",
    )


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_reused_directory_has_no_stale_database_rows(tmp_path):
    root = tmp_path / "snapshot"
    write_snapshot(str(root), [law()], [act()])
    write_snapshot(str(root), [], [])
    with sqlite3.connect(root / "amendments.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM amendment_acts").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM amendments").fetchone()[0] == 0
    assert not list((root / "laws").glob("*.json"))


def test_v2_manifest_counts_artifacts_and_preserves_source_files(tmp_path):
    root = tmp_path / "snapshot"
    root.mkdir()
    (root / "source.tar.bz2").write_bytes(b"archive evidence")
    receipt = [{"filename": "source.tar.bz2", "lastModified": "2026-09-25T01:31:00Z", "sizeBytes": 16}]
    (root / "source-manifest.json").write_text(json.dumps(receipt), encoding="utf-8")
    write_snapshot(str(root), [law()], [act()], forskrifter=[law("forskrift/2024-01-01-2")],
                   forskrifter_archive="source.tar.bz2")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 2
    assert (manifest["law_count"], manifest["forskrift_count"],
            manifest["amendment_act_count"], manifest["amendment_count"]) == (1, 1, 1, 1)
    assert manifest["forskrifter_archive"] == "source.tar.bz2"
    assert set(manifest["artifact_hashes"]) == {
        "laws/lov-2024-01-01-1.json", "forskrifter/forskrift-2024-01-01-2.json",
        "amendments.db", "source-manifest.json",
    }
    assert (root / "source.tar.bz2").read_bytes() == b"archive evidence"
    assert json.loads((root / "source-manifest.json").read_text()) == receipt
    assert read_manifest(str(root)).forskrift_count == 1


def test_duplicate_identities_preserve_last_occurrence_and_report_unique_counts(tmp_path):
    root = tmp_path / "snapshot"
    write_snapshot(str(root), [law(title="Bokmål"), law(title="Nynorsk")],
                   [act(text="old"), act(text="new")])
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["law_count"] == manifest["amendment_act_count"] == 1
    assert manifest["amendment_count"] == 1
    assert manifest["duplicate_policy"] == "last-occurrence-wins"
    assert manifest["duplicate_counts"] == {"laws": 1, "forskrifter": 0, "amendment_acts": 1}
    assert json.loads((root / "laws/lov-2024-01-01-1.json").read_text(encoding="utf-8"))["title"] == "Nynorsk"
    with sqlite3.connect(root / "amendments.db") as conn:
        assert conn.execute("SELECT new_text FROM amendments").fetchone()[0] == "new"


def test_serialization_failure_leaves_previous_snapshot_unchanged(tmp_path, monkeypatch):
    root = tmp_path / "snapshot"
    write_snapshot(str(root), [law()], [act()])
    before = files(root)
    monkeypatch.setattr(LawData, "to_json", lambda self: (_ for _ in ()).throw(RuntimeError("serialization failed")))
    with pytest.raises(RuntimeError, match="serialization failed"):
        write_snapshot(str(root), [law(title="replacement")], [])
    assert files(root) == before


def test_promotion_failure_rolls_back_previous_snapshot(tmp_path, monkeypatch):
    root = tmp_path / "snapshot"
    write_snapshot(str(root), [law()], [act()])
    before = files(root)
    original_replace = Path.replace

    def fail_new_generation(self, target):
        if Path(target) == root and self != root and ".staging-" in self.name:
            raise OSError("promotion failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_new_generation)
    with pytest.raises(OSError, match="promotion failed"):
        write_snapshot(str(root), [], [])
    assert files(root) == before


@pytest.mark.parametrize("refid", ["lov/../../outside", "lov/x\\outside", "../outside", ""])
def test_unsafe_refid_fails_without_changing_snapshot(tmp_path, refid):
    root = tmp_path / "snapshot"
    write_snapshot(str(root), [law()], [])
    before = files(root)
    with pytest.raises(ValueError, match="refid"):
        write_snapshot(str(root), [law(refid)], [])
    assert files(root) == before
