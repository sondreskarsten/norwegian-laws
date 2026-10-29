from norwegian_laws_mcp.markdown import get_section, normalize_section_key, parse_document

from conftest import AKSJELOVEN, LAW


def test_front_matter_and_headings():
    doc = parse_document(LAW)
    assert doc.meta["refid"] == "lov/2025-06-20-105"
    assert doc.title.startswith("Lov om Enhetsregisteret")
    keys = [h.section for h in doc.headings if h.section]
    assert keys == ["1-1", "1-4", "4-7", "4-7a"]
    chapters = [h.chapter for h in doc.headings if h.chapter]
    assert chapters == ["1", "4"]


def test_section_bounds_stop_at_next_section_or_chapter():
    doc = parse_document(LAW)
    sec = get_section(doc, "§ 4-7")
    assert sec.heading.text == "§ 4-7. Opplysninger om underenheter"
    assert "organisasjonsnummer" in sec.text
    assert "Særregel" not in sec.text
    sec = get_section(doc, "1-4")
    assert "registreringsenhet" in sec.text
    assert "Kapittel 4" not in sec.text
    assert get_section(doc, "§ 9-9") is None


def test_chapter_and_lettered_sections():
    doc = parse_document(LAW)
    chap = get_section(doc, "kapittel 4")
    assert "§ 4-7 a" in chap.text
    assert get_section(doc, "§ 4-7 a").heading.section == "4-7a"
    doc = parse_document(AKSJELOVEN)
    assert get_section(doc, "1-5 a").heading.text == "§ 1-5 a. Møte"
    assert get_section(doc, "§ 1-5").heading.text == "§ 1-5. Nærstående"


def test_normalize_section_key():
    assert normalize_section_key("§ 4-7.") == "4-7"
    assert normalize_section_key("§4-7 a") == "4-7a"
    assert normalize_section_key("12") == "12"
