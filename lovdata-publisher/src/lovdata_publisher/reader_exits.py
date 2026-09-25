"""Append-only copies of committed reader Markdown before observed corpus exits.

These are derived reader copies, not raw source observations or legal history.
An absence observation precedes pruning; the later Git commit proves which
deletions were actually published. Its SHA is deliberately not self-embedded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile


SCHEMA = "reader-exit-capture-v1"
ARCHIVE = "reader-exits"
SOURCE_REPOSITORY = "sondreskarsten/norwegian-laws"
_CORPUS = re.compile(r"(lover/lov-|forskrifter/forskrift-)(\d{4}-\d{2}-\d{2}(?:-\d+)?)\.md")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SHA1 = re.compile(r"[0-9a-f]{40}")
_UNKNOWN = ("source_observation", "source_knowledge_time", "legal_repeal", "legal_effective_date")
_FIELDS = {"schema", "capture_id", "artifact_kind", "refid", "title", "source_repository",
           "source_git_commit", "source_path", "git_blob_sha1", "sha256", "bytes", "object_path",
           "observed_absent_at", "exit_basis", "absence_snapshot", "legal_validity", *_UNKNOWN}


def _json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _git(repository: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(repository), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError(f"Reader capture Git check failed ({args[0]}): " +
                         result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _repository(repository: str | Path) -> Path:
    root = Path(repository).resolve(strict=True)
    actual = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != root:
        raise ValueError("Reader capture repository must be the Git worktree root")
    return root


def git_head(repository: str | Path) -> str:
    """Return the actual starting commit without changing Git metadata."""
    return _git(_repository(repository), "rev-parse", "HEAD").decode().strip()


def assert_head(repository: str | Path, expected_head: str) -> None:
    if not _SHA1.fullmatch(expected_head) or git_head(repository) != expected_head:
        raise ValueError("Reader capture HEAD moved or does not match expected_head")


def _safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative).parts
    if not parts or relative != "/".join(parts) or any(p in {".", ".."} or ":" in p or "\\" in p for p in parts):
        raise ValueError("Invalid reader capture path")
    target = root
    for part in parts:
        target = target / part
        if target.is_symlink() or getattr(target, "is_junction", lambda: False)():
            raise ValueError(f"Symlink or reparse path cannot hold a reader capture: {relative}")
    if root not in target.resolve().parents:
        raise ValueError("Reader capture path escapes the repository")
    return target


def _corpus_path(path: str) -> tuple[str, str]:
    match = _CORPUS.fullmatch(path)
    if not match:
        raise ValueError(f"Not a reader corpus path: {path}")
    role, kind = ("laws", "lov") if path.startswith("lover/") else ("forskrifter", "forskrift")
    return role, f"{kind}/{match[2]}"


def _changes(root: Path, *, staged: bool) -> dict[str, str]:
    args = ["diff", "--name-status", "-z", "--no-renames"]
    args += ["--cached"] if staged else ["HEAD"]
    fields = _git(root, *args, "--", ARCHIVE, "lover", "forskrifter").decode("utf-8").split("\0")
    if fields[-1] == "": fields.pop()
    if len(fields) % 2: raise ValueError("Invalid Git change inventory")
    return {fields[i + 1]: fields[i] for i in range(0, len(fields), 2)}


def _append_only(root: Path) -> None:
    for path, status in _changes(root, staged=False).items():
        if path.startswith(ARCHIVE + "/") and status != "A":
            raise ValueError(f"Existing reader capture must remain unchanged: {path}")


def _committed_blob(root: Path, head: str, path: str) -> tuple[str, bytes]:
    entry = _git(root, "ls-tree", "-z", head, "--", path).decode("utf-8").rstrip("\0")
    if not entry:
        raise ValueError(f"Reader capture candidate is untracked at the expected HEAD: {path}")
    metadata, actual_path = entry.split("\t", 1)
    mode, kind, oid = metadata.split()
    if actual_path != path or kind != "blob" or mode not in {"100644", "100755"}:
        raise ValueError(f"Reader capture candidate must be a regular Git blob: {path}")
    return oid, _git(root, "cat-file", "blob", oid)


def _snapshot_context(snapshot_dir: Path, manifest: dict) -> tuple[str, dict]:
    # The public capture API validates the whole snapshot. The formatter uses
    # this helper after its own full validation, avoiding a second raw replay.
    data = (snapshot_dir / "manifest.json").read_bytes()
    if manifest.get("version") != 4 or json.loads(data) != manifest:
        raise ValueError("Reader exit capture requires an unchanged validated v4 snapshot")
    evidence = manifest["evidence"]
    observations_path = evidence["observations"]
    members_path = evidence["members"]
    observations_bytes = (snapshot_dir / observations_path).read_bytes()
    hashes = manifest["artifact_hashes"]
    if _sha256(observations_bytes) != hashes[observations_path]:
        raise ValueError("Reader exit source observations changed after validation")
    observations = json.loads(observations_bytes)
    return _sha256(data), {
        "source_observations_sha256": hashes[observations_path],
        "source_members_sha256": hashes[members_path],
        "archives": observations["archives"],
        "manifest": manifest,
    }


def _absence_identity(manifest_sha: str, context: dict, path: str) -> dict:
    role, refid = _corpus_path(path)
    model_path = f"{role}/{refid.replace('/', '-')}.json"
    manifest = context["manifest"]
    count = "law_count" if role == "laws" else "forskrift_count"
    archives = sorted({row["archive_sha256"] for row in context["archives"] if row["role"] == role})
    if model_path in manifest["artifact_hashes"] or not manifest[count] or not archives:
        raise ValueError(f"Reader exit lacks a populated validated absence scope: {path}")
    return {"manifest_sha256": manifest_sha,
            "source_observations_sha256": context["source_observations_sha256"],
            "source_members_sha256": context["source_members_sha256"],
            "corpus_role": role, "archive_sha256s": archives}


def _capture_id(row: dict) -> str:
    return _sha256(_json([SCHEMA, row["source_git_commit"], row["absence_snapshot"]["manifest_sha256"],
                         row["source_path"], row["sha256"]]))


def _validate_record(row: dict, path: Path, root: Path) -> bytes:
    try:
        role, refid = _corpus_path(row["source_path"])
        absence = row["absence_snapshot"]
        observed = datetime.fromisoformat(row["observed_absent_at"])
        valid = (set(row) == _FIELDS and row["schema"] == SCHEMA
                 and row["artifact_kind"] == "derived_reader_markdown"
                 and row["source_repository"] == SOURCE_REPOSITORY and row["refid"] == refid
                 and isinstance(row["title"], str) and bool(row["title"].strip())
                 and _SHA1.fullmatch(row["source_git_commit"]) and _SHA1.fullmatch(row["git_blob_sha1"])
                 and _SHA256.fullmatch(row["sha256"]) and row["capture_id"] == _capture_id(row)
                 and path.name == row["capture_id"] + ".json"
                 and row["object_path"] == f'{ARCHIVE}/objects/sha256/{row["sha256"]}.md'
                 and type(row["bytes"]) is int and row["bytes"] >= 0
                 and observed.utcoffset() == timezone.utc.utcoffset(observed)
                 and row["exit_basis"] == "validated_snapshot_absence" and row["legal_validity"] == "unknown"
                 and all(row[field] is None for field in _UNKNOWN)
                 and set(absence) == {"manifest_sha256", "source_observations_sha256", "source_members_sha256", "corpus_role", "archive_sha256s"}
                 and absence["corpus_role"] == role
                 and all(_SHA256.fullmatch(absence[key]) for key in ("manifest_sha256", "source_observations_sha256", "source_members_sha256"))
                 and isinstance(absence["archive_sha256s"], list) and bool(absence["archive_sha256s"])
                 and absence["archive_sha256s"] == sorted(set(absence["archive_sha256s"]))
                 and all(_SHA256.fullmatch(item) for item in absence["archive_sha256s"]))
        if not valid: raise ValueError("Invalid record fields")
        target = _safe_path(root, row["object_path"])
        if not target.is_file(): raise ValueError("Missing regular reader object")
        data = target.read_bytes()
        if len(data) != row["bytes"] or _sha256(data) != row["sha256"] or _blob_sha1(data) != row["git_blob_sha1"]:
            raise ValueError("Reader object byte identity mismatch")
        return data
    except (KeyError, TypeError, AttributeError, ValueError, OSError) as exc:
        raise ValueError(f"Invalid reader capture {path.name}: {exc}") from exc


def load_capture_records(repository: str | Path) -> list[dict]:
    """Validate the append-only collection's records and exact object bytes.

    This does not claim that a record was committed or its deletion published;
    consumers establish those facts against their checked-out source commit.
    """
    root = _repository(repository)
    directory = _safe_path(root, f"{ARCHIVE}/records")
    if not directory.exists(): return []
    if not directory.is_dir(): raise ValueError("Reader capture records path must be a directory")
    result = []
    for path in sorted(directory.iterdir()):
        _safe_path(root, path.relative_to(root).as_posix())
        if not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
            raise ValueError(f"Invalid reader capture record path: {path.name}")
        try: row = json.loads(path.read_bytes())
        except (ValueError, OSError) as exc: raise ValueError(f"Invalid reader capture JSON: {path.name}") from exc
        _validate_record(row, path, root)
        result.append(row)
    return result


def _write_immutable(root: Path, relative: str, data: bytes) -> None:
    target = _safe_path(root, relative)
    if target.exists():
        if not target.is_file() or target.read_bytes() != data:
            raise ValueError(f"Refusing to replace a reader capture: {relative}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".capture-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic create without overwrite on both Windows and POSIX filesystems.
        try: os.link(temporary, target)
        except FileExistsError:
            if target.read_bytes() != data: raise ValueError(f"Conflicting reader capture: {relative}")
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)
    if target.read_bytes() != data: raise ValueError(f"Reader capture readback failed: {relative}")


def _capture_validated(repository: str | Path, snapshot_dir: str | Path, stale_paths,
                       *, expected_head: str, manifest: dict) -> list[dict]:
    root, snapshot = _repository(repository), Path(snapshot_dir)
    assert_head(root, expected_head)
    _append_only(root)
    existing = {row["capture_id"]: row for row in load_capture_records(root)}
    manifest_sha, context = _snapshot_context(snapshot, manifest)
    pending = []
    # Validate every candidate before writing even the first archive object.
    for path in sorted(set(stale_paths)):
        _, refid = _corpus_path(path)
        target = _safe_path(root, path)
        if not target.is_file(): raise ValueError(f"Reader capture requires a regular existing file: {path}")
        oid, data = _committed_blob(root, expected_head, path)
        # Compare the index and actual working content, including Git's newline
        # conversion. Merely asking for a diff can trust assume-unchanged flags.
        indexed = _git(root, "rev-parse", f":{path}").decode().strip()
        working = _git(root, "hash-object", "--path", path, "--", path).decode().strip()
        if indexed != oid or working != oid or _git(root, "diff", "--name-only", "HEAD", "--", path):
            raise ValueError(f"Reader capture candidate is dirty or staged: {path}")
        digest = _sha256(data)
        title = next((line[2:].strip() for line in data.decode("utf-8", errors="replace").splitlines()
                      if line.startswith("# ") and line[2:].strip()), refid)
        row = {"schema": SCHEMA, "artifact_kind": "derived_reader_markdown", "refid": refid, "title": title,
               "source_repository": SOURCE_REPOSITORY, "source_git_commit": expected_head, "source_path": path,
               "git_blob_sha1": oid, "sha256": digest, "bytes": len(data),
               "object_path": f"{ARCHIVE}/objects/sha256/{digest}.md",
               "observed_absent_at": datetime.now(timezone.utc).isoformat(),
               "exit_basis": "validated_snapshot_absence", "absence_snapshot": _absence_identity(manifest_sha, context, path),
               "legal_validity": "unknown", **dict.fromkeys(_UNKNOWN)}
        row["capture_id"] = _capture_id(row)
        if row["capture_id"] in existing:
            row["observed_absent_at"] = existing[row["capture_id"]]["observed_absent_at"]
            if row != existing[row["capture_id"]]: raise ValueError("Conflicting existing reader capture")
        pending.append((row, data))
    assert_head(root, expected_head)
    for row, data in pending:
        _write_immutable(root, row["object_path"], data)
        record_path = f'{ARCHIVE}/records/{row["capture_id"]}.json'
        _write_immutable(root, record_path, _json(row))
        _validate_record(row, root / record_path, root)
    assert_head(root, expected_head)
    return [row for row, _ in pending]


def capture_exits(repository: str | Path, snapshot_dir: str | Path, stale_paths,
                  *, expected_head: str | None = None) -> list[dict]:
    """Retain exact committed readers absent from a fully validated v4 snapshot.

    Capture alone does not delete or stage anything. Replay of the same prior
    commit/snapshot/path/blob preserves the first recorded observation time.
    """
    from .snapshot import validate_snapshot
    head = expected_head or git_head(repository)
    assert_head(repository, head)
    manifest = validate_snapshot(snapshot_dir)
    return _capture_validated(repository, snapshot_dir, stale_paths, expected_head=head, manifest=manifest)


def verify_staged_exits(repository: str | Path, *, expected_head: str | None = None,
                        snapshot_dir: str | Path | None = None) -> dict:
    """Require an exact parent blob capture for every staged corpus deletion."""
    root = _repository(repository)
    head = expected_head or git_head(root)
    assert_head(root, head)
    _append_only(root)
    records = {row["capture_id"]: row for row in load_capture_records(root)}
    changes = _changes(root, staged=True)
    deletions = {path for path, status in changes.items() if status == "D" and _CORPUS.fullmatch(path)}
    captured, object_paths = set(), set()
    context = None
    if snapshot_dir is not None:
        from .snapshot import validate_snapshot
        snapshot = Path(snapshot_dir)
        context = _snapshot_context(snapshot, validate_snapshot(snapshot))
    for path, status in changes.items():
        if not path.startswith(ARCHIVE + "/"): continue
        if status != "A": raise ValueError(f"Reader archive changes must be additions: {path}")
        if not re.fullmatch(r"reader-exits/(?:records/[0-9a-f]{64}\.json|objects/sha256/[0-9a-f]{64}\.md)", path):
            raise ValueError(f"Unexpected staged reader archive path: {path}")
        if _git(root, "show", f":{path}") != _safe_path(root, path).read_bytes():
            raise ValueError(f"Reader capture index differs from working bytes: {path}")
        if not path.startswith(f"{ARCHIVE}/records/"): continue
        row = records.get(Path(path).stem)
        if row is None or row["source_git_commit"] != head or row["source_path"] not in deletions:
            raise ValueError(f"Reader capture is not bound to this staged exit: {path}")
        if row["source_path"] in captured: raise ValueError("Duplicate staged reader exit")
        oid, data = _committed_blob(root, head, row["source_path"])
        if oid != row["git_blob_sha1"] or data != _git(root, "show", f':{row["object_path"]}'):
            raise ValueError(f"Staged reader object differs from its actual Git parent: {path}")
        if context is not None and row["absence_snapshot"] != _absence_identity(*context, row["source_path"]):
            raise ValueError(f"Staged reader capture uses a different absence snapshot: {path}")
        captured.add(row["source_path"])
        object_paths.add(row["object_path"])
    if captured != deletions:
        raise ValueError("Staged corpus deletions lack exact reader captures: " + ", ".join(sorted(deletions - captured)))
    added_objects = {path for path in changes if path.startswith(f"{ARCHIVE}/objects/")}
    if added_objects - object_paths:
        raise ValueError("Staged reader objects lack a matching new capture")
    assert_head(root, head)
    return {"source_git_commit": head, "capture_count": len(captured), "source_paths": sorted(captured)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-staged")
    verify.add_argument("--repository", type=Path, required=True)
    verify.add_argument("--expected-head")
    verify.add_argument("--snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_staged_exits(args.repository, expected_head=args.expected_head, snapshot_dir=args.snapshot)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Reader exit verification failed: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
