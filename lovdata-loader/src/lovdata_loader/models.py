"""Structured data models for parsed Norwegian law data.

These models define the snapshot format — the contract between lovdata-loader
and lovdata-publisher. The loader produces these; the publisher consumes them
(via JSON serialization, not direct import).
"""
from dataclasses import dataclass, field, asdict
import json


@dataclass
class ListItem:
    """A single list item inside a legal paragraph.

    marker is the rendered legal label as observed in the source
    (e.g. "1.", "a)", "A.", "I."); empty for an unlabelled bullet.
    value is the source ordinal. paragraphs is the item body, parsed
    with the same ledd grammar so nested lists and multi-paragraph
    items are represented losslessly.
    """
    marker: str = ""
    value: str = ""
    paragraphs: list["Paragraph"] = field(default_factory=list)


@dataclass
class Paragraph:
    """A legal paragraph (ledd) within an article."""
    text: str = ""
    list_items: list[ListItem] = field(default_factory=list)
    list_style: str = ""
    trailing_text: str = ""


@dataclass
class Article:
    """A legal article (§/paragraf) within a section or at the top level."""
    name: str             # e.g. "§ 1-1"
    header_text: str      # e.g. "§ 1-1. Lovens virkeområde"
    paragraphs: list[Paragraph] = field(default_factory=list)
    trailing_text: str = ""
    remainders: list[str] = field(default_factory=list)


@dataclass
class Section:
    """A section (kapittel/del/avsnitt) containing articles and subsections."""
    heading: str
    articles: list[Article] = field(default_factory=list)
    subsections: list["Section"] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    remainders: list[str] = field(default_factory=list)


def _listitem_from_dict(li: dict) -> ListItem:
    return ListItem(
        marker=li.get("marker", ""),
        value=li.get("value", ""),
        paragraphs=[_paragraph_from_dict(p) for p in li.get("paragraphs", [])],
    )


def _paragraph_from_dict(p: dict) -> Paragraph:
    return Paragraph(
        text=p.get("text", ""),
        list_items=[_listitem_from_dict(li) for li in p.get("list_items", [])],
        list_style=p.get("list_style", ""),
        trailing_text=p.get("trailing_text", ""),
    )


def _article_from_dict(a: dict) -> Article:
    return Article(
        name=a["name"],
        header_text=a["header_text"],
        paragraphs=[_paragraph_from_dict(p) for p in a.get("paragraphs", [])],
        trailing_text=a.get("trailing_text", ""),
        remainders=a.get("remainders", []),
    )


def _section_from_dict(s: dict) -> Section:
    return Section(
        heading=s["heading"],
        articles=[_article_from_dict(a) for a in s.get("articles", [])],
        subsections=[_section_from_dict(sub) for sub in s.get("subsections", [])],
        preamble=s.get("preamble", []),
        footnotes=s.get("footnotes", []),
        remainders=s.get("remainders", []),
    )


@dataclass
class LawData:
    """A fully parsed consolidated law."""
    refid: str
    title: str
    short_title: str
    ministry: str
    date_in_force: str
    last_amended: str
    last_amended_in_force: str
    legal_area: str
    sections: list[Section] = field(default_factory=list)
    top_level_articles: list[Article] = field(default_factory=list)
    top_level_paragraphs: list[Paragraph] = field(default_factory=list)
    remainders: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 1) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "LawData":
        return cls(
            refid=d["refid"],
            title=d["title"],
            short_title=d.get("short_title", ""),
            ministry=d.get("ministry", ""),
            date_in_force=d.get("date_in_force", ""),
            last_amended=d.get("last_amended", ""),
            last_amended_in_force=d.get("last_amended_in_force", ""),
            legal_area=d.get("legal_area", ""),
            sections=[_section_from_dict(s) for s in d.get("sections", [])],
            top_level_articles=[_article_from_dict(a) for a in d.get("top_level_articles", [])],
            top_level_paragraphs=[_paragraph_from_dict(p) for p in d.get("top_level_paragraphs", [])],
            remainders=d.get("remainders", []),
        )


@dataclass
class Amendment:
    """A single amendment instruction within an amendment act."""
    change_type: str      # change | repeal | add | move | unknown
    target: str           # e.g. lov/1999-07-02-64/§21
    instruction: str      # e.g. "§ 21 skal lyde:"
    new_text: str
    target_law: str = ""  # e.g. lov/1998-07-17-56


@dataclass
class AmendmentActData:
    """A parsed Lovtidend amendment act."""
    refid: str
    filename: str
    title: str
    short_title: str
    date_in_force: str
    date_published: str
    ministry: str
    changes_to: list[str]
    amendments: list[Amendment]
    misc_info: str
    journal_number: str


@dataclass
class Manifest:
    """Metadata about a snapshot."""
    version: int
    created_at: str
    loader_version: str
    gjeldende_archive: str
    lovtidend_archives: list[str]
    law_count: int
    amendment_act_count: int
    amendment_count: int

    def to_json(self, indent: int = 1) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "Manifest":
        return cls(**d)
