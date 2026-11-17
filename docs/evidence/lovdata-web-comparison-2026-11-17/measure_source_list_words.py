import json,sys,collections,pathlib,re
from bs4 import BeautifulSoup
obs=pathlib.Path(sys.argv[1])
members=[json.loads(l) for l in open(obs/'x/source-members.jsonl',encoding='utf-8')]
members=[m for m in members if m['selected'] and m['role']!='lovtidend']
ledd={'legalP','numberedLegalP','listArticle','centeredP','defaultP'}
w=collections.Counter(); d=collections.defaultdict(set); laws=collections.defaultdict(set)
for m in members:
    soup=BeautifulSoup((obs/'raw'/m['archive_sha256']/m['member_path']).read_bytes(),'lxml')
    for lst in soup.find_all(['ol','ul']):
        if lst.find_parent(class_='documentHeader') or lst.find_parent('footer'): continue
        p=lst.parent; pc=set(p.get('class') or [])
        if pc & ledd or p.name=='li': continue
        k='legalArticle' if 'legalArticle' in pc else ('section' if p.name=='section' else ('body' if p.name=='main' else 'other'))
        w[k]+=len(re.findall(r'\w+',lst.get_text(' '))); d[k].add(m['refid'])
        if m['refid'].startswith('lov/'): laws[k].add(m['refid'])
for k in w: print(k,'words',w[k],'documents',len(d[k]),'of which laws',len(laws[k]))
