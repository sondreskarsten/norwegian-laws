"""Tests for stats_page.py — the aktivitet leaderboard."""
import sqlite3
from pathlib import Path

import pytest

from lovdata_publisher.stats_page import (
    _ministry_slug,
    _refid_to_stem,
    generate_stats_page,
)


def test_refid_to_stem():
    assert _refid_to_stem("lov/1998-07-17-56") == "lov-1998-07-17-56"
    assert _refid_to_stem("forskrift/2024-01-01-1") == "forskrift-2024-01-01-1"


def test_ministry_slug():
    assert _ministry_slug("Finansdepartementet") == "finansdepartementet"
    assert _ministry_slug("Klima- og miljødepartementet") == "klima--og-miljodepartementet"
    assert _ministry_slug("Næringsdepartementet") == "naeringsdepartementet"


def test_generate_stats_page_writes_html(tmp_path):
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
    conn.execute("""
        CREATE TABLE amendments (
            id INTEGER, act_refid TEXT, change_type TEXT,
            target TEXT, target_law TEXT, instruction TEXT, new_text TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ('lov/2024-06-21-42', 'a.xml', 'Endr. regnskapsloven', 'X',
             '2024-11-01', '2024-11-01', '2024-06-21', 'Finansdepartementet',
             'lov/1998-07-17-56', '2024-0042', ''),
            ('lov/2023-01-01-1', 'b.xml', 'Older endr.', 'Y',
             '2023-01-01', '2023-01-01', '2023-01-01', 'Justis- og beredskapsdepartementet',
             'lov/1998-07-17-56', '2023-0001', ''),
        ],
    )
    conn.executemany(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        [
            (1, 'lov/2024-06-21-42', 'change', '§ 7-25', 'lov/1998-07-17-56', '§ 7-25', ''),
            (2, 'lov/2023-01-01-1', 'change', '§ 1-2', 'lov/1998-07-17-56', '§ 1-2', ''),
        ],
    )
    conn.commit()
    conn.close()

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "Regnskapsloven"\nkorttittel: "Regnskapsloven"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "aktivitet.html"
    ok = generate_stats_page(
        db_path=str(db),
        output_path=str(out),
        lover_dir=str(lover),
        forskrifter_dir=str(tmp_path / "forskrifter"),  # doesn't exist
    )
    assert ok is True
    page = out.read_text(encoding="utf-8")
    assert "<h1>Aktivitet" in page
    assert "Regnskapsloven" in page
    assert "2" in page  # Two amending acts
    assert "Finansdepartementet" in page
    # Corpus doc links locally; feed and historie have no manifest attached
    # here, so the gated renderer emits placeholders instead of dead links.
    assert "lover/lov-1998-07-17-56.html" in page
    assert "feeds/lov-1998-07-17-56.xml" not in page
    assert "historie/lov-1998-07-17-56.html" not in page
    assert page.count("\u2014") >= 2


def test_stats_page_gates_links_on_existence(tmp_path):
    from lovdata_publisher.site_index import SiteIndex

    db = tmp_path / "amendments.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE amendment_acts (
        refid TEXT, filename TEXT, title TEXT, short_title TEXT,
        date_in_force TEXT, date_in_force_resolved TEXT,
        date_published TEXT, ministry TEXT, changes_to TEXT,
        journal_number TEXT, misc_info TEXT)""")
    conn.execute("""CREATE TABLE amendments (
        id INTEGER, act_refid TEXT, change_type TEXT,
        target TEXT, target_law TEXT, instruction TEXT, new_text TEXT)""")
    conn.executemany(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ('lov/2026-01-01-1', 'a.xml', 'Endr. gjeldende', 'A', '2026-02-01',
             '2026-02-01', '2026-01-01', 'Finansdepartementet', 'lov/1998-07-17-56', 'j1', ''),
            ('lov/2026-01-02-2', 'b.xml', 'Endr. opphevet', 'B', '2026-02-02',
             '2026-02-02', '2026-01-02', 'Landbruksdepartementet', 'lov/1981-05-29-38', 'j2', ''),
        ],
    )
    conn.executemany(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        [
            (1, 'lov/2026-01-01-1', 'change', '\u00a7 1', 'lov/1998-07-17-56', 'x', ''),
            (2, 'lov/2026-01-02-2', 'change', '\u00a7 2', 'lov/1981-05-29-38', 'x', ''),
        ],
    )
    conn.commit(); conn.close()

    lover = tmp_path / "lover"; lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "Regnskapsloven"\n---\n', encoding="utf-8")

    index = SiteIndex.build(str(tmp_path))
    index.attach_historie({"lov/1998-07-17-56": "historie/regnskapsloven.html"})
    index.attach_feeds({"laws": {"lov/1998-07-17-56": {"path": "feeds/lov-1998-07-17-56.xml"}},
                        "topics": {}, "ministries": {"Finansdepartementet": {"path": "feeds/dept-finansdepartementet.xml"}}})

    out = tmp_path / "aktivitet.html"
    generate_stats_page(db_path=str(db), output_path=str(out),
                        lover_dir=str(lover), forskrifter_dir=str(tmp_path / "forskrifter"),
                        site_index=index)
    page = out.read_text(encoding="utf-8")

    assert 'href="lover/lov-1998-07-17-56.html"' in page
    assert 'href="feeds/lov-1998-07-17-56.xml"' in page
    assert 'href="historie/regnskapsloven.html"' in page
    assert 'href="feeds/dept-finansdepartementet.xml"' in page
    # Repealed target: no local page anywhere, NLO fallback instead
    assert 'href="lover/lov-1981-05-29-38.html"' not in page
    assert 'lovdata.no/dokument/NLO/lov/1981-05-29-38' in page
    # Historical ministry without a feed gets a placeholder, not a dead slug
    assert 'dept-landbruksdepartementet.xml' not in page


def test_generate_stats_page_missing_db_returns_false(tmp_path):
    ok = generate_stats_page(
        db_path=str(tmp_path / "nope.db"),
        output_path=str(tmp_path / "out.html"),
    )
    assert ok is False
    assert not (tmp_path / "out.html").exists()
