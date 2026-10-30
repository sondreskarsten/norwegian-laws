"""Parsing of the repository's Markdown law documents."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
SECTION_RE = re.compile(r"§\s*(\d+(?:-\d+)?)\s*([a-z](?!\w))?")
CHAPTER_RE = re.compile(r"^(?:Kapittel|Kap\.?|Del)\s+([0-9IVXLC]+[A-Za-z]?)\b", re.I)


@dataclass
class Heading:
    level: int
    text: str
    line: int
    section: str | None = None
    chapter: str | None = None


@dataclass
class Section:
    heading: Heading
    start: int
    end: int
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass
class Document:
    text: str
    meta: dict
    lines: list[str]
    headings: list[Heading]

    @property
    def title(self) -> str:
        return str(self.meta.get("tittel") or "")

    @property
    def refid(self) -> str:
        return str(self.meta.get("refid") or "")


def normalize_section_key(spec: str) -> str:
    """Normalize '§ 4-7', '4-7', '§4-7', '§ 1-5 a' to '4-7' / '1-5a'."""
    s = spec.strip().replace("§", "").replace("\xa0", " ").strip()
    s = s.rstrip(".")
    m = re.match(r"^(\d+(?:-\d+)?)\s*([a-zA-Z])?$", s)
    if not m:
        return s.lower().replace(" ", "")
    return m.group(1) + (m.group(2).lower() if m.group(2) else "")


def parse_front_matter(text: str) -> tuple[dict, int]:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}, 0
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, m.group(0).count("\n")


def parse_document(text: str) -> Document:
    meta, _ = parse_front_matter(text)
    lines = text.split("\n")
    headings: list[Heading] = []
    in_fence = False
    for i, line in enumerate(lines, start=1):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2)
        h = Heading(level=level, text=title, line=i)
        sm = SECTION_RE.search(title)
        if sm:
            h.section = normalize_section_key(sm.group(1) + (sm.group(2) or ""))
        else:
            cm = CHAPTER_RE.match(title)
            if cm:
                h.chapter = cm.group(1).lower()
        headings.append(h)
    return Document(text=text, meta=meta, lines=lines, headings=headings)


def section_bounds(doc: Document, heading: Heading) -> tuple[int, int]:
    """1-based inclusive line range for the block under ``heading``."""
    end = len(doc.lines)
    for h in doc.headings:
        if h.line > heading.line and h.level <= heading.level:
            end = h.line - 1
            break
    while end > heading.line and not doc.lines[end - 1].strip():
        end -= 1
    return heading.line, end


def get_section(doc: Document, spec: str) -> Section | None:
    """Find a § or chapter by spec such as '§ 4-7', '4-7', 'kapittel 4', 'kap 4'."""
    spec_clean = spec.strip()
    cm = re.match(r"^(?:kapittel|kap\.?|chapter|del)\s*([0-9IVXLC]+[A-Za-z]?)$", spec_clean, re.I)
    if cm:
        want = cm.group(1).lower()
        for h in doc.headings:
            if h.chapter == want:
                start, end = section_bounds(doc, h)
                return Section(h, start, end, doc.lines[start - 1:end])
        return None
    key = normalize_section_key(spec_clean)
    for h in doc.headings:
        if h.section == key:
            start, end = section_bounds(doc, h)
            return Section(h, start, end, doc.lines[start - 1:end])
    return None


def enclosing_heading(doc: Document, line: int) -> Heading | None:
    """The nearest § heading (or any heading) at or above ``line``."""
    best: Heading | None = None
    for h in doc.headings:
        if h.line > line:
            break
        if h.section:
            best = h
        elif best is None or best.section is None:
            best = h
    return best


def enclosing_section_heading(doc: Document, line: int) -> Heading | None:
    best: Heading | None = None
    for h in doc.headings:
        if h.line > line:
            break
        if h.section:
            best = h
        elif h.level <= 3:
            best = None
    return best


def outline(doc: Document, max_level: int = 6) -> list[Heading]:
    return [h for h in doc.headings if h.level <= max_level]
