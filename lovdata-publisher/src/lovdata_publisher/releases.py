"""Tag monthly stable releases on the law-history branch.

Creates git tags at the last commit of each month (by author date),
plus a rolling 'current' tag at HEAD. Generates release notes
summarizing which laws were amended in each period.
"""
from __future__ import annotations
import subprocess
import re
from dataclasses import dataclass
from datetime import datetime

GITHUB_BASE = "https://github.com/sondreskarsten/norwegian-laws"


@dataclass
class TagPoint:
    tag: str
    commit: str
    date: str
    subject: str


def git(args: list[str], repo: str) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


def get_commits_by_author_date(repo: str) -> list[dict]:
    raw = git(["log", "--format=%H%x00%ai%x00%s", "--reverse"], repo)
    commits = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x00", 2)
        if len(parts) < 3:
            continue
        commits.append({
            "hash": parts[0],
            "author_date": parts[1].strip(),
            "subject": parts[2].strip(),
        })
    return commits


def compute_monthly_tags(commits: list[dict]) -> tuple[list[TagPoint], str]:
    initial_commit = commits[0]["hash"] if commits else ""
    month_last = {}
    for c in commits[1:]:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", c["author_date"])
        if not m:
            continue
        year, month = m.group(1), m.group(2)
        key = f"{year}-{month}"
        month_last[key] = c

    tags = []
    for key in sorted(month_last.keys()):
        c = month_last[key]
        m = re.match(r"(\d{4}-\d{2}-\d{2})", c["author_date"])
        tags.append(TagPoint(
            tag=key,
            commit=c["hash"],
            date=m.group(1) if m else key + "-01",
            subject=c["subject"],
        ))
    return tags, initial_commit


def get_changes_between(repo: str, old_commit: str | None, new_commit: str) -> dict:
    if old_commit:
        diff_raw = git(
            ["diff", "--name-status", old_commit, new_commit, "--", "lover/"],
            repo,
        )
    else:
        diff_raw = git(
            ["diff-tree", "--name-status", "-r", "--root", new_commit, "--", "lover/"],
            repo,
        )

    added, modified, deleted = [], [], []
    for line in diff_raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        status = parts[0].strip()
        path = parts[1].strip() if len(parts) > 1 else ""
        name = path.replace("lover/", "").replace(".md", "")
        if status == "A":
            added.append(name)
        elif status == "M":
            modified.append(name)
        elif status == "D":
            deleted.append(name)

    return {"added": added, "modified": modified, "deleted": deleted}


def count_commits_between(repo: str, old_commit: str | None, new_commit: str) -> int:
    if old_commit:
        raw = git(["rev-list", "--count", f"{old_commit}..{new_commit}"], repo)
    else:
        raw = git(["rev-list", "--count", new_commit], repo)
    return int(raw)


def format_release_notes(
    tag: TagPoint,
    prev_tag: TagPoint | None,
    next_tag: TagPoint | None,
    changes: dict,
    commit_count: int,
) -> str:
    lines = []
    lines.append(f"## Norges lover per {tag.date}")
    lines.append("")

    if prev_tag:
        lines.append(
            f"Endringer siden [{prev_tag.tag}]({GITHUB_BASE}/tree/{prev_tag.tag}) "
            f"({commit_count} endringsvedtak):"
        )
    else:
        lines.append(f"Første stabile versjon ({commit_count} endringsvedtak).")
    lines.append("")

    if changes["modified"]:
        lines.append(f"### Endret ({len(changes['modified'])} lover)")
        lines.append("")
        for name in sorted(changes["modified"])[:50]:
            blob = f"{GITHUB_BASE}/blob/{tag.tag}/lover/{name}.md"
            lines.append(f"- [{name}]({blob})")
        if len(changes["modified"]) > 50:
            lines.append(f"- ... og {len(changes['modified']) - 50} flere")
        lines.append("")

    if changes["added"]:
        lines.append(f"### Nye lover ({len(changes['added'])})")
        lines.append("")
        for name in sorted(changes["added"])[:20]:
            blob = f"{GITHUB_BASE}/blob/{tag.tag}/lover/{name}.md"
            lines.append(f"- [{name}]({blob})")
        if len(changes["added"]) > 20:
            lines.append(f"- ... og {len(changes['added']) - 20} flere")
        lines.append("")

    if changes["deleted"]:
        lines.append(f"### Opphevet ({len(changes['deleted'])})")
        lines.append("")
        for name in sorted(changes["deleted"]):
            lines.append(f"- {name}")
        lines.append("")

    if prev_tag:
        compare = f"{GITHUB_BASE}/compare/{prev_tag.tag}...{tag.tag}"
        lines.append(f"[Full diff mot {prev_tag.tag}]({compare})")
        lines.append("")

    lines.append("---")
    nav_parts = []
    if prev_tag:
        nav_parts.append(f"[← {prev_tag.tag}]({GITHUB_BASE}/releases/tag/{prev_tag.tag})")
    nav_parts.append(f"[Alle versjoner]({GITHUB_BASE}/tags)")
    if next_tag:
        nav_parts.append(f"[{next_tag.tag} →]({GITHUB_BASE}/releases/tag/{next_tag.tag})")
    lines.append(f"*Navigasjon:* {' | '.join(nav_parts)}")

    return "\n".join(lines)


def create_tags(repo: str, dry_run: bool = False) -> list[tuple[TagPoint, str]]:
    commits = get_commits_by_author_date(repo)
    if not commits:
        print("  No commits found")
        return []

    tags, initial_commit = compute_monthly_tags(commits)
    print(f"  Found {len(tags)} monthly tag points (initial commit: {initial_commit[:8]})")

    current_commit = commits[-1]["hash"]
    current_tag = TagPoint(
        tag="current",
        commit=current_commit,
        date=datetime.now().strftime("%Y-%m-%d"),
        subject="Siste tilgjengelige versjon",
    )
    all_tags = tags + [current_tag]

    tag_data = []
    prev_commit = initial_commit
    for i, tag in enumerate(all_tags):
        changes = get_changes_between(repo, prev_commit, tag.commit)
        commit_count = count_commits_between(repo, prev_commit, tag.commit)
        tag_data.append((tag, changes, commit_count))
        prev_commit = tag.commit

    results = []
    for i, (tag, changes, commit_count) in enumerate(tag_data):
        prev_tag = all_tags[i - 1] if i > 0 else None
        next_tag = all_tags[i + 1] if i < len(all_tags) - 1 else None
        notes = format_release_notes(tag, prev_tag, next_tag, changes, commit_count)

        if not dry_run:
            try:
                git(["tag", "-d", tag.tag], repo)
            except RuntimeError:
                pass
            git(["tag", "-a", tag.tag, tag.commit, "-m", f"Norges lover per {tag.date}"], repo)

        results.append((tag, notes))

    print(f"  Created {len(results)} tags ({len(tags)} monthly + current)")
    return results


def push_tags(repo: str, remote: str = "origin"):
    git(["push", remote, "--tags", "--force"], repo)
    print("  Pushed all tags")


if __name__ == "__main__":
    import sys
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    dry = "--dry-run" in sys.argv
    results = create_tags(repo_path, dry_run=dry)
    for tag, notes in results:
        print(f"\n{'='*60}")
        print(f"TAG: {tag.tag} @ {tag.commit[:8]} ({tag.date})")
        print(f"{'='*60}")
        print(notes)
