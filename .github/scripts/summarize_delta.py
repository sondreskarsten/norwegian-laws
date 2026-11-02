#!/usr/bin/env python3
"""Write a factual summary of the documents a publication run changed.

Reads the same working-tree changes under lover/ and forskrifter/ as
extract_delta.py and prints a bokmål summary: a count line, the new
documents with their titles and departments, and the modified documents
grouped by the amending act recorded in their sist-endret field. Nothing is
inferred from the text; a reader who wants the substance opens the diff.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_delta import committed_sist_endret, get_changes, parse_frontmatter  # noqa: E402

MAX_NEW = 40
MAX_SOURCES = 40
MAX_TARGETS_PER_SOURCE = 6


def _name(entry: dict) -> str:
    return entry.get("korttittel") or entry.get("tittel") or entry["refid"]


def collect() -> tuple[list[dict], list[dict]]:
    new, modified = [], []
    for kind, path in get_changes():
        if not path.is_file():
            continue
        fm = parse_frontmatter(path)
        sist = fm.get("sist-endret", "").strip('"')
        if kind == "modified" and committed_sist_endret(path) == sist:
            continue
        entry = {
            "refid": fm.get("refid", str(path)),
            "tittel": fm.get("tittel", "").strip('"'),
            "korttittel": fm.get("korttittel", "").strip('"'),
            "departement": fm.get("departement", "").strip('"'),
            "sist-endret": sist,
        }
        (new if kind == "new" else modified).append(entry)
    new.sort(key=lambda e: e["refid"])
    modified.sort(key=lambda e: e["refid"])
    return new, modified


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def summarize(new: list[dict], modified: list[dict]) -> str:
    if not new and not modified:
        return ""
    parts = []
    if new:
        parts.append(_plural(len(new), "nytt dokument", "nye dokumenter"))
    if modified:
        parts.append(_plural(len(modified), "endret dokument", "endrede dokumenter"))
    lines = [" og ".join(parts) + " i denne publiseringen.", ""]
    if new:
        lines.append("Nye dokumenter:")
        for entry in new[:MAX_NEW]:
            line = f"- {entry['refid']}: {entry['tittel'] or entry['korttittel'] or '(uten tittel)'}"
            if entry["departement"]:
                line += f" ({entry['departement']})"
            lines.append(line)
        if len(new) > MAX_NEW:
            lines.append(f"- … og {len(new) - MAX_NEW} til")
        lines.append("")
    if modified:
        by_source: dict[str, list[dict]] = defaultdict(list)
        for entry in modified:
            by_source[entry["sist-endret"] or "(endringskilde ikke oppgitt)"].append(entry)
        lines.append("Endrede dokumenter etter endringskilde:")
        sources = sorted(by_source, reverse=True)
        for source in sources[:MAX_SOURCES]:
            group = by_source[source]
            targets = "; ".join(f"{e['refid']} {_name(e)}" for e in group[:MAX_TARGETS_PER_SOURCE])
            if len(group) > MAX_TARGETS_PER_SOURCE:
                targets += f"; … og {len(group) - MAX_TARGETS_PER_SOURCE} til"
            lines.append(f"- {source} endrer {_plural(len(group), 'dokument', 'dokumenter')}: {targets}")
        if len(sources) > MAX_SOURCES:
            rest = sum(len(by_source[s]) for s in sources[MAX_SOURCES:])
            lines.append(f"- … og {len(sources) - MAX_SOURCES} endringskilder til som endrer {rest} dokumenter")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    new, modified = collect()
    sys.stdout.write(summarize(new, modified))


if __name__ == "__main__":
    main()
