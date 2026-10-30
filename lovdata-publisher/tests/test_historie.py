"""Tests for lovdata_publisher.historie."""
import sqlite3

from lovdata_publisher.historie import generate_historie


def _db(path, acts):
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE amendment_acts (refid TEXT PRIMARY KEY, filename TEXT, title TEXT, short_title TEXT,
              date_in_force TEXT, date_in_force_resolved TEXT, is_deferred INTEGER, date_published TEXT,
              ministry TEXT, changes_to TEXT, misc_info TEXT, journal_number TEXT, amendment_count INTEGER);
            CREATE TABLE amendments (id INTEGER PRIMARY KEY, act_refid TEXT, change_type TEXT, target TEXT,
              target_law TEXT, instruction TEXT, new_text TEXT);
        """)
        for refid, target in acts:
            conn.execute("INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (refid, "x.xml", f"Endringslov {refid}", "", "2024-01-01", "2024-01-01", 0, "2023-12-01",
                          "D", target, "", "", 1))
            conn.execute("INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text) "
                         "VALUES (?,?,?,?,?,?)", (refid, "change", target + "/§1", target, "§ 1 skal lyde:", "Ny tekst."))


def test_generate_historie_prunes_files_it_did_not_write(tmp_path):
    db = tmp_path / "amendments.db"
    _db(db, [("lov/2024-06-01-10", "lov/2020-01-01-1")])
    out = tmp_path / "historie"
    out.mkdir()
    (out / "lov-1999-01-01-9.md").write_text("stale from an earlier corpus", encoding="utf-8")
    (out / "lov-om-noe.md").write_text("stale from an earlier naming", encoding="utf-8")
    count = generate_historie(str(db), str(out))
    assert count == 1
    assert sorted(p.name for p in out.glob("*.md")) == ["lov-2020-01-01-1.md"]
    assert "§ 1 skal lyde:" in (out / "lov-2020-01-01-1.md").read_text(encoding="utf-8")
