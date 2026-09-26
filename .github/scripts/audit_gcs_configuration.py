"""Read-only audit of optional mirror retention and access; never changes policy."""
import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def audit(bucket):
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]',bucket):raise ValueError('Invalid bucket name')
    token=subprocess.run(['gcloud','auth','print-access-token'],capture_output=True,text=True,check=True).stdout.strip()
    base='https://storage.googleapis.com/storage/v1/b/'+urllib.parse.quote(bucket,safe='')
    result={'bucket':bucket,'checked_at':datetime.now(timezone.utc).isoformat(),'mode':'read_only','limitations':[]}
    def get(suffix, parameters=None):
        url=base+suffix
        if parameters:url+='?'+urllib.parse.urlencode(parameters)
        request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)
    try:
        metadata=get('',{'fields':'versioning,retentionPolicy,softDeletePolicy,lifecycle,iamConfiguration'})
        result['configuration']=metadata
    except urllib.error.HTTPError as exc:
        result['limitations'].append({'check':'bucket_configuration','http_status':exc.code})
    try:
        policy=get('/iam',{'optionsRequestedPolicyVersion':'3'})
        bindings=policy.get('bindings',[])
        result['access']={'policy_version':policy.get('version',1),
          'binding_count':len(bindings),
          'public_bindings':[{'role':b.get('role'),'principals':[m for m in b.get('members',[]) if m in {'allUsers','allAuthenticatedUsers'}],'conditional':bool(b.get('condition'))} for b in bindings if any(m in {'allUsers','allAuthenticatedUsers'} for m in b.get('members',[]))],
          'nonpublic_principal_count':len({m for b in bindings for m in b.get('members',[]) if m not in {'allUsers','allAuthenticatedUsers'}}),
          'scope':'Bucket IAM only; inherited project policies, object ACLs and effective caller access are not established'}
    except urllib.error.HTTPError as exc:
        result['limitations'].append({'check':'bucket_iam','http_status':exc.code})
    try:
        counts={'all_generations':0,'live_generations':0,'noncurrent_generations':0};page=None
        while True:
            query={'versions':'true','maxResults':1000,'fields':'nextPageToken,items(generation,timeDeleted)'}
            if page:query['pageToken']=page
            response=get('/o',query)
            for item in response.get('items',[]):
                counts['all_generations']+=1
                counts['noncurrent_generations' if item.get('timeDeleted') else 'live_generations']+=1
            page=response.get('nextPageToken')
            if not page:break
        result['generation_inventory']=counts
    except urllib.error.HTTPError as exc:
        result['limitations'].append({'check':'retained_generations','http_status':exc.code})
    try:
        count=0;page=None
        while True:
            query={'softDeleted':'true','maxResults':1000,'fields':'nextPageToken,items(generation)'}
            if page:query['pageToken']=page
            response=get('/o',query);count+=len(response.get('items',[]))
            page=response.get('nextPageToken')
            if not page:break
        result['soft_deleted_generations']=count
    except urllib.error.HTTPError as exc:
        result['limitations'].append({'check':'soft_deleted_object_inventory','http_status':exc.code,
          'note':'HTTP 400 can mean that no soft-delete policy is enabled; configuration must corroborate this.'})
    result['status']='partial' if any('http_status' in x for x in result['limitations']) else 'bucket_configuration_and_generations_read'
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bucket',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(audit(a.bucket),indent=2)+'\n',encoding='utf-8')
