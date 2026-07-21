"""Generate standalone per-law HTML pages and a full-text search index.

Reads `lover/*.md`, renders each to a standalone HTML page styled to match
the Quarto book (cosmo theme), and writes them to `_site/lover/*.html`.
Also extends `_site/search.json` with full-text entries pointing at the
per-law pages.

Run after `quarto render` and before deploying to gh-pages.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

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
<a href="../book/dept-{dept_slug}.html">{dept}</a> &raquo;
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
Tidligere versjoner finnes på <a href="../book/versjoner.html">versjonsoversikten</a>
eller direkte i <a href="{github_log}">git log</a>.
</div>

<div class="history-links">
<strong>Historikk:</strong>
<a href="{github_blob}">Kildefil</a> ·
<a href="{github_log}">git log</a> ·
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
        f'<a href="{GITHUB_BASE}/blob/{t}/lover/{filename}">{t}</a>'
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
    """Inject hyperlinks where law short titles appear in body text."""
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

    return pattern.sub(replace, html_body)


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


def strip_markdown_for_search(body: str, max_chars: int = 8000) -> str:
    text = re.sub(r"^#+ ", "", body, flags=re.MULTILINE)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
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
    if version_tags is None:
        import datetime
        version_tags = [f"v{y}" for y in range(2000, datetime.date.today().year + 3)]
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
                dept_slug=dept_slug(dept),
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


def merge_full_text_into_search(
    repo_root: str = ".",
    lover_dir: str = "lover",
    forskrifter_dir: str = "forskrifter",
    site_dir: str = "_site",
    laws_json: str = "laws.json",
) -> None:
    search_path = Path(repo_root) / site_dir / "search.json"
    laws_path = Path(repo_root) / laws_json

    if not search_path.exists():
        print(f"  {search_path} not found, skipping search index merge")
        return

    with open(search_path, encoding="utf-8") as f:
        search_entries = json.load(f)

    existing_count = len(search_entries)
    added_lover = 0
    added_forskrift = 0

    # Index lover/*.md by refid via laws.json (existing logic)
    if laws_path.exists():
        with open(laws_path, encoding="utf-8") as f:
            laws = json.load(f)
        laws_by_file = {law["file"]: law for law in laws}
        lover_path = Path(repo_root) / lover_dir
        for md_file in sorted(lover_path.glob("*.md")):
            law = laws_by_file.get(md_file.name)
            if not law:
                continue
            meta, body = parse_frontmatter_and_body(md_file)
            if not meta:
                continue
            body_text = strip_markdown_for_search(body)
            depts = law.get("departement", [])
            dept_str = ", ".join(depts) if isinstance(depts, list) else str(depts)
            href = f"lover/{md_file.stem}.html"
            title = law.get("tittel", meta.get("tittel", ""))
            korttittel = law.get("korttittel", meta.get("korttittel", ""))
            text_parts = [korttittel, dept_str, law.get("refid", ""), law.get("ikrafttredelse", ""), body_text]
            text = " ".join(p for p in text_parts if p)
            search_entries.append({
                "objectID": f"law:{md_file.name}",
                "href": href,
                "title": title,
                "section": dept_str,
                "text": text,
            })
            added_lover += 1

    # Index forskrifter/*.md directly from frontmatter (no laws.json equivalent yet)
    forskrifter_path = Path(repo_root) / forskrifter_dir
    if forskrifter_path.exists():
        for md_file in sorted(forskrifter_path.glob("*.md")):
            meta, body = parse_frontmatter_and_body(md_file)
            if not meta:
                continue
            body_text = strip_markdown_for_search(body)
            dept_str = meta.get("departement", "")
            href = f"forskrifter/{md_file.stem}.html"
            title = meta.get("tittel", md_file.stem)
            korttittel = meta.get("korttittel", "")
            text_parts = [korttittel, dept_str, meta.get("refid", ""), meta.get("ikrafttredelse", ""), body_text]
            text = " ".join(p for p in text_parts if p)
            search_entries.append({
                "objectID": f"forskrift:{md_file.name}",
                "href": href,
                "title": title,
                "section": dept_str,
                "text": text,
            })
            added_forskrift += 1

    with open(search_path, "w", encoding="utf-8") as f:
        json.dump(search_entries, f, ensure_ascii=False)

    print(f"  Search index: {existing_count} → {len(search_entries)} entries (+{added_lover} lover, +{added_forskrift} forskrifter)")


if __name__ == "__main__":
    generate_per_law_pages()
    merge_full_text_into_search()
