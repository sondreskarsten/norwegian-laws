"""Git operations for building law history with backdated commits.

Handles FastImportStream generation, commit message formatting,
yearly tagging, and repository construction from snapshot data.
"""
from __future__ import annotations
import re
import subprocess
import sqlite3
import json
import tempfile
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


class _SpooledCommands:
    """List-like sink that writes each fast-import line straight to a file."""

    def __init__(self, spool):
        self._spool = spool

    def append(self, line: str) -> None:
        self._spool.write(line.encode("utf-8"))
        self._spool.write(b"\n")


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
        # The stream is spooled to disk as it is produced. A per-act build
        # carries the full text of every changed file for ~17,000 commits,
        # which exceeded memory when kept as a list of strings.
        self._spool = tempfile.NamedTemporaryFile("w+b", prefix="law-fast-import-", suffix=".stream", delete=False)
        self.commands = _SpooledCommands(self._spool)

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
        self._spool.flush()
        self._spool.seek(0)
        try:
            proc = subprocess.run(
                ["git", "fast-import", "--quiet"],
                stdin=self._spool,
                cwd=self.repo_path,
                capture_output=True,
            )
        finally:
            self._spool.close()
            Path(self._spool.name).unlink(missing_ok=True)
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


def create_yearly_tags(repo_path: str, max_year: int | None = None) -> dict[str, str]:
    """Create yearly version tags based on the last commit of each year.

    Years after ``max_year`` (default: the current UTC year) get no tag: a
    published act with a future commencement is not a past version of the law
    (issue #4).
    """
    if max_year is None:
        max_year = datetime.now(timezone.utc).year
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
        if int(year) > max_year:
            continue
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


# ─── Removed documents ────────────────────────────────────────────────────────

REMOVED_PATH_PREFIXES = ("lover/", "forskrifter/")


def removed_documents(source_repo: str, cutoff_date: str | None = None) -> dict[str, dict]:
    """Documents deleted from ``main`` of the source repository, with their terminal text.

    A document that left the Lovdata corpus is deleted from ``lover/`` or
    ``forskrifter/`` by the daily publication. The reconstruction otherwise
    takes its universe from the current snapshot, so every repealed document
    vanished from every yearly tag (issue #6). This reads each deletion from
    the source repository's history: the text as last published, the commit
    that removed it and that commit's date (the *detected* exit, which is not
    a legal repeal date). Paths that exist again on HEAD are not removed.
    """
    log = subprocess.run(
        ["git", "log", "--diff-filter=D", "--name-only", "--format=%x00%H %cI",
         "--", *REMOVED_PATH_PREFIXES],
        cwd=source_repo, capture_output=True, text=True, check=True,
    ).stdout
    present = set(subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", *REMOVED_PATH_PREFIXES],
        cwd=source_repo, capture_output=True, text=True, check=True,
    ).stdout.split("\n"))
    removed: dict[str, dict] = {}
    sha = date = ""
    for line in log.split("\n"):
        if line.startswith("\x00"):
            sha, _, date = line[1:].partition(" ")
            continue
        path = line.strip()
        if not path or path in removed or path in present:
            continue
        if not path.endswith(".md") or path.endswith("/README.md"):
            continue
        detected = date[:10]
        if cutoff_date and detected > cutoff_date:
            continue
        shown = subprocess.run(["git", "show", f"{sha}^:{path}"], cwd=source_repo,
                               capture_output=True, text=True)
        if shown.returncode != 0 or not shown.stdout:
            continue
        removed[path] = {"text": shown.stdout, "detected_exit": detected, "removal_commit": sha}
    return removed


def _refid_from_markdown(text: str) -> str:
    m = re.search(r'^refid:\s*"?([^"\n]+)"?\s*$', text, flags=re.M)
    return m.group(1).strip() if m else ""


def _title_from_markdown(text: str) -> str:
    m = re.search(r'^tittel:\s*"?([^"\n]+)"?\s*$', text, flags=re.M)
    return m.group(1).strip() if m else ""


_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _explicit_dates(text: str | None) -> list[str]:
    """ISO dates written in an in-force field; 'Kongen bestemmer' yields none."""
    return sorted(set(_ISO_DATE_RE.findall(text or "")))


def legal_repeal(conn: sqlite3.Connection, refid: str, cutoff_date: str) -> tuple[str, str]:
    """(act refid, in-force date) of the earliest whole-document repeal of ``refid`` in Lovtidend.

    Old-format records carry an empty target for a whole-document repeal; new-format
    records (``data-repeal-part``) carry the document's own refid as the target.

    The date is the earliest date written in the repealing act's in-force field.
    When that field says only "Kongen bestemmer", the date comes from a later
    commencement decision ("Ikraftsetting av lov …") that names the repealing act
    or the repealed document; when no such decision carries a date either, the
    act is returned with an empty date and the caller dates the deletion on the
    detected exit. The loader's resolved date is not used here: for a deferred
    act it falls back to the publication date, which is not when the repeal took
    effect.
    """
    rows = conn.execute(
        """
        SELECT ac.refid, ac.date_in_force, ac.date_published FROM amendments a
        JOIN amendment_acts ac ON ac.refid = a.act_refid
        WHERE a.change_type = 'repeal' AND (a.target = '' OR a.target IS NULL OR a.target = a.target_law) AND a.target_law = ?
        ORDER BY ac.date_published ASC
        """,
        (refid,),
    ).fetchall()
    unresolved_act = ""
    for act_refid, in_force, published in rows:
        published = (published or "")[:10]
        dates = [d for d in _explicit_dates(in_force) if d <= cutoff_date]
        if not dates:
            commencement = conn.execute(
                """
                SELECT ac.date_in_force FROM amendments a
                JOIN amendment_acts ac ON ac.refid = a.act_refid
                WHERE a.change_type = 'commencement' AND a.target_law IN (?, ?) AND ac.date_published >= ?
                ORDER BY ac.date_published ASC
                """,
                (act_refid, refid, published),
            ).fetchall()
            for (text,) in commencement:
                dates = [d for d in _explicit_dates(text) if published <= d <= cutoff_date]
                if dates:
                    break
        if dates:
            return act_refid, dates[0]
        unresolved_act = unresolved_act or act_refid
    return unresolved_act, ""


BASELINE_SUBJECT = "Utgangspunkt: gjeldende tekst for {n} dokumenter (ikke tilstanden i 2001)"
RESET_SUBJECT = "Tilbakestilling til gjeldende tekst ({n} dokumenter avvek etter gjenavspilling)"
MANIFEST_PATH = "reconstruction-manifest.json"


def reconstruction_manifest(cutoff_date: str, documents: dict[str, dict], removed: dict[str, dict],
                            replayed: dict[str, int], diverged: set[str]) -> str:
    """JSON describing what the reconstruction is per document (issue #5 item 3).

    ``diverged`` documents are those whose forward replay did not round-trip
    to the current text and were snapped back by the reset commit; their
    yearly states are unreliable. The number is otherwise computed on every
    build and discarded.
    """
    entries = {}
    for refid, path in sorted(documents.items()):
        entries[refid] = {
            "path": path,
            "replayed_acts": replayed.get(refid, 0),
            "diverged": refid in diverged,
        }
    for path, info in sorted(removed.items()):
        refid = info.get("refid") or _refid_from_markdown(info["text"]) or path
        entries[refid] = {
            "path": path,
            "replayed_acts": 0,
            "diverged": False,
            "removed": {
                "detected_exit": info["detected_exit"],
                "removal_commit": info["removal_commit"],
                "legal_repeal_act": info.get("legal_repeal_act", ""),
                "legal_repeal_date": info.get("legal_repeal_date", ""),
                "deletion_date": info.get("deletion_date", info["detected_exit"]),
            },
        }
    manifest = {
        "version": 1,
        "cutoff_date": cutoff_date,
        "baseline": "Current consolidated text dated 2001-01-01; amendments replayed forward where the act carried wording; "
                    "a yearly tag holds current text wherever the replay could not regress it.",
        "counts": {
            "documents": len(documents),
            "diverged": len(diverged),
            "removed": len(removed),
        },
        "documents": entries,
    }
    return json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


# ─── Build History Pipeline ──────────────────────────────────────────────────


def build_history(
    snapshot_dir: str,
    repo_path: str,
    mode: str = "year",
    cutoff_date: str | None = None,
    removed_source: str | None = None,
) -> str:
    """Build a git repository with backdated commits from a snapshot.

    Args:
        snapshot_dir: Path to the snapshot directory.
        repo_path: Path to the git repository to build.
        mode: 'year' (default, one commit per year batch) or 'act'
            (one commit per amendment act, ~17,000 commits). Texts are
            ordinary blobs; fast-import bypasses Git LFS clean filters.
        cutoff_date: YYYY-MM-DD (default: today, UTC). Acts whose resolved
            commencement is after this date are not applied; they are not in
            force and the consolidated text does not contain them. The final
            reset commit is dated on this day so graph order and date order
            agree (issue #4).
        removed_source: path of a checkout of the publication repository
            (``main``). Documents deleted from it are added to the baseline
            with their last published text and removed again by a dated
            deletion commit (issue #6): on the legal repeal date when Lovtidend
            carries a whole-document repeal of it, else on the day the
            publication detected the exit.

    Returns:
        The repo path.
    """
    if cutoff_date is None:
        cutoff_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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

    removed = removed_documents(removed_source, cutoff_date) if removed_source else {}
    for path, info in removed.items():
        if path in all_files:
            continue
        all_files[path] = info["text"]
        info["refid"] = _refid_from_markdown(info["text"]) or path
        info["title"] = _title_from_markdown(info["text"])
    if removed:
        print(f"  {len(removed)} removed documents restored from {removed_source}")

    readme_md = generate_tag_readme(law_refids, all_files)
    all_files["lover/README.md"] = readme_md

    print(f"  {len(law_refids)} laws formatted")

    stream = FastImportStream(repo_path)
    stream.add_initial_commit(
        all_files,
        timestamp="2001-01-01",
        message=BASELINE_SUBJECT.format(n=len(law_refids) + len(removed)) + "\n\n"
        "Dette er dagens konsoliderte tekst datert 2001-01-01, ikke lovene slik de var da. "
        "Endringslover spilles av framover der de bærer ny ordlyd; der avspillingen ikke "
        "treffer, viser årstallstaggene gjeldende tekst. Se reconstruction-manifest.json.\n\n"
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
    skipped_future = 0
    replayed_acts: dict[str, int] = defaultdict(int)

    # A removed document leaves the branch by a dated deletion commit, merged
    # into the act stream so graph order stays date order.
    deletions = []
    for path, info in removed.items():
        act_refid, legal_date = legal_repeal(conn, info["refid"], cutoff_date)
        info["legal_repeal_act"] = act_refid
        info["legal_repeal_date"] = legal_date
        info["deletion_date"] = legal_date or info["detected_exit"]
        deletions.append((info["deletion_date"], path, info))
    events = [(row["date_in_force_resolved"] or "2001-01-01", 0, row) for row in rows]
    events += [(date, 1, (path, info)) for date, path, info in deletions]
    events.sort(key=lambda e: (e[0], e[1]))

    for date, kind, payload in events:
        if kind == 1:
            path, info = payload
            if date > cutoff_date:
                continue
            year = date[:4]
            year_last_date[year] = max(year_last_date.get(year, ""), date)
            if info["legal_repeal_act"] and info["legal_repeal_date"]:
                legal = f"Rettslig opphevelse: {info['legal_repeal_act']} i kraft {info['legal_repeal_date']}"
            elif info["legal_repeal_act"]:
                legal = (f"Rettslig opphevelse: {info['legal_repeal_act']} (ikrafttredelsen er ikke fastsatt i "
                         f"Lovtidend; slettet på registrert uttak)")
            else:
                legal = "Rettslig opphevelse: ikke funnet i Lovtidend"
            act_data = {
                "refid": f"opphevet/{info['refid']}",
                "title": f"Opphevet: {info.get('title') or info['refid']}",
                "short_title": "",
                "date_in_force": date,
                "date_in_force_resolved": date,
                "date_published": info["detected_exit"],
                "misc_info": f"{legal}. Registrert fjernet fra kilden: {info['detected_exit']} "
                             f"(commit {info['removal_commit'][:12]} på main).",
            }
            year_files[year][path] = None
            all_files.pop(path, None)
            year_acts[year].append(act_data["refid"])
            if mode == "act":
                stream.add_amendment_commit(act_data, {path: None})
            continue

        row = payload
        act = dict(row)
        changes_to = [r for r in act.get("changes_to", "").split(",") if r.strip()]
        if date > cutoff_date:
            skipped_future += 1
            continue
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
                replayed_acts[law_refid] += 1
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

    if skipped_future:
        print(f"  Skipped {skipped_future} acts with commencement after {cutoff_date}")

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

    diverged = set(refid for refid in body_modified if law_refids.get(refid) in reset_files)
    manifest = reconstruction_manifest(cutoff_date, law_refids, removed, replayed_acts, diverged)
    reset_files[MANIFEST_PATH] = manifest
    act_data = {
        "refid": f"gjeldende-lover/{cutoff_date}",
        "title": RESET_SUBJECT.format(n=len(diverged)),
        "short_title": "",
        "date_in_force": cutoff_date,
        "date_in_force_resolved": cutoff_date,
        "date_published": cutoff_date,
        "misc_info": f"Siste registrerte ikrafttredelse i kilden: {latest_date}. "
                     f"Dokumenter som avvek etter gjenavspilling er listet i {MANIFEST_PATH}.",
    }
    stream.add_amendment_commit(act_data, reset_files)

    if mode == "act":
        commit_count_label = f"~{sum(len(v) for v in year_acts.values())} per-act"
    else:
        commit_count_label = f"{len(year_files)} year batches"
    print(
        f"  Generated {stream.mark_counter} commits "
        f"(1 initial + {commit_count_label} + 1 reset, {len(diverged)} diverged, {len(removed)} removed)"
    )

    # Execute
    print("  Running git fast-import...")
    stream.execute()

    # Yearly tags, never beyond the cutoff year
    tags = create_yearly_tags(repo_path, max_year=int(cutoff_date[:4]))
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
