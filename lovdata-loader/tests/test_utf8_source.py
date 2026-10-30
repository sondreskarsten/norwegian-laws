"""Real valid UTF-8 must never be routed through environment charset guesses."""
from dataclasses import asdict
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tarfile

import pytest

from lovdata_loader.evidence import EvidenceBundle, PARSED_ACTS, value_sha256
from lovdata_loader.parser import parse_law, parse_lovtidend_file
from lovdata_loader.store import write_snapshot

FIXTURES = Path(__file__).parent / "fixtures"


def test_real_amendment_bytes_bom_and_text_have_identical_correct_norwegian_text():
    raw = (FIXTURES / "source_utf8" / "nl-20161216-091.xml").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "6562e740012480dfa7299f06c0657550bf448f234fd0e203ddc0bf3b7909ae49"
    outputs = [asdict(parse_lovtidend_file(value, "nl-20161216-091.xml"))
               for value in (raw, b"\xef\xbb\xbf" + raw, raw.decode("utf-8"))]
    assert outputs[0] == outputs[1] == outputs[2]
    # Correct paragraph targets are included in this parsed-model fingerprint.
    # The act's first change is a single sentence that is both preamble and
    # instruction ('I lov 7. desember 1956 nr. 1 ... skal § 7 første ledd
    # tredje og fjerde punktum lyde:'); it was skipped before the embedded
    # preamble rule, which moved the fingerprint from c0a135c7… to 6694187e….
    # Whole-document repeals, list wording after 'lyde:' and the embedded
    # 'skal ny § … lyde' form (stress test D5) moved it again to
    # 562903c4…..
    assert outputs[0]["amendments"][0]["target_law"] == "lov/1956-12-07-1"
    assert outputs[0]["amendments"][0]["target"] == "§ 7"
    assert outputs[0]["amendments"][0]["new_text"].startswith("Taushetsplikten etter denne bestemmelse")
    assert outputs[0]["amendments"][1]["target"] == "§ 12"
    assert value_sha256(outputs[0]) == "562903c4e498954054d6c2bc711e907de871fd25cf28c61da66ee1a4f91e5e5f"
    assert outputs[0]["amendments"][1]["instruction"] == "§ 12 annet ledd første punktum skal lyde:"
    assert "foregående ledd" in outputs[0]["amendments"][1]["new_text"]


def test_law_bytes_bom_and_text_match_and_capture_keeps_original_raw_identity():
    raw = (FIXTURES / "source_body" / "lov-1687-04-15.xml").read_bytes()
    outputs = [parse_law(value).to_dict() for value in (raw, b"\xef\xbb\xbf" + raw, raw.decode("utf-8"))]
    assert outputs[0] == outputs[1] == outputs[2]
    with_bom = b"\xef\xbb\xbf" + raw
    captured = parse_law(with_bom, capture_source_body=True).source_body
    assert captured["member_sha256"] == hashlib.sha256(with_bom).hexdigest()


def test_invalid_utf8_fails_in_both_entrypoints_instead_of_guessing():
    raw = b'<html><body><main>\xff</main></body></html>'
    with pytest.raises(UnicodeDecodeError):
        parse_law(raw)
    with pytest.raises(UnicodeDecodeError):
        parse_lovtidend_file(raw, "bad.xml")


def test_current_default_v4_and_capture_v5_export_identical_real_amendments(tmp_path):
    raw = (FIXTURES / "source_utf8" / "nl-20161216-091.xml").read_bytes()
    source = tmp_path / "amendments.tar.bz2"
    with tarfile.open(source, "w:bz2") as stream:
        member = tarfile.TarInfo("nl-20161216-091.xml")
        member.size = len(raw)
        stream.addfile(member, BytesIO(raw))
    outputs = []
    for capture, version in ((False, 4), (True, 5)):
        bundle = EvidenceBundle(capture_source_bodies=capture)
        acts = bundle.parse_archive(str(source), "amendment_acts")
        root = tmp_path / str(version)
        write_snapshot(str(root), [], acts, evidence=bundle)
        assert json.loads((root / "manifest.json").read_text())["version"] == version
        assert bundle.members[0]["parsed_model_sha256"] == "562903c4e498954054d6c2bc711e907de871fd25cf28c61da66ee1a4f91e5e5f"
        outputs.append([(root / name).read_bytes() for name in (PARSED_ACTS, "amendments.db")])
    assert outputs[0] == outputs[1]
