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
