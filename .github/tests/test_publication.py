import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).parents[1] / 'scripts' / 'publication.py'
spec = importlib.util.spec_from_file_location('publication', SCRIPT)
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / 'repo'
    path.mkdir()
    git(path, 'init', '-b', 'main')
    git(path, 'config', 'user.email', 'test@example.invalid')
    git(path, 'config', 'user.name', 'Test')
    git(path, 'config', 'core.autocrlf', 'false')
    (path / 'README.md').write_text('public', encoding='utf-8')
    (path / 'lover').mkdir()
    (path / 'lover/lov-2020-01-01-1.md').write_text('law', encoding='utf-8')
    (path / '.github').mkdir()
    (path / '.github/private-runtime.json').write_text('private', encoding='utf-8')
    git(path, 'add', '.')
    git(path, 'commit', '-m', 'fixture')
    return path


def test_stage_exports_committed_product_only(repo, tmp_path):
    (repo / 'gha-creds-test.json').write_text('secret', encoding='utf-8')
    (repo / 'lover/untracked.md').write_text('unreviewed', encoding='utf-8')
    (repo / 'README.md').write_text('uncommitted', encoding='utf-8')
    out = tmp_path / 'output'
    sha = publication.stage(repo, out)
    assert (out / 'README.md').read_text() == 'public'
    assert (out / 'lover/lov-2020-01-01-1.md').read_text() == 'law'
    assert {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()} == {
        'README.md', 'lover/lov-2020-01-01-1.md', 'publication.json'}
    assert json.loads((out / 'publication.json').read_text())['source_sha'] == sha == git(repo, 'rev-parse', 'HEAD')


def test_stage_rejects_nonempty_destination(repo, tmp_path):
    out = tmp_path / 'output'
    out.mkdir()
    (out / 'keep').write_text('keep')
    with pytest.raises(ValueError, match='empty'):
        publication.stage(repo, out)
    assert (out / 'keep').read_text() == 'keep'


def test_stage_rejects_tracked_auth_artifact(repo, tmp_path):
    (repo / 'assets').mkdir()
    (repo / 'assets/gha-creds-test.json').write_text('secret')
    git(repo, 'add', 'assets')
    git(repo, 'commit', '-m', 'bad fixture')
    with pytest.raises(ValueError, match='credential'):
        publication.stage(repo, tmp_path / 'output')


def test_receipt_verifies_exact_source_and_content(tmp_path):
    manifest = [{'filename':'archive', 'lastModified':'2026-01-01', 'sizeBytes':5}]
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    receipt = publication.make_receipt('a' * 40, path)
    assert publication.matches_receipt(receipt, 'a'*40, path)
    assert not publication.matches_receipt(receipt, 'b'*40, path)
    receipt['source_manifest'][0]['sizeBytes'] = 6
    assert not publication.matches_receipt(receipt, 'a'*40, path)


def test_verify_does_not_accept_stale_page(tmp_path, monkeypatch):
    path = tmp_path / 'manifest.json'
    path.write_text('[]')
    stale = publication.make_receipt('b'*40, path)
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps(stale).encode()
    monkeypatch.setattr(publication.urllib.request, 'urlopen', lambda *a, **kw: Response())
    with pytest.raises(RuntimeError, match='not serve'):
        publication.verify('https://example.invalid/publication.json', 'a'*40, path, attempts=1, delay=0)


def test_verify_retries_then_reads_new_receipt(tmp_path, monkeypatch):
    path = tmp_path / 'manifest.json'
    path.write_text('[]')
    responses = [publication.make_receipt('b'*40,path), publication.make_receipt('a'*40,path)]
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps(responses.pop(0)).encode()
    monkeypatch.setattr(publication.urllib.request, 'urlopen', lambda *a, **kw: Response())
    publication.verify('https://example.invalid/publication.json', 'a'*40, path, attempts=2, delay=0)
    assert not responses
