"""Generate Quarto book structure from law markdown files.

Reads the lover/*.md files (already formatted by formatter.py) and
produces Quarto book chapters, search pages, diff tools, and config.
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import yaml
from pathlib import Path
from collections import defaultdict
from .legacy_versions import LEGACY_VERSION_REFS, supported_version_tags

GITHUB_BASE = "https://github.com/sondreskarsten/norwegian-laws"
HISTORY_BRANCH = "law-history"
LEGACY_NOTICE = (
    "**Eksperimentell historikk:** Utgavene er uverifiserte rekonstruksjoner. "
    "De dokumenterer ikke sikkert hvilke regler som gjaldt på en bestemt dato. "
    "Ikrafttredelse og historiske tekster må kontrolleres mot kilden."
)

# Common abbreviations → refid (source: paragraf-mcp LOV_ALIASES, MIT license)
LAW_ALIASES = {
    "lov/1997-06-13-43": ["buofl", "bustadoppføringslova"],
    "lov/1992-07-03-93": ["avhl", "avhendingslova"],
    "lov/2008-06-27-71": ["pbl", "plan-og-bygningsloven"],
    "lov/1999-03-26-17": ["husll", "husleieloven"],
    "lov/1988-05-13-27": ["kjl", "kjøpsloven"],
    "lov/2002-06-21-34": ["fkjl", "forbrukerkjøpsloven"],
    "lov/1989-06-16-63": ["hvtjl", "håndverkertjenesteloven"],
    "lov/2005-06-17-62": ["aml", "arbeidsmiljøloven"],
    "lov/1997-02-28-19": ["ftrl", "folketrygdloven"],
    "lov/1967-02-10": ["fvl", "forvaltningsloven"],
    "lov/2006-05-19-16": ["offl", "offentleglova"],
    "lov/2018-06-22-83": ["koml", "kommuneloven"],
    "lov/2005-06-17-90": ["tvl", "tvisteloven"],
    "lov/2016-06-17-73": ["loa", "anskaffelsesloven"],
    "lov/1969-06-13-26": ["skl", "skadeserstatningsloven"],
    "lov/1918-05-31-4": ["avtl", "avtaleloven"],
    "lov/2005-05-20-28": ["strl", "straffeloven"],
    "lov/2018-06-15-38": ["popplyl", "personopplysningsloven"],
    "lov/1998-07-17-56": ["rskl", "regnskapsloven"],
    "lov/1997-06-13-44": ["asl", "aksjeloven"],
    "lov/1997-06-13-45": ["asal", "allmennaksjeloven"],
    "lov/1984-06-08-58": ["kkl", "konkursloven"],
    "lov/1985-06-21-83": ["sel", "selskapsloven"],
    "lov/1980-02-08-2": ["pantel", "panteloven"],
    "lov/1984-06-08-59": ["deknl", "dekningsloven"],
    "lov/1992-06-26-86": ["tvfbl", "tvangsfullbyrdelsesloven"],
    "forskrift/2016-08-12-974": ["foa", "anskaffelsesforskriften"],
    "forskrift/2009-08-03-1028": ["byggherreforskriften"],
    "forskrift/2010-03-26-488": ["sak10", "byggesaksforskriften"],
    "forskrift/2017-06-19-840": ["tek17", "byggteknisk-forskrift"],
}

KNOWN_DEPARTMENTS = [
    "Arbeids- og inkluderingsdepartementet",
    "Barne- og familiedepartementet",
    "Digitaliserings- og forvaltningsdepartementet",
    "Energidepartementet",
    "Finansdepartementet",
    "Forsvarsdepartementet",
    "Helse- og omsorgsdepartementet",
    "Justis- og beredskapsdepartementet",
    "Klima- og miljødepartementet",
    "Kommunal- og distriktsdepartementet",
    "Kultur- og likestillingsdepartementet",
    "Kunnskapsdepartementet",
    "Landbruks- og matdepartementet",
    "Nærings- og fiskeridepartementet",
    "Samferdselsdepartementet",
    "Statsministerens kontor",
    "Utenriksdepartementet",
]


def parse_frontmatter(filepath: str) -> dict:
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if v:
            result[k.strip()] = v.strip().strip('"')
    return result


def split_departments(dept_str: str) -> list[str]:
    for known in sorted(KNOWN_DEPARTMENTS, key=len, reverse=True):
        dept_str = dept_str.replace(known, f"|{known}|")
    parts = [p.strip() for p in dept_str.split("|") if p.strip()]
    return parts if parts else [dept_str]


def group_laws_by_area(lover_dir: str) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for f in sorted(Path(lover_dir).glob("*.md")):
        if f.name == "README.md":
            continue
        meta = parse_frontmatter(str(f))
        if not meta.get("tittel"):
            continue
        raw_dept = meta.get("departement", "Annet") or "Annet"
        depts = split_departments(raw_dept)
        entry = {
            "file": f.name,
            "path": str(f),
            "tittel": meta.get("tittel", f.stem),
            "korttittel": meta.get("korttittel", ""),
            "refid": meta.get("refid", ""),
            "ikrafttredelse": meta.get("ikrafttredelse", ""),
            "sist-endret": meta.get("sist-endret", ""),
            "sist-endret-ikrafttredelse": meta.get("sist-endret-ikrafttredelse", ""),
            "rettsomrade": meta.get("rettsomrade", ""),
        }
        for dept in depts:
            groups[dept].append(entry)
    return dict(sorted(groups.items()))


def _split_topics(rettsomrade: str) -> list[str]:
    """Parse the rettsomrade frontmatter value into top-level topics.

    rettsomrade holds one topic path per line ('Topic>Sub'), with literal
    newlines escaped as \\n by the formatter. Split on newlines, take the
    top-level topic before '>', and dedup. Values concatenated without any
    separator (the pre-2026-05-19 parser bug) are not recoverable here."""
    if not rettsomrade:
        return []
    topics = set()
    # Split on linebreak first, then on '>'
    for chunk in rettsomrade.replace("\\n", "\n").split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        top = chunk.split(">")[0].strip()
        if top:
            topics.add(top)
    return sorted(topics)


def group_laws_by_topic(lover_dir: str) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for f in sorted(Path(lover_dir).glob("*.md")):
        if f.name == "README.md":
            continue
        meta = parse_frontmatter(str(f))
        if not meta.get("tittel"):
            continue
        topics = _split_topics(meta.get("rettsomrade", ""))
        if not topics:
            continue
        entry = {
            "file": f.name,
            "path": str(f),
            "tittel": meta.get("tittel", f.stem),
            "korttittel": meta.get("korttittel", ""),
            "refid": meta.get("refid", ""),
            "ikrafttredelse": meta.get("ikrafttredelse", ""),
            "departement": meta.get("departement", ""),
        }
        for topic in topics:
            groups[topic].append(entry)
    return dict(sorted(groups.items()))


def extract_year_from_refid(refid: str) -> int:
    m = re.search(r"(\d{4})-\d{2}-\d{2}", refid)
    if m:
        return int(m.group(1))
    return 2001


def compute_version_links(refid: str, version_tags: list[str]) -> list[str]:
    version_tags = supported_version_tags(version_tags)
    enacted_year = extract_year_from_refid(refid)
    first_tag_year = 2001
    start_year = max(enacted_year, first_tag_year)
    all_years = [int(t[1:]) for t in version_tags]
    last_3 = version_tags[-3:]
    last_3_years = {int(t[1:]) for t in last_3}
    sampled = set()
    for y in all_years:
        if y < start_year:
            continue
        if y in last_3_years:
            continue
        if y == start_year or y % 5 == 0:
            sampled.add(y)
    combined = sorted(sampled | last_3_years)
    combined = [y for y in combined if y >= start_year]
    return [f"v{y}" for y in combined]


def get_amendment_stats_by_year(db_path: str) -> dict[str, dict]:
    if not db_path or not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT
            substr(date_in_force_resolved, 1, 4) as year,
            COUNT(*) as act_count,
            SUM(amendment_count) as total_amendments
        FROM amendment_acts
        GROUP BY year
        ORDER BY year
    """).fetchall()
    conn.close()
    stats = {}
    for year, act_count, total_amendments in rows:
        stats[year] = {"acts": act_count, "amendments": total_amendments or 0}
    return stats


def generate_laws_json(lover_dir: str, output_path: str, version_tags: list[str] = None,
                       historie_slugs: dict[str, str] | None = None,
                       forskrifter_dir: str | None = None,
                       amendment_counts: dict[str, int] | None = None) -> list[dict]:
    """Write laws.json.

    amendment_counts: optional {refid: n_amendments} dict. When provided,
    each entry gets an "amendments" field showing how many amendments
    that law has received since 2001. Useful for downstream consumers
    picking which laws to actively monitor.
    """
    version_tags = supported_version_tags(version_tags)
    if amendment_counts is None:
        amendment_counts = {}
    laws = []

    def _add_entries(src_dir: str, kind: str):
        if not os.path.isdir(src_dir):
            return
        for f in sorted(Path(src_dir).glob("*.md")):
            if f.name == "README.md":
                continue
            meta = parse_frontmatter(str(f))
            if not meta.get("tittel"):
                continue
            refid = meta.get("refid", "")
            raw_dept = meta.get("departement", "Annet") or "Annet"
            depts = split_departments(raw_dept)
            tags = compute_version_links(refid, version_tags)
            if kind == "forskrift":
                gh_dir = "forskrifter"
                lovdata_kind = "SF"
            else:
                gh_dir = "lover"
                lovdata_kind = "NL"
            laws.append({
                "file": f.name,
                "refid": refid,
                "eli": "/eli/" + refid.replace("-", "/", 3),
                "tittel": meta.get("tittel", ""),
                "korttittel": meta.get("korttittel", ""),
                "aliases": LAW_ALIASES.get(refid, []),
                "departement": depts,
                "kind": kind,
                "path": f"{gh_dir}/{f.name}",
                "ikrafttredelse": meta.get("ikrafttredelse", ""),
                "sist_endret": meta.get("sist-endret", ""),
                "github": f"{GITHUB_BASE}/blob/main/{gh_dir}/{f.name}",
                "lovdata": f"https://lovdata.no/dokument/{lovdata_kind}/{refid}",
                "log": f"{GITHUB_BASE}/commits/{HISTORY_BRANCH}/{gh_dir}/{f.name}",
                "tags": tags,
                "amendments": amendment_counts.get(refid, 0),
                "historie": (historie_slugs or {}).get(refid),
            })

    _add_entries(lover_dir, "lov")
    if forskrifter_dir:
        _add_entries(forskrifter_dir, "forskrift")

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(laws, fh, ensure_ascii=False, indent=1)
    return laws


def _catalog_loader_lines() -> list[str]:
    """Decode the internal compact catalog into the familiar display records."""
    return [
        'function loadSearchCatalog() {',
        '  return fetch("../search-catalog.json").then(function(r) {',
        '    if (!r.ok) throw new Error("HTTP " + r.status);',
        '    return r.json();',
        '  }).then(function(data) {',
        '    if (data.version !== 1) throw new Error("Ukjent søkeindeksversjon");',
        '    var laws = data.documents.map(function(row) {',
        '      var law = {};',
        '      data.columns.forEach(function(key, i) { law[key] = row[i]; });',
        '      law.departement = law.departement.map(function(i) { return data.departments[i]; });',
        '      law.tags = data.tagSets[law.tags];',
        '      law.file = law.path.split("/").pop();',
        '      law.lovdata = "https://lovdata.no/dokument/" + (law.refid.startsWith("forskrift/") ? "SF/" : "NL/") + law.refid;',
        f'      law.log = "{GITHUB_BASE}/commits/{HISTORY_BRANCH}/" + law.path;',
        '      return law;',
        '    });',
        '    return {laws: laws, fullText: data.fullText};',
        '  });',
        '}',
    ]


def generate_search_page(book_dir: str):
    page = r"""---
title: "Søk i lover"
search: false
---

<label for="law-search" style="font-weight:600;font-size:1.1em;">Søk i lover og forskrifter:</label>
<input type="text" id="law-search" placeholder="f.eks. arbeidsmiljø, straffeloven, lov-2005..." style="width:100%;min-width:0;box-sizing:border-box;padding:8px 12px;margin:8px 0 16px 0;font-size:1em;border:1px solid #ccc;border-radius:4px;">
<fieldset style="border:0;padding:0;margin:0 0 16px;min-width:0;">
<legend style="font-size:1em;font-weight:600;">Søk i</legend>
<div style="display:flex;gap:16px;flex-wrap:wrap;">
<label><input type="radio" name="search-scope" value="titles" checked> Tittel og referanse</label>
<label><input type="radio" name="search-scope" value="body"> Hele lovteksten</label>
</div>
<div id="full-text-size" style="color:#666;font-size:0.9em;margin-top:6px;">Tekstsøk laster bare delene av teksten som trengs for søket.</div>
</fieldset>
<div id="result-count" aria-live="polite" style="margin-bottom:8px;color:#666;"></div>
<div style="width:100%;max-width:100%;min-width:0;overflow-x:auto;">
<table id="law-results" style="width:100%;display:none;">
<thead><tr><th style="text-align:left;">Lov</th><th style="text-align:left;">Korttittel</th><th style="text-align:left;">Departement</th><th style="text-align:right;">Endringer</th><th style="text-align:left;">Lenker</th></tr></thead>
<tbody></tbody>
</table>
</div>
<button id="more-results" type="button" style="display:none;margin-top:12px;">Vis flere teksttreff</button>
<div id="no-results" style="display:none;color:#888;padding:20px 0;">Ingen treff.</div>

```{=html}
<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
<script>
__CATALOG_LOADER__
document.addEventListener("DOMContentLoaded", function() {
  var input = document.getElementById("law-search");
  var table = document.getElementById("law-results");
  var tbody = table.querySelector("tbody");
  var countDiv = document.getElementById("result-count");
  var noResults = document.getElementById("no-results");
  var moreButton = document.getElementById("more-results");
  var bodyScope = document.querySelector('input[name="search-scope"][value="body"]');
  var laws = [];
  var lawsByRef = new Map();
  var fuse = null;
  var fullText = null;
  var pagefindPromise = null;
  var textMatches = [];
  var textResults = [];
  var seenRefs = new Set();
  var textOffset = 0;
  var requestId = 0;
  var searchTimer = null;

  function status(message) {
    tbody.innerHTML = "";
    table.style.display = "none";
    noResults.style.display = "none";
    countDiv.textContent = message;
    moreButton.style.display = "none";
  }

  status("Laster titler og referanser...");
  loadSearchCatalog().then(function(catalog) {
    laws = catalog.laws;
    fullText = catalog.fullText;
    laws.forEach(function(law) { lawsByRef.set(law.refid, law); });
    fuse = new Fuse(laws, {
      keys: [
        {name: "tittel", weight: 0.35}, {name: "korttittel", weight: 0.25},
        {name: "aliases", weight: 0.25}, {name: "refid", weight: 0.1},
        {name: "departement", weight: 0.05}
      ],
      threshold: 0.35, distance: 200, minMatchCharLength: 2
    });
    search();
  }).catch(function() {
    status("Kunne ikke laste søkeoversikten. Last siden på nytt for å prøve igjen.");
  });

  function loadTextSearch() {
    if (!fullText) return Promise.reject(new Error("Tekstindeks mangler"));
    if (!pagefindPromise) {
      pagefindPromise = import("../" + fullText.module).catch(function(error) {
        pagefindPromise = null;
        throw error;
      });
    }
    return pagefindPromise;
  }

  function link(href, text) {
    var a = document.createElement("a");
    a.href = href;
    a.textContent = text;
    return a;
  }

  function renderResults(results, total) {
    status("");
    if (!results.length) { noResults.style.display = "block"; return; }
    table.style.display = "table";
    countDiv.textContent = total > results.length ? "Viser " + results.length + " av " + total + " treff" : total + " treff";
    results.forEach(function(law) {
      var tr = document.createElement("tr");
      var td1 = document.createElement("td");
      td1.style.minWidth = "180px";
      td1.appendChild(link("../" + law.path.replace(/\.md$/, ".html"), law.tittel));
      if (law.excerpt) {
        var excerpt = document.createElement("p");
        excerpt.style.cssText = "font-size:0.9em;color:#666;max-width:32em;";
        excerpt.textContent = law.excerpt;
        td1.appendChild(excerpt);
      }
      var td2 = document.createElement("td");
      td2.textContent = law.korttittel;
      var td3 = document.createElement("td");
      td3.textContent = law.departement.join(", ");
      var td4 = document.createElement("td");
      td4.style.textAlign = "right";
      var n = law.amendments || 0;
      var count = n > 0 && law.historie ? link("../" + law.historie, String(n)) : document.createElement("span");
      count.textContent = n > 0 ? String(n) : "—";
      count.style.color = n >= 50 ? "#dc3545" : n >= 10 ? "#fd7e14" : n > 0 ? "#198754" : "#adb5bd";
      td4.appendChild(count);
      var td5 = document.createElement("td");
      td5.appendChild(link(law.lovdata, "lovdata"));
      td5.appendChild(document.createTextNode(" · "));
      td5.appendChild(link(law.log, "logg"));
      [td1, td2, td3, td4, td5].forEach(function(td) { tr.appendChild(td); });
      tbody.appendChild(tr);
    });
  }

  async function showTextResults(id) {
    moreButton.disabled = true;
    var batch = textMatches.slice(textOffset, textOffset + 10);
    try {
      var data = await Promise.all(batch.map(function(result) { return result.data(); }));
      if (id !== requestId) return;
      textOffset += batch.length;
      data.forEach(function(result) {
        var law = lawsByRef.get(result.meta.refid);
        if (!law || seenRefs.has(law.refid)) return;
        seenRefs.add(law.refid);
        // Decode Pagefind's escaped plain excerpt without inserting source HTML.
        var excerpt = document.createElement("textarea");
        excerpt.innerHTML = result.plain_excerpt;
        textResults.push(Object.assign({}, law, {excerpt: excerpt.value}));
      });
      renderResults(textResults, textResults.length);
      countDiv.textContent = textResults.length + (textResults.length === 1 ? " dokument fra " : " dokumenter fra ") +
        textMatches.length + " teksttreff";
      moreButton.style.display = textOffset < textMatches.length ? "inline-block" : "none";
    } catch (error) {
      if (id === requestId) status("Kunne ikke laste teksttreff. Endre søket for å prøve igjen.");
    } finally {
      if (id === requestId) moreButton.disabled = false;
    }
  }

  async function search() {
    var id = ++requestId;
    var q = input.value.trim();
    if (!fuse) return;
    if (q.length < 2) { status(""); return; }
    if (!bodyScope.checked) {
      var matches = fuse.search(q).map(function(r) { return r.item; });
      renderResults(matches.slice(0, 50), matches.length);
      return;
    }
    status("Søker i lovteksten...");
    try {
      var pagefind = await loadTextSearch();
      if (id !== requestId) return;
      var matches = await pagefind.search(q);
      if (id !== requestId) return;
      textMatches = matches.results;
      textResults = [];
      seenRefs = new Set();
      textOffset = 0;
      await showTextResults(id);
    } catch (error) {
      if (id === requestId) status("Kunne ikke laste tekstindeksen. Endre søket for å prøve igjen.");
    }
  }

  moreButton.addEventListener("click", function() { showTextResults(requestId); });
  input.addEventListener("input", function() {
    ++requestId;
    clearTimeout(searchTimer);
    status("");
    searchTimer = setTimeout(search, 180);
  });
  document.querySelectorAll('input[name="search-scope"]').forEach(function(radio) {
    radio.addEventListener("change", function() {
      clearTimeout(searchTimer);
      search();
    });
  });
});
</script>
```
"""
    page = page.replace("__CATALOG_LOADER__", "\n".join(_catalog_loader_lines()))
    Path(book_dir, "sok.qmd").write_text(page, encoding="utf-8")


def generate_diff_page(book_dir: str, version_tags: list[str]):
    lines = [
        '---',
        'title: "Sammenlign lovversjon"',
        'search: false',
        '---',
        '',
        LEGACY_NOTICE,
        '',
        'Velg en lov og to lagrede utgaver for å sammenligne tekst. Sammenligningen bruker',
        'faste, registrerte kopier av den eldre historikken.',
        '',
        '<div style="display:flex;flex-direction:column;gap:12px;width:100%;max-width:600px;min-width:0;margin:16px 0;">',
        '<label for="diff-law" style="font-weight:600;">Velg lov:</label>',
        '<input type="text" id="diff-law-search" placeholder="Søk etter lov eller forskrift..."',
        '  style="width:100%;min-width:0;box-sizing:border-box;padding:8px;border:1px solid #ccc;border-radius:4px;">',
        '<select id="diff-law" size="6" style="width:100%;min-width:0;box-sizing:border-box;padding:4px;border:1px solid #ccc;border-radius:4px;"></select>',
        '',
        '<div style="display:flex;gap:16px;flex-wrap:wrap;min-width:0;">',
        '<div style="flex:1 1 140px;min-width:0;">',
        '<label for="diff-from" style="font-weight:600;">Fra versjon:</label>',
        '<select id="diff-from" style="width:100%;min-width:0;box-sizing:border-box;padding:6px;border:1px solid #ccc;border-radius:4px;"></select>',
        '</div>',
        '<div style="flex:1 1 140px;min-width:0;">',
        '<label for="diff-to" style="font-weight:600;">Til versjon:</label>',
        '<select id="diff-to" style="width:100%;min-width:0;box-sizing:border-box;padding:6px;border:1px solid #ccc;border-radius:4px;"></select>',
        '</div>',
        '</div>',
        '',
        '<div style="display:flex;gap:12px;flex-wrap:wrap;">',
        '<button id="diff-render" style="padding:8px 20px;background:#0969da;color:#fff;border:none;border-radius:4px;cursor:pointer;">Sammenlign tekst</button>',
        '<button id="diff-compare" style="padding:8px 20px;background:#fff;color:#0969da;border:1px solid #0969da;border-radius:4px;cursor:pointer;">Åpne på GitHub</button>',
        '<button id="diff-log" style="padding:8px 20px;background:#fff;color:#24292f;border:1px solid #d0d7de;border-radius:4px;cursor:pointer;">Se endringslogg</button>',
        '</div>',
        '<div id="diff-info" style="color:#666;font-size:0.9em;"></div>',
        '</div>',
        '',
        '<div id="diff-output" style="width:100%;max-width:100%;min-width:0;overflow-x:auto;margin-top:20px;"></div>',
        '',
        '```{=html}',
        '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/diff2html@3.4.48/bundles/css/diff2html.min.css">',
        '<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>',
        '<script src="https://cdn.jsdelivr.net/npm/diff@5.2.0/dist/diff.min.js"></script>',
        '<script src="https://cdn.jsdelivr.net/npm/diff2html@3.4.48/bundles/js/diff2html-ui.min.js"></script>',
        '<script>',
        *_catalog_loader_lines(),
        'document.addEventListener("DOMContentLoaded", function() {',
        '  var lawSearch = document.getElementById("diff-law-search");',
        '  var lawSelect = document.getElementById("diff-law");',
        '  var fromSelect = document.getElementById("diff-from");',
        '  var toSelect = document.getElementById("diff-to");',
        '  var renderBtn = document.getElementById("diff-render");',
        '  var compareBtn = document.getElementById("diff-compare");',
        '  var logBtn = document.getElementById("diff-log");',
        '  var infoDiv = document.getElementById("diff-info");',
        '  var outDiv = document.getElementById("diff-output");',
        f'  var base = "{GITHUB_BASE}";',
        '  var raw = "https://raw.githubusercontent.com/sondreskarsten/norwegian-laws";',
        f'  var versionRefs = {json.dumps(LEGACY_VERSION_REFS)};',
        '  var laws = [];',
        '  var fuse = null;',
        '  var renderRequest = 0;',
        '',
        '  function clearDiff() {',
        '    renderRequest++;',
        '    outDiv.innerHTML = "";',
        '    infoDiv.textContent = "";',
        '  }',
        '',
        '  function populateTags(sel, tags) {',
        '    sel.innerHTML = "";',
        '    tags.forEach(function(t) {',
        '      var o = document.createElement("option");',
        '      o.value = t; o.textContent = t;',
        '      sel.appendChild(o);',
        '    });',
        '  }',
        '',
        '  function populateLaws(list) {',
        '    lawSelect.innerHTML = "";',
        '    list.forEach(function(law) {',
        '      var o = document.createElement("option");',
        '      o.value = law.path || ("lover/" + law.file);',
        '      o.textContent = (law.korttittel || law.tittel).substring(0,80);',
        '      o.dataset.tags = JSON.stringify(law.tags);',
        '      o.dataset.file = law.file;',
        '      lawSelect.appendChild(o);',
        '    });',
        '    if (list.length > 0) {',
        '      lawSelect.selectedIndex = 0;',
        '    }',
        '    onLawSelect();',
        '  }',
        '',
        '  function onLawSelect() {',
        '    clearDiff();',
        '    var opt = lawSelect.options[lawSelect.selectedIndex];',
        '    var tags = opt ? JSON.parse(opt.dataset.tags || "[]") : [];',
        '    tags = tags.filter(function(tag) { return Object.prototype.hasOwnProperty.call(versionRefs, tag); });',
        '    populateTags(fromSelect, tags);',
        '    populateTags(toSelect, tags);',
        '    if (tags.length >= 2) {',
        '      fromSelect.selectedIndex = Math.max(0, tags.length - 2);',
        '      toSelect.selectedIndex = tags.length - 1;',
        '    }',
        '  }',
        '',
        '  loadSearchCatalog().then(function(data) {',
        '    laws = data.laws;',
        '    fuse = new Fuse(laws, {',
        '      keys: ["tittel","korttittel","refid"],',
        '      threshold: 0.35',
        '    });',
        '    populateLaws(laws);',
        '  });',
        '',
        '  lawSelect.addEventListener("change", onLawSelect);',
        '  fromSelect.addEventListener("change", clearDiff);',
        '  toSelect.addEventListener("change", clearDiff);',
        '',
        '  lawSearch.addEventListener("input", function() {',
        '    var q = lawSearch.value.trim();',
        '    if (!fuse || q.length < 2) { populateLaws(laws); return; }',
        '    var hits = fuse.search(q, {limit:30}).map(function(r){return r.item;});',
        '    populateLaws(hits);',
        '  });',
        '',
        '  renderBtn.addEventListener("click", function() {',
        '    clearDiff();',
        '    var request = renderRequest;',
        '    var path = lawSelect.value;',
        '    var from = fromSelect.value;',
        '    var to = toSelect.value;',
        '    if (!path || !from || !to) { infoDiv.textContent = "Velg lov og versjoner."; return; }',
        '    if (from === to) { infoDiv.textContent = "Velg to ulike versjoner."; return; }',
        '    if (from > to) { var tmp = from; from = to; to = tmp; }',
        '    infoDiv.textContent = "Henter " + from + " og " + to + "...";',
        '    Promise.all([',
        '      fetch(raw + "/" + versionRefs[from] + "/" + path).then(function(r){',
        '        if (!r.ok) throw new Error(from + ": HTTP " + r.status);',
        '        return r.text();',
        '      }),',
        '      fetch(raw + "/" + versionRefs[to] + "/" + path).then(function(r){',
        '        if (!r.ok) throw new Error(to + ": HTTP " + r.status);',
        '        return r.text();',
        '      })',
        '    ]).then(function(parts) {',
        '      if (request !== renderRequest) return;',
        '      var oldText = parts[0];',
        '      var newText = parts[1];',
        '      if (oldText === newText) {',
        '        outDiv.innerHTML = "<p style=\\"padding:1rem;background:#e6ffec;border-left:3px solid #1a7f37;\\">Ingen tekstforskjell mellom " + from + " og " + to + ".</p>";',
        '        infoDiv.textContent = "";',
        '        return;',
        '      }',
        '      var oldHeader = path + " @ " + from;',
        '      var newHeader = path + " @ " + to;',
        '      var patch = Diff.createPatch(path, oldText, newText, oldHeader, newHeader, {context:3});',
        '      var ui = new Diff2HtmlUI(outDiv, patch, {',
        '        drawFileList: false,',
        '        matching: "lines",',
        '        outputFormat: "side-by-side",',
        '        renderNothingWhenEmpty: false,',
        '        synchronisedScroll: true,',
        '      });',
        '      ui.draw();',
        '      infoDiv.textContent = "Diff " + from + " → " + to;',
        '    }).catch(function(err) {',
        '      if (request !== renderRequest) return;',
        '      infoDiv.textContent = "Kunne ikke hente: " + err.message;',
        '    });',
        '  });',
        '',
        '  compareBtn.addEventListener("click", function() {',
        '    var from = fromSelect.value;',
        '    var to = toSelect.value;',
        '    if (!from || !to) { clearDiff(); infoDiv.textContent = "Velg versjoner."; return; }',
        '    if (from === to) { clearDiff(); infoDiv.textContent = "Velg to ulike versjoner."; return; }',
        '    if (from > to) { var tmp = from; from = to; to = tmp; }',
        '    window.open(base + "/compare/" + versionRefs[from] + "..." + versionRefs[to], "_blank");',
        '  });',
        '',
        '  logBtn.addEventListener("click", function() {',
        '    var path = lawSelect.value;',
        '    if (!path) { infoDiv.textContent = "Velg en lov."; return; }',
        '    window.open(base + "/commits/law-history/" + path, "_blank");',
        '  });',
        '});',
        '</script>',
        '```',
        '',
    ]
    with open(os.path.join(book_dir, "diff.qmd"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_subscribe_page(book_dir: str):
    """Find documents in the compact catalog, offering only generated feeds."""
    page = r"""---
title: "Abonner på endringer"
search: false
---

Atom-feeder finnes for dokumenter med registrerte endringskunngjøringer i datagrunnlaget. Søk etter en lov eller forskrift for å se om en feed er tilgjengelig. Hver dokumentfeed viser inntil 50 oppføringer, og er ikke en fullstendig endringshistorikk. Du trenger en egen feed-leser for å følge nye oppføringer.

```{=html}
<style>
#abonner-search { box-sizing: border-box; width: 100%; padding: 8px 12px; margin: 8px 0 16px; font-size: 1em; border: 1px solid #ccc; border-radius: 4px; }
.abonner-card { min-width: 0; overflow-wrap: anywhere; border: 1px solid #dee2e6; border-radius: 6px; padding: 1rem; margin: .6rem 0; background: #fff; }
.abonner-card h2 { font-size: 1.05em; margin: 0; border: 0; }
.abonner-detail { font-size: .85em; color: #6c757d; margin: .25rem 0; }
.abonner-actions { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; margin: .75rem 0; }
.abonner-url { box-sizing: border-box; flex: 1 1 100%; width: 100%; min-width: 0; padding: 6px 10px; font-family: monospace; font-size: .9em; border: 1px solid #ced4da; border-radius: 4px; background: #f8f9fa; }
.abonner-actions button, .abonner-open { padding: 6px 12px; border: 1px solid #2780e3; border-radius: 4px; }
.abonner-actions button { background: #2780e3; color: #fff; cursor: pointer; }
.abonner-open { background: #f8f9fa; color: #2780e3; text-decoration: none; }
</style>
<label for="abonner-search" style="font-weight:600;font-size:1.1em;">Søk etter lov eller forskrift:</label>
<input type="search" id="abonner-search" placeholder="f.eks. regnskapsloven, aml, pbl, skatteloven...">
<p id="abonner-status" role="status">Laster søke- og feedkatalog…</p>
<div id="abonner-results" aria-live="polite"></div>
```

## Flere feeds

- [Skatte- og avgiftsrett](../feeds/topic-skatte--og-avgiftsrett.xml)
- [Bank, finans og regnskapsrett](../feeds/topic-bank-finans-og-regnskapsrett.xml)
- [Arbeidsrett](../feeds/topic-arbeidsrett.xml)
- [Finansdepartementet](../feeds/dept-finansdepartementet.xml)
- [Justis- og beredskapsdepartementet](../feeds/dept-justis--og-beredskapsdepartementet.xml)
- [Se alle tilgjengelige feeds](../feeds/index.html)

## Hvordan abonnere

- **RSS-leser** (Feedly, Inoreader, NetNewsWire, Thunderbird): lim inn feed-URL-en.
- **Slack**: bruk `/feed subscribe <URL>` i ønsket kanal hvis RSS-integrasjonen er tilgjengelig.
- **GitHub Actions, Python eller automatiseringsverktøy**: se [SUBSCRIBE.md](https://github.com/sondreskarsten/norwegian-laws/blob/main/SUBSCRIBE.md) for eksempler.

Denne siden oppretter ikke abonnementer eller sender varsler. Det styres av verktøyet du velger.

```{=html}
<script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
<script>
__CATALOG_LOADER__
document.addEventListener("DOMContentLoaded", function() {
  var input = document.getElementById("abonner-search");
  var results = document.getElementById("abonner-results");
  var status = document.getElementById("abonner-status");
  var feeds = {};
  var fuse = null;

  function appendText(parent, tag, text, className) {
    var node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    parent.appendChild(node);
    return node;
  }

  function renderResults() {
    results.replaceChildren();
    if (!fuse) return;
    var query = input.value.trim();
    if (query.length < 2) {
      status.textContent = "Skriv minst to tegn for å finne et dokument.";
      return;
    }
    var hits = fuse.search(query).map(function(hit) { return hit.item; });
    status.textContent = hits.length ? hits.length + " treff. Viser inntil 6." : "Ingen treff.";
    hits.slice(0, 6).forEach(function(law) {
      var card = document.createElement("article");
      card.className = "abonner-card";
      card.dataset.refid = law.refid;
      var heading = appendText(card, "h2", "");
      var link = appendText(heading, "a", law.tittel);
      link.href = "../" + law.path.replace(/\.md$/, ".html");
      if (law.korttittel) appendText(card, "p", law.korttittel, "abonner-detail");
      if (law.aliases && law.aliases.length) {
        appendText(card, "p", "Aliaser: " + law.aliases.slice(0, 4).join(", "), "abonner-detail");
      }
      var feed = feeds[law.refid];
      if (!feed) {
        appendText(card, "p", "Ingen dokumentfeed tilgjengelig i denne publiseringen. Du kan lese dokumentet eller velge en bredere feed nedenfor.");
        results.appendChild(card);
        return;
      }
      appendText(card, "p", feed.count + " oppføringer i feeden (inntil 50).", "abonner-detail");
      var actions = document.createElement("div");
      actions.className = "abonner-actions";
      var url = new URL("../" + feed.path, window.location.href).href;
      var field = document.createElement("input");
      field.className = "abonner-url";
      field.type = "text";
      field.value = url;
      field.readOnly = true;
      field.setAttribute("aria-label", "Feed-URL for " + (law.korttittel || law.tittel));
      actions.appendChild(field);
      var copy = appendText(actions, "button", "Kopier URL");
      copy.type = "button";
      var copyStatus = document.createElement("p");
      copyStatus.className = "abonner-detail";
      copyStatus.setAttribute("role", "status");
      copy.addEventListener("click", async function() {
        try {
          await navigator.clipboard.writeText(url);
          copy.textContent = "✓ Kopiert";
          copyStatus.textContent = "Feed-URL kopiert. Lim den inn i feed-leseren din.";
        } catch (error) {
          field.focus();
          field.select();
          copyStatus.textContent = "Automatisk kopiering er ikke tilgjengelig. URL-en er markert; kopier den manuelt.";
        }
      });
      var open = appendText(actions, "a", "Åpne feed", "abonner-open");
      open.href = url;
      card.appendChild(actions);
      card.appendChild(copyStatus);
      results.appendChild(card);
    });
  }

  input.addEventListener("input", renderResults);
  Promise.all([
    loadSearchCatalog(),
    fetch("../feeds/index.json").then(function(response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
  ]).then(function(data) {
    if (!data[1].laws || typeof data[1].laws !== "object") throw new Error("Ukjent feedkatalog");
    feeds = data[1].laws;
    fuse = new Fuse(data[0].laws, {
      keys: [
        {name: "tittel", weight: .35}, {name: "korttittel", weight: .25},
        {name: "aliases", weight: .25}, {name: "refid", weight: .1},
        {name: "departement", weight: .05}
      ],
      threshold: .35, distance: 200, minMatchCharLength: 2
    });
    renderResults();
  }).catch(function(error) {
    status.textContent = "Kunne ikke laste søke- og feedkatalogen. Last siden på nytt, eller bruk feed-katalogen nedenfor.";
  });
});
</script>
```
"""
    page = page.replace("__CATALOG_LOADER__", "\n".join(_catalog_loader_lines()))
    Path(book_dir, "abonner.qmd").write_text(page, encoding="utf-8")


def generate_quarto_config(repo_root: str, lover_dir: str = "lover", forskrifter_dir: str = "forskrifter", version_tags: list[str] = None, db_path: str = None, *, source_evidence_links: bool = False):
    """Generate the full Quarto book configuration and chapter files.

    source_evidence_links requires the caller to supply evidence.json and
    snapshot-manifest.json in the rendered site before link validation.
    """
    full_lover = os.path.join(repo_root, lover_dir)
    full_forskrifter = os.path.join(repo_root, forskrifter_dir)
    book_dir = os.path.join(repo_root, "book")
    os.makedirs(book_dir, exist_ok=True)

    groups = group_laws_by_area(full_lover)
    forskrift_groups = group_laws_by_area(full_forskrifter) if os.path.isdir(full_forskrifter) else {}
    topic_groups = group_laws_by_topic(full_lover)

    n_acts = None
    n_amendments = None
    version_tags = supported_version_tags(version_tags)
    if db_path and os.path.exists(db_path):
        from .manifests import count_manifest_rows
        n_acts, n_amendments = count_manifest_rows(db_path)

    # Amendment counts per law refid (for enriching laws.json)
    amendment_counts = {}
    if db_path and os.path.exists(db_path):
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                """
                SELECT target_law, COUNT(DISTINCT act_refid) AS n
                FROM amendments
                WHERE target_law IS NOT NULL AND target_law != ''
                GROUP BY target_law
                """
            ).fetchall()
            amendment_counts = {tl: n for tl, n in rows}
            conn.close()
        except Exception as e:
            print(f"  could not compute amendment counts: {e}")

    # Generate laws.json (lover + forskrifter)
    laws_json_path = os.path.join(repo_root, "laws.json")
    from .historie_pages import scan_historie_slugs
    generate_laws_json(full_lover, laws_json_path, version_tags,
                       historie_slugs=scan_historie_slugs(os.path.join(repo_root, "historie")),
                       forskrifter_dir=full_forskrifter if os.path.isdir(full_forskrifter) else None,
                       amendment_counts=amendment_counts)

    # Generate search + diff + abonner pages
    generate_search_page(book_dir)
    generate_diff_page(book_dir, version_tags)
    generate_subscribe_page(book_dir)

    # Amendment stats
    year_stats = get_amendment_stats_by_year(db_path) if db_path else {}

    # Department chapters — lover
    chapters = []
    for dept, laws in groups.items():
        safe_dept = re.sub(r"[^\w\s-]", "", dept).strip().replace(" ", "-").lower()
        dept_file = f"dept-{safe_dept}.qmd"
        dept_path = os.path.join(book_dir, dept_file)

        lines = [f"# {dept}\n"]
        lines.append(f"*{len(laws)} lover*\n")
        lines.append("| Lov | Korttittel | Lovdata | Historikk |")
        lines.append("|-----|-----------|---------|-----------|")
        for law in sorted(laws, key=lambda x: x["tittel"]):
            stem = law["file"].rsplit(".", 1)[0]
            page = f"../lover/{stem}.html"
            history = f"{GITHUB_BASE}/commits/{HISTORY_BRANCH}/lover/{law['file']}"
            lovdata_url = f"https://lovdata.no/dokument/NL/{law['refid']}"
            title = law["tittel"][:80]
            link = f"[{title}]({page})"
            kort = law["korttittel"] or ""
            lovdata_link = f"[lovdata.no]({lovdata_url})"
            vtags = compute_version_links(law["refid"], version_tags)
            version_links = " · ".join(
                f"[{t}]({GITHUB_BASE}/blob/{LEGACY_VERSION_REFS[t]}/lover/{law['file']})"
                for t in vtags
            )
            hist_cell = f"[log]({history}) · {version_links}"
            lines.append(f"| {link} | {kort} | {lovdata_link} | {hist_cell} |")
        lines.append("")

        with open(dept_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        chapters.append(f"book/{dept_file}")

    # Department chapters — forskrifter
    forskrift_chapters = []
    for dept, forskrifter in forskrift_groups.items():
        safe_dept = re.sub(r"[^\w\s-]", "", dept).strip().replace(" ", "-").lower()
        dept_file = f"forskrift-dept-{safe_dept}.qmd"
        dept_path = os.path.join(book_dir, dept_file)

        lines = [f"# {dept}\n"]
        lines.append(f"*{len(forskrifter)} forskrifter*\n")
        lines.append("| Forskrift | Lovdata | Historikk |")
        lines.append("|-----------|---------|-----------|")
        for forskrift in sorted(forskrifter, key=lambda x: x["tittel"]):
            stem = forskrift["file"].rsplit(".", 1)[0]
            page = f"../forskrifter/{stem}.html"
            history = f"{GITHUB_BASE}/commits/{HISTORY_BRANCH}/forskrifter/{forskrift['file']}"
            lovdata_url = f"https://lovdata.no/dokument/SF/{forskrift['refid']}"
            title = forskrift["tittel"][:80]
            link = f"[{title}]({page})"
            lovdata_link = f"[lovdata.no]({lovdata_url})"
            hist_cell = f"[log]({history})"
            lines.append(f"| {link} | {lovdata_link} | {hist_cell} |")
        lines.append("")

        with open(dept_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        forskrift_chapters.append(f"book/{dept_file}")

    # Topic chapters — group laws by rettsomrade (second navigation axis)
    topic_chapters = []
    for topic, topic_laws in topic_groups.items():
        safe_topic = re.sub(r"[^\w\s-]", "", topic).strip().replace(" ", "-").lower()
        topic_file = f"topic-{safe_topic}.qmd"
        topic_path = os.path.join(book_dir, topic_file)

        lines = [f"# {topic}\n"]
        lines.append(f"*{len(topic_laws)} lover*\n")
        lines.append("| Lov | Korttittel | Departement |")
        lines.append("|-----|-----------|-------------|")
        for law in sorted(topic_laws, key=lambda x: x["tittel"]):
            stem = law["file"].rsplit(".", 1)[0]
            page = f"../lover/{stem}.html"
            title = law["tittel"][:80]
            link = f"[{title}]({page})"
            kort = law["korttittel"] or ""
            dept = law["departement"] or ""
            lines.append(f"| {link} | {kort} | {dept} |")
        lines.append("")

        with open(topic_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        topic_chapters.append(f"book/{topic_file}")

    # Prune generated chapter files this run no longer produces. Stale
    # topic-/dept- qmds otherwise accumulate forever because the deploy
    # workflow only ever git-adds book/ and never removes obsolete output.
    written = {os.path.basename(c) for c in chapters + forskrift_chapters + topic_chapters}
    pruned = 0
    for pattern in ("dept-*.qmd", "forskrift-dept-*.qmd", "topic-*.qmd"):
        for stale in Path(book_dir).glob(pattern):
            if stale.name not in written:
                stale.unlink()
                pruned += 1
    if pruned:
        print(f"  Pruned {pruned} stale generated chapter files from {book_dir}/")

    # Versions page
    ver_lines = [
        "# Eksperimentelle versjoner {.unnumbered}\n",
        LEGACY_NOTICE + "\n",
        "Årstallene nedenfor er navn på eldre rekonstruksjoner, ikke bekreftede juridiske skjæringsdatoer.",
        "Utvalget er registrert 25. september 2026. Lenker og sammenligninger er låst til disse kopiene.",
        "Den frakoblede v2000 og utgaver merket med framtidige år er utelatt.\n",
        "## Lagrede rekonstruksjoner\n",
    ]
    if year_stats:
        ver_lines.append("| Versjon | Bla gjennom | Endringer fra forrige | Omfang |")
        ver_lines.append("|---------|-------------|----------------------|--------|")
    else:
        ver_lines.append("| Versjon | Bla gjennom | Endringer fra forrige |")
        ver_lines.append("|---------|-------------|----------------------|")

    for i, tag in enumerate(version_tags):
        year = tag[1:]
        browse = f"[{tag}]({GITHUB_BASE}/tree/{LEGACY_VERSION_REFS[tag]}/lover)"
        if i > 0:
            prev = version_tags[i - 1]
            diff = f"[{prev}...{tag}]({GITHUB_BASE}/compare/{LEGACY_VERSION_REFS[prev]}...{LEGACY_VERSION_REFS[tag]})"
        else:
            diff = "\u2014"
        if year_stats:
            st = year_stats.get(year, {})
            acts = st.get("acts", 0)
            stat_cell = f"{acts} vedtak" if acts else "\u2014"
            ver_lines.append(f"| `{tag}` | {browse} | {diff} | {stat_cell} |")
        else:
            ver_lines.append(f"| `{tag}` | {browse} | {diff} |")

    ver_lines.append("")
    ver_lines.append("## Verktøy\n")
    ver_lines.append("- [Søk i lover](sok.qmd) \u2014 finn lover etter tittel eller korttittel")
    ver_lines.append("- [Sammenlign lovversjon](diff.qmd) \u2014 velg lov og to årstall for å se endringer\n")
    ver_lines.append("## Bruk med git\n")
    ver_lines.append("```bash")
    ver_lines.append("# Klon historikk-grenen")
    ver_lines.append(f"git clone -b {HISTORY_BRANCH} {GITHUB_BASE}.git")
    ver_lines.append("cd norwegian-laws")
    ver_lines.append("")
    ver_lines.append("# Les den lagrede rekonstruksjonen merket v2020 (ikke verifisert lovtekst for 2020)")
    ver_lines.append(f"git show {LEGACY_VERSION_REFS['v2020']}:lover/lov-1998-07-17-56.md")
    ver_lines.append("")
    ver_lines.append("# Sammenlign to versjoner av en lov")
    ver_lines.append(f"git diff {LEGACY_VERSION_REFS['v2020']} {LEGACY_VERSION_REFS['v2024']} -- lover/lov-1998-07-17-56.md")
    ver_lines.append("")
    ver_lines.append("# Se tekstforskjeller mellom to lagrede rekonstruksjoner")
    ver_lines.append(f"git diff --stat {LEGACY_VERSION_REFS['v2023']} {LEGACY_VERSION_REFS['v2024']}")
    ver_lines.append("```\n")

    with open(os.path.join(book_dir, "versjoner.qmd"), "w", encoding="utf-8") as f:
        f.write("\n".join(ver_lines))

    # Quarto config
    config = {
        "project": {"type": "book", "output-dir": "_site"},
        "lang": "nb",
        "book": {
            "title": "Norges Lover og Forskrifter",
            "subtitle": "Gjeldende formelle lover og sentrale forskrifter",
            "author": "Kilde: Lovdata API (NLOD 2.0)",
            "date": "today",
            "chapters": [
                "index.qmd",
                {"part": "Lover etter departement", "chapters": chapters},
            ] + (
                [{"part": "Lover etter rettsområde", "chapters": topic_chapters}]
                if topic_chapters else []
            ) + (
                [{"part": "Sentrale forskrifter etter departement", "chapters": forskrift_chapters}]
                if forskrift_chapters else []
            ) + [
                "book/versjoner.qmd",
                "book/sok.qmd",
                "book/diff.qmd",
                "book/abonner.qmd",
                "book/about.qmd",
            ],
            "search": True,
            "repo-url": GITHUB_BASE,
            "repo-actions": ["source", "issue"],
        },
        "format": {
            "html": {
                "theme": "cosmo",
                "toc": True,
                "toc-depth": 3,
                "number-sections": False,
                "code-fold": True,
                "lang": "nb",
                "include-in-header":
                    "assets/head-meta.html",
            }
        },
    }

    with open(os.path.join(repo_root, "_quarto.yml"), "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Landing page
    total_unique = len({e["file"] for laws in groups.values() for e in laws})
    total_forskrifter = len({e["file"] for laws in forskrift_groups.values() for e in laws})
    total_docs = total_unique + total_forskrifter
    fmt_no = lambda n: f"{n:,}".replace(",", "\u00a0")
    amendments_line = (
        f"- [`amendments.jsonl.gz`](amendments.jsonl.gz) \u2014 {fmt_no(n_amendments)} visningsrader med identifisert m\u00e5llov eller -forskrift. `new_text` er avkortet til 4\u00a0000 tegn"
        if n_amendments is not None else
        "- [`amendments.jsonl.gz`](amendments.jsonl.gz) \u2014 visningsrader med identifisert m\u00e5llov eller -forskrift. `new_text` er avkortet til 4\u00a0000 tegn"
    )
    acts_line = (
        f"- [`amendment-acts.jsonl.gz`](amendment-acts.jsonl.gz) \u2014 {fmt_no(n_acts)} kunngj\u00f8ringer med publiseringsdato fra Norsk Lovtidend, inkludert endringslover og forskrifter"
        if n_acts is not None else
        "- [`amendment-acts.jsonl.gz`](amendment-acts.jsonl.gz) \u2014 kunngj\u00f8ringer med publiseringsdato fra Norsk Lovtidend, inkludert endringslover og forskrifter"
    )
    index_lines = [
        "# Forord {.unnumbered}\n",
        "Dette er en uoffisiell samling av Norges gjeldende formelle lover,",
        "generert fra [Lovdata API](https://api.lovdata.no/) sine åpne data",
        "under [NLOD 2.0](https://data.norge.no/nlod/no/2.0)-lisensen.\n",
        f"Samlingen inneholder **{total_unique} lover** og",
        f"**{fmt_no(total_forskrifter)} sentrale forskrifter**,",
        f"fordelt på **{len(groups)} departementer**.\n",
        "## 🔔 Spor endringer\n",
        "Atom-feeder finnes for dokumenter med registrerte endringskunngjøringer i datagrunnlaget.",
        "Hver dokumentfeed viser inntil 50 oppføringer; dekningen er ikke en fullstendig endringshistorikk.",
        "Søk etter dokumentet for å se om en feed er tilgjengelig, og legg den til i din egen feed-leser.\n",
        "- [Abonner](book/abonner.qmd) — finn tilgjengelige dokumentfeeder, pluss feeder per rettsområde og departement",
        "- [Aktivitet](aktivitet.html) — topp-liste over de mest endrede lovene, forskriftene, departementene og årgangene",
        "- [Feed-katalog](feeds/) — bla gjennom alle Atom-feeder direkte",
        "- Eksempel: [Atom-feed for regnskapsloven](feeds/lov-1998-07-17-56.xml) · [endringer i § 7-25 spesifikt](historikk/lov-1998-07-17-56/para-7-25.html)\n",
        "## 📥 Bulk-data\n",
        "For nedstrøms automatisering (datavarehus, compliance-dashboards, interne CDC-pipelines):\n",
        amendments_line,
        acts_line,
        f"- [`laws.json`](laws.json) — alle {fmt_no(total_docs)} lover/forskrifter med metadata og endringstellere",
        *([
            "- [Kildekvittering](evidence.json) — kildeobservasjon og permanent lenke til kildepakken",
            "- [Snapshot-manifest](snapshot-manifest.json) — nøyaktig dokumentoversikt og sjekksummer",
        ] if source_evidence_links else []),
        "- [`schemas/`](schemas/amendment-acts.schema.json) — JSON Schema 2020-12 for begge JSONL-strømmene\n",
        "## Les lover\n",
        "- [Søk etter lov](book/sok.qmd) \u2014 finn lover etter tittel, korttittel eller lovnummer",
        "- Bla gjennom lover etter departement i sidemenyen",
        "- Klikk en lov for å lese lovteksten på GitHub",
        "- For autoritativ lovtekst, se [lovdata.no](https://lovdata.no)\n",
        "## Utforsk historikk\n",
        LEGACY_NOTICE + "\n",
        f"- [`{HISTORY_BRANCH}`-grenen]({GITHUB_BASE}/tree/{HISTORY_BRANCH}) inneholder den eldre rekonstruksjonen",
        "- [Eksperimentelle versjoner](book/versjoner.qmd) \u2014 sammenlign registrerte kopier",
        "- [Sammenlign lovversjon](book/diff.qmd) \u2014 velg en lov og to årstall for å se endringer",
        "- Klikk \u00ablog\u00bb i lovtabellene for å se endringshistorikk for en enkelt lov\n",
        "## Ansvarsfraskrivelse\n",
        "Denne samlingen er **uoffisiell** og oppdateres automatisk fra Lovdatas åpne API.",
        "For autoritativ lovtekst, se [lovdata.no](https://lovdata.no).",
        "Innholdet presenteres \u00absom det er\u00bb uten garanti for korrekthet eller aktualitet.\n",
    ]
    with open(os.path.join(repo_root, "index.qmd"), "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))

    # About page
    about_lines = [
        "# Om dette prosjektet {.unnumbered}\n",
        "## Datakilde\n",
        "Lovtekstene er hentet fra [Lovdata API](https://api.lovdata.no/) sine åpne data.\n",
        "## Lisens\n",
        "Innholdet er tilgjengelig under",
        "[Norsk lisens for offentlige data (NLOD) 2.0](https://data.norge.no/nlod/no/2.0).\n",
        "> Inneholder data under Norsk lisens for offentlige data (NLOD)",
        "> tilgjengeliggjort av Lovdata.\n",
        "Kildekoden for dette prosjektet er lisensiert under MIT.\n",
        "## Kontakt\n",
        "Kildekode og feilrapportering:",
        f"[github.com/sondreskarsten/norwegian-laws]({GITHUB_BASE})\n",
    ]
    with open(os.path.join(book_dir, "about.qmd"), "w", encoding="utf-8") as f:
        f.write("\n".join(about_lines))

    print(f"  Generated Quarto config: {total_unique} laws in {len(groups)} departments")
    return config


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    db = sys.argv[2] if len(sys.argv) > 2 else None
    generate_quarto_config(repo, db_path=db)
