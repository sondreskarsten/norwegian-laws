"""Stage public Git content and verify the identity served by Pages."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request


PUBLIC_PATHS = {
    'README.md', 'LICENSE', 'CITATION.cff', 'RELEASES.md', 'SUBSCRIBE.md',
    'laws.json', 'lover', 'forskrifter', 'historie', '_quarto.yml',
    'index.qmd', 'book', 'assets',
}


def make_receipt(source_sha: str, manifest_path: Path | None = None,
                 evidence_path: Path | None = None) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path else None
    encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
    receipt = {'version': 1, 'source_sha': source_sha, 'source_manifest': manifest,
               'source_manifest_sha256': hashlib.sha256(encoded).hexdigest()}
    if evidence_path is not None:
        evidence = json.loads(evidence_path.read_bytes())
        if evidence.get('source_sha') != source_sha or evidence.get('contract') != 'lovdata-observation-release-v1':
            raise ValueError('Evidence release does not match the published source')
        receipt.update(version=2, evidence={
            'observation_id': evidence['observation_id'],
            'receipt_url': evidence['receipt_url'],
            'bundle_sha256': evidence['bundle']['sha256'],
            'snapshot_manifest_sha256': evidence['snapshot_manifest_sha256'],
        })
    return receipt


def matches_receipt(receipt: dict, source_sha: str, manifest_path: Path,
                    evidence_path: Path | None = None) -> bool:
    expected = make_receipt(source_sha, manifest_path, evidence_path)
    return isinstance(receipt, dict) and all(receipt.get(k) == v for k, v in expected.items())


def stage(repo: Path, output: Path) -> str:
    repo, output = repo.resolve(), output.resolve()
    if output == repo or output.is_relative_to(repo):
        raise ValueError('Publication staging must be outside the checkout')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Publication destination must be empty')
    sha = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    names = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-z', '--name-only', sha]).decode().split('\0')
    selected = sorted(PUBLIC_PATHS.intersection(names))
    if not selected:
        raise ValueError('No public product paths in commit')
    with tempfile.TemporaryDirectory(prefix='law-publication-') as temp:
        archive = Path(temp) / 'public.tar'
        subprocess.run(['git', '-C', str(repo), 'archive', '--format=tar', '-o', str(archive), sha, '--', *selected], check=True)
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            # Validate everything before writing anything. No symlinks/hardlinks.
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or '\\' in member.name or ':' in member.name:
                    raise ValueError(f'Unsafe publication path: {member.name}')
                if not (member.isdir() or member.isfile()):
                    raise ValueError(f'Non-regular publication entry: {member.name}')
                if path.name.startswith('gha-creds-') or path.name in {'.env', 'credentials.json'}:
                    raise ValueError(f'Unexpected credential artifact: {member.name}')
            output.mkdir(parents=True, exist_ok=True)
            for member in members:
                target = output / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as stream:
                        target.write_bytes(stream.read())
    (output / 'publication.json').write_text(json.dumps(make_receipt(sha), indent=2)+'\n', encoding='utf-8')
    return sha


def verify(url: str, source_sha: str, manifest_path: Path, *, evidence_path: Path | None = None,
           attempts: int = 30, delay: float = 10) -> None:
    for attempt in range(attempts):
        try:
            # Query and cache headers avoid accepting an old cached receipt.
            separator = '&' if '?' in url else '?'
            request = urllib.request.Request(f'{url}{separator}source={source_sha}', headers={'Cache-Control':'no-cache'})
            with urllib.request.urlopen(request, timeout=20) as response:
                receipt = json.loads(response.read())
            if matches_receipt(receipt, source_sha, manifest_path, evidence_path):
                return
        except (OSError, ValueError):
            pass
        if attempt + 1 < attempts:
            time.sleep(delay)
    raise RuntimeError(f'Published site did not serve the expected source identity after {attempts} checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    stage_parser = commands.add_parser('stage')
    stage_parser.add_argument('--output', type=Path, required=True)
    stage_parser.add_argument('--repo', type=Path, default=Path.cwd())
    receipt_parser = commands.add_parser('receipt')
    receipt_parser.add_argument('--sha', required=True)
    receipt_parser.add_argument('--manifest', type=Path, required=True)
    receipt_parser.add_argument('--output', type=Path, required=True)
    receipt_parser.add_argument('--evidence', type=Path)
    verify_parser = commands.add_parser('verify')
    verify_parser.add_argument('--sha', required=True)
    verify_parser.add_argument('--manifest', type=Path, required=True)
    verify_parser.add_argument('--url', required=True)
    verify_parser.add_argument('--evidence', type=Path)
    args = parser.parse_args()
    if args.command == 'stage':
        print(stage(args.repo, args.output))
    elif args.command == 'receipt':
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(make_receipt(args.sha, args.manifest, args.evidence), indent=2)+'\n', encoding='utf-8')
    else:
        verify(args.url, args.sha, args.manifest, evidence_path=args.evidence)


if __name__ == '__main__':
    main()
