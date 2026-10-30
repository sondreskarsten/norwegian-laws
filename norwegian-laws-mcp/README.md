# norwegian-laws-mcp

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant answer questions about Norwegian laws and central regulations straight from the [norwegian-laws](https://github.com/sondreskarsten/norwegian-laws) Git repository. The repository is treated like a codebase: documents are files, Lovdata updates are commits, and questions are answered with the catalog, `git grep`, `git log`, `git diff`, and `git blame`.

Example questions it is built for:

- *Where is "underenheter" defined?*
- *What changed last week?*
- *How have the Enhetsregisteret law and its regulations changed since June?*
- *Show me § 4-7 of enhetsregisterloven and when its wording last changed.*

## Install

Requires Python 3.11+ and `git` on `PATH`. The server clones the data on first start (a blobless, single-branch clone of `main`: about 50 MB of Git metadata plus the working tree, 15–60 seconds), stores it under `~/.cache/norwegian-laws-mcp/`, and fetches new commits on every start.

### Claude Code

```bash
claude mcp add norwegian-laws -- uvx --from "git+https://github.com/sondreskarsten/norwegian-laws.git#subdirectory=norwegian-laws-mcp" norwegian-laws-mcp
```

### Claude Desktop, Cursor, and other JSON-configured clients

```json
{
  "mcpServers": {
    "norwegian-laws": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sondreskarsten/norwegian-laws.git#subdirectory=norwegian-laws-mcp",
        "norwegian-laws-mcp"
      ]
    }
  }
}
```

### pip

```bash
pip install "norwegian-laws-mcp @ git+https://github.com/sondreskarsten/norwegian-laws.git#subdirectory=norwegian-laws-mcp"
norwegian-laws-mcp            # stdio transport
norwegian-laws-mcp --transport streamable-http --port 8000   # HTTP at http://127.0.0.1:8000/mcp
```

### Use an existing clone

If you already have the repository checked out, point the server at it. A user-provided checkout is never reset; it is fast-forwarded only when you pass `--update` or call the `laws_update_repo` tool.

```bash
NORWEGIAN_LAWS_REPO=/path/to/norwegian-laws norwegian-laws-mcp
# or
norwegian-laws-mcp --repo /path/to/norwegian-laws
```

Reading a yearly version (`version="v2010"`) fetches the `v20*` and `history-*` tags from the remote into the checkout, including a user-provided one; nothing else is written there.

Other settings: `NORWEGIAN_LAWS_REMOTE` (clone URL), `NORWEGIAN_LAWS_CACHE` (cache directory), `NORWEGIAN_LAWS_NO_UPDATE=1` or `--no-update` (never fetch on start), `--prepare-only` (clone/update and exit, useful in CI or Docker builds).

## Tools

| Tool | Answers |
| --- | --- |
| `laws_search_documents` | Find documents by title, short title, abbreviation (`asl`, `aml`), department, or refid. `include_removed=true` also searches acts that have left the current corpus (repealed or replaced). |
| `laws_get_document` | Read a document, one `§` or chapter, its outline (headings with line numbers), or its front matter. Long texts are paged. `at="2026-03-01"` reads the text as committed on that date; `version="v2010"` reads the law-history yearly reconstruction; a repealed act's refid (e.g. `lov/1985-06-21-78`) returns its last observed text with the removal date. |
| `laws_search_text` | Full-text search over all current texts, grouped by document with the enclosing `§`. Fixed phrase or regex. |
| `laws_find_definition` | Where a term is defined: ranks `Med X menes …`, definition sections, and `§` headings naming the term; matches inflections by stem. |
| `laws_recent_changes` | Commits and documents whose text changed in a window (`since="1 week ago"`), filtered by kind, documents, or a catalog query. Also lists changed parsed amendment record files. |
| `laws_document_history` | Commit history of one document with line counts. |
| `laws_diff_document` | Unified diff of a document between two commits, dates, or law-history versions (`v2010`…`v2026`, `history-YYYY-MM-DD`), optionally limited to one `§`. |
| `laws_blame_section` | For each block of lines in a `§`, the commit and date that last changed it. |
| `laws_amendment_records` | Amendment history of a document or one `§`: Lovdata's own `Endret ved lover …` note per provision (back to adoption) plus the instructions parsed from Norsk Lovtidend (`historie/`, 2001 onward), filtered by `§` and date. |
| `laws_related_documents` | Regulations and acts that cite a document by short title or `20. juni 2025 nr. 105` citation. |
| `laws_repo_status` | HEAD, last Lovdata update commit, history depth, document counts. |
| `laws_update_repo` | Fetch the latest commits. |

Revisions and dates accepted by the history tools: commit shas, `HEAD~3`, ISO dates (`2026-10-01`), and Git phrases (`1 week ago`, `yesterday`, `3 months ago`). A date is resolved to the last commit before it.

## What the answers mean

Every history tool ends with a **Data coverage and limits** block that states what the data can and cannot show for that call:

- Git history starts with the repository's first import (February 2026). A requested date before that is clamped to the first commit and labelled as such. "No change in window" means no commit touched the file in the window, not that the law in force was unchanged.
- A commit date records when this project observed a change in Lovdata's consolidated text, not when a provision entered into force. Commits are tagged `source-update` (daily Lovdata import) or `pipeline` (parser or formatting work); diffs and blame can reflect the latter.
- Amendment records are parsed views of Norsk Lovtidend from 2001. They hold the new wording only, never the text that was replaced, and the tool reports the date span the file actually covers. The `Endret ved lover …` notes come from Lovdata's consolidated text and list every amending act since adoption, without wording.
- `version="vYYYY"` reads the law-history branch, a reconstruction built from the current text by applying parsed amendments with inferred dates. It is labelled unverified in every answer. Observed text on `main` starts at the first import (February 2026).
- Repealed or replaced acts leave Lovdata's current corpus. Their refid still resolves to the last observed text, with the removal date, which is not a repeal date. Section numbers differ between an act and its successor (foretaksregisterloven 1985 vs 2025), so pre-replacement questions should read the old act.
- Corpus scope is Lovdata's acts in force and central regulations. Stortingsvedtak (for example the yearly avgiftsvedtak), local regulations, circulars and court decisions are not included; the server says so rather than guessing.
- Only the `main` branch is cloned. The legacy `law-history` branch is not used.
- Blobs are fetched on demand, so `laws_diff_document`, `laws_document_history`, and `laws_blame_section` need network access the first time they touch an old revision of a file. `laws_search_text`, `laws_find_definition`, `laws_recent_changes`, and reading current documents work offline.

Check the source text and legal status at [lovdata.no](https://lovdata.no). This is an unofficial project, unaffiliated with Lovdata or the Norwegian government. Law data: Lovdata, [NLOD 2.0](https://data.norge.no/nlod/no/2.0). Code: MIT.

## Development

```bash
pip install -e "norwegian-laws-mcp/[test]"
cd norwegian-laws-mcp && pytest
norwegian-laws-mcp --repo .. --no-update          # serve the checkout you are working in
npx @modelcontextprotocol/inspector norwegian-laws-mcp --repo .. --no-update
```
