"""Lossless, versioned document-body capture; no implicit snapshot migration.

This stdlib-only adapter deliberately does not replace the convenience LawData
parser. Its output must be explicitly persisted under a compatible snapshot
contract and independently qualified before being used for faithful rendering.
"""
from __future__ import annotations

import hashlib
import json
import re
from xml.etree import ElementTree as ET

CONTRACT = "ordered-source-document-body-v1"
MAX_BYTES = 16 * 1024 * 1024
MAX_NODES = 250_000
MAX_DEPTH = 128
MAX_ATTRIBUTES = 64
MAX_MODEL_BYTES = 32 * 1024 * 1024


class SourceBodyError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def canonical_bytes(value: object) -> bytes:
    """Contract encoding: exact Unicode, sorted object keys, compact JSON."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate_source_body_model(model: dict, *, expected_refid: str) -> None:
    """Validate persisted capture shape/digests; raw fidelity needs the independent gate."""
    def require(condition, detail):
        if not condition:
            raise SourceBodyError("invalid_model", detail)

    require(type(model) is dict and set(model) == {"contract", "member_sha256", "context", "body_sha256", "semantic_sha256", "root"}, "Exact source-body envelope required")
    require(model["contract"] == CONTRACT, "Unsupported source-body contract")
    require(all(type(model[key]) is str and re.fullmatch(r"[0-9a-f]{64}", model[key]) for key in ("member_sha256", "body_sha256", "semantic_sha256")), "Invalid source-body digest")
    context = model["context"]
    require(type(context) is dict and set(context) == {"html_lang", "html_attributes", "head_attributes", "body_attributes", "source_base", "refid"}, "Exact source context required")
    for name in ("html_attributes", "head_attributes", "body_attributes"):
        require(type(context[name]) is dict and len(context[name]) <= MAX_ATTRIBUTES
                and all(type(k) is str and type(v) is str for k, v in context[name].items()), "Invalid context attributes")
    require(context["html_lang"] == context["html_attributes"].get("lang")
            and type(context["source_base"]) is str and context["refid"] == expected_refid
            and type(expected_refid) is str and bool(expected_refid), "Invalid context identity")
    pending = [(model["root"], 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        require(count <= MAX_NODES and depth <= MAX_DEPTH, "Model node/depth limit")
        require(type(node) is dict and set(node) == {"tag", "attributes", "children"}, "Exact source node shape required")
        require(type(node["tag"]) is str and type(node["attributes"]) is dict and type(node["children"]) is list, "Invalid source node")
        require(len(node["attributes"]) <= MAX_ATTRIBUTES and all(type(k) is str and type(v) is str for k, v in node["attributes"].items()), "Invalid node attributes")
        previous_text = False
        for child in node["children"]:
            if type(child) is str:
                require(bool(child) and not previous_text, "Noncanonical text run")
                previous_text = True
            else:
                require(type(child) is dict, "Invalid source child")
                pending.append((child, depth + 1))
                previous_text = False
    try:
        require(len(canonical_bytes(model)) <= MAX_MODEL_BYTES, "Serialized model limit")
        require(_digest(model["root"]) == model["body_sha256"] and _digest([CONTRACT, context, model["root"]]) == model["semantic_sha256"], "Source-body digest mismatch")
    except (UnicodeError, TypeError, RecursionError) as exc:
        raise SourceBodyError("invalid_model", "Noncanonical source-body encoding") from exc


class _BoundedBuilder(ET.TreeBuilder):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.nodes = 0

    def start(self, tag: str, attrs: dict[str, str]):
        self.depth += 1
        self.nodes += 1
        if self.depth > MAX_DEPTH or self.nodes > MAX_NODES or len(attrs) > MAX_ATTRIBUTES:
            raise SourceBodyError("resource_limit", "XML depth, node or attribute limit exceeded")
        if "{" in tag or any("{" in key for key in attrs):
            raise SourceBodyError("unsupported_node_kind", "Namespaces need a separate contract")
        return super().start(tag, attrs)

    def end(self, tag: str):
        result = super().end(tag)
        self.depth -= 1
        return result

    def comment(self, text: str):
        raise SourceBodyError("unsupported_node_kind", "Comments are outside this capture contract")

    def pi(self, target: str, text: str | None = None):
        raise SourceBodyError("unsupported_node_kind", "Processing instructions are unsupported")


def capture_source_body(raw: bytes) -> dict:
    """Capture exactly one main.documentBody and its source context.

    Unknown element/attribute names remain in the captured evidence. They are
    not permission to render: source_body_gate has a separate closed grammar.
    Text/tails become a single ordered mixed-content array without whitespace
    stripping, role guessing, URL rewriting, or legal-state interpretation.
    """
    if not isinstance(raw, bytes):
        raise SourceBodyError("invalid_input", "Expected raw XML bytes")
    if len(raw) > MAX_BYTES:
        raise SourceBodyError("resource_limit", "Raw member exceeds 16 MiB")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceBodyError("unsupported_encoding", "Only UTF-8 source bytes are supported") from exc
    encoding = re.match(r"\s*<\?xml\s+[^?]*encoding\s*=\s*['\"]([^'\"]+)['\"]", text, re.I)
    if encoding and encoding.group(1).lower() not in {"utf-8", "utf8"}:
        raise SourceBodyError("unsupported_encoding", "XML declaration must agree with UTF-8 bytes")
    # Decode before checking so a UTF-16/32 declaration cannot evade lexical
    # guards. Only the observed inert <!DOCTYPE html> form is admitted.
    for declaration in re.findall(r"<![^>]*>", text, flags=re.S):
        if declaration != "<!DOCTYPE html>":
            raise SourceBodyError("unsupported_node_kind", "Only the inert HTML doctype is supported")
    try:
        root = ET.fromstring(text, parser=ET.XMLParser(target=_BoundedBuilder()))
    except ET.ParseError as exc:
        raise SourceBodyError("malformed_source", str(exc)) from exc
    if root.tag != "html":
        raise SourceBodyError("unsupported_context", "Expected an html document")
    heads = root.findall("head")
    bodies = root.findall("body")
    if len(heads) != 1 or len(bodies) != 1:
        raise SourceBodyError("unsupported_context", "Exactly one head and body are required")
    mains = [n for n in root.iter("main") if n.get("class") == "documentBody"]
    if len(mains) != 1 or mains[0] not in list(bodies[0]):
        raise SourceBodyError("body_cardinality", "Exactly one direct main.documentBody is required")
    bases = heads[0].findall("base")
    if len(bases) != 1 or set(bases[0].attrib) != {"href"}:
        raise SourceBodyError("unsupported_context", "Exactly one explicit source base URL is required")
    refs = [n for header in bodies[0].findall("header") for n in header.iter("dd")
            if n.get("class") == "refid"]
    if len(refs) != 1 or not "".join(refs[0].itertext()).strip():
        raise SourceBodyError("unsupported_context", "Exactly one source refid is required")

    def encode(node: ET.Element) -> dict:
        content: list[str | dict] = [node.text] if node.text else []
        for child in node:
            content.append(encode(child))
            if child.tail:
                content.append(child.tail)
        return {"tag": node.tag, "attributes": dict(sorted(node.attrib.items())),
                "children": content}

    context = {"html_lang": root.get("lang"), "source_base": bases[0].get("href"),
               "html_attributes": dict(sorted(root.attrib.items())),
               "head_attributes": dict(sorted(heads[0].attrib.items())),
               "body_attributes": dict(sorted(bodies[0].attrib.items())),
               "refid": "".join(refs[0].itertext()).strip()}
    tree = encode(mains[0])
    return {"contract": CONTRACT, "member_sha256": hashlib.sha256(raw).hexdigest(),
            "context": context, "body_sha256": _digest(tree),
            "semantic_sha256": _digest([CONTRACT, context, tree]), "root": tree}
