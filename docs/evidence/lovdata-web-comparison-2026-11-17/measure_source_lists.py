import json,sys,collections,pathlib
from bs4 import BeautifulSoup
obs=pathlib.Path(sys.argv[1])
members=[json.loads(l) for l in open(obs/'x/source-members.jsonl',encoding='utf-8')]
members=[m for m in members if m['selected'] and m['role']!='lovtidend']
c=collections.Counter(); par=collections.Counter(); docs=collections.Counter(); ex=[]
ledd={'legalP','numberedLegalP','listArticle','centeredP','defaultP'}
for m in members:
    soup=BeautifulSoup((obs/'raw'/m['archive_sha256']/m['member_path']).read_bytes(),'lxml')
    for lst in soup.find_all(['ol','ul']):
        if lst.find_parent(class_='documentHeader') or lst.find_parent('footer'): continue
        p=lst.parent; pc=set(p.get('class') or [])
        inside=bool(pc & ledd) or p.name=='li'
        lis=lst.find_all('li',recursive=False); marked=sum(bool(li.get('data-name') or li.get('value')) for li in lis)
        key='inside paragraph' if inside else 'direct child of '+(p.name+'.'+'.'.join(sorted(pc)) if pc else p.name)
        c[key,'lists']+=1; c[key,'items']+=len(lis); c[key,'marked items']+=marked
        if not inside:
            par[key]+=1; docs[m['refid']]+=marked
            if len(ex)<5: ex.append((m['refid'],str(lst)[:300]))
print('\n'.join(f'{k} {v}' for k,v in sorted(c.items(),key=lambda kv:-kv[1])))
print('documents with direct-child lists',len(docs),'marked items',sum(docs.values()))
print('top docs',docs.most_common(15))
for e in ex: print(e)
