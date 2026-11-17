"""Second processing stream: an lxml reading of each source document, compared with the parsed model.

Shares no extraction code with parser.py. It reads header fields and the whole
document body directly from the XML tree and reports where the snapshot model
disagrees: header fields, source words missing from the model, and model words
that occur nowhere in the source.
"""
import argparse
import json
import re
import sys
import tarfile
from collections import Counter
from pathlib import Path

from lxml import etree

from .coverage import model_tokens
from .language_variants import base_refid, eli_for_refid, language_variants
from .markers import markers_in

INLINE_TAGS = frozenset({"a", "b", "em", "i", "s", "small", "span", "strong", "sub", "sup", "u"})
SEPARATED_CLASSES = frozenset({
    "legalArticleValue", "legalArticleTitle", "futureLegalArticleHeader", "miscHeadline",
    "footnoteLabel", "footnotereference", "data-marginOriginalId",
})
_WORD = re.compile(r"\w+", re.UNICODE)
_SPACE = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _SPACE.sub(" ", text or "").strip()


def _is_inline(element) -> bool:
    return element.tag in INLINE_TAGS and not SEPARATED_CLASSES.intersection((element.get("class") or "").split())


def _collect(element, parts: list) -> None:
    separated = not _is_inline(element)
    if separated:
        parts.append(" ")
    parts.append(element.text or "")
    for child in element:
        if isinstance(child.tag, str):
            _collect(child, parts)
        parts.append(child.tail or "")
    if separated:
        parts.append(" ")


def element_text(element) -> str:
    parts = []
    _collect(element, parts)
    return _squash("".join(parts))


def _source_markers(body) -> list:
    found = []
    for element in body.iter("sup", "span"):
        classes = (element.get("class") or "").split()
        label = _squash("".join(element.itertext()))
        if element.tag == "sup" and "footnotereference" in classes:
            found.append(("reference", element.get("data-unique-footnote-counter") or "", label))
        elif element.tag == "span" and "footnoteLabel" in classes:
            owner = next((a for a in element.iterancestors("article") if a.get("class") == "footnote"), None)
            if owner is not None:
                found.append(("note", owner.get("data-unique-footnote-counter") or "", label))
    return found


def _model_markers(value, found: list) -> list:
    if isinstance(value, str):
        found.extend(markers_in(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if key != "source_body":
                _model_markers(child, found)
    elif isinstance(value, list):
        for child in value:
            _model_markers(child, found)
    return found


def read_document(raw: bytes) -> dict:
    root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True))
    fields = {}
    for dd in root.iterfind(".//header//dl/dd"):
        fields.setdefault(dd.get("class"), dd)

    def text(name):
        return element_text(fields[name]) if name in fields else ""

    def items(name):
        if name not in fields:
            return []
        found = [element_text(li) for li in fields[name].iterfind(".//li")]
        return found or [element_text(fields[name])]

    changed_by = [element_text(a) for a in fields["lastChangedBy"].iterfind(".//a")] if "lastChangedBy" in fields else []
    paired = re.match(re.escape(changed_by[0]) + r"\s*fra\s*(\d{4}-\d{2}-\d{2})", text("lastChangedBy")) if changed_by else None
    body = root.find(".//main[@class='documentBody']")
    return {
        "refid": text("refid"),
        "eli": text("eli"),
        "language": root.get("lang") or "",
        "title": text("title"),
        "short_title": text("titleShort"),
        "ministry": items("ministry"),
        "date_in_force": text("dateInForce"),
        "last_amended": changed_by[0] if changed_by else "",
        "last_amended_in_force": paired.group(1) if paired else text("lastChangeInForce"),
        "legal_area": items("legalArea"),
        "body_text": element_text(body) if body is not None else "",
        "markers": _source_markers(body) if body is not None else [],
    }


def source_shape(raw: bytes) -> list:
    root = etree.fromstring(raw, parser=etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True))
    body = root.find(".//main[@class='documentBody']")
    shape = []
    for element in body.iter() if body is not None else ():
        classes = set((element.get("class") or "").split())
        if element.tag == "section":
            shape.append(["section", element.get("data-name") or ""])
        elif element.tag == "article" and classes & {"legalArticle", "futureLegalArticle"}:
            shape.append(["article", element.get("data-name") or ""])
        elif element.tag == "article" and classes & {"legalP", "numberedLegalP", "centeredP"}:
            shape.append(["ledd", ""])
        elif element.tag == "li":
            shape.append(["li", element.get("data-name") or ""])
        elif element.tag in ("table", "tr", "footer"):
            shape.append([element.tag, ""])
    return shape


def shape_differences(first: list, second: list) -> list:
    differences = [[index, a, b] for index, (a, b) in enumerate(zip(first, second)) if a != b]
    if len(first) != len(second):
        differences.append([min(len(first), len(second)), ["length", len(first)], ["length", len(second)]])
    return differences


def _tokens(text: str) -> Counter:
    return Counter(word.lower() for word in _WORD.findall(text or ""))


def _marker_words(value, found: set) -> set:
    if isinstance(value, dict):
        found.update(_tokens(value.get("marker", "")))
        for child in value.values():
            _marker_words(child, found)
    elif isinstance(value, list):
        for child in value:
            _marker_words(child, found)
    return found


def compare_document(raw: bytes, law: dict) -> dict:
    source = read_document(raw)
    expected = {
        "refid": law.get("refid") if source["language"] == "nn" and base_refid(law.get("refid") or "") == source["refid"] else source["refid"],
        "title": source["title"],
        "short_title": source["short_title"],
        "ministry": "\n".join(source["ministry"]),
        "date_in_force": source["date_in_force"],
        "last_amended": source["last_amended"],
        "legal_area": "\n".join(re.sub(r"\s*>\s*", ">", area) for area in source["legal_area"]),
    }
    if source["last_amended_in_force"]:
        expected["last_amended_in_force"] = source["last_amended_in_force"]
    header = {name: [value, law.get(name) or ""] for name, value in expected.items()
              if _squash(value) != _squash(law.get(name) or "")}
    if source["eli"] and source["eli"] != eli_for_refid(law.get("refid") or source["refid"]):
        header["eli"] = [source["eli"], eli_for_refid(law.get("refid") or source["refid"])]
    source_words = _tokens(source["body_text"])
    body_only = dict(law, short_title="")
    model_words = model_tokens(body_only)
    allowed = _marker_words(law, set())
    novel = Counter({word: count for word, count in model_words.items()
                     if word not in source_words and word not in allowed})
    source_markers = Counter(source["markers"])
    model_markers = Counter(_model_markers(law, []))
    return {
        "refid": source["refid"],
        "language": source["language"],
        "source_words": sum(source_words.values()),
        "header": header,
        "lost": source_words - model_words,
        "novel": novel,
        "markers": len(source["markers"]),
        "markers_missing": source_markers - model_markers,
        "markers_extra": model_markers - source_markers,
    }


def _documents(snapshot: Path) -> dict:
    members = {}
    with (snapshot / "source-members.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["role"] in ("laws", "forskrifter") and row["parse_status"] == "parsed":
                members[(row["archive_sha256"], row["member_path"], row["member_ordinal"])] = row
    return members


def compare_snapshot(snapshot: str = "snapshot") -> dict:
    root = Path(snapshot)
    members = _documents(root)
    variants = {item["member_path"]: item for item in language_variants(snapshot)}
    rows = []
    unpublished = []
    selected_raw = {}
    variant_raw = {}
    for archive_sha256 in sorted({key[0] for key in members}):
        with tarfile.open(root / "raw" / f"{archive_sha256}.tar.bz2", "r:bz2") as archive:
            for ordinal, member in enumerate(archive.getmembers()):
                row = members.get((archive_sha256, member.name, ordinal))
                if row is None:
                    continue
                if not row["selected"] and member.name not in variants:
                    unpublished.append({"member_path": member.name, "refid": row["refid"]})
                    continue
                raw = archive.extractfile(member).read()
                if row["selected"]:
                    law = json.loads((root / row["selected_output_path"]).read_text(encoding="utf-8"))
                    selected_raw[(row["role"], row["refid"])] = raw
                else:
                    law = variants[member.name]["document"]
                    variant_raw[(row["role"], row["refid"], member.name)] = raw
                result = compare_document(raw, law)
                rows.append({
                    "member_path": member.name,
                    "refid": result["refid"],
                    "source_words": result["source_words"],
                    "header": result["header"],
                    "lost": sum(result["lost"].values()),
                    "lost_top": result["lost"].most_common(8),
                    "novel": sum(result["novel"].values()),
                    "novel_top": result["novel"].most_common(8),
                    "markers": result["markers"],
                    "markers_missing": sum(result["markers_missing"].values()),
                    "markers_extra": sum(result["markers_extra"].values()),
                    "markers_top": [list(key) for key, _ in (result["markers_missing"] + result["markers_extra"]).most_common(4)],
                })
    variant_structure = []
    for (role, refid, member_path), raw in sorted(variant_raw.items()):
        first, second = source_shape(selected_raw[(role, refid)]), source_shape(raw)
        variant_structure.append({"member_path": member_path, "refid": refid, "nodes": [len(first), len(second)],
                                  "differences": shape_differences(first, second)[:20]})
    total = sum(row["source_words"] for row in rows)
    return {
        "variant_structure": variant_structure,
        "markers": sum(row["markers"] for row in rows),
        "marker_differences": sum(row["markers_missing"] + row["markers_extra"] for row in rows),
        "documents": len(rows),
        "source_words": total,
        "header_mismatches": sum(len(row["header"]) for row in rows),
        "header_fields": dict(Counter(name for row in rows for name in row["header"])),
        "lost": sum(row["lost"] for row in rows),
        "lost_fraction": sum(row["lost"] for row in rows) / total if total else 0.0,
        "novel": sum(row["novel"] for row in rows),
        "novel_fraction": sum(row["novel"] for row in rows) / total if total else 0.0,
        "unpublished": unpublished,
        "rows": rows,
    }


def main():
    ap = argparse.ArgumentParser(description="Compare the snapshot with an independent lxml reading of its sources")
    ap.add_argument("--snapshot", default="snapshot")
    ap.add_argument("--output")
    ap.add_argument("--max-header-mismatches", type=int, default=0)
    ap.add_argument("--max-lost-fraction", type=float, default=0.0001)
    ap.add_argument("--max-novel-fraction", type=float, default=0.00002)
    ap.add_argument("--max-document-words", type=int, default=150)
    ap.add_argument("--max-unpublished", type=int, default=0)
    ap.add_argument("--max-variant-structure-differences", type=int, default=0)
    ap.add_argument("--max-marker-differences", type=int, default=0)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    report = compare_snapshot(args.snapshot)
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"second stream: docs={report['documents']} source_words={report['source_words']} "
          f"header_mismatches={report['header_mismatches']} {report['header_fields']} "
          f"lost={report['lost']} ({report['lost_fraction']*100:.4f}%) "
          f"novel={report['novel']} ({report['novel_fraction']*100:.4f}%) "
          f"unpublished={len(report['unpublished'])}")
    for row in sorted(report["rows"], key=lambda r: -(r["lost"] + r["novel"]))[:12]:
        if row["lost"] or row["novel"]:
            print(f"    {row['refid']}: lost {row['lost']} {[w for w, _ in row['lost_top'][:4]]} "
                  f"novel {row['novel']} {[w for w, _ in row['novel_top'][:4]]}")
    for row in report["rows"]:
        for name, (source, model) in row["header"].items():
            print(f"    HEADER {row['refid']} {name}: source={source!r} model={model!r}")
    for item in report["unpublished"]:
        print(f"    UNPUBLISHED {item['member_path']} ({item['refid']})")

    ok = True
    if report["header_mismatches"] > args.max_header_mismatches:
        print(f"  FAIL: {report['header_mismatches']} header mismatches > {args.max_header_mismatches}")
        ok = False
    if report["lost_fraction"] > args.max_lost_fraction:
        print(f"  FAIL: lost fraction {report['lost_fraction']:.6f} > {args.max_lost_fraction}")
        ok = False
    if report["novel_fraction"] > args.max_novel_fraction:
        print(f"  FAIL: novel fraction {report['novel_fraction']:.6f} > {args.max_novel_fraction}")
        ok = False
    worst = max((row["lost"] + row["novel"] for row in report["rows"]), default=0)
    if worst > args.max_document_words:
        print(f"  FAIL: a document differs by {worst} words > {args.max_document_words}")
        ok = False
    for item in report["variant_structure"]:
        print(f"    VARIANT {item['member_path']} ({item['refid']}): structure nodes {item['nodes']} "
              f"differences {len(item['differences'])} {item['differences'][:3]}")
    print(f"    footnote markers: {report['markers']} in source, {report['marker_differences']} differences")
    for row in report["rows"]:
        if row["markers_missing"] or row["markers_extra"]:
            print(f"    MARKERS {row['refid']}: missing {row['markers_missing']} extra {row['markers_extra']} {row['markers_top']}")
    if report["marker_differences"] > args.max_marker_differences:
        print(f"  FAIL: {report['marker_differences']} footnote marker differences > {args.max_marker_differences}")
        ok = False
    misaligned = sum(len(item["differences"]) for item in report["variant_structure"])
    if misaligned > args.max_variant_structure_differences:
        print(f"  FAIL: language variants differ in structure at {misaligned} positions > {args.max_variant_structure_differences}")
        ok = False
    if len(report["unpublished"]) > args.max_unpublished:
        print(f"  FAIL: {len(report['unpublished'])} parsed source members are not published > {args.max_unpublished}")
        ok = False
    if not ok and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
