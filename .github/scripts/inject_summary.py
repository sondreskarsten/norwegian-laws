#!/usr/bin/env python3
"""Inject AI-generated summary into README, RELEASES.md, and a commit body file.

Reads the summary from the SUMMARY environment variable. Writes:
  - README.md  : updates content between <!-- AI_SUMMARY_START/END --> markers
  - RELEASES.md: prepends a dated section under the top-level header
  - /tmp/commit-msg.txt: full commit message with subject + summary body
"""
import os
import re
from pathlib import Path
from datetime import datetime, timezone


LABEL = "🤖 AI-generated summary (GitHub Models)"
AI_START = "<!-- AI_SUMMARY_START -->"
AI_END = "<!-- AI_SUMMARY_END -->"
RECENT_MARKER = "<!-- RECENT_AMENDMENTS_START -->"


def update_readme(summary: str, today: str) -> None:
    readme = Path("README.md")
    text = readme.read_text(encoding="utf-8")

    block = (
        f"{AI_START}\n"
        f"*{LABEL} · {today}*\n\n"
        f"{summary}\n"
        f"{AI_END}"
    )

    if AI_START in text and AI_END in text:
        text = re.sub(
            re.escape(AI_START) + r".*?" + re.escape(AI_END),
            lambda _: block,
            text,
            count=1,
            flags=re.DOTALL,
        )
    else:
        text = text.replace(RECENT_MARKER, f"{block}\n\n{RECENT_MARKER}", 1)

    readme.write_text(text, encoding="utf-8")


def update_releases(summary: str, today: str) -> None:
    releases = Path("RELEASES.md")
    section = f"## {today}\n\n*{LABEL}*\n\n{summary}\n"

    if releases.exists():
        existing = releases.read_text(encoding="utf-8")
        if existing.startswith("# "):
            head_end = existing.index("\n") + 1
            new_text = existing[:head_end] + "\n" + section + "\n" + existing[head_end:]
        else:
            new_text = "# Release notes\n\n" + section + "\n" + existing
    else:
        new_text = f"# Release notes\n\n{section}\n"

    releases.write_text(new_text, encoding="utf-8")


def write_commit_body(summary: str, today: str) -> None:
    body = (
        f"Oppdater lover og forskrifter fra Lovdata API {today} [skip ci]\n\n"
        f"{LABEL}\n\n"
        f"{summary}\n"
    )
    Path("/tmp/commit-msg.txt").write_text(body, encoding="utf-8")


def main() -> None:
    summary = os.environ.get("SUMMARY", "").strip()
    if not summary:
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    update_readme(summary, today)
    update_releases(summary, today)
    write_commit_body(summary, today)


if __name__ == "__main__":
    main()
