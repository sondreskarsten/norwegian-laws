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

Other settings: `NORWEGIAN_LAWS_REMOTE` (clone URL), `NORWEGIAN_LAWS_CACHE` (cache directory), `NORWEGIAN_LAWS_NO_UPDATE=1` or `--no-update` (never fetch on start), `--prepare-only` (clone/update and exit, useful in CI or Docker builds).

## Tools

| Tool | Answers |
| --- | --- |
| `laws_search_documents` | Find documents by title, short title, abbreviation (`asl`, `aml`), department, or refid. |
| `laws_get_document` | Read a document, one `§` or chapter, its outline (headings with line numbers), or its front matter. Long texts are paged. |
| `laws_search_text` | Full-text search over all current texts, grouped by document with the enclosing `§`. Fixed phrase or regex. |
| `laws_find_definition` | Where a term is defined: ranks `Med X menes …`, definition sections, and `§` headings naming the term; matches inflections by stem. |
| `laws_recent_changes` | Commits and documents whose text changed in a window (`since="1 week ago"`), filtered by kind, documents, or a catalog query. Also lists changed parsed amendment record files. |
| `laws_document_history` | Commit history of one document with line counts. |
| `laws_diff_document` | Unified diff of a document between two commits or dates, optionally limited to one `§`. |
| `laws_blame_section` | For each block of lines in a `§`, the commit and date that last changed it. |
| `laws_amendment_records` | The amendment instructions parsed from Norsk Lovtidend for a document (`historie/`), filtered by `§` and date. |
| `laws_related_documents` | Regulations and acts that cite a document by short title or `20. juni 2025 nr. 105` citation. |
| `laws_repo_status` | HEAD, last Lovdata update commit, history depth, document counts. |
| `laws_update_repo` | Fetch the latest commits. |

Revisions and dates accepted by the history tools: commit shas, `HEAD~3`, ISO dates (`2026-10-01`), and Git phrases (`1 week ago`, `yesterday`, `3 months ago`). A date is resolved to the last commit before it.

## What the answers mean

- A commit date records when this project observed a change in Lovdata's consolidated text, not when a provision entered into force. Diffs can also reflect parser or formatting changes.
- Amendment records are parsed views of Norsk Lovtidend. They are not a verified reconstruction of legal effect.
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
