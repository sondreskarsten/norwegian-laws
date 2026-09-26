"""Publish a pinned, byte-checked observed-history export as a reader.

Recorded qualification and observed source dates never establish legal validity.
Qualified HTML is copied exactly and displayed without script permission.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

LEGAL = {"status": "unresolved", "from": None, "until": None}
SCOPE = "recorded_qualification_and_exact_published_bytes"
SHA = re.compile(r"[0-9a-f]{64}")
REFID = re.compile(r"(?:lov|forskrift)/[0-9]{4}-[0-9]{2}-[0-9]{2}(?:-[0-9]+)?")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _json(path):
    return json.loads(path.read_bytes())


def _script(value):
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _url(value):
    parsed = urlsplit(value)
    _require(parsed.scheme == "https" and parsed.netloc == "github.com"
             and not parsed.fragment and not parsed.query, "Unsupported history evidence URL")


def validate_export(root: Path):
    """Check all metadata/HTML bytes before replacing any site output."""
    root = Path(root)
    _require(root.is_dir() and not root.is_symlink(), "History export is missing or linked")
    index = _json(root / "index.json")
    _require(index.get("contract") == "history-reader-export-v1"
             and index.get("scope") == SCOPE
             and index.get("source_requalification_in_this_export") is False
             and index.get("legal_valid_time") == LEGAL, "Unsupported history export scope")
    repository, commit = index.get("history_repository"), index.get("history_commit")
    _require(isinstance(repository, str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
             and isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit), "Invalid pinned history checkout")
    products = {row["body_product_id"]: row for row in index["products"]}
    _require(len(products) == len(index["products"]), "Duplicate reader product")
    for identity, product in products.items():
        _require(SHA.fullmatch(identity) and SHA.fullmatch(product["observation_id"]), "Invalid reader product identity")
        for key in ("receipt_url", "publication_url", "source_receipt_url", "bundle_url"):
            _url(product[key])
        prefix = f"https://github.com/{repository}/blob/{commit}/"
        _require(product["receipt_url"] == prefix + f"body-products/{identity}/receipt.json"
                 and product["publication_url"] == prefix + f"body-publications/{identity}.json", "Reader product links are not checkout-pinned")
    documents, files = {}, {"index.json"}
    for refid, pointer in index["documents"].items():
        _require(REFID.fullmatch(refid), "Unsupported reader document identity")
        name = "documents/" + _hash(refid.encode("utf-8")) + ".json"
        _require(pointer["path"] == name and SHA.fullmatch(pointer["metadata_sha256"]), "Invalid reader metadata pointer")
        data = (root / name).read_bytes()
        _require(_hash(data) == pointer["metadata_sha256"], "Reader metadata bytes changed")
        document = json.loads(data)
        _require(document.get("contract") == "history-reader-document-v1" and document.get("refid") == refid
                 and document.get("history_repository") == repository and document.get("history_commit") == commit
                 and document.get("scope") == SCOPE, "Reader document identity or scope differs")
        versions, seen, qualified = document["versions"], set(), 0
        for version in versions:
            identity = version["body_product_id"]
            _require(identity in products and identity not in seen, "Unknown or duplicate reader version")
            seen.add(identity)
            product = products[identity]
            _require(version["observation_id"] == product["observation_id"]
                     and version["knowledge_cutoff"] == product["knowledge_cutoff"]
                     and version["legal_valid_time"] == LEGAL, "Reader observation or legal scope differs")
            for key in ("receipt_url", "publication_url", "source_receipt_url", "bundle_url"):
                _require(version[key] == product[key], "Reader version evidence links differ")
            _url(version["source_bundle_url"])
            _require(all(isinstance(version.get(key), str) and SHA.fullmatch(version[key])
                         for key in ("source_occurrence_id", "semantic_sha256", "body_sha256")), "Invalid reader source/body identity")
            if version["status"] == "passed":
                sha = version["html_sha256"]
                _require(isinstance(sha, str) and SHA.fullmatch(sha)
                         and version["html_path"] == "bodies/" + sha + ".html", "Invalid qualified HTML pointer")
                name_html = version["html_path"]
                _require(_hash((root / name_html).read_bytes()) == sha, "Qualified HTML bytes changed")
                files.add(name_html)
                qualified += 1
            else:
                _require(version["status"] == "rejected" and version["reasons"]
                         and version["html_path"] is None and version["html_sha256"] is None,
                         "Rejected version unexpectedly exposes text")
        _require(len(versions) == pointer["versions"] and qualified == pointer["qualified_versions"], "Reader version counts differ")
        files.add(name)
        documents[refid] = document
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    _require(actual == files and not any(p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in root.rglob("*")),
             "Reader export has unexpected or linked files")
    return index, documents, files


CSS = """body{font:17px/1.55 system-ui,sans-serif;color:#243746;margin:0 auto;padding:1.25rem;max-width:1100px}*{box-sizing:border-box}a{color:#175b94}h1{font-size:1.9rem;line-height:1.25;overflow-wrap:anywhere}.scope{padding:1rem;background:#eef5fa;border-left:4px solid #417ba3}.controls{display:flex;align-items:end;gap:1rem;flex-wrap:wrap;margin:1.5rem 0}label{display:block;font-weight:600}select,input,button{font:inherit;max-width:100%;padding:.5rem}select{width:100%}.select{flex:1;min-width:230px}button{cursor:pointer}button:disabled{cursor:default}.panels{display:grid;grid-template-columns:minmax(0,1fr);gap:1rem}.panels.compare{grid-template-columns:repeat(2,minmax(0,1fr))}.panel{min-width:0;border:1px solid #ccd5dd;padding:.8rem;border-radius:5px}iframe{width:100%;height:72vh;min-height:440px;border:0;background:white}.links{display:flex;gap:.7rem;flex-wrap:wrap;margin:.7rem 0}.muted{color:#536775}.notice{padding:1rem;background:#fff5dd}.citation{width:100%;font-size:.9rem}.versions{padding-left:1.3rem;overflow-wrap:anywhere}details{margin-top:1rem}code{overflow-wrap:anywhere}li{margin:.5rem 0}[hidden]{display:none!important}.directory{list-style:none;padding:0}.directory li{padding:.7rem;border-bottom:1px solid #dce3e9}.directory small{display:block}.search{width:100%;margin:.75rem 0}@media(max-width:700px){body{padding:.8rem}.panels.compare{grid-template-columns:minmax(0,1fr)}h1{font-size:1.55rem}.select{min-width:0;width:100%;flex-basis:100%}iframe{height:65vh}}"""

SCRIPT = r"""
(function(){
  'use strict';
  const data=JSON.parse(document.getElementById('versions-data').textContent);
  const clock=v=>v.knowledge_cutoff?Date.parse(v.knowledge_cutoff):-Infinity;
  const rows=data.versions.map((v,i)=>Object.assign({rank:i},v)).sort((a,b)=>(clock(b)-clock(a))||b.rank-a.rank);
  const byId=new Map(rows.map(v=>[v.body_product_id,v]));
  const select=document.getElementById('version'), other=document.getElementById('comparison');
  const date=v=>v.knowledge_cutoff?new Intl.DateTimeFormat('nb-NO',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Oslo'}).format(new Date(v.knowledge_cutoff)):'Hentetid ikke registrert';
  const label=v=>date(v)+' — '+(v.status==='passed'?'kontrollert tekst':'tekstform ikke støttet')+' · visning '+(v.rank+1);
  for(const v of rows){const option=new Option(label(v),v.body_product_id);select.add(option);if(v.status==='passed')other.add(new Option(label(v),v.body_product_id));}
  const requested=new URLSearchParams(location.search).get('product');
  const initial=requested||rows[0]?.body_product_id;
  function clear(panel){panel.querySelector('iframe').removeAttribute('src');panel.querySelector('iframe').hidden=true;panel.querySelector('.links').replaceChildren();panel.querySelector('.evidence').replaceChildren();panel.querySelector('.unavailable').hidden=true;}
  function link(parent,text,url,download){const a=document.createElement('a');a.textContent=text;a.href=url;if(download)a.download='';parent.append(a);}
  function draw(panel,v){clear(panel);panel.querySelector('h2').textContent=v?date(v):'Utgaven er ikke tilgjengelig';if(!v){panel.querySelector('.unavailable').hidden=false;panel.querySelector('.unavailable').textContent='Denne lenken viser til en utgave som ikke finnes i det publiserte grunnlaget. Velg en tilgjengelig utgave.';return;}
    const links=panel.querySelector('.links'), evidence=panel.querySelector('.evidence');
    if(v.status==='passed'){const frame=panel.querySelector('iframe');frame.src='data/'+v.html_path;frame.hidden=false;link(links,'Åpne teksten','data/'+v.html_path);link(links,'Last ned nøyaktig HTML','data/'+v.html_path,true);}
    else{const notice=panel.querySelector('.unavailable');notice.hidden=false;notice.textContent='Tekstformen er ennå ikke støttet av den kontrollerte leseren. Kilden er bevart og kan lastes ned.';}
    link(links,'Last ned kildegrunnlaget',v.source_bundle_url,true);
    for(const [text,key] of [['Kildekvittering','source_receipt_url'],['Kontrollert utgave','receipt_url'],['Publiseringskvittering','publication_url']]){const p=document.createElement('p');link(p,text,v[key]);evidence.append(p);}
    const p=document.createElement('p');p.textContent='Kildemedlem: '+v.source_member.member_path+'. SHA-256: '+v.source_member.member_sha256;evidence.append(p);
    const id=document.createElement('p');id.textContent='Utgave: '+v.body_product_id;evidence.append(id);
    if(v.reasons?.length){const why=document.createElement('p');why.textContent='Kontrollresultat: '+v.reasons.map(r=>r.code+(r.path?' ('+r.path+')':'')).join('; ');evidence.append(why);}
  }
  function citation(v){const input=document.getElementById('citation'), button=document.getElementById('copy');if(!v){input.value='';button.disabled=true;return;}const url=new URL(location.href);url.search='';url.hash='';url.searchParams.set('product',v.body_product_id);input.value=url.href;button.disabled=false;}
  function update(){const v=byId.get(select.value);draw(document.getElementById('primary'),v);citation(v);document.getElementById('compare-toggle').disabled=!v||v.status!=='passed'||other.options.length<2;if(other.value===select.value){const option=[...other.options].find(o=>o.value!==select.value);other.value=option?option.value:'';}compare();}
  function compare(){const on=document.getElementById('compare-toggle').checked&&!document.getElementById('compare-toggle').disabled;
    document.getElementById('compare-control').hidden=!on;document.getElementById('secondary').hidden=!on;document.getElementById('panels').classList.toggle('compare',on);
    const message=document.getElementById('comparison-note');message.hidden=!on;
    if(!on){clear(document.getElementById('secondary'));return;}const a=byId.get(select.value),b=byId.get(other.value);
    if(!a||!b||a.body_product_id===b.body_product_id){clear(document.getElementById('secondary'));message.textContent='Velg to forskjellige kontrollerte utgaver.';return;}
    draw(document.getElementById('secondary'),b);
    message.textContent=a.semantic_sha256===b.semantic_sha256?'De to utgavene har samme observerte tekst og struktur. Visningen kan være oppdatert.':'Utgavene vises side om side. Forskjeller mellom kildeobservasjoner fastslår ikke når en lovendring gjaldt.';
  }
  if(byId.has(initial))select.value=initial;else{select.add(new Option('Ukjent utgave',initial||''));select.value=initial||'';}
  select.addEventListener('change',()=>{document.getElementById('copy-status').textContent='';const url=new URL(location.href);url.searchParams.set('product',select.value);history.replaceState(null,'',url);update();});
  other.addEventListener('change',compare);document.getElementById('compare-toggle').addEventListener('change',compare);
  document.getElementById('copy').addEventListener('click',async()=>{const input=document.getElementById('citation'),status=document.getElementById('copy-status');try{await navigator.clipboard.writeText(input.value);status.textContent='Lenken er kopiert.';}catch(error){input.focus();input.select();status.textContent='Marker og kopier lenken i feltet.';}});
  update();
})();
"""


def _page(title, content, script=""):
    return '<!doctype html><html lang="nb"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + ' — observerte utgaver</title><style>' + CSS + '</style></head><body>' + content + ('<script>' + script + '</script>' if script else '') + '</body></html>\n'


def _panel(identity, hidden=False):
    return (f'<section class="panel" id="{identity}"' + (' hidden' if hidden else '') + '><h2>Observert tekst</h2><p class="notice unavailable" hidden></p><div class="links"></div><iframe title="' + ('Valgt observert tekst' if identity == 'primary' else 'Observert tekst til sammenligning') + '" sandbox="allow-same-origin" hidden></iframe><details><summary>Kilder og kontroll</summary><div class="evidence"></div></details></section>')


def generate_observed_history(export_dir, site_dir, *, titles=None, site_index=None):
    """Return links only after the complete checked reader has been written."""
    export_dir, site_dir = Path(export_dir), Path(site_dir)
    index, documents, files = validate_export(export_dir)
    titles = titles or {}
    site_dir.mkdir(parents=True, exist_ok=True)
    target = site_dir / "observasjoner"
    _require(not target.exists(), "Observed-history site output already exists")
    with tempfile.TemporaryDirectory(prefix=".observed-reader-", dir=site_dir) as temporary:
        root = Path(temporary) / "observasjoner"
        (root / "data").mkdir(parents=True)
        for name in sorted(files):
            destination = root / "data" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(export_dir / name, destination)
        links, directory = {}, []
        for refid, document in documents.items():
            title = titles.get(refid) or refid
            filename = refid.replace("/", "-") + ".html"
            links[refid] = "observasjoner/" + filename
            current = site_index.doc_page(refid) if site_index is not None else None
            breadcrumb = '<nav><a href="index.html">Observerte utgaver</a>' + (f' · <a href="../{html.escape(current)}">Til dagens leser</a>' if current else '') + '</nav>'
            versions = ''.join('<li><a href="?product=' + html.escape(v["body_product_id"]) + '">' + html.escape((v["knowledge_cutoff"] or "Ukjent hentetid") + (" · kontrollert tekst" if v["status"] == "passed" else " · tekstform ikke støttet")) + '</a></li>' for v in document["versions"])
            content = breadcrumb + '<h1>' + html.escape(title) + '</h1><p><code>' + html.escape(refid) + '</code></p><p class="scope">Dette viser tekst slik den ble hentet fra kilden. Hentedatoen forteller ikke når reglene gjaldt. Velg en utgave for å lese den bevarte teksten og se kildegrunnlaget.</p><div class="controls"><div class="select"><label for="version">Observert utgave</label><select id="version"></select></div><label><input type="checkbox" id="compare-toggle"> Sammenlign to utgaver</label><div class="select" id="compare-control" hidden><label for="comparison">Sammenlign med</label><select id="comparison"></select></div></div><p id="comparison-note" class="notice" hidden></p><div id="panels" class="panels">' + _panel('primary') + _panel('secondary', True) + '</div><p><label for="citation">Lenke til valgt utgave</label><input readonly class="citation" id="citation"></p><button id="copy">Kopier lenke</button><span role="status" id="copy-status"></span><details><summary>Alle bevarte utgaver</summary><ul class="versions">' + versions + '</ul></details><noscript><p>Velg kildegrunnlaget gjennom <a href="data/index.json">utgaveoversikten</a>. Den interaktive tekstleseren trenger JavaScript.</p></noscript><script type="application/json" id="versions-data">' + _script(document) + '</script>'
            (root / filename).write_text(_page(title, content, SCRIPT), encoding="utf-8")
            pointer = index["documents"][refid]
            directory.append({"refid": refid, "title": title, "url": filename, "versions": pointer["versions"], "qualified": pointer["qualified_versions"]})
        directory.sort(key=lambda row: (row["title"].casefold(), row["refid"]))
        body = '<nav><a href="../index.html">Norges Lover</a></nav><h1>Observerte utgaver</h1><p class="scope">Finn bevarte kildeobservasjoner av lover og forskrifter. Kontrollerte tekster kan leses og sammenlignes. Dette er ikke en oversikt over hva som juridisk gjaldt på en bestemt dato.</p><label for="search">Finn lov eller forskrift</label><input id="search" class="search" type="search" placeholder="Tittel eller dokumentnummer"><p id="result-count" role="status"></p><ul class="directory" id="results"></ul><p><a href="data/index.json">Last ned den festede utgaveoversikten</a></p><script type="application/json" id="directory-data">' + _script(directory) + '</script>'
        script = "const rows=JSON.parse(document.getElementById('directory-data').textContent),list=document.getElementById('results'),search=document.getElementById('search');function show(){const q=search.value.toLocaleLowerCase('nb-NO').trim(),found=rows.filter(r=>(r.title+' '+r.refid).toLocaleLowerCase('nb-NO').includes(q));list.replaceChildren();for(const r of found.slice(0,100)){const li=document.createElement('li'),a=document.createElement('a'),small=document.createElement('small');a.href=r.url;a.textContent=r.title;small.textContent=r.refid+' · '+r.versions+' utgaver · '+r.qualified+' med kontrollert tekst';li.append(a,small);list.append(li);}document.getElementById('result-count').textContent=found.length+' dokumenter'+(found.length>100?' — de første 100 vises':'');}search.addEventListener('input',show);show();"
        (root / "index.html").write_text(_page("Observerte utgaver", body, script), encoding="utf-8")
        root.rename(target)
    if site_index is not None:
        site_index.attach_observed(links)
    return links


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("site", type=Path)
    args = parser.parse_args()
    print(json.dumps({"documents": len(generate_observed_history(args.export, args.site))}))
