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
MEMBERS = json.loads((FIXTURES / 'metadata-source-members.json').read_bytes())


def fixture(feature):
    row = next(r for r in MEMBERS if feature in r['features'])
    raw = (FIXTURES / row['retained_file']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['member_sha256']
    return row, raw, captured(raw)


class SourceMetadataTests(unittest.TestCase):
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

    def test_stv_prefix_does_not_relax_document_identity(self):
        row,raw,_ = fixture('STV')
        for location in ('STV/forskrift/1993-06-17-559','UNKNOWN/'+row['refid']):
            with self.subTest(location=location):
                root=ET.fromstring(raw)
                root.find('.//main').set('data-lovdata-URL',location)
                changed=ET.tostring(root,encoding='utf-8')
                result=gate.qualify_source_body(changed,captured(changed),expected_refid=row['refid'],
                    expected_member_sha256=hashlib.sha256(changed).hexdigest(),source_occurrence_id=row['source_occurrence_id'])
                self.assertEqual(result['report']['status'],'rejected')
                self.assertEqual(result['report']['reasons'][0]['code'],'source_context_mismatch')

    def test_metadata_does_not_admit_unknown_values_or_executable_attributes(self):
        for feature,attribute,values in (
            ('repeal_metadata','data-repealeddate',('2026-02-30','tomorrow','20260101','0000-01-01')),
            ('link_external','data-link-type',('javascript','external other',''))):
            _,_,model=fixture(feature)
            for value in values:
                with self.subTest(attribute=attribute,value=value):
                    changed=copy.deepcopy(model)
                    node=next(n for n,_,_ in gate._walk(changed['root']) if attribute in n['attributes'])
                    node['attributes'][attribute]=value
                    with self.assertRaises(gate.BodyRejected): gate._grammar(changed['root'],changed['context'])
        _,_,model=fixture('link_staticfile')
        link=next(n for n,_,_ in gate._walk(model['root']) if n['tag']=='a')
        link['attributes']['onclick']='alert(1)'
        with self.assertRaises(gate.BodyRejected): gate._grammar(model['root'],model['context'])


if __name__=='__main__': unittest.main()
