"""Generate per-(law, paragraph) amendment history pages.

For each (target_law, paragraph) pair that has at least one amendment,
write a small HTML page listing every amendment with its date, instruction
preview, and a link to the changing act. URL: /historikk/{law-stem}/{§-slug}.html

Lets users link directly to "every change to § 7-25 in regnskapsloven"
instead of scrolling the full law historie page or filtering an Atom feed.
"""
from __future__ import annotations

import html
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SITE_BASE = "https://sondreskarsten.github.io/norwegian-laws"


_PARA_RE = re.compile(r'§\s*(\d+\s*[-–]\s*\d+(?:[a-z](?=$|[^a-zæøåA-ZÆØÅ]))?)')


def _normalize_paragraph(target: str, instruction: str = "") -> str:
    """Return canonical '§ X-Y' string, or empty if not a paragraph reference."""
    text = (target or "").strip()
    if not text or text.lower().startswith("kapittel") or text.lower().startswith("del "):
        m = _PARA_RE.search(instruction or "")
        if m:
            return f"§ {re.sub(r'\\s+', '-', m.group(1).strip())}"
        return ""
    # Use .search() (not .match()) so prefixed targets like
    # 'lov/1915-08-13-5/§217a' still extract '§ 2-17a' equivalents.
    m = _PARA_RE.search(text)
    if m:
        return f"§ {re.sub(r'\\s+', '-', m.group(1).strip())}"
    return ""


def _paragraph_slug(paragraph: str) -> str:
    """'§ 7-25' → 'para-7-25'."""
    return "para-" + re.sub(r'[^a-z0-9-]', '', paragraph.lower().replace("§", "").strip().replace(" ", ""))


def _refid_to_stem(refid: str) -> str:
    """'lov/1998-07-17-56' → 'lov-1998-07-17-56'."""
    return refid.replace("/", "-")


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{paragraph} — {law_title} — endringshistorikk</title>
<meta name="description" content="Alle endringer av {paragraph} i {law_title} siden 2001.">
<meta property="og:site_name" content="Norges Lover"/>
<meta property="og:type" content="article"/>
<meta property="og:title" content="{paragraph} {law_title} — endringshistorikk"/>
<meta property="og:description" content="{n_amendments} endringer registrert siden 2001."/>
<meta property="og:url" content="{canonical_url}"/>
<meta property="og:image" content="{site_base}/assets/banner.svg"/>
<meta name="twitter:card" content="summary"/>
<link rel="icon" type="image/svg+xml" href="/norwegian-laws/assets/favicon.svg"/>
<link rel="canonical" href="{canonical_url}"/>
{feed_autodiscovery}
<style>
body {{ max-width: 960px; margin: 0 auto; padding: 1.5rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #212529; }}
nav.breadcrumb {{ background: #f8f9fa; padding: 0.5rem 1rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.9rem; }}
nav.breadcrumb a {{ color: #2780e3; text-decoration: none; }}
nav.breadcrumb a:hover {{ text-decoration: underline; }}
h1 {{ font-size: 1.6rem; border-bottom: 2px solid #dee2e6; padding-bottom: 0.4rem; }}
.intro {{ background: #f8f9fa; border-left: 3px solid #2780e3; padding: 0.75rem 1rem; margin: 1rem 0; }}
.amendment {{ border: 1px solid #dee2e6; border-radius: 4px; padding: 0.75rem 1rem; margin: 0.8rem 0; }}
.amendment .meta {{ color: #6c757d; font-size: 0.85rem; margin-bottom: 0.3rem; }}
.amendment .title {{ font-weight: 600; }}
.amendment .instruction {{ font-style: italic; color: #495057; margin-top: 0.3rem; font-size: 0.9rem; }}
.amendment .new-text {{ margin-top: 0.5rem; }}
.amendment .new-text summary {{ cursor: pointer; color: #2780e3; font-size: 0.85rem; }}
.amendment .new-text-body {{ background: #f8f9fa; border-left: 3px solid #2780e3; padding: 0.6rem 0.9rem; margin-top: 0.4rem; font-size: 0.9rem; line-height: 1.5; color: #212529; }}
.current-text {{ background: #ffffff; border: 1px solid #dee2e6; border-radius: 4px; padding: 1rem 1.25rem; margin: 1.5rem 0; }}
.current-text.repealed {{ background: #fff3cd; border-color: #ffeeba; }}
.current-text.repealed h2 {{ color: #856404; }}
.current-text.removed {{ background: #f8f9fa; border-color: #dee2e6; }}
.current-text.removed h2 {{ color: #6c757d; font-size: 1rem; }}
.current-text h2 {{ margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #495057; }}
.current-text h2 .para-title {{ color: #212529; font-weight: 600; }}
.current-text-body {{ font-size: 0.95rem; line-height: 1.65; }}
.current-text-body p {{ margin: 0.5rem 0; }}
.amendment a {{ color: #2780e3; text-decoration: none; }}
.amendment a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<nav class="breadcrumb">
  <a href="../../">Norges Lover</a> ›
  {law_link} ›
{historie_crumb}
  {paragraph}
</nav>

<h1>{paragraph} — endringshistorikk</h1>

<div class="intro">
  <p style="margin:0;"><strong>{law_title}</strong></p>
  <p style="margin:0.4rem 0 0;">
{fulltext_link} ·
    {feed_link_html}
  </p>
</div>

{current_text_block}

<h2 style="margin-top:2rem;border-bottom:2px solid #dee2e6;padding-bottom:0.4rem;font-size:1.3rem;">Endringer</h2>

<p style="color:#6c757d;">{n_amendments} endring{plural} registrert siden 2001.</p>

{amendments_html}

{neighbor_nav}

<footer style="margin-top:3rem;padding-top:1rem;border-top:1px solid #dee2e6;color:#6c757d;font-size:0.85rem;">
  Generert {generated}. Kilde: Lovdata API (NLOD 2.0).
</footer>
</body>
</html>
"""


def generate_paragraph_history_pages(
    db_path: str = "snapshot/amendments.db",
    output_dir: str = "_site/historikk",
    min_amendments: int = 1,
    site_index: "SiteIndex | None" = None,
) -> tuple[int, dict[str, set[str]]]:
    """Build per-(law, paragraph) HTML pages.

    Returns (pages_written, {law_refid: {paragraphs_with_history_page}}). The
    second value lets the per-law page renderer add history links to amended
    paragraphs without duplicating the SQL.
    """
    from .site_index import SiteIndex
    index = site_index if site_index is not None else SiteIndex.build(".")
    amended: dict[str, set[str]] = {}
    if not Path(db_path).exists():
        print(f"  {db_path} not found, skipping paragraph history")
        return 0, amended

    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='amendments'"
    ).fetchone():
        print("  amendments table missing, skipping paragraph history")
        conn.close()
        return 0, amended

    rows = conn.execute(
        """
        SELECT a.target, a.target_law, a.instruction, a.change_type, a.new_text,
               ac.refid AS act_refid, ac.title AS act_title,
               ac.short_title AS act_short_title,
               ac.date_published, ac.date_in_force, ac.date_in_force_resolved,
               ac.ministry, ac.journal_number
        FROM amendments a
        LEFT JOIN amendment_acts ac ON a.act_refid = ac.refid
        WHERE a.target_law IS NOT NULL AND a.target_law != ''
              AND ac.date_published IS NOT NULL
        ORDER BY ac.date_published DESC, ac.refid DESC, a.id ASC
        """
    ).fetchall()

    # Group by (target_law, normalized_paragraph)
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        para = _normalize_paragraph(r["target"] or "", r["instruction"] or "")
        if not para:
            continue
        grouped[(r["target_law"], para)].append(dict(r))

    # Also need law titles for display
    law_titles: dict[str, str] = {}
    title_rows = conn.execute(
        "SELECT DISTINCT target_law FROM amendments WHERE target_law != ''"
    ).fetchall()
    conn.close()

    # Load titles from markdown frontmatter (no separate laws table)
    for kind, dir_name in [("lov", "lover"), ("forskrift", "forskrifter")]:
        src = Path(dir_name)
        if not src.is_dir():
            continue
        for md_file in src.glob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            try:
                fm_end = text.index("\n---", 4)
            except ValueError:
                continue
            fm = text[4:fm_end]
            meta = {}
            for line in fm.splitlines():
                m = re.match(r'(\S+?):\s*"(.+?)"\s*$', line)
                if m:
                    meta[m.group(1)] = m.group(2)
            refid = meta.get("refid")
            if refid:
                law_titles[refid] = meta.get("korttittel") or meta.get("tittel") or refid

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n_written = 0

    # Build paragraph anchor maps lazily, one per law
    from .feeds import _build_paragraph_anchor_map
    anchor_cache: dict[str, dict[str, str]] = {}

    def anchor_for(target_law: str, paragraph: str) -> str:
        if target_law not in anchor_cache:
            kind, _ = target_law.split("/", 1)
            dir_name = "lover" if kind == "lov" else "forskrifter"
            stem = _refid_to_stem(target_law)
            md_path = Path(dir_name) / f"{stem}.md"
            anchor_cache[target_law] = (
                _build_paragraph_anchor_map(md_path) if md_path.exists() else {}
            )
        return anchor_cache[target_law].get(paragraph, "")

    # Cache of (law_refid → parsed markdown body, paragraph_text_map)
    # paragraph_text_map: {'§ 7-25': '<p>(1) ...</p>...'}
    para_text_cache: dict[str, dict[str, str]] = {}

    def _build_paragraph_text_map(law_refid: str) -> dict[str, str]:
        """Extract each paragraph's body text from the law markdown.

        Returns {'§ X-Y': rendered_html}. Used so a paragraph history page
        can display the current text without forcing the reader to click
        through to the full law page and scroll.
        """
        kind, _ = law_refid.split("/", 1)
        dir_name = "lover" if kind == "lov" else "forskrifter"
        stem = _refid_to_stem(law_refid)
        md_path = Path(dir_name) / f"{stem}.md"
        if not md_path.exists():
            return {}
        text = md_path.read_text(encoding="utf-8")
        # Strip frontmatter
        if text.startswith("---"):
            try:
                fm_end = text.index("\n---", 4)
                text = text[fm_end + 4:]
            except ValueError:
                pass

        result: dict[str, str] = {}
        # Match "##### § X-Y. Title\n\nbody" up to next #### or ##### heading
        # Match "## § X-Y. Title\n\nbody" through to next H2-H6 paragraph header.
        # Norwegian laws use any of H2-H6 for paragraph headers depending on the
        # chapter/section structure (1,394 paragraphs are at H6, 6,486 at H5,
        # 15,197 at H4, 2,885 at H3). The previous {3,5} bound missed 1,394
        # H6-level paragraphs — caught by stress test 2026-05-20.
        header_re = re.compile(
            r'^(#{2,6})\s+(§\s*\d+[-–]\d+[a-z]?)\.?\s+([^\n]+)\n+(.*?)(?=^#{2,6}\s|\Z)',
            re.MULTILINE | re.DOTALL,
        )
        try:
            import markdown as md_lib
        except ImportError:
            md_lib = None

        for m in header_re.finditer(text):
            para_canonical = re.sub(r"§\s*(\d+)-(\d+)([a-z]?)", r"§ \1-\2\3", m.group(2)).strip()
            title_text = m.group(3).strip()
            body_text = m.group(4).rstrip()
            if para_canonical in result:
                continue
            # Render the body. Title is shown separately on the history page,
            # so don't include it here. Use markdown lib for proper paragraphs +
            # cross-refs; fall back to plain <pre> if markdown not installed.
            if md_lib is not None:
                rendered = md_lib.markdown(body_text, extensions=["extra"])
            else:
                rendered = "<pre>" + html.escape(body_text) + "</pre>"
            result[para_canonical] = (title_text, rendered)
        return result

    def current_text_for(law_refid: str, paragraph: str):
        if law_refid not in para_text_cache:
            para_text_cache[law_refid] = _build_paragraph_text_map(law_refid)
        return para_text_cache[law_refid].get(paragraph)

    # Precompute paragraph ordering per law so each history page can show
    # prev/next navigation. We use the canonical (chapter, paragraph,
    # letter-suffix) order, not the alphabetical slug order.
    def _para_sort_key(p: str) -> tuple:
        """'§ 7-25a' → (7, 25, 'a'). For prev/next, group by chapter, then number, then letter."""
        m = re.match(r'§\s*(\d+)-(\d+)([a-z]?)', p)
        if not m:
            return (9999, 9999, '')
        return (int(m.group(1)), int(m.group(2)), m.group(3) or '')

    paragraphs_per_law: dict[str, list[str]] = defaultdict(list)
    for (law_refid, paragraph), _ in grouped.items():
        if len(grouped[(law_refid, paragraph)]) >= min_amendments:
            paragraphs_per_law[law_refid].append(paragraph)
    for lr in paragraphs_per_law:
        paragraphs_per_law[lr].sort(key=_para_sort_key)

    def neighbor_nav(law_refid: str, paragraph: str, law_stem: str) -> str:
        plist = paragraphs_per_law.get(law_refid, [])
        try:
            i = plist.index(paragraph)
        except ValueError:
            return ""
        prev_link = next_link = ""
        if i > 0:
            prev_para = plist[i - 1]
            prev_slug = _paragraph_slug(prev_para)
            prev_link = (
                f'<a class="prev-para" href="{prev_slug}.html" '
                f'style="color:#2780e3;text-decoration:none;">'
                f'← {html.escape(prev_para)}</a>'
            )
        if i < len(plist) - 1:
            nxt_para = plist[i + 1]
            nxt_slug = _paragraph_slug(nxt_para)
            next_link = (
                f'<a class="next-para" href="{nxt_slug}.html" '
                f'style="color:#2780e3;text-decoration:none;">'
                f'{html.escape(nxt_para)} →</a>'
            )
        if not prev_link and not next_link:
            return ""
        return (
            f'<nav class="neighbor-nav" '
            f'style="display:flex;justify-content:space-between;margin:1.5rem 0 0;'
            f'padding:0.6rem 1rem;background:#f8f9fa;border-radius:4px;font-size:0.95rem;">'
            f'<span>{prev_link}</span>'
            f'<span>{next_link}</span>'
            f'</nav>'
        )

    for (law_refid, paragraph), amendments in grouped.items():
        if len(amendments) < min_amendments:
            continue

        amended.setdefault(law_refid, set()).add(paragraph)

        law_stem = _refid_to_stem(law_refid)
        law_title = law_titles.get(law_refid, law_refid)
        para_slug = _paragraph_slug(paragraph)
        para_anchor = anchor_for(law_refid, paragraph)

        # Subdir per law
        law_dir = out_root / law_stem
        law_dir.mkdir(parents=True, exist_ok=True)

        canonical_url = f"{SITE_BASE}/historikk/{law_stem}/{para_slug}.html"

        neighbor_nav_html = neighbor_nav(law_refid, paragraph, law_stem)

        current = current_text_for(law_refid, paragraph)
        if current:
            title_text, body_html = current
            current_text_block = (
                f'<section class="current-text">\n'
                f'  <h2>Gjeldende tekst — <span class="para-title">{html.escape(paragraph)}. {html.escape(title_text)}</span></h2>\n'
                f'  <div class="current-text-body">{body_html}</div>\n'
                f'</section>'
            )
        else:
            # Distinguish "law markdown doesn't exist" (repealed) from "law
            # exists but this specific paragraph isn't in it" (renumbered or
            # removed). Both deserve a status notice rather than silent
            # omission, so the reader knows why there's no current text.
            kind_dir = "lover" if law_refid.startswith("lov/") else "forskrifter"
            md_path = Path(kind_dir) / f"{law_stem}.md"
            if not md_path.exists():
                current_text_block = (
                    f'<section class="current-text repealed">\n'
                    f'  <h2>Loven/forskriften er ikke lenger i kraft</h2>\n'
                    f'  <p style="margin:0;color:#6c757d;">'
                    f'{html.escape(law_title)} finnes ikke som gjeldende lov/forskrift '
                    f'i Lovdata. Endringene under er historiske endringer som ble '
                    f'gjort før loven ble opphevet eller erstattet.</p>\n'
                    f'</section>'
                )
            else:
                # Markdown exists but paragraph not extractable — probably
                # renumbered/removed by a later amendment, or has an unusual
                # heading structure not matched by the regex.
                doc = index.doc_page(law_refid)
                current_text_link = (
                    f'<a href="../../{doc}">Se gjeldende lovtekst \u2192</a>' if doc else
                    f'<a href="{index.lovdata_archive_url(law_refid)}">Se arkivert tekst hos Lovdata \u2192</a>'
                )
                current_text_block = (
                    f'<section class="current-text removed">\n'
                    f'  <h2>{html.escape(paragraph)} finnes ikke i gjeldende tekst</h2>\n'
                    f'  <p style="margin:0;color:#6c757d;">'
                    f'Paragrafen er enten opphevet, omnummerert, eller flyttet '
                    f'siden den siste endringen under. '
                    f'{current_text_link}</p>\n'
                    f'</section>'
                )

        amendments_html_parts = []
        for a in amendments:
            act_doc = index.doc_page(a["act_refid"])
            act_url = f"{SITE_BASE}/{act_doc}" if act_doc else index.lovdata_act_url(a["act_refid"])
            instr_short = html.escape((a["instruction"] or "")[:200])
            new_text_block = ""
            if a["new_text"]:
                # Preserve line breaks; cap length to keep page light
                nt = a["new_text"]
                if len(nt) > 2000:
                    nt = nt[:2000].rstrip() + "…"
                # Convert plain text linebreaks to <br> for readability
                nt_html = html.escape(nt).replace("\n", "<br>")
                new_text_block = (
                    f'  <details class="new-text">\n'
                    f'    <summary>Ny tekst</summary>\n'
                    f'    <div class="new-text-body">{nt_html}</div>\n'
                    f'  </details>\n'
                )
            amendments_html_parts.append(
                f'<div class="amendment">\n'
                f'  <div class="meta">{html.escape(a["date_published"] or "")} · '
                f'{html.escape(a["ministry"] or "")}'
                f'{" · " + html.escape(a["journal_number"]) if a["journal_number"] else ""}'
                f'{" · ikrafttredelse " + html.escape(a["date_in_force_resolved"]) if a["date_in_force_resolved"] else ""}'
                f'</div>\n'
                f'  <div class="title"><a href="{act_url}">'
                f'{html.escape(a["act_short_title"] or a["act_title"] or a["act_refid"])}'
                f'</a></div>\n'
                f'  <div class="instruction">{instr_short}</div>\n'
                f'{new_text_block}'
                f'</div>'
            )

        _fdoc = index.doc_page(law_refid)
        if _fdoc:
            frag = f"#{para_anchor}" if para_anchor else ""
            fulltext_link = f'<a href="../../{_fdoc}{frag}">Les i full lovtekst \u2192</a>'
        else:
            fulltext_link = (
                f'<a href="{index.lovdata_archive_url(law_refid)}" '
                f'title="Opphevet \u2014 arkivert hos Lovdata">Les arkivert tekst \u2192</a>'
            )
        _feed = index.feed(law_refid)
        if _feed:
            feed_autodiscovery = (
                f'<link rel="alternate" type="application/atom+xml" '
                f'title="Atom-feed for hele loven" href="../../{_feed}"/>'
            )
            feed_link_html = f'<a href="../../{_feed}">\U0001F4E1 Atom-feed for hele loven</a>'
        else:
            feed_autodiscovery = (
                '<link rel="alternate" type="application/atom+xml" '
                'title="Norges Lover \u2014 alle endringer" href="../../feed.xml"/>'
            )
            feed_link_html = '<a href="../../feed.xml">\U0001F4E1 Atom-feed (alle endringer)</a>'
        _hist = index.historie_page(law_refid)
        historie_crumb = f'<a href="../../{_hist}">Endringshistorikk</a> \u203a' if _hist else ""
        _doc = index.doc_page(law_refid)
        law_link = (
            f'<a href="../../{_doc}">{html.escape(law_title)}</a>' if _doc else
            f'<a href="{index.lovdata_archive_url(law_refid)}" title="Opphevet \u2014 arkivert hos Lovdata">{html.escape(law_title)}</a>'
        )
        page = PAGE_TEMPLATE.format(
            paragraph=html.escape(paragraph),
            law_link=law_link,
            historie_crumb=historie_crumb,
            fulltext_link=fulltext_link,
            feed_autodiscovery=feed_autodiscovery,
            feed_link_html=feed_link_html,
            law_title=html.escape(law_title),
            law_stem=law_stem,
            para_slug=para_slug,
            para_anchor=para_anchor or "",
            n_amendments=len(amendments),
            plural="er" if len(amendments) > 1 else "",
            canonical_url=canonical_url,
            site_base=SITE_BASE,
            current_text_block=current_text_block,
            amendments_html="\n".join(amendments_html_parts),
            neighbor_nav=neighbor_nav_html,
            generated=now,
        )
        (law_dir / f"{para_slug}.html").write_text(page, encoding="utf-8")
        n_written += 1

    print(f"  Wrote {n_written} paragraph-history pages to {output_dir}/")
    return n_written, amended


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "snapshot/amendments.db"
    out = sys.argv[2] if len(sys.argv) > 2 else "_site/historikk"
    generate_paragraph_history_pages(db_path=db, output_dir=out)
