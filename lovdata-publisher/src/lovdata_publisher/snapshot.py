"""Read-only validation of the loader/publisher snapshot contract.

Version 1 supports the original manifest's three recorded counts. Version 2
also requires a forskrift count and a complete SHA-256 inventory of generated
artifacts (plus the source receipt, when present). Version 3 additionally permits
ordered paragraph blocks under an explicit content and Markdown contract. Older
versions retain their original paragraph interpretation. Raw archives are deliberately
not required: publishers receive the verified snapshot artifact, not downloads.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Invalid snapshot JSON {path}: {exc}") from exc


def _count(manifest: dict, name: str) -> int:
    value = manifest.get(name)
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid snapshot manifest count: {name}")
    return value


def _regular_file(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Missing or invalid snapshot artifact: {path}")


def _validate_nodes(nodes, kind: str, path: Path, version: int):
    if not isinstance(nodes, list):
        raise ValueError(f"Invalid snapshot {kind} list in {path}")
    child_fields = {
        "section": (("articles", "article"), ("subsections", "section")),
        "article": (("paragraphs", "paragraph"),),
        "paragraph": (("list_items", "item"),),
        "item": (("paragraphs", "paragraph"),),
    }
    text_fields = {
        "section": ("heading",), "article": ("name", "header_text", "trailing_text"),
        "paragraph": ("text", "trailing_text", "list_style"), "item": ("marker", "value"),
    }
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError(f"Invalid snapshot {kind} in {path}")
        for field in text_fields[kind]:
            if field in node and not isinstance(node[field], str):
                raise ValueError(f"Invalid snapshot {kind}.{field} in {path}")
        for field in ("preamble", "footnotes", "remainders"):
            if field in node and (not isinstance(node[field], list) or
                                  not all(isinstance(text, str) for text in node[field])):
                raise ValueError(f"Invalid snapshot {kind}.{field} in {path}")
        if kind == "paragraph":
            blocks = node.get("ordered_blocks", [])
            if not isinstance(blocks, list):
                raise ValueError(f"Invalid ordered paragraph blocks in {path}")
            if blocks:
                if version < 3:
                    raise ValueError(f"Ordered paragraph content requires snapshot version 3: {path}")
                if any(node.get(field) for field in ("text", "list_items", "list_style", "trailing_text")):
                    raise ValueError(f"Ordered paragraph cannot also contain legacy content: {path}")
                for block in blocks:
                    if (not isinstance(block, dict)
                            or set(block) - {"kind", "text", "list_items", "list_style"}
                            or not isinstance(block.get("text", ""), str)
                            or not isinstance(block.get("list_style", ""), str)
                            or not isinstance(block.get("list_items", []), list)):
                        raise ValueError(f"Invalid ordered paragraph block in {path}")
                    if block.get("kind") == "text":
                        if not block.get("text", "").strip() or block.get("list_items") or block.get("list_style"):
                            raise ValueError(f"Invalid ordered text block in {path}")
                    elif block.get("kind") == "list":
                        if block.get("text") or not block.get("list_items"):
                            raise ValueError(f"Invalid ordered list block in {path}")
                        _validate_nodes(block["list_items"], "item", path, version)
                    else:
                        raise ValueError(f"Unsupported ordered paragraph block in {path}")
        for field, child_kind in child_fields[kind]:
            _validate_nodes(node.get(field, []), child_kind, path, version)


def _validate_document(data, path: Path, prefix: str, version: int):
    if not isinstance(data, dict):
        raise ValueError(f"Snapshot document must be an object: {path}")
    refid = data.get("refid")
    if not isinstance(refid, str) or not re.fullmatch(
        rf"{prefix}/[A-Za-z0-9][A-Za-z0-9._-]*", refid
    ) or path.name != f"{refid.replace('/', '-')}.json":
        raise ValueError(f"Invalid snapshot refid or filename: {path}")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ValueError(f"Missing snapshot document title: {path}")
    for field in ("short_title", "ministry", "date_in_force", "last_amended",
                  "last_amended_in_force", "legal_area"):
        if field in data and not isinstance(data[field], str):
            raise ValueError(f"Invalid snapshot document {field}: {path}")
    if not isinstance(data.get("remainders", []), list) or not all(
        isinstance(text, str) for text in data.get("remainders", [])
    ):
        raise ValueError(f"Invalid snapshot document remainders: {path}")
    _validate_nodes(data.get("sections", []), "section", path, version)
    _validate_nodes(data.get("top_level_articles", []), "article", path, version)
    _validate_nodes(data.get("top_level_paragraphs", []), "paragraph", path, version)


def _validate_database(path: Path, manifest: dict):
    expected_columns = {
        "amendment_acts": {"refid", "filename", "title", "short_title", "date_in_force",
                           "date_in_force_resolved", "is_deferred", "date_published", "ministry",
                           "changes_to", "misc_info", "journal_number", "amendment_count"},
        "amendments": {"id", "act_refid", "change_type", "target", "target_law", "instruction", "new_text"},
    }
    try:
        # immutable/ro prevents validation from creating or modifying SQLite files.
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
            conn.execute("PRAGMA trusted_schema=OFF")
            if conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("Snapshot database integrity check failed")
            for table, columns in expected_columns.items():
                actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if not columns.issubset(actual):
                    raise ValueError(f"Invalid snapshot database schema: {table}")
            for table, count_name in (("amendment_acts", "amendment_act_count"),
                                      ("amendments", "amendment_count")):
                actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if actual != _count(manifest, count_name):
                    raise ValueError(f"Snapshot {count_name} mismatch: manifest={manifest[count_name]}, actual={actual}")
            orphan = conn.execute("""SELECT 1 FROM amendments a LEFT JOIN amendment_acts p
                ON a.act_refid = p.refid WHERE p.refid IS NULL LIMIT 1""").fetchone()
            mismatch = conn.execute("""SELECT 1 FROM amendment_acts p LEFT JOIN amendments a
                ON a.act_refid = p.refid GROUP BY p.refid, p.amendment_count
                HAVING p.amendment_count IS NULL OR p.amendment_count != COUNT(a.id) LIMIT 1""").fetchone()
            duplicate = conn.execute("""SELECT 1 FROM amendment_acts GROUP BY refid
                HAVING refid IS NULL OR COUNT(*) != 1 LIMIT 1""").fetchone()
            if orphan or mismatch or duplicate:
                raise ValueError("Snapshot amendment rows do not agree with their parent acts")
    except (sqlite3.Error, OSError) as exc:
        raise ValueError(f"Invalid snapshot amendments database: {exc}") from exc


def validate_snapshot(snapshot_dir: str | Path) -> dict:
    """Validate every consumed artifact before publication; return its manifest.

    Raises ValueError for missing, unsupported, malformed or inconsistent input.
    Validation never creates output directories or opens the database writable.
    """
    root = Path(snapshot_dir)
    if not root.is_dir():
        raise ValueError(f"Snapshot directory does not exist: {root}")
    manifest_path = root / "manifest.json"
    _regular_file(manifest_path)
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or type(manifest.get("version")) is not int or manifest["version"] not in (1, 2, 3):
        raise ValueError("Invalid or unsupported snapshot manifest version")
    version = manifest["version"]
    contracts = (("ordered-paragraph-blocks-v1", "law-markdown-ordered-html-v1") if version == 3
                 else ("legacy-paragraphs-v1", "law-markdown-v1"))
    for field, expected in zip(("content_version", "formatter_version"), contracts):
        if manifest.get(field, expected if version < 3 else None) != expected:
            raise ValueError(f"Unsupported snapshot content/formatter contract: {field}")
    for field in ("created_at", "loader_version", "gjeldende_archive"):
        if not isinstance(manifest.get(field), str):
            raise ValueError(f"Invalid snapshot manifest field: {field}")
    if not isinstance(manifest.get("lovtidend_archives"), list) or not all(
        isinstance(name, str) for name in manifest["lovtidend_archives"]
    ):
        raise ValueError("Invalid snapshot manifest field: lovtidend_archives")
    artifact_paths = []
    for subdir, prefix, count_name in (("laws", "lov", "law_count"),
                                       ("forskrifter", "forskrift", "forskrift_count")):
        directory = root / subdir
        if directory.is_symlink() or getattr(directory, "is_junction", lambda: False)():
            raise ValueError(f"Invalid snapshot artifact directory: {directory}")
        if (version >= 2 or subdir == "laws") and not directory.is_dir():
            raise ValueError(f"Missing snapshot artifact directory: {directory}")
        if directory.exists() and not directory.is_dir():
            raise ValueError(f"Invalid snapshot artifact directory: {directory}")
        paths = sorted(directory.glob("*.json"))
        for path in paths:
            _regular_file(path)
            _validate_document(_read_json(path), path, prefix, version)
        if version >= 2 or subdir == "laws" or count_name in manifest:
            if len(paths) != _count(manifest, count_name):
                raise ValueError(f"Snapshot {count_name} mismatch: manifest={manifest[count_name]}, actual={len(paths)}")
        artifact_paths.extend(paths)
    database = root / "amendments.db"
    _regular_file(database)
    if any((root / f"amendments.db{suffix}").exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("Snapshot contains mutable SQLite sidecar files")
    artifact_paths.append(database)
    receipt = root / "source-manifest.json"
    if receipt.exists():
        _regular_file(receipt)
        # download_archives writes the canonical selected-archive list directly.
        sources = _read_json(receipt)
        if not isinstance(sources, list) or not sources:
            raise ValueError("Invalid snapshot source manifest")
        names = []
        for source in sources:
            if (not isinstance(source, dict)
                    or set(source) != {"filename", "lastModified", "sizeBytes"}
                    or not isinstance(source["filename"], str)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]+", source["filename"])
                    or not isinstance(source["lastModified"], str)
                    or not source["lastModified"].strip()
                    or type(source["sizeBytes"]) is not int or source["sizeBytes"] <= 0):
                raise ValueError("Invalid snapshot source manifest entry")
            names.append(source["filename"])
        if names != sorted(set(names)):
            raise ValueError("Snapshot source manifest must contain unique, sorted archives")
        artifact_paths.append(receipt)
    if version >= 2:
        _count(manifest, "forskrift_count")
        if not isinstance(manifest.get("forskrifter_archive"), str):
            raise ValueError("Invalid snapshot manifest field: forskrifter_archive")
        if manifest.get("duplicate_policy") != "last-occurrence-wins":
            raise ValueError("Invalid snapshot duplicate policy")
        duplicates = manifest.get("duplicate_counts")
        if not isinstance(duplicates, dict) or set(duplicates) != {"laws", "forskrifter", "amendment_acts"}:
            raise ValueError("Invalid snapshot duplicate counts")
        for key in duplicates:
            _count(duplicates, key)
        hashes = manifest.get("artifact_hashes")
        expected = {path.relative_to(root).as_posix() for path in artifact_paths}
        if not isinstance(hashes, dict) or set(hashes) != expected:
            raise ValueError("Snapshot artifact hash inventory does not match files")
        for path in artifact_paths:
            name = path.relative_to(root).as_posix()
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if hashes[name] != actual:
                raise ValueError(f"Snapshot artifact hash mismatch: {name}")
    _validate_database(database, manifest)
    return manifest
