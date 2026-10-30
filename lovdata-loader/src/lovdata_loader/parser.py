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
    ParagraphBlock,
    Section,
    ContentRef,
    ROOT_CONTENT_FIELDS,
    SECTION_CONTENT_FIELDS,
    content_order_if_needed,
)


# ─── Header Field Extraction ────────────────────────────────────────────────


def _text(el: Tag) -> str:
    """Extract text preserving spaces around inline elements like <a> tags."""
    return re.sub(r'\s+', ' ', el.get_text(separator=" ")).strip()


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

    Years > 2050 are treated as parse errors. Source data has known typos —
    e.g. forskrift/2016-12-21-1854 has '2107-01-01' as its in-force date
    (likely meant 2017). Without the guard, these propagate to the JSONL
    manifest and break downstream sorting / time-series analysis.
    """
    if any(p in date_str for p in DEFERRED_PATTERNS):
        pub = parse_publication_date(fallback_published)
        return pub, True

    date_str = date_str.strip()
    for fmt in ["%Y-%m-%d", "%d.%m.%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.year > 2050:
                # Clearly a typo (e.g. 2107 for 2017). Fall back to published.
                pub = parse_publication_date(fallback_published)
                return pub, True
            return dt.strftime("%Y-%m-%d"), False
        except ValueError:
            continue

    if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
        # Extra-loose match; check year sanity here too.
        year = int(date_str[:4])
        if year > 2050:
            pub = parse_publication_date(fallback_published)
            return pub, True
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
    if not last_amended_in_force:
        last_amended_in_force = extract_header_field(header, "lastChangeInForce")
    return {
        "refid": extract_header_field(header, "refid"),
        "title": extract_header_field(header, "title"),
        "short_title": extract_header_field(header, "titleShort"),
        "ministry": extract_header_field(header, "ministry"),
        "date_in_force": extract_header_field(header, "dateInForce"),
        "last_amended": last_amended,
        "last_amended_in_force": last_amended_in_force,
        "legal_area": "\n".join(extract_header_list(header, "legalArea")),
    }


def _is_ledd(tag: Tag) -> bool:
    classes = tag.get("class", [])
    return tag.name == "article" and any(
        c in classes for c in ("legalP", "numberedLegalP", "centeredP")
    )


def _is_header(tag: Tag) -> bool:
    return tag.name in ("h1", "h2", "h3", "h4", "h5", "h6", "div", "span") and any(
        c in tag.get("class", [])
        for c in ("legalArticleHeader", "futureLegalArticleHeader")
    )


def _int_to_alpha(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


_ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"),
          (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"),
          (5, "v"), (4, "iv"), (1, "i")]


def _int_to_roman(n: int) -> str:
    s = ""
    for v, sym in _ROMAN:
        while n >= v:
            s += sym
            n -= v
    return s


def _compose_marker(value: str, style: str) -> str:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return ""
    if style == "1":
        return f"{n}."
    if style == "A":
        return f"{_int_to_alpha(n).upper()}."
    if style == "a":
        return f"{_int_to_alpha(n)})"
    if style == "I":
        return f"{_int_to_roman(n).upper()}."
    if style == "i":
        return f"{_int_to_roman(n)})"
    return ""


def _resolve_marker(li: Tag, style: str = "") -> str:
    name = li.get("data-name", "")
    if name:
        return name.strip()
    composed = _compose_marker(li.get("value", ""), style)
    if composed:
        return composed
    legacy = li.get("data-li-identifier", "")
    if legacy and legacy != "-":
        return legacy.strip()
    return ""


def _list_item_paragraphs(li: Tag) -> list[Paragraph]:
    holder = li.find("article", class_="listArticle", recursive=False)
    if holder is None:
        return [_parse_ledd(li)]
    paras = []
    for child in holder.find_all(recursive=False):
        if child.name == "article":
            paras.append(_parse_ledd(child))
        elif child.name == "span" and "miscHeadline" in (child.get("class") or []):
            paras.append(Paragraph(text=_text(child)))
    if not paras:
        paras = [_parse_ledd(holder)]
    return paras


def _parse_list(list_tag: Tag) -> list[ListItem]:
    style = list_tag.get("type", "") or ""
    items = []
    for li in list_tag.find_all("li", recursive=False):
        items.append(ListItem(
            marker=_resolve_marker(li, style),
            value=(li.get("value", "") or "").strip(),
            paragraphs=_list_item_paragraphs(li),
        ))
    return items


def _parse_ledd(ledd: Tag) -> Paragraph:
    text_parts = []
    trailing_parts = []
    items = []
    list_style = ""
    blocks = []
    text_run = []
    has_interleaving = False
    seen_list = False

    def flush_text():
        text = " ".join(text_run).strip()
        if text:
            blocks.append(ParagraphBlock(kind="text", text=text))
        text_run.clear()

    for child in ledd.children:
        if isinstance(child, Tag) and child.name in ("ul", "ol"):
            parsed_items = _parse_list(child)
            if parsed_items:
                if seen_list and any(text_run):
                    has_interleaving = True
                flush_text()
                blocks.append(ParagraphBlock(kind="list", list_items=parsed_items,
                                             list_style=child.get("type", "") or ""))
                seen_list = True
            if not items:
                list_style = child.get("type", "") or ""
            items.extend(parsed_items)
        elif isinstance(child, Tag):
            text = _text(child)
            (trailing_parts if items else text_parts).append(text)
            if text:
                text_run.append(text)
        else:
            t = str(child).strip()
            if t:
                (trailing_parts if items else text_parts).append(t)
                text_run.append(t)
    if has_interleaving:
        flush_text()
        return Paragraph(ordered_blocks=blocks)
    return Paragraph(
        text=" ".join(text_parts).strip(),
        list_items=items,
        list_style=list_style,
        trailing_text=" ".join(trailing_parts).strip(),
    )


def parse_article(article_tag: Tag) -> Article:
    """Parse an XML <article class='legalArticle'> into an Article dataclass."""
    name = article_tag.get("data-name", "")

    article_header = (
        article_tag.find(
            ["h2", "h3", "h4", "h5", "h6", "div", "span"],
            class_="legalArticleHeader",
        )
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
    trailing_parts = []
    for child in article_tag.children:
        if not isinstance(child, Tag):
            continue
        if _is_ledd(child):
            paragraphs.append(_parse_ledd(child))
        elif child.name == "p":
            paragraphs.append(Paragraph(text=_text(child)))
        elif _is_header(child):
            pass
        else:
            text = _text(child)
            if text:
                trailing_parts.append(text)

    return Article(
        name=name,
        header_text=header_text,
        paragraphs=paragraphs,
        trailing_text="\n".join(trailing_parts),
    )


def _is_article(tag: Tag) -> bool:
    classes = tag.get("class", [])
    return tag.name == "article" and any(
        c in classes for c in ("legalArticle", "futureLegalArticle")
    )


def parse_section(section_tag: Tag) -> Section:
    """Parse an XML <section> into a Section dataclass."""
    heading = section_tag.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    heading_text = heading.get_text(strip=True) if heading else ""

    articles = []
    subsections = []
    preamble = []
    footnotes = []
    order = []
    for child in section_tag.children:
        if not isinstance(child, Tag):
            continue
        if _is_article(child):
            order.append(ContentRef("article", len(articles)))
            articles.append(parse_article(child))
        elif child.name == "section":
            order.append(ContentRef("section", len(subsections)))
            subsections.append(parse_section(child))
        elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            pass
        elif child.name == "footer":
            text = _text(child)
            if text:
                order.append(ContentRef("footnote", len(footnotes)))
                footnotes.append(text)
        else:
            text = _text(child)
            if text:
                order.append(ContentRef("preamble", len(preamble)))
                preamble.append(text)

    return Section(
        heading=heading_text,
        articles=articles,
        subsections=subsections,
        preamble=preamble,
        footnotes=footnotes,
        content_order=content_order_if_needed(order, SECTION_CONTENT_FIELDS),
    )


def parse_law(content: bytes | str, *, capture_source_body: bool = False) -> LawData | None:
    """Parse a single law XML document into a LawData dataclass.

    Returns None if the legacy document has no refid. Source-body capture is an
    explicit v5 opt-in and fails on unsupported/malformed source; it never falls
    back to the convenience projection or silently drops a failed body.
    """
    source_body = None
    if capture_source_body:
        from .source_body import capture_source_body as capture_document_body
        source_body = capture_document_body(content)
    # Lovdata's retained XML is UTF-8. Detector choices vary by environment and
    # can turn valid Norwegian text into mojibake. Keep the original bytes for
    # capture identity, while rejecting invalid input instead of guessing.
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    soup = BeautifulSoup(text, "html.parser")
    meta = _parse_law_metadata(soup)

    if source_body is not None and source_body["context"]["refid"] != meta.get("refid"):
        raise ValueError("Source-body refid differs from convenience metadata")

    if not meta.get("refid"):
        return None

    body = soup.find("main", class_="documentBody") or soup.find("body")
    if not body:
        return LawData(**meta, sections=[], top_level_articles=[])

    sections = []
    top_level_articles = []
    top_level_paragraphs = []
    remainders = []
    order = []
    for child in body.children:
        if not isinstance(child, Tag):
            t = str(child).strip()
            if t:
                order.append(ContentRef("remainder", len(remainders)))
                remainders.append(t)
            continue
        if child.name == "section":
            order.append(ContentRef("section", len(sections)))
            sections.append(parse_section(child))
        elif _is_article(child):
            order.append(ContentRef("article", len(top_level_articles)))
            top_level_articles.append(parse_article(child))
        elif _is_ledd(child):
            order.append(ContentRef("paragraph", len(top_level_paragraphs)))
            top_level_paragraphs.append(_parse_ledd(child))
        elif child.name == "p":
            order.append(ContentRef("paragraph", len(top_level_paragraphs)))
            top_level_paragraphs.append(Paragraph(text=_text(child)))
        elif child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            continue
        else:
            text = _text(child)
            if text:
                order.append(ContentRef("remainder", len(remainders)))
                remainders.append(text)

    return LawData(
        **meta,
        sections=sections,
        top_level_articles=top_level_articles,
        top_level_paragraphs=top_level_paragraphs,
        remainders=remainders,
        content_order=content_order_if_needed(order, ROOT_CONTENT_FIELDS),
        source_body=source_body,
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

_INSTRUCTION_RE = re.compile(
    r"(§\s*[\d]+[\w\s-]*?)"
    r"(.*?)"
    r"(skal lyde|oppheves|endres til|flyttes til|blir ny)",
    re.DOTALL,
)

_NEW_SECTION_RE = re.compile(r"Ny(?:tt?)?\s+§\s*[\d]", re.I)
# 'skal § 3 lyde', 'skal § 12-5 første punktum lyde' (verb before the target)
_EMBEDDED_INSTRUCTION_RE = re.compile(r"\bskal\s+(§\s*\d+[\w-]*(?:\s+[a-z](?!\w))?)[^.:]*?\blyde\b")
_EMBEDDED_PREAMBLE_RE = re.compile(r"^\s*I\s+(?:lov|forskrift)\b")
_RENUMBER_RE = re.compile(r"Nåværende\s+", re.I)
_KAPITTEL_RE = re.compile(r"(?:Kapittel|kapittel|Kap\.)\s+\d+", re.I)
_HEADING_RE = re.compile(r"[Oo]verskriften?\s+(?:til\s+)?§", re.I)


def _is_old_instruction(text: str) -> bool:
    return bool(
        _INSTRUCTION_RE.search(text)
        or _NEW_SECTION_RE.search(text)
        or _RENUMBER_RE.match(text)
        or _KAPITTEL_RE.search(text)
        or _HEADING_RE.search(text)
    )


def _classify_old_instruction(text: str) -> str:
    if "oppheves" in text:
        return "repeal"
    if _NEW_SECTION_RE.search(text):
        return "add"
    if _RENUMBER_RE.match(text):
        return "renumber"
    if "skal lyde" in text or "endres til" in text or _EMBEDDED_INSTRUCTION_RE.search(text):
        return "change"
    if _HEADING_RE.search(text):
        return "change"
    return "unknown"


def _extract_target(text: str) -> str:
    # A spaced letter suffix must be a whole token, not the first letter
    # of instructions such as "skal lyde" or "første ledd".
    m = re.search(r"(§\s*[\d]+[\w-]*(?:\s+[a-z](?!\w))?)", text)
    if m:
        return m.group(1).strip()
    m = _KAPITTEL_RE.search(text)
    if m:
        return m.group(0).strip()
    return ""


_MONTHS = {
    "januar": "01", "februar": "02", "mars": "03", "april": "04",
    "mai": "05", "juni": "06", "juli": "07", "august": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12",
}


def _extract_law_refid_from_preamble(text: str) -> str:
    # Matches e.g. 'lov 17. juni 2005 nr. 90', 'forskrift 21. desember 1979
    # nr. 77' and also capitalized variants at start of a sentence
    # ('Lov 20. mai 2005 nr. 28 om straff endres slik').
    m = re.search(
        r"(lov|forskrift|Lov|Forskrift)\s+(?:av\s+)?(\d+)\.\s*(\w+)\s+(\d{4})\s+nr\.\s*(\d+)", text
    )
    if not m:
        return ""
    kind, day, month_name, year, nr = m.groups()
    month = _MONTHS.get(month_name.lower(), "")
    if not month:
        return ""
    return f"{kind.lower()}/{year}-{month}-{day.zfill(2)}-{nr}"


def _is_law_preamble(text: str) -> bool:
    """A 'law preamble' paragraph announces which law the following amendment
    instructions apply to, e.g. 'I lov 17. juni 2005 nr. 90 om mekling og
    rettergang i sivile tvister (tvisteloven) gjøres følgende endringer:'.

    In flat-format multi-law endringslover (no <section> wrappers), these
    preambles also appear in numbered list form, e.g. '1. I lov 20. juli 1893
    nr. 2 om Stranding og Vrag gjøres følgende endringer:'. Both forms must
    be recognised so the parser can re-anchor target_law mid-stream as it
    walks through the children of a flat body.

    Several phrasings are used in the corpus, with 'gjøres følgende
    endringer' being most common but not universal:
      - 'I lov ... gjøres følgende endringer:' (most common)
      - 'Lov ... endres slik:' (e.g. lov/2009-06-19-74)
      - 'I lov ... gjøres disse endringene:' (less common)
      - 'Lova vert oppheva' (repeal)
    Heuristic: contains one of these phrases AND an extractable refid.
    The phrase check is necessary to distinguish from incidental references
    to other laws inside amendment instructions (e.g. '§ 14 skal vise til
    lov 17. juli 1925 nr. 11 om Svalbard').
    """
    if not text:
        return False
    phrases = (
        "gjøres følgende endringer",
        "gjøres disse endringene",
        "gjeres følgjande endringar",
        "vert gjort følgjande endringar",
        "endres slik",
        "endrast slik",
        "Lova vert oppheva",
    )
    if not any(p in text for p in phrases):
        return False
    return bool(_extract_law_refid_from_preamble(text))


_PART_MARKER_RE = re.compile(r"^(?:[IVXLC]+|[A-Z]|\d+)\.?$")


def _is_title_only(text: str) -> bool:
    """A chapter/part title with no instruction verb, e.g. 'Kapittel 7. Tilsyn'."""
    return bool(
        _KAPITTEL_RE.search(text)
        and not _INSTRUCTION_RE.search(text)
        and not _NEW_SECTION_RE.search(text)
        and not _RENUMBER_RE.match(text)
        and not _HEADING_RE.search(text)
        and not re.search(r"skal lyde|oppheves|endres til|flyttes til|blir ny|tilføyes|settes inn", text)
    )


def _is_part_marker(text: str) -> bool:
    return bool(_PART_MARKER_RE.match(text.strip()))


_BODY_TEXT_CLASSES = ("legalP", "numberedLegalP", "listArticle", "centeredP")


def _has_ancestor_class(el: Tag, predicate) -> bool:
    return el.find_parent(class_=predicate) is not None


def _is_future_class(c) -> bool:
    return bool(c) and "future" in c.lower()


def _future_element_text(el: Tag) -> str:
    """Text of a top-level future element, one line per paragraph.

    A futureLegalArticle holds a header span and paragraph articles; joining
    them with newlines keeps the heading separate from the first ledd instead
    of running them together.
    """
    if el.name == "span":
        return el.get_text(strip=True)
    parts = []
    for sub in el.children:
        if not isinstance(sub, Tag):
            continue
        # Collapse whitespace instead of stripping every text node so the
        # header keeps '§ 3-1. Plikt ...' rather than '§ 3-1.Plikt ...'.
        sub_text = " ".join(sub.get_text().split())
        if sub_text:
            parts.append(sub_text)
    if not parts:
        return el.get_text(strip=True)
    return "\n".join(parts)


def _unparsed_body_text(body: Tag, title: str) -> str:
    """Flatten an act body whose instructions matched no known pattern."""
    lines = []
    for raw in body.get_text("\n", strip=True).split("\n"):
        line = raw.strip()
        if not line or _is_part_marker(line) or line == title.strip():
            continue
        lines.append(line)
    return "\n".join(lines)


def _parse_old_format_section(section: Tag, target_law: str = "") -> list[Amendment]:
    children = [c for c in section.children if isinstance(c, Tag)]
    amendments = []

    if not target_law:
        for child in children:
            if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                continue
            target_law = _extract_law_refid_from_preamble(
                child.get_text(strip=True)
            )
            break

    current_instruction = None
    current_target = ""
    current_type = "unknown"
    text_parts = []

    def flush() -> None:
        if current_instruction is not None:
            amendments.append(Amendment(
                change_type=current_type,
                target=current_target,
                instruction=current_instruction,
                new_text="\n".join(text_parts),
                target_law=target_law,
            ))

    for child in children:
        classes = child.get("class", [])
        text = child.get_text(strip=True)

        if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            # A heading that follows an instruction is replacement text, e.g.
            # 'Avsnittets tittel skal lyde:' or 'Nytt kapittel 1 A skal lyde:'
            # followed by the new title as a heading. Part markers such as
            # 'I', 'II' and the act title itself are structure, not wording.
            if current_instruction is not None and text and not _is_part_marker(text):
                text_parts.append(text)
            continue

        # A law-preamble paragraph mid-stream re-anchors target_law for all
        # subsequent amendments. The current amendment (if any) is flushed
        # against the OLD target_law before switching. Preambles may use
        # `defaultP` (numbered list items, e.g. '3. I lov ... gjøres ...') or
        # `legalP` (the act's first/anchor preamble, e.g. 'I lov ... gjøres
        # følgende endringer:' at the very top of the body, before the
        # numbered law list begins).
        if any(c in classes for c in ("defaultP", "legalP")) and _is_law_preamble(text):
            new_law = _extract_law_refid_from_preamble(text)
            if new_law:
                flush()
                current_instruction = None
                current_target = ""
                current_type = "unknown"
                text_parts = []
                target_law = new_law
                continue

        is_instr = "defaultP" in classes and _is_old_instruction(text)

        # Multi-law acts from the early 2000s fold the preamble into the
        # instruction, often in a legalP: 'I lov 29. april 1977 nr. 34 om ...
        # skal § 3 lyde:'. Such a sentence is an instruction and re-anchors
        # the target law at the same time.
        if (any(c in classes for c in ("legalP", "defaultP"))
                and _EMBEDDED_PREAMBLE_RE.match(text)
                and (_INSTRUCTION_RE.search(text) or _EMBEDDED_INSTRUCTION_RE.search(text))):
            embedded_law = _extract_law_refid_from_preamble(text)
            if embedded_law:
                flush()
                current_instruction = None
                text_parts = []
                target_law = embedded_law
                is_instr = True

        # 'Nytt kapittel 1 A skal lyde:' / 'Overskriften til kapittel 7 skal
        # lyde:' are followed by the new title in its own paragraph, e.g.
        # '<i>Kapittel 1 A Den sentrale domstoladministrasjonen</i>'. That
        # title mentions a chapter and used to be taken for a new instruction,
        # which flushed the pending replacement with no wording.
        if (is_instr and current_instruction is not None and not text_parts
                and current_instruction.rstrip().endswith("lyde:")
                and _is_title_only(text)):
            is_instr = False

        if is_instr:
            flush()

            current_target = _extract_target(text)
            current_type = _classify_old_instruction(text)

            if "skal lyde:" in text:
                parts = text.split("skal lyde:", 1)
                current_instruction = parts[0].strip() + " skal lyde:"
                tail = parts[1].strip()
                text_parts = [tail] if tail else []
            else:
                current_instruction = text
                text_parts = []

        elif current_instruction is not None:
            if "futureLegalArticle" in classes:
                for sub in child.children:
                    if not isinstance(sub, Tag):
                        continue
                    sub_cls = sub.get("class", [])
                    sub_text = sub.get_text(strip=True)
                    if any(c in sub_cls for c in (
                        "futureLegalArticleHeader", "legalArticleHeader",
                    )):
                        text_parts.append(sub_text)
                    elif any(c in sub_cls for c in (
                        "legalP", "numberedLegalP", "listArticle",
                    )):
                        text_parts.append(sub_text)
                    elif sub_text:
                        text_parts.append(sub_text)
            elif any(c in classes for c in (
                "legalP", "numberedLegalP",
                "listArticle", "centeredP",
            )):
                text_parts.append(text)
            elif "defaultP" in classes and text:
                text_parts.append(text)

    flush()

    return amendments


def _parse_old_format_amendments(
    body: Tag, header_fallback_law: str = ""
) -> list[Amendment]:
    """Parse amendments from an act body. `header_fallback_law` is used as
    the initial target_law when no preamble is found in the section — set
    only when the act's <changesToDocuments> contains exactly one refid,
    so we can confidently anchor amendments to it. Caught by data review
    2026-05-20: single-law endringslover like lov/2008-12-12-99 have their
    target only in the act title, not repeated as a preamble in each
    <section> body.
    """
    amendments = []
    sections = body.find_all("section", recursive=False)
    if sections:
        for section in sections:
            amendments.extend(
                _parse_old_format_section(section, target_law=header_fallback_law)
            )
    else:
        amendments.extend(
            _parse_old_format_section(body, target_law=header_fallback_law)
        )
    return amendments


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
    for future in change_el.find_all(["article", "span"], class_=_is_future_class):
        # Nested future spans (e.g. futureLegalArticleHeader inside a
        # futureLegalArticle) are already covered by their top-level parent.
        if _has_ancestor_class(future, _is_future_class):
            continue
        text = _future_element_text(future)
        if text:
            new_text_parts.append(text)
    for ledd in change_el.find_all("article", class_=_BODY_TEXT_CLASSES):
        if _has_ancestor_class(ledd, _is_future_class):
            continue
        if ledd.find_parent("article", class_="defaultP"):
            continue
        # listArticle wraps legalP: keep the outermost block only.
        if ledd.find_parent("article", class_=_BODY_TEXT_CLASSES) is not None:
            continue
        text = ledd.get_text(strip=True)
        if text:
            new_text_parts.append(text)

    target_law = ""
    if target:
        m = re.match(r"((?:lov|forskrift)/[\d-]+)(?=/|$)", target)
        if m:
            target_law = m.group(1)

    return Amendment(
        change_type=change_type,
        target=target,
        instruction=instruction,
        new_text="\n".join(new_text_parts),
        target_law=target_law,
    )


def parse_lovtidend_file(content: bytes | str, filename: str) -> AmendmentActData | None:
    """Parse a single Lovtidend XML document into an AmendmentActData."""
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    soup = BeautifulSoup(text, "html.parser")
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

    changes_to = extract_header_list(header, "changesToDocuments")
    if not amendments:
        body = soup.find("main", class_="documentBody") or soup.find("body")
        if body:
            # If the act amends exactly one law/forskrift, use that as the
            # fallback target_law when no in-body preamble is found.
            # Multi-law endringslover always have explicit preambles per
            # section, so the fallback would only confuse them.
            header_fallback_law = (
                changes_to[0] if len(changes_to) == 1 else ""
            )
            amendments = _parse_old_format_amendments(body, header_fallback_law)
            if not amendments and header_fallback_law:
                # The act changes exactly one document but none of its
                # instructions matched a known form (code lists, renamed
                # annex entries, prose). Keep the whole body as one
                # unresolved record so the change is visible in the target
                # document's history instead of disappearing.
                body_text = _unparsed_body_text(body, title_text)
                if body_text:
                    first_line = body_text.split("\n", 1)[0]
                    amendments = [Amendment(
                        change_type="unknown",
                        target="",
                        instruction=first_line,
                        new_text=body_text,
                        target_law=header_fallback_law,
                    )]

    return AmendmentActData(
        refid=refid,
        filename=filename,
        title=title_text,
        short_title=extract_header_field(header, "titleShort"),
        date_in_force=extract_header_field(header, "dateInForce"),
        date_published=extract_header_field(header, "dateOfPublication"),
        ministry=extract_header_field(header, "ministry"),
        changes_to=changes_to,
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
