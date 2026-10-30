import json

import pytest

from norwegian_laws_mcp.catalog import Catalog
from norwegian_laws_mcp.errors import ResolveError

from conftest import catalog_json


@pytest.fixture(scope="module")
def catalog():
    return Catalog.from_json_text(catalog_json())


@pytest.mark.parametrize("ref", [
    "lov/2025-06-20-105", "LOV/2025-06-20-105", "lov-2025-06-20-105", "lover/lov-2025-06-20-105.md",
    "lov-2025-06-20-105.md", "/eli/lov/2025/06/20/105", "enhetsregisterloven", "Enhetsregisterloven",
    "https://lovdata.no/dokument/NL/lov/2025-06-20-105",
])
def test_resolve_variants(catalog, ref):
    assert catalog.resolve(ref).refid == "lov/2025-06-20-105"


def test_resolve_alias_and_short_title(catalog):
    assert catalog.resolve("asl").refid == "lov/1997-06-13-44"
    assert catalog.resolve("aksjeloven").refid == "lov/1997-06-13-44"
    assert catalog.resolve("Aksjeloven – asl").refid == "lov/1997-06-13-44"


def test_resolve_alt_names_and_refid_forms():
    raw = json.loads(catalog_json())
    raw[0]["korttittel"] = "Grunnloven (bokmål) – Grl."
    raw[1]["korttittel"] = ""
    cat = Catalog.from_json_text(json.dumps(raw))
    assert cat.resolve("grunnloven").refid == "lov/2025-06-20-105"
    assert cat.resolve("grl").refid == "lov/2025-06-20-105"
    assert cat.resolve("enhetsregisterforskriften").refid == "forskrift/2025-08-06-1610"
    assert cat.search("LOV-2025-06-20-105")[0][0] == 100
    assert cat.search("aml") == [] or all(e.refid != "lov/1997-06-13-44" for _, e in cat.search("aml"))


def test_resolve_unknown_lists_suggestions(catalog):
    with pytest.raises(ResolveError) as exc:
        catalog.resolve("enhetsregist")
    assert "lov/2025-06-20-105" in str(exc.value)


def test_search_ranks_short_title_and_kind(catalog):
    results = catalog.search("enhetsregister")
    refids = [e.refid for _, e in results]
    assert refids[0] == "lov/2025-06-20-105"
    assert "forskrift/2025-08-06-1610" in refids
    assert catalog.search("enhetsregister", kind="forskrift")[0][1].kind == "forskrift"
    assert all(not e.is_amendment_act for _, e in catalog.search("enhetsregister", include_amendment_acts=False))


def test_search_title_words(catalog):
    results = catalog.search("lov om aksjeselskaper")
    assert results[0][1].refid == "lov/1997-06-13-44"
    assert catalog.search("zzzz-nothing") == []
