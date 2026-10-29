"""Full-text search and definition finding over the law documents."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .catalog import Catalog, Entry
from .markdown import Document, Heading, enclosing_section_heading, parse_document
from .repo import DOC_DIRS, Repo

WORD = r"[\wæøåäöüé]"
NB = rf"(?<!{WORD})"
NA = rf"(?!{WORD})"


@dataclass
class Hit:
    path: str
    line: int
    text: str
    section: Heading | None = None


@dataclass
class DocHits:
    entry: Entry | None
    path: str
    hits: list[Hit] = field(default_factory=list)
    total: int = 0


def _git_prefilter_pattern(term: str) -> str:
    """ERE for git grep that matches the term bytewise regardless of locale."""
    out = []
    for ch in term:
        if ord(ch) < 128:
            out.append(re.escape(ch) if ch.isalnum() or ch in " -" else re.escape(ch))
        else:
            out.append(".{1,2}")
    return "".join(out)


def _paths_for(kind: str | None, entries: list[Entry] | None) -> list[str]:
    if entries:
        return sorted({e.path for e in entries})
    if kind == "lov":
        return ["lover"]
    if kind == "forskrift":
        return ["forskrifter"]
    return list(DOC_DIRS)


def git_grep_lines(repo: Repo, pattern: str, paths: list[str], fixed: bool = False) -> dict[str, list[tuple[int, str]]]:
    args = ["grep", "-n", "-i", "-I", "--no-color"]
    args.append("-F" if fixed else "-E")
    args += ["-e", pattern, "--", *paths]
    out = repo.git(*args, check=False)
    found: dict[str, list[tuple[int, str]]] = {}
    for raw in out.split("\n"):
        if not raw:
            continue
        try:
            path, line, text = raw.split(":", 2)
            found.setdefault(path, []).append((int(line), text))
        except ValueError:
            continue
    return found


class DocCache:
    """Parsed documents keyed by path, invalidated when HEAD moves."""

    def __init__(self, repo: Repo) -> None:
        self.repo = repo
        self.sha: str | None = None
        self.docs: dict[str, Document] = {}

    def get(self, path: str) -> Document:
        head = self.repo.head().sha
        if head != self.sha:
            self.docs.clear()
            self.sha = head
        doc = self.docs.get(path)
        if doc is None:
            doc = parse_document(self.repo.read(path))
            if len(self.docs) > 512:
                self.docs.clear()
            self.docs[path] = doc
        return doc


def search_text(
    repo: Repo,
    cache: DocCache,
    catalog: Catalog,
    query: str,
    *,
    kind: str | None = None,
    entries: list[Entry] | None = None,
    regex: bool = False,
    whole_word: bool = False,
    max_documents: int = 20,
    max_hits_per_document: int = 5,
) -> tuple[list[DocHits], int]:
    """Return per-document hits ordered by hit count, and the total hit count."""
    paths = _paths_for(kind, entries)
    if regex:
        py = re.compile(query, re.I)
        candidates = _python_scan(repo, paths, py)
    else:
        pat = re.escape(query.strip())
        if whole_word:
            pat = NB + pat + NA
        py = re.compile(pat, re.I)
        pre = git_grep_lines(repo, _git_prefilter_pattern(query.strip()), paths)
        candidates = {p: [(n, t) for n, t in lines if py.search(t)] for p, lines in pre.items()}
    candidates = {p: v for p, v in candidates.items() if v}
    ordered = sorted(candidates.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    total = sum(len(v) for v in candidates.values())
    result: list[DocHits] = []
    for path, lines in ordered[:max_documents]:
        doc = cache.get(path)
        dh = DocHits(entry=catalog.by_path.get(path), path=path, total=len(lines))
        for n, text in lines[:max_hits_per_document]:
            dh.hits.append(Hit(path, n, text.strip(), enclosing_section_heading(doc, n)))
        result.append(dh)
    return result, total


def _python_scan(repo: Repo, paths: list[str], py: re.Pattern) -> dict[str, list[tuple[int, str]]]:
    found: dict[str, list[tuple[int, str]]] = {}
    files: list[str] = []
    for p in paths:
        full = repo.path / p
        if full.is_dir():
            files.extend(str(f.relative_to(repo.path)) for f in sorted(full.glob("*.md")))
        elif full.is_file():
            files.append(p)
    for rel in files:
        text = (repo.path / rel).read_text(encoding="utf-8", errors="replace")
        if not py.search(text):
            continue
        for i, line in enumerate(text.split("\n"), start=1):
            if py.search(line):
                found.setdefault(rel, []).append((i, line))
    return found


# -- definitions -----------------------------------------------------------

SUFFIXES = ("ene", "ane", "ene", "ers", "er", "ar", "en", "et", "a", "e")


def stem(term: str) -> str:
    t = term.strip().casefold()
    for suf in SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)]
    return t


@dataclass
class DefinitionHit:
    score: int
    reason: str
    entry: Entry | None
    path: str
    section: Heading | None
    line: int
    text: str


def find_definitions(
    repo: Repo,
    cache: DocCache,
    catalog: Catalog,
    term: str,
    *,
    kind: str | None = None,
    entries: list[Entry] | None = None,
    limit: int = 10,
) -> tuple[list[DefinitionHit], int]:
    base = stem(term)
    word = rf"{NB}{re.escape(base)}{WORD}*"
    mention = re.compile(word, re.I)
    patterns = [
        (100, "definition phrase (med X menes/forstås)", re.compile(rf"{NB}med\s+(?:en\s+|et\s+|ei\s+)?{word}\s+(?:menes|forstås|forstaas)", re.I)),
        (90, "definition phrase (menes/forstås med X)", re.compile(rf"(?:menes|forstås)\s+(?:med\s+)?(?:en\s+|et\s+)?{word}", re.I)),
        (75, "definition phrase (X betyr / X: / X er i denne lov)", re.compile(rf"{word}\s*(?::|betyr|er i denne (?:lov|forskrift)|skal forstås som|omfatter i denne)", re.I)),
        (80, "definition list item", re.compile(rf"^\s*(?:[a-z]\.|\d+\.|-|\*)\s*{word}\s*(?::|,|\s+er\s+|\s+betyr\s+)", re.I)),
    ]
    paths = _paths_for(kind, entries)
    pre = git_grep_lines(repo, _git_prefilter_pattern(base), paths)
    hits: list[DefinitionHit] = []
    mentions_total = 0
    for path, lines in pre.items():
        lines = [(n, t) for n, t in lines if mention.search(t)]
        if not lines:
            continue
        mentions_total += len(lines)
        doc = cache.get(path)
        entry = catalog.by_path.get(path)
        best_in_doc: DefinitionHit | None = None
        for n, text in lines:
            sec = enclosing_section_heading(doc, n)
            in_def_section = bool(sec and re.search(r"definisjon|begrep|forklaring", sec.text, re.I))
            score = 0
            reason = ""
            stripped = text.strip()
            if stripped.startswith("#"):
                score, reason = 60, "section heading names the term"
                if re.search(r"definisjon", stripped, re.I):
                    score += 20
            else:
                for s, r, pat in patterns:
                    if pat.search(text):
                        score, reason = s, r
                        break
            if in_def_section and score < 100:
                score += 20
                reason = (reason + "; " if reason else "") + "inside a definitions section"
            if score == 0:
                continue
            hit = DefinitionHit(score, reason, entry, path, sec, n, stripped)
            hits.append(hit)
    hits.sort(key=lambda h: (-h.score, h.entry.kind != "lov" if h.entry else True, h.path, h.line))
    return hits[:limit], mentions_total
