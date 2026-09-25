"""Generate standalone per-law HTML pages and a full-text search index.

Reads `lover/*.md`, renders each to a standalone HTML page styled to match
the Quarto book (cosmo theme), and writes them to `_site/lover/*.html`.
Also builds a chunked Pagefind index, loaded only when a reader explicitly
chooses full-text search. Default search stays metadata-only.

Run after `quarto render` and before deploying to gh-pages.
"""
from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from .legacy_versions import LEGACY_VERSION_REFS, supported_version_tags

try:
    import markdown as md
except ImportError:
    md = None

GITHUB_BASE = "https://github.com/sondreskarsten/norwegian-laws"
HISTORY_BRANCH = "law-history"
SITE_BASE = "https://sondreskarsten.github.io/norwegian-laws"

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Norges Lover</title>
<meta name="description" content="Gjeldende konsolidert tekst av {title}. Sist endret: {sist_endret}. Med endringshistorikk og Atom-feed for oppdateringer.">
<meta property="og:site_name" content="Norges Lover"/>
<meta property="og:type" content="article"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="Gjeldende konsolidert tekst med endringshistorikk siden 2001."/>
<meta property="og:url" content="https://sondreskarsten.github.io/norwegian-laws/{output_subdir}/{filename_html}"/>
<meta property="og:image" content="https://sondreskarsten.github.io/norwegian-laws/assets/banner.svg"/>
<meta name="twitter:card" content="summary"/>
<meta name="twitter:title" content="{title}"/>
<meta name="twitter:description" content="Norsk lov, oppdatert konsolidert tekst. Sist endret {sist_endret}."/>
<meta name="twitter:image" content="https://sondreskarsten.github.io/norwegian-laws/assets/banner.svg"/>
<link rel="icon" type="image/svg+xml" href="/norwegian-laws/assets/favicon.svg"/>
<link rel="canonical" href="https://sondreskarsten.github.io/norwegian-laws/{output_subdir}/{filename_html}"/>
{feed_autodiscovery}
<style>
body {{ max-width: 960px; margin: 0 auto; padding: 1.5rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #212529; }}
nav.breadcrumb {{ background: #f8f9fa; padding: 0.5rem 1rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.9rem; }}
nav.breadcrumb a {{ color: #2780e3; text-decoration: none; }}
nav.breadcrumb a:hover {{ text-decoration: underline; }}
.metadata {{ background: #f8f9fa; border-left: 3px solid #2780e3; padding: 0.75rem 1rem; margin: 1rem 0; font-size: 0.9rem; }}
.metadata dt {{ font-weight: 600; margin-top: 0.25rem; }}
.metadata dd {{ margin-left: 0; }}
.history-links {{ margin: 1rem 0; padding: 0.75rem; background: #fff3cd; border-radius: 4px; }}
.history-links a {{ margin-right: 0.5rem; }}
.version-banner {{ margin: 1rem 0; padding: 0.5rem 0.75rem; background: #e7f5ff; border-left: 3px solid #2780e3; border-radius: 4px; font-size: 0.9rem; }}
.version-banner a {{ color: #1864ab; }}
h1, h2, h3, h4, h5, h6 {{ margin-top: 1.25em; margin-bottom: 0.5em; }}
h1 {{ font-size: 1.75rem; border-bottom: 2px solid #dee2e6; padding-bottom: 0.3rem; }}
h2 {{ font-size: 1.5rem; color: #495057; }}
h3 {{ font-size: 1.25rem; }}
h4 {{ font-size: 1.1rem; color: #495057; }}
em {{ color: #6c757d; font-size: 0.95em; }}
ul li {{ margin-bottom: 0.25rem; }}
footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 0.85rem; }}
.search-link {{ float: right; }}
</style>
</head>
<body>
<nav class="breadcrumb">
<a href="../index.html">Norges Lover</a> &raquo;
{dept_links} &raquo;
<span>{korttittel_short}</span>
<span class="search-link"><a href="../book/sok.html">Søk</a></span>
</nav>

<div class="metadata">
<dl>
<dt>Refid</dt><dd><code>{refid}</code></dd>
<dt>Departement</dt><dd>{dept}</dd>
<dt>Rettsområde</dt><dd>{rettsomrade}</dd>
<dt>Ikrafttredelse</dt><dd>{ikrafttredelse}</dd>
<dt>Sist endret</dt><dd>{sist_endret}</dd>
<dt>Kilde</dt><dd><a href="{lovdata_url}" target="_blank" rel="noopener">lovdata.no</a></dd>
</dl>
</div>

<div class="version-banner">
Du leser den <strong>gjeldende konsoliderte teksten</strong>. Sist endret: {sist_endret}.
<strong>Eksperimentell historikk:</strong> Eldre utgaver er uverifiserte rekonstruksjoner.
De dokumenterer ikke sikkert hvilke regler som gjaldt på en bestemt dato.
Se <a href="../book/versjoner.html">versjonsoversikten</a> eller
<a href="{github_log}">git-loggen for rekonstruksjonene</a>.
</div>

<div class="history-links">
<strong>Kilder og historikk:</strong>
<a href="{github_blob}">Kildefil</a> ·
<a href="{github_log}">Git-logg (uverifisert rekonstruksjon)</a> ·
{feed_link_html}
{historie_link}{version_links}
</div>

{body}

<footer>
Datakilde: <a href="https://lovdata.no/" target="_blank" rel="noopener">Lovdata</a>
under <a href="https://data.norge.no/nlod/no/2.0" target="_blank" rel="noopener">NLOD 2.0</a>.
Generert fra <a href="{github_blob}">{filename}</a>.
Ikke autoritativ — se Lovdata for gjeldende tekst.
</footer>

</body>
</html>
"""


def parse_frontmatter_and_body(filepath: Path) -> tuple[dict, str]:
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5:]
    meta = {}
    for line in fm_text.splitlines():
        m = re.match(r'^([^:]+):\s*"?(.*?)"?\s*$', line)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip()
    return meta, body


def dept_slug(dept: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", dept).strip().replace(" ", "-").lower()
    return safe


def compute_version_links_html(refid: str, version_tags: list[str], filename: str) -> str:
    if not refid.startswith("lov/"):
        return ""
    version_tags = supported_version_tags(version_tags)
    refid_year = int(refid.split("/")[1][:4])
    relevant_tags = []
    for tag in version_tags:
        tag_year = int(tag[1:])
        if tag_year >= refid_year:
            relevant_tags.append(tag)
    if len(relevant_tags) > 6:
        step = len(relevant_tags) // 6
        relevant_tags = relevant_tags[::step][:6] + [relevant_tags[-1]]
        relevant_tags = list(dict.fromkeys(relevant_tags))
    return " ".join(
        f'<a href="{GITHUB_BASE}/blob/{LEGACY_VERSION_REFS[t]}/lover/{filename}" title="Uverifisert rekonstruksjon">{t}</a>'
        for t in relevant_tags
    )


def build_korttittel_index(lover_path: Path) -> dict[str, str]:
    """Map lowercase korttittel → relative href to per-law page."""
    index = {}
    for md_file in sorted(lover_path.glob("*.md")):
        meta, _ = parse_frontmatter_and_body(md_file)
        if not meta:
            continue
        korttittel = meta.get("korttittel", "")
        if not korttittel:
            continue
        parts = re.split(r"\s+[–-]\s+", korttittel)
        href = f"{md_file.stem}.html"
        for part in parts:
            key = part.strip().lower()
            if len(key) > 4 and key.endswith(("loven", "lova")):
                index[key] = href
    return index


def build_cross_reference_pattern(korttittel_index: dict[str, str]):
    if not korttittel_index:
        return None
    keys = sorted(korttittel_index.keys(), key=len, reverse=True)
    alternation = "|".join(re.escape(k) for k in keys)
    pattern = re.compile(rf"\b({alternation})\b", re.IGNORECASE)
    return pattern


def insert_cross_reference_links(html_body: str, korttittel_index: dict[str, str], pattern, current_stem: str) -> str:
    """Link first mentions in text nodes without rewriting HTML or existing links."""
    if pattern is None:
        return html_body
    seen = set()

    def replace(match):
        key = match.group(1).lower()
        href = korttittel_index.get(key)
        if not href or href == f"{current_stem}.html":
            return match.group(0)
        if key in seen:
            return match.group(0)
        seen.add(key)
        return f'<a href="{href}">{match.group(1)}</a>'

    # Keep the original markup byte-for-byte. In particular, heading IDs often
    # contain the same law names as their text and must never receive anchors.
    line_offsets = [0] + [match.end() for match in re.finditer("\n", html_body)]
    edits = []

    class TextNodeLinker(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.protected = []

        def handle_starttag(self, tag, attrs):
            if tag in {"a", "script", "style", "code", "pre", "textarea", "title"}:
                self.protected.append(tag)

        def handle_endtag(self, tag):
            if tag in self.protected:
                last = len(self.protected) - 1 - self.protected[::-1].index(tag)
                del self.protected[last:]

        def handle_data(self, data):
            if self.protected:
                return
            linked = pattern.sub(replace, data)
            if linked != data:
                line, column = self.getpos()
                start = line_offsets[line - 1] + column
                edits.append((start, start + len(data), linked))

    parser = TextNodeLinker()
    parser.feed(html_body)
    parser.close()
    parts = []
    cursor = 0
    for start, end, linked in edits:
        parts.extend((html_body[cursor:start], linked))
        cursor = end
    parts.append(html_body[cursor:])
    return "".join(parts)


def render_markdown_body(body: str) -> str:
    if md is None:
        body_html = body
        body_html = re.sub(r"^###### (.+)$", r"<h6>\1</h6>", body_html, flags=re.MULTILINE)
        body_html = re.sub(r"^##### (.+)$", r"<h5>\1</h5>", body_html, flags=re.MULTILINE)
        body_html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", body_html, flags=re.MULTILINE)
        body_html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", body_html, flags=re.MULTILINE)
        body_html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body_html, flags=re.MULTILINE)
        body_html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", body_html, flags=re.MULTILINE)
        body_html = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", body_html)
        return body_html
    return md.markdown(body, extensions=["extra", "toc"])


def inject_paragraph_history_links(body_html: str, law_stem: str, amended_paragraphs: set[str]) -> str:
    """Append a small 'history' link to each paragraph header that has been
    amended. Looks for <h4 id="X-Y-...">§ X-Y. Title</h4> and rewrites to
    <h4 id="...">§ X-Y. Title <a class="para-history" href="...">history</a></h4>.

    Only paragraphs in `amended_paragraphs` get a link, since we only generate
    paragraph-history pages for amended paragraphs.
    """
    if not amended_paragraphs:
        return body_html

    def replacer(match):
        tag = match.group(1)        # h4 or h5
        anchor_id = match.group(2)   # 1-2a-regnskapspliktige-...
        rest = match.group(3)        # § 1-2a. Regnskapspliktige...

        # Extract paragraph number from the heading text
        m = re.match(r"§\s*(\d+[-–]\d+[a-z]?)", rest)
        if not m:
            return match.group(0)
        para = f"§ {m.group(1)}"
        if para not in amended_paragraphs:
            return match.group(0)

        # Slug must match paragraph_history._paragraph_slug
        para_slug = "para-" + re.sub(r'[^a-z0-9-]', '', para.lower().replace("§", "").strip().replace(" ", ""))
        link = (
            f' <a class="para-history" href="../historikk/{law_stem}/{para_slug}.html" '
            f'title="Endringshistorikk for {para}" style="font-size:0.75em;font-weight:normal;'
            f'color:#2780e3;text-decoration:none;padding-left:0.4em;">⧉ historikk</a>'
        )
        return f'<{tag} id="{anchor_id}">{rest}{link}</{tag}>'

    # Match h4 or h5 with id="..." and content starting with § X-Y
    pattern = re.compile(
        r'<(h[45])\s+id="([^"]+)">(§\s*\d+[-–]\d+[a-z]?\..+?)</\1>',
        re.DOTALL,
    )
    return pattern.sub(replacer, body_html)


def strip_markdown_for_search(body: str, max_chars: int | None = 8000) -> str:
    text = re.sub(r"^#+ ", "", body, flags=re.MULTILINE)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    if "<" in text or "&" in text:
        from bs4 import BeautifulSoup
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars]
    return text


def generate_per_law_pages(
    repo_root: str = ".",
    lover_dir: str = "lover",
    forskrifter_dir: str = "forskrifter",
    site_dir: str = "_site",
    version_tags: list[str] | None = None,
    historie_map: dict[str, str] | None = None,
    amended_paragraphs_map: dict[str, set[str]] | None = None,
    site_index=None,
) -> int:
    version_tags = supported_version_tags(version_tags)
    if historie_map is None:
        historie_map = {}
    if amended_paragraphs_map is None:
        amended_paragraphs_map = {}

    count = 0
    for source_subdir, output_subdir in [(lover_dir, "lover"), (forskrifter_dir, "forskrifter")]:
        src_path = Path(repo_root) / source_subdir
        if not src_path.exists():
            continue
        out_dir = Path(repo_root) / site_dir / output_subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        korttittel_index = build_korttittel_index(src_path)
        xref_pattern = build_cross_reference_pattern(korttittel_index)

        for md_file in sorted(src_path.glob("*.md")):
            meta, body = parse_frontmatter_and_body(md_file)
            if not meta:
                continue

            tittel = meta.get("tittel", md_file.stem)
            korttittel = meta.get("korttittel", "")
            refid = meta.get("refid", "")
            dept = meta.get("departement", "").split(",")[0].strip()
            ikrafttredelse = meta.get("ikrafttredelse", "")
            sist_endret = meta.get("sist-endret", "")
            rettsomrade = meta.get("rettsomrade", "").replace(">", " &raquo; ").replace("\n", " · ")

            if not dept:
                dept = "Ukjent"

            body_html = render_markdown_body(body)
            body_html = insert_cross_reference_links(body_html, korttittel_index, xref_pattern, md_file.stem)
            # Append a small "history" link next to each amended paragraph header
            amended = amended_paragraphs_map.get(refid, set())
            if amended:
                body_html = inject_paragraph_history_links(body_html, md_file.stem, amended)
            filename = md_file.name
            if refid.startswith("forskrift/"):
                github_blob = f"{GITHUB_BASE}/blob/main/forskrifter/{filename}"
                github_log = f"{GITHUB_BASE}/commits/{HISTORY_BRANCH}/forskrifter/{filename}"
                lovdata_doc_url = f"https://lovdata.no/dokument/SF/{refid}"
            else:
                github_blob = f"{GITHUB_BASE}/blob/main/lover/{filename}"
                github_log = f"{GITHUB_BASE}/commits/{HISTORY_BRANCH}/lover/{filename}"
                lovdata_doc_url = f"https://lovdata.no/dokument/NL/{refid}"
            version_links = compute_version_links_html(refid, version_tags, filename)
            feed_path = site_index.feed(refid) if site_index is not None else f"feeds/{md_file.stem}.xml"
            if feed_path:
                feed_autodiscovery = (
                    f'<link rel="alternate" type="application/atom+xml" '
                    f'title="Endringer i {korttittel or tittel[:50]}" href="../{feed_path}">'
                )
                feed_link_html = (
                    f'<a href="../{feed_path}" title="Abonner p\u00e5 endringer i denne loven via Atom">'
                    f'\U0001F4E1 Atom-feed</a> \u00b7'
                )
            else:
                feed_autodiscovery = (
                    '<link rel="alternate" type="application/atom+xml" '
                    'title="Norges Lover \u2014 alle endringer" href="../feed.xml">'
                )
                feed_link_html = (
                    '<a href="../feed.xml" title="Ingen endringer registrert siden 2001 \u2014 '
                    'abonner p\u00e5 den globale feeden">\U0001F4E1 Atom-feed (alle)</a> \u00b7'
                )
            from .quarto import split_departments
            _parts = [d for d in split_departments(dept) if d.strip()] or ([dept] if dept else [])
            _prefix = "forskrift-dept" if refid.startswith("forskrift/") else "dept"
            _dept_anchors = []
            for _d in _parts:
                _chap = f"book/{_prefix}-{dept_slug(_d)}.html"
                if site_index is not None and site_index.book_chapter(_chap):
                    _dept_anchors.append(f'<a href="../{_chap}">{_d}</a>')
                elif site_index is None:
                    _dept_anchors.append(f'<a href="../{_chap}">{_d}</a>')
                else:
                    _dept_anchors.append(_d)
            dept_links = " \u00b7 ".join(_dept_anchors) if _dept_anchors else "\u2014"
            historie_url = historie_map.get(refid, "")
            historie_link = (
                f'<a href="../{historie_url}" title="Endringshistorikk per paragraf siden 2001">📜 Endringshistorikk</a> · '
                if historie_url else ""
            )

            html = PAGE_TEMPLATE.format(
                title=tittel,
                korttittel_short=korttittel or tittel[:50],
                refid=refid,
                dept=dept,
                dept_links=dept_links,
                rettsomrade=rettsomrade or "—",
                ikrafttredelse=ikrafttredelse or "—",
                sist_endret=sist_endret or "—",
                github_blob=github_blob,
                github_log=github_log,
                feed_autodiscovery=feed_autodiscovery,
                feed_link_html=feed_link_html,
                lovdata_url=lovdata_doc_url,
                version_links=version_links,
                body=body_html,
                filename=filename,
                filename_html=f"{md_file.stem}.html",
                output_subdir=output_subdir,
                historie_link=historie_link,
            )

            out_file = out_dir / f"{md_file.stem}.html"
            out_file.write_text(html, encoding="utf-8")
            count += 1

    print(f"  Generated {count} per-law/forskrift HTML pages")
    return count


def _search_passages(text: str, size: int = 12000, overlap: int = 500):
    """Index every word, with overlap for phrases crossing passage boundaries.

    Bounded passages also bound Pagefind's downloaded result fragments for very
    long laws. Split on whitespace so no word is lost at either boundary.
    """
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary != -1:
                end = boundary
        yield text[start:end]
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
        boundary = text.find(" ", start, end)
        if boundary != -1:
            start = boundary + 1


def merge_full_text_into_search(
    repo_root: str = ".",
    lover_dir: str = "lover",
    forskrifter_dir: str = "forskrifter",
    site_dir: str = "_site",
    laws_json: str = "laws.json",
) -> None:
    """Build opt-in complete body search, retaining the post-render entry point.

    The Python API writes a static Pagefind bundle. The browser downloads only
    query-related index chunks and bounded result passages after explicit opt-in;
    Quarto's default search.json receives no legal body text.
    """
    import asyncio
    from html import escape
    from tempfile import TemporaryDirectory
    from pagefind.index import IndexConfig, PagefindIndex
    from .search_index import write_search_catalog

    output = Path(repo_root) / site_dir
    laws_path = Path(repo_root) / laws_json
    if not laws_path.exists():
        print(f"  {laws_path} not found, skipping full-text index")
        return
    laws = json.loads(laws_path.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)

    async def build_index(staging: Path):
        # A single directory call avoids one Python-service round trip per
        # passage. Staging URLs are private index identities; the UI resolves
        # refid through the catalog to the canonical reader page.
        async with PagefindIndex(config=IndexConfig(output_path=str(output / "pagefind"))) as index:
            result = await index.add_directory(str(staging))
            if result["page_count"] != passages:
                raise ValueError("Pagefind did not index every source passage")

    passages = 0
    with TemporaryDirectory(prefix=".pagefind-input-", dir=output.parent) as staging_dir:
        staging = Path(staging_dir)
        for law in laws:
            source_dir = forskrifter_dir if law.get("kind") == "forskrift" else lover_dir
            source = Path(repo_root) / source_dir / law["file"]
            _, body = parse_frontmatter_and_body(source)
            text = strip_markdown_for_search(body, max_chars=None)
            for number, passage in enumerate(_search_passages(text)):
                html = (
                    '<!doctype html><html lang="nb"><head><meta charset="utf-8">'
                    f'<meta data-pagefind-meta="refid[content]" content="{escape(law["refid"], quote=True)}">'
                    f'<title>{escape(law["tittel"])}</title></head><body>'
                    f'<h1>{escape(law["tittel"])}</h1>'
                    f'<main data-pagefind-body>{escape(passage)}</main></body></html>'
                )
                (staging / f"{source.stem}-part-{number}.html").write_text(html, encoding="utf-8")
                passages += 1
        print(f"  Indexing {passages} complete-text passages with Pagefind", flush=True)
        asyncio.run(build_index(staging))
    write_search_catalog(laws, output / "search-catalog.json", full_text={
        "module": "pagefind/pagefind.js", "documents": len(laws), "passages": passages,
    })
    print(f"  Opt-in full-text search: {len(laws)} documents, {passages} bounded passages")


if __name__ == "__main__":
    generate_per_law_pages()
    merge_full_text_into_search()
