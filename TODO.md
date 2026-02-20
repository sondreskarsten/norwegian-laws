# norwegian-laws: Task List

## Current State (2026-02-19)

**Working:**
- Repo: github.com/sondreskarsten/norwegian-laws (public, MIT + NLOD 2.0)
- 774 laws parsed to Markdown in `lover/`
- Quarto book live at sondreskarsten.github.io/norwegian-laws
- 3 GitHub Actions workflows (deploy, law-history, release)
- v0.2.0 released
- `law-history` branch exists with 7 backdated commits (1 initial + 6 from 2026 Lovtidend)
- Weekly cron schedule for updates

**Broken or incomplete:**
- `law-history` branch has only 6 amendment commits — should have thousands (historical archives not fetched)
- `sist-endret` frontmatter mangled for 575 of 774 laws
- Quarto search indexes only chapter titles, not individual law text

---

## P0: Critical — data is wrong or missing

### 1. Download historical Lovtidend archive (2001–2025)

`download.py` only fetches `lovtidend-avd1-2026.tar.bz2` (190 KB, 6 acts). The API also hosts `lovtidend-avd1-2001-2025.tar.bz2` (69 MB, ~35,000 XML docs). Without it, the `law-history` branch is nearly empty.

**File:** `lovdata-loader/src/lovdata_loader/download.py`
**Fix:** Add `lovtidend_historical` to the download list in `download_archives()`. The key already exists in `ARCHIVES` dict but is skipped in the loop.
**Impact:** Enables thousands of backdated amendment commits instead of 6.
**Note:** 69 MB download + parsing ~35k XML files. CI runtime will increase from ~1 min to ~5–10 min.

### 2. Fix `sist-endret` frontmatter mangling

575 of 774 laws have mangled `sist-endret` values like:
```
sist-endret: "lov/2025-06-20-106fra 2026-01-01"
```
Should be something like:
```
sist-endret: "lov/2025-06-20-106"
ikrafttredelse-endring: "2026-01-01"
```

**Root cause:** `extract_header_field()` calls `get_text(strip=True)` on a `<dd>` element containing `<a href="...">lov/2025-06-20-106</a>fra 2026-01-01`. BeautifulSoup concatenates the anchor text and the sibling text node without a separator.

**File:** `lovdata-loader/src/lovdata_loader/parser.py`, `extract_last_changed_by()`
**Fix:** Either extract only the `<a>` text for `sistEndret`, or split on known patterns like "fra ".
**Impact:** 575 laws get correct metadata. Downstream: commit messages, Quarto display, any future filtering by amendment date.

### 3. Amendment commits have no real content diffs

The `law-history.yml` workflow updates only the `sist-endret` frontmatter field per commit — not the actual law text. Every commit just changes one YAML line, so `git diff` is useless for seeing what actually changed in the law.

**Root cause:** The consolidated archive contains only the *current* text of each law. Lovtidend XML contains the *instruction* ("§ 21 skal lyde:") and the *new text* of individual sections, but the pipeline doesn't patch these into the markdown.

**Options:**
- **(a) Minimal:** Accept that diffs show metadata-only changes. Document this clearly. The `law-history` branch shows *when* a law was amended and *by which act*, not *what changed*. Still useful.
- **(b) Ambitious:** Build a section-level patcher that applies amendment instructions to reconstruct historical versions. Hard — requires mapping `data-change-part` targets (e.g. `lov/1999-07-02-64/§21`) to markdown sections and splicing in `new_text`. Error-prone given the variety of amendment patterns.
- **(c) Compromise:** Include the amendment instruction and new text as a commit message body, so `git log -p` at least shows what the Lovtidend *said* changed, even if the file diff is just metadata.

**Recommendation:** (a) now, (c) soon, (b) maybe never.

---

## P1: Significant — functionality gaps

### 4. Per-law Quarto pages (searchable law text)

Currently each law links to GitHub blob view. This works but means:
- No full-text search over law content from the Quarto site
- Users leave the site to read laws
- Search JSON has only 23 entries (chapter index pages)

**Options:**
- **(a)** Include all 774 `.md` files as Quarto chapters. Build time ~10 min, site size ~200 MB. Sidebar becomes massive.
- **(b)** Generate per-law `.qmd` files as "appendix" chapters under each department, with `toc: false`. Keeps sidebar manageable.
- **(c)** Keep current structure but add a static search index (lunr/fuse.js) built from law content at CI time. Best of both worlds — fast site, full search.

**Recommendation:** (c) first, revisit (b) if people want in-browser reading.

### 5. Individual yearly Lovtidend archives

The API lists `lovtidend-avd1-2001-2025.tar.bz2` as a single 69 MB bundle. Individual year archives (`lovtidend-avd1-2024.tar.bz2`, etc.) return 0 bytes via HEAD but might work via GET — needs testing.

If individual years work, the `law-history.yml` workflow could do incremental updates (only fetch current year) instead of re-downloading 69 MB every week.

**File:** `lovdata-loader/src/lovdata_loader/download.py`
**Test:** Try `urllib.request.urlretrieve` on individual year URLs.

### 6. Forskrifter (regulations) support

The API also provides `gjeldende-sentrale-forskrifter.tar.bz2`. These are regulations issued by ministries — arguably more practically useful than formal laws for many users.

**Scope:** Separate `forskrifter/` directory, own Quarto section, same pipeline pattern.
**Estimate:** ~1 day, mostly plumbing.

### 7. Commit messages for law-history: include amendment details

Currently the law-history workflow just updates `sist-endret`. The commit *message* should include:
- Which sections were changed/added/repealed (from `Amendment.target`)
- The amendment instruction text
- Stortingsvedtak reference

This is partly implemented in `format_commit_message()` but the law-history workflow bypasses `add_amendment_commit()` inline — verify it uses the full formatter.

---

## P2: Quality and polish

### 8. 28 laws missing `ikrafttredelse` (effective date)

These have `ikrafttredelse: ""` in frontmatter. May be laws with "Kongen bestemmer" or historically ambiguous dates. Check if the source XML has this data under a different field.

### 9. Lovdata.no deep links

Each law page on Quarto/GitHub could link back to the authoritative Lovdata page:
```
https://lovdata.no/dokument/NL/lov/{YYYY-MM-DD-NR}
```
Pattern is deterministic from the `refid`. Add to frontmatter and Quarto table.

### 10. Cross-reference links between laws

Many laws reference other laws by short title or refid (e.g. "jf. straffeloven § 62"). Post-processing step to convert these to internal links.

**Complexity:** Medium-high. Requires a lookup table of korttittel → filepath and regex matching in markdown.

### 11. Tests

Test suites exist in `lovdata-loader/tests/` and `lovdata-publisher/tests/`. Additional coverage targets:
- End-to-end: small fixture archive → expected JSON snapshot → expected Markdown output
- Schema drift detection: validate parser against new/changed XML structures from Lovdata
- Snapshot comparison: diff old vs new snapshots to detect regressions

### 12. `_quarto.yml` language setting

Currently `lang: en` (Quarto default). Should be `lang: nb` for Norwegian bokmål. Affects Quarto UI strings (search placeholder, sidebar labels, etc.).

---

## P3: CI/CD and infrastructure

### 13. Rotate the GitHub PAT

The PAT `ghp_d7p...` has been in conversation context and project files. It has full admin scopes. Rotate it after this session.

### 14. CI: law-history workflow should fetch historical archive

`law-history.yml` calls `lovdata-pipeline --download` which uses `download.py`, which skips the historical archive. Fix download.py first (task #1), then the workflow automatically benefits.

### 15. CI: cache downloaded archives

The 69 MB historical archive is static (only updated annually). Cache it in GitHub Actions to avoid re-downloading every week.

```yaml
- uses: actions/cache@v4
  with:
    path: lovtidend-avd1-2001-2025.tar.bz2
    key: lovtidend-historical-${{ hashFiles('...') }}
```

### 16. CI: deploy.yml self-trigger avoidance

The `update-laws` job commits to main and pushes. The push could trigger `deploy.yml` again. The commit message includes `[skip ci]` to prevent this. Verify this continues to work correctly.

### 17. Package versioning automation

Currently manual (`__init__.py` + `pyproject.toml`). Consider `hatch-vcs` or `setuptools-scm` for git-tag-based versioning.

---

## P4: Future / nice-to-have

### 18. PDF export

Removed due to missing TinyTeX in CI. Re-enable with:
```yaml
- name: Install TinyTeX
  run: quarto install tinytex
```
Adds ~2 min to CI. Generates a full PDF of the law index (not individual law texts).

### 19. RSS/Atom feed of changes

Generate a feed from the amendment database so users can subscribe to law changes. Straightforward from the SQLite data.

### 20. Topic tags / legal area classification

The XML has `legalArea` metadata. Currently extracted but not used in Quarto. Could add a second grouping axis (by topic, not just department).

### 21. Historical law versions (beyond Lovtidend)

Lovdata Pro has full historical versions. The public API only has amendments *since 2001*. For laws amended before 2001, the history will be incomplete. Document this limitation.

### 22. Diff visualization

If task #3 option (b) is ever attempted: render diffs as HTML (green/red markup) and include in the Quarto site. Would require reconstructing historical versions first.

---

## Dependency graph

```
#1 (download historical) ──→ #14 (CI uses it) ──→ #15 (cache it)
                         └──→ #3 (content diffs become meaningful with more commits)
                         └──→ #7 (commit messages)

#2 (fix sist-endret) ──→ #11 (add regression test)

#4 (per-law pages) ──→ #10 (cross-references) ──→ #22 (diff visualization)

#13 (rotate PAT) — do immediately, no dependencies
```

## Suggested order

1. **#13** — Rotate PAT (security, 2 minutes)
2. **#2** — Fix sist-endret parsing (data quality, 30 min)
3. **#1** — Download historical Lovtidend (unblocks everything else, 30 min)
4. **#7** — Better commit messages (30 min)
5. **#12** — Set `lang: nb` (5 min)
6. **#14 + #15** — CI improvements (20 min)
7. **#16** — Fix CI self-trigger (5 min)
8. **#9** — Lovdata deep links (15 min)
9. **#4** — Searchable law text (1–2 hours)
10. **#11** — Tests (2–3 hours)
