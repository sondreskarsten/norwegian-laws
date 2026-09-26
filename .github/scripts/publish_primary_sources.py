"""Preserve acquired older primary sources through the existing evidence transport."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import tarfile
from datetime import datetime
from urllib.parse import urlsplit
from publish_evidence import canonical, digest, safe_artifact, publish

CONTRACT = 'primary-source-acquisition-release-v1'


def prepare(source: Path, output: Path, source_sha: str, repository: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):
        raise ValueError('Exact source commit and repository required')
    manifest_path=safe_artifact(source,'manifest.json')
    rows=json.loads(manifest_path.read_bytes())
    if not isinstance(rows,list) or not rows:raise ValueError('Nonempty acquisition manifest required')
    files={'manifest.json'}
    successes=0
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid acquisition record')
        url=urlsplit(row['url'])
        if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Public HTTPS source URL required')
        if datetime.fromisoformat(row['retrieved_at']).tzinfo is None:raise ValueError('Timezone required')
        if 'path' not in row:
            if not row.get('error'):raise ValueError('Missing acquisition outcome')
            continue
        path=safe_artifact(source,row['path'])
        if row.get('status')!=200 or row.get('bytes')!=path.stat().st_size or row.get('sha256')!=digest(path):
            raise ValueError('Acquired source bytes differ from manifest')
        if row['path'] in files:raise ValueError('Duplicate acquired artifact path')
        files.add(row['path']);successes+=1
    if not successes:raise ValueError('No successfully acquired sources')
    output.mkdir(parents=True,exist_ok=True)
    bundle=output/'snapshot.tar.gz'
    with bundle.open('xb') as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0,compresslevel=6) as zipped:
        with tarfile.open(fileobj=zipped,mode='w',format=tarfile.PAX_FORMAT) as tar:
            for name in sorted(files):
                path=safe_artifact(source,name);info=tarfile.TarInfo(name);info.size=path.stat().st_size;info.mode=0o644;info.mtime=0
                with path.open('rb') as stream:tar.addfile(info,stream)
    receipt={'version':1,'contract':CONTRACT,'repository':repository,'source_sha':source_sha,
             'snapshot_manifest_sha256':digest(manifest_path),'member_count':len(files),
             'acquired_sources':successes,'failed_attempts':len(rows)-successes,
             'bundle':{'name':bundle.name,'sha256':digest(bundle),'bytes':bundle.stat().st_size},
             'interpretation':'Acquired evidence only; no legal-date qualification. OCR is derived text; source-hosted printouts are not original gazette scans.',
             'data_attribution':{'basis':'Per-source URL and source documents; no blanket license assignment'}}
    identity=hashlib.sha256(canonical(receipt)).hexdigest();receipt['observation_id']=identity;receipt['release_tag']='primary-source-'+identity
    base=f'https://github.com/{repository}/releases/download/{receipt["release_tag"]}/'
    receipt['bundle']['url']=base+bundle.name;receipt['receipt_url']=base+'evidence.json'
    (output/'evidence.json').write_bytes(canonical(receipt));return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--source-sha',required=True);p.add_argument('--repository',required=True);p.add_argument('--publish',action='store_true');a=p.parse_args()
    receipt=prepare(a.source,a.output,a.source_sha,a.repository)
    if a.publish:publish(a.output,contract=CONTRACT)
    else:print(json.dumps(receipt))
