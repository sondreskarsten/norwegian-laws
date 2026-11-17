import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import lxml.html
import requests

repo = Path(sys.argv[1])
out = Path(sys.argv[2])
delay = float(sys.argv[3])

blocks = ".//p|.//div|.//td|.//th|.//tr|.//li|.//br|.//table|.//h1|.//h2|.//h3|.//h4|.//h5|.//h6"
page_chrome = './/a[@class="share-paragraf"]|.//td[contains(@class,"fotnoteNummer")][normalize-space()="0"]'
opening = './p[contains(@class,"morTag_mf")]'
front_page = 'class="next frontpage"'
headers = {"User-Agent": "norwegian-laws web comparison (github.com/sondreskarsten/norwegian-laws)"}


def words(text):
    return Counter(re.findall(r"\w+", text))


def our_parts(path):
    _, front, body = path.read_text(encoding="utf-8").split("---\n", 2)
    meta = dict(re.findall(r'^([\w-]+): "(.*)"$', front, flags=re.M))
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)
    body = re.sub(r"</?[a-zA-Z][^<>]*>", " ", body)
    body = re.sub(r"\A\s*# .*\n", "", body)
    return meta, body


def lovdata_parts(html):
    root = lxml.html.fromstring(html.decode("utf-8"))
    meta = {}
    for row in root.xpath('//*[@id="documentMeta"]//tr'):
        cells = [c.text_content().strip() for c in row.xpath("./th|./td")]
        if len(cells) == 2:
            meta[cells[0]] = cells[1]
    body = root.xpath('//*[@id="documentBody"]')[0]
    for e in body.xpath(page_chrome):
        e.drop_tree()
    for e in body.xpath(blocks):
        e.tail = " " + (e.tail or "")
        e.text = " " + (e.text or "")
    opening_text = " ".join(e.text_content() for e in body.xpath(opening))
    for e in body.xpath(opening):
        e.drop_tree()
    return meta, body.text_content().replace("​", ""), " ".join(opening_text.split())


catalog = json.loads((repo / "laws.json").read_text(encoding="utf-8"))
pages = out / "pages"
pages.mkdir(parents=True, exist_ok=True)

for n, doc in enumerate(catalog):
    page = pages / (doc["file"][:-3] + ".html")
    if page.exists() and front_page not in page.read_text(encoding="utf-8"):
        continue
    r = requests.get("https://lovdata.no/" + doc["refid"], headers=headers, timeout=60)
    if r.status_code == 200 and not r.url.endswith("/" + doc["refid"]):
        time.sleep(delay)
        r = requests.get(doc["lovdata"], headers=headers, timeout=60)
    if r.status_code == 200 and front_page in r.text:
        complete = lxml.html.fromstring(r.text).xpath('//li[@class="complete"]/a/@href')[0]
        time.sleep(delay)
        r = requests.get("https://lovdata.no" + complete, headers=headers, timeout=120)
    if r.status_code == 200:
        page.write_bytes(r.content)
        (pages / (doc["file"][:-3] + ".url")).write_text(r.url)
    elif r.status_code == 404:
        (pages / (doc["file"][:-3] + ".404")).write_text(r.url)
    else:
        sys.exit(f"stopped at {doc['refid']}: HTTP {r.status_code}")
    if n % 100 == 0:
        print(n, doc["refid"], flush=True)
    time.sleep(delay)

rows = []
for doc in catalog:
    page = pages / (doc["file"][:-3] + ".html")
    if not page.exists():
        rows.append({"refid": doc["refid"], "status": 404})
        continue
    ours_meta, ours_body = our_parts(repo / doc["path"])
    theirs_meta, theirs_body, opening_text = lovdata_parts(page.read_bytes())
    ours, theirs = words(ours_body), words(theirs_body)
    rows.append(
        {
            "refid": doc["refid"],
            "status": 200,
            "lovdata_url": (pages / (doc["file"][:-3] + ".url")).read_text(),
            "catalog_url": doc["lovdata"],
            "lovdata_words": sum(theirs.values()),
            "missing_in_ours": dict(theirs - ours),
            "extra_in_ours": dict(ours - theirs),
            "lovdata_opening_paragraph_words": len(opening_text.split()),
            "ours_meta": ours_meta,
            "lovdata_meta": theirs_meta,
        }
    )

commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
(out / "result.json").write_text(
    json.dumps({"compared_commit": commit, "documents": rows}, ensure_ascii=False, indent=1), encoding="utf-8"
)
