"""Recovery links come from verified reader copies, never inferred repeal dates."""
import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from lovdata_publisher.not_found import HISTORY_ARCHIVE_COMMIT, _prior_readers, generate_not_found_page


PARENT = "98d4e4d5d43d22384cf9c1862816bf8f57122c33"
EXIT = "b8e08232422013a96c38cdfc074618c979777458"


def config(page):
    return json.loads(re.search(r'<script id="recovery-config" type="application/json">(.*?)</script>',
                               page, flags=re.DOTALL).group(1))


def test_all_105_reader_copies_use_exact_original_parent_and_unknown_status(tmp_path):
    page = Path(generate_not_found_page(str(tmp_path), history_archive_commit=None)).read_text(encoding="utf-8")
    copies = config(page)["priorReaders"]
    assert len(copies) == 105
    assert sum(refid.startswith("lov/") for refid in copies) == 61
    assert sum(refid.startswith("forskrift/") for refid in copies) == 44
    for refid, row in copies.items():
        kind, identifier = refid.split("/")
        folder = "lover" if kind == "lov" else "forskrifter"
        assert row["copy"] == f"https://github.com/sondreskarsten/norwegian-laws/blob/{PARENT}/{folder}/{kind}-{identifier}.md"
        assert "archive" not in row and "provenance" not in row
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
    assert "Avledet tekst · Rettslig status ukjent" in page
    assert "eventuell opphevelse er ikke dokumentert her" in page
    assert "2026-07-21" not in page
    assert "atom.xml" not in page and "feed.xml" not in page


def test_viltloven_and_removed_regulation_have_verified_copy_identity():
    rows = _prior_readers(None)
    viltloven = rows["lov/1981-05-29-38"]
    assert viltloven["title"] == "Lov om jakt og fangst av vilt (viltloven)"
    assert viltloven["sha256"] == "b90d64b9b8eb73d19e9f96cd26e05cb3a5aad4b87274ecc6a185c9fde5d93564"
    regulation = rows["forskrift/1960-06-02-1"]
    assert "oreigningslovens § 5" in regulation["title"]
    assert regulation["sha256"] == "e95eee802943ae44f1b35480ce814d674988eb7c32d0c31257b866d6ce04aeb8"
    assert "lov/9999-01-01-1" not in rows


def test_archive_and_provenance_links_require_an_explicit_full_commit(tmp_path):
    commit = "a" * 40
    page = Path(generate_not_found_page(str(tmp_path), history_archive_commit=commit)).read_text(encoding="utf-8")
    copies = config(page)["priorReaders"]
    base = f"https://github.com/sondreskarsten/norwegian-laws-history/blob/{commit}/reader-archive/"
    assert copies["lov/1981-05-29-38"]["archive"] == base + "index.md"
    assert copies["lov/1981-05-29-38"]["provenance"] == base + f"records/{EXIT}/lover/lov-1981-05-29-38.json"
    for invalid in ("main", "HEAD", "a" * 7, "a" * 40 + "/other"):
        with pytest.raises(ValueError, match="complete published Git commit"):
            generate_not_found_page(str(tmp_path), history_archive_commit=invalid)


def test_default_links_use_the_published_history_archive_commit(tmp_path):
    assert HISTORY_ARCHIVE_COMMIT == "a79eda10c52508ab0ff49e5cf7f2d867b322375b"
    page = Path(generate_not_found_page(str(tmp_path))).read_text(encoding="utf-8")
    for row in config(page)["priorReaders"].values():
        assert f"/blob/{HISTORY_ARCHIVE_COMMIT}/reader-archive/" in row["archive"]
        assert f"/blob/{HISTORY_ARCHIVE_COMMIT}/reader-archive/" in row["provenance"]


def test_existing_history_links_only_appear_for_generated_pages(tmp_path):
    history = tmp_path / "historie"
    history.mkdir()
    (history / "known.html").write_text("Existing history", encoding="utf-8")
    index = SimpleNamespace(historie={"lov/2024-01-01-1": "historie/known.html",
                                     "lov/1981-05-29-38": "historie/missing.html"})
    page = Path(generate_not_found_page(str(tmp_path), site_index=index,
                                       site_base="https://example.invalid/custom-prefix")).read_text(encoding="utf-8")
    data = config(page)
    assert data["base"] == "/custom-prefix/"
    assert data["history"] == {"lov/2024-01-01-1": "/custom-prefix/historie/known.html"}
    assert 'href="/custom-prefix/book/sok.html"' in page
    assert 'id="prior-reader"' in page and 'aria-labelledby="prior-reader-heading" hidden' in page
