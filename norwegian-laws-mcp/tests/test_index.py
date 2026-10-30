"""Index-backed tools against a small index with the published schema."""
import json
import sqlite3

import pytest

from norwegian_laws_mcp.index import Index, IndexUnavailable, normalize_section_ref
from norwegian_laws_mcp.service import LawsService


def _node_id(refid, address):
    import hashlib
    return int.from_bytes(hashlib.sha1(f"{refid}\n{address}".encode()).digest()[:8], "big") >> 1


@pytest.fixture
def index_file(tmp_path):
    path = tmp_path / "laws-index.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE documents (refid TEXT PRIMARY KEY, kind TEXT NOT NULL, path TEXT NOT NULL, title TEXT, short_title TEXT,
            department TEXT, rettsomrade TEXT, in_force TEXT, last_amended_act TEXT, last_amended_in_force TEXT);
        CREATE TABLE nodes (id INTEGER PRIMARY KEY, refid TEXT NOT NULL, address TEXT NOT NULL, kind TEXT NOT NULL,
            parent_id INTEGER, ordinal INTEGER NOT NULL, heading TEXT, note TEXT, line_start INTEGER, line_end INTEGER, section_key TEXT);
        CREATE TABLE node_text (node_id INTEGER PRIMARY KEY, text TEXT NOT NULL);
        CREATE TABLE acts (refid TEXT PRIMARY KEY, title TEXT, short_title TEXT, date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT);
        CREATE TABLE amendments (id INTEGER PRIMARY KEY, act_refid TEXT NOT NULL, target_law TEXT, target TEXT, target_section TEXT,
            change_type TEXT, instruction TEXT, new_text TEXT, operations TEXT, date_in_force TEXT, date_published TEXT);
        CREATE TABLE refs (from_refid TEXT NOT NULL, from_node_id INTEGER NOT NULL, to_refid TEXT NOT NULL, to_section TEXT, kind TEXT NOT NULL, text TEXT);
        CREATE TABLE definitions (node_id INTEGER NOT NULL, refid TEXT NOT NULL, term TEXT NOT NULL, definition TEXT NOT NULL);
    """)
    refid = "lov/2025-06-20-105"
    other = "forskrift/2025-10-24-2096"
    conn.execute("INSERT INTO meta VALUES ('schema_version','1'),('kildemanifest','sha256:abc'),('source_sha','deadbeef'),('logical_digest','x')")
    conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)", (refid, "lov", "lover/lov-2025-06-20-105.md", "Lov om Enhetsregisteret (enhetsregisterloven)", "Enhetsregisterloven", "NFD", "", "2026-01-01", "", ""))
    conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)", (other, "forskrift", "forskrifter/forskrift-2025-10-24-2096.md", "Forskrift om konsern", "", "NFD", "", "2026-01-01", "", ""))
    ch = _node_id(refid, "kapittel 1"); s14 = _node_id(refid, "§ 1-4"); l1 = _node_id(refid, "§ 1-4 (1)"); l2 = _node_id(refid, "§ 1-4 (2)")
    s11 = _node_id(refid, "§ 1-1"); l11 = _node_id(refid, "§ 1-1 (1)"); o1 = _node_id(other, "§ 2"); ol = _node_id(other, "§ 2 (1)")
    conn.executemany("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        (ch, refid, "kapittel 1", "chapter", None, 1, "Kapittel 1. Innledende bestemmelser", None, 10, 10, None),
        (s11, refid, "§ 1-1", "section", ch, 1, "§ 1-1. Lovens formål", None, 12, 14, "1-1"),
        (l11, refid, "§ 1-1 (1)", "ledd", s11, 1, "", None, 14, 14, "1-1"),
        (s14, refid, "§ 1-4", "section", ch, 2, "§ 1-4. Definisjoner", "Endret ved lov 20 juni 2025 nr. 106.", 16, 20, "1-4"),
        (l1, refid, "§ 1-4 (1)", "ledd", s14, 1, "", None, 18, 18, "1-4"),
        (l2, refid, "§ 1-4 (2)", "ledd", s14, 2, "", None, 20, 20, "1-4"),
        (o1, other, "§ 2", "section", None, 1, "§ 2. Plikt", None, 5, 7, "2"),
        (ol, other, "§ 2 (1)", "ledd", o1, 1, "", None, 7, 7, "2"),
    ])
    conn.executemany("INSERT INTO node_text VALUES (?,?)", [
        (l11, "Formålet med loven er å legge til rette for effektiv bruk av grunndata."),
        (l1, "Med registreringsenhet menes i denne loven enhet som har registreringsplikt."),
        (l2, "Med underenhet menes en del av en registreringsenhet."),
        (ol, "Et morforetak skal melde opplysninger etter enhetsregisterloven § 1-4."),
    ])
    conn.execute("INSERT INTO acts VALUES (?,?,?,?,?,?,?,?)", ("lov/2025-06-20-106", "Endringslov", "", "2026-01-01", "2026-01-01", "2025-06-20", "NFD", refid))
    conn.execute("INSERT INTO amendments VALUES (?,?,?,?,?,?,?,?,?,?,?)", (1, "lov/2025-06-20-106", refid, "§ 1-4", "1-4", "change", "§ 1-4 annet ledd skal lyde:", "Med underenhet menes en del av en registreringsenhet.", "replace_text", "2026-01-01", "2025-06-20"))
    conn.execute("INSERT INTO amendments VALUES (?,?,?,?,?,?,?,?,?,?,?)", (2, "lov/2025-06-20-106", refid, "§ 1-1", "1-1", "renumber", "Nåværende § 1-1 blir ny § 1-2.", "", "renumber", "2026-01-01", "2025-06-20"))
    conn.execute("INSERT INTO refs VALUES (?,?,?,?,?,?)", (other, ol, refid, "1-4", "name", "enhetsregisterloven § 1-4"))
    conn.execute("INSERT INTO definitions VALUES (?,?,?,?)", (l2, refid, "underenhet", "Med underenhet menes en del av en registreringsenhet."))
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def indexed_service(service, index_file, monkeypatch):
    monkeypatch.setenv("NORWEGIAN_LAWS_INDEX", str(index_file))
    return service


def test_normalize_section_ref():
    assert normalize_section_ref("§ 1-5 a") == "1-5a" and normalize_section_ref("4-7") == "4-7"


def test_status_builds_fts_on_first_open_and_reports_publication_match(indexed_service):
    res = indexed_service.index_status()
    assert res["source"] == "env" and res["counts"]["documents"] == 2 and res["counts"]["fts"] is True
    assert res["meta"]["source_sha"] == "deadbeef"
    assert res["matches_publication"] in (None, False)


def test_outline_and_provision_with_history(indexed_service):
    out = indexed_service.outline("enhetsregisterloven")
    assert [n["address"] for n in out["nodes"]] == ["kapittel 1", "§ 1-1", "§ 1-4"]
    res = indexed_service.provision("lov/2025-06-20-105", "1-4", None)
    assert [l["address"] for l in res["ledd"]] == ["§ 1-4 (1)", "§ 1-4 (2)"]
    assert res["ledd"][1]["text"].startswith("Med underenhet")
    assert res["section"]["note"].startswith("Endret ved lov")
    assert [h["act_refid"] for h in res["history"]] == ["lov/2025-06-20-106"]
    assert res["history"][0]["operations"] == "replace_text"


def test_provision_at_a_date_reports_recorded_wording_or_its_absence(indexed_service):
    res = indexed_service.provision("lov/2025-06-20-105", "§ 1-4", "2026-06-01")
    assert res["wording_at"]["act"] == "lov/2025-06-20-106"
    earlier = indexed_service.provision("lov/2025-06-20-105", "§ 1-4", "2025-06-01")
    assert earlier["wording_at"] is None and earlier["history"] == []
    assert any("not reconstructable" in note for note in earlier["limitations"])


def test_search_references_definitions_and_sql(indexed_service):
    hits = indexed_service.index_search("underenhet", None, 10)["hits"]
    assert hits and hits[0]["address"] == "§ 1-4 (2)" and "[underenhet]" in hits[0]["snippet"]
    refs = indexed_service.references_to("enhetsregisterloven", "1-4", 10)["references"]
    assert [(r["from_refid"], r["from_address"], r["ref_kind"]) for r in refs] == [("forskrift/2025-10-24-2096", "§ 2 (1)", "name")]
    defs = indexed_service.index_definitions("underenhet", 10)["definitions"]
    assert defs[0]["term"] == "underenhet" and defs[0]["address"] == "§ 1-4 (2)"
    res = indexed_service.query_sql("SELECT refid, count(*) AS n FROM nodes GROUP BY refid ORDER BY refid", 10)
    assert res["columns"] == ["refid", "n"] and res["rows"][0] == ["forskrift/2025-10-24-2096", 2]


def test_sql_rejects_writes_and_multiple_statements(indexed_service):
    from norwegian_laws_mcp.errors import LawsError
    with pytest.raises(LawsError):
        indexed_service.query_sql("DELETE FROM nodes", 10)
    with pytest.raises(LawsError):
        indexed_service.query_sql("SELECT 1; SELECT 2", 10)
    with pytest.raises(LawsError):
        indexed_service.query_sql("SELECT * FROM nodes WHERE id IN (SELECT 1); DROP TABLE nodes", 10)
    row = indexed_service.query_sql("SELECT count(*) FROM nodes", 10)["rows"][0]
    assert row == [8]


def test_connector_search_and_fetch(indexed_service):
    res = indexed_service.connector_search("underenhet")
    ids = [r["id"] for r in res["results"]]
    assert "lov/2025-06-20-105#§ 1-4 (2)" in ids
    doc = indexed_service.connector_fetch("lov/2025-06-20-105#§ 1-4 (2)")
    assert doc["metadata"]["section"] == "1-4" and "registreringsenhet" in doc["text"].lower()


def test_without_index_the_tools_say_so(service, monkeypatch):
    monkeypatch.delenv("NORWEGIAN_LAWS_INDEX", raising=False)
    res = service.index_status()
    assert res["path"] is None and "No published index" in res["note"]
    with pytest.raises(IndexUnavailable):
        service.outline("enhetsregisterloven")
