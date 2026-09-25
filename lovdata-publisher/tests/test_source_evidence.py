"""Raw replay and the complete parsed model must survive duplicate selection."""
from dataclasses import asdict
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest

from lovdata_loader.evidence import (EvidenceBundle, MEMBERS, OBSERVATIONS, PARSED_ACTS,
                                    file_sha256)
from lovdata_loader.store import write_snapshot
from lovdata_publisher.snapshot import validate_snapshot
from lovdata_publisher.manifests import generate_amendment_acts_jsonl, generate_amendments_jsonl


FIXTURES = Path(__file__).resolve().parents[2] / "lovdata-loader" / "tests" / "fixtures"


def archive(path, rows):
    with tarfile.open(path, "w:bz2") as out:
        for name, content in rows:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            out.addfile(info, BytesIO(content))
    return path


def sources(tmp_path):
    law = (FIXTURES / "fixture_grunnloven.xml").read_bytes()
    act = (FIXTURES / "fixture_lovtidend.xml").read_text(encoding="utf-8")
    unknown = '<article class="change"><article class="defaultP">Uavklart instruks</article><article class="legalP">' + "Æøå hele teksten. " * 500 + '</article></article>'
    act = act.replace("</main>", unknown + "</main>").encode("utf-8")
    laws = archive(tmp_path / "laws.tar.bz2", [("nested/same.xml", law), ("nested/same.xml", law)])
    acts = archive(tmp_path / "acts.tar.bz2", [("dir/nl-same.xml", act), ("dir/nl-same.xml", act),
        ("other.xml", b"<html/>"), ("nl-missing.xml", b"<html/>"), ("README.txt", b"raw evidence")])
    return laws, acts


def build(root, inputs):
    evidence = EvidenceBundle()
    laws = evidence.parse_archive(str(inputs[0]), "laws")
    acts = evidence.parse_archive(str(inputs[1]), "amendment_acts")
    write_snapshot(str(root), laws, acts, evidence=evidence)
    return evidence, validate_snapshot(root)


def rows(root, name):
    return [json.loads(line) for line in (root / name).read_text(encoding="utf-8").splitlines()]


def test_raw_replay_keeps_every_occurrence_and_complete_parsed_model(tmp_path):
    root = tmp_path / "snapshot"
    evidence, manifest = build(root, sources(tmp_path))
    assert manifest["version"] == 4
    assert manifest["duplicate_counts"] == {"laws": 1, "forskrifter": 0, "amendment_acts": 1}
    exported = rows(root, PARSED_ACTS)
    assert [row["record"] for row in exported] == [asdict(act) for act in evidence.records["amendment_acts"]]
    assert exported[0]["record"]["date_published"] == "2026-01-23 11:40"
    assert exported[0]["record"]["date_in_force"] == "Kongen bestemmer"
    assert len(exported[0]["record"]["amendments"][-1]["new_text"]) > 5000
    assert exported[0]["amendment_occurrences"][-1]["target_status"] == "unresolved"
    assert exported[0]["amendment_occurrences"][-1]["operation_status"] == "unresolved"
    assert exported[0]["legal_valid_time"] == {"status": "unresolved", "date": None}
    inventory = rows(root, MEMBERS)
    assert [row["selected"] for row in inventory[:4]] == [False, True, False, True]
    assert len({row["source_occurrence_id"] for row in inventory if row["parse_status"] == "parsed"}) == 4
    assert {row["parse_status"] for row in inventory} == {"parsed", "excluded_prefix", "excluded_non_xml", "unresolved_missing_refid"}
    observations = json.loads((root / OBSERVATIONS).read_text())
    assert observations["historical_knowledge_time_status"] == "unknown"
    assert all(row["retrieved_at"] is None for row in observations["archives"])

    # Replay retained bytes, not mutable original paths. All deterministic model
    # and membership outputs agree; local observation timestamps intentionally differ.
    replay_sources = tuple(root / row["raw_path"] for row in observations["archives"])
    replay = tmp_path / "replay"
    build(replay, replay_sources)
    for name in (MEMBERS, PARSED_ACTS, "amendments.db"):
        assert (root / name).read_bytes() == (replay / name).read_bytes()
    legacy = tmp_path / "legacy"
    write_snapshot(str(legacy), evidence.records["laws"], evidence.records["amendment_acts"])
    for generate, name in ((generate_amendment_acts_jsonl, "acts.jsonl"), (generate_amendments_jsonl, "amendments.jsonl")):
        generate(str(root / "amendments.db"), str(root / name))
        generate(str(legacy / "amendments.db"), str(legacy / name))
        assert (root / name).read_bytes() == (legacy / name).read_bytes()


@pytest.mark.parametrize("damage", ["member_hash", "omitted_export", "raw_bytes", "selected_binding"])
def test_validation_rejects_incomplete_or_unbound_evidence(tmp_path, damage):
    root = tmp_path / "snapshot"
    _, manifest = build(root, sources(tmp_path))
    name = MEMBERS
    if damage == "raw_bytes":
        name = next(path for path in manifest["artifact_hashes"] if path.startswith("raw/"))
        with (root / name).open("r+b") as stream:
            stream.write(b"bad")
    elif damage == "omitted_export":
        name = PARSED_ACTS
        (root / name).write_text(json.dumps(rows(root, name)[0]) + "\n", encoding="utf-8")
    else:
        inventory = rows(root, MEMBERS)
        inventory[0 if damage == "member_hash" else 1]["member_sha256" if damage == "member_hash" else "selected_output_sha256"] = "0" * 64
        (root / name).write_text("".join(json.dumps(row) + "\n" for row in inventory), encoding="utf-8")
    # Rehashing a malformed inventory cannot make the semantic contract valid.
    if damage != "raw_bytes":
        manifest["artifact_hashes"][name] = file_sha256(root / name)
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        validate_snapshot(root)


def test_changed_source_or_parsed_model_cannot_be_promoted(tmp_path):
    inputs = sources(tmp_path)
    evidence = EvidenceBundle()
    laws = evidence.parse_archive(str(inputs[0]), "laws")
    original = inputs[0].read_bytes()
    inputs[0].write_bytes(b"replaced input")
    root = tmp_path / "snapshot"
    with pytest.raises(ValueError, match="Retained raw archive"):
        write_snapshot(str(root), laws, [], evidence=evidence)
    assert not root.exists()
    inputs[0].write_bytes(original)
    laws[0].title = "changed after capture"
    with pytest.raises(ValueError, match="changed after source capture"):
        write_snapshot(str(root), laws, [], evidence=evidence)
    assert not root.exists()
