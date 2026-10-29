# Stress test log, 29 October 2026

Problems found while driving the repository through the new MCP server (`norwegian-laws-mcp/`) against live data, and while checking the history delivery. Each entry states the evidence, the cause, and what was done. Numbers come from the public observation bundle `observation-fb66b73d…` (sources dated 2026-10-01) unless stated otherwise.

Status key: **fixed** (code changed in this branch, takes effect on the next publication), **mitigated** (visible but labelled), **open** (not changed, reason given).

## Data produced by the pipeline

| # | Problem | Evidence | Cause | Status |
|---|---|---|---|---|
| D1 | Amendment records with a `skal lyde:` instruction but no replacement wording | 1,745 of 86,302 such records in `amendments.db`; 1,668 visible in `historie/*.md`; the rate triples from 2024 (167, 173, 119 per year vs ~40 before). Example: `lov/2025-04-10-11` "§ 3-1 tredje ledd skal lyde:" for regnskapsloven. | Newer Lovtidend markup puts the wording in `article.numberedLegalP` directly under `article.change`; `parse_amendment` only collected `legalP` and `future*` elements. | **fixed** (`parse_amendment` collects `numberedLegalP`, `listArticle`, `centeredP`; test `test_new_format_numbered_ledd_is_replacement_text`) |
| D2 | Replacement heading text duplicated | `lov/2024-06-21-42` "§ 3-1 paragrafoverskriften skal lyde:" produced the heading twice; 36 exact duplicate records across `historie/`. | `futureLegalArticleHeader` spans nested inside `futureLegalArticle` were collected in addition to their parent. | **fixed** (nested future elements skipped; a future article now yields one line per heading and ledd; test `test_new_format_future_article_text_not_duplicated`) |
| D3 | Old-format acts lose wording that Lovdata encodes as a heading | `lov/2001-06-15-41` "Avsnittets tittel skal lyde:" (new title is an `h3`), "Nytt kapittel 1 A skal lyde:" and similar; part of the ~40 empty records per year before 2024. | `_parse_old_format_section` skipped every heading element. | **fixed** (headings after an instruction are kept; bare part markers such as `I`, `II` are not; test `test_old_format_heading_after_instruction_is_text`) |
| D4 | Acts that change one document but match no instruction pattern vanish from that document's history | KOSTRA-forskriften: `forskrift/2025-10-29-2134` and `forskrift/2024-10-14-2624` ("Følgende art går ut", "Funksjon 211 endrer navn til …") produced zero records, so `historie/forskrift-2019-10-18-1412.md` ends in 2023 while README lists the act. 8,331 single-target acts in the database have zero records. | No fallback for unrecognised instruction forms. | **fixed** for single-target acts: the body is kept as one `unknown` record (test `test_unrecognised_single_target_act_keeps_body_as_unknown_record`). Multi-target acts without recognised instructions (see D5) stay empty. |
| D5 | Acts with several targets and no recognised instructions | 17,675 of 39,241 acts have zero records; 7,268 have no `changesToDocuments` at all (new laws, commencement decisions, delegations) and are not amendment acts; the remainder minus D4 are multi-target acts with unrecognised wording. | Attribution needs per-section preambles, which these acts lack. | **open**: recorded here; a per-section fallback would attribute text to the wrong law. |
| D6 | Records carry only new wording, never the replaced text | By design of the Lovtidend parse. | — | **mitigated**: every MCP history tool states this; `laws_amendment_records` also returns Lovdata's own "Endret ved lover …" note per provision. |
| D7 | Future-dated records | `historie/` holds 172 records dated 2027 and 2 dated 2028 (acts published with later commencement). | Display date is the act's commencement. | **open**: correct per source; labelled as display dates. |

## Git history and reader

| # | Problem | Evidence | Cause | Status |
|---|---|---|---|---|
| H1 | The `law-history` branch is frozen | Tip `096496c` dated 2026-09-18; the reader's "rekonstruksjonslogg" links (`laws.json` `log`, department tables, per-law pages) point at it, so every change since September is missing there while `main` has it. | Workflow replaced by an "explain-only" stub on 2026-09-25 (PR #18) when work moved to `norwegian-laws-history`. | **fixed**: `.github/workflows/law-history.yml` rebuilds nightly at 05:30 UTC (see H6 for what changed versus the retired version). |
| H2 | `norwegian-laws-history` does not give users history | Its daily workflow succeeds (55 runs) and the CLI works, but it is a ledger of source-archive digests and qualified HTML bodies since 2026-09-25. `list` takes 17 s and `show` 33 s because every call re-verifies 678 MB of ledger files; any past version requires a 191–240 MB bundle download. Reconstruction of past legal states was never delivered (`docs/WIND-DOWN.md`). | Product scope. | **open** by decision: the repository stays as the evidence product; user-facing history reverts to the in-repo branch (H1). |
| H3 | Issue #3: orphan `v2000` tag | Tag exists on the remote; no build produces a 2000 commit (baseline is dated 2001-01-01). | Never cleaned after an earlier build. | **fixed**: the workflow deletes yearly tags the build did not produce. |
| H4 | Issue #4: `v2027`/`v2028` tags and date order contradicting graph order | Reproduced locally with the retired code: 30 commits, tags up to `v2028`, reset commit dated 2026-10-01 placed after commits dated 2028-01-01. | Acts with future commencement were applied; the reset commit took the newest commencement date. | **fixed**: `build_history(cutoff_date=…)` skips acts commencing after the build date, dates the reset commit on the build date, and `create_yearly_tags(max_year=…)` never tags future years (tests in `test_git_export.py`). |
| H5 | Issue #7: nightly force-push leaves no citable SHA | Pinned SHAs in `legacy_versions.py` would become unreachable at the first rebuild. | Branch and tags were replaced wholesale. | **fixed**: each build pushes `history-YYYY-MM-DD`; the previous tip is tagged before replacement; tags older than 35 days are pruned except the first build of each month. |
| H6 | Reader version pages pinned to September commits | `book/versjoner.qmd` and the diff tool used a fixed catalog of 26 SHAs. | Pinning was the workaround for H5. | **fixed**: version refs are the live yearly tags; pages say the branch is rebuilt nightly and name the build tags. |
| H7 | Issue #6: repealed documents absent from the reconstruction | Inherent to a baseline built from current consolidated text. | — | **open**. |
| H8 | README said regeneration needs `ENABLE_LEGACY_HISTORY=true` | The variable gate still exists in `deploy.yml` but the referenced workflow no longer rebuilt anything. | Stale after the retirement. | **fixed**: README paragraph rewritten; the gate in `deploy.yml` is left as is (the nightly schedule does not need it). |
| H9 | Git history on `main` begins 2026-02-18 and mixes parser commits with source updates | For regnskapsloven, 3 of 10 commits are parser/format work. | — | **mitigated**: MCP tags commits `source-update` or `pipeline` and states the history span. |

## MCP server (`norwegian-laws-mcp/`)

Found and fixed during the same test; listed for completeness: dates before the first commit errored instead of clamping; no coverage statement in outputs; `grunnloven`/`Grl.` did not resolve; `aml` matched `saml`; refid spellings scored low in catalog search; definition patterns missed "X menes"; deleted documents lacked titles in change listings.

## Not reproducible in this environment

- `api.lovdata.no` and `sondreskarsten.github.io` are not reachable from the session proxy, so the live site and a fresh Lovdata download were not checked; the public observation bundle was used instead.
- The GitHub Actions snapshot artifact needs an authenticated download, which was not performed.
