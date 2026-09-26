"""Source-bound row spans and grouped table rows, including invalid grids."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from lovdata_loader import source_body_gate as gate
from lovdata_loader.source_body import capture_source_body as captured

FIXTURES = Path(__file__).parent / 'fixtures/source_body'


def cell(text='cell', **attributes):
    return {'tag': 'td', 'attributes': attributes, 'children': [text]}


def row(*cells):
    return {'tag': 'tr', 'attributes': {}, 'children': list(cells)}


def table(*rows):
    return {'tag': 'table', 'attributes': {}, 'children': [
        {'tag': 'tbody', 'attributes': {}, 'children': list(rows)}]}


class SourceTableSpanTests(unittest.TestCase):
    def test_exact_source_tables_and_rendered_span_tampering(self):
        records = json.loads((FIXTURES / 'table-span-source-members.json').read_text(encoding='utf-8'))
        features = set()
        for record in records:
            with self.subTest(refid=record['refid']):
                raw = (FIXTURES / record['retained_file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), record['member_sha256'])
                model = captured(raw)
                result = gate.qualify_source_body(raw, model, expected_refid=record['refid'],
                    expected_member_sha256=record['member_sha256'], source_occurrence_id=record['source_occurrence_id'])
                self.assertEqual(result['report']['status'], 'passed', result['report'])
                gate.verify_rendered_body(result['html'], model, stylesheet=result['stylesheet'])
                features.update(record['features'])
                for attribute in ('rowspan', 'class="startGroup"'):
                    before = 'rowspan="2"' if attribute == 'rowspan' else attribute
                    if before not in result['html']:
                        continue
                    after = 'rowspan="1"' if attribute == 'rowspan' else 'class=""'
                    with self.subTest(tampered=attribute), self.assertRaises(gate.BodyRejected):
                        gate.verify_rendered_body(result['html'].replace(before, after, 1), model, stylesheet=result['stylesheet'])
        self.assertTrue({'rowspan', 'startGroup'} <= features, features)

    def test_spans_occupy_exact_grid_including_fully_covered_row(self):
        gate._table(table(row(cell('left', rowspan='2'), cell('top', colspan='2')),
                          row(cell('bottom 1'), cell('bottom 2'))), '/table')
        gate._table(table(row(cell(rowspan='2', colspan='2')), row()), '/table')
        # A row-spanning left and right cell leave one middle slot, not two.
        overlapping = table(row(cell(rowspan='2'), cell(), cell(rowspan='2')),
                            row(cell(colspan='2')))
        ragged = table(row(cell(colspan='3')), row(cell(), cell()))
        past_group = table(row(cell(rowspan='2')))
        for model in (overlapping, ragged, past_group, table(row())):
            with self.subTest(model=model), self.assertRaises(gate.BodyRejected):
                gate._table(model, '/table')

    def test_spans_cannot_cross_header_and_body_groups(self):
        model = {'tag': 'table', 'attributes': {}, 'children': [
            {'tag': 'thead', 'attributes': {}, 'children': [row(cell(rowspan='2'))]},
            {'tag': 'tbody', 'attributes': {}, 'children': [row(cell())]}]}
        with self.assertRaises(gate.BodyRejected):
            gate._table(model, '/table')

    def test_span_values_and_group_text_fail_closed(self):
        records = json.loads((FIXTURES / 'table-span-source-members.json').read_text(encoding='utf-8'))
        record = next(r for r in records if 'rowspan' in r['features'])
        model = captured((FIXTURES / record['retained_file']).read_bytes())
        for value in ('0', '-1', '01', '1001', '2.0', ''):
            altered = copy.deepcopy(model)
            span = next(n for n, _, _ in gate._walk(altered['root']) if 'rowspan' in n['attributes'])
            span['attributes']['rowspan'] = value
            with self.subTest(value=value), self.assertRaises(gate.BodyRejected):
                gate._grammar(altered['root'], altered['context'])
        record = next(r for r in records if 'startGroup' in r['features'])
        model = captured((FIXTURES / record['retained_file']).read_bytes())
        group = next(n for n, _, _ in gate._walk(model['root']) if gate._form(n) == ('tr', 'startGroup'))
        group['children'].append('outside cell')
        with self.assertRaises(gate.BodyRejected):
            gate._grammar(model['root'], model['context'])
