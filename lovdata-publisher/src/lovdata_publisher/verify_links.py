"""Post-render internal link integrity check over the built site.

The dead-link class this repo kept meeting was only ever found incidentally:
an emitter reconstructed a path into another generator's namespace, the
target did not exist, and nobody noticed until a human clicked it. This
module turns the class into a deploy-time failure: after everything has
rendered into _site/, walk every HTML and Atom document, resolve every
internal href/src against the files that actually exist, and fail the run
on any miss. New emitters cannot reintroduce the bug silently.

Checked: <a href>, <link href>, <script src>, <img src> in HTML; <link>
elements and href attributes in feeds/*.xml; every <loc> in sitemap.xml.
Skipped: external URLs, mailto:, data:, pure fragments. Fragments and
query strings are stripped before resolution; a directory target resolves
to its index.html.
"""
from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

SITE_PREFIXES = (
    "https://sondreskarsten.github.io/norwegian-laws",
    "/norwegian-laws",
)

HREF_RE = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
XML_HREF_RE = re.compile(r"""href=["']([^"']+)["']""")


def _internalize(url: str) -> str | None:
    """Return a site-root-relative path for internal URLs, else None."""
    url = url.strip()
    if not url or url.startswith(("#", "mailto:", "data:", "javascript:", "tel:")):
        return None
    # Template placeholders inside inline <script> (sok/diff/abonner build
    # hrefs client-side) are not real references.
    if any(c in url for c in ("$", "{", "}", "'", '"', " ", "\\")):
        return None
    for p in SITE_PREFIXES:
        if url.startswith(p):
            # Prefix-stripped URLs are site-root-relative regardless of where
            # the referencing document lives; keep the leading slash so the
            # resolver anchors them at the site root.
            return "/" + url[len(p):].lstrip("/")
    if url.startswith(("http://", "https://", "//")):
        return None
    return url


def _resolve(site: Path, source: Path, target: str) -> Path:
    target = urllib.parse.unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return source
    base = site if target.startswith("/") else source.parent
    p = (base / target.lstrip("/")).resolve()
    if p.is_dir():
        p = p / "index.html"
    return p


def verify_site(site_dir: str = "_site") -> list[str]:
    site = Path(site_dir).resolve()
    failures: list[str] = []
    seen: set[tuple[str, str]] = set()

    def check(source: Path, raw: str) -> None:
        rel = _internalize(raw)
        if rel is None:
            return
        resolved = _resolve(site, source, rel)
        key = (str(source.relative_to(site)), str(resolved))
        if key in seen:
            return
        seen.add(key)
        if site not in resolved.parents and resolved != site:
            failures.append(f"{key[0]} -> {raw} escapes site root")
        elif not resolved.exists():
            failures.append(f"{key[0]} -> {raw}")

    for f in site.rglob("*.html"):
        for m in HREF_RE.finditer(f.read_text(encoding="utf-8", errors="replace")):
            check(f, m.group(1))

    feeds = site / "feeds"
    xml_sources = list(feeds.glob("*.xml")) if feeds.is_dir() else []
    if (site / "feed.xml").exists():
        xml_sources.append(site / "feed.xml")
    for f in xml_sources:
        for m in XML_HREF_RE.finditer(f.read_text(encoding="utf-8", errors="replace")):
            check(f, m.group(1))

    sm = site / "sitemap.xml"
    if sm.exists():
        for m in LOC_RE.finditer(sm.read_text(encoding="utf-8")):
            check(sm, m.group(1))

    return failures


def main() -> None:
    site_dir = sys.argv[1] if len(sys.argv) > 1 else "_site"
    failures = verify_site(site_dir)
    checked = len({s for s, _ in []})
    if failures:
        print(f"LINK INTEGRITY: {len(failures)} broken internal references")
        for f in failures[:80]:
            print("  ", f)
        if len(failures) > 80:
            print(f"   ... and {len(failures) - 80} more")
        sys.exit(1)
    print("LINK INTEGRITY: all internal references resolve")


if __name__ == "__main__":
    main()
