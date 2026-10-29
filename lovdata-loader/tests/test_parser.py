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

    def test_empty_string_falls_back(self):
        date, deferred = parse_effective_date("", "2023-06-20")
        assert date == "2023-06-20"
        assert deferred is True


# ─── parse_publication_date ──────────────────────────────────────────────────

class TestParsePublicationDate:
    def test_iso_datetime(self):
        assert parse_publication_date("2023-06-20 14:30") == "2023-06-20"

    def test_norwegian_date(self):
        assert parse_publication_date("20.06.2023") == "2023-06-20"

    def test_fallback(self):
        assert parse_publication_date("nonsense") == "2000-01-01"


# ─── extract_last_changed_by ────────────────────────────────────────────────

class TestExtractLastChangedBy:
    def test_anchor_with_fra(self):
        html = '<header><dd class="lastChangedBy"><a href="lov/2023-06-16-40">lov/2023-06-16-40</a> fra 2023-07-01</dd></header>'
        soup = BeautifulSoup(html, "html.parser")
        refid, in_force = extract_last_changed_by(soup.find("header"))
        assert refid == "lov/2023-06-16-40"
        assert in_force == "2023-07-01"

    def test_no_element(self):
        html = '<header><dd class="title">Some title</dd></header>'
        soup = BeautifulSoup(html, "html.parser")
        refid, in_force = extract_last_changed_by(soup.find("header"))
        assert refid == ""
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


def test_parse_effective_date_year_typo_falls_back_to_published():
    """Source data has known typos like '2107-01-01' (intended 2017).
    Without sanity, these propagate to JSONL and break time-series. Real
    case caught by data review 2026-05-20: forskrift/2016-12-21-1854 had
    in_force='2107-01-01' which made it dominate /aktivitet.html's
    year-range max.
    """
    # Typo: 2107 instead of 2017
    date, deferred = parse_effective_date("2107-01-01", "2016-12-30")
    assert date == "2016-12-30"
    assert deferred is True

    # Realistic far-future date (deferred to next century) — also rejected
    date, _ = parse_effective_date("2099-01-01", "2024-01-01")
    assert date == "2024-01-01"

    # Just-OK boundary (year 2050)
    date, deferred = parse_effective_date("2050-01-01", "2024-01-01")
    assert date == "2050-01-01"
    assert deferred is False


# ─── Multi-law endringslov target_law tracking ──────────────────────────────


def test_flat_format_multi_law_endringslov_tracks_context():
    """Real case: lov/2007-01-26-3 has 802 amendments across 147 laws in a
    single flat <main class='documentBody'> body — no <section> wrappers.
    Each law-block is announced by a numbered preamble paragraph
    ('N. I lov DATE nr. NR ... gjoeres foelgende endringer:'). Before the
    fix, only the first preamble was found; all 802 amendments inherited
    it (or were null). After the fix, target_law is re-anchored at each
    preamble.
    """
    xml = """<!DOCTYPE html><html><body>
<header class="documentHeader">
<dl class="data-document-key-info">
<dt class="refid">RefID</dt><dd class="refid">lov/2024-06-21-99</dd>
<dt class="title">Tittel</dt><dd class="title">Lov om endringer i flere lover</dd>
<dt class="changesToDocuments">Endrer</dt><dd class="changesToDocuments"><ul>
<li>lov/1900-01-01-1</li><li>lov/1950-06-15-22</li><li>lov/1980-11-30-55</li>
</ul></dd>
</dl></header>
<main class="documentBody">
<h1>Lov om endringer i flere lover.</h1>
<article class="legalP">I lov 1. januar 1900 nr. 1 om første gjøres følgende endringer:</article>
<article class="defaultP">§ 1 skal lyde:</article>
<article class="legalP">Ny tekst for første lov § 1.</article>
<article class="defaultP">§ 2 skal lyde:</article>
<article class="legalP">Ny tekst for første lov § 2.</article>
<article class="defaultP">2. I lov 15. juni 1950 nr. 22 om andre gjøres følgende endringer:</article>
<article class="defaultP">§ 5 skal lyde:</article>
<article class="legalP">Ny tekst for andre lov § 5.</article>
<article class="defaultP">3. I lov 30. november 1980 nr. 55 om tredje gjøres følgende endringer:</article>
<article class="defaultP">§ 10 skal lyde:</article>
<article class="legalP">Ny tekst for tredje lov § 10.</article>
<article class="defaultP">§ 11 oppheves.</article>
</main></body></html>""".encode("utf-8")
    result = parse_lovtidend_file(xml, "test.xml")
    assert result is not None
    assert len(result.amendments) == 5
    expected_laws = [
        "lov/1900-01-01-1", "lov/1900-01-01-1",
        "lov/1950-06-15-22",
        "lov/1980-11-30-55", "lov/1980-11-30-55",
    ]
    actual = [a.target_law for a in result.amendments]
    assert actual == expected_laws
    assert result.amendments[4].change_type == "repeal"


def test_single_law_endringslov_uses_header_fallback():
    """Real case: lov/2008-12-12-99 has its target law in the title only:
    'Lov om endringer i lov 26. mars 1999 nr. 14 om skatt'. The <section>
    bodies (I, II, III...) contain amendment instructions but no preamble,
    so target_law was null for all 65 amendments before the fix. Now uses
    the act-header's <changesToDocuments> as fallback when it has exactly
    one entry.
    """
    xml = """<!DOCTYPE html><html><body>
<header class="documentHeader">
<dl class="data-document-key-info">
<dt class="refid">RefID</dt><dd class="refid">lov/2024-12-01-50</dd>
<dt class="title">Tittel</dt><dd class="title">Lov om endringer i skatteloven</dd>
<dt class="changesToDocuments">Endrer</dt><dd class="changesToDocuments"><ul>
<li>lov/1999-03-26-14</li>
</ul></dd>
</dl></header>
<main class="documentBody">
<h1>Lov om endringer i skatteloven.</h1>
<section><h2>I</h2>
<article class="defaultP">§ 8-11 første ledd bokstav e skal lyde:</article>
<article class="legalP">Ny tekst § 8-11.</article>
<article class="defaultP">§ 8-12 oppheves.</article>
</section>
<section><h2>II</h2>
<article class="defaultP">§ 9-14 skal lyde:</article>
<article class="legalP">Ny tekst § 9-14.</article>
</section>
</main></body></html>""".encode("utf-8")
    result = parse_lovtidend_file(xml, "test.xml")
    assert result is not None
    assert len(result.amendments) == 3
    for a in result.amendments:
        assert a.target_law == "lov/1999-03-26-14"


def test_capitalized_preamble_keyword_recognized():
    """Real case: lov/2009-06-19-74 uses 'Lov 20. mai 2005 nr. 28 om straff
    endres slik:' (capitalized Lov, alternative phrasing 'endres slik').
    The original regex required lowercase 'lov' and the phrase 'gjoeres
    foelgende endringer'.
    """
    xml = """<!DOCTYPE html><html><body>
<header class="documentHeader">
<dl class="data-document-key-info">
<dt class="refid">RefID</dt><dd class="refid">lov/2024-06-19-77</dd>
<dt class="title">Tittel</dt><dd class="title">Lov om endringer</dd>
<dt class="changesToDocuments">Endrer</dt><dd class="changesToDocuments"><ul>
<li>lov/2005-05-20-28</li><li>lov/1981-05-22-25</li>
</ul></dd>
</dl></header>
<main class="documentBody">
<h1>Lov om endringer.</h1>
<section><h2>I</h2>
<article class="legalP">Lov 20. mai 2005 nr. 28 om straff endres slik:</article>
<article class="defaultP">§ 5 nytt femte ledd skal lyde:</article>
<article class="legalP">Ny tekst.</article>
</section>
<section><h2>II</h2>
<article class="legalP">I lov 22. mai 1981 nr. 25 om straffeprosess gjøres følgende endringer:</article>
<article class="defaultP">§ 1 skal lyde:</article>
<article class="legalP">Ny tekst straffeprosess.</article>
</section>
</main></body></html>""".encode("utf-8")
    result = parse_lovtidend_file(xml, "test.xml")
    assert result is not None
    assert len(result.amendments) == 2
    assert result.amendments[0].target_law == "lov/2005-05-20-28"
    assert result.amendments[1].target_law == "lov/1981-05-22-25"


def test_preamble_not_triggered_by_incidental_law_reference():
    """A paragraph that merely mentions another law inside an amendment
    instruction (e.g. '§ 14 skal vise til lov 17. juli 1925 nr. 11 om
    Svalbard') must NOT be treated as a preamble. The check requires both
    a phrase like 'gjoeres foelgende endringer' AND an extractable refid.
    """
    xml = """<!DOCTYPE html><html><body>
<header class="documentHeader">
<dl class="data-document-key-info">
<dt class="refid">RefID</dt><dd class="refid">lov/2024-06-21-42</dd>
<dt class="title">Tittel</dt><dd class="title">Endring</dd>
<dt class="changesToDocuments">Endrer</dt><dd class="changesToDocuments"><ul>
<li>lov/1998-07-17-56</li>
</ul></dd>
</dl></header>
<main class="documentBody">
<h1>Endring</h1>
<article class="legalP">I lov 17. juli 1998 nr. 56 om årsregnskap gjøres følgende endringer:</article>
<article class="defaultP">§ 7-25 skal lyde:</article>
<article class="legalP">Henvisning til lov 17. juli 1925 nr. 11 om Svalbard gjelder ikke her.</article>
<article class="defaultP">§ 7-26 skal lyde:</article>
<article class="legalP">Ny tekst § 7-26.</article>
</main></body></html>""".encode("utf-8")
    result = parse_lovtidend_file(xml, "test.xml")
    assert result is not None
    # Both amendments should still belong to regnskapsloven, NOT Svalbard-loven
    assert len(result.amendments) == 2
    for a in result.amendments:
        assert a.target_law == "lov/1998-07-17-56"


class TestParseLeddInterleaving:
    def test_text_after_list_goes_to_trailing(self):
        from bs4 import BeautifulSoup
        from lovdata_loader.parser import _parse_ledd
        html = """<article class="legalP">Loven gjelder for:
        <ul><li data-name="a)">norske foretak</li>
        <li data-name="b)">utenlandske foretak</li></ul>
        med virksomhet i Norge.</article>"""
        ledd = BeautifulSoup(html, "lxml").find("article")
        p = _parse_ledd(ledd)
        assert p.text == "Loven gjelder for:"
        assert [li.marker for li in p.list_items] == ["a)", "b)"]
        assert [li.paragraphs[0].text for li in p.list_items] == [
            "norske foretak", "utenlandske foretak"
        ]
        assert p.trailing_text == "med virksomhet i Norge."

    def test_no_list_keeps_trailing_empty(self):
        from bs4 import BeautifulSoup
        from lovdata_loader.parser import _parse_ledd
        html = '<article class="legalP">Bare tekst uten liste.</article>'
        ledd = BeautifulSoup(html, "lxml").find("article")
        p = _parse_ledd(ledd)
        assert p.text == "Bare tekst uten liste."
        assert p.trailing_text == ""

    def test_roundtrip_through_dict(self):
        from bs4 import BeautifulSoup
        from lovdata_loader.parser import _parse_ledd
        from lovdata_loader.models import _article_from_dict
        from dataclasses import asdict
        html = """<article class="legalP">Innledning:
        <ul><li data-name="1.">punkt</li></ul>
        Etterfølgende tekst.</article>"""
        ledd = BeautifulSoup(html, "lxml").find("article")
        p = _parse_ledd(ledd)
        art = _article_from_dict({
            "name": "§ 1", "header_text": "§ 1",
            "paragraphs": [asdict(p)],
        })
        assert art.paragraphs[0].trailing_text == "Etterfølgende tekst."
        assert art.paragraphs[0].list_items[0].marker == "1."

    def test_list_item_misc_headline_captured(self):
        from bs4 import BeautifulSoup
        from lovdata_loader.parser import _parse_ledd
        html = """<article class="legalP">Overgangsregler:
        <ol class="defaultList"><li data-name="1."><article class="listArticle">
        <span class="miscHeadline"><i>Tap av retten</i></span>
        <article class="legalP">Når det er fastsatt tap.</article>
        </article></li></ol></article>"""
        ledd = BeautifulSoup(html, "lxml").find("article", class_="legalP")
        p = _parse_ledd(ledd)
        texts = [para.text for para in p.list_items[0].paragraphs]
        assert "Tap av retten" in texts
        assert "Når det er fastsatt tap." in texts


class TestMarkerResolution:
    def _li(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "lxml").find("li")

    def test_data_name_preferred(self):
        from lovdata_loader.parser import _resolve_marker
        assert _resolve_marker(self._li('<li data-name="3." value="3"></li>'), "1") == "3."

    def test_composed_from_value_and_style(self):
        from lovdata_loader.parser import _resolve_marker
        assert _resolve_marker(self._li('<li value="3"></li>'), "1") == "3."
        assert _resolve_marker(self._li('<li value="1"></li>'), "A") == "A."
        assert _resolve_marker(self._li('<li value="2"></li>'), "a") == "b)"
        assert _resolve_marker(self._li('<li value="4"></li>'), "I") == "IV."

    def test_legacy_identifier_fallback(self):
        from lovdata_loader.parser import _resolve_marker
        assert _resolve_marker(self._li('<li data-li-identifier="a)"></li>'), "") == "a)"

    def test_unlabelled_is_bullet(self):
        from lovdata_loader.parser import _resolve_marker
        assert _resolve_marker(self._li('<li></li>'), "") == ""


class TestRealArchiveLists:
    def _articles(self):
        import os
        from bs4 import BeautifulSoup
        from lovdata_loader.parser import parse_article
        path = os.path.join(os.path.dirname(__file__), "fixtures",
                            "fixture_regnskapsloven_lists.xml")
        soup = BeautifulSoup(open(path, encoding="utf-8").read(), "lxml")
        return {
            parse_article(a).name.replace(" ", ""): parse_article(a)
            for a in soup.find_all("article", class_="legalArticle")
        }

    def test_flat_disclosure_list_markers(self):
        items = self._articles()["§7-12"].paragraphs[0].list_items
        assert [li.marker for li in items] == ["1.", "2.", "3.", "4."]
        assert items[0].paragraphs[0].text.startswith("anskaffelseskost")

    def test_nested_oppstillingsplan_depth_three(self):
        paragraph = self._articles()["§6-2"].paragraphs[0]
        blocks = paragraph.ordered_blocks
        assert [block.kind for block in blocks] == ["text", "list", "text", "list"]
        assert blocks[2].text == "EGENKAPITAL OG GJELD"
        top = [item for block in blocks if block.kind == "list" for item in block.list_items]
        assert [li.marker for li in top] == ["A.", "B.", "C.", "D."]
        anlegg = top[0].paragraphs[0].list_items
        assert [li.marker for li in anlegg] == ["I.", "II.", "III."]
        immateriell = anlegg[0].paragraphs[0].list_items
        assert [li.marker for li in immateriell] == ["1.", "2.", "3.", "4."]
        assert immateriell[0].paragraphs[0].text == "Utvikling"

    def test_no_anomalies(self):
        from dataclasses import asdict
        from lovdata_loader.audit import audit_law_lists
        for art in self._articles().values():
            law = {"refid": "lov/1998-07-17-56", "top_level_articles": [asdict(art)]}
            assert audit_law_lists(law)["anomalies"] == []


def _act(body: str, changes_to: str = "<li>lov/1998-07-17-56</li>") -> bytes:
    return f"""<!DOCTYPE html><html><body>
<header class="documentHeader">
<dl class="data-document-key-info">
<dt class="refid">RefID</dt><dd class="refid">lov/2025-04-10-11</dd>
<dt class="title">Tittel</dt><dd class="title">Lov om endringer i regnskapsloven</dd>
<dt class="changesToDocuments">Endrer</dt><dd class="changesToDocuments"><ul>{changes_to}</ul></dd>
</dl></header>
<main class="documentBody"><h1>Lov om endringer i regnskapsloven</h1>
{body}
</main></body></html>""".encode("utf-8")


def test_new_format_numbered_ledd_is_replacement_text():
    """Real case: lov/2025-04-10-11 § 3-1 tredje ledd. Newer acts put the
    new wording in article.numberedLegalP directly under article.change;
    only legalP was collected, so 1,745 'skal lyde:' records had no text."""
    xml = _act("""<section><h2>I</h2>
<article class="document-change" data-document="lov/1998-07-17-56">
<article class="defaultP">I lov 17. juli 1998 nr. 56 om årsregnskap m.v. gjøres følgende endringer:</article>
<article class="change" data-change-part="lov/1998-07-17-56/§3-1/ledd/3">
<article class="defaultP">§ 3-1 tredje ledd skal lyde:</article>
<article class="numberedLegalP" data-numerator="3">(3) For konsernregnskap gjelder ikke § 1-4.</article>
</article>
<article class="change" data-change-part="lov/1998-07-17-56/§3-2/ledd/2 lov/1998-07-17-56/§3-2/ledd/3">
<article class="defaultP">Nåværende tredje og fjerde ledd blir annet og tredje ledd og skal lyde:</article>
<article class="numberedLegalP" data-numerator="2">(2) Første nye ledd.</article>
<article class="numberedLegalP" data-numerator="3">(3) Andre nye ledd.</article>
</article>
</article></section>""")
    result = parse_lovtidend_file(xml, "test.xml")
    assert [a.new_text for a in result.amendments] == [
        "(3) For konsernregnskap gjelder ikke § 1-4.",
        "(2) Første nye ledd.\n(3) Andre nye ledd.",
    ]
    assert result.amendments[0].target_law == "lov/1998-07-17-56"


def test_new_format_future_article_text_not_duplicated():
    """Real case: lov/2024-06-21-42 '§ 3-1 paragrafoverskriften skal lyde:'.
    The futureLegalArticleHeader span sits inside the futureLegalArticle;
    collecting both repeated the heading. A full future article now yields
    one line per heading/ledd."""
    xml = _act("""<section><h2>I</h2>
<article class="change" data-change-part="lov/1998-07-17-56/§3-1">
<article class="defaultP">§ 3-1 paragrafoverskriften skal lyde:</article>
<article class="futureLegalArticle" data-name="§3-1"><span class="futureLegalArticleHeader"><span class="legalArticleValue">§ 3-1</span>. <span class="legalArticleTitle">Plikt til å utarbeide årsregnskap</span></span></article>
</article>
<article class="change" data-add-new-part="lov/1998-07-17-56/§2-1" data-change-part="lov/1998-07-17-56/kap2">
<article class="defaultP">Kapittel 2 skal lyde:</article>
<span class="futuretitle">Kapittel 2 Årsberetning</span>
<article class="futureLegalArticle" data-name="§2-1"><span class="futureLegalArticleHeader"><span class="legalArticleValue">§ 2-1</span>. <span class="legalArticleTitle">Plikt</span></span><article class="numberedLegalP" data-numerator="1">(1) Første ledd.</article><article class="numberedLegalP" data-numerator="2">(2) Andre ledd.</article></article>
</article></section>""")
    result = parse_lovtidend_file(xml, "test.xml")
    assert result.amendments[0].new_text == "§ 3-1. Plikt til å utarbeide årsregnskap"
    assert result.amendments[1].new_text == "Kapittel 2 Årsberetning\n§ 2-1. Plikt\n(1) Første ledd.\n(2) Andre ledd."


def test_old_format_heading_after_instruction_is_text():
    """Real case: lov/2001-06-15-41 'Avsnittets tittel skal lyde:' followed by
    the new title as a heading element, which was skipped."""
    xml = _act("""<section><h2>I</h2>
<article class="defaultP">I lov 17. juli 1998 nr. 56 om årsregnskap m.v. gjøres følgende endringer:</article>
<article class="defaultP">Kapittel 2 avsnitt I skal omfatte §§ 2-1 til 2-9. Avsnittets tittel skal lyde:</article>
<h3>I. Alminnelige bestemmelser</h3>
<article class="defaultP">§ 2-1 skal lyde:</article>
<article class="legalP">Ny tekst.</article>
</section>
<section><h2>II</h2>
<article class="defaultP">§ 2-2 oppheves.</article>
</section>""")
    result = parse_lovtidend_file(xml, "test.xml")
    texts = [(a.instruction, a.new_text) for a in result.amendments]
    assert texts[0] == ("Kapittel 2 avsnitt I skal omfatte §§ 2-1 til 2-9. Avsnittets tittel skal lyde:", "I. Alminnelige bestemmelser")
    assert texts[1] == ("§ 2-1 skal lyde:", "Ny tekst.")
    assert texts[2][0] == "§ 2-2 oppheves."


def test_unrecognised_single_target_act_keeps_body_as_unknown_record():
    """Real case: forskrift/2025-10-29-2134 changes KOSTRA code lists with
    'Følgende art går ut:' / 'Funksjon 211 endrer navn til ...'. No pattern
    matched, so the act vanished from the regulation's history."""
    xml = _act("""<section><h2>I</h2>
<article class="defaultP">I forskrift 18. oktober 2019 nr. 1412 (KOSTRA-forskriften) vedlegg 1 gjøres følgende endringer:</article>
<article class="defaultP">Følgende art går ut:<ul class="defaultList"><li><article class="listArticle"><article class="legalP">Art 270 Andre tjenester</article></article></li></ul></article>
</section>
<section><h2>II</h2>
<article class="defaultP">Funksjon 211 endrer navn til Styrket tilbud til barn i barnehage.</article>
</section>""", changes_to="<li>forskrift/2019-10-18-1412</li>")
    result = parse_lovtidend_file(xml, "test.xml")
    assert len(result.amendments) == 1
    a = result.amendments[0]
    assert a.change_type == "unknown"
    assert a.target_law == "forskrift/2019-10-18-1412"
    assert a.instruction.startswith("I forskrift 18. oktober 2019 nr. 1412")
    assert "Art 270 Andre tjenester" in a.new_text
    assert "Funksjon 211 endrer navn til" in a.new_text
    assert "\nI\n" not in a.new_text and "\nII\n" not in a.new_text


def test_unrecognised_multi_target_act_stays_empty():
    xml = _act("""<section><h2>I</h2>
<article class="defaultP">Funksjon 211 endrer navn til noe.</article>
</section>""", changes_to="<li>forskrift/2019-10-18-1412</li><li>forskrift/2019-10-18-1413</li>")
    result = parse_lovtidend_file(xml, "test.xml")
    assert result.amendments == []


def test_old_format_chapter_title_paragraph_is_replacement_text():
    """Real cases: lov/2001-06-15-62 'Nytt kapittel 1 A skal lyde:' and
    lov/2002-03-15-5 'Overskriften til kapittel 7 skal lyde:' are followed by
    the new title in an italic defaultP that names the chapter; it was taken
    for a new instruction, leaving the replacement empty."""
    xml = _act("""<section><h2>I</h2>
<article class="defaultP">I lov 17. juli 1998 nr. 56 om årsregnskap m.v. gjøres følgende endringer:</article>
<article class="defaultP">Nytt kapittel 1 A skal lyde:</article>
<article class="defaultP"><i>Kapittel 1 A Den sentrale domstoladministrasjonen</i></article>
<article class="defaultP"><strong>§ 33.</strong> Domstoladministrasjonen ledes av et styre.</article>
<article class="legalP">Kongen i statsråd kan treffe vedtak.</article>
<article class="defaultP">Overskriften til kapittel 7 skal lyde:</article>
<article class="defaultP"><i>Kapittel 7. Tilsyn med forurensninger og avfall</i></article>
<article class="defaultP">Kapittel 7A (herunder kapitteloverskriften) oppheves og § 52 c går inn i kapittel 7.</article>
</section>""")
    result = parse_lovtidend_file(xml, "test.xml")
    recs = [(a.instruction, a.new_text) for a in result.amendments]
    assert recs[0] == ("Nytt kapittel 1 A skal lyde:",
                       "Kapittel 1 A Den sentrale domstoladministrasjonen\n§ 33.Domstoladministrasjonen ledes av et styre.\nKongen i statsråd kan treffe vedtak.")
    assert recs[1] == ("Overskriften til kapittel 7 skal lyde:", "Kapittel 7. Tilsyn med forurensninger og avfall")
    assert recs[2][0].startswith("Kapittel 7A (herunder kapitteloverskriften) oppheves")
