"""Tests for generate_laws_json schema with kind and path fields."""
import json
from pathlib import Path

from lovdata_publisher.quarto import generate_laws_json


def _write_law(p: Path, refid: str, korttittel: str = ""):
    body = (
        '---\n'
        f'tittel: "Test law"\n'
        f'korttittel: "{korttittel}"\n'
        f'refid: "{refid}"\n'
        'departement: "Finansdepartementet"\n'
        'ikrafttredelse: "2001-01-01"\n'
        '---\n\n# Test\n'
    )
    p.write_text(body, encoding="utf-8")


def test_generate_laws_json_lov_only(tmp_path):
    lover = tmp_path / "lover"
    lover.mkdir()
    _write_law(lover / "lov-1998-07-17-56.md", "lov/1998-07-17-56", "Regnskapsloven")
    out = tmp_path / "laws.json"

    laws = generate_laws_json(str(lover), str(out), version_tags=["v2001"])

    assert len(laws) == 1
    assert laws[0]["kind"] == "lov"
    assert laws[0]["path"] == "lover/lov-1998-07-17-56.md"
    assert laws[0]["lovdata"].startswith("https://lovdata.no/dokument/NL/")


def test_generate_laws_json_with_forskrifter(tmp_path):
    lover = tmp_path / "lover"
    lover.mkdir()
    forskrifter = tmp_path / "forskrifter"
    forskrifter.mkdir()
    _write_law(lover / "lov-1998-07-17-56.md", "lov/1998-07-17-56", "Regnskapsloven")
    _write_law(forskrifter / "forskrift-2024-06-21-1166.md", "forskrift/2024-06-21-1166")

    out = tmp_path / "laws.json"
    laws = generate_laws_json(
        str(lover), str(out),
        version_tags=["v2024"],
        forskrifter_dir=str(forskrifter),
    )

    kinds = {law["kind"] for law in laws}
    assert kinds == {"lov", "forskrift"}

    forskrift = next(l for l in laws if l["kind"] == "forskrift")
    assert forskrift["path"] == "forskrifter/forskrift-2024-06-21-1166.md"
    assert forskrift["lovdata"].startswith("https://lovdata.no/dokument/SF/")


def test_generate_laws_json_no_forskrifter_dir_is_ok(tmp_path):
    lover = tmp_path / "lover"
    lover.mkdir()
    _write_law(lover / "lov-1998-07-17-56.md", "lov/1998-07-17-56", "Regnskapsloven")

    out = tmp_path / "laws.json"
    laws = generate_laws_json(str(lover), str(out), version_tags=["v2024"], forskrifter_dir=None)
    assert all(l["kind"] == "lov" for l in laws)


def test_generate_subscribe_page_creates_qmd(tmp_path):
    """The subscribe page should be a valid Quarto file with search input + Fuse.js."""
    from lovdata_publisher.quarto import generate_subscribe_page

    generate_subscribe_page(str(tmp_path))
    out = tmp_path / "abonner.qmd"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # Quarto frontmatter
    assert text.startswith('---\ntitle: "Abonner på endringer"')
    # Search input present
    assert 'id="abonner-search"' in text
    # Fuse.js for fuzzy matching against the same keys as sok.qmd
    assert '../assets/vendor/fuse-7.0.0.min.js' in text
    assert 'cdn.jsdelivr' not in text
    assert '"aliases"' in text
    # Pre-curated topic/ministry feeds linked
    assert "topic-skatte--og-avgiftsrett.xml" in text
    assert "dept-finansdepartementet.xml" in text
    # External SUBSCRIBE.md reference
    assert "SUBSCRIBE.md" in text


def test_amendment_counts_propagate_to_laws_json(tmp_path):
    """When amendment_counts dict is passed, each entry gets an 'amendments' field."""
    from lovdata_publisher.quarto import generate_laws_json

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\n'
        'refid: "lov/1998-07-17-56"\n'
        'tittel: "Regnskapsloven"\n'
        'korttittel: "Regnskapsloven"\n'
        '---\n',
        encoding="utf-8",
    )
    (lover / "lov-2024-01-01-1.md").write_text(
        '---\n'
        'refid: "lov/2024-01-01-1"\n'
        'tittel: "Ny lov"\n'
        '---\n',
        encoding="utf-8",
    )

    out = tmp_path / "laws.json"
    counts = {"lov/1998-07-17-56": 42}
    result = generate_laws_json(
        lover_dir=str(lover),
        output_path=str(out),
        amendment_counts=counts,
    )
    by_refid = {e["refid"]: e for e in result}
    assert by_refid["lov/1998-07-17-56"]["amendments"] == 42
    # Law not in counts dict → 0, not missing
    assert by_refid["lov/2024-01-01-1"]["amendments"] == 0


def test_amendment_counts_optional(tmp_path):
    """When amendment_counts not provided, 'amendments' is still present (0)."""
    from lovdata_publisher.quarto import generate_laws_json

    lover = tmp_path / "lover"
    lover.mkdir()
    (lover / "lov-1998-07-17-56.md").write_text(
        '---\n'
        'refid: "lov/1998-07-17-56"\n'
        'tittel: "Regnskapsloven"\n'
        '---\n',
        encoding="utf-8",
    )
    out = tmp_path / "laws.json"
    result = generate_laws_json(
        lover_dir=str(lover),
        output_path=str(out),
    )
    assert result[0]["amendments"] == 0
