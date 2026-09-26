"""Source replacement-text roles and literal presentation remain source-bound."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from lovdata_loader import source_body_gate as gate
from lovdata_loader.source_body import capture_source_body as captured

FIXTURES = Path(__file__).parent / 'fixtures/source_body'


class SourceFuturePresentationTests(unittest.TestCase):
    def test_retained_source_roles_and_exact_render_readback(self):
        records = json.loads((FIXTURES / 'future-presentation-source-members.json').read_text(encoding='utf-8'))
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
                for before, after in (('class="futureLegalArticle"', 'class="legalArticle"'),
                        ('class="futuretitle"', 'class="miscHeadline"'),
                        ('class="underline"', 'class="letterspacing"'),
                        ('class="letterspacing"', 'class="underline"'),
                        ('<blockquote>', '<blockquote data-rulesAssistanceType="0">'),
                        ('<s>', '<i>')):
                    if before not in result['html']:
                        continue
                    changed = result['html'].replace(before, after, 1)
                    if before == '<s>':
                        changed = changed.replace('</s>', '</i>', 1)
                    with self.subTest(changed_role=before), self.assertRaises(gate.BodyRejected):
                        gate.verify_rendered_body(changed, model, stylesheet=result['stylesheet'])
        self.assertTrue({'futureLegalArticle', 'futuretitle', 'underline', 'letterspacing', 'blockquote'} <= features, features)

    def test_unknown_future_roles_and_orphaned_block_text_are_rejected(self):
        records = json.loads((FIXTURES / 'future-presentation-source-members.json').read_text(encoding='utf-8'))
        record = next(r for r in records if 'futureLegalArticle' in r['features'])
        original = captured((FIXTURES / record['retained_file']).read_bytes())
        for kind in ('futureLegalP', 'futureDefaultP', 'unknownFutureRole'):
            model = copy.deepcopy(original)
            node = next(n for n, _, _ in gate._walk(model['root']) if gate._form(n) == ('article', 'futureLegalArticle'))
            node['attributes']['class'] = kind
            with self.subTest(kind=kind), self.assertRaises(gate.BodyRejected):
                gate._grammar(model['root'], model['context'])
        for role in ('futureLegalArticle', 'blockquote'):
            record = next(r for r in records if role in r['features'])
            model = captured((FIXTURES / record['retained_file']).read_bytes())
            node = next(n for n, _, _ in gate._walk(model['root']) if n['attributes'].get('class') == role or n['tag'] == role)
            node['children'].append('orphaned text outside the source paragraph')
            with self.subTest(orphaned=role), self.assertRaises(gate.BodyRejected):
                gate._grammar(model['root'], model['context'])

    def test_presentation_styles_are_bound_to_the_rendered_product(self):
        records = json.loads((FIXTURES / 'future-presentation-source-members.json').read_text(encoding='utf-8'))
        record = next(r for r in records if 'letterspacing' in r['features'])
        raw = (FIXTURES / record['retained_file']).read_bytes(); model = captured(raw)
        result = gate.qualify_source_body(raw, model, expected_refid=record['refid'],
            expected_member_sha256=record['member_sha256'], source_occurrence_id=record['source_occurrence_id'])
        changed = result['stylesheet'].replace('letter-spacing:.15em', 'letter-spacing:0')
        self.assertNotEqual(changed, result['stylesheet'])
        with self.assertRaises(gate.BodyRejected):
            gate.verify_rendered_body(result['html'], model, stylesheet=changed)
