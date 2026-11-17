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
<article class="legalP">Departementet<sup class="footnotereference">1</sup> gir forskrift.
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
    assert "Departementet 1 gir forskrift." in paragraphs[1].text
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
