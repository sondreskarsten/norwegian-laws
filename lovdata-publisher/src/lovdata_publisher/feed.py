"""Generate an Atom feed of recent law and forskrift amendments.

Reads `amendments.db` from a snapshot and emits a standard Atom 1.0 feed
of the most recent N amendment acts, ordered by date_published descending.
Each entry links to the corresponding per-law page on gh-pages.

Entries carry <category> tags for affected paragraphs (so a feed reader
can filter by '§ 7-25'), the ministry, and the kind ('lov' or 'forskrift').
"""
from __future__ import annotations

import html
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .feeds import _filepath_for

SITE_BASE = "https://sondreskarsten.github.io/norwegian-laws"
FEED_URL = f"{SITE_BASE}/feed.xml"

from .site_index import SiteIndex
_INDEX: SiteIndex | None = None

_PARA_RE = re.compile(r'§\s*(\d+\s*[-–]\s*\d+(?:[a-z](?=$|[^a-zæøåA-ZÆØÅ]))?)')


def _atom_entry(act: dict, paragraphs: list[str] | None = None) -> str:
    """Render one Atom entry from an amendment_acts row.

    paragraphs: optional list of affected paragraphs (e.g. ['§ 7-25', '§ 1-2a']).
    Emitted as <category> elements so feed readers can filter by paragraph.
    """
    title = html.escape(act["short_title"] or act["title"] or act["refid"])
    refid = act["refid"]
    target_first = (act.get("changes_to") or "").split(",")[0].strip()
    if target_first and _INDEX is not None:
        doc = _INDEX.doc_page(target_first)
        link = f"{SITE_BASE}/{doc}" if doc else _INDEX.lovdata_archive_url(target_first)
    elif target_first:
        link = f"{SITE_BASE}{_filepath_for(target_first)}"
    else:
        link = f"{SITE_BASE}/"
    published = act.get("date_published") or act.get("date_in_force_resolved") or ""
    # Atom requires RFC3339 timestamps. Source is YYYY-MM-DD or YYYY-MM-DD HH:MM.
    ts = (published[:10] + "T00:00:00Z") if published else "2001-01-01T00:00:00Z"
    summary_lines = []
    if act.get("date_in_force"):
        summary_lines.append(f"Ikrafttredelse: {act['date_in_force']}")
    if act.get("ministry"):
        summary_lines.append(f"Departement: {act['ministry']}")
    if act.get("changes_to"):
        summary_lines.append(f"Endrer: {act['changes_to']}")
    if paragraphs:
        summary_lines.append(f"Berørte paragrafer: {', '.join(paragraphs)}")
    if act.get("misc_info"):
        summary_lines.append(act["misc_info"][:300])
    summary = html.escape("\n".join(summary_lines))

    # Categories: paragraphs (most useful for filtering), then ministry, then kind
    category_parts = []
    for p in paragraphs or []:
        category_parts.append(
            f'  <category term="{html.escape(p)}" label="{html.escape(p)}"/>'
        )
    if act.get("ministry"):
        category_parts.append(
            f'  <category term="ministry:{html.escape(act["ministry"])}" '
            f'label="{html.escape(act["ministry"])}"/>'
        )
    kind = "forskrift" if refid.startswith("forskrift/") else "lov"
    category_parts.append(f'  <category term="kind:{kind}" label="{kind}"/>')
    category_xml = "\n" + "\n".join(category_parts) if category_parts else ""

    return (
        "<entry>\n"
        f"  <id>{html.escape(SITE_BASE)}/feed/{html.escape(refid)}</id>\n"
        f"  <title>{title}</title>\n"
        f"  <link href=\"{html.escape(link)}\"/>\n"
        f"  <updated>{ts}</updated>"
        f"{category_xml}\n"
        f"  <summary>{summary}</summary>\n"
        "</entry>"
    )


def _paragraphs_for_acts(conn, act_refids: list[str]) -> dict[str, list[str]]:
    """Return {act_refid: [paragraph, ...]} from the amendments table.
    Returns {} if amendments table doesn't exist (older snapshots).
    """
    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='amendments'"
    ).fetchone():
        return {}
    if not act_refids:
        return {}
    placeholders = ",".join("?" for _ in act_refids)
    rows = conn.execute(
        f"""
        SELECT act_refid, target, instruction
        FROM amendments
        WHERE act_refid IN ({placeholders})
        """,
        act_refids,
    ).fetchall()
    out: dict[str, list[str]] = {}
    seen: dict[str, set] = {}
    for r in rows:
        ar, target, instruction = r["act_refid"], r["target"] or "", r["instruction"] or ""
        text = target.strip()
        m = None
        if not text or text.lower().startswith("kapittel") or text.lower().startswith("del "):
            m = _PARA_RE.search(instruction)
        else:
            m = _PARA_RE.search(text)
        if m:
            p = f"§ {re.sub(r'\\s+', '-', m.group(1).strip())}"
            seen.setdefault(ar, set())
            if p not in seen[ar]:
                seen[ar].add(p)
                out.setdefault(ar, []).append(p)
    return out


def generate_atom_feed(snapshot_dir: str = "snapshot", output_path: str = "_site/feed.xml", limit: int = 100) -> str:
    db_path = Path(snapshot_dir) / "amendments.db"
    if not db_path.exists():
        print(f"  {db_path} not found, skipping feed generation")
        return ""

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT refid, title, short_title, date_in_force, date_in_force_resolved,
               date_published, ministry, changes_to, misc_info
        FROM amendment_acts
        WHERE date_published IS NOT NULL AND date_published != ''
        ORDER BY date_published DESC, date_in_force_resolved DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    para_map = _paragraphs_for_acts(conn, [r["refid"] for r in rows])
    conn.close()
    entries = "\n".join(_atom_entry(dict(r), para_map.get(r["refid"], [])) for r in rows)

    feed = (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<feed xmlns=\"http://www.w3.org/2005/Atom\">\n"
        "  <title>Norges Lover og Forskrifter — endringer</title>\n"
        f"  <link href=\"{FEED_URL}\" rel=\"self\"/>\n"
        f"  <link href=\"{SITE_BASE}/\"/>\n"
        f"  <updated>{now}</updated>\n"
        f"  <id>{FEED_URL}</id>\n"
        "  <author><name>Lovtidend</name></author>\n"
        "  <subtitle>Nyere endringslover og endringsforskrifter, kunngjort i Norsk Lovtidend</subtitle>\n"
        f"{entries}\n"
        "</feed>\n"
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(feed, encoding="utf-8")
    print(f"  Wrote {len(rows)} feed entries to {out}")
    return str(out)


if __name__ == "__main__":
    _INDEX = SiteIndex.build(".")
    import sys
    snap = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    out = sys.argv[2] if len(sys.argv) > 2 else "_site/feed.xml"
    generate_atom_feed(snap, out)
