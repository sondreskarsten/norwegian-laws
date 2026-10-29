"""Bind every publication commit to its source archives and parser identity.

The main branch must be a pure function of (Lovdata source archives, parser
code). This script keeps that true:

- ``plan``       decides whether the sources changed, whether the parser changed,
                 and whether the previous sources must be regenerated first.
- ``fetch-previous`` restores the previously published source archives from the
                 public observation bundle so a parser change can be committed
                 on unchanged sources, separately from the next source update.
- ``verify-reproducible`` formats the snapshot a second time into a scratch
                 directory and refuses to continue if the output differs from
                 the working tree.
- ``message``    writes the commit message: a subject that names the kind of
                 change, the optional AI summary, and provenance trailers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import urllib.request

PARSER_PATHS = ("lovdata-loader", "lovdata-publisher")
PARSER_OUTPUT_DIRS = ("lover", "forskrifter", "historie")
SUBJECTS = {
    "source": "Oppdater lover og forskrifter fra Lovdata API {date} [skip ci]",
    "parser": "Regenerer lover og forskrifter med endret parser {date} [skip ci]",
}


def git(*args: str, cwd: str | Path = ".") -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True, check=True).stdout.strip()


def canonical_sha256(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _ensure_commit(ref: str, repo: str | Path) -> None:
    """A shallow checkout may lack the acknowledged commit; fetch just that one."""
    probe = subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], cwd=str(repo), capture_output=True)
    if probe.returncode == 0:
        return
    subprocess.run(["git", "fetch", "--quiet", "--depth=1", "origin", ref], cwd=str(repo), check=True,
                   capture_output=True)


def parser_identity(ref: str = "HEAD", repo: str | Path = ".") -> dict:
    """Tree hashes of the code that produces the published files."""
    if ref != "HEAD":
        _ensure_commit(ref, repo)
    return {name: git("rev-parse", f"{ref}:{name}", cwd=repo) for name in PARSER_PATHS}


def parser_changed(previous_sha: str, repo: str | Path = ".") -> bool:
    if not previous_sha:
        return True
    return parser_identity(previous_sha, repo) != parser_identity("HEAD", repo)


def plan(state_path: Path, live_manifest: list[dict], repo: str | Path = ".") -> dict:
    """Classify the pending publication against the acknowledged one."""
    from lovdata_loader.download import select_source_manifest
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    published_manifest = select_source_manifest(state["source_manifest"]) if state.get("source_manifest") else []
    live = select_source_manifest(live_manifest)
    previous_sha = state.get("source_sha", "")
    changed_parser = parser_changed(previous_sha, repo)
    changed_source = live != published_manifest
    evidence = state.get("evidence") or {}
    return {
        "previous_source_sha": previous_sha,
        "previous_identity": parser_identity(previous_sha, repo) if previous_sha else {},
        "identity": parser_identity("HEAD", repo),
        "source_changed": changed_source,
        "parser_changed": changed_parser,
        # Regenerate the old sources first only when both axes moved; a run
        # without a published receipt has nothing to regenerate from.
        "regenerate_previous": bool(changed_parser and changed_source and evidence.get("receipt_url")),
        "previous_receipt_url": evidence.get("receipt_url", ""),
        "previous_bundle_sha256": evidence.get("bundle_sha256", ""),
        "published_manifest_sha256": canonical_sha256(published_manifest) if published_manifest else "",
        "live_manifest_sha256": canonical_sha256(live),
    }


def _download(url: str, target: Path) -> None:
    with urllib.request.urlopen(url, timeout=300) as stream, target.open("wb") as out:
        shutil.copyfileobj(stream, out, length=1 << 20)


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_previous(receipt_url: str, bundle_sha256: str, output: Path, bundle_file: Path | None = None) -> dict:
    """Restore the previously published archives under their original names.

    Returns the loader arguments: gjeldende, forskrifter and lovtidend paths.
    """
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="previous-sources-") as temp:
        temp = Path(temp)
        if bundle_file is None:
            receipt_path = temp / "evidence.json"
            _download(receipt_url, receipt_path)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt["bundle"]["sha256"] != bundle_sha256:
                raise ValueError("Published receipt names a different bundle than the acknowledged publication")
            bundle_file = temp / "snapshot.tar.gz"
            _download(receipt["bundle"]["url"], bundle_file)
        if _digest(bundle_file) != bundle_sha256:
            raise ValueError("Previous source bundle digest mismatch")
        with tarfile.open(bundle_file) as tar:
            members = {m.name: m for m in tar.getmembers() if m.isfile()}
            for name in ("source-observations.json", "source-manifest.json"):
                if name not in members:
                    raise ValueError(f"Bundle lacks {name}")
            observations = json.load(tar.extractfile(members["source-observations.json"]))
            manifest = json.load(tar.extractfile(members["source-manifest.json"]))
            paths: dict[str, str] = {}
            for archive in observations["archives"]:
                raw_path, filename = archive["raw_path"], archive["original_filename"]
                parts = PurePosixPath(filename)
                if parts.name != filename or filename in ("", ".", "..") or raw_path not in members:
                    raise ValueError(f"Unsafe or missing archive entry: {filename}")
                target = output / filename
                with tar.extractfile(members[raw_path]) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1 << 20)
                if _digest(target) != archive["archive_sha256"]:
                    raise ValueError(f"Archive digest mismatch for {filename}")
                paths[filename] = str(target)
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    from lovdata_loader.download import ARCHIVES
    result = {key: paths[name] for key, name in ARCHIVES.items()}
    result["lovtidend"] = sorted(path for name, path in paths.items() if name.startswith("lovtidend-avd1-"))
    return result


def _tree_digest(root: Path) -> dict[str, str]:
    files = {}
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(root))] = _digest(path)
    return files


def verify_reproducible(snapshot: Path, output: Path) -> list[str]:
    """Format the snapshot again elsewhere and list every differing file."""
    differences = []
    with tempfile.TemporaryDirectory(prefix="law-repro-") as temp:
        subprocess.run([sys.executable, "-m", "lovdata_publisher.cli", "--snapshot", str(snapshot),
                        "--output", temp, "--format-only"], check=True, capture_output=True)
        for name in PARSER_OUTPUT_DIRS:
            committed = _tree_digest(output / name)
            again = _tree_digest(Path(temp) / name)
            if name == "lover":
                committed.pop("README.md", None)
                again.pop("README.md", None)
            for rel in sorted(set(committed) | set(again)):
                if committed.get(rel) != again.get(rel):
                    differences.append(f"{name}/{rel}")
    return differences


def message(kind: str, date: str, manifest_path: Path, identity: dict, previous_identity: dict,
            summary_file: Path | None = None) -> str:
    from lovdata_loader.download import select_source_manifest
    manifest = select_source_manifest(json.loads(manifest_path.read_text(encoding="utf-8")))
    lines = [SUBJECTS[kind].format(date=date), ""]
    if summary_file is not None and summary_file.exists():
        body = summary_file.read_text(encoding="utf-8").split("\n", 1)
        if len(body) == 2 and body[1].strip():
            lines += [body[1].strip(), ""]
    if kind == "parser":
        lines += ["Kildearkivene er uendret; bare parser- eller formateringskoden er ny. "
                  "Tekstforskjeller i denne commiten er ikke lovendringer.", ""]
    lines.append(f"Publikasjonstype: {'kilde' if kind == 'source' else 'parser'}")
    lines.append(f"Kildemanifest: sha256:{canonical_sha256(manifest)}")
    for entry in manifest:
        lines.append(f"Kildearkiv: {entry['filename']} {entry['lastModified']} {entry['sizeBytes']}")
    for name in PARSER_PATHS:
        before = previous_identity.get(name, "")
        lines.append(f"Parser: {name} {identity[name]}" + (f" (var {before})" if before and before != identity[name] else ""))
    return "\n".join(lines) + "\n"


def _write_outputs(values: dict) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as out:
        for key, value in values.items():
            out.write(f"{key}={value}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--state", type=Path, default=Path(".github/state/publication.json"))
    p.add_argument("--manifest", type=Path, help="Live manifest JSON; fetched from Lovdata when omitted")
    p.add_argument("--output", type=Path, required=True)

    p = sub.add_parser("fetch-previous")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--bundle-file", type=Path)

    p = sub.add_parser("verify-reproducible")
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("."))

    p = sub.add_parser("message")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--kind", choices=sorted(SUBJECTS), required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--summary-file", type=Path)
    p.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    p.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "plan":
        if args.manifest:
            live = json.loads(args.manifest.read_text(encoding="utf-8"))
        else:
            from lovdata_loader.download import fetch_source_manifest
            live = fetch_source_manifest()
        result = plan(args.state, live)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        _write_outputs({k: str(v).lower() if isinstance(v, bool) else v for k, v in result.items()
                        if k in ("source_changed", "parser_changed", "regenerate_previous")})
        print(json.dumps({k: v for k, v in result.items() if k not in ("identity", "previous_identity")}, indent=2))
    elif args.command == "fetch-previous":
        current = json.loads(args.plan.read_text(encoding="utf-8"))
        paths = fetch_previous(current["previous_receipt_url"], current["previous_bundle_sha256"],
                               args.output, args.bundle_file)
        _write_outputs({"gjeldende": paths["gjeldende"], "forskrifter": paths["forskrifter"],
                        "lovtidend": " ".join(paths["lovtidend"])})
        print(json.dumps(paths, indent=2))
    elif args.command == "verify-reproducible":
        differences = verify_reproducible(args.snapshot, args.output)
        if differences:
            print("Formatting the same snapshot twice produced different files:", file=sys.stderr)
            for rel in differences[:50]:
                print(f"  {rel}", file=sys.stderr)
            return 1
        print(f"Reproducible: {', '.join(PARSER_OUTPUT_DIRS)} identical on a second formatting pass")
    elif args.command == "message":
        current = json.loads(args.plan.read_text(encoding="utf-8"))
        text = message(args.kind, args.date, args.manifest, current["identity"], current.get("previous_identity", {}),
                       args.summary_file)
        args.output.write_text(text, encoding="utf-8")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
