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
MAX_DELTA_CHARS = 20000


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

    lines = ["# Endringer i denne kjøringen\n"]
    used = len(lines[0]) + 1

    if new:
        lines.append(f"## Nye dokumenter ({len(new)})\n")
        used += len(lines[-1]) + 1
        for i, e in enumerate(new):
            line = f"- **{e['refid']}** — {e['tittel']}"
            if e["departement"]:
                line += f"  _[{e['departement']}]_"
            if used + len(line) + 1 > MAX_DELTA_CHARS // 2:
                lines.append(f"- _… og {len(new) - i} til_")
                break
            lines.append(line)
            used += len(line) + 1
        lines.append("")

    if mod:
        by_source = defaultdict(list)
        for e in mod:
            by_source[e["sist-endret"] or "(ukjent kilde)"].append(e)
        lines.append(f"## Endrede dokumenter ({len(mod)}), gruppert etter kildelov\n")
        used = sum(len(l) + 1 for l in lines)
        sources = sorted(by_source, reverse=True)
        for i, src in enumerate(sources):
            group = by_source[src]
            block = [f"- **{src}** endrer {len(group)} dokument(er):"]
            for e in group[:MAX_EXAMPLES_PER_GROUP]:
                block.append(f"    - {e['refid']} — {e['tittel']}")
            if len(group) > MAX_EXAMPLES_PER_GROUP:
                block.append(f"    - _… og {len(group) - MAX_EXAMPLES_PER_GROUP} til_")
            block_len = sum(len(l) + 1 for l in block)
            if used + block_len > MAX_DELTA_CHARS:
                rest_groups = len(sources) - i
                rest_docs = sum(len(by_source[s]) for s in sources[i:])
                lines.append(
                    f"- _… og {rest_groups} kildelov(er) til som endrer "
                    f"{rest_docs} dokument(er)_"
                )
                break
            lines.extend(block)
            used += block_len
        lines.append("")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
