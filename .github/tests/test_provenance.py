import importlib.util
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provenance = script('provenance')

MANIFEST = [
    {"filename": "gjeldende-lover.tar.bz2", "lastModified": "2026-10-01T01:31:00Z", "sizeBytes": 10},
    {"filename": "gjeldende-sentrale-forskrifter.tar.bz2", "lastModified": "2026-10-01T01:32:00Z", "sizeBytes": 11},
    {"filename": "lovtidend-avd1-2001-2025.tar.bz2", "lastModified": "2026-09-14T01:31:00Z", "sizeBytes": 12},
    {"filename": "lovtidend-avd1-2026.tar.bz2", "lastModified": "2026-10-01T01:31:00Z", "sizeBytes": 13},
]


def _git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@x', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@x')
    return subprocess.run(['git', *args], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / 'repo'
    (repo / 'lovdata-loader').mkdir(parents=True)
    (repo / 'lovdata-publisher').mkdir()
    (repo / 'lovdata-loader' / 'a.py').write_text('1')
    (repo / 'lovdata-publisher' / 'b.py').write_text('1')
    (repo / 'lover').mkdir()
    (repo / 'lover' / 'x.md').write_text('law')
    _git(repo, 'init', '-q', '-b', 'main')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-q', '-m', 'first')
    return repo


def _state(repo, sha, manifest=MANIFEST, with_evidence=True):
    state = {'version': 2, 'source_sha': sha, 'source_manifest': manifest}
    if with_evidence:
        state['evidence'] = {'receipt_url': 'https://github.com/x/y/releases/download/observation-a/evidence.json',
                             'bundle_sha256': 'b' * 64}
    path = repo / '.github' / 'state' / 'publication.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(state))
    return path


def test_plan_source_only(repo, monkeypatch):
    monkeypatch.chdir(repo)
    first = _git(repo, 'rev-parse', 'HEAD')
    state = _state(repo, first)
    (repo / 'lover' / 'y.md').write_text('data only')
    _git(repo, 'add', '-A'); _git(repo, 'commit', '-q', '-m', 'data')
    newer = [dict(m) for m in MANIFEST]
    newer[3]['lastModified'] = '2026-10-02T01:31:00Z'
    result = provenance.plan(state, newer, repo)
    assert result['source_changed'] and not result['parser_changed'] and not result['regenerate_previous']
    assert result['identity'] == result['previous_identity']


def test_plan_parser_only(repo, monkeypatch):
    monkeypatch.chdir(repo)
    first = _git(repo, 'rev-parse', 'HEAD')
    state = _state(repo, first)
    (repo / 'lovdata-loader' / 'a.py').write_text('2')
    _git(repo, 'add', '-A'); _git(repo, 'commit', '-q', '-m', 'parser')
    result = provenance.plan(state, MANIFEST, repo)
    assert result['parser_changed'] and not result['source_changed'] and not result['regenerate_previous']
    assert result['identity']['lovdata-loader'] != result['previous_identity']['lovdata-loader']
    assert result['identity']['lovdata-publisher'] == result['previous_identity']['lovdata-publisher']


def test_plan_both_changed_regenerates_previous_only_with_evidence(repo, monkeypatch):
    monkeypatch.chdir(repo)
    first = _git(repo, 'rev-parse', 'HEAD')
    state = _state(repo, first)
    (repo / 'lovdata-publisher' / 'b.py').write_text('2')
    _git(repo, 'add', '-A'); _git(repo, 'commit', '-q', '-m', 'parser')
    newer = [dict(m) for m in MANIFEST]
    newer[0]['sizeBytes'] = 99
    result = provenance.plan(state, newer, repo)
    assert result['parser_changed'] and result['source_changed'] and result['regenerate_previous']
    assert result['previous_bundle_sha256'] == 'b' * 64
    state.write_text(json.dumps({'version': 1, 'source_sha': first, 'source_manifest': MANIFEST}))
    assert not provenance.plan(state, newer, repo)['regenerate_previous']


def test_plan_without_state_treats_parser_as_changed(repo, monkeypatch):
    monkeypatch.chdir(repo)
    result = provenance.plan(repo / 'missing.json', MANIFEST, repo)
    assert result['parser_changed'] and result['source_changed'] and not result['regenerate_previous']


def _bundle(tmp_path, archives):
    bundle = tmp_path / 'snapshot.tar.gz'
    observations = {'archives': []}
    with tarfile.open(bundle, 'w:gz') as tar:
        def add(name, data):
            info = tarfile.TarInfo(name); info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for filename, data in archives.items():
            digest = provenance.hashlib.sha256(data).hexdigest()
            add(f'raw/{digest}.tar.bz2', data)
            observations['archives'].append({'raw_path': f'raw/{digest}.tar.bz2', 'original_filename': filename,
                                             'archive_sha256': digest})
        add('source-observations.json', json.dumps(observations).encode())
        add('source-manifest.json', json.dumps(MANIFEST).encode())
    return bundle


def test_fetch_previous_restores_archives_by_original_name(tmp_path):
    archives = {m['filename']: m['filename'].encode() * 3 for m in MANIFEST}
    bundle = _bundle(tmp_path, archives)
    out = tmp_path / 'prev'
    paths = provenance.fetch_previous('', provenance._digest(bundle), out, bundle_file=bundle)
    assert Path(paths['gjeldende']).name == 'gjeldende-lover.tar.bz2'
    assert Path(paths['forskrifter']).name == 'gjeldende-sentrale-forskrifter.tar.bz2'
    assert [Path(p).name for p in paths['lovtidend']] == ['lovtidend-avd1-2001-2025.tar.bz2', 'lovtidend-avd1-2026.tar.bz2']
    assert (out / 'gjeldende-lover.tar.bz2').read_bytes() == archives['gjeldende-lover.tar.bz2']
    assert json.loads((out / 'source-manifest.json').read_text()) == MANIFEST
    with pytest.raises(ValueError, match='digest mismatch'):
        provenance.fetch_previous('', 'c' * 64, tmp_path / 'other', bundle_file=bundle)


def test_fetch_previous_rejects_unsafe_names(tmp_path):
    bundle = _bundle(tmp_path, {'../evil.tar.bz2': b'x', 'gjeldende-lover.tar.bz2': b'y',
                                'gjeldende-sentrale-forskrifter.tar.bz2': b'z'})
    with pytest.raises(ValueError, match='Unsafe'):
        provenance.fetch_previous('', provenance._digest(bundle), tmp_path / 'prev', bundle_file=bundle)


def test_verify_reproducible_reports_differences(tmp_path, monkeypatch):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    output = tmp_path / 'out'
    for d, content in (('lover', 'A'), ('forskrifter', 'B'), ('historie', 'C')):
        (output / d).mkdir(parents=True)
        (output / d / 'doc.md').write_text(content)
    (output / 'lover' / 'README.md').write_text('index')

    def fake_run(cmd, check, capture_output):
        temp = Path(cmd[cmd.index('--output') + 1])
        for d, content in (('lover', 'A'), ('forskrifter', 'B'), ('historie', 'changed')):
            (temp / d).mkdir(parents=True)
            (temp / d / 'doc.md').write_text(content)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(provenance.subprocess, 'run', fake_run)
    assert provenance.verify_reproducible(snapshot, output) == ['historie/doc.md']


def test_message_carries_provenance_trailers(tmp_path):
    manifest = tmp_path / 'source-manifest.json'
    manifest.write_text(json.dumps(MANIFEST))
    summary = tmp_path / 'commit-msg.txt'
    summary.write_text('Oppdater ... [skip ci]\n\nAI summary line\n')
    identity = {'lovdata-loader': 'a' * 40, 'lovdata-publisher': 'b' * 40}
    previous = {'lovdata-loader': 'a' * 40, 'lovdata-publisher': 'c' * 40}
    text = provenance.message('source', '2026-10-30', manifest, identity, previous, summary)
    assert text.startswith('Oppdater lover og forskrifter fra Lovdata API 2026-10-30 [skip ci]\n\nAI summary line\n')
    assert 'Publikasjonstype: kilde' in text
    assert f'Kildemanifest: sha256:{provenance.canonical_sha256(MANIFEST)}' in text
    assert 'Kildearkiv: lovtidend-avd1-2026.tar.bz2 2026-10-01T01:31:00Z 13' in text
    assert f"Parser: lovdata-publisher {'b' * 40} (var {'c' * 40})" in text
    parser_text = provenance.message('parser', '2026-10-30', manifest, identity, previous)
    assert parser_text.startswith('Regenerer lover og forskrifter med endret parser 2026-10-30 [skip ci]')
    assert 'ikke lovendringer' in parser_text and 'Publikasjonstype: parser' in parser_text


def test_parser_identity_fetches_missing_acknowledged_commit(repo, tmp_path):
    first = _git(repo, 'rev-parse', 'HEAD')
    (repo / 'lovdata-loader' / 'a.py').write_text('2')
    _git(repo, 'add', '-A'); _git(repo, 'commit', '-q', '-m', 'parser')
    shallow = tmp_path / 'shallow'
    subprocess.run(['git', 'clone', '-q', '--depth=1', f'file://{repo}', str(shallow)], check=True, capture_output=True)
    assert subprocess.run(['git', 'cat-file', '-e', f'{first}^{{commit}}'], cwd=shallow, capture_output=True).returncode != 0
    identity = provenance.parser_identity(first, shallow)
    assert identity['lovdata-loader'] != provenance.parser_identity('HEAD', shallow)['lovdata-loader']
