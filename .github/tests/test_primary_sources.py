import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest

SCRIPTS=Path(__file__).resolve().parents[2]/'.github/scripts'
sys.path.insert(0,str(SCRIPTS))
from publish_primary_sources import prepare


def test_primary_acquisition_is_deterministic_and_rejects_changed_sources(tmp_path):
    source=tmp_path/'source';source.mkdir();data=b'exact scan bytes';(source/'page.bin').write_bytes(data)
    rows=[{'url':'https://example.org/scan','retrieved_at':'2026-09-26T09:00:00+00:00','status':200,'path':'page.bin','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]
    (source/'manifest.json').write_text(json.dumps(rows),encoding='utf-8')
    first=prepare(source,tmp_path/'one','a'*40,'example/repo');second=prepare(source,tmp_path/'two','a'*40,'example/repo')
    assert first==second
    assert first['contract']=='primary-source-acquisition-release-v1'
    (source/'page.bin').write_bytes(data+b'changed')
    with pytest.raises(ValueError,match='differ'):prepare(source,tmp_path/'bad','a'*40,'example/repo')


def test_changed_primary_receipt_rejected_before_network(tmp_path, monkeypatch):
    import publish_evidence
    source=tmp_path/'source';source.mkdir();data=b'scan';(source/'page.bin').write_bytes(data)
    rows=[{'url':'https://example.org/scan','retrieved_at':'2026-09-26T09:00:00+00:00','status':200,'path':'page.bin','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]
    (source/'manifest.json').write_text(json.dumps(rows),encoding='utf-8')
    output=tmp_path/'output';receipt=prepare(source,output,'a'*40,'example/repo')
    receipt['source_sha']='b'*40
    (output/'evidence.json').write_text(json.dumps(receipt),encoding='utf-8')
    def unexpected(*args,**kwargs):raise AssertionError('Network called before validation')
    monkeypatch.setattr(publish_evidence,'api',unexpected)
    with pytest.raises(ValueError,match='identity'):publish_evidence.publish(output,contract=receipt['contract'])
