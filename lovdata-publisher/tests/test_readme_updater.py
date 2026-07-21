"""Tests for readme_updater.py."""
import sqlite3
from pathlib import Path

import pytest

from lovdata_publisher.readme_updater import (
    build_recent_block,
    update_readme,
    START_MARKER,
    END_MARKER,
)


def _make_db(tmp_path):
    db_path = tmp_path / "amendments.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ('lov/2026-05-15-1', 'nl.xml', 'Newest Amendment', 'Newest',
             '2026-06-01', '2026-06-01', '2026-05-15', 'FIN',
             'lov/1998-07-17-56', '2026-0500', ''),
            ('lov/2026-04-10-1', 'nl.xml', 'Older Amendment', 'Older',
             '2026-05-01', '2026-05-01', '2026-04-10', 'FIN',
             'lov/1997-06-13-44,lov/1998-07-17-56', '2026-0400', ''),
            ('lov/2026-03-01-1', 'nl.xml', 'Oldest', 'Oldest',
             '2026-04-01', '2026-04-01', '2026-03-01', 'JD',
             'lov/2005-06-17-62', '2026-0300', ''),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


def test_build_recent_block_returns_table(tmp_path):
    db = _make_db(tmp_path)
    block = build_recent_block(str(db), limit_lover=2, limit_forskrift=2)
    assert "| Date | Amendment | Targets |" in block
    assert "Newest" in block
    assert "Older" in block
    # Limit honored
    assert "Oldest" not in block


def test_build_recent_block_orders_newest_first(tmp_path):
    db = _make_db(tmp_path)
    block = build_recent_block(str(db), limit_lover=3, limit_forskrift=3)
    # Newest amendment should appear before older one in the rendered block
    newest_pos = block.find("Newest")
    older_pos = block.find("Older")
    assert newest_pos > 0
    assert older_pos > newest_pos


def test_build_recent_block_truncates_long_titles(tmp_path):
    db_path = tmp_path / "amendments.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    long_title = "A" * 100
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2026-01-01-1', 'nl.xml', long_title, '',
         '2026-01-01', '2026-01-01', '2026-01-01', 'FIN',
         'lov/1998-07-17-56', '2026-0001', ''),
    )
    conn.commit()
    conn.close()
    block = build_recent_block(str(db_path))
    assert "…" in block
    # No raw 100-char title in the block
    assert "A" * 80 not in block


def test_update_readme_replaces_block(tmp_path):
    db = _make_db(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        f"# Title\n\nIntro text.\n\n"
        f"{START_MARKER}\nold content\n{END_MARKER}\n\n"
        f"Footer.\n",
        encoding="utf-8",
    )
    changed = update_readme(str(readme), str(db))
    assert changed
    text = readme.read_text(encoding="utf-8")
    assert "old content" not in text
    assert "Newest" in text
    assert "# Title" in text
    assert "Footer." in text
    # Markers preserved
    assert START_MARKER in text
    assert END_MARKER in text


def test_update_readme_no_change_returns_false(tmp_path):
    db = _make_db(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(
        f"# Title\n{START_MARKER}\n{END_MARKER}\n",
        encoding="utf-8",
    )
    # First call: changes
    assert update_readme(str(readme), str(db))
    # Second call: no change
    assert not update_readme(str(readme), str(db))


def test_update_readme_skips_missing_markers(tmp_path):
    db = _make_db(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("# Just a plain README without markers\n", encoding="utf-8")
    assert not update_readme(str(readme), str(db))
    # File unchanged
    assert readme.read_text(encoding="utf-8") == "# Just a plain README without markers\n"


def test_update_readme_handles_missing_db(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(f"{START_MARKER}\nold\n{END_MARKER}", encoding="utf-8")
    assert not update_readme(str(readme), str(tmp_path / "no-db.db"))


def test_update_readme_handles_missing_readme(tmp_path):
    db = _make_db(tmp_path)
    assert not update_readme(str(tmp_path / "no-readme.md"), str(db))


def test_update_readme_refreshes_dated_amendments_count(tmp_path):
    """README's dated_amendments badge and feature-table row should both
    refresh from the current amendment_acts count."""
    import sqlite3

    db = tmp_path / "amendments.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    # Insert 100 acts so the count is unambiguous
    for i in range(100):
        conn.execute(
            "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f'lov/2024-01-01-{i}', 'a.xml', 'X', 'X', '2024-01-01', '2024-01-01',
             '2024-01-01', 'FIN', 'lov/1998-07-17-56', '2024-0042', ''),
        )
    conn.commit()
    conn.close()

    readme = tmp_path / "README.md"
    readme.write_text(
        '<img alt="Amendments" src="https://img.shields.io/badge/dated_amendments-31%2C459-ba0c2f">\n'
        '\n'
        '| 🕰️ **Backdated git history** | 31,459 amendment acts as backdated commits |\n'
        '\n'
        '<!-- RECENT_AMENDMENTS_START -->\n'
        'placeholder\n'
        '<!-- RECENT_AMENDMENTS_END -->\n',
        encoding="utf-8",
    )

    from lovdata_publisher.readme_updater import update_readme
    changed = update_readme(str(readme), str(db))
    assert changed is True
    text = readme.read_text(encoding="utf-8")
    # Badge updated
    assert "dated_amendments-100-ba0c2f" in text
    assert "31%2C459" not in text
    # Feature-table row updated
    assert "100 amendment acts as backdated commits" in text
    assert "31,459 amendment acts as backdated commits" not in text


BADGED_README = """<img alt="Coverage" src="https://img.shields.io/badge/coverage-9%2C999_documents-2780e3">
<img alt="Amendments" src="https://img.shields.io/badge/dated_amendments-1-ba0c2f">
<img alt="Feeds" src="https://img.shields.io/badge/atom_feeds-9%2C999-7a92b8">

| 📜 **Complete coverage** | All 9,999 formal laws + 9,999 central regulations |
| 🔔 **Per-law Atom feeds** | 9,999 subscribable feeds — one per law/forskrift with amendments, plus 99 rettsområde and 99 ministry feeds |
| 🕰️ **Backdated git history** | 1 amendment acts as backdated commits |
| 📑 **Endringshistorikk** | plus 13,700+ per-paragraph history pages |

""" + START_MARKER + "\nold\n" + END_MARKER + "\n"


def _law_md(tittel, refid, rettsomrade, departement):
    return (
        "---\n"
        f'tittel: "{tittel}"\n'
        f'refid: "{refid}"\n'
        f'rettsomrade: "{rettsomrade}"\n'
        f'departement: "{departement}"\n'
        "---\n\n# X\n"
    )


def _make_corpus(tmp_path):
    lover = tmp_path / "lover"
    forskrifter = tmp_path / "forskrifter"
    lover.mkdir()
    forskrifter.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        _law_md("Regnskapsloven", "lov/1998-07-17-56",
                "Bank, finans og regnskapsrett>Regnskap", "Finansdepartementet"),
        encoding="utf-8",
    )
    (lover / "lov-1997-06-13-44.md").write_text(
        _law_md("Aksjeloven", "lov/1997-06-13-44",
                "Selskaper, fond og foreninger\\nBank, finans og regnskapsrett>Regnskap",
                "Justis- og beredskapsdepartementet"),
        encoding="utf-8",
    )
    (forskrifter / "forskrift-2004-01-19-298.md").write_text(
        _law_md("Førerkortforskriften", "forskrift/2004-01-19-298",
                "Transport og kommunikasjoner>Veitrafikk", "Samferdselsdepartementet"),
        encoding="utf-8",
    )


def _add_amendments_table(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE amendments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            act_refid TEXT, change_type TEXT, target TEXT, target_law TEXT,
            instruction TEXT, new_text TEXT
        )"""
    )
    conn.executemany(
        "INSERT INTO amendments (act_refid, change_type, target, target_law, instruction, new_text)"
        " VALUES (?,?,?,?,?,?)",
        [
            ("lov/2026-05-15-1", "change", "lov/1998-07-17-56/§1-2", "lov/1998-07-17-56",
             "§ 1-2 skal lyde:", "ny tekst"),
            ("lov/2026-04-10-1", "change", "lov/1998-07-17-56/§7-25", "lov/1998-07-17-56",
             "§ 7-25 skal lyde:", "ny tekst"),
        ],
    )
    conn.commit()
    conn.close()


def test_update_readme_refreshes_all_counts(tmp_path):
    from lovdata_publisher.paragraph_history import _normalize_paragraph

    db = _make_db(tmp_path)
    _add_amendments_table(db)
    _make_corpus(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(BADGED_README, encoding="utf-8")

    changed = update_readme(str(readme), str(db))
    assert changed
    text = readme.read_text(encoding="utf-8")

    assert "coverage-3_documents-2780e3" in text
    assert "All 2 formal laws + 1 central regulations" in text
    assert "dated_amendments-3-ba0c2f" in text
    assert "3 amendment acts as backdated commits" in text

    # Amended targets in the db: lov/1998-07-17-56, lov/1997-06-13-44 (in
    # corpus) and lov/2005-06-17-62 (not in corpus) -> 2 per-law feeds.
    # Topics of the amended corpus docs: {Bank..., Selskaper...} -> 2.
    # Ministries: {Finansdepartementet, Justis- og beredskapsdepartementet} -> 2.
    assert "atom_feeds-6-7a92b8" in text
    assert (
        "6 subscribable feeds — one per law/forskrift with amendments, "
        "plus 2 rettsområde and 2 ministry feeds"
    ) in text

    expected_pages = len({
        ("lov/1998-07-17-56", _normalize_paragraph("lov/1998-07-17-56/§1-2", "§ 1-2 skal lyde:")),
        ("lov/1998-07-17-56", _normalize_paragraph("lov/1998-07-17-56/§7-25", "§ 7-25 skal lyde:")),
    })
    assert f"{expected_pages} per-paragraph history pages" in text
    assert "13,700+" not in text


def test_update_readme_without_corpus_dirs_still_updates(tmp_path):
    db = _make_db(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text(BADGED_README, encoding="utf-8")
    changed = update_readme(str(readme), str(db))
    assert changed
    text = readme.read_text(encoding="utf-8")
    assert "dated_amendments-3-ba0c2f" in text
    assert "coverage-9%2C999_documents" in text
