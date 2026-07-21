"""Update the 'Recent amendments' section of README.md from amendments.db.

Replaces content between two HTML comment markers with the N most recent
amendment acts, and refreshes every count the README carries (document
coverage, amendment acts, feeds, per-paragraph pages) so no badge or
feature-table number can drift from the data again. Designed to be run by
the daily workflow after the snapshot is rebuilt.

The README must contain these markers:
    <!-- RECENT_AMENDMENTS_START -->
    ...replaced content...
    <!-- RECENT_AMENDMENTS_END -->
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

START_MARKER = "<!-- RECENT_AMENDMENTS_START -->"
END_MARKER = "<!-- RECENT_AMENDMENTS_END -->"


def _law_url(refid: str) -> str:
    base = "https://sondreskarsten.github.io/norwegian-laws"
    if refid.startswith("forskrift/"):
        return f"{base}/forskrifter/forskrift-{refid.split('/', 1)[1]}.html"
    if refid.startswith("lov/"):
        return f"{base}/lover/lov-{refid.split('/', 1)[1]}.html"
    return base


def build_recent_block(db_path: str, limit_lover: int = 5, limit_forskrift: int = 5) -> str:
    """Return Markdown block of recent amendment acts, split lover vs forskrifter.

    Tax advisors, auditors, and compliance teams generally care more about
    formal lover than forskrifter, so we surface the most recent lover first
    and follow with the most recent forskrifter.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def fetch(kind_prefix: str, limit: int) -> list:
        return conn.execute(
            """
            SELECT refid, title, short_title, date_published,
                   date_in_force, date_in_force_resolved, ministry, changes_to
            FROM amendment_acts
            WHERE date_published IS NOT NULL AND date_published != ''
                  AND refid LIKE ?
                  AND changes_to LIKE ?
            ORDER BY date_published DESC, date_in_force_resolved DESC
            LIMIT ?
            """,
            (f"{kind_prefix}/%", f"{kind_prefix}/%", limit),
        ).fetchall()

    lover_rows = fetch("lov", limit_lover)
    forskrift_rows = fetch("forskrift", limit_forskrift)
    conn.close()

    def render_table(rows) -> list[str]:
        lines = ["| Date | Amendment | Targets |", "|---|---|---|"]
        for row in rows:
            date = row["date_published"][:10] if row["date_published"] else "—"
            title = row["short_title"] or row["title"] or row["refid"]
            if len(title) > 70:
                title = title[:67] + "…"
            title_md = title.replace("|", "\\|")
            targets = (row["changes_to"] or "").split(",")
            target_links = []
            seen = set()
            for t in targets[:3]:
                t = t.strip()
                if not t or t in seen:
                    continue
                seen.add(t)
                target_links.append(f"[`{t}`]({_law_url(t)})")
            if len([t for t in targets if t.strip()]) > 3:
                target_links.append("…")
            targets_md = " ".join(target_links) if target_links else "—"
            lines.append(f"| {date} | {title_md} | {targets_md} |")
        return lines

    sections = []
    if lover_rows:
        sections.append("**Lover (endringslover):**")
        sections.append("")
        sections.extend(render_table(lover_rows))
        sections.append("")
    if forskrift_rows:
        sections.append("**Forskrifter:**")
        sections.append("")
        sections.extend(render_table(forskrift_rows))

    return "\n".join(sections)


def _corpus_counts(base_dir: Path, db_path: str) -> dict:
    """Compute doc totals, feed counts, and per-paragraph page count.

    Mirrors the selection logic of feeds.generate_per_law_feeds and
    paragraph_history.generate_paragraph_history_pages so README numbers
    match what those generators actually produce. Returns {} when the
    lover/ corpus directory is absent (unit-test READMEs)."""
    from .feeds import _scan_frontmatter
    from .paragraph_history import _normalize_paragraph
    from .quarto import split_departments

    lover = base_dir / "lover"
    forskrifter = base_dir / "forskrifter"
    counts: dict = {}
    if not lover.is_dir():
        return counts
    laws = _scan_frontmatter(str(lover), str(forskrifter) if forskrifter.is_dir() else None)
    n_lover = len([f for f in lover.glob("*.md") if f.name != "README.md"])
    n_forskrifter = len([f for f in forskrifter.glob("*.md") if f.name != "README.md"]) if forskrifter.is_dir() else 0
    counts["n_lover"] = n_lover
    counts["n_forskrifter"] = n_forskrifter
    counts["n_docs"] = n_lover + n_forskrifter

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    targets: set = set()
    for row in conn.execute(
        "SELECT changes_to FROM amendment_acts "
        "WHERE changes_to IS NOT NULL AND changes_to != '' "
        "AND date_published IS NOT NULL AND date_published != ''"
    ):
        for target in row["changes_to"].split(","):
            target = target.strip()
            if target:
                targets.add(target)
    amended = targets & set(laws)
    topics: set = set()
    depts: set = set()
    for refid in amended:
        meta = laws[refid]
        for area in meta.get("rettsomrade", "").split("\\n"):
            top = area.split(">", 1)[0].strip()
            if top:
                topics.add(top)
        for dept in split_departments(meta.get("departement", "")):
            if dept.strip():
                depts.add(dept.strip())
    counts["n_law_feeds"] = len(amended)
    counts["n_topic_feeds"] = len(topics)
    counts["n_dept_feeds"] = len(depts)
    counts["n_feeds"] = len(amended) + len(topics) + len(depts)

    has_amendments = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='amendments'"
    ).fetchone() is not None
    if has_amendments:
        pages = set()
        for r in conn.execute(
            "SELECT a.target, a.target_law, a.instruction "
            "FROM amendments a LEFT JOIN amendment_acts ac ON a.act_refid = ac.refid "
            "WHERE a.target_law IS NOT NULL AND a.target_law != '' "
            "AND ac.date_published IS NOT NULL"
        ):
            para = _normalize_paragraph(r["target"] or "", r["instruction"] or "")
            if para:
                pages.add((r["target_law"], para))
        counts["n_para_pages"] = len(pages)
    conn.close()
    return counts


def update_readme(readme_path: str, db_path: str, limit_lover: int = 5, limit_forskrift: int = 5) -> bool:
    """Replace content between markers in README.md. Returns True if changed.

    Also refreshes the dated_amendments shield badge URL and the
    'Backdated git history' row in the feature table, both of which carry a
    hardcoded amendment count that grows over time.
    """
    path = Path(readme_path)
    if not path.exists():
        print(f"  {path} not found")
        return False
    if not Path(db_path).exists():
        print(f"  {db_path} not found")
        return False

    original = path.read_text(encoding="utf-8")
    if START_MARKER not in original or END_MARKER not in original:
        print(f"  Markers not found in {path}, skipping")
        return False

    block = build_recent_block(db_path, limit_lover=limit_lover, limit_forskrift=limit_forskrift)
    replacement = f"{START_MARKER}\n{block}\n{END_MARKER}"
    pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
    new_text = re.sub(pattern, replacement, original, flags=re.DOTALL)

    # Refresh the dated_amendments badge + feature-table row. The badge URL
    # uses URL-encoded comma '%2C'; the table row uses a plain comma. Both
    # carry the same number which is the count of amendment acts in the DB.
    conn = sqlite3.connect(db_path)
    try:
        n_acts = conn.execute("SELECT COUNT(*) FROM amendment_acts").fetchone()[0]
    finally:
        conn.close()
    badge_pattern = r'dated_amendments-[\d%C]+-ba0c2f'
    new_text = re.sub(
        badge_pattern,
        f"dated_amendments-{n_acts:,}".replace(",", "%2C") + "-ba0c2f",
        new_text,
    )
    # Feature-table row: "31,459 amendment acts as backdated commits"
    new_text = re.sub(
        r"\d{1,3}(?:,\d{3})* amendment acts as backdated commits",
        f"{n_acts:,} amendment acts as backdated commits",
        new_text,
    )

    counts = _corpus_counts(path.parent, db_path)
    if counts:
        enc = lambda n: f"{n:,}".replace(",", "%2C")
        plain = lambda n: f"{n:,}"
        new_text = re.sub(
            r"coverage-[\d%C]+_documents-2780e3",
            f"coverage-{enc(counts['n_docs'])}_documents-2780e3",
            new_text,
        )
        new_text = re.sub(
            r"All [\d,]+ formal laws \+ [\d,]+ central regulations",
            f"All {plain(counts['n_lover'])} formal laws + {plain(counts['n_forskrifter'])} central regulations",
            new_text,
        )
        new_text = re.sub(
            r"atom_feeds-[\d%C]+-7a92b8",
            f"atom_feeds-{enc(counts['n_feeds'])}-7a92b8",
            new_text,
        )
        new_text = re.sub(
            r"[\d,]+ subscribable feeds [\u2014-] one per law/forskrift with amendments, plus [\d,]+ rettsomr\u00e5de and [\d,]+ ministry feeds",
            f"{plain(counts['n_feeds'])} subscribable feeds \u2014 one per law/forskrift with amendments, plus {plain(counts['n_topic_feeds'])} rettsomr\u00e5de and {plain(counts['n_dept_feeds'])} ministry feeds",
            new_text,
        )
        if "n_para_pages" in counts:
            new_text = re.sub(
                r"[\d,]+\+? per-paragraph history pages",
                f"{plain(counts['n_para_pages'])} per-paragraph history pages",
                new_text,
            )

    if new_text == original:
        return False

    path.write_text(new_text, encoding="utf-8")
    return True


if __name__ == "__main__":
    import sys
    readme = sys.argv[1] if len(sys.argv) > 1 else "README.md"
    db = sys.argv[2] if len(sys.argv) > 2 else "snapshot/amendments.db"
    changed = update_readme(readme, db)
    print(f"  README updated: {changed}")
