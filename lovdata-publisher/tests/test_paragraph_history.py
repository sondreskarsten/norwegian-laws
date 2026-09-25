"""Tests for paragraph_history.py."""
import sqlite3
from pathlib import Path

from lovdata_publisher.paragraph_history import (
    _normalize_paragraph,
    _paragraph_slug,
    generate_paragraph_history_pages,
)


def test_normalize_paragraph_basic():
    assert _normalize_paragraph("§ 7-25") == "§ 7-25"
    assert _normalize_paragraph("§ 3-3a") == "§ 3-3a"
    assert _normalize_paragraph("§ 1-2a") == "§ 1-2a"


def test_normalize_paragraph_falls_back_to_instruction():
    assert _normalize_paragraph("kapittel 9", "§ 9-1 skal lyde:") == "§ 9-1"
    assert _normalize_paragraph("", "§ 3-1 første ledd skal lyde:") == "§ 3-1"


def test_normalize_paragraph_strips_first_letter_suffix_only():
    """'§ 3-1 første' must NOT match as '§ 3-1f'."""
    assert _normalize_paragraph("§ 3-1 første ledd") == "§ 3-1"


def test_paragraph_slug():
    assert _paragraph_slug("§ 7-25") == "para-7-25"
    assert _paragraph_slug("§ 3-3a") == "para-3-3a"
    assert _paragraph_slug("§ 1-2") == "para-1-2"


def test_generate_paragraph_history_writes_pages(tmp_path, monkeypatch):
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
            ('lov/2024-06-21-42', 'a.xml', 'Endr. regnskapsloven', 'Bærekraft',
             '2024-11-01', '2024-11-01', '2024-06-21', 'FIN', 'lov/1998-07-17-56',
             '2024-0042', ''),
            ('lov/2023-01-01-1', 'b.xml', 'Older endr.', 'Older',
             '2023-01-01', '2023-01-01', '2023-01-01', 'FIN', 'lov/1998-07-17-56',
             '2023-0001', ''),
        ],
    )
    conn.executemany(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        [
            (1, 'lov/2024-06-21-42', 'change', '§ 7-25', 'lov/1998-07-17-56',
             '§ 7-25 skal lyde:', 'Egenkapital ...'),
            (2, 'lov/2023-01-01-1', 'change', '§ 7-25', 'lov/1998-07-17-56',
             '§ 7-25 første ledd skal lyde:', 'Egenkapital ...'),
            (3, 'lov/2024-06-21-42', 'change', '§ 1-2a', 'lov/1998-07-17-56',
             '§ 1-2a skal lyde:', 'Plikt ...'),
        ],
    )
    conn.commit()
    conn.close()

    # Need a stub markdown file so title lookup works
    monkeypatch.chdir(tmp_path)
    lover = Path("lover")
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\nkorttittel: "Regnskapsloven – rskl"\ntittel: "Lov om årsregnskap"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "out"
    n, amended = generate_paragraph_history_pages(
        db_path=str(db),
        output_dir=str(out),
    )

    # Two distinct paragraphs (§ 7-25, § 1-2a) → 2 pages
    assert n == 2

    # amended map should reflect what's now available as history pages
    assert amended == {"lov/1998-07-17-56": {"§ 7-25", "§ 1-2a"}}

    page_725 = out / "lov-1998-07-17-56" / "para-7-25.html"
    assert page_725.exists()
    text = page_725.read_text(encoding="utf-8")
    assert "§ 7-25" in text
    assert "Regnskapsloven" in text
    # Both amendments to § 7-25 should be listed
    assert "2024-06-21" in text
    assert "2023-01-01" in text
    # Newest first
    assert text.index("2024-06-21") < text.index("2023-01-01")

    page_12a = out / "lov-1998-07-17-56" / "para-1-2a.html"
    assert page_12a.exists()


def test_generate_paragraph_history_handles_missing_db(tmp_path):
    n, amended = generate_paragraph_history_pages(
        db_path=str(tmp_path / "nope.db"),
        output_dir=str(tmp_path / "out"),
    )
    assert n == 0


def test_deferred_source_clause_is_not_presented_as_commencement(tmp_path, monkeypatch):
    """Regnskapsloven's 2005 act has a publication fallback, not an in-force date."""
    from lovdata_loader.store import init_db

    db = tmp_path / "amendments.db"
    with init_db(str(db)) as conn:
        conn.execute(
            """INSERT INTO amendment_acts
               (refid, title, date_in_force, date_in_force_resolved, is_deferred,
                date_published, ministry, journal_number)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("lov/2005-06-10-46", "Endringslov til regnskapsloven mv.",
             "Kongen bestemmer.", "2005-06-10", 1, "2005-06-10",
             "Finansdepartementet", "2005-0330"),
        )
        conn.execute(
            """INSERT INTO amendments
               (act_refid, target_law, target, instruction, new_text)
               VALUES (?, ?, ?, ?, ?)""",
            ("lov/2005-06-10-46", "lov/1998-07-17-56", "§ 7-25",
             "§ 7-25 nytt første ledd skal lyde:", "Opptjent egenkapital skal spesifiseres."),
        )
    conn.close()
    monkeypatch.chdir(tmp_path)
    generate_paragraph_history_pages(str(db), str(tmp_path / "out"))
    page = (tmp_path / "out/lov-1998-07-17-56/para-7-25.html").read_text(encoding="utf-8")
    assert "Publisert 2005-06-10" in page
    assert "Kongen bestemmer." in page
    assert "Dato er ikke avklart her" in page
    assert "ikrafttredelse 2005-06-10" not in page


def test_generate_paragraph_history_handles_missing_amendments_table(tmp_path):
    db = tmp_path / "amendments.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE amendment_acts (refid TEXT)")
    conn.close()
    n, amended = generate_paragraph_history_pages(
        db_path=str(db),
        output_dir=str(tmp_path / "out"),
    )
    assert n == 0


def test_normalize_paragraph_handles_prefixed_target():
    """Targets sometimes carry the law refid prefix, e.g. 'lov/1915-08-13-5/§217a'.
    The regex must still extract '§ 217a' (or the X-Y form when present)."""
    assert _normalize_paragraph("lov/1998-07-17-56/§1-2a") == "§ 1-2a"
    assert _normalize_paragraph("forskrift/2024-01-01-1/§2-3") == "§ 2-3"


def test_new_text_renders_in_collapsible_block(tmp_path, monkeypatch):
    """When an amendment row has new_text, the rendered page should include
    a <details>/Ny tekst block with that text."""
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
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2024-06-21-42', 'a.xml', 'Endr. regnskapsloven', 'Bærekraft',
         '2024-11-01', '2024-11-01', '2024-06-21', 'FIN', 'lov/1998-07-17-56',
         '2024-0042', ''),
    )
    conn.execute(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        (1, 'lov/2024-06-21-42', 'change', '§ 7-25', 'lov/1998-07-17-56',
         '§ 7-25 skal lyde:',
         'Egenkapital består av innskutt egenkapital og opptjent egenkapital.'),
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    lover = Path("lover")
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\nkorttittel: "Regnskapsloven"\ntittel: "Lov om årsregnskap"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "out"
    n, _ = generate_paragraph_history_pages(db_path=str(db), output_dir=str(out))
    assert n == 1

    page = (out / "lov-1998-07-17-56" / "para-7-25.html").read_text(encoding="utf-8")
    assert "<summary>Ny tekst</summary>" in page
    assert "Egenkapital består av innskutt egenkapital" in page
    # new_text block should not appear for amendments without new_text
    # (sanity check the optional-block path is genuinely conditional)


def test_no_new_text_block_when_missing(tmp_path, monkeypatch):
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
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2024-06-21-42', 'a.xml', 'Endr.', 'X',
         '2024-11-01', '2024-11-01', '2024-06-21', 'FIN', 'lov/1998-07-17-56',
         '2024-0042', ''),
    )
    conn.execute(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        (1, 'lov/2024-06-21-42', 'change', '§ 7-25', 'lov/1998-07-17-56',
         '§ 7-25 skal oppheves.', ''),  # empty new_text
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    lover = Path("lover")
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\nkorttittel: "X"\ntittel: "Y"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "out"
    generate_paragraph_history_pages(db_path=str(db), output_dir=str(out))
    page = (out / "lov-1998-07-17-56" / "para-7-25.html").read_text(encoding="utf-8")
    assert "<summary>Ny tekst</summary>" not in page


def test_current_paragraph_text_renders_from_markdown(tmp_path, monkeypatch):
    """The history page should include a 'Gjeldende tekst' section showing
    the current paragraph text extracted from the law markdown."""
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
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2024-06-21-42', 'a.xml', 'Endr.', 'X',
         '2024-11-01', '2024-11-01', '2024-06-21', 'FIN', 'lov/1998-07-17-56',
         '2024-0042', ''),
    )
    conn.execute(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        (1, 'lov/2024-06-21-42', 'change', '§ 7-25', 'lov/1998-07-17-56',
         '§ 7-25 skal lyde:', 'Egenkapital ...'),
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    lover = Path("lover")
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\n'
        'refid: "lov/1998-07-17-56"\n'
        'korttittel: "Regnskapsloven"\n'
        'tittel: "Lov om årsregnskap"\n'
        '---\n'
        '\n'
        '# Regnskapsloven\n'
        '\n'
        '##### § 7-25. Egenkapital\n'
        '\n'
        '(1) Opptjent egenkapital skal spesifiseres.\n'
        '\n'
        '(2) Det skal opplyses om endringer.\n'
        '\n'
        '##### § 7-26. Neste paragraf\n'
        '\n'
        '(1) Skal ikke vises på § 7-25 history page.\n',
        encoding="utf-8",
    )

    out = tmp_path / "out"
    generate_paragraph_history_pages(db_path=str(db), output_dir=str(out))
    page = (out / "lov-1998-07-17-56" / "para-7-25.html").read_text(encoding="utf-8")

    # Current text section present
    assert '<section class="current-text">' in page
    assert "Gjeldende tekst" in page
    assert "§ 7-25. Egenkapital" in page
    assert "Opptjent egenkapital skal spesifiseres" in page
    assert "Det skal opplyses om endringer" in page
    # Adjacent paragraph's text must NOT leak in
    assert "Skal ikke vises" not in page
    assert "§ 7-26" not in page.split("<section class=\"current-text\">")[1].split("</section>")[0]


def test_current_text_shows_repealed_notice_when_markdown_missing(tmp_path, monkeypatch):
    """If the law markdown is unavailable (law has been repealed/replaced),
    the history page shows a 'Lov/forskrift ikke lenger i kraft' notice
    instead of silently omitting the Gjeldende tekst section."""
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
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2024-06-21-42', 'a.xml', 'Endr.', 'X',
         '2024-11-01', '2024-11-01', '2024-06-21', 'FIN', 'lov/9999-12-31-99',
         '2024-0042', ''),
    )
    conn.execute(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        (1, 'lov/2024-06-21-42', 'change', '§ 1-1', 'lov/9999-12-31-99',
         '§ 1-1 skal lyde:', ''),
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    # NO markdown file for lov/9999-12-31-99 (simulating a repealed law)
    out = tmp_path / "out"
    n, _ = generate_paragraph_history_pages(db_path=str(db), output_dir=str(out))
    assert n == 1
    page = (out / "lov-9999-12-31-99" / "para-1-1.html").read_text(encoding="utf-8")
    # Repealed notice present, not silent omission
    assert '<section class="current-text repealed">' in page
    assert "ikke lenger i kraft" in page
    # But the amendments section is still there
    assert "Endringer" in page


def test_current_text_shows_removed_notice_when_paragraph_not_in_law(tmp_path, monkeypatch):
    """If the law markdown exists but the specific paragraph isn't found
    (renumbered or removed by a later amendment), the history page shows
    a 'paragraph finnes ikke i gjeldende tekst' notice."""
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
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2024-06-21-42', 'a.xml', 'X', 'X',
         '2024-11-01', '2024-11-01', '2024-06-21', 'FIN', 'lov/1998-07-17-56',
         '2024-0042', ''),
    )
    conn.execute(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        (1, 'lov/2024-06-21-42', 'remove', '§ 99-99', 'lov/1998-07-17-56',
         '§ 99-99 oppheves', ''),
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    lover = Path("lover")
    lover.mkdir()
    # Markdown exists but does NOT contain § 99-99
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "Regnskapsloven"\n---\n'
        '\n##### § 1-1. Bare denne paragrafen\n\nNoe tekst.\n',
        encoding="utf-8",
    )

    out = tmp_path / "out"
    generate_paragraph_history_pages(db_path=str(db), output_dir=str(out))
    page = (out / "lov-1998-07-17-56" / "para-99-99.html").read_text(encoding="utf-8")
    # Removed notice present
    assert '<section class="current-text removed">' in page
    assert "finnes ikke i gjeldende tekst" in page
    # Links to current law text
    assert "../../lover/lov-1998-07-17-56.html" in page


def test_neighbor_navigation_between_paragraph_pages(tmp_path, monkeypatch):
    """Each paragraph history page should link to prev/next paragraph in canonical
    (chapter, paragraph, letter) order."""
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
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2024-06-21-42', 'a.xml', 'X', 'X', '2024-11-01', '2024-11-01',
         '2024-06-21', 'FIN', 'lov/1998-07-17-56', '2024-0042', ''),
    )
    # Three paragraphs in non-canonical insert order to verify sorting
    conn.executemany(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        [
            (1, 'lov/2024-06-21-42', 'change', '§ 7-25', 'lov/1998-07-17-56', '§ 7-25', ''),
            (2, 'lov/2024-06-21-42', 'change', '§ 1-2', 'lov/1998-07-17-56', '§ 1-2', ''),
            (3, 'lov/2024-06-21-42', 'change', '§ 1-2a', 'lov/1998-07-17-56', '§ 1-2a', ''),
            (4, 'lov/2024-06-21-42', 'change', '§ 1-3', 'lov/1998-07-17-56', '§ 1-3', ''),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    lover = Path("lover")
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "X"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "out"
    generate_paragraph_history_pages(db_path=str(db), output_dir=str(out))

    # § 1-2a should be between § 1-2 and § 1-3 in canonical order
    page_12a = (out / "lov-1998-07-17-56" / "para-1-2a.html").read_text(encoding="utf-8")
    assert 'href="para-1-2.html"' in page_12a
    assert "← § 1-2" in page_12a
    assert 'href="para-1-3.html"' in page_12a
    assert "§ 1-3 →" in page_12a

    # § 1-2 (first) should have no prev, only next
    page_12 = (out / "lov-1998-07-17-56" / "para-1-2.html").read_text(encoding="utf-8")
    assert "prev-para" not in page_12  # No prev link
    assert "§ 1-2a →" in page_12

    # § 7-25 (last) should have no next
    page_725 = (out / "lov-1998-07-17-56" / "para-7-25.html").read_text(encoding="utf-8")
    assert "← § 1-3" in page_725
    assert "next-para" not in page_725  # No next link


def test_current_text_extracts_h6_paragraph_headers(tmp_path, monkeypatch):
    """Paragraph headers can be at H2-H6 depending on the law's structure.
    Caught by Playwright stress test 2026-05-20: folketrygdloven uses H6 for
    paragraphs under H4 sections, and the regex only allowed H3-H5."""
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
    conn.execute(
        "INSERT INTO amendment_acts VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ('lov/2024-06-21-42', 'a.xml', 'X', 'X', '2024-01-01', '2024-01-01',
         '2024-01-01', 'FIN', 'lov/1997-02-28-19', '2024-0042', ''),
    )
    conn.execute(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        (1, 'lov/2024-06-21-42', 'change', '§ 3-18', 'lov/1997-02-28-19',
         '§ 3-18', ''),
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    lover = Path("lover")
    lover.mkdir()
    # Folketrygdloven-style structure: H4 section, H6 paragraphs
    (lover / "lov-1997-02-28-19.md").write_text(
        '---\nrefid: "lov/1997-02-28-19"\ntittel: "Folketrygdloven"\n---\n'
        '\n'
        '# Folketrygdloven\n'
        '\n'
        '#### Kap. 3 Beregningsregler\n'
        '\n'
        '###### § 3-18. Beregning av alderspensjon ved yrkesskade\n'
        '\n'
        '(1) Bestemmelsene gjelder uavhengig av...\n'
        '\n'
        '###### § 3-19. Neste paragraf\n'
        '\n'
        '(1) Skal ikke vises på § 3-18 page.\n',
        encoding="utf-8",
    )

    out = tmp_path / "out"
    generate_paragraph_history_pages(db_path=str(db), output_dir=str(out))
    page = (out / "lov-1997-02-28-19" / "para-3-18.html").read_text(encoding="utf-8")

    assert '<section class="current-text">' in page
    assert "§ 3-18. Beregning av alderspensjon ved yrkesskade" in page
    assert "Bestemmelsene gjelder uavhengig av" in page
    # Adjacent paragraph's text must NOT leak in
    assert "Skal ikke vises" not in page
