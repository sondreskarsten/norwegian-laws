# norwegian-laws: Task List

## Current state (2026-07-21)

**Production:**
- Repo: github.com/sondreskarsten/norwegian-laws (public, MIT code + NLOD 2.0 data)
- 794 lover + 3,438 sentrale forskrifter; Lovdata manifest polled daily at
  02:00 UTC, deploy dispatched on change (event-driven, not cron)
- Archive cache: exact weekly keys, no restore-keys fallback (a prefix
  fallback froze consolidated texts 2026-06-14..07-21 while lovtidend,
  which is uncached, kept flowing)
- `law-history` branch: per-act commits, LFS-backed, yearly tags v2000
  and onward; rebuilt via dispatch chained from a successful deploy
- Live site on gh-pages: per-law/per-forskrift pages, dept and topic
  chapters, per-paragraph history pages, aktivitet leaderboard, Atom
  feeds (per law/topic/ministry), JSONL manifests + JSON Schemas
- 137 passing tests (38 loader + 99 publisher); pytest runs per package
- 6 GitHub Actions workflows: poll-lovdata (daily), deploy
  (repository_dispatch + push), law-history (dispatch-chained),
  gcs-sync (dispatch-chained), release (tags v*.*.*), test
- README counts (coverage, feeds, amendment acts, per-paragraph pages)
  refresh from data on every deploy via readme_updater; stale generated
  book chapters are pruned by generate_quarto_config
- The lovdata-pipeline monolith, its root pyproject, and its orphaned
  test suite were removed 2026-07-21 (MIGRATION.md Phase 3)

**Per-law pages include:**
- Cross-reference linking to related laws/forskrifter
- Section-level `<h4 id="...">` anchors on every § for deep-linking
- Version banner pointing at git history and version table
- Rettsområde row in metadata (one-to-many via parser fix)
- Lovdata.no source link
- Full body text indexed in search.json

**Atom feed:** Top 100 most-recent amendments, autodiscovered via
`<link rel="alternate" type="application/atom+xml">` in every book page head.

**Diff page (book/diff.qmd):** Pick any law or forskrift, pick two yearly
tag versions, click "Sammenlign tekst" to render a side-by-side diff
inline. Uses diff2html-ui + jsdiff loaded from jsdelivr; fetches raw text
from `raw.githubusercontent.com` (LFS resolved server-side, CORS *).
Falls back to GitHub compare and endringslogg buttons.

`laws.json` (used by the diff page and dept search index) contains both
lover and forskrifter entries with `kind`, `path`, `tags`, and per-law
`amendments` counts.

---

## Remaining items

### Deferred (not worth doing)

- **PDF export.** A single PDF of all laws+forskrifter is unusable. Per-law
  PDFs are duplicative of the per-law HTML pages.
- **Workflow dedup.** deploy.yml and law-history.yml both run `lovdata-load`.
  Saves ~2 min on Mondays, adds coordination complexity.
- **PAT rotation.** The GitHub PAT is in project context. Deferred per
  project policy.
- **Per-version pages.** Lovdata renders each historical version as its own
  page. Doing it here would require rendering each law at each yearly
  tag (~20K extra pages × LFS smudge cost). The diff page covers the
  "what changed between version X and Y" workflow without this expense.
