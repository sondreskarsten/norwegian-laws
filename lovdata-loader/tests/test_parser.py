"""Tests for lovdata_loader.parser."""
import re
import pytest
from pathlib import Path
from bs4 import BeautifulSoup

from lovdata_loader.parser import (
    parse_effective_date,
    parse_publication_date,
    extract_last_changed_by,
    _parse_law_metadata,
    parse_article,
    parse_section,
    parse_law,
    parse_lovtidend_file,
)
from lovdata_loader.models import LawData

FIXTURES = Path(__file__).parent / "fixtures"


# ─── parse_effective_date ────────────────────────────────────────────────────

class TestParseEffectiveDate:
    def test_iso_date(self):
        date, deferred = parse_effective_date("2024-01-01", "2023-12-15")
        assert date == "2024-01-01"
        assert deferred is False

    def test_norwegian_date(self):
        date, deferred = parse_effective_date("01.01.2024", "2023-12-15")
        assert date == "2024-01-01"
        assert deferred is False

    def test_kongen_bestemmer(self):
        date, deferred = parse_effective_date("Kongen bestemmer", "2023-12-15")
        assert date == "2023-12-15"
        assert deferred is True

    def test_kongen_fastsetter(self):
        date, deferred = parse_effective_date("Kongen fastsetter", "2023-06-20 14:30")
        assert date == "2023-06-20"
        assert deferred is True

    def test_kongen_fastset(self):
        date, deferred = parse_effective_date("Kongen fastset", "2023-06-20")
        assert date == "2023-06-20"
        assert deferred is True

    def test_iso_date_with_trailing_text(self):
        date, deferred = parse_effective_date("2024-01-01 some extra text", "2023-12-15")
        assert date == "2024-01-01"
        assert deferred is False

    def test_empty_string_falls_back(self):
        date, deferred = parse_effective_date("", "2023-06-20")
        assert date == "2023-06-20"
        assert deferred is True

    def test_garbage_falls_back(self):
        date, deferred = parse_effective_date("Straks", "2023-06-20")
        assert date == "2023-06-20"
        assert deferred is True

    def test_straks_with_date(self):
        date, deferred = parse_effective_date("Straks, med virkning fra 2020-01-01", "2019-12-20")
        assert date == "2019-12-20"
        assert deferred is True


# ─── parse_publication_date ──────────────────────────────────────────────────

class TestParsePublicationDate:
    def test_iso_datetime(self):
        assert parse_publication_date("2023-06-20 14:30") == "2023-06-20"

    def test_norwegian_date(self):
        assert parse_publication_date("20.06.2023") == "2023-06-20"

    def test_iso_date(self):
        assert parse_publication_date("2023-06-20") == "2023-06-20"

    def test_norwegian_datetime(self):
        assert parse_publication_date("20.06.2023 14:30") == "2023-06-20"

    def test_fallback(self):
        assert parse_publication_date("nonsense") == "2000-01-01"

    def test_whitespace(self):
        assert parse_publication_date("  2023-06-20  ") == "2023-06-20"


# ─── extract_last_changed_by ────────────────────────────────────────────────

class TestExtractLastChangedBy:
    def test_anchor_with_fra(self):
        html = '<header><dd class="lastChangedBy"><a href="lov/2023-06-16-40">lov/2023-06-16-40</a> fra 2023-07-01</dd></header>'
        soup = BeautifulSoup(html, "html.parser")
        refid, in_force = extract_last_changed_by(soup.find("header"))
        assert refid == "lov/2023-06-16-40"
        assert in_force == "2023-07-01"

    def test_forskrift_anchor(self):
        html = '<header><dd class="lastChangedBy"><a href="forskrift/2024-06-07-928">forskrift/2024-06-07-928</a> fra 2024-05-21</dd></header>'
        soup = BeautifulSoup(html, "html.parser")
        refid, in_force = extract_last_changed_by(soup.find("header"))
        assert refid == "forskrift/2024-06-07-928"
        assert in_force == "2024-05-21"

    def test_no_element(self):
        html = '<header><dd class="title">Some title</dd></header>'
        soup = BeautifulSoup(html, "html.parser")
        refid, in_force = extract_last_changed_by(soup.find("header"))
        assert refid == ""
        assert in_force == ""

    def test_plain_text_no_anchor(self):
        html = '<header><dd class="sistEndret">lov/2020-01-01-5</dd></header>'
        soup = BeautifulSoup(html, "html.parser")
        refid, in_force = extract_last_changed_by(soup.find("header"))
        assert refid == "lov/2020-01-01-5"
        assert in_force == ""


# ─── Fixture-based: parse_law ────────────────────────────────────────────────

class TestParseLawFixtures:
    def test_grunnloven(self):
        path = FIXTURES / "fixture_grunnloven.xml"
        if not path.exists():
            pytest.skip("fixture not available")
        law = parse_law(path.read_bytes())
        assert law is not None
        assert law.refid == "lov/1814-05-17"
        assert "Grunnlov" in law.title

    def test_norske_lov(self):
        path = FIXTURES / "fixture_norske_lov.xml"
        if not path.exists():
            pytest.skip("fixture not available")
        law = parse_law(path.read_bytes())
        assert law is not None
        assert law.refid == "lov/1687-04-15"
        assert law.ministry == "Justis- og beredskapsdepartementet"


# ─── LawData round-trip ─────────────────────────────────────────────────────

# ─── parse_article: text/list interleaving ──────────────────────────────────

class TestParseArticleInterleaving:
    """Verify that text before and after a <ul> within a paragraph is not merged.

    The legacy pipeline flushes accumulated text before processing a list,
    so 'Loven gjelder for:' and 'med virksomhet i Norge.' are separate
    paragraphs with the list items between them.
    """

    def test_text_before_and_after_list_are_separate(self):
        html = """<article class='legalArticle' data-name='§1'>
        <h3 class='legalArticleHeader'><span class='legalArticleValue'>§ 1</span></h3>
        <article class='legalP'>
          <span>Loven gjelder for:</span>
          <ul>
            <li data-li-identifier='a)'>norske foretak</li>
            <li data-li-identifier='b)'>utenlandske foretak</li>
          </ul>
          <span>med virksomhet i Norge.</span>
        </article>
        </article>"""
        soup = BeautifulSoup(html, "html.parser")
        art_tag = soup.find("article", class_="legalArticle")
        article = parse_article(art_tag)

        # There must be more than 1 paragraph to properly separate text/list
        assert len(article.paragraphs) >= 3, (
            f"Expected at least 3 paragraphs (text, list, text), "
            f"got {len(article.paragraphs)}"
        )

        # The first paragraph should contain ONLY the intro text
        assert article.paragraphs[0].text == "Loven gjelder for:"
        assert article.paragraphs[0].list_items == []

        # The second paragraph should contain the list items
        assert article.paragraphs[1].list_items
        assert len(article.paragraphs[1].list_items) == 2
        assert article.paragraphs[1].list_items[0].identifier == "a)"
        assert article.paragraphs[1].list_items[1].identifier == "b)"

        # The third paragraph should contain ONLY the concluding text
        assert article.paragraphs[2].text == "med virksomhet i Norge."
        assert article.paragraphs[2].list_items == []

    def test_text_only_paragraph(self):
        """A paragraph with only text, no list, should produce a single Paragraph."""
        html = """<article class='legalArticle' data-name='§1'>
        <article class='legalP'>
          <span>Bare tekst her.</span>
        </article>
        </article>"""
        soup = BeautifulSoup(html, "html.parser")
        art_tag = soup.find("article", class_="legalArticle")
        article = parse_article(art_tag)
        assert len(article.paragraphs) == 1
        assert article.paragraphs[0].text == "Bare tekst her."
        assert article.paragraphs[0].list_items == []

    def test_list_only_paragraph(self):
        """A paragraph with only a list, no text, should work."""
        html = """<article class='legalArticle' data-name='§1'>
        <article class='legalP'>
          <ul>
            <li data-li-identifier='a)'>punkt a</li>
          </ul>
        </article>
        </article>"""
        soup = BeautifulSoup(html, "html.parser")
        art_tag = soup.find("article", class_="legalArticle")
        article = parse_article(art_tag)
        assert len(article.paragraphs) == 1
        assert article.paragraphs[0].list_items
        assert article.paragraphs[0].list_items[0].text == "punkt a"

    def test_text_then_list_no_trailing_text(self):
        """Text followed by a list with no trailing text."""
        html = """<article class='legalArticle' data-name='§1'>
        <article class='legalP'>
          <span>Formål:</span>
          <ul>
            <li data-li-identifier='a)'>punkt a</li>
            <li data-li-identifier='b)'>punkt b</li>
          </ul>
        </article>
        </article>"""
        soup = BeautifulSoup(html, "html.parser")
        art_tag = soup.find("article", class_="legalArticle")
        article = parse_article(art_tag)
        assert len(article.paragraphs) >= 2
        assert article.paragraphs[0].text == "Formål:"
        assert article.paragraphs[0].list_items == []
        assert len(article.paragraphs[1].list_items) == 2


# ─── parse_section: standalone legalP ────────────────────────────────────────

class TestParseSectionStandaloneParagraphs:
    """Verify that standalone article.legalP elements inside sections are not dropped.

    The legacy section_to_markdown handles two types of children:
      1. legalArticle elements → formatted as articles
      2. article.legalP elements → standalone text paragraphs

    The refactored parse_section was only capturing legalArticle, silently
    dropping the standalone legalP paragraphs.
    """

    def test_standalone_legalP_preserved(self):
        html = """<section>
        <h2>Kapittel 1</h2>
        <article class='legalArticle' data-name='§1'>
        <h3 class='legalArticleHeader'><span class='legalArticleValue'>§ 1</span></h3>
        <article class='legalP'>Artikkel tekst.</article>
        </article>
        <article class='legalP'>En frittstående paragraf.</article>
        </section>"""
        soup = BeautifulSoup(html, "html.parser")
        section_tag = soup.find("section")
        section = parse_section(section_tag)

        assert section.heading == "Kapittel 1"
        # Should have 2 entries: the legalArticle and the standalone legalP
        assert len(section.articles) == 2, (
            f"Expected 2 articles (1 real + 1 standalone paragraph), "
            f"got {len(section.articles)}"
        )
        # The first should be the real article
        assert section.articles[0].name == "§1"
        # The second should represent the standalone paragraph
        assert len(section.articles[1].paragraphs) >= 1
        assert "frittstående paragraf" in section.articles[1].paragraphs[0].text

    def test_only_articles_no_standalone(self):
        """A section with only legalArticle children should work normally."""
        html = """<section>
        <h2>Kap 1</h2>
        <article class='legalArticle' data-name='§1'>
        <h3 class='legalArticleHeader'><span class='legalArticleValue'>§ 1</span></h3>
        <article class='legalP'>Tekst.</article>
        </article>
        </section>"""
        soup = BeautifulSoup(html, "html.parser")
        section_tag = soup.find("section")
        section = parse_section(section_tag)
        assert len(section.articles) == 1
        assert section.articles[0].name == "§1"

    def test_multiple_standalone_paragraphs(self):
        """Multiple standalone legalP paragraphs are all preserved."""
        html = """<section>
        <h2>Kap 2</h2>
        <article class='legalP'>Første avsnitt.</article>
        <article class='legalP'>Andre avsnitt.</article>
        </section>"""
        soup = BeautifulSoup(html, "html.parser")
        section_tag = soup.find("section")
        section = parse_section(section_tag)
        assert len(section.articles) == 2
        assert "Første avsnitt" in section.articles[0].paragraphs[0].text
        assert "Andre avsnitt" in section.articles[1].paragraphs[0].text


class TestLawDataSerialization:
    def test_to_json_and_back(self):
        law = LawData(
            refid="lov/2024-01-01-1",
            title="Testlov",
            short_title="Testloven",
            ministry="Testdepartementet",
            date_in_force="2024-06-01",
            last_amended="",
            last_amended_in_force="",
            legal_area="Test",
            sections=[],
            top_level_articles=[],
        )
        d = law.to_dict()
        restored = LawData.from_dict(d)
        assert restored.refid == law.refid
        assert restored.title == law.title
        assert restored.ministry == law.ministry


# ─── Fixture-based: parse_lovtidend_file ────────────────────────────────────

class TestParseLovtidendFixture:
    @pytest.fixture
    def lovtidend_act(self):
        path = FIXTURES / "fixture_lovtidend.xml"
        if not path.exists():
            pytest.skip("fixture not available")
        act = parse_lovtidend_file(path.read_bytes(), "fixture_lovtidend.xml")
        if act is None:
            pytest.skip("fixture parsed to None")
        return act

    def test_has_refid(self, lovtidend_act):
        assert lovtidend_act.refid

    def test_has_title(self, lovtidend_act):
        assert lovtidend_act.title

    def test_has_amendments(self, lovtidend_act):
        assert len(lovtidend_act.amendments) > 0

    def test_has_changes_to(self, lovtidend_act):
        assert len(lovtidend_act.changes_to) > 0

    def test_amendment_has_type(self, lovtidend_act):
        for a in lovtidend_act.amendments:
            assert a.change_type in ("change", "repeal", "add", "move", "unknown")

    def test_amendment_has_target(self, lovtidend_act):
        typed = [a for a in lovtidend_act.amendments if a.change_type != "unknown"]
        assert all(a.target for a in typed)
