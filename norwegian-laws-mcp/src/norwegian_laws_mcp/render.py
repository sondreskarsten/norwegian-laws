"""Markdown rendering of service results."""
from __future__ import annotations


def _limits(res: dict) -> list[str]:
    """Render the 'Data coverage and limits' block shared by the history tools."""
    out = ["", "## Data coverage and limits"]
    cov = res.get("coverage")
    if cov:
        out.append(f"- {cov['statement']}")
    for note in res.get("limitations") or []:
        out.append(f"- {note}")
    if res.get("note"):
        out.append(f"- {res['note']}")
    return out


def _kind_tag(kind: str | None) -> str:
    if kind == "pipeline":
        return " [pipeline]"
    if kind == "parser-regeneration":
        return " [parser regeneration, not a source change]"
    return ""


def _doc_line(d: dict) -> str:
    title = d.get("short_title") or d.get("title") or d.get("refid")
    extra = []
    if d.get("short_title") and d.get("title") and d["short_title"] != d["title"]:
        extra.append(d["title"])
    if d.get("aliases"):
        extra.append("aliases: " + ", ".join(d["aliases"]))
    if d.get("department"):
        extra.append(", ".join(d["department"]))
    if d.get("in_force"):
        extra.append(f"in force: {d['in_force']}")
    if d.get("last_amended_by"):
        extra.append(f"last amended by {d['last_amended_by']}")
    if d.get("amendment_records"):
        extra.append(f"{d['amendment_records']} amendment records")
    if d.get("removed_from_corpus"):
        extra.append(f"REMOVED from the current corpus {d['removed_from_corpus']}")
    tail = f" — {'; '.join(extra)}" if extra else ""
    return f"**{title}** `{d['refid']}` ({d['kind']}, `{d['path']}`){tail}"


def search_documents(query: str, items: list[dict]) -> str:
    if not items:
        return f"No documents match '{query}'. Try a shorter query, an abbreviation (e.g. 'asl'), or a refid."
    lines = [f"# Documents matching '{query}' ({len(items)})", ""]
    for d in items:
        lines.append(f"- {_doc_line(d)} [score {d['score']}]")
    return "\n".join(lines)


def document(res: dict) -> str:
    d = res["document"]
    head = [f"# {d.get('title') or d['refid']}", f"{_doc_line(d)}", f"Lovdata: {d['lovdata']}"]
    prov = res.get("provenance") or {}
    if prov.get("rev"):
        head.append(f"Text source: {prov['source']} (`{prov['rev'][:10]}`, {str(prov.get('date') or '')[:10]})")
    for note in prov.get("limitations") or []:
        head.append(f"Limit: {note}")
    head.append("")
    if res["mode"] == "metadata":
        head.append("## Front matter")
        for k, v in res["front_matter"].items():
            head.append(f"- {k}: {v}")
        head.append("")
        head.append(f"{res['headings']} headings, {res['lines']} lines, {res['characters']} characters.")
        return "\n".join(head)
    if res["mode"] == "outline":
        head.append("## Outline")
        for h in res["outline"]:
            indent = "  " * (h["level"] - 1)
            key = f" [section {h['section']}]" if h.get("section") else ""
            head.append(f"{indent}- L{h['line']}: {h['text']}{key}")
        return "\n".join(head)
    if res.get("section"):
        s = res["section"]
        head.append(f"Section: {s['heading']} (lines {s['start_line']}–{s['end_line']})")
        head.append("")
    body = res["text"]
    tail = ""
    if res.get("truncated"):
        tail = (f"\n\n[... truncated at {res['offset'] + len(body)} of {res['total_characters']} characters; "
                f"call again with offset={res['next_offset']} to continue]")
    return "\n".join(head) + body + tail


def search_text(res: dict) -> str:
    if res["total_hits"] == 0:
        return f"No matches for '{res['query']}'."
    lines = [f"# Text search: '{res['query']}' — {res['total_hits']} matching lines in "
             f"{len(res['results'])} documents shown", ""]
    for r in res["results"]:
        ident = f"`{r['refid']}`" if r["refid"] else f"`{r['path']}`"
        lines.append(f"## {r['title']} {ident} — {r['hits_in_document']} hits")
        for h in r["hits"]:
            sec = f" ({h['section']})" if h["section"] else ""
            lines.append(f"- L{h['line']}{sec}: {h['text']}")
        lines.append("")
    return "\n".join(lines)


def definitions(res: dict) -> str:
    if not res["definitions"]:
        return (f"No definition-like passages found for '{res['term']}' (stem '{res['stem']}', "
                f"{res['total_mentions']} plain mentions). Try laws_search_text for all mentions.")
    lines = [f"# Where '{res['term']}' is defined (stem '{res['stem']}', {res['total_mentions']} mentions in total)", ""]
    for d in res["definitions"]:
        ident = f"`{d['refid']}`" if d["refid"] else f"`{d['path']}`"
        sec = f", {d['section']}" if d["section"] else ""
        lines.append(f"- **{d['title']}** {ident}{sec}, line {d['line']} [score {d['score']}: {d['why']}]")
        lines.append(f"  > {d['text']}")
    return "\n".join(lines)


def _change_items(items: list[dict]) -> list[str]:
    out = []
    for d in items:
        ident = f"`{d['refid']}`" if d["refid"] else ""
        title = d["title"] or d["path"]
        when = d["last_change"][:10] if d["first_change"] == d["last_change"] else f"{d['first_change'][:10]} → {d['last_change'][:10]}"
        out.append(f"- {d['status']}: **{title}** {ident} `{d['path']}` ({when}, {len(d['commits'])} commit(s))")
    return out


def recent_changes(res: dict) -> str:
    window = f"since {res['since']}" if res["since"] else "all history"
    if res["until"]:
        window += f" until {res['until']}"
    lines = [f"# Changes {window}", ""]
    if not res["commits"]:
        lines.append("No commits touched the selected documents in this window.")
        lines += _limits(res)
        return "\n".join(lines)
    lines.append(f"## Commits ({len(res['commits'])})")
    for c in res["commits"]:
        lines.append(f"- {c['date'][:10]} `{c['sha'][:10]}` {c['subject']} ({c['files']} files){_kind_tag(c.get('kind'))}")
    lines.append("")
    lines.append(f"## Law/regulation texts changed ({res['total_text_documents_changed']})")
    lines += _change_items(res["text_documents"]) or ["- none"]
    if res["total_text_documents_changed"] > len(res["text_documents"]):
        lines.append(f"- ... {res['total_text_documents_changed'] - len(res['text_documents'])} more; narrow with kind/query/documents or raise limit")
    lines.append("")
    lines.append(f"## Parsed amendment records changed (historie/) ({res['total_amendment_record_files_changed']})")
    lines += _change_items(res["amendment_record_files"]) or ["- none"]
    if res["total_amendment_record_files_changed"] > len(res["amendment_record_files"]):
        lines.append(f"- ... {res['total_amendment_record_files_changed'] - len(res['amendment_record_files'])} more")
    lines += _limits(res)
    return "\n".join(lines)


def document_history(res: dict) -> str:
    d = res["document"]
    lines = [f"# History of {d.get('short_title') or d['refid']} `{d['refid']}` (`{d['path']}`)", ""]
    if not res["commits"]:
        lines.append("No commits touched this document in the selected window.")
    for c in res["commits"]:
        lines.append(f"- {c['date'][:10]} `{c['sha'][:10]}` +{c['added']}/-{c['deleted']} {c['subject']}{_kind_tag(c.get('kind'))}")
    lines += _limits(res)
    return "\n".join(lines)


def diff(res: dict) -> str:
    d = res["document"]
    sec = f" section {res['section']}" if res["section"] else ""
    f, t = res["from"], res["to"]
    f_req = f" (requested '{f['requested']}')" if f.get("clamped_to_first_commit") or f.get("clamped_to_head") else ""
    t_req = f" (requested '{t['requested']}')" if t.get("clamped_to_first_commit") or t.get("clamped_to_head") else ""
    lines = [f"# Diff of {d.get('short_title') or d['refid']} `{d['refid']}`{sec}",
             f"from `{f['rev'][:10]}` ({f['date'][:10]}){f_req} to `{t['rev'][:10]}` ({t['date'][:10]}){t_req}", ""]
    if f["existed"] and not t["existed"]:
        lines.append("The document no longer exists at the end revision.")
    if not res["changed"]:
        lines.append("No textual change between these revisions in the repository.")
    else:
        lines += ["```diff", res["diff"].rstrip("\n"), "```"]
        if res["truncated"]:
            lines.append("[diff truncated; narrow with section=... or raise max_chars]")
    lines += _limits(res)
    return "\n".join(lines)


def blame(res: dict) -> str:
    d = res["document"]
    sec = f" — {res['section']}" if res["section"] else ""
    lines = [f"# Last change per line block: {d.get('short_title') or d['refid']} `{d['refid']}`{sec}",
             f"Lines {res['lines'][0]}–{res['lines'][1]}", ""]
    for r in res["runs"]:
        span = f"L{r['lines'][0]}" if r["lines"][0] == r["lines"][1] else f"L{r['lines'][0]}–{r['lines'][1]}"
        lines.append(f"- {span}: last changed {r['last_changed']} `{r['commit']}` ({r['subject']}){_kind_tag(r.get('kind'))} — {r['first_line']}")
    lines += _limits(res)
    return "\n".join(lines)


def amendment_records(res: dict) -> str:
    d = res["document"]
    lines = [f"# Amendment history: {d.get('short_title') or d['refid']} `{d['refid']}`", ""]
    flt = f" for § {res['section_filter']}" if res.get("section_filter") else ""
    if res.get("inline_amendment_notes"):
        lines.append(f"## Lovdata's per-provision notes in the current text{flt} ({len(res['inline_amendment_notes'])})")
        for n in res["inline_amendment_notes"]:
            lines.append(f"- **{n['section']}**: {n['note']}")
        lines.append("")
    if res.get("message"):
        lines.append(f"## Parsed Lovtidend records{flt}")
        lines.append(res["message"])
    else:
        span = f"{res['earliest_record']} to {res['latest_record']}" if res.get("earliest_record") else "none"
        lines.append(f"## Parsed Lovtidend records{flt}: {res['total']} of {res['total_in_file']} in `{res['source_file']}` "
                     f"(file covers {span}), newest first")
        lines.append("")
        for r in res["records"]:
            url = f" <{r['amending_act_url']}>" if r.get("amending_act_url") else ""
            lines.append(f"### {r['date']} — {r['paragraph']} — by `{r['amending_act']}`{url}")
            if r["instruction"]:
                lines.append(f"*{r['instruction']}*")
            if r["text"]:
                lines.append("")
                lines += [f"> {t}" for t in r["text"].split("\n")]
            lines.append("")
        if res["total"] > len(res["records"]):
            lines.append(f"[... {res['total'] - len(res['records'])} more; raise limit or filter by section/since]")
    lines += _limits(res)
    return "\n".join(lines)


def related(res: dict) -> str:
    d = res["document"]
    lines = [f"# Documents related to {d.get('short_title') or d['refid']} `{d['refid']}`",
             f"Searched for: {', '.join(res['search_terms'])}", ""]
    if not res["related"]:
        lines.append("No other document mentions this one by short title or citation.")
        return "\n".join(lines)
    for r in res["related"]:
        ident = f"`{r['refid']}`" if r["refid"] else f"`{r['path']}`"
        lines.append(f"- **{r['title']}** {ident} ({r['kind']}) — {r['mentions']} mentions; matched {', '.join(r['matched'])}")
    if res["total_related"] > len(res["related"]):
        lines.append(f"- ... {res['total_related'] - len(res['related'])} more")
    return "\n".join(lines)


def status(res: dict) -> str:
    h = res["head"]
    lines = [
        "# Repository status",
        f"- Checkout: `{res['path']}` ({'managed clone' if res['managed_clone'] else 'user-provided checkout'}) from {res['remote']}",
        f"- HEAD: `{h['sha'][:10]}` {h['date']} — {h['subject']}",
    ]
    lu = res["last_lovdata_update_commit"]
    if lu:
        lines.append(f"- Last Lovdata update commit: `{lu['sha'][:10]}` {lu['date']} — {lu['subject']}")
    lines.append(f"- Commits available: {res['commits_in_history']}{' (shallow clone)' if res['shallow'] else ''}")
    docs = res["documents"]
    lines.append(f"- Documents: {docs['total']} ({docs['lover']} lover, {docs['forskrifter']} forskrifter)")
    if res["last_update_check"]:
        u = res["last_update_check"]
        lines.append(f"- Last update check: {u['checked_at']} ({'new commits' if u['changed'] else 'no change'})")
    lines.append(f"- Parsed amendment records: Norsk Lovtidend avd. I from {res['lovtidend_from_year']}")
    lines.append(f"- Documents removed from the corpus over the branch history: {res['removed_documents']} (readable with laws_get_document; list with laws_search_documents include_removed=true)")
    lines.append(f"- Corpus scope: {res['corpus_scope']}")
    lines += _limits({"coverage": res["coverage"]})
    return "\n".join(lines)


def outline(res: dict) -> str:
    d = res["document"]
    lines = [f"# Outline of {d.get('short_title') or d.get('title')} `{d['refid']}`", ""]
    for n in res["nodes"]:
        indent = "" if n["kind"] == "chapter" else "  "
        lines.append(f"{indent}- {n['heading'] or n['address']} (lines {n['line_start']}–{n['line_end']})")
    if not res["nodes"]:
        lines.append("No chapters or §§ were recognised in this document.")
    lines += _limits(res)
    return "\n".join(lines)


def provision(res: dict) -> str:
    d, sec = res["document"], res["section"]
    lines = [f"# {d.get('short_title') or d.get('title')} — {sec.get('heading') or sec['address']}", f"`{d['refid']}` {sec['address']}", ""]
    for ledd in res["ledd"]:
        lines.append(f"**{ledd['address']}**")
        lines.append(ledd.get("text") or "")
        lines.append("")
    if sec.get("note"):
        lines.append(f"*{sec['note']}*")
        lines.append("")
    if res.get("wording_at"):
        w = res["wording_at"]
        lines += [f"## Last recorded wording on or before {res['at']}", f"Set by {w['act']} in force {w['date_in_force']} ({w['instruction']}):", "",
                  "> " + (w["text"] or "").replace("\n", "\n> "), "", f"- {w['note']}", ""]
    lines.append(f"## Amendment records for this § ({len(res['history'])})")
    for h in res["history"]:
        wording = " — wording recorded" if h.get("new_text") else ""
        lines.append(f"- {h['date_in_force'] or '?'} {h['act_refid']} [{h['change_type']}; {h.get('operations') or 'uncatalogued'}]: {h['instruction']}{wording}")
    if not res["history"]:
        lines.append("- none in Norsk Lovtidend records from 2001")
    lines += _limits(res)
    return "\n".join(lines)


def index_search(res: dict) -> str:
    hits = res["hits"]
    if not hits:
        return f"No provisions match '{res['query']}'." + "\n".join(_limits(res))
    lines = [f"# Provisions matching '{res['query']}' ({len(hits)})", ""]
    for h in hits:
        lines.append(f"- **{h.get('short_title') or h.get('title')}** `{h['refid']}` {h['address']} ({h['kind']}): …{h['snippet']}…")
    lines += _limits(res)
    return "\n".join(lines)


def references(res: dict) -> str:
    d = res["document"]
    target = f"{d['refid']}" + (f" § {res['section']}" if res.get("section") else "")
    refs = res["references"]
    lines = [f"# Provisions citing {d.get('short_title') or d.get('title')} ({target}): {len(refs)}", ""]
    for r in refs:
        sec = f" § {r['to_section']}" if r.get("to_section") else ""
        lines.append(f"- {r.get('short_title') or r.get('title')} `{r['from_refid']}` {r['from_address']} → {target.split(' ')[0]}{sec} ({r['ref_kind']}: “{r['text']}”)")
    lines += _limits(res)
    return "\n".join(lines)


def index_definitions(res: dict) -> str:
    defs = res["definitions"]
    lines = [f"# Definitions of '{res['term']}' ({len(defs)})", ""]
    for d in defs:
        lines.append(f"- **{d['term']}** — {d.get('short_title') or d.get('title')} `{d['refid']}` {d['address']}: {d['definition']}")
    if not defs:
        lines.append("- none in the definitions table; try laws_find_definition for free-text phrasing")
    lines += _limits(res)
    return "\n".join(lines)


def sql(res: dict) -> str:
    cols = res["columns"]
    lines = [f"# {len(res['rows'])} row(s){' (truncated)' if res.get('truncated') else ''} in {res['seconds']} s", ""]
    if cols:
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "---|" * len(cols))
        for row in res["rows"]:
            lines.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ")[:200] if v is not None else "" for v in row) + " |")
    lines += _limits(res)
    return "\n".join(lines)


def index_status(res: dict) -> str:
    lines = ["# Index status"]
    if not res.get("path"):
        lines.append(f"- Not available: {res.get('note')}")
        return "\n".join(lines + _limits(res))
    m = res["meta"]
    lines.append(f"- File: `{res['path']}` ({res['source']})")
    lines.append(f"- Built from publication `{(m.get('source_sha') or '?')[:10]}`, manifest {m.get('kildemanifest', '?')}, "
                 f"parser loader `{(m.get('parser_loader') or '?')[:10]}` publisher `{(m.get('parser_publisher') or '?')[:10]}`")
    match = res.get("matches_publication")
    lines.append("- Matches the checkout's acknowledged publication: " + ("yes" if match else "no" if match is False else "unknown (no publication state or unstamped index)"))
    c = res["counts"]
    lines.append(f"- Rows: {c['documents']} documents, {c['nodes']} nodes, {c['node_text']} ledd texts, {c['amendments']} amendment records, {c['refs']} references, {c['definitions']} definitions; full-text table {'built' if c['fts'] else 'missing'}")
    if res.get("note"):
        lines.append(f"- {res['note']}")
    lines += _limits(res)
    return "\n".join(lines)
