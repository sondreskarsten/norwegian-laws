> **Status (2026-07-21): completed — historical document.** The split
> shipped; Phase 3 closed on 2026-07-21 when `src/lovdata_pipeline/`, the
> root `pyproject.toml`, and the orphaned root test suite were removed and
> release builds were repointed at the two live packages. Reality has since
> outgrown this plan: the loader gained `audit.py`, `coverage.py`, and
> `reconstruct.py`; the publisher grew from 6 to 17 modules (feeds, historie,
> per-law pages, paragraph history, manifests, sitemap, stats, readme
> updater) and depends on `markdown` in addition to `pyyaml`; workflows
> install both packages editable from this repo rather than from PyPI; and
> law-history is dispatch-chained from deploy with `--history-mode act
> --use-lfs` instead of a weekly cron. Consult the workflows and package
> sources for current truth; keep this file for the architectural rationale.

# Migration Plan: Split into Two Libraries

## Motivation

The current `lovdata-pipeline` package is a monolith that downloads, parses, formats,
and publishes Norwegian laws in a single pass. This creates several problems:

1. **No checkpointing** — if the API returns inconsistent data mid-run, or the process
   crashes during git operations, you lose all work and must re-download everything.
2. **Coupled concerns** — XML parsing logic is entangled with Markdown formatting and
   git commit generation, making each harder to test and evolve independently.
3. **No stable intermediate format** — parsed data lives only as in-memory dataclasses
   that are immediately consumed. There's no way to inspect, validate, or replay from
   a known-good snapshot.

The fix: split into two libraries with a well-defined data contract between them.

---

## Architecture

```
                 ┌─────────────────────────────────┐
                 │        Lovdata Public API        │
                 │ api.lovdata.no/v1/publicData/get │
                 └────────────────┬────────────────┘
                                  │
                    .tar.bz2 archives (XML)
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    lovdata-loader                            │
│                                                             │
│  download.py   ─── fetch archives from API                  │
│  parser.py     ─── parse XML → structured Python objects    │
│  models.py     ─── LawData, AmendmentActData dataclasses    │
│  store.py      ─── serialize to snapshot directory           │
│  cli.py        ─── `lovdata-load` CLI                       │
│                                                             │
│  Output: snapshot directory (JSON + SQLite)                  │
└────────────────────────────┬────────────────────────────────┘
                             │
              snapshot/  (the contract)
              ├── laws/
              │   ├── lov-1814-05-17.json
              │   ├── lov-1998-07-17-56.json
              │   └── ... (774 files)
              ├── amendments.db
              └── manifest.json
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   lovdata-publisher                          │
│                                                             │
│  formatter.py    ─── snapshot JSON → Markdown with YAML fm  │
│  git_export.py   ─── FastImportStream, backdated commits    │
│  quarto.py       ─── Quarto book chapters, search, diff     │
│  releases.py     ─── monthly tags and release notes         │
│  search_index.py ─── merge into Quarto search.json          │
│  cli.py          ─── `lovdata-publish` CLI                  │
│                                                             │
│  Output: lover/*.md, book/*.qmd, git history                │
└─────────────────────────────────────────────────────────────┘
```

---

## The Contract: Snapshot Directory

The snapshot is the single point of coupling between the two libraries. It is a
directory with a fixed structure that `lovdata-loader` writes and `lovdata-publisher`
reads. This means:

- You can run `lovdata-load` once, inspect the snapshot, fix issues, and re-run
  `lovdata-publish` without re-downloading anything.
- You can version-control snapshots or archive them as release artifacts.
- If the API returns bad data, you diff the new snapshot against a known-good one
  before publishing.

### Snapshot structure

```
snapshot/
├── manifest.json          # metadata about this snapshot
├── laws/                  # one JSON file per consolidated law
│   ├── lov-1814-05-17.json
│   ├── lov-1998-07-17-56.json
│   └── ...
└── amendments.db          # SQLite database of amendment acts
```

### manifest.json

```json
{
  "version": 1,
  "created_at": "2026-02-19T12:00:00Z",
  "loader_version": "0.1.0",
  "source": {
    "gjeldende_archive": "gjeldende-lover.tar.bz2",
    "lovtidend_archives": [
      "lovtidend-avd1-2001-2025.tar.bz2",
      "lovtidend-avd1-2026.tar.bz2"
    ]
  },
  "counts": {
    "laws": 774,
    "amendment_acts": 35127,
    "amendments": 98432
  }
}
```

### Law JSON format (per file)

Each `laws/<refid>.json` contains the fully parsed law as structured data — not yet
formatted as Markdown. This is the key insight: the intermediate format is *structured*,
not *presentation*.

```json
{
  "refid": "lov/1998-07-17-56",
  "title": "Lov om årsregnskap m.v. (regnskapsloven)",
  "short_title": "Regnskapsloven – rskl",
  "ministry": "Finansdepartementet",
  "date_in_force": "1999-01-01",
  "last_amended": "lov/2025-06-20-106",
  "last_amended_in_force": "2026-01-01",
  "legal_area": "Næringsliv",
  "sections": [
    {
      "heading": "Kapittel 1. Virkeområde",
      "articles": [
        {
          "name": "§ 1-1",
          "header_text": "§ 1-1. Lovens virkeområde",
          "paragraphs": [
            {
              "text": "Loven gjelder for regnskapspliktige etter § 1-2.",
              "list_items": []
            },
            {
              "text": "Kongen kan i forskrift bestemme at...",
              "list_items": [
                {"identifier": "a)", "text": "utenlandske foretak..."},
                {"identifier": "b)", "text": "andre foretak..."}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### amendments.db schema (unchanged from current)

```sql
CREATE TABLE amendment_acts (
    refid TEXT PRIMARY KEY,
    filename TEXT,
    title TEXT,
    short_title TEXT,
    date_in_force TEXT,
    date_in_force_resolved TEXT,
    is_deferred INTEGER,
    date_published TEXT,
    ministry TEXT,
    changes_to TEXT,         -- comma-separated refids
    misc_info TEXT,
    journal_number TEXT,
    amendment_count INTEGER
);

CREATE TABLE amendments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    act_refid TEXT REFERENCES amendment_acts(refid),
    change_type TEXT,        -- change | repeal | add | move
    target TEXT,
    instruction TEXT,
    new_text TEXT
);
```

---

## Library 1: `lovdata-loader`

### Purpose

Download archives from the Lovdata API and parse them into a normalized snapshot.
Pure data extraction — no formatting, no git, no presentation concerns.

### Package structure

```
lovdata-loader/
├── src/lovdata_loader/
│   ├── __init__.py          # __version__
│   ├── models.py            # Dataclasses for parsed data
│   ├── download.py          # Fetch archives from Lovdata API
│   ├── parser.py            # XML → dataclass parsing
│   ├── store.py             # Write snapshot directory
│   └── cli.py               # `lovdata-load` entry point
├── tests/
│   ├── test_parser.py
│   ├── test_store.py
│   ├── test_download.py
│   ├── fixtures/
│   │   ├── fixture_grunnloven.xml
│   │   ├── fixture_norske_lov.xml
│   │   ├── fixture_lovtidend.xml
│   │   └── fixture_regnskapsloven.xml
│   └── conftest.py
├── pyproject.toml
├── LICENSE
└── README.md
```

### models.py — Data models

```python
"""Structured data models for parsed Norwegian law data.

These models are the contract between lovdata-loader and lovdata-publisher.
They define the shape of a snapshot: what the loader produces and what the
publisher consumes.
"""
from dataclasses import dataclass, field


@dataclass
class ListItem:
    identifier: str       # e.g. "a)", "1.", "-"
    text: str


@dataclass
class Paragraph:
    text: str
    list_items: list[ListItem] = field(default_factory=list)


@dataclass
class Article:
    name: str             # e.g. "§ 1-1"
    header_text: str      # e.g. "§ 1-1. Lovens virkeområde"
    paragraphs: list[Paragraph] = field(default_factory=list)


@dataclass
class Section:
    heading: str          # e.g. "Kapittel 1. Virkeområde"
    articles: list[Article] = field(default_factory=list)


@dataclass
class LawData:
    """A fully parsed consolidated law. One per law file."""
    refid: str
    title: str
    short_title: str
    ministry: str
    date_in_force: str
    last_amended: str
    last_amended_in_force: str
    legal_area: str
    sections: list[Section] = field(default_factory=list)
    # For top-level articles not inside a section (e.g. short laws)
    top_level_articles: list[Article] = field(default_factory=list)


@dataclass
class Amendment:
    change_type: str      # change | repeal | add | move | unknown
    target: str           # e.g. lov/1999-07-02-64/§21
    instruction: str      # e.g. "§ 21 skal lyde:"
    new_text: str


@dataclass
class AmendmentActData:
    """A parsed Lovtidend amendment act."""
    refid: str
    filename: str
    title: str
    short_title: str
    date_in_force: str
    date_published: str
    ministry: str
    changes_to: list[str]
    amendments: list[Amendment]
    misc_info: str
    journal_number: str


@dataclass
class Manifest:
    version: int
    created_at: str
    loader_version: str
    gjeldende_archive: str
    lovtidend_archives: list[str]
    law_count: int
    amendment_act_count: int
    amendment_count: int
```

### parser.py — Where current pipeline.py parsing logic goes

Maps from current `pipeline.py`:

| Current function | New location | Changes |
|---|---|---|
| `extract_header_field()` | `parser.py` | Unchanged |
| `extract_header_list()` | `parser.py` | Unchanged |
| `extract_last_changed_by()` | `parser.py` | Unchanged |
| `parse_law_metadata()` | `parser.py` → returns `LawData` (metadata only) | Returns new model |
| `legal_article_to_markdown()` | **Removed** — replaced by `parse_article()` | Returns `Article` dataclass, not markdown string |
| `section_to_markdown()` | **Removed** — replaced by `parse_section()` | Returns `Section` dataclass, not markdown string |
| `law_to_markdown()` | **Split**: parsing → `parse_law()` in loader, formatting → `format_law()` in publisher | Critical split point |
| `parse_consolidated_archive()` | `parser.py` → returns `list[LawData]` | Returns structured data, no file I/O |
| `parse_amendment()` | `parser.py` | Unchanged |
| `parse_lovtidend_file()` | `parser.py` → returns `AmendmentActData` | Renamed model |
| `parse_lovtidend_archive()` | `parser.py` → returns `list[AmendmentActData]` | Returns structured data |
| `parse_effective_date()` | `parser.py` | Unchanged (shared utility) |
| `parse_publication_date()` | `parser.py` | Unchanged (shared utility) |

Key new functions:

```python
def parse_article(article_tag: Tag) -> Article:
    """Parse an XML <article class="legalArticle"> into structured data."""
    ...

def parse_section(section_tag: Tag) -> Section:
    """Parse an XML <section> into structured data."""
    ...

def parse_law(content: bytes) -> LawData | None:
    """Parse a single law XML document into structured data."""
    ...

def parse_consolidated_archive(archive_path: str) -> list[LawData]:
    """Parse all laws from the consolidated archive. No file I/O."""
    ...

def parse_lovtidend_archive(archive_path: str, prefix_filter: str = "nl-") -> list[AmendmentActData]:
    """Parse all amendment acts from a Lovtidend archive."""
    ...
```

### store.py — Snapshot serialization

```python
def write_snapshot(
    output_dir: str,
    laws: list[LawData],
    amendment_acts: list[AmendmentActData],
    source_archives: dict[str, str],
) -> str:
    """Write a snapshot directory from parsed data. Returns path."""
    ...

def read_snapshot(snapshot_dir: str) -> tuple[list[LawData], str]:
    """Read laws from a snapshot directory. Returns (laws, db_path)."""
    ...
```

### download.py — Mostly unchanged from current

```python
def download_archives(output_dir: str = ".") -> dict[str, str]:
    """Download all archives from Lovdata API. Returns paths."""
    ...
```

### cli.py — `lovdata-load` command

```
Usage: lovdata-load [OPTIONS]

  Download and parse Lovdata archives into a snapshot directory.

Options:
  --output DIR          Snapshot output directory [default: snapshot/]
  --download            Download archives from API first
  --gjeldende PATH      Path to consolidated laws archive
  --lovtidend PATH      Paths to Lovtidend archives (repeatable)
  --skip-amendments     Skip Lovtidend parsing (faster, laws only)
```

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lovdata-loader"
version = "0.1.0"
description = "Download and parse Norwegian law XML from the Lovdata public API"
requires-python = ">=3.11"
license = {text = "MIT"}
dependencies = [
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
]

[project.optional-dependencies]
test = ["pytest>=8.0"]

[project.scripts]
lovdata-load = "lovdata_loader.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/lovdata_loader"]
```

Note: `pyyaml` is **not** a dependency. The loader produces JSON, not YAML.

---

## Library 2: `lovdata-publisher`

### Purpose

Read a snapshot directory and produce all outputs: Markdown files, git history,
Quarto book, releases, search index. All formatting and publishing concerns live here.

### Package structure

```
lovdata-publisher/
├── src/lovdata_publisher/
│   ├── __init__.py          # __version__
│   ├── formatter.py         # LawData → Markdown with YAML frontmatter
│   ├── git_export.py        # FastImportStream, backdated commits, tags
│   ├── quarto.py            # Quarto book generation
│   ├── releases.py          # Monthly tag management
│   ├── search_index.py      # Search index merging
│   └── cli.py               # `lovdata-publish` entry point
├── tests/
│   ├── test_formatter.py
│   ├── test_git_export.py
│   ├── test_quarto.py
│   └── conftest.py
├── pyproject.toml
├── LICENSE
└── README.md
```

### formatter.py — The core formatting engine

This is where `law_to_markdown()` lands, but now it operates on structured `LawData`
objects instead of raw BeautifulSoup. This is the key win: formatting is deterministic
and decoupled from XML parsing quirks.

```python
def format_law_markdown(law: LawData) -> str:
    """Convert a structured LawData object to Markdown with YAML frontmatter.

    This function is deterministic: same input always produces same output.
    It does not touch XML, HTML, or the network.
    """
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f'tittel: "{law.title}"')
    if law.short_title:
        lines.append(f'korttittel: "{law.short_title}"')
    lines.append(f'refid: "{law.refid}"')
    lines.append(f'departement: "{law.ministry}"')
    lines.append(f'ikrafttredelse: "{law.date_in_force}"')
    if law.last_amended:
        lines.append(f'sist-endret: "{law.last_amended}"')
    if law.last_amended_in_force:
        lines.append(f'sist-endret-ikrafttredelse: "{law.last_amended_in_force}"')
    lines.append("---")
    lines.append("")
    lines.append(f"# {law.title}")
    lines.append("")

    for section in law.sections:
        lines.append(format_section(section))

    for article in law.top_level_articles:
        lines.append(format_article(article, depth=0))

    return "\n".join(lines)


def format_section(section: Section) -> str:
    """Format a Section as Markdown."""
    ...

def format_article(article: Article, depth: int = 0) -> str:
    """Format an Article as Markdown."""
    ...
```

### git_export.py — Where git operations go

Maps from current `pipeline.py`:

| Current function/class | New location | Changes |
|---|---|---|
| `FastImportStream` | `git_export.py` | Unchanged |
| `date_to_git_timestamp()` | `git_export.py` | Unchanged |
| `format_commit_message()` | `git_export.py` | Takes `AmendmentActData` from snapshot |
| `generate_tag_readme()` | `git_export.py` | Reads from formatted markdown dict |
| `create_yearly_tags()` | `git_export.py` | Unchanged |
| `run_pipeline()` | **Split**: data loading part in loader CLI, git building in `build_history()` | Critical split point |

```python
def build_history(
    snapshot_dir: str,
    repo_path: str,
    db_path: str,
) -> str:
    """Build a git repository with backdated commits from a snapshot.

    1. Reads laws from snapshot, formats to Markdown
    2. Reads amendment acts from SQLite
    3. Creates initial commit with all laws
    4. Creates one commit per amendment, sorted by date
    5. Creates yearly tags

    Returns repo path.
    """
    ...
```

### quarto.py, releases.py, search_index.py

These move almost unchanged. The only difference is that `quarto.py` reads from
the formatted `lover/*.md` files (same as today) rather than directly from XML.

### cli.py — `lovdata-publish` command

```
Usage: lovdata-publish [OPTIONS]

  Read a snapshot and produce formatted outputs.

Options:
  --snapshot DIR        Snapshot directory to read [default: snapshot/]
  --output DIR          Output directory for Markdown files [default: .]
  --format-only         Write Markdown files only, skip git operations
  --build-history       Build the law-history branch with backdated commits
  --quarto              Generate Quarto book chapters
  --repo-path DIR       Git repo path for history operations
```

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lovdata-publisher"
version = "0.1.0"
description = "Format and publish Norwegian law data as Markdown, git history, and Quarto books"
requires-python = ">=3.11"
license = {text = "MIT"}
dependencies = [
    "pyyaml>=6.0",
]

[project.optional-dependencies]
loader = ["lovdata-loader>=0.1.0"]
test = ["pytest>=8.0"]

[project.scripts]
lovdata-publish = "lovdata_publisher.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/lovdata_publisher"]
```

Note: `beautifulsoup4` and `lxml` are **not** dependencies. The publisher never touches XML.

---

## Module-by-Module Migration Map

### Current → New (complete mapping)

```
src/lovdata_pipeline/
├── __init__.py
│   └─→ split into both packages' __init__.py
│
├── download.py
│   └─→ lovdata-loader/src/lovdata_loader/download.py     (unchanged)
│
├── pipeline.py
│   ├─ LawMetadata          →  loader/models.py::LawData       (expanded)
│   ├─ Amendment             →  loader/models.py::Amendment     (unchanged)
│   ├─ AmendmentAct          →  loader/models.py::AmendmentActData (renamed)
│   │
│   ├─ extract_header_field  →  loader/parser.py                (unchanged)
│   ├─ extract_header_list   →  loader/parser.py                (unchanged)
│   ├─ extract_last_changed  →  loader/parser.py                (unchanged)
│   ├─ parse_law_metadata    →  loader/parser.py                (unchanged)
│   ├─ parse_amendment       →  loader/parser.py                (unchanged)
│   ├─ parse_lovtidend_file  →  loader/parser.py                (unchanged)
│   ├─ parse_lovtidend_archive → loader/parser.py               (unchanged)
│   ├─ parse_consolidated_archive → loader/parser.py            (returns LawData, no file I/O)
│   ├─ parse_effective_date  →  loader/parser.py                (unchanged)
│   ├─ parse_publication_date → loader/parser.py                (unchanged)
│   │
│   ├─ legal_article_to_markdown → SPLIT:
│   │   ├─ parse_article()   →  loader/parser.py  (XML → Article dataclass)
│   │   └─ format_article()  →  publisher/formatter.py (Article → Markdown)
│   │
│   ├─ section_to_markdown   → SPLIT:
│   │   ├─ parse_section()   →  loader/parser.py  (XML → Section dataclass)
│   │   └─ format_section()  →  publisher/formatter.py (Section → Markdown)
│   │
│   ├─ law_to_markdown       → SPLIT:
│   │   ├─ parse_law()       →  loader/parser.py  (XML → LawData)
│   │   └─ format_law_markdown() → publisher/formatter.py (LawData → Markdown)
│   │
│   ├─ init_db               →  loader/store.py                 (unchanged)
│   ├─ store_amendment_act   →  loader/store.py                 (unchanged)
│   │
│   ├─ FastImportStream      →  publisher/git_export.py         (unchanged)
│   ├─ date_to_git_timestamp →  publisher/git_export.py         (unchanged)
│   ├─ format_commit_message →  publisher/git_export.py         (unchanged)
│   ├─ CHANGE_TYPE_LABELS    →  publisher/git_export.py         (unchanged)
│   ├─ generate_tag_readme   →  publisher/git_export.py         (unchanged)
│   ├─ create_yearly_tags    →  publisher/git_export.py         (unchanged)
│   ├─ refid_to_filepath     →  publisher/formatter.py          (unchanged)
│   │
│   └─ run_pipeline          → SPLIT:
│       ├─ parse + store     →  loader/cli.py
│       └─ format + git      →  publisher/cli.py
│
├── quarto.py
│   └─→ lovdata-publisher/src/lovdata_publisher/quarto.py  (unchanged)
│
├── releases.py
│   └─→ lovdata-publisher/src/lovdata_publisher/releases.py (unchanged)
│
├── search_index.py
│   └─→ lovdata-publisher/src/lovdata_publisher/search_index.py (unchanged)
│
└── cli.py
    └─→ split into loader/cli.py and publisher/cli.py
```

---

## Why This Split Makes Outputs Consistent

### Problem: inconsistent API data across runs

If you run the pipeline on Monday and Tuesday, and the API updated a law between
those runs, the Markdown output, git history, and Quarto book will all differ — even
for laws that didn't change. This happens because:

1. Parsing and formatting are interleaved — you can't compare "what the API gave us"
   versus "what we produced" because the intermediate state is ephemeral.
2. No way to detect which specific laws changed between runs.

### Solution: the snapshot is the checkpoint

```
Run 1 (Monday):
  lovdata-load → snapshot-2026-02-17/
  lovdata-publish --snapshot snapshot-2026-02-17/ → lover/*.md

Run 2 (Tuesday, API has new data):
  lovdata-load → snapshot-2026-02-18/

  # Before publishing, diff the snapshots:
  diff -r snapshot-2026-02-17/laws/ snapshot-2026-02-18/laws/

  # Only the changed laws show up. If the diff looks wrong, investigate.
  # If it looks right, publish from the new snapshot:
  lovdata-publish --snapshot snapshot-2026-02-18/ → lover/*.md
```

Key invariant: **`lovdata-publish` is deterministic**. Given the same snapshot, it
always produces byte-identical Markdown. This means:

- Restarting a failed publish is safe (just re-run with the same snapshot).
- You can re-generate all outputs from an archived snapshot months later.
- Formatting bugs are isolated: fix `formatter.py`, re-run on the same snapshot,
  compare output.

---

## Updated CI/CD Workflows

### deploy.yml (main branch — weekly law updates)

```yaml
name: Update laws and deploy book

on:
  schedule:
    - cron: '0 6 * * 1'
  workflow_dispatch:

jobs:
  load:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install loader
        run: pip install lovdata-loader

      - name: Download and parse
        run: lovdata-load --download --output snapshot/

      - name: Upload snapshot
        uses: actions/upload-artifact@v4
        with:
          name: snapshot
          path: snapshot/
          retention-days: 30

  publish:
    needs: load
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download snapshot
        uses: actions/download-artifact@v4
        with: { name: snapshot, path: snapshot/ }

      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install publisher
        run: pip install lovdata-publisher

      - name: Format Markdown
        run: lovdata-publish --snapshot snapshot/ --output . --format-only

      - name: Generate Quarto chapters
        run: lovdata-publish --snapshot snapshot/ --output . --quarto

      - uses: quarto-dev/quarto-actions/setup@v2
      - name: Render book
        run: quarto render

      - name: Merge search index
        run: python -m lovdata_publisher.search_index _site laws.json

      - name: Commit and deploy
        run: |
          git config user.name "Lovtidend"
          git config user.email "lovtidend@lovdata.no"
          git add lover/ book/ _quarto.yml index.qmd laws.json
          if ! git diff --staged --quiet; then
            git commit -m "Oppdater lover $(date +%Y-%m-%d) [skip ci]"
            git push
          fi

      - name: Deploy to Pages
        uses: JamesIves/github-pages-deploy-action@v4
        with: { folder: _site, branch: gh-pages, clean: true }
```

### law-history.yml (law-history branch — weekly rebuild)

```yaml
name: Build law history branch

on:
  schedule:
    - cron: '0 7 * * 1'
  workflow_dispatch:

jobs:
  build-history:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install both libraries
        run: pip install lovdata-loader lovdata-publisher

      - name: Cache historical archive
        uses: actions/cache@v4
        with:
          path: /tmp/lovtidend-avd1-2001-2025.tar.bz2
          key: lovtidend-historical-2001-2025

      - name: Load snapshot
        run: lovdata-load --download --output /tmp/snapshot/

      - name: Build git history
        run: |
          mkdir -p /tmp/law-repo && cd /tmp/law-repo
          git init --initial-branch=main
          lovdata-publish --snapshot /tmp/snapshot/ --build-history --repo-path /tmp/law-repo

      - name: Push
        run: |
          cd /tmp/law-repo
          git branch -m main law-history
          git remote add origin https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git
          git push -f origin law-history
          git push -f origin --tags
```

---

## Migration Steps (execution order)

### Phase 1: Create `lovdata-loader` (can be done independently)

1. Create new repo `lovdata-loader`
2. Copy and refactor parsing code from `pipeline.py` into `parser.py`
3. Create `models.py` with the structured data models
4. Create `store.py` for snapshot serialization (JSON + SQLite)
5. Move `download.py` with minimal changes
6. Write CLI that chains: download → parse → store
7. Port existing parser tests, add snapshot round-trip tests
8. Publish to PyPI (or just GitHub for now)

### Phase 2: Create `lovdata-publisher` (depends on models from Phase 1)

1. Create new repo `lovdata-publisher`
2. Add `lovdata-loader` as an optional dependency (only for the models)
3. Write `formatter.py` with the Markdown generation from structured data
4. Move `git_export.py` (FastImportStream, commit formatting, tags)
5. Move `quarto.py`, `releases.py`, `search_index.py` with minimal changes
6. Write CLI that chains: read snapshot → format → publish
7. Port existing formatting tests, add round-trip tests
8. Publish

### Phase 3: Update `norwegian-laws` repo

1. Remove `src/lovdata_pipeline/` entirely
2. Update `pyproject.toml` to depend on both libraries
3. Update GitHub Actions workflows per the examples above
4. Update `TODO.md` and `README.md`
5. Test end-to-end with a manual `workflow_dispatch`

### Phase 4: Shared models package (optional, if warranted)

If the two libraries need to share the dataclass models at import time (e.g., the
publisher needs to deserialize `LawData` objects), extract `models.py` into a third
micro-package `lovdata-models`. For now, the publisher can just read JSON dicts
without importing the loader's models — the snapshot JSON schema *is* the contract.

---

## Dependency Graph

```
lovdata-loader                    lovdata-publisher
├── beautifulsoup4 >=4.12         ├── pyyaml >=6.0
├── lxml >=5.0                    └── (no BS4, no lxml)
└── (no pyyaml, no git)

         snapshot directory
         (JSON + SQLite)
              │
              └── the only coupling point
```

Neither library depends on the other at runtime. The snapshot directory format
(documented in this file) is the contract. This means:

- You can upgrade `lovdata-loader` without touching the publisher.
- You can fix formatting bugs in the publisher and re-run on an old snapshot.
- A completely different tool could produce a valid snapshot directory.

---

## Testing Strategy

### lovdata-loader tests

```
tests/
├── test_parser.py           # XML fixture → LawData assertions
│   ├── test_parse_grunnloven_metadata
│   ├── test_parse_article_structure
│   ├── test_parse_section_with_lists
│   ├── test_parse_lovtidend_amendment_types
│   └── test_parse_effective_date_*  (existing tests, moved here)
├── test_store.py            # LawData → JSON → LawData round-trip
│   ├── test_write_read_roundtrip
│   ├── test_manifest_counts
│   └── test_amendments_db_schema
├── test_download.py         # Mock urllib, verify URLs called
└── fixtures/                # Existing XML fixtures, moved here
```

### lovdata-publisher tests

```
tests/
├── test_formatter.py        # LawData → Markdown assertions
│   ├── test_frontmatter_fields
│   ├── test_section_heading_levels
│   ├── test_list_formatting
│   ├── test_deterministic_output  (same input → same output)
│   └── test_special_characters_escaped
├── test_git_export.py       # FastImportStream, commit messages
│   ├── test_commit_message_format
│   ├── test_deferred_date_handling
│   └── test_amendment_commit_structure
├── test_quarto.py           # Chapter generation
│   ├── test_split_departments  (existing, moved here)
│   └── test_group_laws_by_area
└── conftest.py              # Shared fixtures (sample LawData objects)
```

### Integration test (in `norwegian-laws` repo)

```python
def test_full_pipeline(tmp_path):
    """End-to-end: XML fixture → snapshot → Markdown → verify content."""
    # 1. Parse fixture
    laws = parse_consolidated_archive("tests/fixtures/small_archive.tar.bz2")

    # 2. Write snapshot
    write_snapshot(tmp_path / "snapshot", laws, [], {})

    # 3. Read and format
    loaded_laws, _ = read_snapshot(tmp_path / "snapshot")
    for law in loaded_laws:
        md = format_law_markdown(law)
        assert md.startswith("---")
        assert law.refid in md
```

---

## Open Questions

1. **Shared models package?** — The publisher needs to deserialize law data from JSON.
   It can either import `lovdata-loader`'s models (adding a dependency) or just work
   with plain dicts. Recommendation: start with plain dicts, extract shared models
   only if type-checking friction becomes painful.

2. **Where does `refid_to_filepath()` live?** — It's used by both formatting (to name
   files) and git export (to create commits). Put it in the publisher since the loader
   doesn't write Markdown files.

3. **Should the publisher accept raw XML as a fallback?** — No. If you need to go from
   XML to Markdown, run the loader first. Single responsibility.

4. **PyPI or just GitHub?** — Start with GitHub-only (`pip install git+https://...`).
   Publish to PyPI once the APIs stabilize.
