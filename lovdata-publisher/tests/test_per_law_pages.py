"""Tests for per_law_pages module."""
import re
from pathlib import Path

from lovdata_publisher.per_law_pages import (
    build_korttittel_index,
    build_cross_reference_pattern,
    dept_slug,
    insert_cross_reference_links,
    parse_frontmatter_and_body,
    render_markdown_body,
    strip_markdown_for_search,
)


def test_dept_slug_basic():
    assert dept_slug("Finansdepartementet") == "finansdepartementet"
    assert dept_slug("Nærings- og fiskeridepartementet") == "nærings--og-fiskeridepartementet"
    assert dept_slug("Statsministerens kontor") == "statsministerens-kontor"


def test_parse_frontmatter_and_body(tmp_path):
    f = tmp_path / "lov-1998-07-17-56.md"
    f.write_text(
        '---\n'
        'tittel: "Lov om årsregnskap"\n'
        'korttittel: "Regnskapsloven – rskl"\n'
        'refid: "lov/1998-07-17-56"\n'
        'departement: "Finansdepartementet"\n'
        '---\n\n'
        '# Lov om årsregnskap\n\n## Kapittel 1\n\nFørste paragraf.',
        encoding="utf-8",
    )
    meta, body = parse_frontmatter_and_body(f)
    assert meta["tittel"] == "Lov om årsregnskap"
    assert meta["korttittel"] == "Regnskapsloven – rskl"
    assert meta["refid"] == "lov/1998-07-17-56"
    assert "# Lov om årsregnskap" in body


def test_build_korttittel_index(tmp_path):
    (tmp_path / "lov-1997-06-13-44.md").write_text(
        '---\nkorttittel: "Aksjeloven – asl"\nrefid: "lov/1997-06-13-44"\n---\n\nbody',
        encoding="utf-8",
    )
    (tmp_path / "lov-1998-07-17-56.md").write_text(
        '---\nkorttittel: "Regnskapsloven – rskl"\nrefid: "lov/1998-07-17-56"\n---\n\nbody',
        encoding="utf-8",
    )
    index = build_korttittel_index(tmp_path)
    assert index["aksjeloven"] == "lov-1997-06-13-44.html"
    assert index["regnskapsloven"] == "lov-1998-07-17-56.html"


def test_cross_reference_links_replace_first_mention():
    index = {"aksjeloven": "lov-1997-06-13-44.html", "regnskapsloven": "lov-1998-07-17-56.html"}
    pattern = build_cross_reference_pattern(index)
    html = "Se aksjeloven § 8-2 og deretter aksjeloven § 9-1."
    result = insert_cross_reference_links(html, index, pattern, current_stem="lov-1998-07-17-56")
    # First occurrence becomes a hyperlink, second stays plain
    assert '<a href="lov-1997-06-13-44.html">aksjeloven</a>' in result
    assert result.count("<a") == 1


def test_cross_reference_skips_self():
    index = {"regnskapsloven": "lov-1998-07-17-56.html"}
    pattern = build_cross_reference_pattern(index)
    html = "Regnskapsloven gjelder for alle aksjeselskaper."
    result = insert_cross_reference_links(html, index, pattern, current_stem="lov-1998-07-17-56")
    assert "<a" not in result


def test_cross_reference_preserves_real_datalagring_heading_id():
    import xml.etree.ElementTree as ET

    title = (
        "Lov om endringer i ekomloven og straffeprosessloven mv. "
        "(gjennomføring av EUs datalagringsdirektiv i norsk rett)"
    )
    index = {"ekomloven": "ekom.html", "straffeprosessloven": "straffe.html",
             "aksjeloven": "aksje.html"}
    html = render_markdown_body(f"# {title}\n\nSe aksjeloven § 8-2 og aksjeloven § 9-1.")
    result = insert_cross_reference_links(html, index, build_cross_reference_pattern(index), "lov-2011-04-15-11")
    # The original heading opening tag must survive byte-for-byte.
    assert result.startswith(html.split(">", 1)[0] + ">")
    heading = ET.fromstring(result.split("</h1>", 1)[0] + "</h1>")
    assert "".join(heading.itertext()) == title
    assert result.count('<a href="aksje.html">aksjeloven</a>') == 1


def test_cross_reference_preserves_markup_existing_links_and_code():
    index = {"aksjeloven": "aksje.html"}
    untouched = (
        '<!-- aksjeloven --><a href="aksjeloven.html" title="aksjeloven">aksjeloven</a>'
        '<script>const title = "aksjeloven";</script><style>.aksjeloven { color: red }</style>'
        '<pre>aksjeloven</pre><code>aksjeloven</code>'
    )
    html = untouched + '\n<p title="aksjeloven">Se aksjeloven &amp; regnskapsloven.</p>'
    result = insert_cross_reference_links(html, index, build_cross_reference_pattern(index), "other")
    assert result == untouched + '\n<p title="aksjeloven">Se <a href="aksje.html">aksjeloven</a> &amp; regnskapsloven.</p>'


def test_strip_markdown_for_search_truncates():
    body = ("# Title\n\n*emphasis* and [link](url) and " + "x " * 5000)
    text = strip_markdown_for_search(body, max_chars=100)
    assert len(text) <= 100
    assert "[link]" not in text
    assert "*emphasis*" not in text


def test_build_korttittel_index_handles_compound_korttittel(tmp_path):
    (tmp_path / "lov-1997-06-13-44.md").write_text(
        '---\nkorttittel: "Aksjeloven – asl"\nrefid: "lov/1997-06-13-44"\n---\n\nbody',
        encoding="utf-8",
    )
    index = build_korttittel_index(tmp_path)
    # We only index the part ending in 'loven'/'lova', not abbreviations
    assert "aksjeloven" in index
    assert "asl" not in index


def test_lovdata_style_key_info_helpers():
    from lovdata_publisher.per_law_pages import format_no_date, lovdata_code, sist_endret_display
    assert lovdata_code("lov/1998-07-17-56") == "LOV-1998-07-17-56"
    assert lovdata_code("forskrift/2025-08-06-1610") == "FOR-2025-08-06-1610"
    assert lovdata_code("lov/1814-05-17") == "LOV-1814-05-17"
    assert format_no_date("1999-01-01") == "01.01.1999"
    assert format_no_date("2026-01-01, 2026-07-01, Kongen bestemmer") == "01.01.2026, 01.07.2026, Kongen bestemmer"
    assert sist_endret_display("lov/2025-06-20-106", "2026-01-01") == "LOV-2025-06-20-106 <code>lov/2025-06-20-106</code> fra 01.01.2026"
    assert sist_endret_display("", "") == "—"


def test_toc_and_notes_from_rendered_body():
    from lovdata_publisher.per_law_pages import build_toc_html, render_markdown_body, style_amendment_notes
    body = ("# Lov om test\n\n## Kapittel 1. Innledning\n\n#### § 1-1. Formål\n\nTekst.\n\n"
            "*Endret ved lov 10 juni 2005 nr. 46 (ikr. 1 juli 2005).*\n\n#### § 1-2. Virkeområde\n\nMer.\n")
    html = style_amendment_notes(render_markdown_body(body))
    assert '<p class="note">Endret ved lov 10 juni 2005 nr. 46 (ikr. 1 juli 2005).</p>' in html
    toc = build_toc_html(html)
    assert '<li class="lvl2"><a href="#kapittel-1-innledning">Kapittel 1. Innledning</a></li>' in toc
    assert '<li class="lvl4"><a href="#1-1-formal">§ 1-1. Formål</a></li>' in toc
    assert "Lov om test" not in toc


def test_generated_page_puts_title_first_and_keeps_one_h1(tmp_path):
    from lovdata_publisher.per_law_pages import generate_per_law_pages
    (tmp_path / "lover").mkdir()
    (tmp_path / "lover" / "lov-1998-07-17-56.md").write_text(
        '---\ntittel: "Lov om årsregnskap m.v. (regnskapsloven)"\nkorttittel: "Regnskapsloven – rskl"\n'
        'refid: "lov/1998-07-17-56"\ndepartement: "Finansdepartementet"\nikrafttredelse: "1999-01-01"\n'
        'sist-endret: "lov/2025-06-20-106"\nsist-endret-ikrafttredelse: "2026-01-01"\n---\n\n'
        "# Lov om årsregnskap m.v. (regnskapsloven)\n\n## Kapittel 1. Virkeområde\n\n#### § 1-1. Lovens virkeområde\n\n(1) Loven gjelder.\n\n"
        "*Endret ved lov 10 juni 2005 nr. 46.*\n", encoding="utf-8")
    assert generate_per_law_pages(str(tmp_path), site_dir="_site") == 1
    html = (tmp_path / "_site" / "lover" / "lov-1998-07-17-56.html").read_text(encoding="utf-8")
    assert html.count("<h1") == 1
    assert html.index('<h1 class="doc-title">') < html.index('<table class="keyinfo">') < html.index('<h2 id="kapittel-1-virkeomrade">')
    assert "LOV-1998-07-17-56" in html and "01.01.1999" in html and "fra 01.01.2026" in html
    assert 'action="../book/sok.html"' in html
    assert '<aside class="toc"' in html and 'href="#1-1-lovens-virkeomrade"' in html
    assert '<p class="note">Endret ved lov 10 juni 2005 nr. 46.</p>' in html
    assert "\U0001F4E1" not in html and "📜" not in html
