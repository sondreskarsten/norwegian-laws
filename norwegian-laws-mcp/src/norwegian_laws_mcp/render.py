"""Markdown rendering of service results."""
from __future__ import annotations


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
    head = [f"# {d.get('title') or d['refid']}", f"{_doc_line(d)}", f"Lovdata: {d['lovdata']}", ""]
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
        lines.append("")
        lines.append(res["note"])
        return "\n".join(lines)
    lines.append(f"## Commits ({len(res['commits'])})")
    for c in res["commits"]:
        lines.append(f"- {c['date'][:10]} `{c['sha'][:10]}` {c['subject']} ({c['files']} files)")
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
    lines.append("")
    lines.append(res["note"])
    return "\n".join(lines)


def document_history(res: dict) -> str:
    d = res["document"]
    lines = [f"# History of {d.get('short_title') or d['refid']} `{d['refid']}` (`{d['path']}`)", ""]
    if not res["commits"]:
        lines.append("No commits touched this document in the selected window.")
    for c in res["commits"]:
        lines.append(f"- {c['date'][:10]} `{c['sha'][:10]}` +{c['added']}/-{c['deleted']} {c['subject']}")
    lines += ["", res["note"]]
    return "\n".join(lines)


def diff(res: dict) -> str:
    d = res["document"]
    sec = f" section {res['section']}" if res["section"] else ""
    lines = [f"# Diff of {d.get('short_title') or d['refid']} `{d['refid']}`{sec}",
             f"from `{res['from']['rev'][:10]}` ({res['from']['date'][:10]}) to `{res['to']['rev'][:10]}` ({res['to']['date'][:10]})", ""]
    if not res["from"]["existed"] and res["to"]["existed"]:
        lines.append("The document did not exist at the start revision; the diff shows it as added.")
    if res["from"]["existed"] and not res["to"]["existed"]:
        lines.append("The document no longer exists at the end revision.")
    if not res["changed"]:
        lines.append("No textual change between these revisions.")
    else:
        lines += ["```diff", res["diff"].rstrip("\n"), "```"]
        if res["truncated"]:
            lines.append("[diff truncated; narrow with section=... or raise max_chars]")
    lines += ["", res["note"]]
    return "\n".join(lines)


def blame(res: dict) -> str:
    d = res["document"]
    sec = f" — {res['section']}" if res["section"] else ""
    lines = [f"# Last change per line block: {d.get('short_title') or d['refid']} `{d['refid']}`{sec}",
             f"Lines {res['lines'][0]}–{res['lines'][1]}", ""]
    for r in res["runs"]:
        span = f"L{r['lines'][0]}" if r["lines"][0] == r["lines"][1] else f"L{r['lines'][0]}–{r['lines'][1]}"
        lines.append(f"- {span}: last changed {r['last_changed']} `{r['commit']}` ({r['subject']}) — {r['first_line']}")
    lines += ["", res["note"]]
    return "\n".join(lines)


def amendment_records(res: dict) -> str:
    d = res["document"]
    lines = [f"# Parsed amendment records: {d.get('short_title') or d['refid']} `{d['refid']}`", ""]
    if res.get("message"):
        lines.append(res["message"])
        return "\n".join(lines)
    flt = f" for § {res['section_filter']}" if res.get("section_filter") else ""
    lines.append(f"{res['total']} records{flt} (source `{res['source_file']}`), newest first:")
    lines.append("")
    for r in res["records"]:
        lines.append(f"## {r['date']} — {r['paragraph']} — by `{r['amending_act']}`")
        if r["instruction"]:
            lines.append(f"*{r['instruction']}*")
        if r["text"]:
            lines.append("")
            lines += [f"> {t}" for t in r["text"].split("\n")]
        lines.append("")
    if res["total"] > len(res["records"]):
        lines.append(f"[... {res['total'] - len(res['records'])} more; raise limit or filter by section/since]")
    lines.append(res["note"])
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
    return "\n".join(lines)
