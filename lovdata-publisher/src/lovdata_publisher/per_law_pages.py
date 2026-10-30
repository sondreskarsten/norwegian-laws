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
:root {{ --ink: #1d2733; --muted: #5c6773; --rule: #d9dee3; --brand: #17365d; --link: #1a4d8f; --panel: #f4f6f8; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: var(--ink); background: #fff; }}
a {{ color: var(--link); }}
.topbar {{ background: var(--brand); color: #fff; }}
.topbar .inner {{ max-width: 1240px; margin: 0 auto; padding: 0.55rem 1rem; display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem 1.25rem; }}
.topbar .brand {{ color: #fff; font-weight: 700; text-decoration: none; font-size: 1.05rem; white-space: nowrap; }}
.topbar form {{ display: flex; flex: 1 1 260px; max-width: 520px; margin: 0; }}
.topbar input[type=search] {{ flex: 1; min-width: 0; padding: 0.4rem 0.6rem; border: 1px solid #0f2744; border-radius: 3px 0 0 3px; font-size: 0.95rem; }}
.topbar button {{ padding: 0.4rem 0.8rem; border: 1px solid #0f2744; border-left: 0; border-radius: 0 3px 3px 0; background: #e9eef5; color: var(--brand); font-weight: 600; cursor: pointer; }}
nav.breadcrumb {{ max-width: 1240px; margin: 0 auto; padding: 0.6rem 1rem 0; font-size: 0.9rem; color: var(--muted); }}
nav.breadcrumb a {{ text-decoration: none; }}
nav.breadcrumb a:hover {{ text-decoration: underline; }}
.page {{ max-width: 1240px; margin: 0 auto; padding: 0 1rem 2rem; display: grid; grid-template-columns: minmax(0, 1fr); gap: 0 2.5rem; }}
.doc {{ min-width: 0; max-width: 78ch; }}
h1.doc-title {{ font-size: 1.7rem; line-height: 1.25; margin: 0.9rem 0 0.4rem; }}
.doc-kind {{ color: var(--muted); font-size: 0.9rem; margin: 0; }}
table.keyinfo {{ border-collapse: collapse; width: 100%; margin: 1rem 0 1.25rem; font-size: 0.92rem; background: var(--panel); border: 1px solid var(--rule); }}
table.keyinfo th, table.keyinfo td {{ text-align: left; vertical-align: top; padding: 0.35rem 0.75rem; border-bottom: 1px solid var(--rule); }}
table.keyinfo th {{ width: 11rem; font-weight: 600; color: var(--muted); white-space: nowrap; }}
table.keyinfo tr:last-child th, table.keyinfo tr:last-child td {{ border-bottom: 0; }}
table.keyinfo code {{ font-size: 0.85em; color: var(--muted); }}
details.about {{ margin: 0 0 1.25rem; padding: 0.5rem 0.9rem; border: 1px solid var(--rule); border-radius: 3px; font-size: 0.9rem; background: #fff; }}
details.about summary {{ cursor: pointer; font-weight: 600; color: var(--brand); }}
details.about p {{ margin: 0.5rem 0; }}
.doc h1 {{ font-size: 1.45rem; border-bottom: 1px solid var(--rule); padding-bottom: 0.3rem; margin-top: 1.5rem; }}
.doc h2 {{ font-size: 1.3rem; margin-top: 2rem; color: var(--brand); }}
.doc h3 {{ font-size: 1.12rem; margin-top: 1.6rem; }}
.doc h4, .doc h5, .doc h6 {{ font-size: 1.02rem; margin-top: 1.4rem; margin-bottom: 0.35rem; }}
.doc p {{ margin: 0 0 0.75rem; }}
.doc ul li, .doc ol li {{ margin-bottom: 0.25rem; }}
.doc blockquote {{ margin: 0.75rem 0; padding-left: 0.9rem; border-left: 3px solid var(--rule); color: #2f3a45; }}
.doc .note {{ color: var(--muted); font-size: 0.84rem; margin: 0.15rem 0 1rem; }}
.doc .note em {{ font-style: normal; }}
a.para-history {{ font-size: 0.72rem; font-weight: normal; color: var(--link); text-decoration: none; padding-left: 0.5em; }}
aside.toc {{ display: none; }}
details.toc-mobile {{ margin: 0.75rem 0 1rem; border: 1px solid var(--rule); border-radius: 3px; padding: 0.4rem 0.8rem; font-size: 0.92rem; }}
details.toc-mobile summary {{ cursor: pointer; font-weight: 600; color: var(--brand); }}
.toc-list {{ list-style: none; margin: 0.4rem 0 0; padding: 0; }}
.toc-list li {{ margin: 0.15rem 0; }}
.toc-list li.lvl3, .toc-list li.lvl4, .toc-list li.lvl5 {{ padding-left: 0.9rem; }}
.toc-list li.lvl4, .toc-list li.lvl5 {{ padding-left: 1.8rem; font-size: 0.9em; }}
.toc-list a {{ text-decoration: none; }}
.toc-list a:hover {{ text-decoration: underline; }}
footer {{ max-width: 1240px; margin: 2rem auto 0; padding: 1rem 1rem 2rem; border-top: 1px solid var(--rule); color: var(--muted); font-size: 0.85rem; }}
@media (min-width: 992px) {{
  .page {{ grid-template-columns: 280px minmax(0, 1fr); }}
  aside.toc {{ display: block; position: sticky; top: 0; align-self: start; max-height: 100vh; overflow-y: auto; padding: 1rem 0.75rem 1rem 0; font-size: 0.88rem; border-right: 1px solid var(--rule); }}
  aside.toc h2 {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin: 0 0 0.5rem; }}
  details.toc-mobile {{ display: none; }}
}}
</style>
</head>
<body>
<div class="topbar"><div class="inner">
<a class="brand" href="../index.html">Norges Lover</a>
<form action="../book/sok.html" method="get" role="search">
<input type="search" name="q" placeholder="Søk i lover og forskrifter" aria-label="Søk i lover og forskrifter">
<button type="submit">Søk</button>
</form>
</div></div>
<nav class="breadcrumb">
<a href="../index.html">Norges Lover</a> &rsaquo;
{dept_links} &rsaquo;
<span>{korttittel_short}</span>
</nav>

<div class="page">
<aside class="toc" aria-label="Innhold">
<h2>Innhold</h2>
{toc_html}
</aside>

<article class="doc">
<p class="doc-kind">{doc_kind}</p>
<h1 class="doc-title">{title}</h1>

<table class="keyinfo">
<tr><th>Dato</th><td>{lovdata_code} <code>{refid}</code></td></tr>
<tr><th>Korttittel</th><td>{korttittel}</td></tr>
<tr><th>Departement</th><td>{dept}</td></tr>
<tr><th>Rettsområde</th><td>{rettsomrade}</td></tr>
<tr><th>Ikrafttredelse</th><td>{ikrafttredelse}</td></tr>
<tr><th>Sist endret</th><td>{sist_endret_display}</td></tr>
<tr><th>Kilde</th><td><a href="{lovdata_url}" target="_blank" rel="noopener">Dokumentet hos Lovdata</a></td></tr>
</table>

<details class="toc-mobile">
<summary>Innhold</summary>
{toc_html}
</details>

<details class="about">
<summary>Om denne utgaven, kilder og historikk</summary>
<p>Du leser den gjeldende konsoliderte teksten slik den sist ble hentet fra Lovdata. Eldre utgaver er uverifiserte rekonstruksjoner og dokumenterer ikke sikkert hvilke regler som gjaldt på en bestemt dato; se <a href="../book/versjoner.html">versjonsoversikten</a> eller <a href="{github_log}">git-loggen for rekonstruksjonene</a>.</p>
<p><a href="{github_blob}">Kildefil (Markdown)</a> ·
<a href="{github_log}">Git-logg (uverifisert rekonstruksjon)</a> ·
{feed_link_html}
{observed_link}{historie_link}{version_links}</p>
</details>

{body}
</article>
</div>

<footer>
Datakilde: <a href="https://lovdata.no/" target="_blank" rel="noopener">Lovdata</a>
under <a href="https://data.norge.no/nlod/no/2.0" target="_blank" rel="noopener">NLOD 2.0</a>.
Generert fra <a href="{github_blob}">{filename}</a>.
Ikke autoritativ — se Lovdata for gjeldende tekst.
</footer>

</body>
</html>
"""


_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_HEADING_RE = re.compile(r"<h([2-5])\b[^>]*\bid=\"([^\"]+)\"[^>]*>(.*?)</h\1>", re.S)


def format_no_date(value: str) -> str:
    """Write ISO dates the way Lovdata shows them: 01.01.1999. Other text is kept."""
    return _ISO_DATE_RE.sub(lambda m: f"{m.group(3)}.{m.group(2)}.{m.group(1)}", value or "")


def lovdata_code(refid: str) -> str:
    """Lovdata's document code: lov/1998-07-17-56 -> LOV-1998-07-17-56, forskrift/... -> FOR-..."""
    m = re.match(r"^(lov|forskrift)/(\d{4}-\d{2}-\d{2}(?:-\d+)?)$", refid or "")
    if not m:
        return refid or ""
    return ("LOV" if m.group(1) == "lov" else "FOR") + "-" + m.group(2)


def sist_endret_display(sist_endret: str, sist_endret_ikraft: str) -> str:
    if not sist_endret:
        return "—"
    code = lovdata_code(sist_endret)
    text = code if code == sist_endret else f"{code} <code>{sist_endret}</code>"
    if sist_endret_ikraft:
        text += f" fra {format_no_date(sist_endret_ikraft)}"
    return text


def build_toc_html(body_html: str) -> str:
    """A nested-looking list of the document's chapter and § headings."""
    items = []
    for level, anchor, inner in _HEADING_RE.findall(body_html):
        text = re.sub(r"<a class=\"para-history\".*?</a>", "", inner, flags=re.S)
        text = re.sub(r"<[^>]+>", "", text).strip()
        if not text:
            continue
        items.append(f'<li class="lvl{level}"><a href="#{anchor}">{text}</a></li>')
    if not items:
        return '<p class="doc-kind">Ingen inndeling.</p>'
    return '<ul class="toc-list">\n' + "\n".join(items) + "\n</ul>"


_NOTE_RE = re.compile(r"<p><em>((?:Endret|Endra|Tilføyd|Tilføyet|Opphevet|Oppheva|Endres|Oppheves) (?:ved|av) .*?)</em></p>", re.S)


def style_amendment_notes(body_html: str) -> str:
    """Lovdata's per-provision 'Endret ved lov ...' notes as small grey footnotes."""
    return _NOTE_RE.sub(lambda m: f'<p class="note">{m.group(1)}</p>', body_html)


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
            body_html = style_amendment_notes(body_html)
            # The document title is rendered by the page template; drop the
            # Markdown H1 so it is not shown twice.
            body_html = re.sub(r"^\s*<h1\b[^>]*>.*?</h1>\s*", "", body_html, count=1, flags=re.S)
            toc_html = build_toc_html(body_html)
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
                    f'Atom-feed</a> \u00b7'
                )
            else:
                feed_autodiscovery = (
                    '<link rel="alternate" type="application/atom+xml" '
                    'title="Norges Lover \u2014 alle endringer" href="../feed.xml">'
                )
                feed_link_html = (
                    '<a href="../feed.xml" title="Ingen endringer registrert siden 2001 \u2014 '
                    'abonner p\u00e5 den globale feeden">Atom-feed (alle)</a> \u00b7'
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
                f'<a href="../{historie_url}" title="Endringshistorikk per paragraf siden 2001">Endringshistorikk</a> · '
                if historie_url else ""
            )

            html = PAGE_TEMPLATE.format(
                title=tittel,
                korttittel_short=korttittel or tittel[:50],
                korttittel=korttittel or "—",
                refid=refid,
                lovdata_code=lovdata_code(refid),
                doc_kind="Forskrift" if refid.startswith("forskrift/") else "Lov",
                dept=dept,
                dept_links=dept_links,
                rettsomrade=rettsomrade or "—",
                ikrafttredelse=format_no_date(ikrafttredelse) or "—",
                sist_endret=sist_endret or "—",
                sist_endret_display=sist_endret_display(sist_endret, meta.get("sist-endret-ikrafttredelse", "")),
                toc_html=toc_html,
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
                observed_link=(site_index.link(site_index.observed_page(refid), "Observerte kildeutgaver", base="../") + " · "
                               if site_index is not None and site_index.observed_page(refid) else ""),
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
