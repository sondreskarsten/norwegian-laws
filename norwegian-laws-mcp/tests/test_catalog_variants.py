from norwegian_laws_mcp.catalog import normalize_refid, refid_to_path


def test_nynorsk_variant_refid_resolves_to_its_own_file():
    assert normalize_refid("LOV-1814-05-17-nn") == "lov/1814-05-17-nn"
    assert refid_to_path("lov/1814-05-17-nn") == "lover/lov-1814-05-17-nn.md"
    assert refid_to_path("lov/1814-05-17") == "lover/lov-1814-05-17.md"
