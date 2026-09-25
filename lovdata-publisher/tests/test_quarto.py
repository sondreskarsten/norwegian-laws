"""Tests for lovdata_publisher.quarto."""
from lovdata_publisher.quarto import split_departments, parse_frontmatter


# ─── split_departments ──────────────────────────────────────────────────────

class TestSplitDepartments:
    def test_single_department(self):
        assert split_departments("Finansdepartementet") == ["Finansdepartementet"]

    def test_concatenated_departments(self):
        result = split_departments("Klima- og miljødepartementetLandbruks- og matdepartementet")
        assert result == ["Klima- og miljødepartementet", "Landbruks- og matdepartementet"]

    def test_unknown_department(self):
        assert split_departments("Ukjent departement") == ["Ukjent departement"]

    def test_empty_string(self):
        assert split_departments("") == [""]

    def test_triple_concatenation(self):
        result = split_departments(
            "FinansdepartementetJustis- og beredskapsdepartementetKunnskapsdepartementet"
        )
        assert len(result) == 3
        assert "Finansdepartementet" in result
        assert "Justis- og beredskapsdepartementet" in result
        assert "Kunnskapsdepartementet" in result


# ─── parse_frontmatter ──────────────────────────────────────────────────────

class TestParseFrontmatter:
    def test_reads_real_law_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text('---\ntittel: "Testlov"\nrefid: "lov/2024-01-01-1"\n---\n\n# Testlov\n')
        meta = parse_frontmatter(str(f))
        assert meta["tittel"] == "Testlov"
        assert meta["refid"] == "lov/2024-01-01-1"

    def test_no_frontmatter(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("# Just a heading\n")
        meta = parse_frontmatter(str(f))
        assert meta == {}


def test_full_text_links_use_encoded_actual_match(tmp_path):
    """Exercise the emitted JS; stems/HTML must not become a query or URL."""
    import shutil
    import subprocess

    import pytest
    from lovdata_publisher.quarto import generate_search_page

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is needed to execute the generated browser helper")
    generate_search_page(str(tmp_path))
    page = (tmp_path / "sok.qmd").read_text(encoding="utf-8")
    start = page.index("  function matchedTextFragment(")
    helper = page[start:page.index("  function renderResults(", start)]
    script = r'''
const assert = require("node:assert/strict");
// The helper only uses an inert textarea to decode Pagefind's escaped text.
const document = {createElement() { return {
  set innerHTML(value) { this.value = value.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">"); }
}; }};
''' + helper + r'''
assert.equal(matchedTextFragment("No highlighted match"), "");
assert.equal(matchedTextFragment("<mark></mark>"), "");
assert.equal(matchedTextFragment("før <mark>års-regnskap</mark> <mark>&amp;</mark> etter"),
  "#:~:text=f%C3%B8r-,%C3%A5rs%2Dregnskap%20%26,-etter&text=%C3%A5rs%2Dregnskap%20%26");
assert.equal(matchedTextFragment("<mark>&lt;script&gt;</mark>"), "#:~:text=%3Cscript%3E");
assert.equal(matchedTextFragment("skal gjennomgå <mark>denne</mark> <mark>forordnings</mark> <mark>virkemåte</mark> og framlegge"),
  "#:~:text=skal%20gjennomg%C3%A5-,denne%20forordnings%20virkem%C3%A5te,-og%20framlegge&text=denne%20forordnings%20virkem%C3%A5te");
'''
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    assert 'matchFragment: matchedTextFragment(result.excerpt)' in page
    assert '(law.matchFragment || "")' in page
