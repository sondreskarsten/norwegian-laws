"""Structured data models for parsed Norwegian law data.

These models define the snapshot format — the contract between lovdata-loader
and lovdata-publisher. The loader produces these; the publisher consumes them
(via JSON serialization, not direct import).
"""
from dataclasses import dataclass, field, asdict
import json
from typing import Literal


LEGACY_CONTENT_VERSION = "legacy-paragraphs-v1"
LEGACY_FORMATTER_VERSION = "law-markdown-v1"
ORDERED_CONTENT_VERSION = "ordered-paragraph-blocks-v1"
ORDERED_FORMATTER_VERSION = "law-markdown-ordered-html-v1"
CONTAINER_CONTENT_VERSION = "ordered-law-containers-v1"
CONTAINER_FORMATTER_VERSION = "law-markdown-ordered-containers-v1"
SOURCE_BODY_CONTENT_VERSION = "ordered-source-document-body-v1"
# The website still uses the existing convenience projection; faithful observed
# source-body publication is qualified separately by the independent consumer.
SOURCE_BODY_FORMATTER_VERSION = "law-markdown-convenience-with-source-body-v1"

# Insertion order is the legacy formatter traversal. References preserve these
# arrays as the single owners of content while describing a different order.
ROOT_CONTENT_FIELDS = {"paragraph": "top_level_paragraphs", "remainder": "remainders",
                       "section": "sections", "article": "top_level_articles"}
SECTION_CONTENT_FIELDS = {"preamble": "preamble", "article": "articles",
                          "section": "subsections", "footnote": "footnotes", "remainder": "remainders"}


@dataclass
class ContentRef:
    """One existing child at its original position in a law or section."""
    kind: Literal["paragraph", "remainder", "section", "article", "preamble", "footnote"]
    index: int


def content_order_if_needed(order: list[ContentRef], fields: dict[str, str]) -> list[ContentRef]:
    ranks = {kind: index for index, kind in enumerate(fields)}
    return order if any(ranks[a.kind] > ranks[b.kind] for a, b in zip(order, order[1:])) else []


def validate_content_order(data: dict, fields: dict[str, str]) -> list[dict]:
    """Every ordered child must reference an existing array element exactly once."""
    order = data.get("content_order", [])
    if not isinstance(order, list):
        raise ValueError("Invalid container content_order: expected a list")
    if not order:
        return order
    expected = set()
    for kind, field_name in fields.items():
        children = data.get(field_name, [])
        if not isinstance(children, list):
            raise ValueError(f"Invalid ordered container child array: {field_name}")
        expected.update((kind, index) for index in range(len(children)))
    seen = set()
    for reference in order:
        if (not isinstance(reference, dict) or set(reference) != {"kind", "index"}
                or not isinstance(reference["kind"], str) or reference["kind"] not in fields
                or type(reference["index"]) is not int or reference["index"] < 0):
            raise ValueError("Invalid container content_order reference")
        identity = (reference["kind"], reference["index"])
        if identity not in expected or identity in seen:
            raise ValueError("Container content_order has an invalid or duplicate child reference")
        seen.add(identity)
    if seen != expected:
        raise ValueError("Container content_order must reference every child exactly once")
    return order


def _content_order_from_dict(data: dict, fields: dict[str, str]) -> list[ContentRef]:
    return [ContentRef(**reference) for reference in validate_content_order(data, fields)]


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
class ParagraphBlock:
    """A text run or one list, in its observed position within a single ledd."""
    kind: str
    text: str = ""
    list_items: list[ListItem] = field(default_factory=list)
    list_style: str = ""


@dataclass
class Paragraph:
    """A legal paragraph (ledd) within an article."""
    text: str = ""
    list_items: list[ListItem] = field(default_factory=list)
    list_style: str = ""
    trailing_text: str = ""
    # Only populated when the legacy text/list/trailing shape loses ordering.
    # Ordered content is exclusive: legacy fields stay empty in that case.
    ordered_blocks: list[ParagraphBlock] = field(default_factory=list)


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
    # Empty/absent means legacy grouped traversal. Nonempty covers every child.
    content_order: list[ContentRef] = field(default_factory=list)


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
        ordered_blocks=[ParagraphBlock(
            kind=block["kind"], text=block.get("text", ""),
            list_items=[_listitem_from_dict(li) for li in block.get("list_items", [])],
            list_style=block.get("list_style", ""),
        ) for block in p.get("ordered_blocks", [])],
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
        content_order=_content_order_from_dict(s, SECTION_CONTENT_FIELDS),
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
    # References describe source traversal without duplicating owned content.
    content_order: list[ContentRef] = field(default_factory=list)
    source_body: dict | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.source_body is None:
            # Older receipt/model hashes must not acquire a new null field.
            data.pop("source_body")
        return data

    def to_json(self, indent: int = 1) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "LawData":
        if "source_body" in d:
            from .source_body import validate_source_body_model
            validate_source_body_model(d["source_body"], expected_refid=d["refid"])
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
            content_order=_content_order_from_dict(d, ROOT_CONTENT_FIELDS),
            source_body=d.get("source_body"),
        )


def uses_ordered_content(law: LawData) -> bool:
    """Whether any ledd needs the version-3 snapshot reader."""
    def paragraphs(rows):
        return any(p.ordered_blocks or any(paragraphs(item.paragraphs)
                                          for item in p.list_items) for p in rows)

    def articles(rows):
        return any(paragraphs(article.paragraphs) for article in rows)

    def sections(rows):
        return any(articles(section.articles) or sections(section.subsections) for section in rows)

    return bool(paragraphs(law.top_level_paragraphs)
                or articles(law.top_level_articles) or sections(law.sections))


def uses_ordered_containers(law: LawData) -> bool:
    def sections(rows):
        return any(section.content_order or sections(section.subsections) for section in rows)
    return bool(law.content_order or sections(law.sections))


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
    # Version 2 counts describe persisted unique identities, not parsed inputs.
    forskrift_count: int = 0
    forskrifter_archive: str = ""
    artifact_hashes: dict[str, str] = field(default_factory=dict)
    duplicate_policy: str = "last-occurrence-wins"
    duplicate_counts: dict[str, int] = field(default_factory=dict)
    # Version 3 permits explicit paragraph/container order contracts. Version 4
    # adds source evidence independently of the selected content contract.
    # Version 1/2 retain the original flat-paragraph Markdown contract.
    content_version: str = "legacy-paragraphs-v1"
    formatter_version: str = "law-markdown-v1"
    # Version 4 binds retained source bytes and all parsed amendment occurrences.
    evidence: dict = field(default_factory=dict)

    def to_json(self, indent: int = 1) -> str:
        data = asdict(self)
        if self.version < 4:
            data.pop("evidence")
        if self.version < 3:
            # Preserve the v2 shape for older Manifest(**data) readers, too.
            data.pop("content_version")
            data.pop("formatter_version")
        return json.dumps(data, ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "Manifest":
        return cls(**d)
