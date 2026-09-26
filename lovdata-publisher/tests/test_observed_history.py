"""Consume a real local Git reader export; refuse changed or invented payloads."""
from pathlib import Path
import hashlib
import json
import shutil

import pytest

from lovdata_publisher.observed_history import generate_observed_history, validate_export
from lovdata_publisher.site_index import SiteIndex

FIXTURE = Path(__file__).parent / "fixtures/observed_history"


def test_reader_keeps_exact_published_html_and_registers_links(tmp_path):
    index, documents, files = validate_export(FIXTURE)
    site = tmp_path / "site"
    links = SiteIndex({"lov/2024-01-01-1"})
    generated = generate_observed_history(FIXTURE, site, titles={"lov/2024-01-01-1": "Title <with markup>"}, site_index=links)
    assert links.observed == generated
    assert len(generated) == 2
    for name in files:
        assert (site / "observasjoner/data" / name).read_bytes() == (FIXTURE / name).read_bytes()
    page = (site / generated["lov/2024-01-01-1"]).read_text(encoding="utf-8")
    assert "Title &lt;with markup&gt;" in page
    assert '../lover/lov-2024-01-01-1.html' in page
    assert 'sandbox="allow-same-origin"' in page and 'allow-scripts' not in page
    assert 'product=' in page and 'Alle bevarte utgaver' in page
    rejected = documents["lov/2024-01-01-2"]
    assert all(v["html_path"] is None and v["status"] == "rejected" for v in rejected["versions"])
    assert index["documents"]["lov/2024-01-01-1"]["qualified_versions"] == 2


def test_changed_html_and_metadata_are_rejected_before_site_output(tmp_path):
    export = tmp_path / "export"
    shutil.copytree(FIXTURE, export)
    body = next((export / "bodies").glob("*.html"))
    original = body.read_bytes()
    body.write_bytes(original + b"changed")
    with pytest.raises(ValueError, match="HTML bytes changed"):
        generate_observed_history(export, tmp_path / "site")
    assert not (tmp_path / "site/observasjoner").exists()
    body.write_bytes(original)
    meta = next((export / "documents").glob("*.json"))
    meta.write_bytes(meta.read_bytes() + b" ")
    with pytest.raises(ValueError, match="metadata bytes changed"):
        validate_export(export)


def test_export_cannot_promote_rejected_text_or_claim_legal_dates(tmp_path):
    export = tmp_path / "export"
    shutil.copytree(FIXTURE, export)
    index = json.loads((export / "index.json").read_bytes())
    pointer = index["documents"]["lov/2024-01-01-2"]
    path = export / pointer["path"]
    document = json.loads(path.read_bytes())
    document["versions"][0]["html_path"] = next((export / "bodies").glob("*.html")).relative_to(export).as_posix()
    data = json.dumps(document).encode()
    path.write_bytes(data)
    pointer["metadata_sha256"] = hashlib.sha256(data).hexdigest()
    (export / "index.json").write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="Rejected version unexpectedly"):
        validate_export(export)
    index["legal_valid_time"]["from"] = "2020-01-01"
    (export / "index.json").write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="export scope"):
        validate_export(export)
