"""Tests for lovdata_publisher.formatter."""
from lovdata_publisher.formatter import (
    format_law_markdown,
    format_article,
    format_section,
    refid_to_filepath,
)


class TestRefidToFilepath:
    def test_standard(self):
        assert refid_to_filepath("lov/1998-07-17-56") == "lover/lov-1998-07-17-56.md"


class TestFormatLawMarkdown:
    def test_basic_law(self):
        law = {
            "refid": "lov/2024-01-01-1",
            "title": "Testlov om testing",
            "short_title": "Testloven",
            "ministry": "Testdepartementet",
            "date_in_force": "2024-06-01",
            "last_amended": "lov/2024-06-01-5",
            "last_amended_in_force": "2024-07-01",
            "legal_area": "Test",
            "sections": [
                {
                    "heading": "Kapittel 1. Virkeområde",
                    "articles": [
                        {
                            "name": "§ 1",
                            "header_text": "§ 1. Lovens formål",
                            "paragraphs": [
                                {"text": "Denne lov har som formål å teste.", "list_items": []}
                            ],
                        }
                    ],
                }
            ],
            "top_level_articles": [],
        }
        md = format_law_markdown(law)
        assert 'refid: "lov/2024-01-01-1"' in md
        assert 'sist-endret: "lov/2024-06-01-5"' in md
        assert "## Kapittel 1. Virkeområde" in md
        assert "#### § 1. Lovens formål" in md
        assert "Denne lov har som formål å teste." in md

    def test_deterministic(self):
        """Same input must produce identical output."""
        law = {
            "refid": "lov/2024-01-01-1",
            "title": "Test",
            "sections": [],
            "top_level_articles": [],
        }
        md1 = format_law_markdown(law)
        md2 = format_law_markdown(law)
        assert md1 == md2

    def test_no_optional_fields(self):
        """Missing optional fields should not crash."""
        law = {
            "refid": "lov/2024-01-01-1",
            "title": "Minimal lov",
            "sections": [],
            "top_level_articles": [],
        }
        md = format_law_markdown(law)
        assert "---" in md
        assert "# Minimal lov" in md
        assert "sist-endret" not in md


class TestFormatArticle:
    def test_with_list_items(self):
        article = {
            "name": "§ 1",
            "header_text": "§ 1. Formål",
            "paragraphs": [
                {
                    "text": "Loven gjelder for:",
                    "list_items": [
                        {"marker": "a)", "paragraphs": [{"text": "norske foretak"}]},
                        {"marker": "b)", "paragraphs": [{"text": "utenlandske foretak"}]},
                    ],
                }
            ],
        }
        md = format_article(article, depth=1)
        assert "a) norske foretak" in md
        assert "b) utenlandske foretak" in md
        assert "- a)" not in md


class TestFormatArticleTrailingText:
    def test_trailing_text_renders_after_list(self):
        article = {
            "name": "§ 1",
            "header_text": "§ 1. Formål",
            "paragraphs": [
                {
                    "text": "Loven gjelder for:",
                    "list_items": [
                        {"marker": "a)", "paragraphs": [{"text": "norske foretak"}]},
                    ],
                    "trailing_text": "med virksomhet i Norge.",
                }
            ],
        }
        md = format_article(article, depth=1)
        intro = md.index("Loven gjelder for:")
        item = md.index("a) norske foretak")
        trail = md.index("med virksomhet i Norge.")
        assert intro < item < trail
