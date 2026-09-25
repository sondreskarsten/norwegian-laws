"""Root/section interleaving survives parsing, JSON replay and publication."""
from copy import deepcopy
from io import BytesIO
import json
import tarfile

import pytest

from lovdata_loader.evidence import EvidenceBundle
from lovdata_loader.models import LawData, CONTAINER_CONTENT_VERSION, CONTAINER_FORMATTER_VERSION
from lovdata_loader.parser import parse_law
from lovdata_loader.store import write_snapshot
from lovdata_publisher.formatter import format_law_markdown
from lovdata_publisher.snapshot import validate_snapshot


def article(text):
    return f'<article class="legalArticle"><article class="legalP">{text}</article></article>'


SOURCE = ('<html><header><dl><dd class="refid">lov/2024-01-01-1</dd>'
          '<dd class="title">Ordered test</dd></dl></header><main class="documentBody">'
          + article('ROOT-FIRST') + '<p>ROOT-PARAGRAPH</p><section><h2>CHAPTER</h2>'
          + article('ALPHA') + '<section><h3>SUBHEADING</h3>' + article('BRAVO')
          + '<footer>EARLY-NOTE</footer><section><h4>INNER</h4>' + article('CHARLIE')
          + '</section><p>LATE-NARRATIVE</p></section>' + article('DELTA')
          + '</section><p>ROOT-LAST</p></main></html>').encode()
TOKENS = ['ROOT-FIRST', 'ROOT-PARAGRAPH', 'ALPHA', 'BRAVO', 'EARLY-NOTE',
          'CHARLIE', 'LATE-NARRATIVE', 'DELTA', 'ROOT-LAST']


def test_source_order_survives_nested_containers_and_json_roundtrip():
    law = parse_law(SOURCE)
    encoded = json.loads(law.to_json())
    replay = LawData.from_dict(encoded)
    assert replay == law
    assert len(law.top_level_articles) == 1
    assert len(law.top_level_paragraphs) == 2
    assert len(law.sections[0].articles) == 2
    rendered = format_law_markdown(replay.to_dict())
    assert sorted(TOKENS, key=rendered.index) == TOKENS
    assert all(rendered.count(token) == 1 for token in TOKENS)


def test_legacy_grouped_source_keeps_empty_order_and_identical_rendering():
    raw = SOURCE[:SOURCE.index(b'<main')] + (
        '<main class="documentBody"><p>INTRO</p><section><h2>CHAPTER</h2>'
        '<p>PREAMBLE</p>' + article('ALPHA') + '<section><h3>INNER</h3>'
        + article('BRAVO') + '</section><footer>NOTE</footer></section>'
        + article('LAST') + '</main></html>').encode()
    data = parse_law(raw).to_dict()
    assert data['content_order'] == []
    assert data['sections'][0]['content_order'] == []
    legacy = deepcopy(data)
    def remove_order(node):
        node.pop('content_order', None)
        for section in node.get('sections', []) + node.get('subsections', []):
            remove_order(section)
    remove_order(legacy)
    assert format_law_markdown(data) == format_law_markdown(legacy)


@pytest.mark.parametrize('damage', ['omitted', 'duplicate', 'out_of_range', 'boolean', 'wrong_kind'])
def test_invalid_references_cannot_silently_drop_or_repeat_content(damage):
    data = parse_law(SOURCE).to_dict()
    # Check a nested section as well as the root contract in the next test.
    order = data['sections'][0]['content_order']
    if damage == 'omitted':
        order.pop()
    elif damage == 'duplicate':
        order.append(order[0])
    elif damage == 'out_of_range':
        order[0]['index'] = 99
    elif damage == 'boolean':
        order[0]['index'] = False
    else:
        order[0]['kind'] = 'paragraph'
    with pytest.raises(ValueError, match='content_order'):
        LawData.from_dict(data)
    with pytest.raises(ValueError, match='content_order'):
        format_law_markdown(data)


@pytest.mark.parametrize('with_evidence', [False, True])
def test_contract_keeps_evidence_envelope_and_rejects_old_reader(tmp_path, with_evidence):
    evidence = None
    laws = [parse_law(SOURCE)]
    if with_evidence:
        archive = tmp_path / 'laws.tar.bz2'
        with tarfile.open(archive, 'w:bz2') as stream:
            info = tarfile.TarInfo('nl/example.xml')
            info.size = len(SOURCE)
            stream.addfile(info, BytesIO(SOURCE))
        evidence = EvidenceBundle()
        laws = evidence.parse_archive(str(archive), 'laws')
    root = tmp_path / 'snapshot'
    write_snapshot(str(root), laws, [], evidence=evidence)
    manifest = validate_snapshot(root)
    assert manifest['version'] == (4 if with_evidence else 3)
    assert (manifest['content_version'], manifest['formatter_version']) == (
        CONTAINER_CONTENT_VERSION, CONTAINER_FORMATTER_VERSION)
    path = root / 'manifest.json'
    manifest['content_version'] = 'ordered-paragraph-blocks-v1'
    manifest['formatter_version'] = 'law-markdown-ordered-html-v1'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='Ordered containers require'):
        validate_snapshot(root)
    # Root order absent still cannot conceal a nested new representation.
    document = root / 'laws/lov-2024-01-01-1.json'
    data = json.loads(document.read_text(encoding='utf-8'))
    data['content_order'] = []
    document.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='Ordered containers require'):
        validate_snapshot(root)
