#!/usr/bin/env python3
"""Extract delta of changed law/forskrift files for AI summarisation.

Reads git status under lover/ and forskrifter/, parses frontmatter, prints a
compact Markdown briefing to stdout. New documents are enumerated in full;
modified documents are grouped by their source amendment and truncated to
keep the prompt small.
"""
import subprocess
import re
import sys
from pathlib import Path
from collections import defaultdict


MAX_EXAMPLES_PER_GROUP = 5


def get_changes() -> list[tuple[str, Path]]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", "lover/", "forskrifter/"],
        capture_output=True, text=True, check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        if not line:
            continue
        code = line[:2]
        path = line[3:].strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        flag = code.strip()
        if flag in ("M", "A", "??", "AM", "MM"):
            kind = "new" if flag in ("A", "??") else "modified"
            rows.append((kind, Path(path)))
    return rows


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    try:
        end = text.index("\n---\n", 4)
    except ValueError:
        return {}
    fm = text[4:end]
    out = {}
    for line in fm.splitlines():
        m = re.match(r'^([\w-]+):\s*"?(.*?)"?\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def main() -> None:
    changes = get_changes()
    if not changes:
        sys.exit(0)

    new, mod = [], []
    for kind, p in changes:
        if not p.exists():
            continue
        fm = parse_frontmatter(p)
        entry = {
            "refid": fm.get("refid", str(p)),
            "tittel": fm.get("tittel", "").strip('"'),
            "departement": fm.get("departement", "").strip('"'),
            "sist-endret": fm.get("sist-endret", "").strip('"'),
        }
        (new if kind == "new" else mod).append(entry)

    print("# Endringer i denne kjøringen\n")

    if new:
        print(f"## Nye dokumenter ({len(new)})\n")
        for e in new:
            line = f"- **{e['refid']}** — {e['tittel']}"
            if e["departement"]:
                line += f"  _[{e['departement']}]_"
            print(line)
        print()

    if mod:
        by_source = defaultdict(list)
        for e in mod:
            by_source[e["sist-endret"] or "(ukjent kilde)"].append(e)
        print(f"## Endrede dokumenter ({len(mod)}), gruppert etter kildelov\n")
        for src in sorted(by_source, reverse=True):
            group = by_source[src]
            print(f"- **{src}** endrer {len(group)} dokument(er):")
            for e in group[:MAX_EXAMPLES_PER_GROUP]:
                print(f"    - {e['refid']} — {e['tittel']}")
            if len(group) > MAX_EXAMPLES_PER_GROUP:
                print(f"    - _… og {len(group) - MAX_EXAMPLES_PER_GROUP} til_")
        print()


if __name__ == "__main__":
    main()
