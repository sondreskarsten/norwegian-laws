"""Ordered content is rendered in source order and guarded by its contract."""
from dataclasses import asdict
import json
from pathlib import Path

from bs4 import BeautifulSoup
import markdown
import pytest

from lovdata_loader.models import LawData
from lovdata_loader.parser import parse_article
from lovdata_loader.store import write_snapshot
from lovdata_publisher.formatter import format_article, format_all_laws, format_law_markdown
from lovdata_publisher.snapshot import validate_snapshot


MIXED = ('<article class="legalP">ALPHA<ol><li data-name="1.">BRAVO</li></ol>'
         'CHARLIE<ol><li data-name="2.">DELTA</li></ol>ECHO</article>')


def mixed_article(body=MIXED):
    return parse_article(BeautifulSoup('<article class="legalArticle" data-name="§1">'
                                       + body + '</article>', 'html.parser').article)


def assert_order(rendered):
    tokens = ['ALPHA', 'BRAVO', 'CHARLIE', 'DELTA', 'ECHO']
    assert sorted(tokens, key=rendered.index) == tokens
    assert all(rendered.count(token) == 1 for token in tokens)


def test_ordered_content_renders_in_articles_top_level_and_nested_lists():
    article = asdict(mixed_article())
    assert_order(format_article(article))
    assert_order(format_law_markdown({'refid': 'lov/2024-01-01-1', 'title': 'Test',
                                     'top_level_paragraphs': article['paragraphs']}))
    nested = mixed_article('<article class="legalP"><ol><li data-name="a)">'
                           '<article class="listArticle">' + MIXED
                           + '</article></li></ol></article>')
    assert_order(format_article(asdict(nested)))


def test_single_list_keeps_existing_markdown_bytes():
    article = mixed_article('<article class="legalP">ALPHA<ol><li data-name="1.">'
                            'BRAVO</li></ol>CHARLIE</article>')
    assert format_article(asdict(article)) == 'ALPHA\n\n1. BRAVO\n\nCHARLIE\n'


def test_real_ordered_legal_lists_retain_nested_html_hierarchy():
    fixture = (Path(__file__).parents[2] / 'lovdata-loader/tests/fixtures/'
               'fixture_regnskapsloven_lists.xml')
    source = BeautifulSoup(fixture.read_text(encoding='utf-8'), 'html.parser')
    article = source.find('article', class_='legalArticle', attrs={'data-name': '§6-2'})
    rendered = markdown.markdown(format_article(asdict(parse_article(article))),
                                 extensions=['extra', 'toc'])
    soup = BeautifulSoup(rendered, 'html.parser')
    top_lists = [node for node in soup.select('ol.legal-list') if not node.find_parent('li')]
    assert len(top_lists) == 2
    first_items = top_lists[0].find_all('li', recursive=False)
    assert [li.find('span', class_='legal-marker').get_text() for li in first_items] == ['A.', 'B.']
    roman_list = first_items[0].find('ol', class_='legal-list')
    roman_items = roman_list.find_all('li', recursive=False)
    assert [li.find('span', class_='legal-marker').get_text() for li in roman_items] == ['I.', 'II.', 'III.']
    numeric_items = roman_items[0].find('ol').find_all('li', recursive=False)
    assert [li.find('span', class_='legal-marker').get_text() for li in numeric_items] == ['1.', '2.', '3.', '4.']
    assert 'Utvikling' in numeric_items[0].get_text()
    assert [li.find('span', class_='legal-marker').get_text()
            for li in top_lists[1].find_all('li', recursive=False)] == ['C.', 'D.']
    assert not soup.find(['pre', 'code'])


def test_ordered_snapshot_contract_and_unknown_contract_fail_closed(tmp_path):
    law = LawData.from_dict({'refid': 'lov/2024-01-01-1', 'title': 'Test',
                             'top_level_articles': [asdict(mixed_article())]})
    snapshot = tmp_path / 'snapshot'
    write_snapshot(str(snapshot), [law], [])
    manifest_path = snapshot / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['version'] == 3
    assert manifest['content_version'] == 'ordered-paragraph-blocks-v1'
    assert manifest['formatter_version'] == 'law-markdown-ordered-html-v1'
    validate_snapshot(snapshot)
    output = tmp_path / 'output'
    format_all_laws(str(snapshot), str(output))
    assert_order((output / 'lover/lov-2024-01-01-1.md').read_text())
    for field, value in [('content_version', 'future'), ('formatter_version', 'future'),
                         ('version', 2)]:
        invalid = dict(manifest, **{field: value})
        manifest_path.write_text(json.dumps(invalid))
        with pytest.raises(ValueError, match='[Cc]ontent|[Cc]ontract|[Oo]rdered|[Ff]ormatter'):
            validate_snapshot(snapshot)
    downgraded = dict(manifest, version=2, content_version='legacy-paragraphs-v1',
                     formatter_version='law-markdown-v1')
    manifest_path.write_text(json.dumps(downgraded))
    with pytest.raises(ValueError, match='requires snapshot version 3'):
        validate_snapshot(snapshot)


def test_ordered_snapshot_still_checks_content_hashes_and_counts(tmp_path):
    law = LawData.from_dict({'refid': 'lov/2024-01-01-1', 'title': 'Test',
                             'top_level_articles': [asdict(mixed_article())]})
    snapshot = tmp_path / 'snapshot'
    write_snapshot(str(snapshot), [law], [])
    manifest_path = snapshot / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest_path.write_text(json.dumps(dict(manifest, law_count=2)))
    with pytest.raises(ValueError, match='law_count mismatch'):
        validate_snapshot(snapshot)
    manifest_path.write_text(json.dumps(manifest))
    document = snapshot / 'laws/lov-2024-01-01-1.json'
    data = json.loads(document.read_text())
    blocks = data['top_level_articles'][0]['paragraphs'][0]['ordered_blocks']
    blocks[0]['text'] = 'Changed after snapshot publication'
    document.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='artifact hash mismatch'):
        validate_snapshot(snapshot)
    blocks[0]['kind'] = 'unknown'
    document.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Unsupported ordered paragraph block'):
        validate_snapshot(snapshot)
