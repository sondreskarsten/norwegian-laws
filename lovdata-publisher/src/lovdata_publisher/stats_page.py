"""Generate a stats/leaderboard page: most-amended laws, by ministry, by year.

Purpose: help users discover which laws to monitor. The interactive
abonner page is search-driven (you have to know what you want); this is
discovery-driven (top of the list = most active).
"""
from __future__ import annotations

import html
import re
import sqlite3

from .site_index import SiteIndex
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SITE_BASE = "https://sondreskarsten.github.io/norwegian-laws"


def _refid_to_stem(refid: str) -> str:
    return refid.replace("/", "-")


def _kind_dir(refid: str) -> str:
    return "forskrifter" if refid.startswith("forskrift/") else "lover"


def _law_titles(lover_dir: str, forskrifter_dir: str) -> dict[str, dict]:
    """Read frontmatter for every law + forskrift, return {refid: {title, korttittel}}."""
    out: dict[str, dict] = {}
    for d in (lover_dir, forskrifter_dir):
        p = Path(d)
        if not p.is_dir():
            continue
        for md in p.glob("*.md"):
            text = md.read_text(encoding="utf-8")
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
                out[refid] = {
                    "title": meta.get("tittel", refid),
                    "korttittel": meta.get("korttittel", ""),
                    "ministry": meta.get("departement", ""),
                }
    return out


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="nb">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aktivitet — hvilke lover endres oftest? — Norges Lover</title>
<meta name="description" content="Topp-lister over de mest endrede norske lovene og forskriftene siden 2001, og endringsvolum per år og departement.">
<meta property="og:site_name" content="Norges Lover"/>
<meta property="og:type" content="article"/>
<meta property="og:title" content="Aktivitet — hvilke norske lover endres oftest?"/>
<meta property="og:description" content="Topp-lister: mest endrede lover/forskrifter, mest aktive år, mest aktive departementer."/>
<meta property="og:url" content="{site_base}/aktivitet.html"/>
<meta property="og:image" content="{site_base}/assets/banner.svg"/>
<meta name="twitter:card" content="summary"/>
<link rel="icon" type="image/svg+xml" href="/norwegian-laws/assets/favicon.svg"/>
<link rel="canonical" href="{site_base}/aktivitet.html"/>
<style>
body {{ max-width: 1000px; margin: 0 auto; padding: 1.5rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.55; color: #212529; }}
h1 {{ font-size: 1.8rem; border-bottom: 2px solid #dee2e6; padding-bottom: 0.4rem; margin-top: 0; }}
h2 {{ font-size: 1.3rem; margin-top: 2rem; color: #495057; }}
.intro {{ background: #f8f9fa; border-left: 3px solid #2780e3; padding: 0.75rem 1rem; margin: 1rem 0 2rem; font-size: 0.95rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 0.5rem 0; }}
th, td {{ padding: 0.5rem 0.7rem; text-align: left; border-bottom: 1px solid #dee2e6; }}
th {{ background: #f8f9fa; font-weight: 600; font-size: 0.85rem; color: #495057; text-transform: uppercase; letter-spacing: 0.03em; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; color: #495057; }}
tr:hover {{ background: #fafbfc; }}
a {{ color: #2780e3; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.year-bar {{ display: inline-block; height: 12px; background: linear-gradient(90deg, #2780e3 0%, #0969da 100%); border-radius: 2px; vertical-align: middle; margin-right: 0.4rem; }}
.muted {{ color: #6c757d; font-size: 0.85rem; }}
nav.crumb {{ background: #f8f9fa; padding: 0.5rem 1rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.9rem; }}
footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #dee2e6; color: #6c757d; font-size: 0.85rem; }}
</style>
</head>
<body>
<nav class="crumb">
  <a href="./">Norges Lover</a> › Aktivitet
</nav>

<h1>Aktivitet — hvilke lover endres oftest?</h1>

<div class="intro">
  <p style="margin:0;">Statisk topp-liste over de mest aktive lovene, forskriftene, departementene og årgangene fra Lovdata sin endringshistorikk siden 2001. Dataen oppdateres når hovedsamlingen oppdateres (daglig). For søkbart oversikt, se <a href="book/abonner.html">abonner-siden</a>.</p>
</div>

<h2>Mest endrede lover</h2>
<p class="muted">Lover rangert etter antall endringslover som har endret dem siden 2001.</p>
<table>
  <thead><tr><th>#</th><th>Lov</th><th>Korttittel</th><th class="num">Endringer</th><th>Feed</th><th>Historikk</th></tr></thead>
  <tbody>
{top_laws_rows}
  </tbody>
</table>

<h2>Mest endrede forskrifter</h2>
<p class="muted">Forskrifter rangert etter antall endringer siden 2001.</p>
<table>
  <thead><tr><th>#</th><th>Forskrift</th><th>Korttittel</th><th class="num">Endringer</th><th>Feed</th><th>Historikk</th></tr></thead>
  <tbody>
{top_forskrifter_rows}
  </tbody>
</table>

<h2>Endringsvolum per år</h2>
<p class="muted">Antall endringslover publisert hvert år. Balkene viser volum relativt til toppåret.</p>
<table>
  <thead><tr><th>År</th><th class="num">Endringslover</th><th>Volum</th></tr></thead>
  <tbody>
{year_rows}
  </tbody>
</table>

<h2>Mest aktive departementer</h2>
<p class="muted">Antall endringslover fremmet av hvert departement siden 2001.</p>
<table>
  <thead><tr><th>Departement</th><th class="num">Endringslover</th><th>Feed</th></tr></thead>
  <tbody>
{ministry_rows}
  </tbody>
</table>

<h2>Siste endringer</h2>
<p class="muted">De 20 siste endringslovene Lovdata har publisert. For komplett oversikt med 100 entries, se <a href="feed.xml">/feed.xml</a>.</p>
<table>
  <thead><tr><th>Publisert</th><th>Endringslov</th><th>Endrer</th><th>Departement</th></tr></thead>
  <tbody>
{latest_rows}
  </tbody>
</table>

<footer>
  Generert {generated}. Kilde: Lovdata API (NLOD 2.0). Topp-listene er statisk
  gjengivelse av <a href="laws.json">laws.json</a> sortert etter
  <code>amendments</code>-feltet.
</footer>
</body>
</html>
"""


def _render_law_row(rank: int, refid: str, count: int, titles: dict, index: SiteIndex) -> str:
    meta = titles.get(refid, {})
    title = meta.get("title", refid)
    korttittel = meta.get("korttittel", "")
    doc = index.link(index.doc_page(refid), title[:80],
                     fallback_url=index.lovdata_archive_url(refid),
                     title=None if refid in index.corpus else "Opphevet — arkivert hos Lovdata")
    feed = index.link(index.feed(refid), "\U0001F4E1", title="Atom-feed") if index.feed(refid) else '<span class="muted">—</span>'
    hist = index.link(index.historie_page(refid), "\u29c9", title="Endringshistorikk") if index.historie_page(refid) else '<span class="muted">—</span>'
    return (
        f'<tr>'
        f'<td class="num">{rank}</td>'
        f'<td>{doc}</td>'
        f'<td class="muted">{html.escape(korttittel)}</td>'
        f'<td class="num"><strong>{count}</strong></td>'
        f'<td>{feed}</td>'
        f'<td>{hist}</td>'
        f'</tr>'
    )


def _render_year_row(year: str, count: int, max_count: int) -> str:
    bar_width = int(80 * count / max_count) if max_count > 0 else 0
    return (
        f'<tr>'
        f'<td>{html.escape(year)}</td>'
        f'<td class="num"><strong>{count}</strong></td>'
        f'<td><span class="year-bar" style="width:{bar_width}px;"></span></td>'
        f'</tr>'
    )


def _ministry_slug(ministry: str) -> str:
    """Mirror feeds.py dept_slug()."""
    s = ministry.lower()
    s = (s.replace("å", "a").replace("ø", "o").replace("æ", "ae")
           .replace(" ", "-"))
    return re.sub(r'[^a-z0-9-]', '', s)


def generate_stats_page(
    db_path: str = "snapshot/amendments.db",
    output_path: str = "_site/aktivitet.html",
    lover_dir: str = "lover",
    forskrifter_dir: str = "forskrifter",
    top_n: int = 20,
    site_index: SiteIndex | None = None,
) -> bool:
    """Build aktivitet.html. Returns True on success, False on missing data."""
    if not Path(db_path).exists():
        print(f"  {db_path} not found, skipping stats page")
        return False

    titles = _law_titles(lover_dir, forskrifter_dir)
    index = site_index if site_index is not None else SiteIndex.build(str(Path(lover_dir).parent))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Top laws / forskrifter by distinct amending acts
    rows = conn.execute(
        """
        SELECT target_law, COUNT(DISTINCT act_refid) AS n
        FROM amendments
        WHERE target_law IS NOT NULL AND target_law != ''
        GROUP BY target_law
        ORDER BY n DESC
        """
    ).fetchall()
    top_laws = [(r["target_law"], r["n"]) for r in rows if r["target_law"].startswith("lov/")][:top_n]
    top_forskrifter = [(r["target_law"], r["n"]) for r in rows if r["target_law"].startswith("forskrift/")][:top_n]

    # Year breakdown
    # IMPORTANT: count only acts that actually amend an existing law/forskrift —
    # the amendment_acts table is misleadingly named; it contains every Lovtidend
    # publication including new standalone forskrifter, delegations, repeals,
    # and decisions (~17,478 of 38,672 don't amend anything). Filtering by
    # presence in the amendments table gives the correct count of true
    # endringslover.
    year_rows = conn.execute(
        """
        SELECT substr(date_published, 1, 4) AS y, COUNT(DISTINCT refid) AS n
        FROM amendment_acts
        WHERE date_published IS NOT NULL AND date_published != ''
          AND refid IN (SELECT DISTINCT act_refid FROM amendments)
        GROUP BY y ORDER BY y DESC
        LIMIT 26
        """
    ).fetchall()
    year_data = [(r["y"], r["n"]) for r in year_rows]
    max_year_count = max((c for _, c in year_data), default=1)

    # Ministry breakdown — same filtering: count only acts that actually amend.
    ministry_rows = conn.execute(
        """
        SELECT ministry, COUNT(DISTINCT refid) AS n
        FROM amendment_acts
        WHERE ministry IS NOT NULL AND ministry != ''
          AND refid IN (SELECT DISTINCT act_refid FROM amendments)
        GROUP BY ministry
        ORDER BY n DESC
        LIMIT 20
        """
    ).fetchall()
    ministry_data = [(r["ministry"], r["n"]) for r in ministry_rows]

    # Latest 20 amendments
    latest_rows_db = conn.execute(
        """
        SELECT refid, title, short_title, date_published, ministry, changes_to
        FROM amendment_acts
        WHERE date_published IS NOT NULL AND date_published != ''
        ORDER BY date_published DESC, refid DESC
        LIMIT 20
        """
    ).fetchall()
    conn.close()

    top_laws_html = "\n".join(
        _render_law_row(i + 1, refid, n, titles, index) for i, (refid, n) in enumerate(top_laws)
    )
    top_forskrifter_html = "\n".join(
        _render_law_row(i + 1, refid, n, titles, index) for i, (refid, n) in enumerate(top_forskrifter)
    )
    year_html = "\n".join(_render_year_row(y, n, max_year_count) for y, n in year_data)
    ministry_html = "\n".join(
        f'<tr><td>{html.escape(m)}</td>'
        f'<td class="num"><strong>{n}</strong></td>'
        f'<td>{index.link(index.ministry_feed(m), "\U0001F4E1", title="Atom-feed for departementet") if index.ministry_feed(m) else chr(0x2014)}</td>'
        f'</tr>'
        for m, n in ministry_data
    )

    # Latest amendments rows
    def _latest_row(r):
        title = r["short_title"] or r["title"] or r["refid"]
        # changes_to is comma-separated refids; show first target as link
        targets = [t.strip() for t in (r["changes_to"] or "").split(",") if t.strip()]
        target_links = []
        for t in targets[:3]:
            target_links.append(
                index.link(index.doc_page(t), _refid_to_stem(t),
                           fallback_url=index.lovdata_archive_url(t),
                           title=None if t in index.corpus else "Opphevet — arkivert hos Lovdata")
            )
        if len(targets) > 3:
            target_links.append(f'<span class="muted">+ {len(targets) - 3} til</span>')
        return (
            f'<tr>'
            f'<td>{html.escape(r["date_published"][:10] if r["date_published"] else "")}</td>'
            f'<td>{html.escape(title[:80])}</td>'
            f'<td>{", ".join(target_links) or "<span class=\"muted\">—</span>"}</td>'
            f'<td class="muted">{html.escape(r["ministry"] or "—")}</td>'
            f'</tr>'
        )

    latest_html = "\n".join(_latest_row(r) for r in latest_rows_db)

    page = PAGE_TEMPLATE.format(
        site_base=SITE_BASE,
        top_laws_rows=top_laws_html,
        top_forskrifter_rows=top_forskrifter_html,
        year_rows=year_html,
        ministry_rows=ministry_html,
        latest_rows=latest_html,
        generated=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"  Wrote stats page to {output_path}")
    return True


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "snapshot/amendments.db"
    out = sys.argv[2] if len(sys.argv) > 2 else "_site/aktivitet.html"
    generate_stats_page(db_path=db, output_path=out)
