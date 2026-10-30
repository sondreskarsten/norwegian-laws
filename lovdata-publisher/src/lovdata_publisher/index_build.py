"""Build the queryable index of the published corpus (docs/NODE-HISTORY-DESIGN.md).

The index is a SQLite file derived in the same run from the same parser output
as the committed Markdown (``lover/``, ``forskrifter/``) and the amendment
database. It never becomes a second source of truth: it carries the source
manifest digest and parser identity it was built from, and its *logical
digest* (SHA-256 over the sorted rows of every content table) is what the
reproducibility gate compares, because SQLite files are not byte-stable.

Tables
  meta(key, value)                      provenance and schema version
  documents(refid, kind, path, ...)     one row per published document
  nodes(id, refid, address, kind, parent_id, ordinal, heading, line_start, line_end)
  node_text(node_id, text)              wording of each node
  node_fts                              FTS5 over node_text (external content; built by the reader on first open)
  acts(refid, title, ...)               amendment acts
  amendments(id, act_refid, target_law, target_section, change_type, instruction,
             new_text, operations, date_in_force, date_published)
  refs(from_refid, from_node_id, to_refid, to_section, kind, text)
  definitions(node_id, refid, term, definition)

Node ids are deterministic (a hash of refid and address), so the same address
keeps its id across builds. Renumbering is recorded as ``renumber`` amendment
records; moving an id with its provision across a renumbering is not done yet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

SCHEMA_VERSION = 1
CONTENT_TABLES = ("documents", "nodes", "node_text", "acts", "amendments", "refs", "definitions")

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
SECTION_HEADING_RE = re.compile(r"^§\s*(\d+(?:-\d+)*)\s*([a-z](?!\w))?\.?\s*(.*)$")
CHAPTER_HEADING_RE = re.compile(r"^(Kapittel|Kap\.?|Del|Avsnitt|Vedlegg)\s+([0-9IVXLC]+\s?[A-Za-z]?)\.?\s*(.*)$", re.I)
LEDD_RE = re.compile(r"^\((\d+)\)\s+(.*)$")
ITEM_RE = re.compile(r"^(\s*)(?:(\d+)\.|([a-zæøå])\.|-)\s+(.*)$")
NOTE_RE = re.compile(r"^\*Endret ved .*\*$|^\*Tilføyd ved .*\*$|^\*Opphevet ved .*\*$")

NAMED_REF_RE = re.compile(r"\b([A-Za-zÆØÅæøå][\wæøå-]*(?:loven|lova|forskriften|forskrifta|lovens|lovas))\s+§\s*(\d+(?:-\d+)*(?:\s?[a-z](?!\w))?)")
REFID_REF_RE = re.compile(r"\b(lov|forskrift|Lov|Forskrift)\s+(?:av\s+)?(\d{1,2})\.\s*(\w+)\s+(\d{4})\s+nr\.\s*(\d+)(?:\s+§\s*(\d+(?:-\d+)*(?:\s?[a-z](?!\w))?))?")
INTERNAL_REF_RE = re.compile(r"(?<![\wæøå])§\s*(\d+(?:-\d+)*(?:\s?[a-z](?!\w))?)")
DEFINITION_SENTENCE_RE = re.compile(r"\b[Mm]ed\s+([^,.;:]{2,80}?)\s+(?:menes|forstås|forstår\s+en|meiner\s+ein|er\s+meint)\b[^.]*?(?:\s|:)\s*([^.]+\.)")
DEFINITION_ITEM_RE = re.compile(r"^(?:\d+\.|[a-zæøå]\.|-)?\s*([^:]{2,60}?)\s*:\s+(.{10,})$")
DEFINITION_HEADING_RE = re.compile(r"definisjon|forstås med|menes med|ordforklar|begrep", re.I)
MONTHS = {"januar": "01", "februar": "02", "mars": "03", "april": "04", "mai": "05", "juni": "06", "juli": "07",
          "august": "08", "september": "09", "oktober": "10", "november": "11", "desember": "12"}


def node_id(refid: str, address: str) -> int:
    digest = hashlib.sha1(f"{refid}\n{address}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") >> 1


def section_key(number: str, letter: str | None = None) -> str:
    key = number.strip().replace(" ", "")
    if letter:
        key += letter.strip().lower()
    return key


def normalize_section_ref(spec: str) -> str:
    """'§ 4-7', '4-7 a', '§4-7a' -> '4-7a'."""
    s = spec.replace("§", "").replace("\xa0", " ").strip().rstrip(".")
    m = re.match(r"^(\d+(?:-\d+)*)\s*([a-zA-Z])?$", s)
    if not m:
        return s.lower().replace(" ", "")
    return section_key(m.group(1), m.group(2))


def parse_front_matter(text: str) -> tuple[dict, int]:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}, 0
    meta = {}
    for line in m.group(1).split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        meta[key.strip()] = value
    return meta, m.group(0).count("\n")


def parse_nodes(refid: str, text: str) -> list[dict]:
    """Chapter, section, ledd and item nodes of one Markdown document."""
    lines = text.split("\n")
    nodes: list[dict] = []
    chapter = None
    section = None
    ledd = None
    item_ordinal = 0
    ledd_ordinal = 0
    in_fence = False

    seen: dict[str, int] = {}

    def add(kind, address, parent, ordinal, heading, line_start):
        # A document can repeat an address (annex sections numbered from § 1
        # again); the second occurrence is addressed '§ 1 [2]' so ids stay unique.
        seen[address] = seen.get(address, 0) + 1
        if seen[address] > 1:
            address = f"{address} [{seen[address]}]"
        node = {"id": node_id(refid, address), "refid": refid, "address": address, "kind": kind,
                "parent_id": parent["id"] if parent else None, "ordinal": ordinal, "heading": heading,
                "line_start": line_start, "line_end": line_start, "text_lines": []}
        nodes.append(node)
        return node

    for i, line in enumerate(lines, start=1):
        if line.startswith("```"):
            in_fence = not in_fence
        if in_fence:
            if ledd is not None:
                ledd["text_lines"].append(line); ledd["line_end"] = i
            continue
        m = HEADING_RE.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2)
            if level == 1:
                continue
            sm = SECTION_HEADING_RE.match(title)
            if sm:
                key = section_key(sm.group(1), sm.group(2))
                section = add("section", f"§ {key}", chapter, len([n for n in nodes if n["kind"] == "section"]) + 1,
                              title, i)
                ledd = None; ledd_ordinal = 0; item_ordinal = 0
                continue
            cm = CHAPTER_HEADING_RE.match(title)
            if cm:
                label = cm.group(2).replace(" ", "")
                chapter = add("chapter", f"{cm.group(1).lower().rstrip('.')} {label}", None,
                              len([n for n in nodes if n["kind"] == "chapter"]) + 1, title, i)
                section = None; ledd = None
                continue
            # other headings (annex titles, part names) become chapter-like markers
            chapter = add("chapter", f"heading {i}", None, len([n for n in nodes if n["kind"] == "chapter"]) + 1, title, i)
            section = None; ledd = None
            continue
        if section is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if NOTE_RE.match(stripped):
            section["note"] = stripped.strip("*")
            continue
        lm = LEDD_RE.match(stripped)
        if lm:
            ledd_ordinal = int(lm.group(1))
            ledd = add("ledd", f"{section['address']} ({ledd_ordinal})", section, ledd_ordinal, "", i)
            ledd["text_lines"].append(lm.group(2)); item_ordinal = 0
            section["line_end"] = i
            continue
        im = ITEM_RE.match(line)
        if im and ledd is not None and not im.group(1):
            item_ordinal += 1
            label = im.group(2) or im.group(3) or str(item_ordinal)
            unit = "nr." if im.group(2) else ("bokstav" if im.group(3) else "strekpunkt")
            item = add("item", f"{ledd['address']} {unit} {label}", ledd, item_ordinal, "", i)
            item["text_lines"].append(im.group(4))
            ledd["text_lines"].append(stripped); ledd["line_end"] = i; section["line_end"] = i
            continue
        if ledd is None:
            ledd_ordinal += 1
            ledd = add("ledd", f"{section['address']} ({ledd_ordinal})", section, ledd_ordinal, "", i)
            item_ordinal = 0
        ledd["text_lines"].append(stripped); ledd["line_end"] = i; section["line_end"] = i
    for n in nodes:
        n["text"] = "\n".join(n["text_lines"]).strip()
        del n["text_lines"]
    # Wording is stored once, on the ledd: a section's text is the
    # concatenation of its ledd and an item's text is part of its ledd.
    for n in nodes:
        if n["kind"] in ("section", "chapter"):
            n["text"] = ""
    return nodes


def alias_map(documents: list[dict]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for doc in documents:
        short = doc.get("short_title") or ""
        for part in re.split(r"\s+[–-]\s+|,", short):
            part = part.strip().lower()
            if part and re.search(r"loven$|lova$|forskriften$|forskrifta$", part):
                aliases.setdefault(part, doc["refid"])
        title = doc.get("title") or ""
        for paren in re.findall(r"\(([^()]+)\)", title):
            paren = paren.strip().lower()
            if re.search(r"loven$|lova$|forskriften$|forskrifta$", paren) and " " not in paren:
                aliases.setdefault(paren, doc["refid"])
    return aliases


def extract_refs(doc_refid: str, node: dict, aliases: dict[str, str]) -> list[dict]:
    text = node["text"]
    if not text:
        return []
    refs = []
    seen = set()
    for m in REFID_REF_RE.finditer(text):
        kind, day, month, year, nr, sec = m.groups()
        mm = MONTHS.get(month.lower())
        if not mm:
            continue
        to = f"{kind.lower()}/{year}-{mm}-{day.zfill(2)}-{nr}"
        key = (to, normalize_section_ref(sec) if sec else "")
        if key not in seen:
            seen.add(key)
            refs.append({"to_refid": to, "to_section": key[1], "kind": "refid", "text": m.group(0)})
    for m in NAMED_REF_RE.finditer(text):
        name, sec = m.group(1).lower(), m.group(2)
        to = aliases.get(name)
        if not to:
            continue
        key = (to, normalize_section_ref(sec))
        if key not in seen:
            seen.add(key)
            refs.append({"to_refid": to, "to_section": key[1], "kind": "name", "text": m.group(0)})
    named_spans = [m.span(2) for m in NAMED_REF_RE.finditer(text)]
    refid_spans = [m.span() for m in REFID_REF_RE.finditer(text)]
    for m in INTERNAL_REF_RE.finditer(text):
        if any(a <= m.start(1) < b for a, b in named_spans + refid_spans):
            continue
        key = (doc_refid, normalize_section_ref(m.group(1)))
        if key[1] == normalize_section_ref(node["address"].split(" (")[0]) if node["address"].startswith("§") else False:
            continue
        if key not in seen:
            seen.add(key)
            refs.append({"to_refid": doc_refid, "to_section": key[1], "kind": "internal", "text": m.group(0)})
    return refs


def extract_definitions(section: dict, children: list[dict]) -> list[dict]:
    found = []
    heading = section.get("heading", "")
    in_definition_section = bool(DEFINITION_HEADING_RE.search(heading)) or bool(
        re.search(r"(?:I denne (?:loven?|forskrifta|forskriften) (?:forstås|menes)|I denne lov forstås|I lova her tyder)", section["text"][:300])
    )
    for node in children:
        for line in node["text"].split("\n"):
            m = DEFINITION_SENTENCE_RE.search(line)
            if m:
                found.append({"node_id": node["id"], "term": m.group(1).strip(), "definition": line.strip()})
            elif in_definition_section and node["kind"] == "item":
                im = DEFINITION_ITEM_RE.match(line)
                if im:
                    found.append({"node_id": node["id"], "term": im.group(1).strip(), "definition": im.group(2).strip()})
    return found


def read_documents(root: Path) -> list[tuple[dict, str]]:
    docs = []
    for kind, folder in (("lov", "lover"), ("forskrift", "forskrifter")):
        for path in sorted((root / folder).glob("*.md")):
            if path.name == "README.md":
                continue
            text = path.read_text(encoding="utf-8")
            meta, _ = parse_front_matter(text)
            refid = meta.get("refid") or ""
            if not refid:
                continue
            docs.append(({
                "refid": refid, "kind": kind, "path": f"{folder}/{path.name}", "title": meta.get("tittel", ""),
                "short_title": meta.get("korttittel", ""), "department": meta.get("departement", ""),
                "rettsomrade": meta.get("rettsomrade", ""), "in_force": meta.get("ikrafttredelse", ""),
                "last_amended_act": meta.get("sist-endret", ""), "last_amended_in_force": meta.get("sist-endret-ikrafttredelse", ""),
            }, text))
    return docs


FTS_SQL = "CREATE VIRTUAL TABLE node_fts USING fts5(text, content='node_text', content_rowid='node_id', tokenize='unicode61')"


def ensure_fts(conn: sqlite3.Connection) -> bool:
    """Create and fill the full-text index when it is missing; returns True when it was built.

    The published asset ships without it (it is derived data and a third of
    the file); a reader builds it once on first open.
    """
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'node_fts'").fetchone():
        return False
    conn.execute(FTS_SQL)
    conn.execute("INSERT INTO node_fts(node_fts) VALUES ('rebuild')")
    conn.commit()
    return True


def build(root: Path, db_path: Path, output: Path, meta: dict[str, str], fts: bool = False) -> dict:
    from lovdata_loader.instruction_catalog import InstructionCatalog
    catalog = InstructionCatalog()
    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE documents (refid TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL, title TEXT, short_title TEXT,
            department TEXT, rettsomrade TEXT, in_force TEXT, last_amended_act TEXT, last_amended_in_force TEXT);
        CREATE TABLE nodes (id INTEGER PRIMARY KEY, refid TEXT NOT NULL, address TEXT NOT NULL, kind TEXT NOT NULL,
            parent_id INTEGER, ordinal INTEGER NOT NULL, heading TEXT, note TEXT, line_start INTEGER, line_end INTEGER,
            section_key TEXT);
        CREATE INDEX nodes_refid ON nodes (refid, kind, ordinal);
        CREATE INDEX nodes_section ON nodes (refid, section_key);
        CREATE TABLE node_text (node_id INTEGER PRIMARY KEY, text TEXT NOT NULL);
        CREATE TABLE acts (refid TEXT PRIMARY KEY, title TEXT, short_title TEXT, date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT);
        CREATE TABLE amendments (id INTEGER PRIMARY KEY, act_refid TEXT NOT NULL, target_law TEXT, target TEXT, target_section TEXT,
            change_type TEXT, instruction TEXT, new_text TEXT, operations TEXT, date_in_force TEXT, date_published TEXT);
        CREATE INDEX amendments_target ON amendments (target_law, target_section, date_in_force);
        CREATE TABLE refs (from_refid TEXT NOT NULL, from_node_id INTEGER NOT NULL, to_refid TEXT NOT NULL, to_section TEXT,
            kind TEXT NOT NULL, text TEXT);
        CREATE INDEX refs_to ON refs (to_refid, to_section);
        CREATE TABLE definitions (node_id INTEGER NOT NULL, refid TEXT NOT NULL, term TEXT NOT NULL, definition TEXT NOT NULL);
        CREATE INDEX definitions_term ON definitions (term);
    """)
    docs = read_documents(root)
    documents = [d for d, _ in docs]
    aliases = alias_map(documents)
    counts = {"documents": 0, "nodes": 0, "refs": 0, "definitions": 0, "amendments": 0}
    for doc, text in docs:
        conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)", (
            doc["refid"], doc["kind"], doc["path"], doc["title"], doc["short_title"], doc["department"],
            doc["rettsomrade"], doc["in_force"], doc["last_amended_act"], doc["last_amended_in_force"]))
        counts["documents"] += 1
        nodes = parse_nodes(doc["refid"], text)
        for n in nodes:
            key = normalize_section_ref(n["address"].split(" (")[0]) if n["kind"] != "chapter" else None
            conn.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                n["id"], n["refid"], n["address"], n["kind"], n["parent_id"], n["ordinal"], n["heading"],
                n.get("note"), n["line_start"], n["line_end"], key))
            if n["text"] and n["kind"] == "ledd":
                conn.execute("INSERT INTO node_text VALUES (?,?)", (n["id"], n["text"]))
            counts["nodes"] += 1
            if n["kind"] == "ledd":
                for ref in extract_refs(doc["refid"], n, aliases):
                    conn.execute("INSERT INTO refs VALUES (?,?,?,?,?,?)", (
                        doc["refid"], n["id"], ref["to_refid"], ref["to_section"], ref["kind"], ref["text"]))
                    counts["refs"] += 1
        children_of: dict[int | None, list[dict]] = {}
        for n in nodes:
            children_of.setdefault(n["parent_id"], []).append(n)
        for section in (n for n in nodes if n["kind"] == "section"):
            ledd_nodes = children_of.get(section["id"], [])
            children = ledd_nodes + [item for ledd in ledd_nodes for item in children_of.get(ledd["id"], [])]
            section_text = "\n\n".join(l["text"] for l in ledd_nodes if l["text"])
            for d in extract_definitions({**section, "text": section_text}, children):
                conn.execute("INSERT INTO definitions VALUES (?,?,?,?)", (d["node_id"], doc["refid"], d["term"], d["definition"]))
                counts["definitions"] += 1
    if fts:
        ensure_fts(conn)

    if db_path.exists():
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            for row in src.execute("SELECT refid, title, short_title, date_in_force, date_in_force_resolved, date_published, ministry, changes_to FROM amendment_acts"):
                conn.execute("INSERT INTO acts VALUES (?,?,?,?,?,?,?,?)", tuple(row))
            for row in src.execute("""SELECT a.id, a.act_refid, a.target_law, a.target, a.change_type, a.instruction, a.new_text,
                                             ac.date_in_force_resolved, ac.date_published
                                      FROM amendments a LEFT JOIN amendment_acts ac ON ac.refid = a.act_refid ORDER BY a.id"""):
                aid, act, tlaw, target, ctype, instr, new_text, d_in_force, d_pub = row
                sec = ""
                m = re.search(r"§\s*(\d+(?:-\d+)*(?:\s?[a-z](?!\w))?)", target or "") or re.search(r"§\s*(\d+(?:-\d+)*(?:\s?[a-z](?!\w))?)", instr or "")
                if m:
                    sec = normalize_section_ref(m.group(1))
                ops = ",".join(catalog.classify(instr or ""))
                # The full wording stays in the amendment database and in historie/;
                # the index keeps what a reader needs to see which text was set.
                conn.execute("INSERT INTO amendments VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                    aid, act, tlaw, target, sec, ctype, (instr or "")[:500], (new_text or "")[:1500], ops,
                    (d_in_force or "")[:10], (d_pub or "")[:10]))
                counts["amendments"] += 1
        finally:
            src.close()
    for key, value in {"schema_version": str(SCHEMA_VERSION), **meta}.items():
        conn.execute("INSERT INTO meta VALUES (?,?)", (key, value))
    conn.commit()
    digest = logical_digest(conn)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('logical_digest', ?)", (digest,))
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    counts["logical_digest"] = digest
    return counts


def logical_digest(conn: sqlite3.Connection) -> str:
    """SHA-256 over the sorted rows of every content table; stable across SQLite file layouts."""
    h = hashlib.sha256()
    for table in CONTENT_TABLES:
        h.update(table.encode())
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        for row in sorted(rows, key=lambda r: json.dumps(r, ensure_ascii=False, default=str)):
            h.update(json.dumps(row, ensure_ascii=False, default=str).encode("utf-8"))
            h.update(b"\n")
    return h.hexdigest()


def stamp(output: Path, meta: dict[str, str]) -> None:
    conn = sqlite3.connect(output)
    for key, value in meta.items():
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


def read_meta(output: Path) -> dict[str, str]:
    conn = sqlite3.connect(f"file:{output}?mode=ro", uri=True)
    try:
        return dict(conn.execute("SELECT key, value FROM meta").fetchall())
    finally:
        conn.close()


def _meta_args(values: list[str]) -> dict[str, str]:
    meta = {}
    for item in values or []:
        key, _, value = item.partition("=")
        meta[key] = value
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build, stamp or digest the corpus index")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("--laws", type=Path, default=Path("."), help="Directory holding lover/ and forskrifter/")
    p.add_argument("--db", type=Path, default=Path("snapshot/amendments.db"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--meta", action="append", default=[], help="key=value stored in the meta table")
    p.add_argument("--fts", action="store_true", help="Also build the full-text index (readers build it on first open otherwise)")
    p = sub.add_parser("stamp")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--meta", action="append", default=[])
    p = sub.add_parser("digest")
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        counts = build(args.laws, args.db, args.output, _meta_args(args.meta), fts=args.fts)
        print(json.dumps(counts))
    elif args.command == "stamp":
        stamp(args.output, _meta_args(args.meta))
        print(json.dumps(read_meta(args.output)))
    else:
        conn = sqlite3.connect(f"file:{args.output}?mode=ro", uri=True)
        print(logical_digest(conn))
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
