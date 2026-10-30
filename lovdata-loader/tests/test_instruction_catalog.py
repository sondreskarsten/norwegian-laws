import json
import sqlite3

import pytest

from lovdata_loader.instruction_catalog import InstructionCatalog, load_catalog, main, normalize


@pytest.fixture(scope="module")
def catalog():
    return InstructionCatalog()


@pytest.mark.parametrize("text, expected", [
    ("§ 3 skal lyde:", "replace_text"),
    ("§ 1-2 første ledd nr. 4 annet strekpunkt skal lyde:", "replace_text"),
    ("I lov 17. juni 2005 nr. 90 skal § 3 lyde:", "replace_text"),
    ("§ 2 andre ledd bokstav a (endret) skal lydeInntil 5 000 tonn", "replace_text"),
    ("Ny § 4 a skal lyde:", "new_provision"),
    ("§ 5 nytt tredje ledd skal lyde:", "new_provision"),
    ("§ 12 oppheves.", "repeal"),
    ("Følgjande lov vert opphevd:", "repeal"),
    ("Gjeldende § 5 av dykkesertifikatoppheves.", "repeal"),
    ("Punktum etter «jf.» i § 4 bokstav k fjernes.", "repeal"),
    ("Nåværende § 4 blir ny § 5.", "renumber"),
    ("Nåværende tredje og fjerde ledd blir fjerde og nytt femte ledd.", "renumber"),
    ("Nåværende bokstaver o) til w) blir p) til x).", "renumber"),
    ("Nåværende kapittel IVog Vblir kapittel IIIog IV.", "renumber"),
    ("§ 5 flyttes til kapittel 2 og blir ny § 2-4.", "move"),
    ("I § 4 endres «departementet» til «Kongen».", "word_substitution"),
    ("I § 3 erstattes henvisningen til «direktiv 1» av en henvisning til «direktiv 2».", "word_substitution"),
    ("I vedlegg XV kapittel 3 byttes PDF-filen ut med vedlagte PDF-fil:", "word_substitution"),
    ("I § 3 tilføyes nytt annet punktum:", "insert"),
    ("Mellom kapittel 4 og 5 settes følgende inn:", "insert"),
    ("Loven trer i kraft 1. juli 2026.", "commencement"),
    ("Delt ikraftsetting av lov 20. juni 2025 nr. 105.", "commencement"),
    ("I lov 17. juni 2005 nr. 90 om mekling (tvisteloven) gjøres følgende endringer:", "preamble"),
    ("Endring i følgjande lov:", "preamble"),
    ("I bestemmelser 12. desember 2003 nr. 1938 om økonomistyring i staten er det gjort en rekke endringer:", "preamble"),
    ("Kapittel 7. Tilsyn", "structural_title"),
    ("§ 4", "structural_title"),
    ("§ 3 første ledd bokstav d:", "structural_title"),
    ("Kongens myndighet etter kommuneloven § 3 nr. 3 delegeres til departementet.", "delegation"),
    ("Med hjemmel i lov 17. desember 1976 nr. 100 § 3 fastsettes forsinkelsesrenten til 8,75 prosent p.a.", "decision_text"),
    ("§ 1-3, § 1-10, § 2-7, kapittel 2, kapittel 4 og kapittel 7.", "target_list"),
])
def test_catalogued_wordings_are_classified(catalog, text, expected):
    assert expected in catalog.classify(text)


def test_target_marker_is_not_mistaken_for_a_replacement(catalog):
    assert catalog.classify("§ 3 første ledd skal lyde:") == ["replace_text"]
    assert "structural_title" not in catalog.classify("§ 3 første ledd skal lyde:")


def test_instruction_like_requires_a_target_and_an_instruction_ending(catalog):
    assert catalog.instruction_like("§ 4 annet ledd skal annulleres.")
    assert not catalog.instruction_like("Agder fylke")
    assert not catalog.instruction_like("Loven gjelder " * 40 + "§ 1.")


def test_normalize_collapses_references_numbers_and_quotes():
    assert normalize("3. I lov 17. juni 2005 nr. 90 § 4-2 endres «a» til «b».") == "I LAWREF §N endres «…» til «…»."
    assert normalize("Nåværende § 12 a blir ny § 13.") == "Nåværende §N blir ny §N."


def test_report_lists_only_uncatalogued_instruction_like_forms(catalog):
    rows = [
        ("lov/2026-01-01-1", "change", "§ 3 skal lyde:"),
        ("lov/2026-01-01-1", "unknown", "§ 4 annet ledd skal annulleres."),
        ("lov/2026-01-01-2", "unknown", "§ 7 skal annulleres."),
        ("lov/2026-01-01-2", "unknown", "Agder fylke"),
    ]
    report = catalog.report(rows)
    assert report["instructions"] == 4
    assert report["by_operation"]["replace_text"] == 1
    assert report["not_instruction_like"] == 1
    assert [f["form"] for f in report["unknown_forms"]] == ["§N annet ledd skal annulleres.", "§N skal annulleres."]
    assert report["unknown_forms"][0]["examples"] == [
        {"act": "lov/2026-01-01-1", "instruction": "§ 4 annet ledd skal annulleres."}
    ]


def test_reviewed_non_instructions_are_not_reported():
    data = load_catalog()
    data["reviewed_non_instructions"] = ["§N skal annulleres."]
    report = InstructionCatalog(data).report([("lov/2026-01-01-2", "unknown", "§ 7 skal annulleres.")])
    assert report["unknown_forms"] == []
    assert report["reviewed_non_instructions"] == 1


def test_every_catalogue_example_matches_its_own_operation(catalog):
    for operation in catalog.catalog["operations"]:
        for example in operation["examples"]:
            assert operation["id"] in catalog.classify(example), (operation["id"], example)


def test_cli_reads_a_snapshot_database_and_fails_on_unknown_forms(tmp_path, capsys):
    db = tmp_path / "amendments.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE amendments (id INTEGER PRIMARY KEY, act_refid TEXT, change_type TEXT, target TEXT, target_law TEXT, instruction TEXT, new_text TEXT)")
    conn.executemany("INSERT INTO amendments (act_refid, change_type, instruction) VALUES (?, ?, ?)", [
        ("lov/2026-01-01-1", "change", "§ 3 skal lyde:"),
        ("lov/2026-01-01-1", "unknown", "§ 4 skal annulleres."),
    ])
    conn.commit()
    conn.close()
    out = tmp_path / "forms.json"
    assert main(["--db", str(db), "--output", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["unknown_forms"][0]["form"] == "§N skal annulleres."
    assert main(["--db", str(db), "--output", str(out), "--fail-on-unknown"]) == 1
