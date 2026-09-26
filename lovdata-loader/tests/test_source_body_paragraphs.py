"""Preserve source paragraph labels, continuations and formatting exactly."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from lovdata_loader import source_body_gate as gate
from test_source_body_lists import captured

FIXTURES = Path(__file__).parent / 'fixtures/source_body'
MEMBERS = json.loads((FIXTURES / 'paragraph-source-members.json').read_bytes())


def fixture(refid):
    row = next(r for r in MEMBERS if r['refid'] == refid)
    raw = (FIXTURES / row['retained_file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['member_sha256']
    model = captured(raw)
    return raw, model, dict(expected_refid=refid, expected_member_sha256=row['member_sha256'], source_occurrence_id=row['source_occurrence_id'])


class SourceParagraphTests(unittest.TestCase):
    def test_four_complete_retained_documents_qualify_and_reverse_check(self):
        for row in MEMBERS:
            with self.subTest(refid=row['refid']):
                raw, model, binding = fixture(row['refid'])
                result = gate.qualify_source_body(raw, model, **binding)
                self.assertEqual(result['report']['status'], 'passed', result['report'])
                gate.verify_rendered_body(result['html'], model, stylesheet=result['stylesheet'])
                self.assertNotIn('counter-increment', result['stylesheet'])
                self.assertNotIn('::before', result['stylesheet'])

    def test_numbered_paragraph_cannot_lose_or_change_its_source_label(self):
        _, model, _ = fixture('lov/1909-03-23')
        for replacement in ('', '999. Wrong label'):
            altered = copy.deepcopy(model)
            node = next(n for n, _, _ in gate._walk(altered['root']) if gate._form(n) == ('article', 'numberedLegalP'))
            node['children'][0] = replacement
            with self.assertRaises(gate.BodyRejected):
                gate._grammar(altered['root'], altered['context'])

    def test_changed_numbered_text_or_css_cannot_pass_render_readback(self):
        raw, model, binding = fixture('lov/1909-03-23')
        result = gate.qualify_source_body(raw, model, **binding)
        numbered = next(n for n, _, _ in gate._walk(model['root']) if gate._form(n) == ('article', 'numberedLegalP'))
        label = numbered['children'][0][:2]
        self.assertIn(label, result['html'])
        with self.assertRaises(gate.BodyRejected):
            gate.verify_rendered_body(result['html'].replace(label, '99.', 1), model, stylesheet=result['stylesheet'])
        with self.assertRaises(gate.BodyRejected):
            gate.verify_rendered_body(result['html'], model, stylesheet=result['stylesheet']+'article{display:none}')

    def test_unknown_size_and_conflicting_center_alignment_are_rejected(self):
        for refid, form, attribute, value in (
            ('lov/1981-04-08-7', ('article', 'defaultP'), 'data-text-size', 'invisible'),
            ('lov/1814-05-17', ('article', 'centeredP'), 'data-text-align', 'right'),
            ('lov/1981-04-08-7', ('span', 'legalArticleValue'), 'data-legalArea', 'unknown; injected'),
        ):
            _, model, _ = fixture(refid)
            node = next(n for n, _, _ in gate._walk(model['root']) if gate._form(n) == form)
            node['attributes'][attribute] = value
            with self.assertRaises(gate.BodyRejected):
                gate._grammar(model['root'], model['context'])


if __name__ == '__main__':
    unittest.main()
