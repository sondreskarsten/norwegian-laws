"""MCP server definition."""
from __future__ import annotations

import functools
from typing import Annotated, Callable, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__, render
from .errors import LawsError
from .repo import Repo
from .service import LawsService, to_json

Kind = Literal["lov", "forskrift"] | None
Format = Literal["markdown", "json"]

INSTRUCTIONS = """\
Tools over the norwegian-laws Git repository (https://github.com/sondreskarsten/norwegian-laws):
Lovdata's consolidated Norwegian laws (lover/) and central regulations (forskrifter/) as Markdown,
parsed amendment records (historie/), and a catalog (laws.json). Every document is identified by a
refid such as lov/1997-06-13-44 or forskrift/2025-08-06-1610; aliases like 'asl' or short titles
like 'enhetsregisterloven' also resolve.

Typical workflows:
- "Where is X defined?" -> laws_find_definition, then laws_get_document with section=... to read it.
- "What changed last week?" -> laws_recent_changes(since="1 week ago"), then laws_diff_document.
- "How have the Enhetsregisteret rules changed?" -> laws_search_documents("enhetsregister") or
  laws_related_documents, then laws_recent_changes(query=...) / laws_document_history / laws_diff_document,
  and laws_amendment_records for the parsed Lovtidend instructions.

Data coverage, which every history tool also states in its output:
- Git history starts with the first import (February 2026). A date before that is clamped to the first
  commit and flagged. 'No change in window' means no commit touched the file, not that the law was stable.
- Commits are tagged 'source-update' (daily Lovdata import) or 'pipeline' (parser/format work); diffs and
  blame can reflect the latter.
- laws_amendment_records covers Norsk Lovtidend from 2001 and returns only new wording, never the replaced
  text; it also returns Lovdata's own 'Endret ved lover ...' note per provision, which reaches back to adoption.
- laws_get_document version='vYYYY' and laws_diff_document between 'vYYYY' tags read the law-history
  branch: a reconstruction built from the current text by applying parsed amendments, labelled unverified.
- Repealed or replaced acts leave Lovdata's current corpus. Their refid still resolves; the last observed
  text is returned with the removal date, which is not a repeal date.
- Corpus scope: gjeldende lover and sentrale forskrifter only. Stortingsvedtak (e.g. avgiftsvedtak),
  local regulations, circulars and court decisions are not here; say so instead of guessing.
- Era and regime matter: when an act was replaced (e.g. foretaksregisterloven 1985 -> 2025,
  enhetsregisterloven 1994 -> 2025), section numbers differ between the acts; read the old act's last
  text for pre-replacement questions.
Git commit dates say when this project observed a change, not when a provision entered into force.
Amendment records are parsed views of Norsk Lovtidend, not a verified reconstruction of legal effect.
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, idempotent_hint=True, open_world_hint=False)
UPDATE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=True)


def _guard(fn: Callable[..., str]) -> Callable[..., str]:
    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> str:
        try:
            return fn(*args, **kwargs)
        except LawsError as exc:
            return f"Error: {exc}"
    return wrapper


def _out(fmt: str, data: dict | list, renderer: Callable[..., str], *render_args) -> str:
    if fmt == "json":
        return to_json(data)
    return renderer(*render_args, data) if render_args else renderer(data)


def build_server(service: LawsService) -> MCPServer:
    mcp = MCPServer(
        "norwegian_laws_mcp",
        title="Norwegian laws",
        description="Norwegian laws and regulations from the norwegian-laws Git repository",
        instructions=INSTRUCTIONS,
        version=__version__,
        website_url="https://sondreskarsten.github.io/norwegian-laws/",
    )

    @mcp.tool(name="laws_search_documents", title="Find laws and regulations", annotations=READ_ONLY)
    @_guard
    def laws_search_documents(
        query: Annotated[str, Field(description="Title words, short title, abbreviation (e.g. 'asl', 'aml'), "
                                                "department, or refid (e.g. 'lov/1997-06-13-44').", min_length=1)],
        kind: Annotated[Kind, Field(description="Restrict to 'lov' (acts) or 'forskrift' (regulations).")] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 10,
        include_amendment_acts: Annotated[bool, Field(description="Include amendment acts/regulations "
                                                                  "('Endringslov ...', 'Forskrift om endring ...').")] = True,
        include_removed: Annotated[bool, Field(description="Also search documents that have left the current corpus "
                                                           "(repealed or replaced acts); slower on first use.")] = False,
        format: Format = "markdown",
    ) -> str:
        """Search the catalog of all current Norwegian acts (lover) and central regulations (forskrifter).

        Returns refid, kind, titles, aliases, department, commencement, last amending act and the
        repository path for each match. Use the refid in the other tools. A refid of a repealed act
        (e.g. 'lov/1985-06-21-78') resolves in the other tools even without this search.
        """
        items = service.search_documents(query, kind, limit, include_amendment_acts, include_removed)
        return _out(format, items, render.search_documents, query)

    @mcp.tool(name="laws_get_document", title="Read a law or a section of it", annotations=READ_ONLY)
    @_guard
    def laws_get_document(
        ref: Annotated[str, Field(description="refid, alias, short title, or path, e.g. 'lov/2025-06-20-105', "
                                              "'enhetsregisterloven', 'asl'.")],
        section: Annotated[str | None, Field(description="A single provision or chapter: '§ 4-7', '4-7', "
                                                         "'§ 12', 'kapittel 4'. Omit for the whole text.")] = None,
        mode: Annotated[Literal["text", "outline", "metadata"],
                        Field(description="'text' returns the Markdown; 'outline' lists all headings with line "
                                          "numbers and section keys; 'metadata' returns the YAML front matter.")] = "text",
        offset: Annotated[int, Field(ge=0, description="Character offset for paging long texts.")] = 0,
        max_chars: Annotated[int, Field(ge=500, le=200000)] = 20000,
        at: Annotated[str | None, Field(description="Read the text as committed on main at a date or revision "
                                                    "('2026-03-01', 'HEAD~20', a sha). Observed text, not legal state.")] = None,
        version: Annotated[str | None, Field(description="Read a yearly reconstruction from the law-history branch: "
                                                         "'v2010' ... 'v2026', or a build tag 'history-YYYY-MM-DD'. "
                                                         "Unverified reconstruction, labelled as such.")] = None,
    ) -> str:
        """Read a document's consolidated text, one § or chapter, its outline, or its metadata.

        Current text by default. Repealed or replaced acts that have left the corpus (e.g. the 1985
        foretaksregisterlov 'lov/1985-06-21-78') return their last observed text with the removal date.
        'at' reads the text as this repository held it on a date; 'version' reads the law-history
        yearly reconstruction. Long documents are paged; use mode='outline' first for long texts.
        """
        res = service.get_document(ref, section, mode, offset, max_chars, at, version)
        return render.document(res)

    @mcp.tool(name="laws_search_text", title="Full-text search across all documents", annotations=READ_ONLY)
    @_guard
    def laws_search_text(
        query: Annotated[str, Field(description="Phrase to find (case-insensitive). With regex=true, a Python "
                                                "regular expression.", min_length=2)],
        kind: Kind = None,
        documents: Annotated[list[str] | None, Field(description="Restrict to these documents (refids/aliases).")] = None,
        regex: Annotated[bool, Field(description="Treat query as a regular expression (slower, scans every file).")] = False,
        whole_word: Annotated[bool, Field(description="Match whole words only.")] = False,
        max_documents: Annotated[int, Field(ge=1, le=200)] = 20,
        max_hits_per_document: Annotated[int, Field(ge=1, le=50)] = 5,
        format: Format = "markdown",
    ) -> str:
        """Grep the current text of all laws and regulations (like `git grep`).

        Results are grouped per document, ordered by hit count, with line numbers and the enclosing §.
        Use laws_get_document with section=... to read a hit in context.
        """
        res = service.search_text(query, kind, documents, regex, whole_word, max_documents, max_hits_per_document)
        return _out(format, res, render.search_text)

    @mcp.tool(name="laws_find_definition", title="Find where a term is defined", annotations=READ_ONLY)
    @_guard
    def laws_find_definition(
        term: Annotated[str, Field(description="A legal term in Norwegian, singular or plural, e.g. 'underenhet', "
                                               "'underenheter', 'nærstående', 'arbeidstaker'.", min_length=2)],
        kind: Kind = None,
        documents: Annotated[list[str] | None, Field(description="Restrict to these documents (refids/aliases).")] = None,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
        format: Format = "markdown",
    ) -> str:
        """Locate provisions that define or primarily regulate a term.

        Ranks definition phrases ('Med X menes ...', 'X betyr ...'), lines in sections titled
        'Definisjoner', and § headings naming the term. Inflections are matched by stem
        (underenhet/underenheter/underenhetene). Falls back to telling you how many plain
        mentions exist when no definition-like passage is found.
        """
        res = service.find_definition(term, kind, documents, limit)
        return _out(format, res, render.definitions)

    @mcp.tool(name="laws_recent_changes", title="What changed in a time window", annotations=READ_ONLY)
    @_guard
    def laws_recent_changes(
        since: Annotated[str | None, Field(description="Start of window: ISO date '2026-10-01' or git phrase "
                                                       "'1 week ago', 'yesterday', '3 months ago'.")] = "1 week ago",
        until: Annotated[str | None, Field(description="End of window (same formats). Default: now.")] = None,
        kind: Kind = None,
        documents: Annotated[list[str] | None, Field(description="Only these documents (refids/aliases).")] = None,
        query: Annotated[str | None, Field(description="Only documents whose title/alias matches this catalog "
                                                       "query, e.g. 'enhetsregister', 'skatt'.")] = None,
        include_amendment_records: Annotated[bool, Field(description="Also report changed parsed amendment "
                                                                     "record files under historie/.")] = True,
        limit: Annotated[int, Field(ge=1, le=500, description="Max documents and commits listed.")] = 50,
        format: Format = "markdown",
    ) -> str:
        """List commits and documents whose text changed in the repository in a time window (git log).

        Answers 'what changed last week' or 'how have the Enhetsregisteret rules changed since June'.
        Follow up with laws_diff_document for the actual textual difference.
        """
        res = service.recent_changes(since, until, kind, documents, query, include_amendment_records, limit)
        return _out(format, res, render.recent_changes)

    @mcp.tool(name="laws_document_history", title="Commit history of one document", annotations=READ_ONLY)
    @_guard
    def laws_document_history(
        ref: Annotated[str, Field(description="refid, alias, short title, or path.")],
        since: Annotated[str | None, Field(description="ISO date or git phrase like '1 year ago'.")] = None,
        until: str | None = None,
        limit: Annotated[int, Field(ge=1, le=500)] = 30,
    ) -> str:
        """List the commits that changed a document, newest first, with added/deleted line counts (git log --numstat)."""
        res = service.document_history(ref, since, until, limit)
        return render.document_history(res)

    @mcp.tool(name="laws_diff_document", title="Diff a document between two points in time", annotations=READ_ONLY)
    @_guard
    def laws_diff_document(
        ref: Annotated[str, Field(description="refid, alias, short title, or path.")],
        from_rev: Annotated[str, Field(description="Older point: commit sha, 'HEAD~5', ISO date '2026-06-01', "
                                                   "phrase '1 month ago' (resolved to the last commit before it), or a "
                                                   "law-history version 'v2010' / build tag 'history-YYYY-MM-DD'.")],
        to_rev: Annotated[str, Field(description="Newer point (same formats). Default HEAD.")] = "HEAD",
        section: Annotated[str | None, Field(description="Limit the diff to one § or chapter, e.g. '§ 4-7'.")] = None,
        context: Annotated[int, Field(ge=0, le=20)] = 3,
        max_chars: Annotated[int, Field(ge=1000, le=200000)] = 20000,
    ) -> str:
        """Unified diff of a document's consolidated text between two revisions or dates (git diff).

        With section=..., only that provision is compared, which keeps the output small.
        """
        res = service.diff_document(ref, from_rev, to_rev, section, context, max_chars)
        return render.diff(res)

    @mcp.tool(name="laws_blame_section", title="When each line was last changed", annotations=READ_ONLY)
    @_guard
    def laws_blame_section(
        ref: Annotated[str, Field(description="refid, alias, short title, or path.")],
        section: Annotated[str | None, Field(description="A § or chapter, e.g. '§ 4-7'. Omit for the whole "
                                                         "document (can be long).")] = None,
    ) -> str:
        """Show for each block of lines the commit and date that last changed it (git blame).

        Useful for 'when did this wording last change in the repository?'.
        """
        res = service.blame_section(ref, section)
        return render.blame(res)

    @mcp.tool(name="laws_amendment_records", title="Parsed amendment records for a document", annotations=READ_ONLY)
    @_guard
    def laws_amendment_records(
        ref: Annotated[str, Field(description="refid, alias, short title, or path of the amended document.")],
        section: Annotated[str | None, Field(description="Only records targeting this §, e.g. '§ 4-7'.")] = None,
        since: Annotated[str | None, Field(description="Only records dated on/after this ISO date.")] = None,
        limit: Annotated[int, Field(ge=1, le=500)] = 50,
    ) -> str:
        """Amendment history of a document or one provision, from two sources.

        1. Lovdata's own per-provision notes in the current text ('Endret ved lover 17 des 1999 nr. 93
           (ikr. 1 jan 2000), ...'), which list every amending act since adoption with commencement.
        2. Records parsed from Norsk Lovtidend (historie/ files, 2001 onward): amending act, targeted §,
           instruction ('§ 4-7 første ledd skal lyde:') and the new wording when present.
        Use this for 'how has § X changed over the years'; Git tools only cover 2026 onward.
        """
        res = service.amendment_records(ref, section, since, limit)
        return render.amendment_records(res)

    @mcp.tool(name="laws_related_documents", title="Documents that reference a document", annotations=READ_ONLY)
    @_guard
    def laws_related_documents(
        ref: Annotated[str, Field(description="refid, alias, short title, or path.")],
        kind: Kind = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 20,
    ) -> str:
        """Find regulations and acts that cite a document by short title ('enhetsregisterloven') or
        citation ('20. juni 2025 nr. 105'), plus catalog entries whose titles name it.

        Use this to collect the forskrifter that belong to an act before asking for changes.
        """
        res = service.related_documents(ref, kind, limit)
        return render.related(res)

    @mcp.tool(name="laws_repo_status", title="Repository status", annotations=READ_ONLY)
    @_guard
    def laws_repo_status() -> str:
        """Report the checkout path, HEAD commit, last Lovdata update commit, history depth and document counts."""
        return render.status(service.repo_status())

    @mcp.tool(name="laws_update_repo", title="Fetch the latest data", annotations=UPDATE)
    @_guard
    def laws_update_repo() -> str:
        """Fetch the latest commits from GitHub and move the checkout to them. Requires network access."""
        res = service.update_repo()
        h = res["head"]
        state = "new commits fetched" if res["changed"] else "already up to date"
        return f"Repository {state}. HEAD is now `{h['sha'][:10]}` ({h['date']}): {h['subject']}"

    return mcp


def create_server(repo: Repo) -> MCPServer:
    return build_server(LawsService(repo))
