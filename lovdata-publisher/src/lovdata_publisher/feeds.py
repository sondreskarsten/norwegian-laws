"""Generate per-law, per-topic, and per-ministry Atom feeds.

The single repo-wide feed (feed.py) lists the most recent N amendments.
This module produces fine-grained feeds: one per law, one per rettsområde
topic, and one per ministry, so external systems can subscribe to changes
in a specific area instead of polling the firehose.

Per-law feed URL pattern:
    /feeds/lov-{date-nr}.xml      e.g. /feeds/lov-1998-07-17-56.xml
    /feeds/forskrift-{date-nr}.xml

Per-topic feed (slugified rettsområde):
    /feeds/topic-{slug}.xml       e.g. /feeds/topic-skatte--og-avgiftsrett.xml

Per-ministry feed (slugified departement):
    /feeds/dept-{slug}.xml        e.g. /feeds/dept-finansdepartementet.xml

Index page at /feeds/ listing all available feeds for discovery.
"""
from __future__ import annotations

import html
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SITE_BASE = "https://sondreskarsten.github.io/norwegian-laws"


def _slug(text: str) -> str:
    """Slugify a Norwegian topic/ministry name for URLs."""
    s = text.lower()
    s = (s.replace("æ", "ae").replace("ø", "o").replace("å", "a"))
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


def _normalize_paragraph_ref(target: str, instruction: str) -> str:
    """Extract a canonical paragraph reference (e.g. '§ 7-1') from
    the target field or fall back to parsing the amendment instruction.

    Returns empty string if no paragraph reference can be identified
    (e.g. when the target is 'kapittel 9' or the whole law).
    """
    # Letter suffix must be a SINGLE letter followed by whitespace/punctuation/end,
    # not the start of "første", "annet", etc.
    para_re = re.compile(r'§§?\s*(\d+\s*[-–]\s*\d+(?:[a-z](?=$|[^a-zæøåA-ZÆØÅ]))?)')

    text = (target or "").strip()
    if not text or text.lower().startswith("kapittel") or text.lower().startswith("del "):
        m = para_re.search(instruction or "")
        if m:
            return f"§ {re.sub(r'\\s+', '-', m.group(1).strip())}"
        return ""
    # Use .search() (not .match()) so prefixed targets like
    # 'lov/1915-08-13-5/§217a' still match.
    m = para_re.search(text)
    if m:
        return f"§ {re.sub(r'\\s+', '-', m.group(1).strip())}"
    return ""


def _build_paragraph_anchor_map(md_path: Path) -> dict[str, str]:
    """For one law/forskrift markdown file, return {paragraph: anchor}.

    Example return: {'§ 1-1': '1-1-lovens-virkeomrade', '§ 1-2a': '1-2a-...'}

    Anchors use python-markdown's toc.slugify (which is the same routine
    used to generate the per-law HTML page anchors), so feed links match
    the rendered page IDs exactly.
    """
    try:
        from markdown.extensions.toc import slugify
    except ImportError:
        return {}

    header_re = re.compile(r'^#{3,5}\s+(§\s*\d+[-–]\d+[a-z]?)\.?\s+(.+?)\s*$', re.MULTILINE)
    text = md_path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in header_re.finditer(text):
        para_raw = re.sub(r"\s+", "-", m.group(1).replace("§", "§ ")).replace("--", "-")
        para_canonical = re.sub(r"§\s*(\d+)-(\d+)([a-z]?)", r"§ \1-\2\3", m.group(1))
        para_canonical = para_canonical.replace("  ", " ").strip()
        # Slugify "§ 1-2a. Title" → "1-2a-title-slug"
        slug = slugify(f"{m.group(1)}. {m.group(2)}", "-")
        # Only keep the first occurrence (some laws revoke + reintroduce paragraphs)
        if para_canonical not in out:
            out[para_canonical] = slug
    return out


def _filepath_for(refid: str) -> str:
    if refid.startswith("forskrift/"):
        return f"/forskrifter/forskrift-{refid.split('/', 1)[1]}.html"
    if refid.startswith("lov/"):
        return f"/lover/lov-{refid.split('/', 1)[1]}.html"
    return ""


def _atom_entry(act: dict, anchor_refid: str, paragraph_anchors: dict[str, str] | None = None) -> str:
    """Render one Atom entry. anchor_refid is the law the feed is *about*.

    paragraph_anchors: optional {paragraph: html_anchor} map. When present and
    the act amends exactly one paragraph, the link href gets the matching
    `#anchor` fragment so feed readers jump directly to the changed section.
    """
    title = html.escape(act["short_title"] or act["title"] or act["refid"])
    refid = act["refid"]
    link_frag = _filepath_for(anchor_refid)
    link = f"{SITE_BASE}{link_frag}" if link_frag else f"{SITE_BASE}/"

    # Deep-link to the changed paragraph when there's a single one and we have its anchor.
    paragraphs = act.get("_paragraphs") or []
    if paragraphs and paragraph_anchors:
        anchor = paragraph_anchors.get(paragraphs[0])
        if anchor:
            link = f"{link}#{anchor}"

    published = act.get("date_published") or act.get("date_in_force_resolved") or ""
    ts = (published[:10] + "T00:00:00Z") if published else "2001-01-01T00:00:00Z"
    summary_lines = []
    if act.get("date_in_force"):
        summary_lines.append(f"Ikrafttredelse: {act['date_in_force']}")
    if act.get("ministry"):
        summary_lines.append(f"Departement: {act['ministry']}")
    if act.get("changes_to"):
        summary_lines.append(f"Endrer: {act['changes_to']}")
    if act.get("journal_number"):
        summary_lines.append(f"Lovtidend: {act['journal_number']}")
    if paragraphs:
        summary_lines.append(f"Berørte paragrafer: {', '.join(paragraphs)}")
    if act.get("misc_info"):
        summary_lines.append(act["misc_info"][:300])
    summary = html.escape("\n".join(summary_lines))

    # <category> elements let feed readers filter by paragraph
    category_xml = "\n".join(
        f'  <category term="{html.escape(p)}" label="{html.escape(p)}"/>' for p in paragraphs
    )
    if category_xml:
        category_xml = "\n" + category_xml

    return (
        "<entry>\n"
        f"  <id>{html.escape(SITE_BASE)}/feeds/{html.escape(anchor_refid)}/{html.escape(refid)}</id>\n"
        f"  <title>{title}</title>\n"
        f"  <link href=\"{html.escape(link)}\"/>\n"
        f"  <updated>{ts}</updated>"
        f"{category_xml}\n"
        f"  <summary>{summary}</summary>\n"
        "</entry>"
    )


def _wrap_feed(title: str, self_url: str, subtitle: str, entries_xml: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<feed xmlns=\"http://www.w3.org/2005/Atom\">\n"
        f"  <title>{html.escape(title)}</title>\n"
        f"  <link href=\"{html.escape(self_url)}\" rel=\"self\"/>\n"
        f"  <link href=\"{SITE_BASE}/\"/>\n"
        f"  <updated>{now}</updated>\n"
        f"  <id>{html.escape(self_url)}</id>\n"
        "  <author><name>Lovtidend</name></author>\n"
        f"  <subtitle>{html.escape(subtitle)}</subtitle>\n"
        f"{entries_xml}\n"
        "</feed>\n"
    )


def _scan_frontmatter(lover_dir: str, forskrifter_dir: str | None) -> dict:
    """Return refid → {tittel, korttittel, rettsomrade, departement, _md_path}."""
    laws = {}
    for d in [lover_dir, forskrifter_dir]:
        if not d or not Path(d).is_dir():
            continue
        for path in Path(d).glob("*.md"):
            if path.name == "README.md":
                continue
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            try:
                fm_end = text.index("\n---", 4)
                fm = text[4:fm_end]
            except ValueError:
                continue
            meta = {}
            for line in fm.splitlines():
                m = re.match(r'(\S+?):\s*"(.+?)"\s*$', line)
                if m:
                    meta[m.group(1)] = m.group(2)
            refid = meta.get("refid")
            if refid:
                meta["_md_path"] = path
                laws[refid] = meta
    return laws


def generate_per_law_feeds(
    snapshot_dir: str = "snapshot",
    lover_dir: str = "lover",
    forskrifter_dir: str | None = "forskrifter",
    output_dir: str = "_site/feeds",
    limit_per_feed: int = 50,
) -> dict:
    """Generate one Atom feed per law and per topic/ministry.

    Returns a manifest dict: {refid → output path} plus topic/ministry feeds.
    """
    db_path = Path(snapshot_dir) / "amendments.db"
    if not db_path.exists():
        print(f"  {db_path} not found, skipping feed generation")
        return {}

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    laws = _scan_frontmatter(lover_dir, forskrifter_dir)
    print(f"  Scanned {len(laws)} law/forskrift frontmatters")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Index amendments by target refid, joining to extract per-paragraph targets
    # so each Atom entry can carry <category> elements for paragraph-level filtering.
    by_target: dict[str, list[dict]] = defaultdict(list)
    paragraphs_by_act: dict[tuple[str, str], set[str]] = defaultdict(set)

    # Build paragraph index: (act_refid, target_law) → set of normalized paragraphs.
    # The 'amendments' table is optional — older snapshots may not have it.
    has_amendments_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='amendments'"
    ).fetchone() is not None
    if has_amendments_table:
        para_rows = conn.execute(
            """
            SELECT act_refid, target_law, target, instruction
            FROM amendments
            WHERE target_law IS NOT NULL AND target_law != ''
            """
        ).fetchall()
        for r in para_rows:
            para = _normalize_paragraph_ref(r["target"] or "", r["instruction"] or "")
            if para:
                paragraphs_by_act[(r["act_refid"], r["target_law"])].add(para)

    all_rows = conn.execute(
        """
        SELECT refid, title, short_title, date_in_force, date_in_force_resolved,
               date_published, ministry, changes_to, journal_number, misc_info
        FROM amendment_acts
        WHERE changes_to IS NOT NULL AND changes_to != ''
              AND date_published IS NOT NULL AND date_published != ''
        ORDER BY date_published DESC, date_in_force_resolved DESC
        """
    ).fetchall()
    for row in all_rows:
        for target in (row["changes_to"] or "").split(","):
            target = target.strip()
            if not target:
                continue
            paragraphs = sorted(paragraphs_by_act.get((row["refid"], target), set()))
            entry = dict(row)
            entry["_paragraphs"] = paragraphs
            by_target[target].append(entry)
    conn.close()
    print(f"  {len(all_rows)} amendment acts indexed against {len(by_target)} target laws")

    manifest = {"laws": {}, "topics": {}, "ministries": {}}

    # === Per-law feeds ===
    for refid, meta in laws.items():
        rows = by_target.get(refid, [])[:limit_per_feed]
        if not rows:
            continue
        if refid.startswith("forskrift/"):
            stem = "forskrift-" + refid.split("/", 1)[1]
        else:
            stem = "lov-" + refid.split("/", 1)[1]
        fname = f"{stem}.xml"
        self_url = f"{SITE_BASE}/feeds/{fname}"
        title = meta.get("korttittel") or meta.get("tittel") or refid

        # Build paragraph→anchor map from the markdown so feed entries can
        # deep-link to the changed paragraph instead of the law's homepage.
        md_path = meta.get("_md_path")
        anchor_map = _build_paragraph_anchor_map(md_path) if md_path else {}

        entries = "\n".join(_atom_entry(dict(r), refid, anchor_map) for r in rows)
        feed = _wrap_feed(
            title=f"{title} — endringer",
            self_url=self_url,
            subtitle=f"Endringer i {meta.get('tittel') or refid} fra Norsk Lovtidend",
            entries_xml=entries,
        )
        (out / fname).write_text(feed, encoding="utf-8")
        manifest["laws"][refid] = {
            "path": f"feeds/{fname}",
            "tittel": meta.get("tittel", ""),
            "korttittel": meta.get("korttittel", ""),
            "count": len(rows),
        }

    print(f"  Wrote {len(manifest['laws'])} per-law feeds")

    # === Per-topic (rettsområde) feeds ===
    topics: dict[str, list[tuple[str, sqlite3.Row]]] = defaultdict(list)
    for refid, meta in laws.items():
        rettsomrade_raw = meta.get("rettsomrade", "")
        if not rettsomrade_raw:
            continue
        for area in rettsomrade_raw.split("\\n"):
            area = area.strip()
            if not area:
                continue
            top_level = area.split(">", 1)[0].strip()
            if not top_level:
                continue
            for row in by_target.get(refid, []):
                topics[top_level].append((refid, row))

    for topic, items in topics.items():
        seen = set()
        unique = []
        for refid, row in items:
            key = (refid, row["refid"])
            if key in seen:
                continue
            seen.add(key)
            unique.append((refid, row))
        unique.sort(key=lambda x: x[1]["date_published"] or "", reverse=True)
        unique = unique[:limit_per_feed]
        if not unique:
            continue
        slug = _slug(topic)
        fname = f"topic-{slug}.xml"
        self_url = f"{SITE_BASE}/feeds/{fname}"
        entries = "\n".join(_atom_entry(dict(row), refid) for refid, row in unique)
        feed = _wrap_feed(
            title=f"{topic} — endringer",
            self_url=self_url,
            subtitle=f"Endringer i lover og forskrifter innen {topic}",
            entries_xml=entries,
        )
        (out / fname).write_text(feed, encoding="utf-8")
        manifest["topics"][topic] = {
            "slug": slug,
            "path": f"feeds/{fname}",
            "count": len(unique),
        }

    print(f"  Wrote {len(manifest['topics'])} per-topic feeds")

    # === Per-ministry feeds ===
    # Some laws have concatenated departments like "Klima- og miljødepartementetLandbruks- og matdepartementet"
    # Use the same KNOWN_DEPARTMENTS split logic as quarto.py.
    from .quarto import split_departments as _split_dept

    ministries: dict[str, list[tuple[str, sqlite3.Row]]] = defaultdict(list)
    for refid, meta in laws.items():
        dept_raw = meta.get("departement", "")
        if not dept_raw:
            continue
        for dept in _split_dept(dept_raw):
            dept = dept.strip()
            if not dept:
                continue
            for row in by_target.get(refid, []):
                ministries[dept].append((refid, row))

    for dept, items in ministries.items():
        seen = set()
        unique = []
        for refid, row in items:
            key = (refid, row["refid"])
            if key in seen:
                continue
            seen.add(key)
            unique.append((refid, row))
        unique.sort(key=lambda x: x[1]["date_published"] or "", reverse=True)
        unique = unique[:limit_per_feed]
        if not unique:
            continue
        slug = _slug(dept)
        fname = f"dept-{slug}.xml"
        self_url = f"{SITE_BASE}/feeds/{fname}"
        entries = "\n".join(_atom_entry(dict(row), refid) for refid, row in unique)
        feed = _wrap_feed(
            title=f"{dept} — endringer",
            self_url=self_url,
            subtitle=f"Endringer i lover og forskrifter under {dept}",
            entries_xml=entries,
        )
        (out / fname).write_text(feed, encoding="utf-8")
        manifest["ministries"][dept] = {
            "slug": slug,
            "path": f"feeds/{fname}",
            "count": len(unique),
        }

    print(f"  Wrote {len(manifest['ministries'])} per-ministry feeds")

    # === Index JSON for discovery ===
    import json
    index_path = out / "index.json"
    index_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"  Wrote feed manifest to {index_path}")

    # === Human-readable index page ===
    _write_index_html(out, manifest)

    return manifest


def _write_index_html(out: Path, manifest: dict) -> None:
    """Write a discoverable HTML index of all feeds."""
    laws_html = []
    laws_sorted = sorted(
        manifest["laws"].items(),
        key=lambda x: -x[1]["count"],
    )
    for refid, info in laws_sorted:
        title = info["korttittel"] or info["tittel"] or refid
        laws_html.append(
            f'<tr><td><a href="{info["path"].split("/", 1)[1]}">{html.escape(title)}</a></td>'
            f'<td><code>{html.escape(refid)}</code></td>'
            f'<td style="text-align:right">{info["count"]}</td></tr>'
        )

    topics_html = []
    for topic, info in sorted(manifest["topics"].items(), key=lambda x: -x[1]["count"]):
        topics_html.append(
            f'<tr><td><a href="{info["path"].split("/", 1)[1]}">{html.escape(topic)}</a></td>'
            f'<td style="text-align:right">{info["count"]}</td></tr>'
        )

    ministries_html = []
    for dept, info in sorted(manifest["ministries"].items(), key=lambda x: -x[1]["count"]):
        ministries_html.append(
            f'<tr><td><a href="{info["path"].split("/", 1)[1]}">{html.escape(dept)}</a></td>'
            f'<td style="text-align:right">{info["count"]}</td></tr>'
        )

    page = f"""<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Atom-feeds — Norges Lover</title>
<style>
body {{ max-width: 960px; margin: 0 auto; padding: 1.5rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; line-height: 1.55; color: #212529; }}
h1 {{ font-size: 1.75rem; border-bottom: 2px solid #dee2e6; padding-bottom: 0.3rem; }}
h2 {{ font-size: 1.3rem; margin-top: 2rem; color: #495057; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.95rem; }}
th, td {{ padding: 0.4rem 0.6rem; border-bottom: 1px solid #dee2e6; text-align: left; }}
th {{ background: #f8f9fa; }}
code {{ font-size: 0.85em; color: #6c757d; }}
.intro {{ background: #f8f9fa; border-left: 3px solid #2780e3; padding: 0.75rem 1rem; margin: 1rem 0; }}
.intro code {{ color: #1864ab; }}
nav {{ margin-bottom: 1rem; font-size: 0.9rem; }}
nav a {{ color: #2780e3; }}
</style>
</head>
<body>
<nav><a href="../index.html">← Norges Lover</a></nav>
<h1>Atom-feeds for regulatoriske endringer</h1>

<div class="intro">
Abonner på endringer i norske lover og forskrifter. Hver feed publiseres som
<a href="https://datatracker.ietf.org/doc/html/rfc4287" target="_blank">Atom 1.0</a>
og kan leses av enhver feed-leser, automatiseringsverktøy eller GitHub Action.
<p style="margin: 0.5rem 0 0 0;">
Eksempel: <code>curl https://sondreskarsten.github.io/norwegian-laws/feeds/lov-1998-07-17-56.xml</code>
</p>
</div>

<h2>Feeds per lov ({len(manifest["laws"])})</h2>
<table>
<thead><tr><th>Lov / forskrift</th><th>Refid</th><th style="text-align:right">Endringer</th></tr></thead>
<tbody>
{chr(10).join(laws_html)}
</tbody>
</table>

<h2>Feeds per rettsområde ({len(manifest["topics"])})</h2>
<table>
<thead><tr><th>Rettsområde</th><th style="text-align:right">Endringer</th></tr></thead>
<tbody>
{chr(10).join(topics_html)}
</tbody>
</table>

<h2>Feeds per departement ({len(manifest["ministries"])})</h2>
<table>
<thead><tr><th>Departement</th><th style="text-align:right">Endringer</th></tr></thead>
<tbody>
{chr(10).join(ministries_html)}
</tbody>
</table>

<footer style="margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 0.85rem;">
Datakilde: <a href="https://lovdata.no/" target="_blank">Lovdata</a> under
<a href="https://data.norge.no/nlod/no/2.0" target="_blank">NLOD 2.0</a>.
Ikke autoritativ — se Lovdata for gjeldende tekst.
</footer>
</body>
</html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"  Wrote feed index HTML to {out / 'index.html'}")


if __name__ == "__main__":
    import sys
    snap = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    lover = sys.argv[2] if len(sys.argv) > 2 else "lover"
    fsk = sys.argv[3] if len(sys.argv) > 3 else "forskrifter"
    out_dir = sys.argv[4] if len(sys.argv) > 4 else "_site/feeds"
    generate_per_law_feeds(snap, lover, fsk, out_dir)
