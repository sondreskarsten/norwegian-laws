"""Read a mirrored product back without relying on rsync's success message."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


def gsutil(*args: str) -> bytes:
    return subprocess.check_output(['gsutil', *args])


def verify(staged: Path, bucket: str) -> dict:
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]+[a-z0-9]', bucket):
        raise ValueError('Expected a bucket name without a URL or prefix')
    base = f'gs://{bucket}/'
    expected = {p.relative_to(staged).as_posix(): p for p in staged.rglob('*') if p.is_file()}
    if 'publication.json' not in expected or 'laws.json' not in expected:
        raise ValueError('Staged publication is incomplete')
    listing = gsutil('ls', base + '**').decode().splitlines()
    remote = {line[len(base):] for line in listing if line.startswith(base) and not line.endswith('/')}
    missing, extra = sorted(expected.keys() - remote), sorted(remote - expected.keys())
    if missing or extra:
        # Names are enough to diagnose accidental files; never read their bodies.
        raise RuntimeError(f'Mirror membership mismatch: missing={missing[:20]}, extra={extra[:20]}')
    suspect = [p for p in remote if PurePosixPath(p).name.startswith('gha-creds-')
               or PurePosixPath(p).name in {'.env', 'credentials.json'}]
    if suspect:
        raise RuntimeError(f'Unexpected runtime artifacts in mirror: {suspect}')
    samples = ['publication.json', 'laws.json']
    for prefix in ('lover/', 'forskrifter/'):
        documents = sorted(p for p in expected if p.startswith(prefix) and p.endswith('.md'))
        if not documents:
            raise ValueError(f'No document in staged {prefix}')
        samples.append(documents[0])
    readbacks = {}
    for name in samples:
        content = gsutil('cat', base + name)
        actual = hashlib.sha256(content).hexdigest()
        wanted = hashlib.sha256(expected[name].read_bytes()).hexdigest()
        if actual != wanted:
            raise RuntimeError(f'Mirror readback hash differs: {name}')
        readbacks[name] = {'sha256': actual, 'bytes': len(content)}
    return {'version': 1, 'source_sha': json.loads(expected['publication.json'].read_text())['source_sha'],
            'object_count': len(remote), 'exact_current_membership': True,
            'current_runtime_artifacts': 0, 'readbacks': readbacks,
            'scope': 'Authenticated current-object readback; not an audit of IAM or retained object versions'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staged', type=Path, required=True)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.staged, args.bucket)
    args.receipt.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))
