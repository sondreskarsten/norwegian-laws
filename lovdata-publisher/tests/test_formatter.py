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


class TestFormatAllLawsPruning:
    def _snapshot(self, tmp_path, laws=(), forskrifter=()):
        import json
        snap = tmp_path / "snapshot"
        for sub, items in [("laws", laws), ("forskrifter", forskrifter)]:
            d = snap / sub
            d.mkdir(parents=True)
            for refid, title in items:
                (d / f"{refid.replace('/', '-')}.json").write_text(
                    json.dumps({"refid": refid, "title": title, "sections": []}),
                    encoding="utf-8",
                )
        return snap

    def test_prunes_md_absent_from_snapshot(self, tmp_path):
        from lovdata_publisher.formatter import format_all_laws

        snap = self._snapshot(
            tmp_path,
            laws=[("lov/2020-01-01-1", "Ny lov")],
            forskrifter=[("forskrift/2021-02-02-2", "Ny forskrift")],
        )
        out = tmp_path / "out"
        (out / "lover").mkdir(parents=True)
        (out / "forskrifter").mkdir(parents=True)
        (out / "lover" / "lov-1985-06-21-78.md").write_text("stale", encoding="utf-8")
        (out / "forskrifter" / "forskrift-1960-06-02-1.md").write_text("stale", encoding="utf-8")
        (out / "lover" / "README.md").write_text("keep", encoding="utf-8")

        results = format_all_laws(str(snap), str(out))

        assert not (out / "lover" / "lov-1985-06-21-78.md").exists()
        assert not (out / "forskrifter" / "forskrift-1960-06-02-1.md").exists()
        assert (out / "lover" / "README.md").exists()
        assert (out / "lover" / "lov-2020-01-01-1.md").exists()
        assert "lov/2020-01-01-1" in results

    def test_partial_snapshot_does_not_wipe_other_corpus(self, tmp_path):
        from lovdata_publisher.formatter import format_all_laws

        snap = self._snapshot(tmp_path, laws=[("lov/2020-01-01-1", "Ny lov")])
        out = tmp_path / "out"
        (out / "forskrifter").mkdir(parents=True)
        (out / "forskrifter" / "forskrift-1960-06-02-1.md").write_text("keep", encoding="utf-8")

        format_all_laws(str(snap), str(out))

        assert (out / "forskrifter" / "forskrift-1960-06-02-1.md").exists()
