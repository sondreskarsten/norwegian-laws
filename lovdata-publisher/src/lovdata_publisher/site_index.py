"""Single source of truth for what the published site contains.

Every generator that emits a link into another generator's namespace must
resolve it through a SiteIndex instead of reconstructing the path from raw
data. Reconstruction is how the site accumulated dead links: emitters
assumed a page, feed, or historie file existed for every refid, ministry
string, or act in amendments.db, while the producers publish only for the
current corpus and use their own naming rules (korttittel slugs for
historie, manifest slugs for topic/ministry feeds).

The index is built once per publish run from the corpus on disk, then
enriched with the manifests the producers already return (historie map,
feeds manifest, amended-paragraph map). Resolution methods return a
root-relative path or None; ``link()`` renders an anchor when the target
exists and falls back to an external archive URL or plain text when it
does not, so a repealed law degrades to Lovdata's NLO namespace or the
law-history branch instead of a 404.
"""
from __future__ import annotations

import html
from pathlib import Path

GITHUB_BASE = "https://github.com/sondreskarsten/norwegian-laws"
LOVDATA = "https://lovdata.no/dokument"


def refid_to_stem(refid: str) -> str:
    return refid.replace("/", "-")


def stem_to_refid(stem: str) -> str:
    return stem.replace("lov-", "lov/", 1) if stem.startswith("lov-") else stem.replace("forskrift-", "forskrift/", 1)


class SiteIndex:
    def __init__(self, corpus: set[str] | None = None):
        self.corpus: set[str] = corpus or set()
        self.historie: dict[str, str] = {}
        self.feeds_laws: dict[str, str] = {}
        self.feeds_topics: dict[str, str] = {}
        self.feeds_ministries: dict[str, str] = {}
        self.paragraphs: dict[str, set[str]] = {}
        self.book_chapters: set[str] = set()

    @classmethod
    def build(cls, repo_root: str = ".") -> "SiteIndex":
        """Scan lover/ and forskrifter/ for the refids that actually publish."""
        root = Path(repo_root)
        corpus = set()
        for sub in ("lover", "forskrifter"):
            d = root / sub
            if not d.is_dir():
                continue
            for f in d.glob("*.md"):
                if f.name != "README.md":
                    corpus.add(stem_to_refid(f.stem))
        return cls(corpus)

    def attach_historie(self, historie_map: dict[str, str]) -> None:
        """historie_map: refid -> path relative to site root (historie/x.html)."""
        self.historie.update(historie_map or {})

    def attach_feeds(self, manifest: dict) -> None:
        """manifest as returned by feeds.generate_per_law_feeds."""
        if not manifest:
            return
        self.feeds_laws.update({r: m["path"] for r, m in manifest.get("laws", {}).items()})
        self.feeds_topics.update({t: m["path"] for t, m in manifest.get("topics", {}).items()})
        self.feeds_ministries.update({d: m["path"] for d, m in manifest.get("ministries", {}).items()})

    def attach_paragraphs(self, amended_map: dict[str, set]) -> None:
        self.paragraphs.update(amended_map or {})

    def attach_book_chapters(self, site_dir: str) -> None:
        """Register the chapter files quarto actually rendered into _site/book."""
        book = Path(site_dir) / "book"
        if book.is_dir():
            self.book_chapters = {f"book/{f.name}" for f in book.glob("*.html")}

    # --- resolution: root-relative path or None ---

    def doc_page(self, refid: str) -> str | None:
        if refid not in self.corpus:
            return None
        sub = "forskrifter" if refid.startswith("forskrift/") else "lover"
        return f"{sub}/{refid_to_stem(refid)}.html"

    def historie_page(self, refid: str) -> str | None:
        return self.historie.get(refid)

    def feed(self, refid: str) -> str | None:
        return self.feeds_laws.get(refid)

    def ministry_feed(self, ministry: str) -> str | None:
        return self.feeds_ministries.get(ministry)

    def topic_feed(self, topic: str) -> str | None:
        return self.feeds_topics.get(topic)

    def book_chapter(self, path: str) -> str | None:
        return path if path in self.book_chapters else None

    def para_page(self, refid: str, para: str) -> str | None:
        if para in self.paragraphs.get(refid, set()):
            return f"historikk/{refid_to_stem(refid)}/para-{para}.html"
        return None

    # --- external archives that exist regardless of gjeldende status ---

    @staticmethod
    def lovdata_act_url(refid: str) -> str:
        """Lovtidend page for an amendment act; exists for every published act."""
        return f"{LOVDATA}/LTI/{refid}"

    @staticmethod
    def lovdata_archive_url(refid: str) -> str:
        """Repealed documents move to Lovdata's NLO/SFO namespaces."""
        ns = "SFO" if refid.startswith("forskrift/") else "NLO"
        return f"{LOVDATA}/{ns}/{refid}"

    @staticmethod
    def law_history_url(refid: str) -> str:
        """Commit history on the law-history branch. Only documents in the
        CURRENT corpus have history there: build_history reconstructs from
        snapshot/laws, so repealed documents have no commits at any point.
        For repealed documents use lovdata_archive_url instead."""
        sub = "forskrifter" if refid.startswith("forskrift/") else "lover"
        return f"{GITHUB_BASE}/commits/law-history/{sub}/{refid_to_stem(refid)}.md"

    # --- rendering ---

    @staticmethod
    def link(path: str | None, text: str, base: str = "", fallback_url: str | None = None,
             title: str | None = None) -> str:
        """Anchor to a local target, else to a fallback URL, else escaped text."""
        t = html.escape(text)
        attrs = f' title="{html.escape(title)}"' if title else ""
        if path is not None:
            return f'<a href="{base}{path}"{attrs}>{t}</a>'
        if fallback_url:
            return f'<a href="{fallback_url}"{attrs}>{t}</a>'
        return t
