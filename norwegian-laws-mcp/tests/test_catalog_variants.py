from norwegian_laws_mcp.catalog import normalize_refid, refid_to_path


def test_nynorsk_variant_refid_resolves_to_its_own_file():
    assert normalize_refid("LOV-1814-05-17-nn") == "lov/1814-05-17-nn"
    assert refid_to_path("lov/1814-05-17-nn") == "lover/lov-1814-05-17-nn.md"
    assert refid_to_path("lov/1814-05-17") == "lover/lov-1814-05-17.md"


def test_lovdata_eli_with_padding_or_placeholder_resolves():
    assert normalize_refid("/eli/lov/1884/06/14/03") == "lov/1884-06-14-3"
    assert normalize_refid("/eli/lov/1687/04/15/0") == "lov/1687-04-15"
    assert normalize_refid("/eli/lov/1998/07/17/56") == "lov/1998-07-17-56"
