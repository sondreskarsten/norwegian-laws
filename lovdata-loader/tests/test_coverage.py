import os
from dataclasses import asdict

from lovdata_loader.parser import parse_law
from lovdata_loader.coverage import law_coverage, model_tokens, source_tokens

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


class TestArchaicCompleteness:
    def test_pre1850_law_fully_captured(self):
        content = open(os.path.join(FIX, "fixture_archaic_law.xml"), "rb").read()
        law = asdict(parse_law(content))
        cov = law_coverage(content, law)
        assert cov["coverage"] == 1.0
        assert law["top_level_paragraphs"]
        body = " ".join(p["text"].lower() for p in law["top_level_paragraphs"])
        assert "skipper" in body


class TestHarness:
    def test_detects_missing_content(self):
        content = (
            b'<html><body><main class="documentBody">'
            b'<article class="legalP">alpha beta gamma delta</article>'
            b'</main></body></html>'
        )
        full = {"title": "", "top_level_paragraphs": [{"text": "alpha beta gamma delta"}]}
        partial = {"title": "", "top_level_paragraphs": [{"text": "alpha beta"}]}
        assert law_coverage(content, full)["coverage"] == 1.0
        assert law_coverage(content, partial)["coverage"] < 1.0

    def test_source_ignores_chrome(self):
        content = (
            b'<html><body><main class="documentBody">'
            b'<nav>navigasjon</nav><footer>bunntekst</footer>'
            b'<article class="legalP">innhold</article>'
            b'</main></body></html>'
        )
        src = source_tokens(content)
        assert src.get("innhold", 0) == 1
        assert "navigasjon" not in src
        assert "bunntekst" not in src

    def test_model_tokens_covers_every_field(self):
        law = {
            "title": "tittelord", "short_title": "kort",
            "sections": [{
                "heading": "overskrift", "preamble": ["forord"], "footnotes": ["fotnote"],
                "remainders": ["rest"], "subsections": [],
                "articles": [{
                    "name": "§1", "header_text": "hode", "trailing_text": "hale",
                    "remainders": ["arest"],
                    "paragraphs": [{"text": "ledd", "list_items": [
                        {"marker": "1.", "paragraphs": [{"text": "punkt"}]}]}],
                }],
            }],
            "top_level_articles": [], "top_level_paragraphs": [{"text": "toppledd"}],
            "remainders": ["lovrest"],
        }
        t = model_tokens(law)
        for w in ["tittelord", "kort", "overskrift", "forord", "fotnote", "rest",
                  "hode", "hale", "arest", "ledd", "punkt", "toppledd", "lovrest"]:
            assert t.get(w, 0) >= 1
