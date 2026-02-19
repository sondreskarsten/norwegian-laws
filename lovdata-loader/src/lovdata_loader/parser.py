"""Parse Lovdata XML into structured data models.

This module handles all XML/HTML parsing. It takes raw XML bytes and produces
clean Python dataclasses (LawData, AmendmentActData). No Markdown, no git,
no file I/O beyond reading tar archives.
"""
import os
import re
import tarfile
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from .models import (
    Amendment,
    AmendmentActData,
    Article,
    LawData,
    ListItem,
    Paragraph,
    Section,
)


# ─── Header Field Extraction ────────────────────────────────────────────────


def extract_header_field(header: Tag, css_class: str) -> str:
    """Extract text content from a <dd> element by CSS class."""
    dd = header.find("dd", class_=css_class)
    if not dd:
        return ""
    return dd.get_text(strip=True)


def extract_header_list(header: Tag, css_class: str) -> list[str]:
    """Extract a list of text values from a <dd> element."""
    dd = header.find("dd", class_=css_class)
    if not dd:
        return []
    items = dd.find_all("li")
    if items:
        return [li.get_text(strip=True) for li in items]
    return [dd.get_text(strip=True)]


def extract_last_changed_by(header: Tag) -> tuple[str, str]:
    """Extract the last-amended-by reference and its effective date.

    Returns (refid, in_force_date). Handles the <a> tag correctly to avoid
    concatenating the anchor text with sibling text.
    """
    for css_class in ["lastChangedBy", "sistEndret", "lastAmended"]:
        dd = header.find("dd", class_=css_class)
        if not dd:
            continue
        anchor = dd.find("a")
        if anchor:
            refid = anchor.get_text(strip=True)
            rest = ""
            for sibling in anchor.next_siblings:
                t = str(sibling).strip()
                if t:
                    rest += t
            in_force = ""
            m = re.search(r"fra\s*(\d{4}-\d{2}-\d{2})", rest)
            if m:
                in_force = m.group(1)
            return refid, in_force
        return dd.get_text(strip=True), ""
    return "", ""


# ─── Date Parsing ────────────────────────────────────────────────────────────

DEFERRED_PATTERNS = ["Kongen bestemmer", "Kongen fastsetter", "Kongen fastset"]


def parse_effective_date(date_str: str, fallback_published: str) -> tuple[str, bool]:
    """Parse an effective date, falling back to publication date if deferred.

    Returns (resolved_date, is_deferred).
    """
    if any(p in date_str for p in DEFERRED_PATTERNS):
        pub = parse_publication_date(fallback_published)
        return pub, True

    date_str = date_str.strip()
    for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d"), False
        except ValueError:
            continue

    if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10], False

    pub = parse_publication_date(fallback_published)
    return pub, True


def parse_publication_date(date_str: str) -> str:
    """Parse a publication date string into YYYY-MM-DD format."""
    date_str = date_str.strip()
    for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if m:
        return m.group(1)
    return "2000-01-01"


# ─── Consolidated Law Parser ────────────────────────────────────────────────


def _parse_law_metadata(soup: BeautifulSoup) -> dict:
    """Extract metadata fields from a law's XML header."""
    header = soup.find("header")
    if not header:
        return {}
    last_amended, last_amended_in_force = extract_last_changed_by(header)
    return {
        "refid": extract_header_field(header, "refid"),
        "title": extract_header_field(header, "title"),
        "short_title": extract_header_field(header, "titleShort"),
        "ministry": extract_header_field(header, "ministry"),
        "date_in_force": extract_header_field(header, "dateInForce"),
        "last_amended": last_amended,
        "last_amended_in_force": last_amended_in_force,
        "legal_area": extract_header_field(header, "legalArea"),
    }


def parse_article(article_tag: Tag) -> Article:
    """Parse an XML <article class='legalArticle'> into an Article dataclass."""
    name = article_tag.get("data-name", "")

    article_header = (
        article_tag.find(["h3", "h4", "h5", "span"], class_="legalArticleHeader")
        or article_tag.find("span", class_="futureLegalArticleHeader")
    )
    header_text = ""
    if article_header:
        value = article_header.find("span", class_="legalArticleValue")
        title_span = article_header.find("span", class_="legalArticleTitle")
        header_text = value.get_text(strip=True) if value else ""
        if title_span:
            header_text += f". {title_span.get_text(strip=True)}"

    paragraphs = []
    for ledd in article_tag.find_all(
        "article",
        class_=lambda c: c and ("legalP" in c or "numberedLegalP" in c) if c else False,
        recursive=False,
    ):
        text_parts = []
        for child in ledd.children:
            if isinstance(child, Tag) and child.name == "ul":
                # Flush accumulated text as a separate paragraph before the list
                if text_parts:
                    paragraphs.append(Paragraph(
                        text=" ".join(text_parts), list_items=[],
                    ))
                    text_parts = []
                items = []
                for li in child.find_all("li", recursive=False):
                    identifier = li.get("data-li-identifier", "-")
                    li_text = li.get_text(strip=True)
                    items.append(ListItem(identifier=identifier, text=li_text))
                if items:
                    paragraphs.append(Paragraph(text="", list_items=items))
            elif isinstance(child, Tag):
                text_parts.append(child.get_text(strip=True))
            else:
                t = str(child).strip()
                if t:
                    text_parts.append(t)
        if text_parts:
            paragraphs.append(Paragraph(
                text=" ".join(text_parts), list_items=[],
            ))

    return Article(name=name, header_text=header_text, paragraphs=paragraphs)


def parse_section(section_tag: Tag) -> Section:
    """Parse an XML <section> into a Section dataclass."""
    heading = section_tag.find(["h2", "h3", "h4"])
    heading_text = heading.get_text(strip=True) if heading else ""

    articles = []
    for child in section_tag.children:
        if not isinstance(child, Tag):
            continue
        if "legalArticle" in child.get("class", []):
            articles.append(parse_article(child))
        elif child.name == "article" and "legalP" in child.get("class", []):
            # Standalone paragraph not inside a legalArticle — wrap as an
            # Article with no name/header so the formatter emits plain text.
            text = child.get_text(strip=True)
            if text:
                articles.append(Article(
                    name="",
                    header_text="",
                    paragraphs=[Paragraph(text=text, list_items=[])],
                ))

    return Section(heading=heading_text, articles=articles)


def parse_law(content: bytes) -> LawData | None:
    """Parse a single law XML document into a LawData dataclass.

    Returns None if the document has no refid.
    """
    soup = BeautifulSoup(content, "html.parser")
    meta = _parse_law_metadata(soup)

    if not meta.get("refid"):
        return None

    body = soup.find("main", class_="documentBody") or soup.find("body")
    if not body:
        return LawData(**meta, sections=[], top_level_articles=[])

    sections = []
    for section in body.find_all("section", recursive=False):
        sections.append(parse_section(section))

    top_level_articles = []
    for article in body.find_all("article", class_="legalArticle", recursive=False):
        top_level_articles.append(parse_article(article))

    return LawData(
        **meta,
        sections=sections,
        top_level_articles=top_level_articles,
    )


def parse_consolidated_archive(archive_path: str) -> list[LawData]:
    """Parse all laws from a consolidated laws tar.bz2 archive.

    Returns a list of LawData objects. Does no file I/O beyond reading
    the archive.
    """
    laws = []
    with tarfile.open(archive_path, "r:bz2") as tar:
        members = [m for m in tar.getmembers() if m.name.endswith(".xml")]
        for i, member in enumerate(members):
            f = tar.extractfile(member)
            if not f:
                continue
            law = parse_law(f.read())
            if law:
                laws.append(law)
            if (i + 1) % 100 == 0:
                print(f"  Parsed {i + 1}/{len(members)} laws...")
    return laws


# ─── Lovtidend Amendment Parser ──────────────────────────────────────────────


def parse_amendment(change_el: Tag) -> Amendment:
    """Parse a single amendment element from Lovtidend XML."""
    change_type = "unknown"
    target = ""

    if change_el.get("data-change-part"):
        change_type = "change"
        target = change_el["data-change-part"]
    elif change_el.get("data-repeal-part"):
        change_type = "repeal"
        target = change_el["data-repeal-part"]
    elif change_el.get("data-add-new-part"):
        change_type = "add"
        target = change_el["data-add-new-part"]
    elif change_el.get("data-move-part"):
        change_type = "move"
        target = change_el["data-move-part"]

    instruction_el = change_el.find("article", class_="defaultP")
    instruction = instruction_el.get_text(strip=True) if instruction_el else ""

    new_text_parts = []
    for future in change_el.find_all(
        ["article", "span"],
        class_=lambda c: c and "future" in c.lower() if c else False,
    ):
        new_text_parts.append(future.get_text(strip=True))
    for ledd in change_el.find_all("article", class_="legalP"):
        if ledd.find_parent(class_=lambda c: c and "future" in c.lower() if c else False):
            continue
        if ledd.find_parent("article", class_="defaultP"):
            continue
        new_text_parts.append(ledd.get_text(strip=True))

    return Amendment(
        change_type=change_type,
        target=target,
        instruction=instruction,
        new_text="\n".join(new_text_parts),
    )


def parse_lovtidend_file(content: bytes, filename: str) -> AmendmentActData | None:
    """Parse a single Lovtidend XML document into an AmendmentActData."""
    soup = BeautifulSoup(content, "html.parser")
    header = soup.find("header")
    if not header:
        return None

    refid = extract_header_field(header, "refid")
    if not refid:
        return None

    title_text = extract_header_field(header, "title")
    if not title_text and soup.find("title"):
        title_text = soup.find("title").get_text(strip=True)

    amendments = []
    for change_el in soup.find_all("article", class_="change"):
        amendments.append(parse_amendment(change_el))

    return AmendmentActData(
        refid=refid,
        filename=filename,
        title=title_text,
        short_title=extract_header_field(header, "titleShort"),
        date_in_force=extract_header_field(header, "dateInForce"),
        date_published=extract_header_field(header, "dateOfPublication"),
        ministry=extract_header_field(header, "ministry"),
        changes_to=extract_header_list(header, "changesToDocuments"),
        amendments=amendments,
        misc_info=extract_header_field(header, "miscInformation"),
        journal_number=extract_header_field(header, "journalNumber"),
    )


def parse_lovtidend_archive(
    archive_path: str, prefix_filter: str = "nl-"
) -> list[AmendmentActData]:
    """Parse all amendment acts from a Lovtidend tar.bz2 archive."""
    acts = []
    with tarfile.open(archive_path, "r:bz2") as tar:
        members = [
            m
            for m in tar.getmembers()
            if m.name.endswith(".xml")
            and os.path.basename(m.name).startswith(prefix_filter)
        ]
        for member in members:
            f = tar.extractfile(member)
            if not f:
                continue
            act = parse_lovtidend_file(f.read(), os.path.basename(member.name))
            if act:
                acts.append(act)
    return acts
