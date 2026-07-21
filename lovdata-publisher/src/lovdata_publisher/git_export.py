"""Git operations for building law history with backdated commits.

Handles FastImportStream generation, commit message formatting,
yearly tagging, and repository construction from snapshot data.
"""
from __future__ import annotations
import re
import subprocess
import sqlite3
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .formatter import refid_to_filepath


# ─── Date Utilities ──────────────────────────────────────────────────────────

DEFERRED_PATTERNS = ["Kongen bestemmer", "Kongen fastsetter", "Kongen fastset"]


def parse_effective_date(date_str: str, fallback_published: str) -> tuple[str, bool]:
    """Parse an effective date, falling back to publication date if deferred."""
    if any(p in date_str for p in DEFERRED_PATTERNS):
        pub = parse_publication_date(fallback_published)
        return pub, True

    date_str = date_str.strip()
    for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d"), False
        except ValueError:
            continue

    if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10], False

    pub = parse_publication_date(fallback_published)
    return pub, True


def parse_publication_date(date_str: str) -> str:
    """Parse a publication date string into YYYY-MM-DD format."""
    date_str = date_str.strip()
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if m:
        return m.group(1)
    return "2000-01-01"


def date_to_git_timestamp(date_str: str) -> str:
    """Convert a YYYY-MM-DD date to a git timestamp string."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dt = dt.replace(hour=12, minute=0, second=0, tzinfo=timezone.utc)
        return f"{int(dt.timestamp())} +0100"
    except ValueError:
        return f"{int(datetime(2000, 1, 1, 12, tzinfo=timezone.utc).timestamp())} +0100"


# ─── Commit Message Formatting ──────────────────────────────────────────────

CHANGE_TYPE_LABELS = {
    "change": "endret",
    "repeal": "opphevet",
    "add": "tilføyd",
    "move": "flyttet",
}


def format_commit_message(act_row: dict) -> str:
    """Format a commit message for an amendment act.

    Args:
        act_row: Dict with amendment act fields from SQLite or snapshot.
    """
    effective_date, is_deferred = parse_effective_date(
        act_row.get("date_in_force", ""),
        act_row.get("date_published", ""),
    )
    pub_date = parse_publication_date(act_row.get("date_published", ""))

    lines = []
    summary = act_row.get("short_title") or act_row.get("title", "")
    if len(summary) > 72:
        summary = summary[:69] + "..."
    lines.append(summary)
    lines.append("")

    lines.append(f"Endringslov: {act_row['refid']}")
    if is_deferred:
        lines.append(
            f"Ikrafttredelse: {act_row.get('date_in_force', '')} (bruker kunngjøringsdato)"
        )
    else:
        lines.append(f"Ikrafttredelse: {effective_date}")
    lines.append(f"Kunngjort: {pub_date}")

    if act_row.get("journal_number"):
        lines.append(f"Journalnummer: {act_row['journal_number']}")
    if act_row.get("misc_info"):
        short_misc = act_row["misc_info"][:200]
        lines.append(f"Stortingsvedtak: {short_misc}")

    return "\n".join(lines)


# ─── Git Fast-Import Stream ─────────────────────────────────────────────────


class FastImportStream:
    """Build a git fast-import command stream for creating backdated commits."""

    def __init__(
        self,
        repo_path: str,
        committer_name: str = "Lovtidend",
        committer_email: str = "lovtidend@lovdata.no",
    ):
        self.repo_path = repo_path
        self.committer_name = committer_name
        self.committer_email = committer_email
        self.mark_counter = 0
        self.commands = []

    def _next_mark(self) -> int:
        self.mark_counter += 1
        return self.mark_counter

    def add_initial_commit(
        self,
        files: dict[str, str],
        timestamp: str,
        message: str = "Initial import av gjeldende lover",
    ):
        """Add the initial commit with all law files."""
        mark = self._next_mark()
        ts = date_to_git_timestamp(timestamp)

        self.commands.append("commit refs/heads/main")
        self.commands.append(f"mark :{mark}")
        self.commands.append(
            f"author {self.committer_name} <{self.committer_email}> {ts}"
        )
        self.commands.append(
            f"committer {self.committer_name} <{self.committer_email}> {ts}"
        )

        msg_bytes = message.encode("utf-8")
        self.commands.append(f"data {len(msg_bytes)}")
        self.commands.append(message)

        for filepath, content in sorted(files.items()):
            content_bytes = content.encode("utf-8")
            self.commands.append(f"M 100644 inline {filepath}")
            self.commands.append(f"data {len(content_bytes)}")
            self.commands.append(content)

        self.commands.append("")

    def add_amendment_commit(
        self, act_row: dict, affected_files: dict[str, str | None]
    ):
        """Add a commit for a single amendment act.

        Args:
            act_row: Amendment act data (dict with refid, dates, etc.).
            affected_files: Map of filepath → new content (None = delete).
        """
        effective_date, is_deferred = parse_effective_date(
            act_row.get("date_in_force", ""),
            act_row.get("date_published", ""),
        )
        pub_date = parse_publication_date(act_row.get("date_published", ""))
        mark = self._next_mark()

        author_ts = date_to_git_timestamp(effective_date)
        committer_ts = date_to_git_timestamp(pub_date)
        message = format_commit_message(act_row)
        msg_bytes = message.encode("utf-8")

        self.commands.append("commit refs/heads/main")
        self.commands.append(f"mark :{mark}")
        self.commands.append(
            f"author Stortinget <stortinget@stortinget.no> {author_ts}"
        )
        self.commands.append(
            f"committer {self.committer_name} <{self.committer_email}> {committer_ts}"
        )
        self.commands.append(f"data {len(msg_bytes)}")
        self.commands.append(message)

        for filepath, content in sorted(affected_files.items()):
            if content is None:
                self.commands.append(f"D {filepath}")
            else:
                content_bytes = content.encode("utf-8")
                self.commands.append(f"M 100644 inline {filepath}")
                self.commands.append(f"data {len(content_bytes)}")
                self.commands.append(content)

        self.commands.append("")

    def execute(self):
        """Execute the fast-import stream against the repository."""
        stream = "\n".join(self.commands) + "\n"
        proc = subprocess.run(
            ["git", "fast-import", "--quiet"],
            input=stream.encode("utf-8"),
            cwd=self.repo_path,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git fast-import failed: {proc.stderr.decode()}")
        subprocess.run(
            ["git", "checkout", "main"], cwd=self.repo_path, capture_output=True
        )


# ─── Tag Utilities ───────────────────────────────────────────────────────────


def generate_tag_readme(law_files: dict[str, str], all_files: dict[str, str]) -> str:
    """Generate a README.md for the lover/ directory listing all laws by department."""
    groups = defaultdict(list)
    for refid, filepath in law_files.items():
        content = all_files.get(filepath, "")
        m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        meta = {}
        if m:
            for line in m.group(1).splitlines():
                k, _, v = line.partition(":")
                if v:
                    meta[k.strip()] = v.strip().strip('"')
        dept = meta.get("departement", "Annet") or "Annet"
        kort = meta.get("korttittel", "")
        filename = filepath.split("/")[-1] if "/" in filepath else filepath
        groups[dept].append((meta.get("tittel", refid), kort, filename))

    lines = [f"# Norges lover ({len(law_files)} lover)\n"]
    lines.append(
        "Denne filen er auto-generert for å gjøre tag-visningen lesbar på GitHub.\n"
    )
    for dept in sorted(groups.keys()):
        laws = sorted(groups[dept], key=lambda x: x[0])
        lines.append(f"## {dept} ({len(laws)})\n")
        lines.append("| Lov | Korttittel |")
        lines.append("|-----|-----------|")
        for tittel, kort, filename in laws:
            lines.append(f"| [{filename}]({filename}) | {kort} |")
        lines.append("")
    return "\n".join(lines)


def create_yearly_tags(repo_path: str) -> dict[str, str]:
    """Create yearly version tags based on the last commit of each year."""
    log = subprocess.run(
        ["git", "log", "--format=%H %aI", "--reverse"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    year_commits = {}
    for line in log.stdout.strip().split("\n"):
        if not line.strip():
            continue
        sha, date = line.split(" ", 1)
        year = date[:4]
        year_commits[year] = sha

    tags = {}
    for year in sorted(year_commits):
        tag_name = f"v{year}"
        subprocess.run(
            ["git", "tag", "-f", tag_name, year_commits[year]],
            cwd=repo_path,
            capture_output=True,
        )
        tags[tag_name] = year_commits[year]

    return tags


# ─── Build History Pipeline ──────────────────────────────────────────────────


def setup_lfs(repo_path: str) -> None:
    """Initialize git-lfs and track law/forskrift markdown files."""
    subprocess.run(["git", "lfs", "install", "--local"], cwd=repo_path, capture_output=True)
    for pattern in ["lover/*.md", "forskrifter/*.md"]:
        subprocess.run(
            ["git", "lfs", "track", pattern],
            cwd=repo_path,
            capture_output=True,
        )


def build_history(
    snapshot_dir: str,
    repo_path: str,
    mode: str = "year",
    use_lfs: bool = False,
) -> str:
    """Build a git repository with backdated commits from a snapshot.

    Args:
        snapshot_dir: Path to the snapshot directory.
        repo_path: Path to the git repository to build.
        mode: 'year' (default, one commit per year batch) or 'act'
            (one commit per amendment act, ~2400 commits).
        use_lfs: If True, configure git-lfs to track lover/*.md before
            committing. Required when mode='act' to dodge GitHub's
            HTTP 500 on dense object graphs.

    Returns:
        The repo path.
    """
    from .formatter import format_law_markdown
    from lovdata_loader.reconstruct import (
        strip_trailing_text, apply_amendment, parse_instruction,
    )

    snapshot = Path(snapshot_dir)
    laws_dir = snapshot / "laws"
    forskrifter_dir = snapshot / "forskrifter"
    db_path = str(snapshot / "amendments.db")

    # Initialize git repo
    subprocess.run(
        ["git", "init", "--initial-branch=main", repo_path], capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Lovtidend"],
        cwd=repo_path,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "lovtidend@lovdata.no"],
        cwd=repo_path,
        capture_output=True,
    )

    # Load and format all laws and forskrifter. Initial commit gets full
    # text — amendments modify from there.
    print("  Reading laws and forskrifter from snapshot...")
    law_refids = {}
    law_dicts = {}
    all_files = {}

    from lovdata_loader.reconstruct import (
        strip_trailing_text, apply_amendment, parse_instruction,
    )

    json_paths = sorted(laws_dir.glob("*.json"))
    if forskrifter_dir.exists():
        json_paths += sorted(forskrifter_dir.glob("*.json"))

    for path in json_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        refid = data.get("refid", "")
        if not refid:
            continue
        strip_trailing_text(data)
        md = format_law_markdown(data)
        filepath = refid_to_filepath(refid)
        all_files[filepath] = md
        law_refids[refid] = filepath
        law_dicts[refid] = data

    readme_md = generate_tag_readme(law_refids, all_files)
    all_files["lover/README.md"] = readme_md

    if use_lfs:
        all_files[".gitattributes"] = (
            "lover/*.md filter=lfs diff=lfs merge=lfs -text\n"
            "forskrifter/*.md filter=lfs diff=lfs merge=lfs -text\n"
        )
        setup_lfs(repo_path)

    print(f"  {len(law_refids)} laws formatted")

    stream = FastImportStream(repo_path)
    stream.add_initial_commit(
        all_files,
        timestamp="2001-01-01",
        message=f"Grunnlinje: {len(law_refids)} gjeldende lover\n\n"
        f"Kilde: gjeldende-lover.tar.bz2 (Lovdata API)\n"
        f"Lisens: NLOD 2.0",
    )
    print(f"  Initial commit: {len(all_files)} files")

    # Save original current text before amendments mutate law_dicts
    original_texts = dict(all_files)
    body_modified = set()

    # Read amendment acts from SQLite, batch by year
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT refid, title, short_title, date_in_force, date_in_force_resolved,
               date_published, ministry, changes_to, misc_info, journal_number
        FROM amendment_acts
        ORDER BY date_in_force_resolved ASC, date_published ASC
    """
    ).fetchall()

    year_files = defaultdict(dict)
    year_acts = defaultdict(list)
    year_last_date = {}

    for row in rows:
        act = dict(row)
        changes_to = [r for r in act.get("changes_to", "").split(",") if r.strip()]
        date = act["date_in_force_resolved"] or "2001-01-01"
        year = date[:4]
        year_last_date[year] = max(year_last_date.get(year, ""), date)

        act_amendments = conn.execute(
            """
            SELECT change_type, target_law, instruction, new_text
            FROM amendments
            WHERE act_refid = ? AND length(new_text) > 0
        """,
            (act["refid"],),
        ).fetchall()

        affected_for_act = {}
        for law_refid in changes_to:
            filepath = law_refids.get(law_refid)
            if not filepath or filepath not in all_files:
                continue

            law_data = law_dicts.get(law_refid)
            if not law_data:
                continue

            text_changed = False
            for ctype, tlaw, instr, new_text in act_amendments:
                if tlaw == law_refid:
                    if apply_amendment(law_data, instr, new_text, ctype):
                        text_changed = True

            if text_changed:
                content = format_law_markdown(law_data)
                body_modified.add(law_refid)
            else:
                content = all_files[filepath]

            if "sist-endret:" in content:
                content = re.sub(
                    r'sist-endret: ".*?"',
                    f'sist-endret: "{act["refid"]}"',
                    content,
                    count=1,
                )
            else:
                content = content.replace(
                    "\n---\n\n",
                    f'\nsist-endret: "{act["refid"]}"\n---\n\n',
                    1,
                )
            year_files[year][filepath] = content
            all_files[filepath] = content
            affected_for_act[filepath] = content

        year_acts[year].append(act["refid"])

        if mode == "act" and affected_for_act:
            stream.add_amendment_commit(act, affected_for_act)

    conn.close()

    if mode == "year":
        # Emit one commit per year
        for year in sorted(year_files.keys()):
            files = year_files[year]
            act_count = len(year_acts[year])
            act_data = {
                "refid": f"lovtidend/{year}",
                "title": f"Endringslov {year} ({act_count} lover)",
                "short_title": "",
                "date_in_force": year_last_date.get(year, f"{year}-12-31"),
                "date_in_force_resolved": year_last_date.get(year, f"{year}-12-31"),
                "date_published": year_last_date.get(year, f"{year}-12-31"),
            }
            stream.add_amendment_commit(act_data, files)

    # Single reset commit: snap all body-modified laws and forskrifter back to current text.
    reset_files = {}
    latest_date = "2001-01-01"
    reset_paths = sorted(laws_dir.glob("*.json"))
    if forskrifter_dir.exists():
        reset_paths += sorted(forskrifter_dir.glob("*.json"))
    for path in reset_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        refid = data.get("refid", "")
        if not refid or refid not in body_modified:
            continue
        filepath = law_refids[refid]
        effective = data.get("last_amended_in_force", "") or data.get("date_in_force", "")
        if effective and effective > latest_date:
            latest_date = effective
        current = original_texts.get(filepath, "")
        if current and current != all_files.get(filepath, ""):
            reset_files[filepath] = current
            all_files[filepath] = current

    if reset_files:
        act_data = {
            "refid": f"gjeldende-lover/{latest_date}",
            "title": f"Gjeldende konsolidert tekst ({len(reset_files)} lover)",
            "short_title": "",
            "date_in_force": latest_date,
            "date_in_force_resolved": latest_date,
            "date_published": latest_date,
        }
        stream.add_amendment_commit(act_data, reset_files)

    if mode == "act":
        commit_count_label = f"~{sum(len(v) for v in year_acts.values())} per-act"
    else:
        commit_count_label = f"{len(year_files)} year batches"
    print(
        f"  Generated {stream.mark_counter} commits "
        f"(1 initial + {commit_count_label} + {'1 reset' if reset_files else '0 resets'})"
    )

    # Execute
    print("  Running git fast-import...")
    stream.execute()

    # Yearly tags
    tags = create_yearly_tags(repo_path)
    if tags:
        print(f"  Created {len(tags)} yearly tags: {min(tags)}..{max(tags)}")

    # Verify
    total_commits = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    print(f"  Repository built: {total_commits.stdout.strip()} commits")

    return repo_path
