"""Catalogue of Lovtidend amendment-instruction wordings.

``instruction_catalog.json`` lists every operation wording the parser has
met in the 2001– Lovtidend archives (``skal lyde``, ``oppheves``,
``Nåværende … blir …`` and so on), in both written languages, with the
effect each has on the target document.  The catalogue is the contract
behind node-level history: a wording that is not in it cannot be applied
to a provision, so it must be added by a pull request before the parser can
attribute the change.

``report`` classifies every instruction in a snapshot against the catalogue
and lists the *unknown forms*: texts that look like an amendment instruction
(short, name a target unit, end like an instruction) but match no catalogued
operation.  The deploy workflow turns a non-empty list into a GitHub issue.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from importlib import resources
from pathlib import Path
from typing import Iterable

_LAWREF_RE = re.compile(
    r"\b(?:lov|forskrift|forskrifter|regler|vedtekter|instruks)\s+(?:av\s+)?\d{1,2}\.\s*\w+\s+\d{4}\s+nr\.\s*\d+",
    re.I,
)
_SECTION_RE = re.compile(r"§§?\s*\d+[\w-]*(?:\s+[a-zæøå](?!\w))?")
_DATE_RE = re.compile(r"\b\d{1,2}\.\s*(?:januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|desember)\s+\d{4}\b", re.I)
_QUOTE_RE = re.compile(r"[«»\"“”]([^«»\"“”]*)[«»\"“”]")
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)*\b")
_SPACE_RE = re.compile(r"\s+")
_LEADING_MARKER_RE = re.compile(r"^(?:\d+\.|[IVXL]+\.|[A-Z]\.)\s+")


def load_catalog(path: str | Path | None = None) -> dict:
    if path is None:
        text = resources.files(__package__).joinpath("instruction_catalog.json").read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


class InstructionCatalog:
    def __init__(self, catalog: dict | None = None):
        self.catalog = catalog or load_catalog()
        self.version = self.catalog["version"]
        self._operations = [
            (op["id"], [re.compile(p, re.I | re.S) for p in op["patterns"]])
            for op in self.catalog["operations"]
        ]
        like = self.catalog["instruction_like"]
        self._max_length = like["max_length"]
        self._target = re.compile(like["target_pattern"], re.I)
        self._terminators = tuple(like["terminators"])
        self._reviewed = set(self.catalog.get("reviewed_non_instructions", []))

    @property
    def operation_ids(self) -> list[str]:
        return [op_id for op_id, _ in self._operations]

    def classify(self, text: str) -> list[str]:
        """Return the ids of every catalogued operation whose wording occurs in ``text``."""
        text = _SPACE_RE.sub(" ", (text or "").strip())
        return [op_id for op_id, patterns in self._operations if any(p.search(text) for p in patterns)]

    def instruction_like(self, text: str) -> bool:
        """True for a short text that names a target unit and ends like an instruction."""
        text = _SPACE_RE.sub(" ", (text or "").strip())
        return (
            0 < len(text) <= self._max_length
            and text.endswith(self._terminators)
            and bool(self._target.search(text))
        )

    def report(self, instructions: Iterable[tuple[str, str, str]]) -> dict:
        """Classify ``(act_refid, change_type, instruction)`` rows.

        ``unknown_forms`` lists instruction-like texts without any catalogued
        operation, grouped by normalised form, excluding forms reviewed as
        non-instructions.  Parser classification is reported next to the
        catalogue's so drift between them is visible.
        """
        by_operation: Counter[str] = Counter()
        by_parser_type: Counter[str] = Counter()
        combos: Counter[str] = Counter()
        unknown: Counter[str] = Counter()
        unknown_examples: dict[str, list[dict]] = {}
        reviewed: Counter[str] = Counter()
        not_instruction_like = 0
        total = 0
        for act, change_type, instruction in instructions:
            total += 1
            by_parser_type[change_type or "unknown"] += 1
            ops = self.classify(instruction)
            for op_id in ops:
                by_operation[op_id] += 1
            if ops:
                combos["+".join(ops)] += 1
                continue
            if not self.instruction_like(instruction):
                not_instruction_like += 1
                continue
            form = normalize(instruction)
            if form in self._reviewed:
                reviewed[form] += 1
                continue
            unknown[form] += 1
            examples = unknown_examples.setdefault(form, [])
            if len(examples) < 5:
                examples.append({"act": act, "instruction": _SPACE_RE.sub(" ", instruction.strip())[:300]})
        return {
            "catalog_version": self.version,
            "instructions": total,
            "by_operation": dict(sorted(by_operation.items())),
            "by_parser_change_type": dict(sorted(by_parser_type.items())),
            "operation_combinations": dict(combos.most_common()),
            "not_instruction_like": not_instruction_like,
            "reviewed_non_instructions": sum(reviewed.values()),
            "unknown_forms": [
                {"form": form, "count": count, "examples": unknown_examples[form]}
                for form, count in sorted(unknown.items(), key=lambda item: (-item[1], item[0]))
            ],
        }


def normalize(text: str) -> str:
    """Collapse an instruction to its wording: references, numbers and quoted words become placeholders."""
    text = _SPACE_RE.sub(" ", (text or "").strip())
    text = _LEADING_MARKER_RE.sub("", text)
    text = _LAWREF_RE.sub("LAWREF", text)
    text = _DATE_RE.sub("DATE", text)
    text = _QUOTE_RE.sub("«…»", text)
    text = _SECTION_RE.sub("§N", text)
    text = _NUMBER_RE.sub("N", text)
    return text[:200]


def read_snapshot_instructions(database: str | Path) -> list[tuple[str, str, str]]:
    conn = sqlite3.connect(f"file:{Path(database)}?mode=ro", uri=True)
    try:
        return conn.execute(
            "SELECT act_refid, change_type, instruction FROM amendments ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify the instructions in a snapshot against the catalogue")
    parser.add_argument("--db", default="snapshot/amendments.db", help="amendments.db of a loader snapshot")
    parser.add_argument("--output", help="Write the JSON report here (default: stdout)")
    parser.add_argument("--catalog", help="Alternative catalogue file")
    parser.add_argument("--fail-on-unknown", action="store_true", help="Exit 1 when unknown forms are present")
    args = parser.parse_args(argv)
    catalog = InstructionCatalog(load_catalog(args.catalog) if args.catalog else None)
    result = catalog.report(read_snapshot_instructions(args.db))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    unknown = len(result["unknown_forms"])
    print(f"{result['instructions']} instructions, {unknown} unknown forms", file=__import__('sys').stderr)
    return 1 if (args.fail_on_unknown and unknown) else 0


if __name__ == "__main__":
    raise SystemExit(main())
