# Delivery status

Updated 26 September 2026. This document supersedes earlier status summaries; dated evidence files retain the results of their own runs. Work stays in `github.com/sondreskarsten` on `fix/reliable-laws-delivery` and `fix/reliable-history-delivery`. Preserve generated branches, historical references and immutable publications. No cloud handoff or DNB migration is part of delivery.

## Product position

The current reader and source-data delivery work. Observed history preserves and retrieves exact source versions. Reliable legal-date reconstruction is unfinished: an observed version is not proof of what legally applied on that date.

| Plan step | Delivered evidence | Remaining work |
|---|---|---|
| 1. Close v6 | Public reader receipt and acknowledgement agree at `78f4f540c6011ea8ebe99c7de47f3caf0708a6db`; seven history products, nine representative v6 documents, source downloads and Constitution comparison read back. Independent offline regeneration reproduced exact product `9f7f2209f9bc03b0bf986f5129b3d4fbbaf2d1c261fed82e5c6fd2854274d602`. | None for v6 acceptance; do not rerun completed jobs. |
| 2. Source boundary | Accepted-source inventory covers 40,822 identities, including duplicate occurrences and 5,875 current/prior-current identities. Supplemental older-source bundle publicly retained and independently verified. | Qualify original baselines; acquire/segment remaining obtainable primary sources; link originals, amendments, commencement, corrections and repeal evidence to document intervals. Availability counts are not legal coverage. |
| 3. Structures | Published v7 product `044f1fc7ac178149dc0a0a022e48dfd26ca579e5db845b56c271c4ac436ec8f5` has 5,247 qualified bodies and 627 explicit rejections. v8 supports 5,351 locally, with all 104 additions checked against raw XML and all 5,247 prior payloads unchanged. | v7 reader deployment/regeneration acceptance; v8 release; 523 remaining v8 structural rejections including images, formulas, tables and other source forms. Implementable structures remain defects/work, not completed limitations. |
| 4. Ordered operations | Branch interface `ordered-operations` retains complete raw trees, exact source paths, all parsed operations, unmatched blocks and zero-operation acts. | Publish integration; resolve replacement/insertion/repeal/renumber/move scope, prove coverage against raw acts, and qualify complete replacement structures. Adjacency is only candidate evidence. |
| 5. Legal timing/replay | Evidence clocks, source identities and unresolved temporal proposals are preserved. | Register eligible interpretation methods; establish baseline and commencement evidence; implement deterministic operations/preconditions, conflict handling, expiry and before/after receipts. `reconstruct` is not delivered. |
| 6. Reader legal history | Observed-version selection, comparison, sources and citations work; legacy comparisons remain labelled unverified. | Legal-date/knowledge-cutoff answers, shared coverage, operation-linked paragraph histories and supported reconstructed before/after states. |
| 7. Operations | Public clipboard/feed readback, constrained-network search, fresh Windows installation and Linux CI installation; watcher repeated/new/interrupted-state replay. | Live watcher issue delivery, literal clean fork with eligible destination account, genuine subsequent scheduled cycle, recovery/catch-up acceptance and optional GCS configuration audit. |
| 8. Reconciliation | Existing branches reused and reviewed batches pushed; delivery evidence retained. | Complete remaining requirements before closing issues or claiming final completion; merge pending reviewed changes after active publication. |

## Reader acceptance

The selected current corpus contains 756 laws and 5,118 regulations. Metadata/full-text search, representative source order, paragraph links, topic/ministry navigation, amendment activity, observed-version comparison, source downloads and mobile journeys have public readback evidence. These representative journeys do not prove all corpus structures.

The public archive retains 106 prior reader documents, including a natural current-corpus exit. Earlier Markdown copies have provenance but are not qualified historical baselines. The real regulation `2022-12-21-2456` has six retained current-corpus observations followed by three comparable absences; disappearance does not establish repeal or legal validity.

Subscription clipboard access returned the exact Regnskapsloven feed URL, and its public feed yielded 50 distinct records. The constrained-network record uses an aggregate 1 Mbit/s proxy with 150 ms added per request; title and full-text queries produced readable results with loading feedback. Timings are recorded upper bounds, not broad performance benchmarks. Evidence is in the reader repository's `docs/evidence/subscription-clipboard-public.json` and `search-constrained-network.json`.

The retained GitHub watcher now uses durable issue markers to recover after issue creation followed by failed state persistence. Replay covers unchanged records, one added record, and closed-issue lookup across pages. Live issue creation with a user's token is not claimed. Slack/Teams setup and delivery claims are excluded from active scope; repository feeds and the GitHub watcher remain.

## Primary evidence and historical limitations

Of 5,875 current/prior-current identities, 4,284 have matching retained Lovtidend candidates and 1,591 do not. This is an availability inventory, not a qualification of original enactment text or a complete amendment chain. Seventeen identities are represented only by prior generated reader copies in the inventory.

The [public older-source acquisition](https://github.com/sondreskarsten/norwegian-laws/releases/tag/primary-source-066a4a3e8cfc83754c9295875841d010d550ff3978f60e9746fdcfe8cc0bb0c5) preserves 20 acquired files plus a manifest, including failed attempts. A fresh Windows installation independently downloaded and verified the public receipt and bundle. The discovered source indexes contain 200 volume links through UiO and 49 government PDF links. Whole-volume acquisition, segmentation, source qualification and registration into legal coverage remain implementation work. Missing index links do not prove missing holdings. A real 1983 header/commencement-order date conflict remains unresolved.

`source-coverage --known-at` excludes later accepted observations and generated archive copies without known evidence clocks. `verify-primary` verifies acquired bytes; `ordered-operations` preserves source structure. Neither interface establishes legal eligibility. Never substitute today's text or use publication, disappearance or Git dates as legal dates.

## Active release and external prerequisites

- v7 history intake [36233058951](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36233058951) succeeded, including remote publication readback at `9f93e0fbb15d0202d31564b3aefcb4404ff075e5`. See `docs/evidence/body-publication-v7.json`.
- Reader publication [36233063699](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36233063699) has completed acquisition and evidence publication; website deployment remains in progress at this update.
- Independent v7 regeneration [36234686740](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36234686740) is running with pinned generator/runtime and networking denied during regeneration. Do not duplicate it.
- Earlier publication attempts stopped safely when their branch moved. Hold further merges until the active writer finishes; do not rerun failed stale checkouts blindly.
- A literal fork cannot be established under the same authenticated owner: GitHub returned the original repository with `fork:false`, and no eligible organization is available. A different eligible account or explicitly approved organization is a concrete prerequisite. Fresh clone/install is verified separately.
- The optional GCS current-object mirror was previously checked against 11,510 objects. A read-only retention/versioning/lifecycle/bucket-IAM audit is prepared but not run. Its results will not establish inherited project IAM or all effective object access.
- The producer's daily source poll is scheduled for 02:00 UTC. Same-day manual or push-triggered runs do not prove a genuine subsequent scheduled cycle.

## Issues and next actions

Reader issues #3–#7 and history #4, #5, #6 and #8 remain open. Reader #8–#10 and history #1, #3 and #7 were closed with earlier delivery evidence. Do not close semantic history requirements because a structural product or workflow passes.

Finish current publication/readback first. Then merge the reviewed primary-source, ordered-evidence, watcher and v8 batch; publish and independently read the resulting product once. Continue grouped table/assets/formula support and source qualification, followed by eligible reconstruction and the legal-date reader. Complete operational acceptance and map each issue to published evidence before final closure.
