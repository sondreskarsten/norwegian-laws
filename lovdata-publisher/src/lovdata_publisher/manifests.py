"""Generate JSON Lines manifests for programmatic consumption.

Two files at the deployed site root:

- amendment-acts.jsonl(.gz) — one row per amendment act (~38,672 rows). Coarser
  grain; matches Atom feed entries 1:1.
- amendments.jsonl(.gz) — one row per (act, target_law, paragraph) triple
  (~90,000 rows). Finer grain; suitable for "did any amendment touch §7-25
  in regnskapsloven since 2023?" queries.

Both are sorted newest-first by date_published. Any downstream pipeline can
ingest these without parsing 2,627 XML files.

Files are written to the deployed site (_site/), NOT committed to git, since
the uncompressed sizes (~30MB and ~40MB) would bloat the repo on every
regeneration. The .gz versions (~3-5MB each) are the recommended download.
"""
from __future__ import annotations

import gzip
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path


# Shared by the writers and the homepage counts so display eligibility cannot drift.
_ACTS_EXPORT_SOURCE = """
    FROM amendment_acts
    WHERE date_published IS NOT NULL AND date_published != ''
"""
_AMENDMENTS_EXPORT_SOURCE = """
    FROM amendments a
    LEFT JOIN amendment_acts ac ON a.act_refid = ac.refid
    WHERE a.target_law IS NOT NULL AND a.target_law != ''
"""


def count_manifest_rows(db_path: str) -> tuple[int, int]:
    """Count exactly the rows eligible for the two display exports."""
    with closing(sqlite3.connect(db_path)) as conn:
        acts = conn.execute("SELECT COUNT(*) " + _ACTS_EXPORT_SOURCE).fetchone()[0]
        has_amendments = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='amendments'"
        ).fetchone()
        amendments = (
            conn.execute("SELECT COUNT(*) " + _AMENDMENTS_EXPORT_SOURCE).fetchone()[0]
            if has_amendments else 0
        )
    return acts, amendments


def _normalize_paragraph_ref(target: str, instruction: str) -> str:
    """Extract canonical paragraph ref. Mirrors feeds._normalize_paragraph_ref."""
    para_re = re.compile(r'§§?\s*(\d+\s*[-–]\s*\d+(?:[a-z](?=$|[^a-zæøåA-ZÆØÅ]))?)')
    text = (target or "").strip()
    if not text or text.lower().startswith("kapittel") or text.lower().startswith("del "):
        m = para_re.search(instruction or "")
        if m:
            return f"§ {re.sub(r'\\s+', '-', m.group(1).strip())}"
        return ""
    # Use .search() so 'lov/1915-08-13-5/§217a'-style prefixed targets match.
    m = para_re.search(text)
    if m:
        return f"§ {re.sub(r'\\s+', '-', m.group(1).strip())}"
    return ""


def _open_pair(out_path: Path):
    """Open uncompressed + gzipped file handles for parallel writing."""
    plain = out_path.open("w", encoding="utf-8")
    gz = gzip.open(str(out_path) + ".gz", "wt", encoding="utf-8")
    return plain, gz


def _close_pair(plain, gz):
    plain.close()
    gz.close()


def generate_amendment_acts_jsonl(db_path: str, output_path: str) -> int:
    """Write JSON Lines of amendment acts, newest first. Writes both .jsonl and .jsonl.gz."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT refid, title, short_title, date_in_force, date_in_force_resolved,
               date_published, ministry, changes_to, journal_number, misc_info,
               is_deferred, amendment_count
        {_ACTS_EXPORT_SOURCE}
        ORDER BY date_published DESC, date_in_force_resolved DESC, refid DESC
        """
    ).fetchall()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plain, gz = _open_pair(out)
    try:
        for r in rows:
            targets = [t.strip() for t in (r["changes_to"] or "").split(",") if t.strip()]
            obj = {
                "refid": r["refid"],
                "title": r["title"],
                "short_title": r["short_title"] or None,
                "ministry": r["ministry"] or None,
                "date_published": r["date_published"][:10] if r["date_published"] else None,
                "date_in_force": r["date_in_force"] or None,
                "date_in_force_resolved": r["date_in_force_resolved"] or None,
                "is_deferred": bool(r["is_deferred"]),
                "journal_number": r["journal_number"] or None,
                "amendment_count": r["amendment_count"],
                "targets": targets,
                "misc_info": r["misc_info"][:500] if r["misc_info"] else None,
            }
            line = json.dumps(obj, ensure_ascii=False) + "\n"
            plain.write(line)
            gz.write(line)
    finally:
        _close_pair(plain, gz)
    conn.close()
    return len(rows)


def generate_amendments_jsonl(db_path: str, output_path: str) -> int:
    """Write JSON Lines of paragraph-level amendments, newest first.

    Joined with amendment_acts so each row has the publish/in-force dates
    needed to filter by time without a second lookup.

    Writes both .jsonl and .jsonl.gz.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # amendments table may not exist on older snapshots
    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='amendments'"
    ).fetchone():
        print("  amendments table missing, skipping amendments.jsonl")
        conn.close()
        return 0

    rows = conn.execute(
        f"""
        SELECT a.id, a.act_refid, a.change_type, a.target, a.target_law,
               a.instruction, a.new_text,
               ac.title AS act_title, ac.short_title AS act_short_title,
               ac.ministry, ac.date_published, ac.date_in_force,
               ac.date_in_force_resolved, ac.journal_number
        {_AMENDMENTS_EXPORT_SOURCE}
        ORDER BY ac.date_published DESC, a.act_refid DESC, a.id ASC
        """
    ).fetchall()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    plain, gz = _open_pair(out)
    n = 0
    try:
        for r in rows:
            paragraph = _normalize_paragraph_ref(r["target"] or "", r["instruction"] or "")
            obj = {
                "act_refid": r["act_refid"],
                "act_title": r["act_short_title"] or r["act_title"],
                "target_law": r["target_law"],
                "target": r["target"] or None,
                "paragraph": paragraph or None,
                "change_type": r["change_type"] or None,
                "instruction": (r["instruction"] or "")[:200] or None,
                # new_text is the replacement paragraph wording. Capped at
                # 4000 chars to keep the file reasonable but big enough for
                # most full-paragraph replacements.
                "new_text": (r["new_text"] or "")[:4000] or None,
                "ministry": r["ministry"] or None,
                "date_published": r["date_published"][:10] if r["date_published"] else None,
                "date_in_force": r["date_in_force"] or None,
                "date_in_force_resolved": r["date_in_force_resolved"] or None,
                "journal_number": r["journal_number"] or None,
            }
            line = json.dumps(obj, ensure_ascii=False) + "\n"
            plain.write(line)
            gz.write(line)
            n += 1
    finally:
        _close_pair(plain, gz)
    conn.close()
    return n


def generate_manifests(db_path: str, output_dir: str) -> tuple[int, int]:
    """Generate both manifests. Returns (acts_count, amendments_count)."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    acts_n = generate_amendment_acts_jsonl(db_path, str(out / "amendment-acts.jsonl"))
    print(f"  Wrote amendment-acts.jsonl with {acts_n} rows")
    amendments_n = generate_amendments_jsonl(db_path, str(out / "amendments.jsonl"))
    print(f"  Wrote amendments.jsonl with {amendments_n} rows")
    generate_schemas(str(out))
    print(f"  Wrote schemas to {out}/schemas/")
    return acts_n, amendments_n


# JSON Schema definitions for the manifests. Inlined rather than read from a
# file so the schema is colocated with the producer code; if a field is added
# above, this must be updated here as well. Schema follows draft 2020-12.

_ACTS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://sondreskarsten.github.io/norwegian-laws/schemas/amendment-acts.schema.json",
    "title": "Lovtidend act (one row per published act)",
    "description": (
        "One published act from Norsk Lovtidend. Despite the file name, this "
        "table contains ALL Lovtidend publications, not just amendments — "
        "about 55% are actual endringslover that amend existing laws; the "
        "remaining ~45% are new standalone forskrifter, repeals, delegations, "
        "decisions, etc. To filter for acts that actually amend something, "
        "join on amendments.act_refid (see amendments.schema.json). Sourced "
        "from amendment_acts in the snapshot SQLite database, originally "
        "parsed from Lovdata XML."
    ),
    "type": "object",
    "required": ["refid", "title", "date_published"],
    "properties": {
        "refid": {
            "type": "string",
            "description": "Canonical Lovdata ID, e.g. 'lov/2024-06-21-42'.",
            "pattern": "^(lov|forskrift)/\\d{4}-\\d{2}-\\d{2}-\\d+$",
        },
        "title": {"type": "string", "description": "Full official title."},
        "short_title": {"type": ["string", "null"], "description": "Shorter title for display, often Norwegian abbreviation."},
        "ministry": {"type": ["string", "null"], "description": "Norwegian ministry that proposed the act."},
        "date_published": {
            "type": "string",
            "format": "date",
            "description": "Date the act was published in Norsk Lovtidend (YYYY-MM-DD).",
        },
        "date_in_force": {
            "type": ["string", "null"],
            "description": "Raw date_in_force field as published. May be a date or a textual description.",
        },
        "date_in_force_resolved": {
            "type": ["string", "null"],
            "format": "date",
            "description": "Best-effort YYYY-MM-DD resolution of date_in_force.",
        },
        "is_deferred": {"type": "boolean", "description": "Whether the act has a deferred entry-into-force."},
        "journal_number": {
            "type": ["string", "null"],
            "description": "Lovtidend journal number, e.g. '2024-0042'.",
        },
        "amendment_count": {
            "type": ["integer", "null"],
            "minimum": 0,
            "description": (
                "Number of paragraph-level amendments this act made. NOT the "
                "number of laws affected; for that, len(targets)."
            ),
        },
        "targets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of refids for laws/forskrifter that this act amends.",
        },
        "misc_info": {
            "type": ["string", "null"],
            "description": "Hjemmel text, truncated to 500 chars.",
        },
    },
}

_AMENDMENTS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://sondreskarsten.github.io/norwegian-laws/schemas/amendments.schema.json",
    "title": "Paragraph-level amendment (one row per amended paragraph)",
    "description": (
        "One paragraph-level amendment. For acts that touch multiple paragraphs "
        "of multiple laws, there are N rows. Sourced from joining the amendments "
        "and amendment_acts tables in the snapshot SQLite database."
    ),
    "type": "object",
    "required": ["act_refid", "target_law"],
    "properties": {
        "act_refid": {
            "type": "string",
            "description": (
                "Amending act refid; foreign key to amendment-acts.refid. "
                "Pattern allows pre-1970s acts that lack a numeric counter."
            ),
            "pattern": "^(lov|forskrift)/\\d{4}-\\d{2}-\\d{2}(-\\d+)?$",
        },
        "act_title": {"type": ["string", "null"], "description": "Short title of the amending act."},
        "target_law": {
            "type": "string",
            "description": (
                "Refid of the law/forskrift being amended. Pattern allows "
                "pre-1970s acts that lack a numeric counter."
            ),
            "pattern": "^(lov|forskrift)/\\d{4}-\\d{2}-\\d{2}(-\\d+)?$",
        },
        "target": {
            "type": ["string", "null"],
            "description": "Raw target reference, e.g. '§ 7-25' or 'kapittel 7'.",
        },
        "paragraph": {
            "type": ["string", "null"],
            "description": (
                "Normalized paragraph reference, e.g. '§ 7-25' or '§ 1-2a'. "
                "Null when the amendment is at chapter level or a letter that "
                "couldn't be canonicalized."
            ),
            "pattern": "^§ \\d+-\\d+[a-z]?$",
        },
        "change_type": {
            "type": ["string", "null"],
            "enum": ["change", "add", "remove", "repeal", "renumber", "move", "unknown", None],
            "description": (
                "Whether the amendment changed, added, removed, repealed, "
                "renumbered, or moved the paragraph. 'unknown' when Lovdata "
                "wording didn't fit any specific pattern."
            ),
        },
        "instruction": {
            "type": ["string", "null"],
            "description": "Lovdata's instruction text, e.g. '§ 7-25 skal lyde:'. Truncated to 200 chars.",
        },
        "new_text": {
            "type": ["string", "null"],
            "description": (
                "Replacement paragraph wording from Lovdata. Truncated to 4000 "
                "chars. Only populated when change_type is 'change' or 'add'."
            ),
        },
        "ministry": {"type": ["string", "null"]},
        "date_published": {"type": ["string", "null"], "format": "date"},
        "date_in_force": {"type": ["string", "null"]},
        "date_in_force_resolved": {"type": ["string", "null"], "format": "date"},
        "journal_number": {"type": ["string", "null"]},
    },
}


def generate_schemas(output_dir: str) -> None:
    """Write JSON Schema documents for both manifests.

    Files are placed at {output_dir}/schemas/{amendment-acts,amendments}.schema.json.
    The schemas are valid JSON Schema 2020-12 and can be linked to from the
    manifests via $schema (consumers do that lookup themselves; we just publish).
    """
    schemas_dir = Path(output_dir) / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    (schemas_dir / "amendment-acts.schema.json").write_text(
        json.dumps(_ACTS_SCHEMA, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (schemas_dir / "amendments.schema.json").write_text(
        json.dumps(_AMENDMENTS_SCHEMA, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "snapshot/amendments.db"
    out = sys.argv[2] if len(sys.argv) > 2 else "."
    generate_manifests(db, out)
