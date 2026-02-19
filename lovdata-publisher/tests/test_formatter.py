"""Tests for lovdata_publisher.formatter and git_export."""
from lovdata_publisher.formatter import (
    format_law_markdown,
    format_article,
    format_section,
    refid_to_filepath,
)
from lovdata_publisher.git_export import format_commit_message


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
                        {"identifier": "a)", "text": "norske foretak"},
                        {"identifier": "b)", "text": "utenlandske foretak"},
                    ],
                }
            ],
        }
        md = format_article(article, depth=1)
        assert "- a) norske foretak" in md
        assert "- b) utenlandske foretak" in md


# ─── format_commit_message ──────────────────────────────────────────────────

class TestFormatCommitMessage:
    """Test that commit messages include amendment details.

    The legacy format_commit_message includes an 'Endringer:' section listing
    each individual amendment (e.g. '  - §1: endret'). The refactored version
    must also include this when amendment data is available.
    """

    def test_includes_amendment_details(self):
        act_row = {
            "refid": "lov/2024-01-01-1",
            "title": "Testlov",
            "short_title": "Testlov",
            "date_in_force": "2024-06-01",
            "date_published": "2024-01-15",
            "ministry": "Testdepartementet",
            "changes_to": "lov/2020-01-01-5",
            "misc_info": "",
            "journal_number": "2024-0001",
            "amendments": [
                {"change_type": "change", "target": "lov/2020-01-01-5/§1"},
                {"change_type": "repeal", "target": "lov/2020-01-01-5/§2"},
            ],
        }
        msg = format_commit_message(act_row)
        assert "Endringer:" in msg, "Commit message should include 'Endringer:' section"
        assert "endret" in msg, "Should include 'endret' label for change type"
        assert "opphevet" in msg, "Should include 'opphevet' label for repeal type"

    def test_no_amendments_key_still_works(self):
        """When no amendments key is present, message should still work."""
        act_row = {
            "refid": "lov/2024-01-01-1",
            "title": "Testlov",
            "short_title": "Testlov",
            "date_in_force": "2024-06-01",
            "date_published": "2024-01-15",
            "ministry": "",
            "changes_to": "",
            "misc_info": "",
            "journal_number": "",
        }
        msg = format_commit_message(act_row)
        assert msg.startswith("Testlov")
        assert "Endringslov:" in msg

    def test_empty_amendments_list(self):
        """An empty amendments list should not produce an Endringer section."""
        act_row = {
            "refid": "lov/2024-01-01-1",
            "title": "Testlov",
            "short_title": "Testlov",
            "date_in_force": "2024-06-01",
            "date_published": "2024-01-15",
            "ministry": "",
            "changes_to": "",
            "misc_info": "",
            "journal_number": "",
            "amendments": [],
        }
        msg = format_commit_message(act_row)
        assert "Endringer:" not in msg


# ─── End-to-end: formatter handles interleaved text/list ────────────────────

class TestFormatterInterleavedOutput:
    """Test that the full parse→format pipeline preserves text/list ordering.

    When a legal paragraph has text → list → text, the formatted Markdown
    should show: text paragraph, then list items, then text paragraph.
    Not: merged text followed by list items.
    """

    def test_interleaved_roundtrip(self):
        """Paragraphs with split text/list produce correct Markdown output."""
        article = {
            "name": "§ 1",
            "header_text": "§ 1. Virkeområde",
            "paragraphs": [
                {"text": "Loven gjelder for:", "list_items": []},
                {
                    "text": "",
                    "list_items": [
                        {"identifier": "a)", "text": "norske foretak"},
                        {"identifier": "b)", "text": "utenlandske foretak"},
                    ],
                },
                {"text": "med virksomhet i Norge.", "list_items": []},
            ],
        }
        md = format_article(article, depth=1)
        # The text "Loven gjelder for:" must appear BEFORE the list items
        idx_text = md.index("Loven gjelder for:")
        idx_list = md.index("- a) norske foretak")
        idx_trailing = md.index("med virksomhet i Norge.")
        assert idx_text < idx_list < idx_trailing, (
            "Text before list must appear before list items, "
            "which must appear before trailing text"
        )
