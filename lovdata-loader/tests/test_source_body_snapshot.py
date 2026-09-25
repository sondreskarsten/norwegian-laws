"""Explicit v5 capture keeps legacy receipt bytes and fails before publication."""
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest

from lovdata_loader.evidence import (EvidenceBundle, MEMBERS, OBSERVATIONS, canonical_json,
    file_sha256, validate_evidence, value_sha256)
from lovdata_loader.models import LawData, SOURCE_BODY_CONTENT_VERSION, SOURCE_BODY_FORMATTER_VERSION
from lovdata_loader.parser import parse_law
from lovdata_loader.source_body import SourceBodyError, canonical_bytes
from lovdata_loader.store import write_snapshot

FIXTURES = Path(__file__).parent / "fixtures" / "source_body"
MEMBERS_FIXTURE = json.loads((FIXTURES / "source-members.json").read_text(encoding="utf-8"))


def archive(path, members):
    with tarfile.open(path, "w:bz2") as target:
        for name, raw in members:
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            target.addfile(info, BytesIO(raw))
    return path


def build(tmp_path, capture=True):
    raw = (FIXTURES / "lov-1687-04-15.xml").read_bytes()
    path = archive(tmp_path / "source.tar.bz2", [("first.xml", raw), ("same-refid.xml", raw)])
    bundle = EvidenceBundle(capture_source_bodies=capture)
    laws = bundle.parse_archive(str(path), "laws")
    root = tmp_path / "snapshot"
    write_snapshot(str(root), laws, [], evidence=bundle)
    return root, laws, bundle, json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def test_explicit_v5_preserves_every_occurrence_and_binds_complete_model(tmp_path):
    root, laws, bundle, manifest = build(tmp_path)
    assert manifest["version"] == 5
    assert (manifest["content_version"], manifest["formatter_version"]) == (SOURCE_BODY_CONTENT_VERSION, SOURCE_BODY_FORMATTER_VERSION)
    assert manifest["law_count"] == 1 and manifest["duplicate_counts"]["laws"] == 1
    rows = [json.loads(line) for line in (root / MEMBERS).read_text(encoding="utf-8").splitlines()]
    assert len({row["source_occurrence_id"] for row in rows}) == 2
    assert [row["selected"] for row in rows] == [False, True]
    assert [row["parsed_model_sha256"] for row in rows] == [value_sha256(law.to_dict()) for law in laws]
    for law in laws:
        assert LawData.from_dict(law.to_dict()).to_dict() == law.to_dict()
    observation = json.loads((root / OBSERVATIONS).read_text(encoding="utf-8"))
    assert set(observation["parser_identity"]["source_files"]) == {"parser.py", "models.py", "evidence.py", "source_body.py"}
    validate_evidence(root, manifest)


def test_default_v4_keeps_exact_legacy_serialization_and_convenience_fields(tmp_path):
    root, laws, bundle, manifest = build(tmp_path, capture=False)
    assert manifest["version"] == 4
    assert "source_body" not in laws[0].to_dict()
    assert "source_body" not in json.loads(next((root / "laws").glob("*.json")).read_text(encoding="utf-8"))
    observation = json.loads((root / OBSERVATIONS).read_text(encoding="utf-8"))
    assert set(observation["parser_identity"]["source_files"]) == {"parser.py", "models.py", "evidence.py"}
    validate_evidence(root, manifest)
    for row in MEMBERS_FIXTURE:
        raw = (FIXTURES / row["retained_file"]).read_bytes()
        old = parse_law(raw).to_dict()
        new = parse_law(raw, capture_source_body=True).to_dict()
        assert new.pop("source_body")
        assert new == old
        assert LawData.from_dict(old).to_json() == json.dumps(old, ensure_ascii=False, indent=1)


def test_source_bodies_cannot_silently_enter_old_or_mixed_snapshot(tmp_path):
    raw = (FIXTURES / "lov-1687-04-15.xml").read_bytes()
    captured = parse_law(raw, capture_source_body=True)
    root = tmp_path / "snapshot"
    for evidence, laws in [(None, [captured]), (EvidenceBundle(), [captured]),
                           (EvidenceBundle(capture_source_bodies=True), [captured, parse_law(raw)])]:
        with pytest.raises(ValueError, match="v5 evidence bundle"):
            write_snapshot(str(root), laws, [], evidence=evidence)
        assert not root.exists()
    malformed = captured.to_dict()
    malformed["source_body"] = None
    with pytest.raises(SourceBodyError):
        LawData.from_dict(malformed)


def test_capture_failure_has_no_legacy_fallback(tmp_path):
    raw = (FIXTURES / "lov-1687-04-15.xml").read_bytes().replace(b'</main>', b'</article></main>')
    path = archive(tmp_path / "bad.tar.bz2", [("bad.xml", raw)])
    assert parse_law(raw) is not None
    with pytest.raises(SourceBodyError, match="malformed_source"):
        EvidenceBundle(capture_source_bodies=True).parse_archive(str(path), "laws")


def test_rehashed_source_tree_corruption_still_fails_raw_comparison(tmp_path):
    root, laws, bundle, manifest = build(tmp_path)
    target = next((root / "laws").glob("*.json"))
    model = json.loads(target.read_text(encoding="utf-8"))
    body = model["source_body"]
    body["root"]["children"].append("Invented source text")
    body["body_sha256"] = hashlib.sha256(canonical_bytes(body["root"])).hexdigest()
    body["semantic_sha256"] = hashlib.sha256(canonical_bytes([body["contract"], body["context"], body["root"]])).hexdigest()
    target.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    rows = [json.loads(line) for line in (root / MEMBERS).read_text(encoding="utf-8").splitlines()]
    rows[-1]["parsed_model_sha256"] = value_sha256(model)
    rows[-1]["selected_output_sha256"] = file_sha256(target)
    (root / MEMBERS).write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
    manifest["artifact_hashes"][target.relative_to(root).as_posix()] = file_sha256(target)
    manifest["artifact_hashes"][MEMBERS] = file_sha256(root / MEMBERS)
    with pytest.raises(ValueError, match="source_model_mismatch"):
        validate_evidence(root, manifest)


def test_changed_captured_model_cannot_replace_an_existing_snapshot(tmp_path):
    root, laws, bundle, manifest = build(tmp_path)
    original = (root / "manifest.json").read_bytes()
    laws[-1].source_body["context"]["body_attributes"] = {"lang": "nn"}
    with pytest.raises(SourceBodyError):
        write_snapshot(str(root), laws, [], evidence=bundle)
    assert (root / "manifest.json").read_bytes() == original
