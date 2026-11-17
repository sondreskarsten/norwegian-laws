"""A language variant sharing a refid is published from the snapshot's own raw archive."""
import json
from pathlib import Path

import pytest

from lovdata_loader.evidence import EvidenceBundle
from lovdata_loader.language_variants import language_variants
from lovdata_loader.second_stream import compare_snapshot
from lovdata_loader.store import write_snapshot
from lovdata_publisher.formatter import format_all_laws
from lovdata_publisher.per_law_pages import lovdata_code
from lovdata_publisher.reader_exits import _corpus_path

from test_source_evidence import FIXTURES, archive


def snapshot(tmp_path, names=("nl/nl-18140517-000-nn.xml", "nl/nl-18140517-000.xml")):
    bokmal = (FIXTURES / "fixture_grunnloven.xml").read_bytes()
    nynorsk = bokmal.replace(b"Kongeriket Norges Grunnlov", b"Kongeriket Noregs grunnlov").replace(b'lang="nb"', b'lang="nn"')
    assert nynorsk != bokmal and b'lang="nn"' in nynorsk
    laws = archive(tmp_path / "laws.tar.bz2", [(names[0], nynorsk), (names[1], bokmal)])
    evidence = EvidenceBundle()
    root = tmp_path / "snapshot"
    write_snapshot(str(root), evidence.parse_archive(str(laws), "laws"), [], evidence=evidence)
    return root


def test_variant_is_read_back_and_published_under_its_own_refid(tmp_path):
    root = snapshot(tmp_path)
    before = sorted(path.name for path in root.rglob("*") if path.is_file())
    variants = language_variants(str(root))
    assert [item["document"]["refid"] for item in variants] == ["lov/1814-05-17-nn"]
    assert variants[0]["document"]["title"] == "Kongeriket Noregs grunnlov"

    written = format_all_laws(str(root), str(tmp_path / "out"))
    assert written == {"lov/1814-05-17": "lover/lov-1814-05-17.md", "lov/1814-05-17-nn": "lover/lov-1814-05-17-nn.md"}
    nynorsk = (tmp_path / "out" / "lover" / "lov-1814-05-17-nn.md").read_text(encoding="utf-8")
    bokmal = (tmp_path / "out" / "lover" / "lov-1814-05-17.md").read_text(encoding="utf-8")
    assert 'refid: "lov/1814-05-17-nn"' in nynorsk and "Kongeriket Noregs grunnlov" in nynorsk
    assert 'eli: "/eli/lov/1814/05/17/0"' in nynorsk and 'eli: "/eli/lov/1814/05/17/0"' in bokmal
    assert sorted(path.name for path in root.rglob("*") if path.is_file()) == before

    format_all_laws(str(root), str(tmp_path / "out"))
    assert (tmp_path / "out" / "lover" / "lov-1814-05-17-nn.md").read_text(encoding="utf-8") == nynorsk

    report = compare_snapshot(str(root))
    assert report["documents"] == 2 and report["unpublished"] == [] and report["header_mismatches"] == 0
    assert [item["differences"] for item in report["variant_structure"]] == [[]]
    assert report["variant_structure"][0]["nodes"][0] == report["variant_structure"][0]["nodes"][1] > 0


def test_variant_with_a_missing_paragraph_is_reported(tmp_path):
    from lovdata_loader.second_stream import shape_differences, source_shape
    bokmal = (FIXTURES / "fixture_grunnloven.xml").read_bytes()
    start = bokmal.index(b'<article class="legalArticle"')
    end = bokmal.index(b'<article class="legalArticle"', start + 1)
    shorter = bokmal[:start] + bokmal[end:]
    differences = shape_differences(source_shape(bokmal), source_shape(shorter))
    assert differences and differences[-1][1][0] == "length"


def test_unsuffixed_duplicate_stays_unpublished_and_is_reported(tmp_path):
    root = snapshot(tmp_path, names=("nl/a.xml", "nl/b.xml"))
    assert language_variants(str(root)) == []
    assert [item["member_path"] for item in compare_snapshot(str(root))["unpublished"]] == ["nl/a.xml"]


def test_variant_bytes_must_match_the_member_inventory(tmp_path):
    root = snapshot(tmp_path)
    members = root / "source-members.jsonl"
    rows = [json.loads(line) for line in members.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        if row["member_path"].endswith("-nn.xml"):
            row["parsed_model_sha256"] = "0" * 64
    members.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="member inventory"):
        language_variants(str(root))


def test_identifiers_accept_the_variant_suffix():
    assert lovdata_code("lov/1814-05-17-nn") == "LOV-1814-05-17"
    assert _corpus_path("lover/lov-1814-05-17-nn.md") == ("laws", "lov/1814-05-17-nn")


def test_reader_page_links_markers_and_keeps_heading_ids():
    from lovdata_publisher.per_law_pages import build_toc_html, render_markdown_body
    body = ('#### § 5.<sup data-fn="1">1</sup> (skade)\n\nTekst<sup data-fn="1">1</sup> her.\n\n'
            '*<sup data-fn-note="1">1</sup> Jf. direktiv.*\n')
    html = render_markdown_body(body)
    clean = render_markdown_body("#### § 5. (skade)\n")
    assert 'id="5-skade"' in html and 'id="5-skade"' in clean
    assert html.count('<sup class="fotnoteref"><a href="#fotnote_1"') == 2 and html.count('id="fotnoteref_1"') == 1
    assert '<a class="fotnote-nummer" href="#fotnoteref_1" id="fotnote_1">1</a>' in html
    assert "" not in html
    assert ">§ 5. (skade)<" in build_toc_html(html)


def test_marker_survives_html_escaping_in_literal_lists():
    from lovdata_publisher.formatter import _escape_keeping_markers
    text = 'direktiv 91/321/EØF ,<sup data-fn="40">1</sup> & <b>'
    assert _escape_keeping_markers(text) == 'direktiv 91/321/EØF ,<sup data-fn="40">1</sup> &amp; &lt;b&gt;'
