"""Tests for site_index.py and verify_links.py — the systemic dead-link net."""
from pathlib import Path

from lovdata_publisher.site_index import SiteIndex, refid_to_stem, stem_to_refid
from lovdata_publisher.verify_links import verify_site


def _corpus(tmp_path):
    (tmp_path / "lover").mkdir()
    (tmp_path / "forskrifter").mkdir()
    (tmp_path / "lover" / "lov-1998-07-17-56.md").write_text("x", encoding="utf-8")
    (tmp_path / "forskrifter" / "forskrift-2004-01-19-298.md").write_text("x", encoding="utf-8")
    (tmp_path / "lover" / "README.md").write_text("x", encoding="utf-8")


def test_stem_roundtrip():
    assert stem_to_refid(refid_to_stem("lov/1998-07-17-56")) == "lov/1998-07-17-56"
    assert stem_to_refid(refid_to_stem("forskrift/2004-01-19-298")) == "forskrift/2004-01-19-298"


def test_build_and_doc_page(tmp_path):
    _corpus(tmp_path)
    idx = SiteIndex.build(str(tmp_path))
    assert idx.corpus == {"lov/1998-07-17-56", "forskrift/2004-01-19-298"}
    assert idx.doc_page("lov/1998-07-17-56") == "lover/lov-1998-07-17-56.html"
    assert idx.doc_page("forskrift/2004-01-19-298") == "forskrifter/forskrift-2004-01-19-298.html"
    assert idx.doc_page("lov/1981-05-29-38") is None


def test_manifest_attachment_and_fallbacks(tmp_path):
    _corpus(tmp_path)
    idx = SiteIndex.build(str(tmp_path))
    idx.attach_historie({"lov/1998-07-17-56": "historie/regnskapsloven.html"})
    idx.attach_feeds({
        "laws": {"lov/1998-07-17-56": {"path": "feeds/lov-1998-07-17-56.xml"}},
        "topics": {"Skatterett": {"path": "feeds/topic-skatterett.xml"}},
        "ministries": {"Finansdepartementet": {"path": "feeds/dept-finansdepartementet.xml"}},
    })
    idx.attach_paragraphs({"lov/1998-07-17-56": {"7-25"}})

    assert idx.historie_page("lov/1998-07-17-56") == "historie/regnskapsloven.html"
    assert idx.historie_page("lov/1981-05-29-38") is None
    assert idx.feed("lov/1998-07-17-56") == "feeds/lov-1998-07-17-56.xml"
    assert idx.ministry_feed("Landbruksdepartementet") is None
    assert idx.para_page("lov/1998-07-17-56", "7-25").endswith("para-7-25.html")
    assert idx.para_page("lov/1998-07-17-56", "9-9") is None
    assert idx.lovdata_archive_url("lov/1981-05-29-38") == "https://lovdata.no/dokument/NLO/lov/1981-05-29-38"
    assert idx.lovdata_archive_url("forskrift/1960-06-02-1") == "https://lovdata.no/dokument/SFO/forskrift/1960-06-02-1"
    assert idx.lovdata_act_url("lov/2025-06-20-102") == "https://lovdata.no/dokument/LTI/lov/2025-06-20-102"


def test_link_rendering():
    idx = SiteIndex()
    assert idx.link("lover/x.html", "Tittel <a>") == '<a href="lover/x.html">Tittel &lt;a&gt;</a>'
    assert idx.link("lover/x.html", "T", base="../") == '<a href="../lover/x.html">T</a>'
    assert idx.link(None, "T", fallback_url="https://example.com") == '<a href="https://example.com">T</a>'
    assert idx.link(None, "Bare tekst") == "Bare tekst"


def _site(tmp_path):
    site = tmp_path / "_site"
    (site / "lover").mkdir(parents=True)
    (site / "book").mkdir()
    (site / "lover" / "lov-1.html").write_text(
        '<a href="../book/ok.html">ok</a> <a href="https://ext.example/x">ext</a> '
        '<a href="#frag">frag</a> <a href="mailto:a@b">m</a>', encoding="utf-8")
    (site / "book" / "ok.html").write_text('<a href="../lover/lov-1.html">back</a>', encoding="utf-8")
    (site / "index.html").write_text('<a href="/norwegian-laws/book/ok.html">abs</a>', encoding="utf-8")
    return site


def test_verify_site_passes_on_clean_tree(tmp_path):
    site = _site(tmp_path)
    assert verify_site(str(site)) == []


def test_verify_site_catches_dead_and_escaping_refs(tmp_path):
    site = _site(tmp_path)
    (site / "book" / "bad.html").write_text(
        '<a href="../lover/lov-missing.html">dead</a> <a href="../../etc/passwd">esc</a>',
        encoding="utf-8")
    failures = verify_site(str(site))
    assert any("lov-missing.html" in f for f in failures)
    assert any("escapes site root" in f for f in failures)
    assert len(failures) == 2


def test_verify_site_checks_feeds_and_sitemap(tmp_path):
    site = _site(tmp_path)
    (site / "feeds").mkdir()
    (site / "feeds" / "a.xml").write_text(
        '<link href="https://sondreskarsten.github.io/norwegian-laws/lover/lov-1.html"/>'
        '<link href="https://sondreskarsten.github.io/norwegian-laws/lover/gone.html"/>',
        encoding="utf-8")
    (site / "sitemap.xml").write_text(
        "<urlset><url><loc>https://sondreskarsten.github.io/norwegian-laws/book/ok.html</loc></url>"
        "<url><loc>https://sondreskarsten.github.io/norwegian-laws/nope.html</loc></url></urlset>",
        encoding="utf-8")
    failures = verify_site(str(site))
    assert any("gone.html" in f for f in failures)
    assert any("nope.html" in f for f in failures)
    assert len(failures) == 2
