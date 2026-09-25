import importlib.util
import json
from pathlib import Path
import tarfile

import pytest


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evidence = script('publish_evidence')
mirror = script('verify_gcs_publication')


def test_bundle_is_repeatable_and_uses_only_bound_artifacts(tmp_path, monkeypatch):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    (snapshot / 'raw').mkdir()
    (snapshot / 'raw/source.tar.bz2').write_bytes(b'original archive')
    (snapshot / 'parsed.jsonl').write_bytes(b'full parsed record\n')
    (snapshot / 'gha-creds-untracked.json').write_bytes(b'must not publish')
    manifest = {'version': 4, 'artifact_hashes': {
        name: evidence.digest(snapshot / name) for name in ['raw/source.tar.bz2', 'parsed.jsonl']}}
    (snapshot / 'manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(evidence, 'validate_snapshot', lambda _: manifest)
    first = evidence.prepare(snapshot, tmp_path / 'a', 'a'*40, 'example/laws')
    second = evidence.prepare(snapshot, tmp_path / 'b', 'a'*40, 'example/laws')
    assert first == second
    with tarfile.open(tmp_path / 'a/snapshot.tar.gz') as archive:
        assert archive.getnames() == ['manifest.json', 'parsed.jsonl', 'raw/source.tar.bz2']
        assert archive.extractfile('raw/source.tar.bz2').read() == b'original archive'


def test_published_partial_release_is_not_mutated(tmp_path, monkeypatch):
    (tmp_path / 'snapshot.tar.gz').write_bytes(b'bundle')
    (tmp_path / 'evidence.json').write_text(json.dumps({
        'contract': 'lovdata-observation-release-v1',
        'bundle': {'name': 'snapshot.tar.gz', 'bytes': 6, 'sha256': evidence.digest(tmp_path / 'snapshot.tar.gz')},
        'repository': 'example/laws', 'release_tag': 'observation-abc', 'source_sha': 'a'*40}))
    monkeypatch.setattr(evidence, 'api', lambda endpoint, **kw: None if '/git/ref/' in endpoint else {
        'target_commitish': 'a'*40, 'assets': [], 'draft': False})
    monkeypatch.setattr(evidence.subprocess, 'run', lambda *a, **kw: pytest.fail('Unexpected remote write'))
    with pytest.raises(ValueError, match='refuse to mutate'):
        evidence.publish(tmp_path)


def test_mirror_checks_exact_membership_then_reads_consumer_bytes(tmp_path, monkeypatch):
    objects = {'publication.json': b'{"source_sha":"abc"}', 'laws.json': b'[]',
               'lover/one.md': b'law', 'forskrifter/two.md': b'regulation'}
    for name, body in objects.items():
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(body)
    def remote(action, url):
        if action == 'ls':
            return '\n'.join('gs://example/' + p for p in objects).encode()
        return objects[url.removeprefix('gs://example/')]
    monkeypatch.setattr(mirror, 'gsutil', remote)
    result = mirror.verify(tmp_path, 'example')
    assert result['exact_current_membership'] and len(result['readbacks']) == 4
    objects['lover/one.md'] = b'stale'
    with pytest.raises(RuntimeError, match='readback hash differs'):
        mirror.verify(tmp_path, 'example')
    objects['gha-creds-old.json'] = b'do not read'
    with pytest.raises(RuntimeError, match='membership mismatch'):
        mirror.verify(tmp_path, 'example')
