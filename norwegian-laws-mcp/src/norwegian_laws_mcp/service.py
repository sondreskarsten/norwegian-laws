"""Tool logic independent of the MCP transport."""
from __future__ import annotations

import json
import re
import threading

from . import history, search
from .catalog import Catalog, Entry
from .errors import LawsError, ResolveError
from .markdown import get_section, outline, parse_document
from .repo import CATALOG_FILE, DOC_DIRS, HISTORIE_DIR, Repo

MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "desember"]

DATA_NOTE = (
    "Note: repository commit dates record when this project observed a change in Lovdata's "
    "consolidated text, not when a law entered into force. Amendment records are parsed "
    "views of Norsk Lovtidend. Verify legal status at lovdata.no."
)


def citation_variants(refid: str) -> list[str]:
    """Citation strings used inside law texts, e.g. '20. juni 2025 nr. 105'."""
    m = re.match(r"^(lov|forskrift)/(\d{4})-(\d{2})-(\d{2})(?:-(\d+))?$", refid)
    if not m:
        return []
    year, month, day, nr = m.group(2), int(m.group(3)), int(m.group(4)), m.group(5)
    base = f"{day}. {MONTHS[month - 1]} {year}"
    out = [f"{base} nr. {nr}" if nr else base]
    out.append(refid)
    out.append(refid.replace("/", "-").upper())
    return out


class LawsService:
    def __init__(self, repo: Repo) -> None:
        self.repo = repo
        self.cache = search.DocCache(repo)
        self._catalog: Catalog | None = None
        self._catalog_sha: str | None = None
        self._lock = threading.Lock()

    # -- state -------------------------------------------------------------

    def catalog(self) -> Catalog:
        self.repo.ready()
        head = self.repo.head().sha
        with self._lock:
            if self._catalog is None or self._catalog_sha != head:
                self._catalog = Catalog.from_json_text(self.repo.read(CATALOG_FILE))
                self._catalog_sha = head
            return self._catalog

    def resolve(self, ref: str) -> Entry:
        return self.catalog().resolve(ref)

    def resolve_many(self, refs: list[str] | None) -> list[Entry]:
        if not refs:
            return []
        cat = self.catalog()
        out: list[Entry] = []
        for r in refs:
            out.append(cat.resolve(r))
        return out

    def entries_for_filter(self, documents: list[str] | None, query: str | None, kind: str | None) -> list[Entry]:
        entries = self.resolve_many(documents)
        if query:
            found = [e for _, e in self.catalog().search(query, kind=kind, limit=200)]
            if not found:
                raise ResolveError(f"No documents match query '{query}'.")
            entries += found
        if kind:
            entries = [e for e in entries if e.kind == kind]
        seen: set[str] = set()
        uniq = []
        for e in entries:
            if e.refid not in seen:
                seen.add(e.refid)
                uniq.append(e)
        return uniq

    # -- tools -------------------------------------------------------------

    def search_documents(self, query: str, kind: str | None, limit: int, include_amendment_acts: bool) -> list[dict]:
        results = self.catalog().search(query, kind=kind, limit=limit, include_amendment_acts=include_amendment_acts)
        return [dict(score=round(s, 1), **e.summary()) for s, e in results]

    def get_document(self, ref: str, section: str | None, mode: str, offset: int, max_chars: int) -> dict:
        entry = self.resolve(ref)
        doc = self.cache.get(entry.path)
        result: dict = {"document": entry.summary(), "mode": mode}
        if mode == "metadata":
            result["front_matter"] = doc.meta
            result["headings"] = len(doc.headings)
            result["lines"] = len(doc.lines)
            result["characters"] = len(doc.text)
            return result
        if mode == "outline":
            result["outline"] = [
                {"level": h.level, "line": h.line, "text": h.text, "section": h.section}
                for h in outline(doc)
            ]
            return result
        if section:
            sec = get_section(doc, section)
            if sec is None:
                available = [h.section for h in doc.headings if h.section]
                raise ResolveError(
                    f"{entry.refid} has no section '{section}'. Sections present: "
                    + (", ".join(f"§ {s}" for s in available[:60]) + (" ..." if len(available) > 60 else "") if available else "none recognised")
                    + ". Use mode='outline' to list headings."
                )
            text = sec.text
            result["section"] = {"heading": sec.heading.text, "start_line": sec.start, "end_line": sec.end}
        else:
            text = doc.text
        total = len(text)
        chunk = text[offset: offset + max_chars]
        result["text"] = chunk
        result["offset"] = offset
        result["total_characters"] = total
        result["truncated"] = offset + len(chunk) < total
        if result["truncated"]:
            result["next_offset"] = offset + len(chunk)
        return result

    def search_text(self, query: str, kind: str | None, documents: list[str] | None, regex: bool,
                    whole_word: bool, max_documents: int, max_hits_per_document: int) -> dict:
        entries = self.resolve_many(documents)
        results, total = search.search_text(
            self.repo, self.cache, self.catalog(), query, kind=kind, entries=entries or None,
            regex=regex, whole_word=whole_word, max_documents=max_documents,
            max_hits_per_document=max_hits_per_document,
        )
        return {
            "query": query,
            "total_hits": total,
            "documents_with_hits": len(results) if total == 0 else None,
            "results": [
                {
                    "refid": dh.entry.refid if dh.entry else None,
                    "title": dh.entry.display_name if dh.entry else dh.path,
                    "kind": dh.entry.kind if dh.entry else None,
                    "path": dh.path,
                    "hits_in_document": dh.total,
                    "hits": [
                        {"line": h.line, "section": h.section.text if h.section else None, "text": h.text}
                        for h in dh.hits
                    ],
                }
                for dh in results
            ],
        }

    def find_definition(self, term: str, kind: str | None, documents: list[str] | None, limit: int) -> dict:
        entries = self.resolve_many(documents)
        hits, mentions = search.find_definitions(
            self.repo, self.cache, self.catalog(), term, kind=kind, entries=entries or None, limit=limit,
        )
        return {
            "term": term,
            "stem": search.stem(term),
            "total_mentions": mentions,
            "definitions": [
                {
                    "score": h.score,
                    "why": h.reason,
                    "refid": h.entry.refid if h.entry else None,
                    "title": h.entry.display_name if h.entry else h.path,
                    "kind": h.entry.kind if h.entry else None,
                    "path": h.path,
                    "section": h.section.text if h.section else None,
                    "section_key": h.section.section if h.section else None,
                    "line": h.line,
                    "text": h.text,
                }
                for h in hits
            ],
        }

    def recent_changes(self, since: str | None, until: str | None, kind: str | None, documents: list[str] | None,
                       query: str | None, include_amendment_records: bool, limit: int) -> dict:
        self.repo.ready()
        cat = self.catalog()
        entries = self.entries_for_filter(documents, query, kind)
        if entries:
            paths = history.doc_paths_from_entries(entries, include_amendment_records)
        else:
            if kind == "lov":
                paths = ["lover"]
            elif kind == "forskrift":
                paths = ["forskrifter"]
            else:
                paths = list(DOC_DIRS)
            if include_amendment_records:
                paths.append(HISTORIE_DIR)
        changes = history.changes_between(self.repo, since=since, until=until, paths=paths)
        if kind and not entries:
            prefix = "lover/" if kind == "lov" else "forskrifter/"
            changes = [c for c in changes if c.path.startswith(prefix) or c.path.startswith(HISTORIE_DIR + "/")]
        text_changes = [c for c in changes if not c.path.startswith(HISTORIE_DIR + "/")]
        record_changes = [c for c in changes if c.path.startswith(HISTORIE_DIR + "/")]
        text_docs = history.group_by_document(text_changes, cat)
        record_docs = history.group_by_document(record_changes, cat)
        commits = {}
        for c in changes:
            commits.setdefault(c.sha, {"sha": c.sha, "date": c.date, "subject": c.subject, "files": 0})
            commits[c.sha]["files"] += 1

        def doc_item(dc: history.DocumentChange) -> dict:
            e = dc.entry
            if e is None and dc.path.startswith(HISTORIE_DIR + "/"):
                e = self._entry_for_historie(dc.path, cat)
            return {
                "path": dc.path,
                "refid": e.refid if e else None,
                "title": e.display_name if e else None,
                "kind": e.kind if e else None,
                "status": "".join(history.STATUS_WORDS.get(s, s) + " " for s in dc.statuses).strip(),
                "first_change": dc.first_date,
                "last_change": dc.last_date,
                "commits": [c.sha[:10] for c in dc.changes],
            }

        return {
            "since": since,
            "until": until,
            "head": self.repo.head().sha,
            "commits": sorted(commits.values(), key=lambda c: c["date"], reverse=True)[:limit],
            "total_text_documents_changed": len(text_docs),
            "text_documents": [doc_item(d) for d in text_docs[:limit]],
            "total_amendment_record_files_changed": len(record_docs),
            "amendment_record_files": [doc_item(d) for d in record_docs[:limit]],
            "note": DATA_NOTE,
        }

    def _entry_for_historie(self, path: str, cat: Catalog) -> Entry | None:
        base = path.rsplit("/", 1)[-1]
        e = cat.by_path.get(base)
        if e:
            return e
        html = path[:-3] + ".html" if path.endswith(".md") else path
        for entry in cat.entries:
            if entry.historie == html:
                return entry
        return None

    def document_history(self, ref: str, since: str | None, until: str | None, limit: int) -> dict:
        entry = self.resolve(ref)
        commits = history.document_log(self.repo, entry.path, since=since, until=until, limit=limit)
        return {"document": entry.summary(), "commits": commits, "note": DATA_NOTE}

    def diff_document(self, ref: str, from_rev: str, to_rev: str, section: str | None, context: int, max_chars: int) -> dict:
        entry = self.resolve(ref)
        res = history.diff_document(self.repo, entry.path, from_rev=from_rev, to_rev=to_rev, section=section, context=context)
        diff = res.diff
        truncated = len(diff) > max_chars
        return {
            "document": entry.summary(),
            "section": section,
            "from": {"rev": res.from_sha, "date": res.from_date, "existed": res.existed_before},
            "to": {"rev": res.to_sha, "date": res.to_date, "existed": res.existed_after},
            "changed": bool(diff.strip()),
            "diff": diff[:max_chars],
            "truncated": truncated,
            "note": DATA_NOTE,
        }

    def blame_section(self, ref: str, section: str | None) -> dict:
        entry = self.resolve(ref)
        doc = self.cache.get(entry.path)
        if section:
            sec = get_section(doc, section)
            if sec is None:
                raise ResolveError(f"{entry.refid} has no section '{section}'. Use laws_get_document with mode='outline'.")
            start, end = sec.start, sec.end
            heading = sec.heading.text
        else:
            start, end, heading = 1, len(doc.lines), None
        runs = history.blame_lines(self.repo, entry.path, start, end)
        return {
            "document": entry.summary(),
            "section": heading,
            "lines": [start, end],
            "runs": [
                {"lines": [r.start, r.end], "last_changed": r.date, "commit": r.sha[:10], "subject": r.subject, "first_line": r.first_line}
                for r in runs
            ],
            "note": DATA_NOTE,
        }

    def amendment_records(self, ref: str, section: str | None, since: str | None, limit: int) -> dict:
        entry = self.resolve(ref)
        path = history.historie_path_for(self.repo, entry)
        if path is None:
            return {"document": entry.summary(), "records": [], "total": 0,
                    "message": "No parsed amendment records exist for this document in historie/."}
        meta, records = history.parse_historie(self.repo.read(path))
        key = None
        if section:
            from .markdown import normalize_section_key
            key = normalize_section_key(section)
            records = [r for r in records if normalize_section_key(r.paragraph) == key]
        if since:
            records = [r for r in records if r.date >= since]
        records.sort(key=lambda r: r.date, reverse=True)
        return {
            "document": entry.summary(),
            "source_file": path,
            "section_filter": key,
            "total": len(records),
            "records": [
                {"paragraph": r.paragraph, "date": r.date, "amending_act": r.act, "instruction": r.instruction, "text": r.text}
                for r in records[:limit]
            ],
            "note": "Dates are display dates from the parsed amendment act; they are not verified commencement dates.",
        }

    def related_documents(self, ref: str, kind: str | None, limit: int) -> dict:
        entry = self.resolve(ref)
        cat = self.catalog()
        terms = list(dict.fromkeys([n for n in entry.names if len(n) >= 5] + citation_variants(entry.refid)))
        paths = ["lover"] if kind == "lov" else ["forskrifter"] if kind == "forskrift" else list(DOC_DIRS)
        counts: dict[str, int] = {}
        matched_terms: dict[str, set[str]] = {}
        for term in terms:
            pat = search._git_prefilter_pattern(term)
            found = search.git_grep_lines(self.repo, pat, paths)
            py = re.compile(search.NB + re.escape(term) + search.NA, re.I)
            for path, lines in found.items():
                if path == entry.path:
                    continue
                n = sum(1 for _, t in lines if py.search(t))
                if n:
                    counts[path] = counts.get(path, 0) + n
                    matched_terms.setdefault(path, set()).add(term)
        title_hits = []
        for n in entry.names:
            if len(n) >= 5:
                title_hits += [e for _, e in cat.search(n, kind=kind, limit=50) if e.refid != entry.refid]
        for e in title_hits:
            counts.setdefault(e.path, 0)
            matched_terms.setdefault(e.path, set()).add("title")
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return {
            "document": entry.summary(),
            "search_terms": terms,
            "total_related": len(ranked),
            "related": [
                {
                    "refid": cat.by_path[p].refid if p in cat.by_path else None,
                    "title": cat.by_path[p].display_name if p in cat.by_path else p,
                    "kind": cat.by_path[p].kind if p in cat.by_path else None,
                    "path": p,
                    "mentions": n,
                    "matched": sorted(matched_terms.get(p, [])),
                }
                for p, n in ranked[:limit]
            ],
        }

    def repo_status(self) -> dict:
        self.repo.ready()
        head = self.repo.head()
        last_update_commit = self.repo.git("log", "-1", "--date=iso-strict", "--format=%H%x1f%ad%x1f%s",
                                           "--grep=Oppdater lover og forskrifter", "HEAD").strip()
        parts = last_update_commit.split("\x1f") if last_update_commit else []
        cat = self.catalog()
        return {
            "path": str(self.repo.path),
            "remote": self.repo.remote,
            "managed_clone": self.repo.managed,
            "head": {"sha": head.sha, "date": head.date, "subject": head.subject},
            "last_lovdata_update_commit": {"sha": parts[0], "date": parts[1], "subject": parts[2]} if len(parts) == 3 else None,
            "commits_in_history": self.repo.commit_count(),
            "shallow": self.repo.is_shallow(),
            "documents": {"total": len(cat), "lover": sum(e.kind == "lov" for e in cat.entries),
                          "forskrifter": sum(e.kind == "forskrift" for e in cat.entries)},
            "last_update_check": self.repo.last_update,
        }

    def update_repo(self) -> dict:
        self.repo.ready()
        result = self.repo.update()
        self.cache.docs.clear()
        return {**result, "head": self.repo.head().__dict__}


def to_json(data: dict | list) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1)
