"""Source-bound qualification for identifiers, metadata and semantic typography."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET
from lovdata_loader import source_body_gate as gate
from test_source_body_lists import captured

FIXTURES = Path(__file__).parent / 'fixtures/source_body'
MEMBERS = json.loads((FIXTURES / 'presentation-source-members.json').read_bytes())


def fixture(feature):
    row = next(r for r in MEMBERS if feature in r['features'])
    raw = (FIXTURES / row['retained_file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['member_sha256']
    return row, raw, captured(raw)


class SourcePresentationTests(unittest.TestCase):
    def test_real_documents_preserve_exact_source_metadata_and_typography(self):
        for row in MEMBERS:
            with self.subTest(refid=row['refid']):
                raw = (FIXTURES / row['retained_file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),row['member_sha256'])
                model = captured(raw)
                result = gate.qualify_source_body(raw,model,expected_refid=row['refid'],
                    expected_member_sha256=row['member_sha256'],source_occurrence_id=row['source_occurrence_id'])
                self.assertEqual(result['report']['status'],'passed',result['report'])
                self.assertEqual(result['report']['legal_state'],'not_assessed')
                gate.verify_rendered_body(result['html'],model,stylesheet=result['stylesheet'])
                for tag in ('sup','sub','h4','h5','h6'):
                    if any(n['tag']==tag for n,_,_ in gate._walk(model['root'])):
                        with self.assertRaises(gate.BodyRejected):
                            gate.verify_rendered_body(result['html'].replace('<'+tag,'<i',1),
                                                      model,stylesheet=result['stylesheet'])
                for attr in ('data-repealeddate','data-link-type'):
                    if any(attr in n['attributes'] for n,_,_ in gate._walk(model['root'])):
                        self.assertIn(attr+'=',result['html'])
                        with self.assertRaises(gate.BodyRejected):
                            gate.verify_rendered_body(result['html'].replace(attr+'=',attr+'-lost=',1),
                                                      model,stylesheet=result['stylesheet'])

    def test_unknown_presentation_values_are_rejected(self):
        for feature, attribute, value in (
            ('margin-top', 'margin-top', 'false'),
            ('caption', 'data-caption-placement', 'sideways'),
            ('data-rulesAssistanceType', 'data-rulesAssistanceType', '1'),
            ('span', 'lang', 'x<script>')):
            _, _, model = fixture(feature)
            if feature == 'span':
                node = next(n for n,_,_ in gate._walk(model['root']) if n['tag']=='span' and 'lang' in n['attributes'])
            else:
                node = next(n for n,_,_ in gate._walk(model['root']) if attribute in n['attributes'])
            node['attributes'][attribute] = value
            with self.assertRaises(gate.BodyRejected): gate._grammar(model['root'],model['context'])

    def test_explicit_margin_rule_overrides_default_paragraph_spacing(self):
        _, _, model = fixture('margin-top')
        self.assertIn('main.documentBody article.defaultP[margin-top=true]{margin-top:1.3em}',
                      gate.stylesheet_for_body(model['root']))
