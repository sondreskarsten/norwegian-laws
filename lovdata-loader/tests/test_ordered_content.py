"""A ledd retains interleaved text/list order without becoming multiple ledd."""
from dataclasses import asdict

from bs4 import BeautifulSoup
import pytest

from lovdata_loader.audit import audit_law_lists
from lovdata_loader.coverage import model_tokens
from lovdata_loader.models import LawData
from lovdata_loader.parser import parse_amendment, parse_article


MIXED = ('<article class="legalArticle" data-name="§1"><article class="legalP">'
         'ALPHA<ol type="1"><li data-name="1.">BRAVO</li></ol>'
         'CHARLIE<ol type="1"><li data-name="2.">DELTA</li></ol>ECHO'
         '</article></article>')


def test_ordered_paragraph_survives_json_roundtrip_and_is_counted_once():
    article = parse_article(BeautifulSoup(MIXED, 'html.parser').article)
    law = LawData.from_dict({'refid': 'lov/2024-01-01-1', 'title': 'Test',
                             'top_level_articles': [asdict(article)]})
    result = LawData.from_dict(law.to_dict()).to_dict()
    paragraphs = result['top_level_articles'][0]['paragraphs']
    assert len(paragraphs) == 1
    assert [block['kind'] for block in paragraphs[0]['ordered_blocks']] == [
        'text', 'list', 'text', 'list', 'text']
    assert [block['text'] for block in paragraphs[0]['ordered_blocks']
            if block['kind'] == 'text'] == ['ALPHA', 'CHARLIE', 'ECHO']
    tokens = model_tokens(result)
    assert all(tokens[word] == 1 for word in ('alpha', 'bravo', 'charlie', 'delta', 'echo'))
    assert audit_law_lists(result)['items'] == 2


@pytest.mark.parametrize('attribute,kind', [
    ('data-change-part', 'change'), ('data-repeal-part', 'repeal'),
    ('data-add-new-part', 'add'), ('data-move-part', 'move'),
])
def test_structured_regulation_target(attribute, kind):
    change = BeautifulSoup('<article class="change"><article class="defaultP">'
                           '§1 skal lyde:</article></article>', 'html.parser').article
    change[attribute] = 'forskrift/2020-01-01-1/§1'
    amendment = parse_amendment(change)
    assert amendment.target_law == 'forskrift/2020-01-01-1'
    assert amendment.change_type == kind
    assert amendment.target == 'forskrift/2020-01-01-1/§1'
