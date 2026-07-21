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
