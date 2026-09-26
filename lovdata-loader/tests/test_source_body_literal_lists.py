"""Exact retained source labels, including symbols and compound numbering."""
import copy
import hashlib
import json
import html
import unittest
from pathlib import Path
from lovdata_loader import source_body_gate as gate
from lovdata_loader.source_body import capture_source_body as captured

FIXTURES = Path(__file__).parent / 'fixtures/source_body'

class SourceLiteralListLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((FIXTURES / 'literal-list-source-members.json').read_text(encoding='utf-8'))

    def test_retained_source_labels_survive_raw_and_render_readback(self):
        features = set()
        for row in self.rows:
            with self.subTest(refid=row['refid']):
                raw = (FIXTURES / row['retained_file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['member_sha256'])
                model = captured(raw)
                result = gate.qualify_source_body(raw, model, expected_refid=row['refid'],
                    expected_member_sha256=row['member_sha256'], source_occurrence_id=row['source_occurrence_id'])
                self.assertEqual(result['report']['status'], 'passed', result['report'])
                gate.verify_rendered_body(result['html'], model, stylesheet=result['stylesheet'])
                labels = {n['attributes']['data-name'] for n, _, _ in gate._walk(model['root'])
                          if n['tag'] == 'li' and 'data-name' in n['attributes']}
                self.assertEqual(labels, set(row['markers']))
                self.assertIn('content:attr(data-name)', result['stylesheet'])
                features.update(row['features'])
                marker = next(n['attributes']['data-name'] for n, _, _ in gate._walk(model['root'])
                              if n['tag'] == 'li' and 'data-name' in n['attributes'])
                changed = result['html'].replace('data-name="' + html.escape(marker, quote=True) + '"', 'data-name="WRONG"', 1)
                self.assertNotEqual(changed, result['html'])
                with self.assertRaises(gate.BodyRejected):
                    gate.verify_rendered_body(changed, model, stylesheet=result['stylesheet'])
        self.assertTrue({'en-dash', 'bullet', 'compound', 'nordic', 'parentheses'} <= features, features)

    def test_ambiguous_missing_and_unsafe_marker_fields_remain_rejected(self):
        node = {'tag': 'ul', 'attributes': {'class': 'defaultList'}, 'children': [
            {'tag': 'li', 'attributes': {'data-name': '–', 'data-li-identifier': '–'}, 'children': [
                {'tag': 'article', 'attributes': {'class': 'listArticle'}, 'children': [
                    {'tag': 'article', 'attributes': {'class': 'legalP'}, 'children': ['text']}]}]}]}
        gate._list(node, '/ul')
        for label in ('', 'x' * 33, 'a\nb', '\u202e1.', '<img>', 'a b', '\u200b1.'):
            altered = copy.deepcopy(node)
            altered['children'][0]['attributes'] = {'data-name': label, 'data-li-identifier': label}
            with self.subTest(label=label), self.assertRaises(gate.BodyRejected):
                gate._list(altered, '/ul')
        for attrs in ({'data-name': '–'}, {'data-li-identifier': '–'}, {'data-name': '–', 'data-li-identifier': '-'}):
            altered = copy.deepcopy(node); altered['children'][0]['attributes'] = attrs
            with self.subTest(attrs=attrs), self.assertRaises(gate.BodyRejected):
                gate._list(altered, '/ul')

    def test_source_values_remain_literal_and_bounded(self):
        node = {'tag': 'ol', 'attributes': {'class': 'defaultList', 'type': '1'}, 'children': [
            {'tag': 'li', 'attributes': {'data-name': '0.', 'value': '0'}, 'children': [
                {'tag': 'article', 'attributes': {'class': 'listArticle'}, 'children': ['body']}]}]}
        gate._list(node, '/ol')
        for value in ('-1', '01', '2147483648', '1.1', '', '1000000000000000'):
            altered = copy.deepcopy(node); altered['children'][0]['attributes']['value'] = value
            with self.subTest(value=value), self.assertRaises(gate.BodyRejected):
                gate._list(altered, '/ol')
