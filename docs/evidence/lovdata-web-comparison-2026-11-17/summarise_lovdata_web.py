import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rows = result["documents"]


def iso_dates(text):
    return [
        datetime.datetime.strptime(d, "%d.%m.%Y").strftime("%Y-%m-%d")
        for d in re.findall(r"\b\d\d\.\d\d\.\d{4}\b", text)
    ]


def header_pairs(page, ours):
    yield "tittel", page.get(""), ours.get("tittel")
    yield "korttittel", page.get("Korttittel", ""), ours.get("korttittel", "")
    yield (
        "departement",
        sorted(re.split(r",\s*|\n", page.get("Departement", ""))),
        sorted(ours.get("departement", "").split("\\n")),
    )
    if page.get("ELI"):
        yield "eli", page["ELI"].removeprefix("https://lovdata.no"), ours.get("eli")
    dates = iso_dates(page.get("Ikrafttredelse", ""))
    if dates:
        yield "ikrafttredelse", dates, re.findall(r"\d{4}-\d\d-\d\d", ours.get("ikrafttredelse", ""))
    last = re.match(r"(LOV|FOR)-[\d-]+", page.get("Sist endret", ""))
    if last:
        ref = last.group(0).replace("LOV-", "lov/").replace("FOR-", "forskrift/")
        yield "sist-endret", ref, ours.get("sist-endret", "")


source_words = sum(r["lovdata_words"] for r in rows)
missing = Counter()
extra = Counter()
for r in rows:
    missing.update(r["missing_in_ours"])
    extra.update(r["extra_in_ours"])
missing_total = sum(missing.values())
extra_total = sum(extra.values())
list_marks = sum(v for k, v in missing.items() if re.fullmatch(r"\d+|[a-zæøå]|[ivx]+", k))
fused = sum(v for k, v in missing.items() if re.fullmatch(r"\D+\d+", k))

opening = [r for r in rows if r["lovdata_opening_paragraph_words"]]
bases = Counter(r["lovdata_url"].split("/dokument/")[1].split("/")[0] for r in rows)
catalog_404 = [r for r in rows if r["lovdata_url"].split("/dokument/")[1].split("/")[0] != r["catalog_url"].split("/dokument/")[1].split("/")[0]]

header_diffs = defaultdict(list)
for r in rows:
    for field, page_value, our_value in header_pairs(r["lovdata_meta"], r["ours_meta"]):
        if page_value != our_value:
            header_diffs[field].append((r["refid"], page_value, our_value))

per_doc = sorted(
    rows, key=lambda r: -(sum(r["missing_in_ours"].values()) + sum(r["extra_in_ours"].values()))
)

lines = [
    "# lovdata.no web comparison",
    "",
    f"Compared commit: `{result['compared_commit']}`. Documents: {len(rows)}, all with a lovdata.no page.",
    "",
    "## Words",
    "",
    "| Measure | Count |",
    "|---|---|",
    f"| Words on lovdata.no (opening paragraph excluded) | {source_words:,} |",
    f"| Missing in ours | {missing_total:,} ({missing_total / source_words:.4%}) |",
    f"| of which bare list numbers or letters | {list_marks:,} |",
    f"| of which word with a fused footnote digit on the page | {fused:,} |",
    f"| In ours, not on lovdata.no | {extra_total:,} |",
    f"| Documents word-for-word equal | {sum(not r['missing_in_ours'] and not r['extra_in_ours'] for r in rows):,} |",
    "",
    f"Opening paragraph (`morTag_mf`: Hjemmel/Fastsatt, Jf. tidligere) on lovdata.no, not in ours: "
    f"{len(opening):,} documents, {sum(r['lovdata_opening_paragraph_words'] for r in opening):,} words.",
    "",
    "Most frequent missing words: " + ", ".join(f"`{k}` {v}" for k, v in missing.most_common(30)),
    "",
    "Most frequent extra words: " + ", ".join(f"`{k}` {v}" for k, v in extra.most_common(30)),
    "",
    "## Addresses",
    "",
    "Lovdata base of the address `https://lovdata.no/<refid>` redirects to: "
    + ", ".join(f"{k} {v}" for k, v in bases.most_common()),
    "",
    f"Catalog `lovdata` link with a different base (404 on lovdata.no): {len(catalog_404):,} documents.",
    "",
    "## Header fields",
    "",
    "| Field | Documents differing |",
    "|---|---|",
]
lines += [f"| {k} | {len(v)} |" for k, v in sorted(header_diffs.items(), key=lambda kv: -len(kv[1]))]
for field, diffs in sorted(header_diffs.items(), key=lambda kv: -len(kv[1])):
    lines += ["", f"### {field}", "", "| refid | lovdata.no | ours |", "|---|---|---|"]
    lines += [f"| {ref} | {str(a)[:120]} | {str(b)[:120]} |" for ref, a, b in diffs[:15]]
lines += [
    "",
    "## Largest word differences",
    "",
    "| refid | lovdata.no words | missing | extra |",
    "|---|---|---|---|",
]
lines += [
    f"| {r['refid']} | {r['lovdata_words']} | {sum(r['missing_in_ours'].values())} | {sum(r['extra_in_ours'].values())} |"
    for r in per_doc[:40]
]
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
