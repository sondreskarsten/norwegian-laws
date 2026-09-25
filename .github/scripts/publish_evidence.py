"""Publish and read back an append-only, content-addressed source observation.

GitHub Releases provide durable downloads without another storage credential.
Hash addressing detects replacement; this is not a claim of physical WORM storage.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile
import urllib.request

from lovdata_publisher.snapshot import validate_snapshot


def canonical(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_artifact(root: Path, name: str) -> Path:
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name:
        raise ValueError(f'Unsafe evidence path: {name}')
    path = root / name
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Missing or escaped evidence path: {name}')
    if any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)()
           for p in [path, *path.parents] if p == root or root in p.parents):
        raise ValueError(f'Linked evidence path: {name}')
    return path


def prepare(snapshot: Path, output: Path, source_sha: str, repository: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha):
        raise ValueError('Expected a full source commit SHA')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Expected owner/repository')
    manifest = validate_snapshot(snapshot)
    if manifest['version'] != 4:
        raise ValueError('Durable evidence requires a version-4 snapshot with raw sources')
    output.mkdir(parents=True, exist_ok=True)
    bundle = output / 'snapshot.tar.gz'
    files = sorted({'manifest.json', *manifest['artifact_hashes']})
    # Fixed container metadata: identical artifact bytes produce identical bundles.
    with bundle.open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=6) as zipped:
            with tarfile.open(fileobj=zipped, mode='w', format=tarfile.PAX_FORMAT) as tar:
                for name in files:
                    path = safe_artifact(snapshot, name)
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                    with path.open('rb') as stream:
                        tar.addfile(info, stream)
    receipt = {
        'version': 1, 'contract': 'lovdata-observation-release-v1',
        'repository': repository, 'source_sha': source_sha,
        'snapshot_version': manifest['version'],
        'snapshot_manifest_sha256': digest(snapshot / 'manifest.json'),
        'bundle': {'name': bundle.name, 'sha256': digest(bundle), 'bytes': bundle.stat().st_size},
        'member_count': len(files),
        'data_attribution': {'provider': 'Lovdata', 'license': 'NLOD 2.0',
                             'license_url': 'https://data.norge.no/nlod/no/2.0'},
        'interpretation': 'Observed source and parsed projection; not an authoritative legal-as-of reconstruction',
    }
    identity = hashlib.sha256(canonical(receipt)).hexdigest()
    receipt['observation_id'] = identity
    receipt['release_tag'] = 'observation-' + identity
    base = f'https://github.com/{repository}/releases/download/{receipt["release_tag"]}/'
    receipt['bundle']['url'] = base + bundle.name
    receipt['receipt_url'] = base + 'evidence.json'
    (output / 'evidence.json').write_bytes(canonical(receipt))
    return receipt


def api(endpoint: str, payload: dict | None = None, *, missing_ok: bool = False):
    command = ['gh', 'api', '--hostname', 'github.com', endpoint]
    if payload is not None:
        command += ['--method', 'POST', '--input', '-']
    result = subprocess.run(command, input=canonical(payload) if payload is not None else None,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        if missing_ok and b'HTTP 404' in result.stderr:
            return None
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return json.loads(result.stdout)


def download_hash(url: str) -> tuple[str, int]:
    checksum, size = hashlib.sha256(), 0
    with urllib.request.urlopen(url, timeout=120) as stream:
        while chunk := stream.read(1024 * 1024):
            checksum.update(chunk)
            size += len(chunk)
    return checksum.hexdigest(), size


def find_release(endpoint: str, tag: str):
    release = api(f'{endpoint}/tags/{tag}', missing_ok=True)
    if release is not None:
        return release
    # Drafts are not consistently returned by the published-tag endpoint.
    # Resume the same draft after an interrupted upload instead of duplicating it.
    page = 1
    while True:
        releases = api(f'{endpoint}?per_page=100&page={page}')
        matches = [item for item in releases if item['tag_name'] == tag]
        if len(matches) > 1:
            raise ValueError('Ambiguous existing observation releases')
        if matches:
            return api(f'{endpoint}/{matches[0]["id"]}')
        if len(releases) < 100:
            return None
        page += 1


def publish(output: Path) -> dict:
    receipt = json.loads((output / 'evidence.json').read_bytes())
    bundle = output / 'snapshot.tar.gz'
    if (receipt.get('contract') != 'lovdata-observation-release-v1'
            or receipt['bundle'].get('name') != bundle.name
            or receipt['bundle'].get('sha256') != digest(bundle)
            or receipt['bundle'].get('bytes') != bundle.stat().st_size):
        raise ValueError('Local evidence bundle no longer matches its receipt')
    repository, tag = receipt['repository'], receipt['release_tag']
    endpoint = f'repos/{repository}/releases'
    reference = api(f'repos/{repository}/git/ref/tags/{tag}', missing_ok=True)
    if reference is not None and (reference['object'].get('sha') != receipt['source_sha']
                                   or reference['object'].get('type') != 'commit'):
        raise ValueError('Existing observation tag identifies another commit')
    release = find_release(endpoint, tag)
    if release is None:
        release = api(endpoint, {
            'tag_name': tag, 'target_commitish': receipt['source_sha'],
            'name': 'Source observation ' + receipt['observation_id'][:12],
            'body': ('Content-addressed Lovdata source evidence and versioned parsed snapshot. '
                     'The snapshot manifest binds every included artifact and raw archive. '
                     'Dates in the parsed projection are not verified historical legal validity.\n\n'
                     'Data: Lovdata, NLOD 2.0. See evidence.json for identities and attribution.\n\n'
                     'Existing assets are never overwritten by this workflow.'),
            'draft': True, 'prerelease': False, 'make_latest': 'false',
        })
    # A pre-existing release must identify this exact generation.
    if release.get('target_commitish') != receipt['source_sha']:
        raise ValueError('Existing evidence release targets another source commit')
    remote = {asset['name']: asset for asset in release['assets']}
    expected = {'snapshot.tar.gz', 'evidence.json'}
    if set(remote) - expected:
        raise ValueError('Unexpected evidence release assets')
    for name in sorted(expected):
        path = output / name
        if name not in remote:
            if not release['draft']:
                raise ValueError('Published evidence is incomplete; refuse to mutate it')
            subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo',
                            f'https://github.com/{repository}'], check=True)
            refreshed = api(f'{endpoint}/{release["id"]}')
            remote = {asset['name']: asset for asset in refreshed['assets']}
        with tempfile.TemporaryDirectory(prefix='evidence-readback-') as temp:
            download = Path(temp) / name
            with download.open('wb') as stream:
                subprocess.run(['gh', 'api', '--hostname', 'github.com',
                                f'{endpoint}/assets/{remote[name]["id"]}',
                                '-H', 'Accept: application/octet-stream'], stdout=stream, check=True)
            if digest(download) != digest(path):
                raise ValueError(f'Evidence asset differs; refuse overwrite: {name}')
    if release['draft']:
        subprocess.run(['gh', 'release', 'edit', tag, '--draft=false', '--latest=false',
                        '--repo', f'https://github.com/{repository}'], check=True)
    reference = api(f'repos/{repository}/git/ref/tags/{tag}')
    if (reference['object'].get('sha') != receipt['source_sha']
            or reference['object'].get('type') != 'commit'):
        raise ValueError('Published observation tag does not identify the exact source commit')
    # Read as an independent unauthenticated consumer after publication.
    for name in sorted(expected):
        path = output / name
        actual = download_hash(f'https://github.com/{repository}/releases/download/{tag}/{name}')
        if actual != (digest(path), path.stat().st_size):
            raise ValueError(f'Public evidence readback differs: {name}')
    print(json.dumps({'release': f'https://github.com/{repository}/releases/tag/{tag}',
                      'public_readback': True, 'observation_id': receipt['observation_id']}))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    prepare(args.snapshot, args.output, args.source_sha, args.repository)
    if args.publish:
        publish(args.output)
