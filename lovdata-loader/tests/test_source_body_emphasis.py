"""Keep source emphasis in two complete retained documents, without guessing styles."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from lovdata_loader import source_body_gate as gate
from test_source_body_lists import captured

FIXTURES = Path(__file__).parent / 'fixtures/source_body'
MEMBERS = json.loads((FIXTURES / 'emphasis-source-members.json').read_bytes())


class SourceEmphasisTests(unittest.TestCase):
    def test_real_source_emphasis_survives_capture_and_rendering(self):
        for row in MEMBERS:
            if row['refid'] == 'forskrift/1995-07-13-646':
                continue
            with self.subTest(refid=row['refid']):
                raw = (FIXTURES / row['retained_file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['member_sha256'])
                model = captured(raw)
                result = gate.qualify_source_body(raw, model, expected_refid=row['refid'],
                    expected_member_sha256=row['member_sha256'], source_occurrence_id=row['source_occurrence_id'])
                self.assertEqual(result['report']['status'], 'passed', result['report'])
                self.assertIn('<strong>', result['html'])
                gate.verify_rendered_body(result['html'], model, stylesheet=result['stylesheet'])
                with self.assertRaises(gate.BodyRejected):
                    gate.verify_rendered_body(result['html'].replace('<strong>', '<i>').replace('</strong>', '</i>'),
                                              model, stylesheet=result['stylesheet'])
                changed = copy.deepcopy(model)
                strong = next(n for n,_,_ in gate._walk(changed['root']) if n['tag']=='strong')
                strong['attributes']['style'] = 'display:none'
                with self.assertRaises(gate.BodyRejected):
                    gate._grammar(changed['root'],changed['context'])

    def test_table_in_source_default_paragraph_remains_scrollable(self):
        row = next(r for r in MEMBERS if r['refid']=='forskrift/1995-07-13-646')
        raw = (FIXTURES / row['retained_file']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),row['member_sha256'])
        model = captured(raw)
        result = gate.qualify_source_body(raw,model,expected_refid=row['refid'],
            expected_member_sha256=row['member_sha256'],source_occurrence_id=row['source_occurrence_id'])
        self.assertEqual(result['report']['status'],'passed',result['report'])
        self.assertIn('data-source-body-derived="table-scroll"',result['html'])
        gate.verify_rendered_body(result['html'],model,stylesheet=result['stylesheet'])
        with self.assertRaises(gate.BodyRejected):
            gate.verify_rendered_body(result['html'].replace('tabindex="0"','tabindex="-1"'),
                                      model,stylesheet=result['stylesheet'])


if __name__ == '__main__':
    unittest.main()
