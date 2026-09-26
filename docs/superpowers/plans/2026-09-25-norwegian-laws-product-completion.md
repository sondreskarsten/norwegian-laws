# Norwegian Laws Product Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Work stays in this existing task; use bounded parallel agents only for independent work. The user's delivery-first instruction overrides a mechanical test-first or approval-pause workflow.

**Goal:** Finish the current reader, evidence distribution and historical-law product in the two personal GitHub repositories, with published output that users can retrieve and understand.

**Architecture:** `norwegian-laws` acquires source evidence and publishes the reader, feeds and display exports. `norwegian-laws-history` independently accepts evidence, qualifies readable projections, preserves prior products and develops evidence-backed legal reconstruction. The reader consumes pinned history products; immutable raw evidence and derived/legal claims remain distinct.

**Tech Stack:** Existing Python packages and standard-library history consumer, Git/GitHub Actions, Quarto, Pagefind and GitHub Pages. Production Python 3.12; preserve supported Python >=3.11 consumer compatibility and verify Windows checkout behavior. GCS remains an optional existing mirror.

**Spec:** [Product scope and user stories](../specs/2026-09-25-norwegian-laws-product-scope.md). Also read the existing history `docs/CONTRACT.md` and `docs/REUSE-AUDIT.md`; their first-pilot limit does not remove later legal reconstruction from this full plan.

## Global Constraints

- Both repositories remain under `github.com/sondreskarsten`.
- Reuse `fix/reliable-laws-delivery` and `fix/reliable-history-delivery`; minimize new branches.
- Preserve generated `gh-pages`/`law-history` branches, existing tags, source releases and accepted observations.
- All implementation, integration and coordination continue in this task. No cloud coding setup, new task or handoff.
- Delivery is the focus. Checks must establish real published behavior or prevent a demonstrated defect; test volume is not progress by itself.
- Existing documentation and green workflows are not sufficient evidence of working functionality.
- Source observation time, publication time, Git time and legal validity are separate.
- Do not turn today's consolidated text into an invented historic baseline; do not infer repeal from source disappearance.
- Raw source bytes remain retrievable when a derived representation cannot be qualified.

## Review Focus

- Mixed legal structure can retain all words while changing order or visible paragraph boundaries: D1/D6 must compare source/model/rendered output and inspect actual presentation.
- Two source occurrences can share a refid, including Constitution language variants: D4/D6 must preserve occurrences and declare display selection.
- A repeal can have empty replacement text, and one act can have several commencement rules: D7/D8 must retain operations and resolve time at the correct scope.
- Unchanged source bytes, interrupted publication or concurrent commits can cause false success or duplicate changes: D4/D5/D10 must preserve accepted state and prove replay/catch-up.
- Removed documents and unsupported historical dates can look like repeals or valid past text: D3/D8/D9 must preserve provenance and give explicit unknown/partial results.

## Delivery map and dependencies

| Package | Deliverable | Dependency | Existing issues |
|---|---|---|---|
| D1 | Finish the current ordering deployment | Existing PR14 | Main TODO shared interface |
| D2 | Complete reader/search/subscription/data journeys | D1 for final public regression | Main #3–#5, #8–#10 |
| D3 | Publish removed-document recovery and capture future exits | Existing verified backfill; D5 for future source history | Main #6 |
| D4 | Publish qualified observed-text products | Accepted source evidence; local checker/materializer | History #4/#5/#7 |
| D5 | Deliver two real observations, stable publication and independent reproduction | D4 | History #8; main #7 |
| D6 | Expand structural fidelity across the actual document corpus | D1/D4 contracts | History #4/#5; main shared interface |
| D7 | Publish operation-level and temporal evidence | Accepted complete parsed-act evidence | History #6 |
| D8 | Deliver evidence-backed historical-date reconstruction | D6/D7 plus justified baseline evidence | Follow-up beyond existing pilot issues |
| D9 | Put observed and legal history into the reader | D5 for observed UI; D8 for legal-date UI | Main #5/#7; history product |
| D10 | Prove continuing operation and finish portability/integrations | Starts now; final acceptance after shipped changes | Both TODOs / history #8 |

D2 and D3 can progress alongside D4. D7 and baseline-source discovery in D8 can progress alongside structural expansion. One orchestrator owns integration, merges and production dispatch; agents have disjoint file ownership. Do not restart a live production run.

**Immediate batch:** finish D1; ship prepared D2/D3/D4 work after real readback; then complete D5. **Next batch:** D6/D7 and D8 source feasibility. **Final product batch:** reconstruction, reader integration and continued-operation acceptance. Each package may use several small PRs on the same existing branch; no branch per work package.

## Repository and file responsibilities

Paths below are repository-relative; new paths are explicitly marked as planned.

| Repository | Paths | Responsibility |
|---|---|---|
| Main | `lovdata-loader/src/lovdata_loader/download.py`, `evidence.py`, `store.py` | Acquisition, retained source/member evidence and snapshots |
| Main | `models.py`, `parser.py`, `coverage.py` in that loader package | Ordered representation and parsing; coverage remains diagnostic until structural proof |
| Main | `lovdata-publisher/src/lovdata_publisher/formatter.py`, `per_law_pages.py` | Current readable output, references and removed-path behavior |
| Main | Publisher `quarto.py`, `search_index.py`, `manifests.py`, `feeds.py`, `feed.py` | Search, subscription, navigation, display exports and feeds |
| Main | Publisher `paragraph_history.py`, `historie_pages.py`, `stats_page.py`, `not_found.py`, `legacy_versions.py` | History/activity/recovery user journeys and legacy limitations |
| Main | `.github/workflows/deploy.yml`, `poll-lovdata.yml`, `.github/scripts/publication.py`, `publish_evidence.py`, `push_main.py` | Existing production orchestration and acknowledgement |
| History | `law_history/validation.py`, `ledger.py`, `__main__.py` | Independent acceptance, exact retrieval and CLI |
| History | Local new `law_history/structure.py`, `materialize.py` | Independent structural qualification and derived products |
| History | Planned `law_history/publication.py`; existing `.github/scripts/ingest_public_observations.py`, `.github/workflows/observe.yml` | Checked publication and catch-up in the existing workflow |
| History | Local new `reader-archive/**`; `.gitattributes` | Exact prior reader copies and byte-preserving checkout |
| History | Planned `law_history/operations.py`, `claims.py`, `baselines.py`, `reconstruct.py`, `queries.py` | Separate operation interpretation, temporal claims, prior states, reconstruction and queries |
| Main | Planned publisher `observed_history.py` | Consume pinned history indexes and generate current-site history views |
| Both | `docs/evidence/**`, relevant README/TODO/contract files | Portable acceptance evidence and accurate product descriptions |

Do not import the existing loader `reconstruct.py` or publisher `git_export.py` as legal authorities. Reuse bounded mechanics only after their preconditions and failure behavior are proved.

## D1 — Finish the current ordering deployment

**Outcome:** the five confirmed document-order defects are repaired on the actual public reader.

**Files:** main `TODO.md`, `docs/evidence/live-container-order-readback.json` (new), existing pipeline files only if production exposes a defect.

- [x] Inspect run `36171176807`: production, Pages deployment and acknowledgement completed successfully. The public receipt names source `7971606f7683612779e17cea1ef53d8531ba0fa3` and observation `ca32e6b7b13b3435683c450f81cfc1ea0ae4c0a95694a0cde0d7cf2bc20e5f4c`; no duplicate dispatch is needed.
- [x] Match the new public publication receipt, generated source commit, evidence release and committed acknowledgement. PR14 source `7971606` and acknowledgement `313d36f` agree; see `docs/evidence/live-container-order-readback.json`.
- [x] Read public output for laws `1916-07-21-2`, `2011-04-15-11`, `1967-12-15-9` and regulations `1956-11-09-5`, `2022-04-06-625`; compare the affected source sequences. All five real source/model/public sequences match.
- [x] Visually inspect closing provisions, interleaved instructions and appendix text; preserve paragraph/list/crosslink behavior already delivered. The patent appendix note was also checked publicly after PR15; affected heading and ordinary body crosslinks work.
- [x] Accept the new evidence contract independently in history and record what changed because of representation rather than legal amendment. The local two-real-observation consumer rehearsal accepts `ca32e6b7…`; its three qualified bodies remain unchanged, complex bodies remain unqualified and no legal amendment is inferred. Portable evidence is included in history PR11.
- [x] Commit the acceptance receipt and update the TODO only after public readback.

**Done:** all five public examples and their publication identity agree. A successful job alone is insufficient.

## D2 — Finish the current reader and amendment-monitoring experience

**Outcome:** a user can search, browse, inspect amendment records and subscribe without misleading counts or unavailable-feed promises.

**Files:** main publisher `quarto.py`, `manifests.py`, `search_index.py`, `feeds.py`, `paragraph_history.py`, `historie_pages.py`, `stats_page.py`, `legacy_versions.py`; focused existing checks in `test_quarto.py`, `test_manifests.py`, `test_topic_split.py`, `test_stats_page.py`; `README.md`, `SUBSCRIBE.md`.

- [x] Finish the in-progress shared export-count implementation; homepage totals must describe the rows actually exported, including filtering, rather than the database's total instructions. Merged in main PR15; deployed readback is a separate gate below.
- [x] Use `search-catalog.json` for subscription lookup and `feeds/index.json` for availability; offer copy/open actions only for a published feed. Keep a reader route for a document without one. Merged in main PR15.
- [x] Exercise title/abbreviation/refid lookup, copy and open, an unavailable-feed case, and keyboard/mobile interaction on generated real corpus output. Local generated content passed; direct feed retrieval succeeded, while local Chrome feed display was blocked by its client. See `docs/evidence/subscription-local.json`.
- [x] Exercise topic → document → feed and ministry → document journeys; reconcile page membership with the source catalog and feed inventory. Public source `9285be5` audit reconciles all 69 topic rows, all 102 Finance documents and the feeds; see `docs/evidence/reader-journeys-public.json`.
- [x] Exercise one document timeline, one paragraph timeline and the activity page. All 33 current-corpus top rows, 26 yearly counts and 20 ministry counts reconcile. PR17 publicly fixes the fabricated commencement display, qualifies parsed coverage and contains mobile tables. Regnskapsloven §7-25 shows its original deferred clause separately from publication; paragraph/timeline/activity pages measure 375/375 at 390px. See `docs/evidence/reader-pr17-public.json`.
- [x] Confirm supported legacy references are pinned; exclude orphan/future unsupported versions from selectable results. Public version links and comparison mappings match all 26 pinned commits; v2000/v2027/v2028 are excluded. The retired manual workflow run 36210484103 succeeded with all 36 remote ref lines unchanged. These remain explicitly unverified reconstructions. See `docs/evidence/legacy-retirement-public.json`.
- [ ] Measure first/repeat metadata and full-text queries with an explicitly recorded mobile network profile. Report bytes and timing; correct material usability failures instead of claiming an unmeasured speed improvement.
- [ ] Publish through the existing pipeline, repeat the user journeys on the deployed site and update main #3–#5 only for the acceptance actually met. PR17 run `36185527804` and public receipt/acknowledgement pass at source `8ccd1da`; date, archive, ministry-label and mobile readback is recorded. Remaining issue acceptance and controlled-network measurement stay open.

**Interfaces:** display counts and exports share one authoritative eligibility definition; the compact catalog supplies document identity/navigation, the feed index supplies available subscription URLs. No display export becomes a reconstruction input.

**Done:** all listed reader journeys work publicly; feed availability, row counts and date descriptions match the actual products.

## D3 — Make removed documents retrievable and preserve future exits

**Outcome:** a visitor can retrieve a prior reader copy and its provenance, while new removals do not erase earlier observations.

**Files:** history `reader-archive/**`, `.gitattributes`, `docs/evidence/prior-reader-backfill.json`; main publisher `not_found.py`, `formatter.py`; history `ledger.py` and planned `queries.py`.

- [x] Stage the prepared 105 objects only with byte-preserving attributes; verify staged bytes against SHA-256 and original Git blob identities. Every staged object and sidecar verified; included in history PR11.
- [x] Publish the browse index, Viltloven entry, metadata sidecars and immutable original-copy links. History commit `a79eda1` is public; all 105 copies and sidecars were independently retrieved and matched their original identities (660,274 bytes).
- [x] Link public missing-page recovery to the archived copy/provenance where an exact identity exists. PR16's 105 identities/pins and representative bytes were read back; PR17 adds the public on-site archive and raw download links. Both retained documents and the unknown-page route fit 390px, and recovery links reach the archive. See `docs/evidence/reader-pr16-public.json` and `docs/evidence/reader-pr17-public.json`. One regulation raw URL is blocked by the local Chrome client; its independent HTTP bytes match.
- [x] Before future generated-current-file removal, preserve any otherwise-unretained derived copy with its source commit and detected exit; new raw observations already remain in the independent ledger.
  Deployed in PR17: exact committed bytes, atomic capture-before-prune, expected-parent/staged-deletion checks, immutable replay and re-entry versions. Controlled Git publication/readback passes. The public archive has 105 prior copies; this production run had zero new exits, so a naturally occurring exit readback remains part of continued-operation acceptance.
- [ ] Compute observation membership changes only between comparable archive scopes. Emit `not_present_in_observation`; keep legal repeal unresolved unless separately evidenced.
- [x] Verify a controlled temporary before/after corpus and a real previously removed document without changing live source membership. Controlled capture/re-entry/replay evidence is in `docs/evidence/reader-archive-local.json`; PR17 retrieves the original Viltloven and regulation bytes publicly without changing source membership.
- [ ] Update main #6 with the corrected count, published retrieval and remaining pre-observation source gaps.

**Done:** all 105 known copies are publicly addressable, their original bytes are unchanged, and a future observed exit retains retrieval. Earlier legal history is not inferred from their Git removal date.

## D4 — Publish qualified observed-text products

**Outcome:** accepted source evidence yields useful readable products for qualified documents and explicit reasons for every unqualified selection.

**Files:** history local `structure.py`, `materialize.py`, `__main__.py`, `.gitattributes`; planned `publication.py`; existing observe workflow/script; `docs/CONTRACT.md`, `README.md`, focused `test_structure.py` and new `test_materialize.py`.

**Current interfaces to finish:**
```python
qualify(raw_bytes, model_dict, refid)
# -> (report, source_inventory, source_events, source_paths, model_events, html_or_none)
materialize(repository, observation_id, refids=None, expected_parent="auto")
# -> accepted/already_present receipt
materializations(repository)
# -> verified parent-ordered receipts
```

- [x] Integrate the reviewed paragraph-display fix: multiple paragraphs in list items remain visibly separate, with markers preserved.
- [x] Finish exact source/model binding, bounded selection, receipt schema validation, artifact inventory, expected-parent checks and same-input idempotence in the materializer.
- [x] Retain a report for each requested document; failed/unsupported structure produces no promoted body. Preserve all raw evidence independently.
- [x] Publish readable body artifacts, deterministic semantic identities, generator/runtime identity and representation-change classification. Run timestamps must not contaminate semantic body identity.
- [x] Commit new observations/products append-only with normal project authorship and current publication times. Refuse unexpected remote parents and existing-file changes.
- [x] Record the actual Git commit/tree in a subsequent publication receipt, avoiding circular hashes. Recover safely if the product commit succeeded but receipt publication did not.
- [x] Integrate with the existing observation workflow; do not introduce a competing scheduler.
- [x] Generate from the real public bundle, replay unchanged, alter one stored product in a disposable copy and prove rejection, then publish and independently read back the selected products. Public data commit `b29c62d` and receipt commit `6551ae7` contain two observed products; all 46 artifact files and Git subtree bindings verified. Qualified semantic JSON and HTML match independent local generation despite different runtime-specific receipt identities.
- [x] Publish and visually read back the heading-wrap repair discovered on `lov/1949-07-28-15` at 390px. History PR12/run `36179778132` appends three products; all 69 artifacts verified, corrected HTML matches the rendered previews and both earlier product trees remain unchanged. Latest publication commit: `90d4c83`.

**Initial concrete selection:** qualified candidates `lov/1845-06-07`, `lov/1949-07-28-15`, `forskrift/2022-09-02-1529`; retain the known mixed/complex documents as rejection evidence. This selection establishes integration, not completed corpus support.

**Done:** a fresh consumer retrieves the published receipt/raw evidence and reproduces the same selected semantic outputs. History #4/#5 closure must state the bounded grammar; D6 remains required.

## D5 — Complete the two-observation history delivery

**Outcome:** real successive observations produce stable, citable history without synthetic changes, rewrites or special cloud credentials.

**Files:** history observe workflow/script, `publication.py`, `ledger.py`, `materialize.py`, `docs/evidence/two-observation-delivery.json` (new).

- [x] Accept the next actual producer observation, including the new ordering-contract release if available; retain the first accepted directory unchanged. Public workflow `36178454989` accepts `ca32e6b7…` alongside retained `ccdbf3e4…`.
- [x] Reproduce both from public receipts. Report raw-source change, observation membership change and representation change separately. Local full-bundle acceptance and public product readback agree for the bounded selection; legal dates remain unresolved.
- [x] For unchanged qualified bodies, show no textual amendment while retaining the second observation time and provenance.
- [x] Interrupt publication at the product/receipt boundary in a disposable repository and recover without duplicates, overwrites or force pushes.
- [ ] Exercise fresh installation and ordinary-token execution. Distinguish a fresh checkout from a literal clean-fork run; do not claim the latter without executing it. If no authorized independent fork target is available, record that exact remaining acceptance dependency.
- [x] Independently clone/download the published result, verify old bytes and commit reachability, and regenerate the selected product offline. History runs `36187783649` and `36188237555` reproduce published samples `8633cba…` / `240d7ee…` from observations `ccdbf3e4…` / `ca32e6b7…` on Python 3.12.14. Networking is denied during fresh generation; target products are not copied; all 23 artifact bytes per product and five previous receipt hashes match. History evidence: `docs/evidence/offline-body-reproduction-public.json` and `offline-body-reproduction-second-public.json`. Literal clean-fork and next scheduled-cycle acceptance remain open.
- [ ] Close history #8 and the replacement-publication part of main #7 only after their actual acceptance is met.

**Done:** two real observations, durable publication, independent reproduction, stable previous identities and the required portability evidence are all recorded. This does not complete legal reconstruction.

## D6 — Expand faithful structure across the actual corpus

**Outcome:** readable products preserve the meaningful structure of the full selected corpus, rather than only three simple examples.

**Files:** main loader `models.py`, `parser.py`, `evidence.py`; publisher `formatter.py`, `per_law_pages.py`; history `structure.py`, `validation.py`; source-bound fixtures and `docs/evidence/structural-coverage.json` (new).

**Current implementation evidence:** explicit snapshot v5 retains every selected
ordered source body; default loader output remains v4. Full local parsing,
publisher validation and independent history validation passed for 756 laws,
5,118 regulations, 39,208 acts and 45,114 source members. All prior convenience
models match; strict UTF-8 decoding fixed a demonstrated runtime misclassification.
History PR14 merged as `0667744` before producer activation. The new renderer
supports declared links, notes and column-spanning tables, with exact source/model
reverse accounting and phone/keyboard table readback. Full qualification totals,
remaining grammar expansion and public delivery are still open.

- [ ] Inventory every actual structural form in current law/regulation bodies and representative amendment sources; produce per-document unsupported reasons rather than a single token coverage score.
  Current-body inventory completed for all 5,874 selected documents / 5,875 source occurrences. Links affect 5,448 documents; named sections 2,439; structured footnotes 1,084; tables 652. The 117 bound examples and exact attribute inventory inform D6 implementation; these are form counts, not qualification totals.
- [ ] Implement forms in real-population order: mixed containers and multiple paragraphs; nested ordered/unordered lists and markers; links/emphasis/superscripts; footnotes and references; tables and spans; appendices/attachments and remaining legal-bearing elements.
- [ ] For each form, specify its ordered events and exact normalization/exclusion rule, update parser/model/renderer together, and keep the independent source traversal independent.
- [ ] Preserve original source occurrences and language variants. A display choice must identify its selected occurrence; duplicate refids must not silently overwrite the archive.
- [ ] Reject missing/reordered/duplicated provisions and changed markers with a source location. Render and inspect representative real documents, including tables/footnotes and mobile overflow behavior.
- [ ] Run the whole-corpus inventory after each supported-form batch. Publish qualified/unqualified totals and exact residual reasons; never hide failures behind a percentage threshold.
- [ ] Version any changed representation and preserve prior published products. Reconcile changed text with source evidence before treating it as a legal amendment.

**Done:** corpus-wide accounting proves the declared projection and every remaining unsupported document is explicitly accounted for. A claim of full faithful coverage requires all meaningful forms in that population to be supported; a high pass rate is not sufficient.

**26 September coverage update:** public v5 product `48740f70` accounts for all 5,874 selections: 4,376 qualified and 1,498 rejected. Independent public retrieval preserves all 4,175 prior qualified HTML/CSS/body hashes and all 5,874 semantic identities. Exactly 201 existing documents become readable; this representation improvement is not a legal amendment. Exact offline v5 reproduction passed in run 36212841405. Complete v2/v3/v4 products and their receipts remain preserved. History PR19 records the public readback, reproduction and every remaining rejection. Main PR21 mirrors the published emphasis/table gate. Full structural coverage remains open. Diagnostic inspection of the earlier retained snapshot shows all 84 body/header rejection cases use the omitted `STV` prefix with matching document identifiers; current-source qualification is required before promoting that next support change.

## D7 — Preserve and interpret operation-level temporal evidence

**Outcome:** every amendment operation remains addressable, including unresolved targets, empty repeal text and scoped commencement uncertainty.

**Files:** history planned `operations.py`, `claims.py`; existing `validation.py`, `__main__.py`, `docs/CONTRACT.md`; new `tests/test_operations.py`, `tests/test_claims.py`; main timeline/feed date labels where necessary.

**Planned interfaces:**
```python
extract_operations(snapshot_root, observation_id) -> list[dict]
resolve_claims(operations, evidence_catalog, knowledge_cutoff) -> list[dict]
```

Operation records bind `source_occurrence_id` + `parsed_model_sha256` + zero-based `operation_ordinal`, source/model locations, original instruction/replacement/target strings, candidate target and resolution status. Binding the parsed revision prevents parser corrections/reordering from reusing a previous operation identity. Claim records bind operation/document scope, evidence IDs and locations, method/version, knowledge cutoff, legal start/end bounds and status `explicit|conditional|partial|conflicting|unresolved`. Corrections append a new claim with superseded IDs.

**Delivery status (26 September):** complete operation evidence is published and independently read back. Observation `be688fe8` carries 39,214 acts, 99,972 operations and 139,186 unresolved claims in public product `182c4b74`. The complete 102,605,176-byte artifact/index/source-catalog/record bindings were validated and the corrected amendment target retrieved. Earlier products remain preserved. Ordered replacement subtrees, operation scope and justified legal-time resolution remain unfinished; parsed-model completeness is not source-operation completeness. See history `docs/evidence/operations-public-readback.json` and `docs/evidence/corrected-history-operations-public.json`.

- [x] Read complete `parsed-amendment-acts.v1.jsonl`, retaining original order and every operation; reconcile to its raw occurrence and producer inventory. Complete public operation products, index/source bindings and real consumer retrieval were verified.
- [ ] Where the current parsed model flattened replacement text, extract the complete ordered replacement subtree from retained raw amendment XML and version that interface. An export that is complete relative to a lossy parsed model is not enough for legal replay.
- [ ] Preserve unresolved targets and empty replacement text. Classify replacement, insertion, repeal/removal, renumbering and move without silently coercing unknown instructions.
- [ ] Capture raw commencement expressions and separate act-wide from provision-specific rules. Preserve `Kongen bestemmer`, conditions, retroactivity, temporary effect and conflicting expressions explicitly.
- [ ] Register independently retrieved commencement orders/corrections as evidence; assign a legal bound only when the relevant operation scope is established.
- [x] Keep existing publication-date fallback outside the legal evidence path. PR17 published corrected date labels with direct public readback; history claims preserve unresolved legal dates.
- [x] Publish a versioned operation/claim export and CLI retrieval, with original evidence available beside interpretations. Original evidence and unresolved claims are public; later proposals remain legally ineligible.
- [ ] Independently inspect real repeal-with-empty-text, deferred-commencement and multiple-commencement cases; verify that later knowledge adds claims rather than rewriting earlier records.

**Done:** history #6's full operation/uncertainty interface is public and reproducible. This supplies inputs to reconstruction; it does not by itself prove a past state.

## D8 — Deliver evidence-backed historical-date reconstruction

**Outcome:** a date query returns a justified legal text where evidence supports it, with explicit partial/unavailable results and cited gaps elsewhere.

**Files:** history planned `baselines.py`, `reconstruct.py`, `queries.py`; `operations.py`, `claims.py`, `__main__.py`; new `docs/SOURCE-COVERAGE.md`, `tests/test_reconstruction.py`; versioned `baselines/**` and `reconstructions/**` products.

**Planned interface:**
```python
reconstruct(repository, refid, legal_date, knowledge_cutoff) -> dict
```
The result contains requested dates, baseline evidence, applied operation/claim IDs in order, unresolved operations, content identity and separate structural/legal coverage status. The future CLI is `law-history reconstruct REFID --legal-date YYYY-MM-DD --known-at TIMESTAMP`; document it as unavailable until implemented.

- [ ] Start source feasibility alongside D6/D7: inventory which enacted/prior consolidated texts, amendment acts and commencement decisions can actually be acquired for the target documents and periods.
- [ ] Acquire eligible primary evidence with hashes, origin, retrieval time and attribution. Do not promote recovered generated Markdown or the legacy synthetic graph into a baseline.
- [ ] Publish a coverage matrix by document and earliest justified state. Name missing source classes/access constraints concretely; do not invent a universal 2001 baseline.
- [ ] Validate each baseline's content and legal-date basis independently. Record unresolved boundaries and refuse extrapolation through gaps.
- [ ] Implement exact-target operations over the ordered model: whole provision, paragraph, sentence/item, heading, insert, remove/repeal, renumber and move. Require an unambiguous target and any stated old-text precondition; missing targets are failures, never silent no-ops.
- [ ] Apply only operations whose legal scope/time is established by evidence available at the requested knowledge cutoff. Handle same-day order, partial commencement, temporary provisions, corrections and conflicts explicitly.
- [ ] Preserve before/after evidence and applied-operation receipts. Do not backdate Git commits or use a reset-to-current-text operation to mask divergence.
- [ ] Compare reconstructed states with independent known states at several real checkpoints, including one law, one regulation, one removed document, scoped commencement and renumbering/repeal. Exercise before/on/after boundaries, retroactivity and separate knowledge cutoffs; prove no current-text or later-knowledge leakage. A scoped repeal must not delete the entire article. Identify exact unsupported intervals where a comparison cannot be justified.
- [ ] Publish the reconstruction query and coverage report. Expand operation/source support until the requested historical coverage is achieved; obtain a concrete user decision only if required source access or evidence is genuinely unavailable.

**Done:** supported queries reproduce independently evidenced historical text, and unsupported queries identify why they cannot. The overall historical-coverage objective remains open while required periods/documents lack evidence or supported operations.

## D9 — Integrate history into the public reader

**Outcome:** users can distinguish observed versions from legal-date reconstructions, compare them, cite them and recover missing information.

**Files:** main planned publisher `observed_history.py`; existing `per_law_pages.py`, `paragraph_history.py`, `historie_pages.py`, `quarto.py`, `not_found.py`; history `queries.py` and public indexes.

- [ ] Generate a compact public history index keyed by refid/source occurrence with pinned observation/product/claim identities and availability status.
- [ ] Add observed-version timelines and comparison to current document pages after D5; show observation dates and representation changes accurately.
- [ ] Add a legal-date selector after D8. Show source basis, applicable date, knowledge cutoff and completeness beside the answer.
- [ ] Link paragraph history to exact operations/evidence and qualified before/after content. Keep parsed records visible where a legal reconstruction is unavailable.
- [ ] Provide stable copyable citations and raw evidence downloads; preserve existing deep links and recovery routes.
- [ ] Give partial/unavailable results a useful explanation and source links; never silently substitute current text for a requested historical date.
- [ ] Keep legacy comparisons separately labelled and pinned, with no suggestion that their annual tag is a proven historical snapshot.
- [ ] Exercise the full current → observed history → legal date → comparison → source/citation journey on desktop, keyboard and a 390px viewport after deployment.

**Done:** observed history is usable from the reader and historical-date requests obey the reconstruction coverage contract publicly.

## D10 — Verify ongoing delivery, portability and supported integrations

**Outcome:** delivery continues without manual repair and users can consume the products reliably.

**Files:** existing workflows in both repositories, watcher example under main `examples/github-action-watcher/`, `SUBSCRIBE.md`, main GCS workflow/verification script, portable `docs/evidence/**`.

- [ ] Observe a subsequent scheduled source poll, changed/no-change processing decision, evidence release, site readback, acknowledgement and independent history intake. Record each state separately.
- [ ] Exercise failed/interrupted publication and missed-release catch-up using disposable local repositories/artifacts; never disrupt the working public site to manufacture a failure.
- [ ] Reproduce installation and retrieval from fresh Linux/Windows environments; preserve exact ledger/product bytes with checkout attributes.
- [ ] Run the watcher against a controlled sequence with a repeated record and a newly added record, proving no duplicate notification decision. Actual external messages require a user-designated destination; documentation alone is not an integrated service.
- [ ] Read representative feeds with an independent consumer. Record which external integrations have actually delivered and which remain instructions/examples.
- [ ] Audit existing GCS current/retained object policy and access using read-only identity-safe tooling; apply only concrete necessary corrections within existing authorization. Keep the core independent of the mirror.
- [ ] Remove stale counts, unsupported completeness promises and superseded handoff instructions from active documentation; retain dated evidence as dated evidence.
- [ ] Review every U01–U20 story against published evidence and update issue status. Preserve open gaps instead of treating a green run as product completion.

**Done:** a real subsequent daily cycle and consumer readback succeed, supported environments/integrations are demonstrated, and remaining source/coverage limitations are accurately tracked.

## Execution commands and evidence conventions

Use the existing checkouts and virtual environments. Never rely on an editable installation pointing at a different clone.

```powershell
# Main checkout: explicit current source packages.
$env:PYTHONPATH = 'lovdata-loader/src;lovdata-publisher/src'
& '..\venv\Scripts\python.exe' -m pytest lovdata-publisher/tests/test_container_order.py -q

# History checkout: actual command-line entry point.
python -m law_history --repository '..\implementation-evidence\public-v4-consumer\ledger' list
python -m law_history --repository '..\implementation-evidence\public-v4-consumer\ledger' show lov/1998-07-17-56
python -m law_history --repository '..\implementation-evidence\public-v4-consumer\ledger' materialize --observation ccdbf3e45098076118bf9362b60d31b7a80dc1aab1dcc2e226a4aee58c92b596
python -m unittest discover -s tests -v
```

The history commands above use the retained independent-consumer ledger and its real public observation. Run materialization only after finishing D4's local implementation; use a fresh scratch ledger for independent reproduction. New reconstruction/claim commands are planned interfaces and must not be reported as existing before implementation. Use focused regression cases for changed behavior and required CI; broaden only for an unresolved risk or failure.

Each published delivery receipt records actual identities and results, for example the already verified current-corpus delivery:
```json
{
  "story_ids": ["U01"],
  "repository": "sondreskarsten/norwegian-laws",
  "source_commit": "2d90a466a8ca3954494f82041409b39242c5c1f5",
  "observation_ids": ["ccdbf3e45098076118bf9362b60d31b7a80dc1aab1dcc2e226a4aee58c92b596"],
  "published_product_identity": "observation-ccdbf3e45098076118bf9362b60d31b7a80dc1aab1dcc2e226a4aee58c92b596",
  "consumer_checks": ["Public catalog identities match the production source snapshot"],
  "coverage": "756 laws and 5118 regulations; exact catalog membership",
  "limitations": ["Whole-corpus rendered-body fidelity and subsequent daily operation remain unverified"]
}
```
New deliveries must supply their own newly verified identities, outcomes and limits rather than copying this example.

## Tracking and completion audit

- [x] User chose continued execution in this task; cloud handoff removed.
- [x] Current code/file boundaries and issue inventory inspected for this plan.
- [x] Existing published work separated from local unfinished changes.
- [x] D1 current deployment completed and publicly read back.
- [ ] D2 reader/monitoring journeys complete.
- [ ] D3 removed-document archive and future exits delivered.
- [x] D4 qualified observed products published, including the mobile title repair; bounded three-document qualification only.
- [ ] D5 two-observation and independent reproduction delivered.
- [ ] D6 actual-corpus structural requirements satisfied.
- [ ] D7 operation/temporal interface delivered.
- [ ] D8 requested legal reconstruction and evidence coverage achieved.
- [ ] D9 history reader experience delivered.
- [ ] D10 continuing operation and supported integrations verified.

No elapsed-time estimate substitutes for acceptance. The final audit must trace every story and issue requirement to current published evidence. A finished pilot, test suite, manifest or plan does not complete the full product.

