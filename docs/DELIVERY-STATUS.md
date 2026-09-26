# Delivery status and remaining work

Work resumed under the user-approved completion plan on **26 September 2026**. This is the restart point; older dated reports remain evidence of their own runs. Both repositories remain in `github.com/sondreskarsten`. Reuse `fix/reliable-laws-delivery` and `fix/reliable-history-delivery`; preserve generated branches, historical tags and immutable evidence. No cloud handoff or DNB migration is required.

## Working and delivered

- Current reader: 756 laws and 5,118 regulations; metadata and full-text search, corrected ordering, paragraph links, subscription availability, representative topic/ministry journeys and amendment activity are publicly verified.
- Public observed-history reader: version selection, changed/unchanged comparison, unsupported/unknown selection handling, pinned source downloads and mobile layouts are verified. Latest reader receipt/acknowledgement readback is source `78f4f540c6011ea8ebe99c7de47f3caf0708a6db` (main PR22). Seven products and nine newly qualified v6 examples were read back, with an unchanged Constitution comparison.
- Exact source evidence, immutable observations and raw XML retrieval work. Nine accepted observations were inspected in the current ledger.
- History v6 product `9f7f2209f9bc03b0bf986f5129b3d4fbbaf2d1c261fed82e5c6fd2854274d602` is published: **4,938 qualified bodies / 936 explicitly unsupported / 5,874 selections**. Independently downloaded artifact hashes match; all 4,376 prior qualified bodies retain identical HTML/CSS/body identities and all 5,874 semantic identities are unchanged. The 562 additions are representation support, not legal amendments. The independently exported reader data contains seven products and 5,875 retained document identities; this local export does not establish refreshed website deployment. [Public v6 readback](https://github.com/sondreskarsten/norwegian-laws-history/blob/main/docs/evidence/observed-body-v6-public.json) and [all remaining rejections](https://github.com/sondreskarsten/norwegian-laws-history/blob/main/docs/evidence/observed-body-v6-rejections.json) are retained in the history repository.
- History PR21 is merged at `9502fc06fc04353d6d006377055fbd9219b1db0a`. `show REFID --role laws|forskrifter|amendment_acts` distinguishes a current-corpus exit from a retained amendment source. The real regulation `2022-12-21-2456` has six current-corpus observations followed by three comparable absences; legal validity remains unresolved. Review, focused verification and post-merge CI pass.
- The public reader archive contains 106 retained documents, including the first natural exit. Earlier recovered Markdown copies have provenance but are not historical legal baselines.
- Complete parsed operation evidence is published. Verified product `182c4b74...` contains 39,214 acts, 99,972 operations and 139,186 unresolved claims. Display downloads contain 99,110 eligible rows; display exports are not reconstruction inputs.

## Publications/checks already running at pause

Do not restart these merely because work resumes. Inspect their final state and outputs first.

| Run | Purpose | State at last check |
|---|---|---|
| [Main 36222112299](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36222112299) | Deploy main PR22 metadata/typography support and refresh observed-history inputs | Successful; public v6 index, nine new bodies, comparison and acknowledgement read back. |
| [History 36222100288](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36222100288) | Generate and publish v6 bodies | Successful; artifact readback completed. |
| [History 36222784579](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36222784579) | Independently regenerate exact v6 product with networking denied during generation | Successful; exact v6 product reproduced with networking denied and no target copy. Report retained in history evidence. |
| [History 36222773638](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36222773638) | Post-PR21 observation intake | Successful. |

The refreshed v6 reader is now verified. No legal-date functionality is claimed by the running jobs. Existing daily workflows remain enabled; no new automation was created.

## Remaining delivery, in order

Release acceptance is now complete. Follow [the resumed execution plan](https://github.com/sondreskarsten/norwegian-laws/blob/main/docs/superpowers/plans/2026-09-26-fastest-delivery.md) and [the source-availability report](https://github.com/sondreskarsten/norwegian-laws-history/blob/main/docs/SOURCE-COVERAGE.md); its inventory is not yet qualified historical coverage.

1. **Completed: release acceptance.** Public v6 reader receipt, acknowledgement, representative new bodies and comparison agree. Independent v6 regeneration reproduced the exact product. No rerun is needed.
2. **Complete structural coverage (D6).** The 936 rejected documents have explicit reasons. Largest first-rejection groups: `margin-top` attributes (130), `data-text-size` (95), margin-ID articles (85), miscellaneous headings (76), unsupported list markers (69), images (55), table captions (43), plain spans (39), rules-assistance attributes (38) and indent containers (38). More structures may appear after each first rejection is addressed. Support requires source/model/render agreement and readable output; never silently drop unsupported content.
3. **Finish operation and temporal evidence (D7).** Preserve complete ordered replacement subtrees from raw amendment XML, exact instruction/target locations and operation scope. Classify replacement/insertion/repeal/renumber/move without coercing unknown cases. Establish act-wide versus provision-specific commencement, deferred decisions, conditions, retroactivity, expiry and conflicts. Later claims must append, not overwrite source evidence. Parsed-model completeness is not source-operation completeness. Issue history #6 remains open and has been updated.
4. **Build justified historical reconstruction (D8).** Acquire and qualify enacted/prior baselines and commencement evidence; publish coverage by document/time. Implement exact-target replay with preconditions and receipts, then compare with independent known states. The local whole-article prototype is legally ineligible: complete amendment coverage and conditional expiry remain unresolved. Reliable arbitrary-date legal text is **not delivered**.
5. **Finish history reader integration (D9).** Add legal-date and knowledge-cutoff queries only after D8, with partial/unavailable results and source basis. Connect paragraph histories to exact operation evidence. Stable citation links work; OS clipboard readback remains inconclusive.
6. **Finish continuing operation and portability (D2/D5/D10).** Verify a subsequent scheduled daily cycle, literal clean-fork operation, controlled slow-network search, notification deduplication and actual supported integrations. Slack/Teams integrations and claims are excluded by the approved scope. Audit optional GCS retention/IAM; current-object checks do not establish retention/access correctness.

## Issue and restart discipline

Main #3–#7 remain open; #8–#10 were closed with evidence. History #4, #5, #6 and #8 remain open; #1, #3 and #7 were closed with evidence. Do not close remaining issues merely because a workflow is green.

Start with read-only status/issue/run checks and `git status`. Fetch and normally merge current `origin/main` into the existing implementation branches; preserve any new work. Do not force-push, recreate the repositories, regenerate the legacy yearly graph or substitute current text for an unsupported past date. No implementation batch is left waiting for manual publication authority; the unfinished work is the scope above.


## Presentation batch v7 — local acceptance, publication pending

The retained 5,874-document corpus now renders and reverses 5,247 bodies under `observed-body-source-presentation-v7`; 309 are newly supported. All 4,938 previously supported HTML and stylesheet payloads are byte-identical. Nine retained raw XML fixtures qualify source-to-model-to-render across margin labels, miscellaneous headings, indentation, captions, language spans, spacing, small text and assistance metadata. Browser inspection confirms margin headings and captioned tables. Remaining 627 first rejections are recorded in `docs/evidence/source-body-presentation-v7-local.json`. This is local representation acceptance, not a published v7 product or a legal-time qualification.
