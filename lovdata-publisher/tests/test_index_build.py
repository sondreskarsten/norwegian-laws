import json
import sqlite3

from lovdata_publisher.index_build import (
    alias_map, build, ensure_fts, extract_refs, logical_digest, normalize_section_ref, parse_nodes, read_meta,
)

LAW = """---
tittel: "Lov om årsregnskap m.v. (regnskapsloven)"
korttittel: "Regnskapsloven – rskl"
refid: "lov/1998-07-17-56"
departement: "Finansdepartementet"
ikrafttredelse: "1999-01-01"
sist-endret: "lov/2025-06-20-106"
---

# Lov om årsregnskap m.v. (regnskapsloven)

## Kapittel 1. Virkeområde

#### § 1-1. Lovens virkeområde

(1) Loven gjelder regnskapspliktige som nevnt i § 1-2 første ledd nr. 1 til 12.

(2) Kongen fastsetter regler, jf. selskapsloven § 1-2 og lov 13. juni 1997 nr. 44 § 3-1.

*Endret ved lover 15 juni 2001 nr. 59.*

#### § 1-2. Regnskapspliktige

(1) Regnskapspliktige etter denne loven er:

1. aksjeselskaper,
2. selskap som definert i selskapsloven § 1-2 første ledd bokstav a,

(2) Med regnskapsår menes i denne loven kalenderåret.

## Vedlegg 1

#### § 1. Skjema

Et skjema.
"""

OTHER = """---
tittel: "Lov om selskaper (selskapsloven)"
korttittel: "Selskapsloven"
refid: "lov/1985-06-21-83"
---

# Lov om selskaper

#### § 1-2. Definisjoner

I denne loven forstås med:

1. selskap: en sammenslutning som driver virksomhet for felles regning.
"""


def test_parse_nodes_builds_chapters_sections_ledd_and_items():
    nodes = parse_nodes("lov/1998-07-17-56", LAW)
    addresses = [(n["kind"], n["address"]) for n in nodes]
    assert ("chapter", "kapittel 1") in addresses
    assert ("section", "§ 1-1") in addresses and ("ledd", "§ 1-1 (2)") in addresses
    assert ("item", "§ 1-2 (1) nr. 2") in addresses
    assert ("section", "§ 1") in addresses
    section = next(n for n in nodes if n["address"] == "§ 1-1")
    assert section["note"].startswith("Endret ved lover 15 juni 2001")
    ledd = next(n for n in nodes if n["address"] == "§ 1-2 (1)")
    assert ledd["text"].startswith("Regnskapspliktige etter denne loven er:")
    assert "aksjeselskaper" in ledd["text"]
    ids = [n["id"] for n in nodes]
    assert len(ids) == len(set(ids))
    assert parse_nodes("lov/1998-07-17-56", LAW)[3]["id"] == nodes[3]["id"]


def test_repeated_address_in_the_same_document_gets_a_distinct_id():
    text = LAW + "\n#### § 1. Skjema igjen\n\nEnda et skjema.\n"
    nodes = parse_nodes("lov/1998-07-17-56", text)
    repeated = [n for n in nodes if n["address"].startswith("§ 1 ") or n["address"] == "§ 1"]
    assert [n["address"] for n in repeated if n["kind"] == "section"] == ["§ 1", "§ 1 [2]"]


def test_references_are_resolved_by_alias_refid_and_internally():
    docs = [{"refid": "lov/1998-07-17-56", "title": "Lov om årsregnskap m.v. (regnskapsloven)", "short_title": "Regnskapsloven – rskl"},
            {"refid": "lov/1985-06-21-83", "title": "Lov om selskaper (selskapsloven)", "short_title": "Selskapsloven"}]
    aliases = alias_map(docs)
    assert aliases["regnskapsloven"] == "lov/1998-07-17-56" and aliases["selskapsloven"] == "lov/1985-06-21-83"
    nodes = parse_nodes("lov/1998-07-17-56", LAW)
    ledd = next(n for n in nodes if n["address"] == "§ 1-1 (2)")
    refs = extract_refs("lov/1998-07-17-56", ledd, aliases)
    assert {(r["to_refid"], r["to_section"], r["kind"]) for r in refs} == {
        ("lov/1985-06-21-83", "1-2", "name"), ("lov/1997-06-13-44", "3-1", "refid"),
    }
    first = next(n for n in nodes if n["address"] == "§ 1-1 (1)")
    assert [(r["to_refid"], r["to_section"], r["kind"]) for r in extract_refs("lov/1998-07-17-56", first, aliases)] == [
        ("lov/1998-07-17-56", "1-2", "internal"),
    ]
    assert normalize_section_ref("§ 1-5 a") == "1-5a" and normalize_section_ref("§ 8-11-1") == "8-11-1"
    three = parse_nodes("forskrift/1999-11-19-1158", "---\nrefid: \"x\"\n---\n\n#### § 8-11-1. Virkeområde\n\nTekst.\n\n#### § 8-11-2. Mer\n\nMer tekst.\n")
    assert [n["address"] for n in three if n["kind"] == "section"] == ["§ 8-11-1", "§ 8-11-2"]


def _corpus(tmp_path):
    root = tmp_path / "corpus"
    (root / "lover").mkdir(parents=True)
    (root / "forskrifter").mkdir()
    (root / "lover" / "lov-1998-07-17-56.md").write_text(LAW, encoding="utf-8")
    (root / "lover" / "lov-1985-06-21-83.md").write_text(OTHER, encoding="utf-8")
    db = tmp_path / "amendments.db"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE amendment_acts (refid TEXT PRIMARY KEY, filename TEXT, title TEXT, short_title TEXT,
              date_in_force TEXT, date_in_force_resolved TEXT, is_deferred INTEGER, date_published TEXT, ministry TEXT,
              changes_to TEXT, misc_info TEXT, journal_number TEXT, amendment_count INTEGER);
            CREATE TABLE amendments (id INTEGER PRIMARY KEY, act_refid TEXT, change_type TEXT, target TEXT, target_law TEXT,
              instruction TEXT, new_text TEXT);
            INSERT INTO amendment_acts VALUES ('lov/2001-06-15-59','x.xml','Endringslov','',
              '2005-01-01','2005-01-01',0,'2001-06-15','Finansdepartementet','lov/1998-07-17-56','','',1);
            INSERT INTO amendments VALUES (1,'lov/2001-06-15-59','change','§ 1-1','lov/1998-07-17-56',
              '§ 1-1 første ledd skal lyde:','Loven gjelder regnskapspliktige.');
        """)
    return root, db


def test_build_writes_documents_nodes_refs_definitions_amendments_and_meta(tmp_path):
    root, db = _corpus(tmp_path)
    out = tmp_path / "laws-index.sqlite"
    counts = build(root, db, out, {"kildemanifest": "sha256:abc", "parser_loader": "t1"})
    assert counts["documents"] == 2 and counts["amendments"] == 1 and counts["refs"] >= 3
    conn = sqlite3.connect(out)
    assert conn.execute("SELECT kind, path FROM documents WHERE refid='lov/1998-07-17-56'").fetchone() == ("lov", "lover/lov-1998-07-17-56.md")
    row = conn.execute("SELECT target_section, operations, date_in_force FROM amendments").fetchone()
    assert row == ("1-1", "replace_text", "2005-01-01")
    terms = {t for (t,) in conn.execute("SELECT term FROM definitions")}
    assert "regnskapsår" in terms and "selskap" in terms
    meta = read_meta(out)
    assert meta["kildemanifest"] == "sha256:abc" and meta["schema_version"] == "1"
    assert meta["logical_digest"] == logical_digest(conn)
    assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='node_fts'").fetchone() is None
    assert ensure_fts(conn) is True and ensure_fts(conn) is False
    hit = conn.execute("SELECT n.address FROM node_fts f JOIN nodes n ON n.id = f.rowid WHERE node_fts MATCH 'kalenderåret'").fetchone()
    assert hit == ("§ 1-2 (2)",)


def test_logical_digest_is_stable_across_builds_and_ignores_meta(tmp_path):
    root, db = _corpus(tmp_path)
    a = build(root, db, tmp_path / "a.sqlite", {"kildemanifest": "one"})
    b = build(root, db, tmp_path / "b.sqlite", {"kildemanifest": "two", "source_sha": "x"})
    assert a["logical_digest"] == b["logical_digest"]
    (root / "lover" / "lov-1998-07-17-56.md").write_text(LAW.replace("kalenderåret", "regnskapsperioden"), encoding="utf-8")
    c = build(root, db, tmp_path / "c.sqlite", {"kildemanifest": "one"})
    assert c["logical_digest"] != a["logical_digest"]
