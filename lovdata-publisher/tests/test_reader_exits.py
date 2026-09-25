"""Exact committed reader copies must survive a validated snapshot exit."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from lovdata_loader.evidence import EvidenceBundle
from lovdata_loader.store import write_snapshot
from lovdata_publisher.formatter import format_all_laws
from lovdata_publisher import reader_exits as exits
from lovdata_publisher.reader_archive import published_captures


LAW = "lover/lov-1981-05-29-38.md"
REG = "forskrifter/forskrift-1960-06-02-1.md"
OLD = {LAW: "# Tidligere lov – æøå\r\n\r\nAvledet lesekopi.\r\n".encode(),
       REG: "# Tidligere forskrift\n\n1. Behold teksten.\n".encode()}


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def commit(root, message="controlled parent"):
    git(root, "add", "--all")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD").decode().strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Reader capture test")
    git(root, "config", "user.email", "capture@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    git(root, "config", "core.longpaths", "true")
    (root / ".gitattributes").write_text("reader-exits/** -text\n", encoding="utf-8")
    for path, data in OLD.items():
        target = root / path
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(data)
    commit(root)
    return root


def snapshot(tmp_path, *, regulations=True):
    root = tmp_path / "snapshot"
    evidence = EvidenceBundle()
    parsed = {}
    for role, refid in (("laws", "lov/2020-01-01-1"), ("forskrifter", "forskrift/2020-01-01-1")):
        if role == "forskrifter" and not regulations:
            parsed[role] = []
            continue
        content = (f'<html><head><title>Beholdt dokument</title></head><body><header>'
                   f'<dl><dd class="refid">{refid}</dd><dd class="title">Beholdt dokument</dd></dl>'
                   f'</header><main class="documentBody"><h1>Beholdt dokument</h1>'
                   f'<article class="legalP">Beholdt tekst.</article></main></body></html>').encode()
        path = tmp_path / f"{role}.tar.bz2"
        with tarfile.open(path, "w:bz2") as archive:
            info = tarfile.TarInfo("controlled.xml")
            info.size = len(content)
            archive.addfile(info, BytesIO(content))
        parsed[role] = evidence.parse_archive(str(path), role)
    write_snapshot(str(root), parsed["laws"], [], forskrifter=parsed["forskrifter"], evidence=evidence)
    return root


def test_capture_commit_and_remote_readback_preserve_exact_bytes(repo, tmp_path):
    snap = snapshot(tmp_path)
    parent = exits.git_head(repo)
    result = format_all_laws(str(snap), str(repo), capture_repository=repo, expected_head=parent)
    assert len(result) == 2 and not (repo / LAW).exists() and not (repo / REG).exists()
    records = exits.load_capture_records(repo)
    with pytest.raises(ValueError, match="committed publication"):
        published_captures(repo)
    assert {row["source_path"] for row in records} == set(OLD)
    for row in records:
        data = OLD[row["source_path"]]
        assert (repo / row["object_path"]).read_bytes() == data
        assert git(repo, "show", f'{parent}:{row["source_path"]}') == data
        assert row["sha256"] == hashlib.sha256(data).hexdigest()
        assert row["git_blob_sha1"] == git(repo, "rev-parse", f'{parent}:{row["source_path"]}').decode().strip()
        assert row["source_git_commit"] == parent and row["legal_validity"] == "unknown"
        assert all(row[key] is None for key in ("source_observation", "source_knowledge_time", "legal_repeal", "legal_effective_date"))
        assert row["absence_snapshot"]["manifest_sha256"] == hashlib.sha256((snap / "manifest.json").read_bytes()).hexdigest()
        assert row["observed_absent_at"].endswith("+00:00")
    git(repo, "add", "--all")
    assert exits.verify_staged_exits(repo, expected_head=parent, snapshot_dir=snap)["capture_count"] == 2
    checked = subprocess.run([sys.executable, "-m", "lovdata_publisher.reader_exits", "verify-staged",
                              "--repository", str(repo), "--expected-head", parent, "--snapshot", str(snap)],
                             check=True, capture_output=True)
    assert json.loads(checked.stdout)["capture_count"] == 2
    child = commit(repo, "capture and prune")
    published = published_captures(repo)
    for row in records:
        entry = published[row["refid"]][0]
        assert entry["creationCommit"] == child and entry["sha256"] == row["sha256"]
        assert entry["copy"] == f'https://github.com/{row["source_repository"]}/blob/{child}/{row["object_path"]}'
        assert entry["provenance"].endswith(f'/{child}/reader-exits/records/{row["capture_id"]}.json')
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    git(repo, "push", str(remote), "HEAD:refs/heads/main")
    assert child.encode() in git(repo, "ls-remote", str(remote), "refs/heads/main")
    for row in records:
        assert git(remote, "show", f'{child}:{row["object_path"]}') == OLD[row["source_path"]]


def test_capture_replay_retains_first_timestamp(repo, tmp_path):
    snap = snapshot(tmp_path)
    parent = exits.git_head(repo)
    first = exits.capture_exits(repo, snap, [LAW, REG], expected_head=parent)
    before = {p.relative_to(repo): p.read_bytes() for p in (repo / "reader-exits").rglob("*") if p.is_file()}
    assert exits.capture_exits(repo, snap, [REG, LAW], expected_head=parent) == first
    assert {p.relative_to(repo): p.read_bytes() for p in (repo / "reader-exits").rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("damage", ["dirty", "staged", "assume_unchanged", "untracked", "moved_head", "snapshot"])
def test_fail_before_any_current_output_write(repo, tmp_path, damage):
    snap = snapshot(tmp_path)
    parent = exits.git_head(repo)
    if damage in {"dirty", "staged", "assume_unchanged"}:
        if damage == "assume_unchanged": git(repo, "update-index", "--assume-unchanged", REG)
        (repo / REG).write_bytes(b"changed reader")
        if damage == "staged": git(repo, "add", REG)
    elif damage == "untracked":
        (repo / "lover/lov-1990-01-01-1.md").write_bytes(b"local only")
    elif damage == "moved_head":
        (repo / "new.txt").write_text("concurrent input")
        commit(repo, "moved head")
    else:
        (snap / "manifest.json").write_text("{}")
    before = {p: (repo / p).read_bytes() for p in OLD}
    with pytest.raises(ValueError):
        format_all_laws(str(snap), str(repo), capture_repository=repo, expected_head=parent)
    assert all((repo / p).read_bytes() == data for p, data in before.items())
    assert not (repo / "lover/lov-2020-01-01-1.md").exists()
    assert not (repo / "reader-exits").exists()


def test_capture_write_failure_preserves_current_pages(repo, tmp_path, monkeypatch):
    snap = snapshot(tmp_path)
    def fail(*args, **kwargs):
        raise OSError("controlled capture write failure")
    monkeypatch.setattr(exits, "_write_immutable", fail)
    with pytest.raises(OSError, match="controlled"):
        format_all_laws(str(snap), str(repo), capture_repository=repo)
    assert all((repo / p).read_bytes() == data for p, data in OLD.items())
    assert not (repo / "lover/lov-2020-01-01-1.md").exists()


def test_partial_scope_keeps_regulation_and_only_captures_law(repo, tmp_path):
    snap = snapshot(tmp_path, regulations=False)
    format_all_laws(str(snap), str(repo), capture_repository=repo)
    assert (repo / REG).read_bytes() == OLD[REG]
    assert [row["source_path"] for row in exits.load_capture_records(repo)] == [LAW]


@pytest.mark.parametrize("damage", ["uncaptured_delete", "not_deleted", "object_not_staged", "moved_head"])
def test_staged_verifier_rejects_unbound_publication(repo, tmp_path, damage):
    snap = snapshot(tmp_path)
    parent = exits.git_head(repo)
    if damage == "uncaptured_delete":
        (repo / LAW).unlink()
    else:
        exits.capture_exits(repo, snap, [LAW], expected_head=parent)
        if damage != "not_deleted": (repo / LAW).unlink()
    git(repo, "add", "--all")
    if damage == "object_not_staged":
        git(repo, "restore", "--staged", "reader-exits/objects")
    elif damage == "moved_head":
        # A new commit containing the staged capture is not the required parent.
        commit(repo, "unexpected commit")
    with pytest.raises(ValueError):
        exits.verify_staged_exits(repo, expected_head=parent)


def test_existing_capture_is_immutable_and_reentry_creates_another(repo, tmp_path):
    snap = snapshot(tmp_path)
    format_all_laws(str(snap), str(repo), capture_repository=repo)
    first = exits.load_capture_records(repo)
    first_commit = commit(repo, "first exit")
    (repo / LAW).write_bytes(OLD[LAW])
    commit(repo, "reader reentry")
    format_all_laws(str(snap), str(repo), capture_repository=repo)
    second = exits.load_capture_records(repo)
    assert len(second) == 3 and all(row in second for row in first)
    assert len({row["capture_id"] for row in second if row["source_path"] == LAW}) == 2
    git(repo, "add", "--all")
    exits.verify_staged_exits(repo)
    second_commit = commit(repo, "second exit")
    versions = published_captures(repo)["lov/1981-05-29-38"]
    assert [row["creationCommit"] for row in versions] == [second_commit, first_commit]
    assert len({row["captureId"] for row in versions}) == 2
    record = repo / "reader-exits/records" / f'{first[0]["capture_id"]}.json'
    record.write_bytes(record.read_bytes().replace(b'"unknown"', b'"known"'))
    git(repo, "add", str(record))
    with pytest.raises(ValueError): exits.verify_staged_exits(repo)


def test_symlink_candidate_fails_without_pruning(repo, tmp_path):
    target = repo / LAW
    target.unlink()
    try:
        target.symlink_to(repo / REG)
    except OSError:
        pytest.skip("Symlink creation requires Windows developer mode or elevation")
    with pytest.raises(ValueError, match="[Ss]ymlink|[Rr]egular|[Rr]eparse"):
        format_all_laws(str(snapshot(tmp_path)), str(repo), capture_repository=repo)
    assert target.is_symlink() and (repo / REG).read_bytes() == OLD[REG]


def test_clean_checkout_newline_conversion_preserves_committed_bytes(repo, tmp_path):
    git(repo, "config", "core.autocrlf", "true")
    (repo / REG).write_bytes(OLD[REG].replace(b"\n", b"\r\n"))
    assert not git(repo, "diff", "--name-only", "HEAD", "--", REG)
    rows = exits.capture_exits(repo, snapshot(tmp_path), [REG])
    assert (repo / rows[0]["object_path"]).read_bytes() == OLD[REG]


def test_present_document_cannot_be_captured_as_absent(repo, tmp_path):
    path = "lover/lov-2020-01-01-1.md"
    (repo / path).write_bytes(b"# Existing current reader\n")
    commit(repo)
    with pytest.raises(ValueError, match="absence scope"):
        exits.capture_exits(repo, snapshot(tmp_path), [path])
    assert not (repo / "reader-exits").exists()


def test_head_movement_during_capture_prevents_current_writes(repo, tmp_path, monkeypatch):
    original = exits._write_immutable
    moved = False
    def moving_write(*args, **kwargs):
        nonlocal moved
        original(*args, **kwargs)
        if not moved:
            git(repo, "commit", "--allow-empty", "-m", "concurrent HEAD movement")
            moved = True
    monkeypatch.setattr(exits, "_write_immutable", moving_write)
    with pytest.raises(ValueError, match="HEAD moved"):
        format_all_laws(str(snapshot(tmp_path)), str(repo), capture_repository=repo)
    assert all((repo / p).read_bytes() == data for p, data in OLD.items())
    assert not (repo / "lover/lov-2020-01-01-1.md").exists()


def test_staged_capture_must_bind_the_supplied_snapshot(repo, tmp_path):
    first = snapshot(tmp_path)
    format_all_laws(str(first), str(repo), capture_repository=repo)
    git(repo, "add", "--all")
    other = tmp_path / "other-input"
    other.mkdir()
    with pytest.raises(ValueError, match="different absence snapshot"):
        exits.verify_staged_exits(repo, snapshot_dir=snapshot(other))
