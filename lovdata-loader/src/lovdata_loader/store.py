"""Serialize parsed data into a snapshot directory.

A snapshot is the stable intermediate format between lovdata-loader and
lovdata-publisher. It consists of:
  - laws/<refid>.json   — one JSON file per law (structured, not Markdown)
  - amendments.db       — SQLite database of amendment acts
  - manifest.json       — metadata about this snapshot
"""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .models import (AmendmentActData, LawData, Manifest, uses_ordered_content,
                     ORDERED_CONTENT_VERSION, ORDERED_FORMATTER_VERSION)
from .parser import parse_effective_date, parse_publication_date


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the amendments SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS amendment_acts (
            refid TEXT PRIMARY KEY,
            filename TEXT,
            title TEXT,
            short_title TEXT,
            date_in_force TEXT,
            date_in_force_resolved TEXT,
            is_deferred INTEGER,
            date_published TEXT,
            ministry TEXT,
            changes_to TEXT,
            misc_info TEXT,
            journal_number TEXT,
            amendment_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS amendments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            act_refid TEXT REFERENCES amendment_acts(refid),
            change_type TEXT,
            target TEXT,
            target_law TEXT,
            instruction TEXT,
            new_text TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_amendments_act ON amendments(act_refid);
        CREATE INDEX IF NOT EXISTS idx_acts_date ON amendment_acts(date_in_force_resolved);
        CREATE INDEX IF NOT EXISTS idx_amendments_law ON amendments(target_law);
    """)
    return conn


def store_amendment_act(conn: sqlite3.Connection, act: AmendmentActData):
    """Store a single amendment act and its amendments in SQLite."""
    effective_date, is_deferred = parse_effective_date(
        act.date_in_force, act.date_published
    )
    pub_date = parse_publication_date(act.date_published)

    # Delete existing amendment rows first to avoid duplicates on re-run.
    # INSERT OR REPLACE on the parent table replaces the act row, but
    # child rows in amendments would otherwise accumulate.
    conn.execute("DELETE FROM amendments WHERE act_refid = ?", (act.refid,))

    conn.execute(
        """
        INSERT OR REPLACE INTO amendment_acts
        (refid, filename, title, short_title, date_in_force, date_in_force_resolved,
         is_deferred, date_published, ministry, changes_to, misc_info, journal_number,
         amendment_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            act.refid,
            act.filename,
            act.title,
            act.short_title,
            act.date_in_force,
            effective_date,
            int(is_deferred),
            pub_date,
            act.ministry,
            ",".join(act.changes_to),
            act.misc_info,
            act.journal_number,
            len(act.amendments),
        ),
    )

    for a in act.amendments:
        conn.execute(
            """
            INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (act.refid, a.change_type, a.target, a.target_law, a.instruction, a.new_text),
        )


def _unique_records(records, prefix: str | None = None):
    """Preserve the historic last-occurrence choice, while counting actual rows.

    Consolidated archives can contain language variants with the same refid.
    This keeps that existing choice explicit instead of inventing a language
    policy or claiming that overwritten variants were separately published.
    """
    unique = {}
    for record in records:
        refid = record.refid
        if not isinstance(refid, str) or not re.fullmatch(
            r"(?:lov|forskrift)/[A-Za-z0-9][A-Za-z0-9._-]*", refid
        ) or (prefix and not refid.startswith(prefix + "/")):
            raise ValueError(f"Invalid snapshot refid: {refid!r}")
        if not isinstance(record.title, str) or not record.title.strip():
            raise ValueError(f"Missing title for snapshot refid: {refid!r}")
        unique[refid] = record
    return unique


def _copy_source_file(src, dst):
    """Keep large raw archives without requiring a second full disk copy."""
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)
    return str(dst)


def _remove_work_directory(path: Path, root: Path):
    """Only remove our uniquely named sibling staging/backup directories."""
    if path.parent.resolve() != root.parent.resolve() or not path.name.startswith(
        (f".{root.name}.staging-", f".{root.name}.backup-")
    ):
        raise ValueError(f"Refusing to remove unexpected snapshot work path: {path}")
    if path.exists():
        shutil.rmtree(path)


def write_snapshot(
    output_dir: str,
    laws: list[LawData],
    amendment_acts: list[AmendmentActData],
    gjeldende_archive: str = "",
    lovtidend_archives: list[str] | None = None,
    forskrifter: list[LawData] | None = None,
    forskrifter_archive: str = "",
) -> str:
    """Build and promote a complete version-2/3 snapshot from parsed data.

    Creates:
      output_dir/
      ├── manifest.json
      ├── laws/
      │   ├── lov-1814-05-17.json
      │   └── ...
      ├── forskrifter/
      │   ├── forskrift-2024-06-21-1166.json (optional)
      │   └── ...
      └── amendments.db

    A fresh database and all JSON files are staged beside the destination.
    Existing raw downloads are preserved. A failed build or directory promotion
    leaves the previous snapshot intact; concurrent writers fail on a lock.
    Directory renames avoid mixed artifact generations, but a process crash
    between the two renames may require restoring the retained backup directory.
    Version 3 marks ordered paragraph content that older publishers must reject;
    snapshots containing only legacy paragraphs keep version 2 compatibility.

    Returns the snapshot directory path.
    """
    if lovtidend_archives is None:
        lovtidend_archives = []
    if forskrifter is None:
        forskrifter = []

    law_records = _unique_records(laws, "lov")
    forskrift_records = _unique_records(forskrifter, "forskrift")
    act_records = _unique_records(amendment_acts)
    requested_root = Path(output_dir)
    if requested_root.is_symlink() or getattr(requested_root, "is_junction", lambda: False)():
        raise ValueError("Snapshot output must not be a symlink or junction")
    root = requested_root.absolute()
    if root.exists() and not root.is_dir():
        raise ValueError(f"Snapshot output is not a directory: {root}")
    root.parent.mkdir(parents=True, exist_ok=True)
    lock = root.with_name(f".{root.name}.snapshot.lock")
    lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    stage = None
    backup = root.with_name(f".{root.name}.backup-{uuid.uuid4().hex}")
    try:
        stage = Path(tempfile.mkdtemp(prefix=f".{root.name}.staging-", dir=root.parent))
        # The download CLI stores archives and its provenance receipt in root.
        # Preserve all other entries, but never carry forward database sidecars.
        if root.exists():
            for entry in root.iterdir():
                if entry.name in {"laws", "forskrifter", "manifest.json", "amendments.db",
                                  "amendments.db-wal", "amendments.db-shm", "amendments.db-journal"}:
                    continue
                destination = stage / entry.name
                if entry.is_symlink() or getattr(entry, "is_junction", lambda: False)():
                    raise ValueError(f"Snapshot source entry must not be a link: {entry}")
                if entry.is_dir():
                    shutil.copytree(entry, destination, copy_function=_copy_source_file, symlinks=True)
                elif entry.name == "source-manifest.json":
                    shutil.copy2(entry, destination)
                else:
                    _copy_source_file(entry, destination)

        artifacts = []
        for subdir, records in (("laws", law_records), ("forskrifter", forskrift_records)):
            (stage / subdir).mkdir()
            for refid, record in sorted(records.items()):
                path = stage / subdir / f"{refid.replace('/', '-')}.json"
                path.write_text(record.to_json(), encoding="utf-8", newline="\n")
                artifacts.append(path)

        conn = init_db(str(stage / "amendments.db"))
        try:
            for act in act_records.values():
                store_amendment_act(conn, act)
            conn.commit()
            actual_acts = conn.execute("SELECT COUNT(*) FROM amendment_acts").fetchone()[0]
            actual_amendments = conn.execute("SELECT COUNT(*) FROM amendments").fetchone()[0]
            if actual_acts != len(act_records) or actual_amendments != sum(len(a.amendments) for a in act_records.values()):
                raise ValueError("Snapshot amendment counts do not match staged database")
            if conn.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("Snapshot database integrity check failed")
        finally:
            conn.close()
        artifacts.append(stage / "amendments.db")
        if (stage / "source-manifest.json").is_file():
            artifacts.append(stage / "source-manifest.json")
        hashes = {}
        for path in artifacts:
            with path.open("rb") as stream:
                hashes[path.relative_to(stage).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
        ordered = any(uses_ordered_content(record)
                      for records in (law_records, forskrift_records) for record in records.values())
        manifest = Manifest(
            version=3 if ordered else 2,
            created_at=datetime.now(timezone.utc).isoformat(),
            loader_version=__version__,
            gjeldende_archive=gjeldende_archive,
            lovtidend_archives=lovtidend_archives,
            law_count=len(law_records),
            forskrift_count=len(forskrift_records),
            forskrifter_archive=forskrifter_archive,
            amendment_act_count=actual_acts,
            amendment_count=actual_amendments,
            artifact_hashes=hashes,
            duplicate_counts={"laws": len(laws) - len(law_records),
                              "forskrifter": len(forskrifter) - len(forskrift_records),
                              "amendment_acts": len(amendment_acts) - len(act_records)},
            content_version=ORDERED_CONTENT_VERSION if ordered else "legacy-paragraphs-v1",
            formatter_version=ORDERED_FORMATTER_VERSION if ordered else "law-markdown-v1",
        )
        (stage / "manifest.json").write_text(manifest.to_json(), encoding="utf-8", newline="\n")
        had_previous = root.exists()
        if had_previous:
            root.replace(backup)
        try:
            stage.replace(root)
        except BaseException:
            if had_previous:
                backup.replace(root)
            raise
        if backup.exists():
            # The committed snapshot is usable even if old-backup cleanup fails.
            try:
                _remove_work_directory(backup, root)
            except OSError:
                pass
    finally:
        try:
            if stage is not None:
                _remove_work_directory(stage, root)
        finally:
            os.close(lock_fd)
            lock.unlink()
    return str(requested_root)


def read_laws_from_snapshot(snapshot_dir: str) -> list[LawData]:
    """Read all law JSON files from a snapshot directory."""
    laws_dir = Path(snapshot_dir) / "laws"
    laws = []
    for path in sorted(laws_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        laws.append(LawData.from_dict(data))
    return laws


def read_manifest(snapshot_dir: str) -> Manifest:
    """Read the manifest from a snapshot directory."""
    path = Path(snapshot_dir) / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return Manifest.from_dict(data)
