"""Invalid snapshot input must fail before changing published output."""
import hashlib
import json
import sqlite3

import pytest

from lovdata_publisher.formatter import format_all_laws


def make_snapshot(root, version=1):
    (root / "laws").mkdir(parents=True)
    (root / "forskrifter").mkdir()
    (root / "laws/lov-2024-01-01-1.json").write_text(
        json.dumps({"refid": "lov/2024-01-01-1", "title": "Test law", "sections": []}),
        encoding="utf-8",
    )
    with sqlite3.connect(root / "amendments.db") as conn:
        conn.executescript("""
            CREATE TABLE amendment_acts (refid TEXT PRIMARY KEY, filename TEXT,
              title TEXT, short_title TEXT, date_in_force TEXT, date_in_force_resolved TEXT,
              is_deferred INTEGER, date_published TEXT, ministry TEXT, changes_to TEXT,
              misc_info TEXT, journal_number TEXT, amendment_count INTEGER);
            CREATE TABLE amendments (id INTEGER PRIMARY KEY, act_refid TEXT,
              change_type TEXT, target TEXT, target_law TEXT, instruction TEXT, new_text TEXT);
        """)
    manifest = dict(version=version, created_at="2026-09-25T00:00:00+00:00", loader_version="0.1.0",
                    gjeldende_archive="laws.tar.bz2", lovtidend_archives=[], law_count=1,
                    amendment_act_count=0, amendment_count=0)
    if version == 2:
        # Canonical downloader receipt: a list, rather than a wrapper object.
        (root / "source-manifest.json").write_text(json.dumps([
            {"filename": "gjeldende-lover.tar.bz2", "lastModified": "2026-09-19T01:31:00Z", "sizeBytes": 5810986},
            {"filename": "gjeldende-sentrale-forskrifter.tar.bz2", "lastModified": "2026-09-25T01:31:00Z", "sizeBytes": 21343742},
            {"filename": "lovtidend-avd1-2001-2025.tar.bz2", "lastModified": "2026-09-14T01:31:00Z", "sizeBytes": 69305260},
            {"filename": "lovtidend-avd1-2026.tar.bz2", "lastModified": "2026-09-24T01:30:00Z", "sizeBytes": 1432514},
        ]), encoding="utf-8")
        manifest.update(forskrift_count=0, forskrifter_archive="", duplicate_policy="last-occurrence-wins",
                        duplicate_counts={"laws": 0, "forskrifter": 0, "amendment_acts": 0},
                        artifact_hashes={p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in root.rglob("*") if p.is_file()})
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def output_files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file()}


def test_missing_snapshot_does_not_create_output(tmp_path):
    out = tmp_path / "out"
    with pytest.raises(ValueError, match="[Ss]napshot"):
        format_all_laws(str(tmp_path / "missing"), str(out))
    assert not out.exists()


@pytest.mark.parametrize("damage", ["manifest", "count", "json", "title", "database", "unsafe_refid"])
def test_invalid_input_preserves_all_output(tmp_path, damage):
    snap = make_snapshot(tmp_path / "snapshot")
    out = tmp_path / "out"
    (out / "lover").mkdir(parents=True)
    (out / "lover/lov-2000-01-01-1.md").write_text("keep old output", encoding="utf-8")
    before = output_files(out)
    if damage == "manifest":
        (snap / "manifest.json").unlink()
    elif damage == "count":
        manifest = json.loads((snap / "manifest.json").read_text())
        manifest["law_count"] = 20
        (snap / "manifest.json").write_text(json.dumps(manifest))
    elif damage in {"json", "title", "unsafe_refid"}:
        (snap / "laws/lov-2024-02-01-2.json").write_text(
            {"json": "{", "title": '{"refid": "lov/2024-02-01-2"}',
             "unsafe_refid": '{"refid": "lov/../../outside", "title": "Bad"}'}[damage], encoding="utf-8")
    else:
        (snap / "amendments.db").write_bytes(b"not sqlite")
    with pytest.raises(ValueError):
        format_all_laws(str(snap), str(out))
    assert output_files(out) == before
    assert not (out / "forskrifter").exists()


@pytest.mark.parametrize("version", [1, 2])
def test_valid_versioned_snapshot_formats(tmp_path, version):
    snap = make_snapshot(tmp_path / "snapshot", version)
    result = format_all_laws(str(snap), str(tmp_path / "out"))
    assert result == {"lov/2024-01-01-1": "lover/lov-2024-01-01-1.md"}


def test_hash_mismatch_rejected_before_output(tmp_path):
    snap = make_snapshot(tmp_path / "snapshot", 2)
    path = snap / "laws/lov-2024-01-01-1.json"
    path.write_text(path.read_text().replace("Test law", "Changed law"), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        format_all_laws(str(snap), str(tmp_path / "out"))
    assert not (tmp_path / "out").exists()


def test_database_internal_counts_are_validated(tmp_path):
    snap = make_snapshot(tmp_path / "snapshot")
    with sqlite3.connect(snap / "amendments.db") as conn:
        conn.execute("INSERT INTO amendment_acts (refid, amendment_count) VALUES ('lov/2024-01-01-2', 1)")
    manifest = json.loads((snap / "manifest.json").read_text())
    manifest["amendment_act_count"] = 1
    (snap / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="amendment"):
        format_all_laws(str(snap), str(tmp_path / "out"))


def test_invalid_render_structure_leaves_all_output_unchanged(tmp_path):
    snap = make_snapshot(tmp_path / "snapshot")
    (snap / "laws/lov-2024-01-01-1.json").write_text(json.dumps({
        "refid": "lov/2024-01-01-1", "title": "Broken law", "sections": [None],
    }))
    with pytest.raises(ValueError):
        format_all_laws(str(snap), str(tmp_path / "out"))
    assert not (tmp_path / "out").exists()
