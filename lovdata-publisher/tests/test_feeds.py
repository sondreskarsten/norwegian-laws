"""Tests for the per-law/topic/ministry feed generator."""
import sqlite3
import tempfile
from pathlib import Path

import pytest

from lovdata_publisher.feeds import (
    _slug,
    _filepath_for,
    _scan_frontmatter,
    generate_per_law_feeds,
)


def test_slug_handles_norwegian_chars():
    assert _slug("Skatterett") == "skatterett"
    assert _slug("Arbeids- og inkluderingsdepartementet") == "arbeids--og-inkluderingsdepartementet"
    assert _slug("Bank, finans og regnskapsrett") == "bank-finans-og-regnskapsrett"
    assert _slug("Næringsliv") == "naeringsliv"
    assert _slug("Sjøfart") == "sjofart"


def test_filepath_for_lov():
    assert _filepath_for("lov/1998-07-17-56") == "/lover/lov-1998-07-17-56.html"


def test_filepath_for_forskrift():
    assert _filepath_for("forskrift/2024-06-21-1166") == "/forskrifter/forskrift-2024-06-21-1166.html"


def test_filepath_for_unknown_returns_empty():
    assert _filepath_for("foobar") == ""


def test_scan_frontmatter_reads_yaml(tmp_path):
    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\n'
        'tittel: "Lov om årsregnskap m.v. (regnskapsloven)"\n'
        'korttittel: "Regnskapsloven – rskl"\n'
        'refid: "lov/1998-07-17-56"\n'
        'departement: "Finansdepartementet"\n'
        'rettsomrade: "Bank, finans og regnskapsrett>Regnskap"\n'
        '---\n\n# Body\n',
        encoding="utf-8",
    )
    result = _scan_frontmatter(str(lover), None)
    assert "lov/1998-07-17-56" in result
    meta = result["lov/1998-07-17-56"]
    assert meta["korttittel"] == "Regnskapsloven – rskl"
    assert meta["departement"] == "Finansdepartementet"


def test_generate_per_law_feeds_writes_xml(tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    db = sqlite3.connect(str(snapshot / "amendments.db"))
    db.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    db.execute("""
        INSERT INTO amendment_acts VALUES
        ('lov/2024-06-21-42', 'nl.xml', 'Endringer i regnskapsloven',
         'Bærekraftsrapportering', '2024-11-01', '2024-11-01',
         '2024-06-21', 'FIN', 'lov/1998-07-17-56', '2024-0042', '')
    """)
    db.commit()
    db.close()

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\n'
        'tittel: "Lov om årsregnskap m.v. (regnskapsloven)"\n'
        'korttittel: "Regnskapsloven – rskl"\n'
        'refid: "lov/1998-07-17-56"\n'
        'departement: "Finansdepartementet"\n'
        'rettsomrade: "Bank, finans og regnskapsrett>Regnskap"\n'
        '---\n\n# Body\n',
        encoding="utf-8",
    )

    out = tmp_path / "feeds_out"
    manifest = generate_per_law_feeds(
        snapshot_dir=str(snapshot),
        lover_dir=str(lover),
        forskrifter_dir=None,
        output_dir=str(out),
    )

    assert "lov/1998-07-17-56" in manifest["laws"]
    feed_path = out / "lov-1998-07-17-56.xml"
    assert feed_path.exists()
    feed_text = feed_path.read_text(encoding="utf-8")
    assert "<feed" in feed_text
    assert "<entry>" in feed_text
    assert "lov/2024-06-21-42" in feed_text
    assert "Bærekraftsrapportering" in feed_text

    # Topic feed
    topic_feed = out / "topic-bank-finans-og-regnskapsrett.xml"
    assert topic_feed.exists()
    assert "Bank, finans og regnskapsrett" in topic_feed.read_text(encoding="utf-8")

    # Ministry feed
    dept_feed = out / "dept-finansdepartementet.xml"
    assert dept_feed.exists()


def test_generate_handles_missing_db(tmp_path):
    snapshot = tmp_path / "no_snapshot"
    out = tmp_path / "feeds_out"
    manifest = generate_per_law_feeds(
        snapshot_dir=str(snapshot),
        lover_dir=str(tmp_path / "lover"),
        forskrifter_dir=None,
        output_dir=str(out),
    )
    assert manifest == {}


def test_generate_skips_laws_with_no_amendments(tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    db = sqlite3.connect(str(snapshot / "amendments.db"))
    db.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    db.commit()
    db.close()

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "X"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "feeds_out"
    manifest = generate_per_law_feeds(
        snapshot_dir=str(snapshot),
        lover_dir=str(lover),
        forskrifter_dir=None,
        output_dir=str(out),
    )
    assert manifest["laws"] == {}
    assert not (out / "lov-1998-07-17-56.xml").exists()


def test_atom_feed_is_valid_xml(tmp_path):
    """Generated feed must be parseable as XML."""
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    db = sqlite3.connect(str(snapshot / "amendments.db"))
    db.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    # Include special chars that need escaping
    db.execute("""
        INSERT INTO amendment_acts VALUES
        ('lov/2024-06-21-42', 'nl.xml',
         'Endringer i lov med <special> & "chars"', 'Test',
         '2024-11-01', '2024-11-01',
         '2024-06-21', 'FIN', 'lov/1998-07-17-56', '2024-0042', '')
    """)
    db.commit()
    db.close()

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "Regnskapsloven"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "feeds_out"
    generate_per_law_feeds(
        snapshot_dir=str(snapshot),
        lover_dir=str(lover),
        forskrifter_dir=None,
        output_dir=str(out),
    )

    import xml.etree.ElementTree as ET
    feed_path = out / "lov-1998-07-17-56.xml"
    tree = ET.parse(feed_path)
    root = tree.getroot()
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    assert root.tag == "{http://www.w3.org/2005/Atom}feed"
    entries = root.findall("atom:entry", ns)
    assert len(entries) == 1


def test_normalize_paragraph_ref_extracts_from_target():
    from lovdata_publisher.feeds import _normalize_paragraph_ref
    assert _normalize_paragraph_ref("§ 7-1", "") == "§ 7-1"
    assert _normalize_paragraph_ref("§ 7-25", "") == "§ 7-25"
    assert _normalize_paragraph_ref("§ 3-3a", "") == "§ 3-3a"


def test_normalize_paragraph_ref_falls_back_to_instruction():
    from lovdata_publisher.feeds import _normalize_paragraph_ref
    assert _normalize_paragraph_ref("", "§ 3-1 første ledd skal lyde:") == "§ 3-1"
    assert _normalize_paragraph_ref("kapittel 9", "§ 9-1 skal lyde:") == "§ 9-1"


def test_normalize_paragraph_ref_returns_empty_for_chapter():
    from lovdata_publisher.feeds import _normalize_paragraph_ref
    assert _normalize_paragraph_ref("kapittel 9", "Nytt kapittel skal lyde:") == ""
    assert _normalize_paragraph_ref("", "Loven oppheves.") == ""


def test_feed_with_amendments_table_includes_categories(tmp_path):
    """When amendments table exists, entries should include <category> per paragraph."""
    import sqlite3
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    db = sqlite3.connect(str(snapshot / "amendments.db"))
    db.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    db.execute("""
        CREATE TABLE amendments (
            id INTEGER, act_refid TEXT, change_type TEXT,
            target TEXT, target_law TEXT, instruction TEXT, new_text TEXT
        )
    """)
    db.execute("""
        INSERT INTO amendment_acts VALUES
        ('lov/2024-06-21-42', 'nl.xml', 'Endringer i regnskapsloven',
         'Bærekraftsrapportering', '2024-11-01', '2024-11-01',
         '2024-06-21', 'FIN', 'lov/1998-07-17-56', '2024-0042', '')
    """)
    db.executemany(
        "INSERT INTO amendments VALUES (?,?,?,?,?,?,?)",
        [
            (1, 'lov/2024-06-21-42', 'change', '§ 1-2a', 'lov/1998-07-17-56',
             '§ 1-2a skal lyde:', 'Bestemmelsene ...'),
            (2, 'lov/2024-06-21-42', 'change', '§ 2-3', 'lov/1998-07-17-56',
             '§ 2-3 skal lyde:', 'Store foretak ...'),
        ],
    )
    db.commit()
    db.close()

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "Regnskapsloven"\n---\n',
        encoding="utf-8",
    )

    out = tmp_path / "feeds"
    generate_per_law_feeds(
        snapshot_dir=str(snapshot),
        lover_dir=str(lover),
        forskrifter_dir=None,
        output_dir=str(out),
    )

    feed_text = (out / "lov-1998-07-17-56.xml").read_text(encoding="utf-8")
    # Atom <category> elements should appear for each amended paragraph
    assert '<category term="§ 1-2a"' in feed_text
    assert '<category term="§ 2-3"' in feed_text
    assert "Berørte paragrafer" in feed_text


def test_feed_link_includes_paragraph_anchor_when_single_paragraph(tmp_path):
    """When an amendment touches exactly one paragraph, the entry link
    should deep-link to that paragraph's anchor on the law page."""
    import sqlite3
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    db = sqlite3.connect(str(snapshot / "amendments.db"))
    db.execute("""
        CREATE TABLE amendment_acts (
            refid TEXT, filename TEXT, title TEXT, short_title TEXT,
            date_in_force TEXT, date_in_force_resolved TEXT,
            date_published TEXT, ministry TEXT, changes_to TEXT,
            journal_number TEXT, misc_info TEXT
        )
    """)
    db.execute("""
        CREATE TABLE amendments (
            id INTEGER, act_refid TEXT, change_type TEXT,
            target TEXT, target_law TEXT, instruction TEXT, new_text TEXT
        )
    """)
    db.execute("""
        INSERT INTO amendment_acts VALUES
        ('lov/2024-06-21-42', 'nl.xml', 'Endringer i regnskapsloven',
         'Bærekraftsrapportering', '2024-11-01', '2024-11-01',
         '2024-06-21', 'FIN', 'lov/1998-07-17-56', '2024-0042', '')
    """)
    db.execute("""
        INSERT INTO amendments VALUES (
            1, 'lov/2024-06-21-42', 'change', '§ 1-2a', 'lov/1998-07-17-56',
            '§ 1-2a skal lyde:', 'Bestemmelsene ...'
        )
    """)
    db.commit()
    db.close()

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\nrefid: "lov/1998-07-17-56"\ntittel: "Regnskapsloven"\n---\n\n'
        '# Regnskapsloven\n\n'
        '#### § 1-1. Lovens virkeområde\n\n(1) Loven gjelder ...\n\n'
        '#### § 1-2a. Regnskapspliktige med plikt til å utarbeide bærekraftsrapportering\n\n(1) ...\n',
        encoding="utf-8",
    )

    out = tmp_path / "feeds"
    generate_per_law_feeds(
        snapshot_dir=str(snapshot),
        lover_dir=str(lover),
        forskrifter_dir=None,
        output_dir=str(out),
    )

    feed_text = (out / "lov-1998-07-17-56.xml").read_text(encoding="utf-8")
    # Link should include the paragraph anchor
    assert "lov-1998-07-17-56.html#1-2a" in feed_text


def test_paragraph_anchor_map_uses_only_the_heading_line(tmp_path):
    """A bare '#### § 24-2' heading followed by a paragraph used to get an
    anchor made of the next line's text, which the rendered page never has."""
    from lovdata_publisher.feeds import _build_paragraph_anchor_map
    md = tmp_path / "lov-1989-06-16-69.md"
    md.write_text(
        "#### § 24-1. Ikrafttredelse\n\nTekst.\n\n#### § 24-2\n\n"
        "Loven gjelder fullt ut for forsikringsavtaler som blir inngått etter lovens ikrafttredelse.\n\n"
        "##### § 24-3a. Overgang\n\nMer.\n", encoding="utf-8")
    anchors = _build_paragraph_anchor_map(md)
    assert anchors["§ 24-1"] == "24-1-ikrafttredelse"
    assert anchors["§ 24-2"] == "24-2"
    assert anchors["§ 24-3a"] == "24-3a-overgang"
