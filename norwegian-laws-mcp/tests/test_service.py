import pytest

from norwegian_laws_mcp import render
from norwegian_laws_mcp.errors import ResolveError


def test_get_document_section_and_paging(service):
    res = service.get_document("enhetsregisterloven", "§ 4-7", "text", 0, 20000)
    assert res["section"]["heading"] == "§ 4-7. Opplysninger om underenheter"
    assert "registerføreren" in res["text"]
    paged = service.get_document("enhetsregisterloven", None, "text", 0, 500)
    assert paged["truncated"] and paged["next_offset"] == 500
    outline = service.get_document("asl", None, "outline", 0, 500)
    assert any(h["section"] == "1-5a" for h in outline["outline"])
    meta = service.get_document("asl", None, "metadata", 0, 500)
    assert meta["front_matter"]["korttittel"] == "Aksjeloven – asl"
    with pytest.raises(ResolveError):
        service.get_document("asl", "§ 77", "text", 0, 500)


def test_search_text_groups_by_document(service):
    res = service.search_text("underenhet", None, None, False, False, 10, 5)
    paths = [r["path"] for r in res["results"]]
    assert "lover/lov-2025-06-20-105.md" in paths
    assert "forskrifter/forskrift-2025-08-06-1610.md" in paths
    hit = next(r for r in res["results"] if r["refid"] == "lov/2025-06-20-105")
    assert hit["hits"][0]["section"].startswith("§ 4-7")
    only_lov = service.search_text("underenhet", "lov", None, False, False, 10, 5)
    assert all(r["kind"] == "lov" for r in only_lov["results"])
    regex = service.search_text(r"organisasjonsnummer av \w+", None, None, True, False, 10, 5)
    assert regex["total_hits"] == 1
    assert "Underenhet" in render.search_text(res) or "underenhet" in render.search_text(res)


def test_find_definition_ranks_definition_phrase_first(service):
    res = service.find_definition("underenheter", None, None, 10)
    assert res["stem"] == "underenhet"
    top = res["definitions"][0]
    assert top["refid"] == "forskrift/2025-08-06-1610"
    assert top["why"].startswith("definition phrase")
    assert any(d["refid"] == "lov/2025-06-20-105" and d["section"].startswith("§ 4-7") for d in res["definitions"])
    text = render.definitions(res)
    assert "Med underenhet menes" in text
    nothing = service.find_definition("sjiraff", None, None, 10)
    assert nothing["definitions"] == [] and "No definition-like" in render.definitions(nothing)


def test_recent_changes_window_and_filters(service):
    res = service.recent_changes("2026-02-15", "2026-03-10", None, None, None, True, 50)
    assert [c["sha"][:4] for c in res["commits"]] and len(res["commits"]) == 1
    statuses = {d["path"]: d["status"] for d in res["text_documents"]}
    assert statuses["lover/lov-2025-06-20-105.md"] == "modified"
    assert statuses["forskrifter/forskrift-2026-01-01-1.md"] == "added"
    everything = service.recent_changes("2025-12-01", None, None, None, None, True, 50)
    assert len(everything["commits"]) == 5
    assert any(d["path"] == "historie/aksjeloven.md" for d in everything["amendment_record_files"])
    filtered = service.recent_changes("2025-12-01", None, None, None, "enhetsregister", True, 50)
    assert {d["refid"] for d in filtered["text_documents"]} >= {"lov/2025-06-20-105", "forskrift/2025-08-06-1610"}
    assert all(d["refid"] != "lov/1997-06-13-44" for d in filtered["text_documents"])
    none = service.recent_changes("2026-04-02", None, None, None, None, True, 50)
    assert none["commits"] == [] and "No commits" in render.recent_changes(none)
    assert "modified" in render.recent_changes(res)


def test_document_history_and_diff(service):
    hist = service.document_history("enhetsregisterloven", None, None, 10)
    assert len(hist["commits"]) == 2
    assert hist["commits"][0]["added"] == 1 and hist["commits"][0]["deleted"] == 1
    diff = service.diff_document("enhetsregisterloven", "2026-02-15", "HEAD", None, 1, 20000)
    assert diff["changed"] and "+(2) Hver underenhet" in diff["diff"]
    sec = service.diff_document("enhetsregisterloven", "HEAD~3", "HEAD", "§ 4-7", 1, 20000)
    assert sec["changed"] and "registerføreren" in sec["diff"]
    unchanged = service.diff_document("enhetsregisterloven", "HEAD~3", "HEAD", "§ 1-1", 1, 20000)
    assert not unchanged["changed"]
    before = service.diff_document("enhetsregisterforskriften", "HEAD~4", "HEAD", None, 1, 20000)
    assert not before["from"]["existed"] and before["to"]["existed"] and before["changed"]
    assert "```diff" in render.diff(diff)


def test_blame_section(service):
    res = service.blame_section("enhetsregisterloven", "§ 4-7")
    dates = {r["last_changed"] for r in res["runs"]}
    assert dates == {"2026-01-01", "2026-03-01"}
    changed = next(r for r in res["runs"] if r["last_changed"] == "2026-03-01")
    assert changed["first_line"].startswith("(2) Hver underenhet")


def test_amendment_records(service):
    res = service.amendment_records("asl", None, None, 50)
    assert res["total"] == 3
    assert res["records"][0]["date"] == "2021-05-05"
    sec = service.amendment_records("aksjeloven", "§ 1-5", None, 50)
    assert sec["total"] == 2 and sec["records"][0]["amending_act"] == "lov/2019-12-20-100"
    since = service.amendment_records("aksjeloven", None, "2020-01-01", 50)
    assert since["total"] == 2
    none = service.amendment_records("enhetsregisterloven", None, None, 50)
    assert none["records"] == [] and "No parsed amendment records" in render.amendment_records(none)
    assert "skal lyde" in render.amendment_records(res)


def test_related_documents(service):
    res = service.related_documents("enhetsregisterloven", None, 10)
    assert res["related"][0]["refid"] == "forskrift/2025-08-06-1610"
    assert "20. juni 2025 nr. 105" in res["related"][0]["matched"]
    assert "enhetsregisterloven" in res["related"][0]["matched"]


def test_repo_status(service):
    res = service.repo_status()
    assert res["documents"] == {"total": 4, "lover": 2, "forskrifter": 2}
    assert res["last_lovdata_update_commit"]["subject"].startswith("Oppdater")
    assert res["commits_in_history"] == 5
    assert "Repository status" in render.status(res)


def test_search_documents_render(service):
    items = service.search_documents("enhetsregister", None, 10, True)
    assert items[0]["refid"] == "lov/2025-06-20-105"
    assert "Enhetsregisterloven" in render.search_documents("enhetsregister", items)


def test_dates_before_history_are_clamped_and_labelled(service):
    res = service.diff_document("enhetsregisterloven", "2020-01-01", "HEAD", "§ 4-7", 1, 20000)
    assert res["from"]["clamped_to_first_commit"] and res["from"]["requested"] == "2020-01-01"
    assert res["from"]["date"].startswith("2026-01-01")
    assert any("before the first commit" in n for n in res["limitations"])
    text = render.diff(res)
    assert "requested '2020-01-01'" in text and "Data coverage and limits" in text
    future = service.diff_document("enhetsregisterloven", "HEAD~1", "2030-01-01", None, 1, 20000)
    assert future["to"]["clamped_to_head"]
    same = service.diff_document("enhetsregisterloven", "2026-04-01", "HEAD", None, 1, 20000)
    assert not same["changed"] and any("same commit" in n for n in same["limitations"])


def test_window_limitations_and_commit_kinds(service):
    res = service.recent_changes("2 years ago", None, None, None, None, True, 50)
    assert any("before or at the first commit" in n for n in res["limitations"])
    assert {c["kind"] for c in res["commits"]} == {"source-update", "pipeline"}
    assert res["coverage"]["first_commit"]["date"].startswith("2026-01-01")
    statuses = {d["path"]: d["status"] for d in res["text_documents"]}
    assert statuses["lover/lov-2025-06-20-105.md"] == "added → modified"
    empty = service.recent_changes("2026-04-02", None, None, None, None, True, 50)
    assert any("'No change'" in n for n in empty["limitations"])
    assert "[pipeline]" in render.recent_changes(res)
    hist = service.document_history("enhetsregisterloven", None, None, 10)
    assert any("first appears in the repository on 2026-01-01" in n for n in hist["limitations"])
    assert "Data coverage and limits" in render.document_history(hist)
    blame = service.blame_section("enhetsregisterloven", "§ 4-7")
    assert any("floor at 2026-01-01" in n for n in blame["limitations"])


def test_amendment_records_report_coverage_and_inline_notes(service, fixture_repo):
    res = service.amendment_records("asl", None, None, 50)
    assert res["earliest_record"] == "2013-06-14" and res["latest_record"] == "2021-05-05"
    assert res["lovtidend_from_year"] == 2001
    assert any("new wording only" in n for n in res["limitations"])
    text = render.amendment_records(res)
    assert "file covers 2013-06-14 to 2021-05-05" in text and "Data coverage and limits" in text
    sec = service.amendment_records("enhetsregisterloven", "§ 1-1", None, 50)
    assert sec["records"] == [] and "Data coverage and limits" in render.amendment_records(sec)


def test_inline_amendment_notes_are_extracted():
    from norwegian_laws_mcp.history import inline_amendment_notes
    lines = ["#### § 3-1. Plikt", "", "Tekst.", "", "*Endret ved lover 10 des 2004 nr. 81 (ikr. 1 jan 2005), 30 juni 2006 nr. 38.*", "*Ikke en note*"]
    assert inline_amendment_notes(lines) == ["Endret ved lover 10 des 2004 nr. 81 (ikr. 1 jan 2005), 30 juni 2006 nr. 38."]


def test_removed_document_resolves_with_last_text_and_removal_label(service):
    res = service.get_document("lov/1985-06-21-78", "§ 8-3", "text", 0, 5000)
    assert res["document"]["removed_from_corpus"] == "2026-04-01"
    assert "navnevern" in res["text"]
    assert any("no longer in Lovdata's current corpus" in n for n in res["provenance"]["limitations"])
    text = render.document(res)
    assert "REMOVED from the current corpus 2026-04-01" in text and "last observed version" in text
    assert service.resolve("Foretaksregisterloven – fregl").refid == "lov/1985-06-21-78"
    items = service.search_documents("registrering av foretak", None, 5, True, include_removed=True)
    assert any(i["refid"] == "lov/1985-06-21-78" and i.get("removed_from_corpus") for i in items)
    assert not any(i["refid"] == "lov/1985-06-21-78" for i in service.search_documents("registrering av foretak", None, 5, True))


def test_dated_read_returns_text_as_committed(service):
    res = service.get_document("enhetsregisterloven", "§ 4-7", "text", 0, 5000, at="2026-02-15")
    assert "registerføreren" not in res["text"]
    assert res["provenance"]["source"].startswith("observed consolidated text")
    assert any("not the text legally in force" in n for n in res["provenance"]["limitations"])
    with pytest.raises(ResolveError, match="was not in the corpus"):
        service.get_document("enhetsregisterforskriften", None, "text", 0, 5000, at="2026-01-15")


def test_repo_status_counts_removed_and_states_scope(service):
    res = service.repo_status()
    assert res["removed_documents"] == 1
    assert "Stortingsvedtak" in res["corpus_scope"]
    assert "removed from the corpus" in render.status(res)
