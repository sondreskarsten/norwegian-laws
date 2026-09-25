import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('push_main', Path(__file__).parents[1]/'scripts/push_main.py')
push_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push_main)


def test_push_failures_exhaust_attempts_without_success(monkeypatch):
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        if args[:1] == ('push',):
            raise subprocess.CalledProcessError(1, ['git', *args])
        return ''
    monkeypatch.setattr(push_main, 'git', run)
    with pytest.raises(RuntimeError, match='3 attempts'):
        push_main.push(attempts=3, delay=0)
    assert len([x for x in calls if x[0]=='push']) == 3
    assert not any(x[0] in {'fetch', 'rebase'} for x in calls)


def test_push_requires_remote_identity_match(monkeypatch):
    def run(*args, **kwargs):
        if args[0] == 'rev-parse': return 'a'*40
        if args[0] == 'ls-remote': return 'b'*40+'\trefs/heads/main'
        return ''
    monkeypatch.setattr(push_main, 'git', run)
    with pytest.raises(RuntimeError, match='remote'):
        push_main.push(attempts=1, delay=0)


def test_push_to_local_bare_remote(tmp_path, monkeypatch):
    remote = tmp_path/'remote.git'
    local = tmp_path/'local'
    subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
    subprocess.run(['git','init','-b','main',str(local)],check=True,capture_output=True)
    monkeypatch.chdir(local)
    push_main.git('config','user.name','Test')
    push_main.git('config','user.email','test@example.invalid')
    (local/'data').write_text('contents')
    push_main.git('add','data')
    push_main.git('commit','-m','test')
    push_main.git('remote','add','origin',str(remote))
    assert push_main.push(attempts=1, delay=0) == push_main.git('rev-parse','HEAD')
