"""The second stream must agree with the parser on text that inline markup used to damage."""
from dataclasses import asdict

from lovdata_loader.parser import parse_law
from lovdata_loader.second_stream import compare_document, read_document

DOCUMENT = """<?xml version="1.0" encoding="utf-8"?>
<html lang="no"><head><title>t</title></head><body><header><dl class="data-document-key-info">
<dt class="title">Tittel</dt><dd class="title">Lov om avgift på utslipp av CO<sub>2</sub> i petroleumsvirksomhet</dd>
<dt class="titleShort">Korttittel</dt><dd class="titleShort">Lov om CO<sub>2</sub>-avgift</dd>
<dt class="refid">RefID</dt><dd class="refid">lov/1990-12-21-72</dd>
<dt class="ministry">Departement</dt><dd class="ministry"><ul><li>Finansdepartementet</li><li>Nærings- og fiskeridepartementet</li></ul></dd>
<dt class="dateInForce">Ikrafttredelse</dt><dd class="dateInForce">1991-01-01</dd>
<dt class="lastChangeInForce">Ikrafttredelse av siste endring</dt><dd class="lastChangeInForce">2019-05-15</dd>
<dt class="lastChangedBy">Sist endret ved</dt><dd class="lastChangedBy"><a href="lov/2019-05-15-1">lov/2019-05-15-1</a>, <a href="lov/2014-09-23-2">lov/2014-09-23-2</a> fra 2014-11-13</dd>
<dt class="legalArea">Rettsområde</dt><dd class="legalArea"><ul><li><a href="legal-areas/1">Skatte- og avgiftsrett</a> &gt; <a href="legal-areas/1.1">Særavgifter</a></li></ul></dd>
</dl></header><main class="documentBody" id="dokument">
<h1>Lov om avgift på utslipp av CO<sub>2</sub> i petroleumsvirksomhet</h1>
<section class="section" data-name="kapI"><h2>Kapittel 1<br/>Avgift etter <a href="lov/1996-11-29-72">petroleumsloven</a> § 4 annet ledd</h2>
<article class="legalArticle" data-name="§1"><h3 class="legalArticleHeader"><span class="legalArticleValue">§ 1</span>. <span class="legalArticleTitle">Utslipp av CO<sub>2</sub> og NO<sub>X</sub> for anlegg</span></h3>
<article class="legalP">Avgiften gjelder CO<sub>2</sub> og CO<sub>2</sub>-ekvivalenter på 10<sup>6</sup> m<sup>3</sup>, jf. <a href="lov/1996-11-29-72/§4">§ 4</a>.</article>
<article class="legalP">Departementet<sup class="footnotereference" data-unique-footnote-counter="7">1</sup> gir forskrift.
<table><tbody><tr><td>SO<sub>2</sub></td><td>Molekylvekt</td></tr></tbody></table></article>
</article></section></main></body></html>""".encode("utf-8")


def test_header_fields_keep_inline_spacing_and_every_ministry():
    law = parse_law(DOCUMENT)
    assert law.title == "Lov om avgift på utslipp av CO2 i petroleumsvirksomhet"
    assert law.short_title == "Lov om CO2-avgift"
    assert law.ministry == "Finansdepartementet\nNærings- og fiskeridepartementet"


def test_in_force_date_belongs_to_the_first_amending_act():
    law = parse_law(DOCUMENT)
    assert law.last_amended == "lov/2019-05-15-1"
    assert law.last_amended_in_force == "2019-05-15"


def test_headings_do_not_join_words_across_inline_markup():
    section = parse_law(DOCUMENT).sections[0]
    assert section.heading == "Kapittel 1 Avgift etter petroleumsloven § 4 annet ledd"
    assert section.articles[0].header_text == "§ 1. Utslipp av CO2 og NOX for anlegg"


def test_subscripts_stay_attached_and_do_not_cross_table_cells():
    paragraphs = parse_law(DOCUMENT).sections[0].articles[0].paragraphs
    assert paragraphs[0].text.startswith("Avgiften gjelder CO2 og CO2-ekvivalenter på 106 m3, jf.")
    assert 'Departementet<sup data-fn="7">1</sup> gir forskrift.' in paragraphs[1].text
    assert "SO2 Molekylvekt" in paragraphs[1].text


def test_second_stream_agrees_with_the_parsed_model():
    result = compare_document(DOCUMENT, asdict(parse_law(DOCUMENT)))
    assert result["header"] == {}
    assert not result["lost"] and not result["novel"]


def test_second_stream_reports_header_and_body_disagreement():
    law = asdict(parse_law(DOCUMENT))
    law["ministry"] = "FinansdepartementetNærings- og fiskeridepartementet"
    law["title"] = "Lov om avgift på utslipp av CO2i petroleumsvirksomhet"
    law["sections"][0]["articles"][0]["paragraphs"][0]["text"] = "Avgiften gjelder CO 2"
    result = compare_document(DOCUMENT, law)
    assert set(result["header"]) == {"title", "ministry"}
    assert result["lost"]["co2"] and result["novel"]["co"] and result["novel"]["co2i"]


def test_read_document_separates_blocks_but_not_inline_markup():
    source = read_document(DOCUMENT)
    assert source["ministry"] == ["Finansdepartementet", "Nærings- og fiskeridepartementet"]
    assert "CO2-ekvivalenter på 106 m3" in source["body_text"]
    assert "SO2 Molekylvekt" in source["body_text"]
    assert "Departementet 1 gir" in source["body_text"]


def test_eli_follows_lovdatas_padding_and_placeholder():
    from lovdata_loader.language_variants import eli_for_refid
    assert eli_for_refid("lov/1998-07-17-56") == "/eli/lov/1998/07/17/56"
    assert eli_for_refid("lov/1884-06-14-3") == "/eli/lov/1884/06/14/03"
    assert eli_for_refid("forskrift/1957-06-07-3391") == "/eli/forskrift/1957/06/07/3391"
    assert eli_for_refid("lov/1687-04-15") == "/eli/lov/1687/04/15/0"
    assert eli_for_refid("lov/1814-05-17-nn") == "/eli/lov/1814/05/17/0"


def test_second_stream_compares_the_source_eli():
    with_eli = DOCUMENT.replace(b'<dt class="refid">', b'<dt class="eli">ELI</dt><dd class="eli">/eli/lov/1990/12/21/72</dd><dt class="refid">')
    assert compare_document(with_eli, asdict(parse_law(with_eli)))["header"] == {}
    wrong = with_eli.replace(b"/eli/lov/1990/12/21/72", b"/eli/lov/1990/12/21/072")
    assert set(compare_document(wrong, asdict(parse_law(wrong)))["header"]) == {"eli"}


def _with_heading_marker(before: bytes, after: bytes) -> bytes:
    marker = b'<sup class="footnotereference" data-unique-footnote-counter="9">1</sup>'
    footer = (b'<footer class="footnotes"><article class="footnote" data-name="1" data-unique-footnote-counter="9">'
              b'<span class="footnoteLabel">1</span> Jf. direktiv 2009/103.</article></footer></article></section>')
    marked = DOCUMENT.replace(before, after.replace(b"MARKER", marker)).replace(b"</article></section>", footer)
    assert marked != DOCUMENT
    return marked


def test_footnote_marker_keeps_its_place_in_a_heading():
    between = _with_heading_marker(b'<span class="legalArticleValue">\xc2\xa7 1</span>. ',
                                   b'<span class="legalArticleValue">\xc2\xa7 1</span>.MARKER ')
    article = parse_law(between).sections[0].articles[0]
    assert article.header_text == '§ 1.<sup data-fn="9">1</sup> Utslipp av CO2 og NOX for anlegg'
    assert '<sup data-fn-note="9">1</sup> Jf. direktiv 2009/103.' in article.trailing_text
    result = compare_document(between, asdict(parse_law(between)))
    assert not result["lost"] and not result["novel"]
    assert result["markers"] == 3 and not result["markers_missing"] and not result["markers_extra"]

    after = _with_heading_marker(b'for anlegg</span></h3>', b'for anlegg</span>MARKER</h3>')
    assert parse_law(after).sections[0].articles[0].header_text == '§ 1. Utslipp av CO2 og NOX for anlegg<sup data-fn="9">1</sup>'


def test_second_stream_reports_a_dropped_marker():
    marked = _with_heading_marker(b'for anlegg</span></h3>', b'for anlegg</span>MARKER</h3>')
    law = asdict(parse_law(marked))
    law["sections"][0]["articles"][0]["header_text"] = "§ 1. Utslipp av CO2 og NOX for anlegg"
    result = compare_document(marked, law)
    assert dict(result["markers_missing"]) == {("reference", "9", "1"): 1}


def test_marker_helpers():
    from lovdata_loader.markers import markers_in, plain_text, strip_markers
    text = 'Art 3.<sup data-fn="15">1</sup> og <sup data-fn-note="15">1</sup> Sml. traktaten'
    assert plain_text(text).split() == ["Art", "3.", "1", "og", "1", "Sml.", "traktaten"]
    assert strip_markers('Art 3.<sup data-fn="15">1</sup>') == "Art 3."
    assert markers_in(text) == [("reference", "15", "1"), ("note", "15", "1")]


def test_amendment_act_keeps_every_ministry():
    from lovdata_loader.parser import parse_lovtidend_file
    act = """<html><head><title>t</title></head><body><header><dl>
<dt class="refid">RefID</dt><dd class="refid">forskrift/2020-01-01-1</dd>
<dt class="title">Tittel</dt><dd class="title">Forskrift om endring i forskrift om CO<sub>2</sub> og fisk</dd>
<dt class="ministry">Departement</dt><dd class="ministry"><ul><li>Fiskeridepartementet</li><li>Landbruksdepartementet</li></ul></dd>
<dt class="dateOfPublication">Kunngjort</dt><dd class="dateOfPublication">2020-01-02 10:00</dd>
</dl></header><main class="documentBody"><h1>Forskrift</h1></main></body></html>"""
    record = parse_lovtidend_file(act, "sf-20200101-0001.xml")
    assert record.ministry == "Fiskeridepartementet\nLandbruksdepartementet"


def test_links_keep_following_punctuation_and_inline_markup_joins_words():
    doc = DOCUMENT.replace(
        '<article class="legalP">Avgiften gjelder'.encode(),
        '<article class="legalP">Se <a href="lov/1/§3">§ 3</a>. Sa<i>m</i>me (<a href="x">pkt</a>) og<br/>neste. Avgiften gjelder'.encode())
    text = parse_law(doc).sections[0].articles[0].paragraphs[0].text
    assert text.startswith("Se § 3. Samme (pkt) og neste. Avgiften gjelder")
    result = compare_document(doc, asdict(parse_law(doc)))
    assert not result["lost"] and not result["novel"]


def test_each_footnote_is_its_own_line_and_adjacent_titles_stay_apart():
    doc = DOCUMENT.replace(b"</article></section>", (
        b'<footer class="footnotes"><article class="footnote" data-unique-footnote-counter="1"><span class="footnoteLabel">1</span> Jf. ODA art. 3.</article>'
        b'<article class="footnote" data-unique-footnote-counter="2"><span class="footnoteLabel">2</span> N\xc3\xa5 domstolen.</article></footer>'
        b'</article><span class="futuretitle">C46. Samfunnsmedisin</span><span class="futuretitle">C46.1 Rolle</span></section>'))
    law = parse_law(doc)
    assert law.sections[0].articles[0].trailing_text.split("\n") == [
        '<sup data-fn-note="1">1</sup> Jf. ODA art. 3.', '<sup data-fn-note="2">2</sup> Nå domstolen.']
    result = compare_document(doc, asdict(law))
    assert not result["lost"] and not result["novel"]
