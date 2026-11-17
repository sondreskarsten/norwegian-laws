"""Language variants that share a refid with the selected document.

The consolidated archive holds the Grunnlov twice under refid lov/1814-05-17:
nl-18140517-000.xml (bokmål) and nl-18140517-000-nn.xml (nynorsk). The snapshot
selects one document per refid and keeps the other only in the member
inventory. This module reads such a member back from the snapshot's own raw
archive, checks it against the inventory, and returns its parsed model under
the refid Lovdata uses for it, lov/1814-05-17-nn. The snapshot and its evidence
are not changed.
"""
import hashlib
import json
import tarfile
from pathlib import Path

from .evidence import _record_dict, value_sha256
from .parser import parse_law

VARIANT_SUFFIX = "-nn"
SOURCE_BODY_CONTENT = "ordered-source-document-body-v1"


def base_refid(refid: str) -> str:
    return refid.removesuffix(VARIANT_SUFFIX)


def variant_rows(snapshot_dir: str = "snapshot") -> list[dict]:
    rows = []
    if not (Path(snapshot_dir) / "source-members.jsonl").is_file():
        return rows
    with (Path(snapshot_dir) / "source-members.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["role"] in ("laws", "forskrifter") and row["parse_status"] == "parsed":
                rows.append(row)
    selected = {(row["role"], row["refid"]) for row in rows if row["selected"]}
    return [row for row in rows
            if not row["selected"] and Path(row["member_path"]).stem.endswith(VARIANT_SUFFIX)
            and (row["role"], row["refid"]) in selected]


def language_variants(snapshot_dir: str = "snapshot") -> list[dict]:
    root = Path(snapshot_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    capture = manifest.get("content_version") == SOURCE_BODY_CONTENT
    documents = []
    for row in variant_rows(snapshot_dir):
        with tarfile.open(root / "raw" / f"{row['archive_sha256']}.tar.bz2", "r:bz2") as archive:
            member = archive.getmembers()[row["member_ordinal"]]
            raw = archive.extractfile(member).read()
        if member.name != row["member_path"] or hashlib.sha256(raw).hexdigest() != row["member_sha256"]:
            raise ValueError(f"Language variant differs from the member inventory: {row['member_path']}")
        record = parse_law(raw, capture_source_body=capture)
        if record is None or value_sha256(_record_dict(record)) != row["parsed_model_sha256"]:
            raise ValueError(f"Language variant model differs from the member inventory: {row['member_path']}")
        document = _record_dict(record)
        document["refid"] = record.refid + VARIANT_SUFFIX
        documents.append({"role": row["role"], "member_path": row["member_path"], "raw": raw, "document": document})
    return documents
