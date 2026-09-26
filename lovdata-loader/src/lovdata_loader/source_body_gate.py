"""Independent stdlib-only source-body gate and bounded safe renderer.

May be packaged/vendored unchanged by a consumer: no loader imports. The raw
reader uses Expat callbacks, independently of the producer's ElementTree walk.
The bounded grammar rejects unsupported source roles instead of approximating
them. The declared list grammar retains explicit source markers.
Numbered paragraphs retain labels already present in the source text. Images,
formulas, row spans and
unhandled source roles remain explicit rejections.
"""
from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import json
import re
from collections import Counter
from urllib.parse import urljoin, urlsplit
from xml.parsers import expat

CONTRACT = "ordered-source-document-body-v1"
GATE_VERSION = "observed-body-source-emphasis-tables-v5"
MAX_BYTES = 16 * 1024 * 1024
MAX_MODEL_BYTES = 32 * 1024 * 1024
MAX_NODES = 250_000
MAX_DEPTH = 128
MAX_ATTRIBUTES = 64
_HASH = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_BODY_CSS = """main.documentBody{overflow-wrap:anywhere}main.documentBody article.legalP{margin:.65em 0}main.documentBody article.changesToParent{border-left:3px solid #73899b;padding:.6em 1em;background:#f1f4f6;font-size:.9em}main.documentBody footer.footnotes{border-top:1px solid #8a9aaa;margin-top:1.4em}main.documentBody article.footnote{font-size:.9em;margin:.6em 0}main.documentBody a[data-source-body-derived=backref]{margin-left:.5em}main.documentBody [data-source-body-derived=table-scroll]{max-width:100%;overflow-x:auto;margin:1em 0}main.documentBody [data-source-body-derived=table-scroll]:focus-visible{outline:2px solid #27649b;outline-offset:2px}main.documentBody table{border-collapse:collapse;min-width:100%;width:auto}main.documentBody th,main.documentBody td{border:1px solid #91a1aa;padding:.3em .5em;overflow-wrap:normal;word-break:normal}main.documentBody [data-text-align=left]{text-align:left}main.documentBody [data-text-align=center]{text-align:center}main.documentBody [data-text-align=right]{text-align:right}main.documentBody [data-vertical-align=top]{vertical-align:top}main.documentBody [data-vertical-align=middle]{vertical-align:middle}main.documentBody [data-vertical-align=bottom]{vertical-align:bottom}"""
_TABLE_SCROLL_ATTRIBUTES = {"aria-label": "Tabell (rull vannrett ved behov)",
                            "data-source-body-derived": "table-scroll",
                            "role": "region", "tabindex": "0"}
_LIST_CSS = """main.documentBody .defaultList{padding-inline-start:2.2em;margin:.65em 0}main.documentBody .defaultList .defaultList{padding-inline-start:1.8em}main.documentBody ul.defaultList{list-style-type:disc}main.documentBody .defaultList>li[data-name]::marker{content:attr(data-name) " ";font-variant-numeric:tabular-nums}main.documentBody .defaultList>li>article.listArticle>article.legalP:first-child{margin-top:0}main.documentBody .defaultList>li{padding-inline-start:.25em;margin:.4em 0}"""


_PARAGRAPH_FORMS = {("article", "defaultP"), ("article", "numberedLegalP"), ("article", "centeredP"), ("p", "leddfortsettelse")}
_PARAGRAPH_CSS = """main.documentBody article.defaultP,main.documentBody article.numberedLegalP,main.documentBody article.centeredP,main.documentBody p.leddfortsettelse{margin:.65em 0}main.documentBody article.defaultP[data-text-size=small]{font-size:.9em}main.documentBody article.centeredP{text-align:center}"""


def stylesheet_for_body(root: dict) -> str:
    """Retain earlier stylesheet bytes unless newly supported forms occur."""
    forms = {_form(n) for n, _, _ in _walk(root)}
    return (SOURCE_BODY_CSS + (_LIST_CSS if forms & _LISTS else "")
            + (_PARAGRAPH_CSS if forms & _PARAGRAPH_FORMS else ""))

# Exact form/attribute pairs. No arbitrary class/data-* passthrough.
_FORMS = {
    ("main", "documentBody"): {"class", "id", "data-lovdata-URL"},
    ("section", "section"): {"class", "id", "data-name", "data-lovdata-URL"},
    ("article", "legalArticle"): {"class", "id", "data-name", "data-lovdata-URL"},
    ("article", "legalP"): {"class", "id"},
    ("article", "defaultP"): {"class", "id", "data-text-size"},
    ("article", "numberedLegalP"): {"class", "id", "data-numerator"},
    ("article", "centeredP"): {"class", "id", "data-text-align"},
    ("p", "leddfortsettelse"): {"class", "id"},
    ("ol", "defaultList"): {"class", "type"},
    ("ul", "defaultList"): {"class"},
    ("li", ""): {"data-name", "data-li-identifier", "value"},
    ("article", "listArticle"): {"class", "id"},
    ("article", "changesToParent"): {"class"},
    ("article", "footnote"): {"class", "data-name", "data-unique-footnote-counter"},
    ("footer", "footnotes"): {"class"},
    ("span", "legalArticleValue"): {"class", "data-legalArea"},
    ("span", "legalArticleTitle"): {"class"},
    ("span", "footnoteLabel"): {"class"},
    ("sup", "footnotereference"): {"class", "data-footnotereferencevalue", "data-unique-footnote-counter"},
    ("h1", ""): set(), ("h2", ""): set(), ("h3", ""): set(),
    ("h2", "legalArticleHeader"): {"class"},
    ("h3", "legalArticleHeader"): {"class"},
    ("h4", "legalArticleHeader"): {"class"},
    ("a", ""): {"href"}, ("i", ""): set(), ("strong", ""): set(), ("br", ""): set(),
    ("table", ""): set(), ("thead", ""): set(), ("tbody", ""): set(),
    ("tr", ""): set(),
    ("th", ""): {"colspan", "data-text-align", "data-vertical-align"},
    ("td", ""): {"colspan", "data-text-align", "data-vertical-align"},
}
_INLINE = {("a", ""), ("i", ""), ("strong", ""), ("br", ""), ("sup", "footnotereference")}
_HEADINGS = {("h1", ""), ("h2", ""), ("h3", ""),
             ("h2", "legalArticleHeader"), ("h3", "legalArticleHeader"), ("h4", "legalArticleHeader")}
for _heading in _HEADINGS:
    _FORMS[_heading] |= {"data-text-align"}
_LISTS = {("ol", "defaultList"), ("ul", "defaultList")}
_CHILDREN = {
    ("main", "documentBody"): _HEADINGS | _LISTS | {("section", "section"), ("article", "legalArticle"), ("article", "legalP"), ("article", "changesToParent"), ("footer", "footnotes")},
    ("section", "section"): _HEADINGS | _LISTS | {("section", "section"), ("article", "legalArticle"), ("article", "legalP"), ("article", "changesToParent"), ("footer", "footnotes")},
    ("article", "legalArticle"): _HEADINGS | _LISTS | {("article", "legalP"), ("article", "changesToParent"), ("footer", "footnotes")},
    ("article", "legalP"): _INLINE | _LISTS | {("table", "")},
    ("ol", "defaultList"): {("li", "")},
    ("ul", "defaultList"): {("li", "")},
    ("li", ""): {("article", "listArticle")},
    ("article", "listArticle"): {("article", "legalP")},
    ("article", "changesToParent"): _INLINE,
    ("article", "footnote"): _INLINE | {("span", "footnoteLabel")},
    ("footer", "footnotes"): {("article", "footnote")},
    ("table", ""): {("thead", ""), ("tbody", "")},
    ("thead", ""): {("tr", "")}, ("tbody", ""): {("tr", "")},
    ("tr", ""): {("td", ""), ("th", "")},
    ("td", ""): _INLINE, ("th", ""): _INLINE,
    ("a", ""): {("i", ""), ("strong", ""), ("br", "")},
    ("i", ""): {("a", ""), ("strong", ""), ("br", "")},
    ("strong", ""): _INLINE,
    ("span", "legalArticleTitle"): _INLINE,
    **{heading: _INLINE | {("span", "legalArticleValue"), ("span", "legalArticleTitle")} for heading in _HEADINGS},
}
for _parent in (("main", "documentBody"), ("section", "section"), ("article", "legalArticle")):
    _CHILDREN[_parent] |= {("article", "defaultP"), ("article", "numberedLegalP"), ("article", "centeredP")}
_CHILDREN[("article", "listArticle")] |= {("article", "defaultP")}
_CHILDREN[("article", "defaultP")] = _INLINE | _LISTS | {("table", ""), ("footer", "footnotes")}
_CHILDREN[("article", "numberedLegalP")] = _INLINE | _LISTS | {("article", "legalP"), ("table", ""), ("footer", "footnotes")}
_CHILDREN[("article", "centeredP")] = _INLINE
_CHILDREN[("p", "leddfortsettelse")] = _INLINE
for _parent in (("article", "legalP"), ("article", "numberedLegalP"), ("article", "defaultP")):
    _CHILDREN[_parent] |= {("p", "leddfortsettelse")}

_ELEMENT_ONLY = {("main", "documentBody"), ("section", "section"),
                 ("article", "legalArticle"), ("footer", "footnotes"),
                 ("table", ""), ("thead", ""), ("tbody", ""), ("tr", ""),
                 ("ol", "defaultList"), ("ul", "defaultList"),
                 ("li", ""), ("article", "listArticle")}


class BodyRejected(ValueError):
    def __init__(self, code: str, path: str, detail: str):
        self.code, self.path, self.detail = code, path, detail
        super().__init__(f"{code} at {path}: {detail}")


def _require(ok: bool, code: str, path: str, detail: str) -> None:
    if not ok:
        raise BodyRejected(code, path, detail)


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _walk(root: dict):
    """Iterative schema validation prevents oversized/deep model recursion."""
    pending = [(root, "/main[1]", 1, None)]
    count = characters = 0
    while pending:
        node, path, depth, parent = pending.pop()
        count += 1
        _require(count <= MAX_NODES and depth <= MAX_DEPTH, "resource_limit", path, "Model node/depth limit")
        _require(type(node) is dict and set(node) == {"tag", "attributes", "children"}, "invalid_model", path, "Exact node shape required")
        tag, attrs, children = node["tag"], node["attributes"], node["children"]
        _require(type(tag) is str and type(attrs) is dict and type(children) is list,
                 "invalid_model", path, "Invalid tag, attributes or mixed content")
        _require(len(attrs) <= MAX_ATTRIBUTES and all(type(k) is str and type(v) is str for k, v in attrs.items()), "invalid_model", path, "String attributes required")
        characters += len(tag) + sum(len(k) + len(v) for k, v in attrs.items())
        previous_text = False
        counters: Counter = Counter()
        next_nodes = []
        for child in children:
            if type(child) is str:
                _require(bool(child) and not previous_text, "invalid_model", path, "Empty/adjacent text runs are noncanonical")
                characters += len(child)
                previous_text = True
            else:
                _require(type(child) is dict and type(child.get("tag")) is str, "invalid_model", path, "Invalid child node")
                counters[child["tag"]] += 1
                next_nodes.append((child, f"{path}/{child['tag']}[{counters[child['tag']]}]", depth + 1, node))
                previous_text = False
        _require(characters <= MAX_MODEL_BYTES, "resource_limit", path, "Model text/attribute limit")
        yield node, path, parent
        pending.extend(reversed(next_nodes))


def _events(node: dict, lower_attributes: bool = False):
    attrs = node["attributes"]
    yield ("start", node["tag"], tuple(sorted((k.lower() if lower_attributes else k, v) for k, v in attrs.items())))
    for child in node["children"]:
        if type(child) is str:
            yield ("text", child)
        else:
            yield from _events(child, lower_attributes)
    yield ("end", node["tag"])


def _compare_raw(raw: bytes, root_model: dict, context: dict) -> int:
    """Compare Expat source events as they arrive, with one buffered text run."""
    parser = expat.ParserCreate()
    parser.buffer_text = True
    stack: list[str] = []
    counters: list[Counter] = []
    paths: list[str] = []
    expected = iter(_events(root_model))
    text_parts: list[str] = []
    active_depth = 0
    body_count = node_count = event_count = 0
    source_context = {"html_lang": None, "html_attributes": None, "head_attributes": None,
                      "body_attributes": None, "source_base": None, "refid": None}
    bases = heads = bodies = refs = 0
    ref_depth = 0
    ref_text: list[str] = []

    def event(value):
        nonlocal event_count
        event_count += 1
        _require(next(expected, None) == value, "source_model_mismatch", paths[-1] if paths else "/", "Raw source event differs from model")

    def flush():
        if text_parts:
            event(("text", "".join(text_parts)))
            text_parts.clear()

    def start(tag, attrs):
        nonlocal active_depth, body_count, node_count, bases, heads, bodies, refs, ref_depth
        node_count += 1
        _require(node_count <= MAX_NODES and len(stack) < MAX_DEPTH and len(attrs) <= MAX_ATTRIBUTES,
                 "resource_limit", "/", "Raw XML limits")
        _require(":" not in tag and not any(":" in key or key == "xmlns" for key in attrs),
                 "unsupported_node_kind", "/", "Namespaces are not supported")
        if active_depth:
            flush()
        ordinal = 1
        if counters:
            counters[-1][tag] += 1
            ordinal = counters[-1][tag]
        path = (paths[-1] if paths else "") + f"/{tag}[{ordinal}]"
        stack.append(tag)
        counters.append(Counter())
        paths.append(path)
        if len(stack) == 1:
            _require(tag == "html", "unsupported_context", path, "Expected html document")
            source_context["html_lang"] = attrs.get("lang")
            source_context["html_attributes"] = dict(attrs)
        if stack == ["html", "head"]:
            source_context["head_attributes"] = dict(attrs)
            heads += 1
        if stack == ["html", "body"]:
            source_context["body_attributes"] = dict(attrs)
            bodies += 1
        if stack == ["html", "head", "base"]:
            bases += 1
            _require(set(attrs) == {"href"}, "unsupported_context", path, "Explicit base href required")
            source_context["source_base"] = attrs["href"]
        if tag == "dd" and attrs.get("class") == "refid" and stack[:3] == ["html", "body", "header"]:
            refs += 1
            ref_depth = len(stack)
        if tag == "main" and attrs.get("class") == "documentBody":
            body_count += 1
            _require(stack == ["html", "body", "main"] and not active_depth,
                     "body_cardinality", path, "Document body must be a direct child")
            active_depth = len(stack)
        if active_depth:
            event(("start", tag, tuple(sorted(attrs.items()))))

    def end(tag):
        nonlocal active_depth, ref_depth
        if active_depth:
            flush()
            event(("end", tag))
            if len(stack) == active_depth:
                active_depth = 0
        if ref_depth and len(stack) == ref_depth:
            source_context["refid"] = "".join(ref_text).strip()
            ref_depth = 0
        stack.pop()
        counters.pop()
        paths.pop()

    def text(value):
        if active_depth:
            text_parts.append(value)
        if ref_depth:
            ref_text.append(value)

    def unsupported(*args):
        raise BodyRejected("unsupported_node_kind", paths[-1] if paths else "/", "Unsupported XML lexical construct")

    def doctype(name, system, public, internal):
        _require(name == "html" and system is None and public is None and not internal,
                 "unsupported_node_kind", "/", "Only inert HTML doctype is supported")

    def declaration(version, encoding, standalone):
        _require(encoding is None or encoding.lower() in {"utf-8", "utf8"},
                 "unsupported_encoding", "/", "Only UTF-8 is supported")

    parser.StartElementHandler, parser.EndElementHandler = start, end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = doctype
    parser.XmlDeclHandler = declaration
    parser.EntityDeclHandler = unsupported
    parser.ExternalEntityRefHandler = unsupported
    parser.StartCdataSectionHandler = unsupported
    parser.ProcessingInstructionHandler = unsupported
    parser.CommentHandler = unsupported
    try:
        parser.Parse(raw, True)
    except expat.ExpatError as exc:
        raise BodyRejected("malformed_source", "/", str(exc)) from exc
    _require(body_count == 1 and heads == bodies == bases == refs == 1,
             "body_cardinality", "/", "Exactly one body and source context required")
    _require(next(expected, None) is None, "source_model_mismatch", "/", "Model contains extra events")
    _require(source_context == context, "source_context_mismatch", "/", "Raw context differs from model")
    return event_count


def _form(node: dict):
    return node["tag"], node["attributes"].get("class", "")


def _plain(node: dict) -> str:
    return "".join(c for c in node["children"] if type(c) is str)


def _target(href: str, base: str, path: str) -> str:
    _require(bool(href) and not href.startswith("#"), "unsupported_link_target", path, "Local fragment mapping is not in this grammar")
    _require(not any(ord(c) <= 32 or ord(c) == 127 or c == "\\" for c in href),
             "unsupported_link_target", path, "Control, whitespace or backslash in link")
    try:
        resolved = urljoin(base, href)
        parts = urlsplit(resolved)
        valid = parts.scheme in {"https", "http"} and bool(parts.hostname) and parts.username is None and parts.password is None
        _ = parts.port
    except ValueError:
        valid = False
        resolved = ""
    _require(valid, "unsupported_link_target", path, "Only absolute HTTP(S) link targets are supported")
    return resolved


def _table(node: dict, path: str) -> None:
    groups = [c for c in node["children"] if type(c) is dict]
    names = [c["tag"] for c in groups]
    _require(names in (["tbody"], ["thead", "tbody"]), "invalid_table_topology", path, "Explicit tbody and optional preceding thead required")
    width = None
    for group in groups:
        rows = [c for c in group["children"] if type(c) is dict]
        _require(bool(rows), "invalid_table_topology", path, "Empty row group")
        for row in rows:
            cells = [c for c in row["children"] if type(c) is dict]
            _require(bool(cells), "invalid_table_topology", path, "Empty table row")
            cell_width = sum(int(c["attributes"].get("colspan", "1")) for c in cells)
            if width is None:
                width = cell_width
            _require(cell_width == width and width <= 1024, "invalid_table_topology", path, "Inconsistent or oversized column grid")


def _list(node: dict, path: str) -> None:
    """Admit only source shapes demonstrated by the retained list fixtures.

    data-name is a literal source label, not an inferred ordinal. The renderer
    uses that exact label, while retaining the independently declared type and
    item value. No counter punctuation or implied start is added to the source.
    Explicit start/reversed/style attributes remain rejected until evidenced.
    """
    tag, attrs = node["tag"], node["attributes"]
    items = [c for c in node["children"] if type(c) is dict]
    _require(bool(items) and all(_form(c) == ("li", "") for c in items),
             "unsupported_list_topology", path, "Nonempty direct li children required")
    if tag == "ol":
        _require(attrs.get("type") in {"1", "a", "A", "i", "I"},
                 "unsupported_list_marker", path, "Observed ordered-list type required")
    for item in items:
        a = item["attributes"]
        children = [c for c in item["children"] if type(c) is dict]
        _require(len(children) == 1 and _form(children[0]) == ("article", "listArticle"),
                 "unsupported_list_topology", path, "Exactly one source listArticle per item required")
        _require(bool(children[0]["children"]), "unsupported_list_topology", path,
                 "Empty listArticle is outside this observed subset")
        if tag == "ol":
            _require(set(a) == {"data-name", "value"}
                     and bool(re.fullmatch(r"[1-9][0-9]{0,5}", a.get("value", "")))
                     and bool(re.fullmatch(r"(?:[0-9]{1,6}|[A-Za-z]{1,12})[.)]?", a.get("data-name", ""))),
                     "unsupported_list_marker", path,
                     "Ordered item requires exact bounded source label and positive declared value")
        else:
            _require(not a or a == {"data-name": "-", "data-li-identifier": "-"},
                     "unsupported_list_marker", path,
                     "Unordered subset supports unlabeled disc items or matching explicit hyphen fields")


def _grammar(root: dict, context: dict):
    _require(not set(context["html_attributes"]) - {"lang"} and not context["head_attributes"]
             and not context["body_attributes"], "unsupported_context", "/", "Captured context attributes are outside the render grammar")
    _require(_form(root) == ("main", "documentBody"), "unsupported_form", "/main[1]", "Root must be main.documentBody")
    _require(context["source_base"] == "https://lovdata.no/", "unsupported_context", "/", "Initial grammar requires the observed Lovdata base")
    language = context["html_lang"]
    _require(language is None or language == "" or bool(re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", language)),
             "unsupported_context", "/", "Unsupported document language declaration")
    # Some observed main elements omit this redundant source URL. The accepted
    # catalog/header/member identity remains mandatory in verify_source_body.
    if "data-lovdata-URL" in root["attributes"]:
        location = root["attributes"]["data-lovdata-URL"]
        _require(location.split("/", 1)[0] in {"NL", "SF", "DEL", "LTI", "INS"}
                 and location.partition("/")[2] == context["refid"],
                 "source_context_mismatch", "/main[1]", "Body source identity differs from header refid")
    ids = set()
    notes = {}
    references: Counter = Counter()
    tables = []
    lists = []
    counts: Counter = Counter()
    for node, path, parent in _walk(root):
        form, attrs = _form(node), node["attributes"]
        counts[form[0]] += 1
        _require(form in _FORMS, "unsupported_form", path, repr(form))
        _require(not set(attrs) - _FORMS[form], "unsupported_attribute", path, repr(sorted(set(attrs) - _FORMS[form])))
        _require(len({key.lower() for key in attrs}) == len(attrs), "unsupported_attribute", path, "HTML attribute-name collision")
        if parent is not None:
            _require(form in _CHILDREN.get(_form(parent), set()), "unsupported_nesting", path, "Child does not have a declared browser-safe parent")
            # Cross-nested links are invalid HTML even through italic wrappers.
        if form in _ELEMENT_ONLY:
            _require(not _plain(node).strip(), "unsupported_nesting", path, "Text outside declared block children")
        if form == ("br", ""):
            _require(not node["children"], "unsupported_nesting", path, "br cannot own content")
        if "data-text-size" in attrs:
            _require(attrs["data-text-size"] == "small", "unsupported_attribute_value", path, "Unknown paragraph text size")
        if "data-legalArea" in attrs:
            # Preserve source classification metadata verbatim, including
            # multiple space-separated codes. It is not a legal-time claim.
            classification = attrs["data-legalArea"]
            _require(0 < len(classification) <= 256 and all(
                re.fullmatch(r"[0-9]{2}[a-z]?(?:\.[0-9]{2}){0,5}", code)
                for code in classification.split(" ")),
                     "unsupported_attribute_value", path, "Unsupported source classification identifier")
        if form == ("article", "centeredP"):
            _require(attrs.get("data-text-align", "center") == "center", "unsupported_attribute_value", path, "Conflicting centered paragraph alignment")
        if form == ("article", "numberedLegalP"):
            number = attrs.get("data-numerator", "")
            _require(bool(re.fullmatch(r"[0-9]{1,9}", number)), "unsupported_paragraph_label", path, "Bounded source paragraph number required")
            # The source already contains its label. Never synthesize a CSS
            # counter or silently accept a conflicting or absent visible label.
            first = node["children"][0] if node["children"] and type(node["children"][0]) is str else ""
            _require(bool(re.match(r"(?:" + number + r"[.)]|\(" + number + r"\))(?=\s|$)", first.lstrip())),
                     "unsupported_paragraph_label", path, "Visible paragraph label differs from its source number")
        if "id" in attrs:
            identity = attrs["id"]
            _require(bool(identity) and not any(c.isspace() for c in identity) and identity not in ids,
                     "duplicate_id", path, "Missing, whitespace-containing or duplicate ID")
            ids.add(identity)
        if form == ("a", ""):
            _require("href" in attrs, "unsupported_attribute", path, "Link target required")
            _target(attrs["href"], context["source_base"], path)
            _require(not any(n is not node and (n["tag"] == "a" or _form(n) == ("sup", "footnotereference"))
                             for n, _, _ in _walk(node)),
                     "unsupported_nesting", path, "Nested source or generated footnote anchors are invalid HTML")
        if "colspan" in attrs:
            _require(bool(re.fullmatch(r"[1-9][0-9]{0,3}", attrs["colspan"])) and int(attrs["colspan"]) <= 1000,
                     "invalid_table_topology", path, "Positive bounded colspan required")
        if "data-text-align" in attrs:
            _require(attrs["data-text-align"] in {"left", "right", "center"}, "unsupported_attribute_value", path, "Unknown text alignment")
        if "data-vertical-align" in attrs:
            _require(attrs["data-vertical-align"] in {"top", "middle", "bottom"}, "unsupported_attribute_value", path, "Unknown vertical alignment")
        if form == ("table", ""):
            tables.append((node, path))
        if form in _LISTS:
            lists.append((node, path))
        if form in {("article", "footnote"), ("sup", "footnotereference")}:
            key = attrs.get("data-unique-footnote-counter", "")
            _require(bool(re.fullmatch(r"[1-9][0-9]{0,8}", key)), "ambiguous_footnote_target", path, "Positive bounded unique counter required")
            if form[0] == "article":
                labels = [c for c in node["children"] if type(c) is dict and _form(c) == ("span", "footnoteLabel")]
                _require(key not in notes and len(labels) == 1 and attrs.get("data-name") == _plain(labels[0]),
                         "ambiguous_footnote_target", path, "Unique counter and matching source label required")
                notes[key] = {"id": "source-body-note-" + key, "label": attrs["data-name"]}
            else:
                _require(bool(attrs.get("data-footnotereferencevalue")) and _plain(node) == attrs["data-footnotereferencevalue"],
                         "ambiguous_footnote_target", path, "Visible reference must match its source label")
                references[key] += 1
    _require(not set(references) - set(notes), "missing_footnote_target", "/main[1]", "Unmatched source footnote counter")
    for node, path, _ in _walk(root):
        if _form(node) == ("sup", "footnotereference"):
            a = node["attributes"]
            _require(notes[a["data-unique-footnote-counter"]]["label"] == a["data-footnotereferencevalue"],
                     "ambiguous_footnote_target", path, "Reference/target source labels differ")
    generated = {n["id"] for n in notes.values()} | {f"source-body-ref-{key}-{i}" for key, count in references.items() for i in range(1, count + 1)}
    _require(not generated & ids, "generated_id_collision", "/main[1]", "Source IDs collide with derived note navigation")
    for node, path in tables:
        _table(node, path)
    for node, path in lists:
        _list(node, path)
    return notes, references, dict(counts)


def _render(root: dict, context: dict, notes: dict, references: Counter) -> str:
    seen: Counter = Counter()

    def visit(node):
        if type(node) is str:
            return html.escape(node)
        tag, attrs = node["tag"], dict(node["attributes"])
        body = "".join(visit(c) for c in node["children"])
        if tag == "main" and context["html_lang"] is not None:
            attrs["lang"] = context["html_lang"]
        if tag == "a":
            attrs["data-source-body-href"] = attrs["href"]
            attrs["href"] = _target(attrs["href"], context["source_base"], "/")
        if attrs.get("class") == "footnotereference":
            key = attrs["data-unique-footnote-counter"]
            seen[key] += 1
            body = (f'<a data-source-body-derived="note-link" href="#{notes[key]["id"]}" '
                    f'id="source-body-ref-{key}-{seen[key]}" role="doc-noteref">{body}</a>')
        if attrs.get("class") == "footnote":
            key = attrs["data-unique-footnote-counter"]
            attrs["id"] = notes[key]["id"]
            for i in range(1, references[key] + 1):
                body += (f'<a aria-label="Back to footnote reference {i}" '
                         f'data-source-body-derived="backref" href="#source-body-ref-{key}-{i}">↩</a>')
        encoded = "".join(f' {key}="{html.escape(value, quote=True)}"' for key, value in sorted(attrs.items()))
        rendered = f"<{tag}{encoded}>" + ("" if tag == "br" else body + f"</{tag}>")
        if tag == "table":
            scroll_attrs = "".join(f' {key}="{html.escape(value, quote=True)}"'
                                   for key, value in sorted(_TABLE_SCROLL_ATTRIBUTES.items()))
            return f"<div{scroll_attrs}>{rendered}</div>"
        return rendered
    return visit(root)


class _RenderedTree(HTMLParser):
    """Strict fragment readback, with no implicit HTML error recovery."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.roots = []
        self.stack = []
        self.count = 0

    def handle_starttag(self, tag, attrs):
        self.count += 1
        _require(self.count <= MAX_NODES * 3 and len(self.stack) < MAX_DEPTH + 2, "resource_limit", "/render", "Rendered limits exceeded")
        _require(len(attrs) == len(dict(attrs)) and all(v is not None for _, v in attrs), "rendered_reverse_check_mismatch", "/render", "Duplicate/bare rendered attributes")
        node = {"tag": tag, "attributes": dict(attrs), "children": []}
        (self.stack[-1]["children"] if self.stack else self.roots).append(node)
        if tag != "br":
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        raise BodyRejected("rendered_reverse_check_mismatch", "/render", "Unexpected self-closing syntax")

    def handle_endtag(self, tag):
        _require(bool(self.stack) and self.stack[-1]["tag"] == tag, "rendered_reverse_check_mismatch", "/render", "Mismatched rendered nesting")
        self.stack.pop()

    def handle_data(self, data):
        _require(bool(self.stack), "rendered_reverse_check_mismatch", "/render", "Text outside body fragment")
        children = self.stack[-1]["children"]
        if children and type(children[-1]) is str:
            children[-1] += data
        elif data:
            children.append(data)

    def handle_comment(self, data):
        raise BodyRejected("rendered_reverse_check_mismatch", "/render", "Unexpected comment")

    def handle_decl(self, decl):
        raise BodyRejected("rendered_reverse_check_mismatch", "/render", "Unexpected declaration")

    def handle_pi(self, data):
        raise BodyRejected("rendered_reverse_check_mismatch", "/render", "Unexpected processing instruction")


def verify_rendered_body(fragment: str, model: dict, *, stylesheet: str) -> None:
    """Reject any unaccounted rendering change, including derived navigation.

    The model itself must already have passed the raw-source comparison. This
    function is public for a consumer's post-write artifact readback.
    """
    _validate_model(model)
    _require(stylesheet == stylesheet_for_body(model["root"]), "rendered_reverse_check_mismatch", "/render/style", "The declared stylesheet must be retained exactly")
    notes, references, counts = _grammar(model["root"], model["context"])
    _require(type(fragment) is str and len(fragment.encode("utf-8")) <= MAX_MODEL_BYTES * 2,
             "resource_limit", "/render", "Rendered artifact size/type")
    parser = _RenderedTree()
    parser.feed(fragment)
    parser.close()
    _require(not parser.stack and len(parser.roots) == 1, "rendered_reverse_check_mismatch", "/render", "Exactly one complete body fragment required")
    refs_seen: Counter = Counter()
    backs_seen: Counter = Counter()
    tables_seen = 0

    def reverse(node):
        nonlocal tables_seen
        tag, attrs = node["tag"], dict(node["attributes"])
        children = []
        if tag == "main" and model["context"]["html_lang"] is not None:
            _require(attrs.pop("lang", None) == model["context"]["html_lang"],
                     "rendered_reverse_check_mismatch", "/render", "Inherited source language changed")
        if tag == "a" and "data-source-body-href" in attrs:
            original = attrs.pop("data-source-body-href")
            _require(attrs.get("href") == _target(original, model["context"]["source_base"], "/render"), "rendered_reverse_check_mismatch", "/render", "Rewritten link target differs")
            attrs["href"] = original
        if attrs.get("class") == "footnote":
            key = attrs.get("data-unique-footnote-counter")
            _require(key in notes and attrs.pop("id", None) == notes[key]["id"], "rendered_reverse_check_mismatch", "/render", "Wrong derived note ID")
        for child in node["children"]:
            if type(child) is str:
                children.append(child)
                continue
            ca = child["attributes"]
            kind = ca.get("data-source-body-derived")
            if kind == "table-scroll":
                _require(tag == "article" and attrs.get("class") in {"legalP", "defaultP", "numberedLegalP"}
                         and child["tag"] == "div" and ca == _TABLE_SCROLL_ATTRIBUTES
                         and len(child["children"]) == 1
                         and type(child["children"][0]) is dict
                         and child["children"][0]["tag"] == "table",
                         "rendered_reverse_check_mismatch", "/render", "Incorrect table scroll region")
                tables_seen += 1
                children.append(reverse(child["children"][0]))
            elif kind == "note-link":
                key = attrs.get("data-unique-footnote-counter")
                refs_seen[key] += 1
                expected = {"data-source-body-derived": "note-link", "href": "#" + notes.get(key, {}).get("id", ""), "id": f"source-body-ref-{key}-{refs_seen[key]}", "role": "doc-noteref"}
                _require(tag == "sup" and attrs.get("class") == "footnotereference" and len(node["children"]) == 1 and child["tag"] == "a" and ca == expected and all(type(c) is str for c in child["children"]), "rendered_reverse_check_mismatch", "/render", "Incorrect note navigation")
                children.extend(child["children"])
            elif kind == "backref":
                key = attrs.get("data-unique-footnote-counter")
                backs_seen[key] += 1
                i = backs_seen[key]
                expected = {"aria-label": f"Back to footnote reference {i}", "data-source-body-derived": "backref", "href": f"#source-body-ref-{key}-{i}"}
                _require(tag == "article" and attrs.get("class") == "footnote" and child["tag"] == "a" and ca == expected and child["children"] == ["↩"], "rendered_reverse_check_mismatch", "/render", "Incorrect note backlink")
            else:
                _require(kind is None, "rendered_reverse_check_mismatch", "/render", "Unrecognized derived content")
                children.append(reverse(child))
        return {"tag": tag, "attributes": attrs, "children": children}

    restored = reverse(parser.roots[0])
    _require(refs_seen == references and backs_seen == references, "rendered_reverse_check_mismatch", "/render", "Missing or extra navigation")
    _require(tables_seen == counts.get("table", 0), "rendered_reverse_check_mismatch", "/render", "Missing or extra table scroll region")
    _require(list(_events(restored)) == list(_events(model["root"], True)),
             "rendered_reverse_check_mismatch", "/render", "Source-bearing content/order/attributes changed")


def _validate_model(model: dict) -> None:
    keys = {"contract", "member_sha256", "context", "body_sha256", "semantic_sha256", "root"}
    _require(type(model) is dict and set(model) == keys and model["contract"] == CONTRACT,
             "invalid_model", "/", "Unknown source-body envelope")
    context = model["context"]
    _require(type(context) is dict and set(context) == {"html_lang", "html_attributes", "head_attributes", "body_attributes", "source_base", "refid"}
             and (context["html_lang"] is None or type(context["html_lang"]) is str)
             and type(context["source_base"]) is str and type(context["refid"]) is str,
             "invalid_model", "/", "Invalid source context")
    for name in ("html_attributes", "head_attributes", "body_attributes"):
        _require(type(context[name]) is dict and len(context[name]) <= MAX_ATTRIBUTES
                 and all(type(k) is str and type(v) is str for k, v in context[name].items()),
                 "invalid_model", "/", "Invalid context attribute map")
    _require(context["html_lang"] == context["html_attributes"].get("lang"),
             "invalid_model", "/", "Inconsistent inherited language")
    for _ in _walk(model["root"]):
        pass
    try:
        encoded = _canonical(model)
        _require(len(encoded) <= MAX_MODEL_BYTES, "resource_limit", "/", "Serialized model exceeds limit")
        _require(_digest(model["root"]) == model["body_sha256"]
                 and _digest([CONTRACT, context, model["root"]]) == model["semantic_sha256"],
                 "model_binding_mismatch", "/", "Tree/context digest differs")
    except (UnicodeError, TypeError, RecursionError) as exc:
        raise BodyRejected("invalid_model", "/", "Noncanonical model encoding") from exc


def verify_source_body(raw: bytes, model: dict, *, expected_member_sha256: str,
                       expected_refid: str, source_occurrence_id: str) -> dict:
    """Prove capture fidelity independently, without admitting render grammar.

    Expected identities must come from the independently accepted source catalog.
    Unsupported render forms remain valid captured evidence if every raw event
    matches. A mismatch raises BodyRejected; no error code implies acceptance.
    """
    _require(type(raw) is bytes and len(raw) <= MAX_BYTES, "resource_limit", "/", "Raw input type/size")
    _require(type(expected_member_sha256) is str and bool(_HASH.fullmatch(expected_member_sha256))
             and type(source_occurrence_id) is str and bool(_HASH.fullmatch(source_occurrence_id))
             and type(expected_refid) is str and bool(expected_refid), "source_binding_mismatch", "/", "Catalog identity required")
    _require(hashlib.sha256(raw).hexdigest() == expected_member_sha256, "source_binding_mismatch", "/", "Raw member digest differs")
    try:
        raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise BodyRejected("unsupported_encoding", "/", "Only UTF-8 is supported") from exc
    _validate_model(model)
    _require(model["member_sha256"] == expected_member_sha256 and model["context"]["refid"] == expected_refid,
             "source_binding_mismatch", "/", "Model/raw catalog binding differs")
    event_count = _compare_raw(raw, model["root"], model["context"])
    return {"verification_version": "source-body-capture-comparison-v1", "source_body_contract": CONTRACT,
            "scope": "observed_document_body", "status": "verified",
            "source_occurrence_id": source_occurrence_id, "refid": expected_refid,
            "member_sha256": expected_member_sha256, "body_sha256": model["body_sha256"],
            "semantic_sha256": model["semantic_sha256"], "source_body_model_sha256": _digest(model),
            "source_events": event_count, "rendering": "not_assessed",
            "legal_state": "not_assessed", "document_completeness": "not_assessed"}


def qualify_source_body(raw: bytes, model: dict, *, expected_member_sha256: str,
                        expected_refid: str, source_occurrence_id: str) -> dict:
    """Return a report and HTML only on complete bounded qualification.

    Caller first validates the immutable snapshot/catalog. Expected identities
    come from that accepted catalog, not from the model being qualified. This
    gate does not install a new snapshot contract or qualify legacy projections.
    """
    report = {"gate_version": GATE_VERSION, "source_body_contract": CONTRACT,
              "scope": "observed_document_body", "status": "rejected",
              "source_occurrence_id": source_occurrence_id, "refid": expected_refid,
              "member_sha256": expected_member_sha256,
              "legal_state": "not_assessed", "document_completeness": "not_assessed"}
    try:
        proof = verify_source_body(raw, model, expected_member_sha256=expected_member_sha256,
                                   expected_refid=expected_refid, source_occurrence_id=source_occurrence_id)
        notes, references, counts = _grammar(model["root"], model["context"])
        rendered = _render(model["root"], model["context"], notes, references)
        stylesheet = stylesheet_for_body(model["root"])
        verify_rendered_body(rendered, model, stylesheet=stylesheet)
        report.update(status="passed", body_sha256=model["body_sha256"], semantic_sha256=model["semantic_sha256"],
                      source_body_model_sha256=proof["source_body_model_sha256"], source_events=proof["source_events"],
                      element_counts=counts, rendered_sha256=hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                      stylesheet_sha256=hashlib.sha256(stylesheet.encode("utf-8")).hexdigest(),
                      rendered_reverse_check="passed")
        return {"report": report, "html": rendered, "stylesheet": stylesheet}
    except BodyRejected as exc:
        report["reasons"] = [{"code": exc.code, "path": exc.path, "detail": exc.detail}]
        return {"report": report, "html": None, "stylesheet": None}
