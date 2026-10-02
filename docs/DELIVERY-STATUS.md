# Delivery status

Updated 26 September 2026. This document supersedes earlier status summaries; dated evidence files retain the results of their own runs. Work stays in `github.com/sondreskarsten` on `fix/reliable-laws-delivery` and `fix/reliable-history-delivery`. Preserve generated branches, historical references and immutable publications. No cloud handoff or DNB migration is part of delivery.

Implementation stopped at the user's request. See [WIND-DOWN.md](WIND-DOWN.md) for the complete unfinished-work record and recoverable code archive. Active runtime remains the merged v10 code.

## Product position

The current reader and source-data delivery work. Observed history preserves and retrieves exact source versions. Reliable legal-date reconstruction is unfinished: an observed version is not proof of what legally applied on that date.

| Plan step | Delivered evidence | Remaining work |
|---|---|---|
| 1. Close v6 | Public reader receipt and acknowledgement agree at `78f4f540c6011ea8ebe99c7de47f3caf0708a6db`; seven history products, nine representative v6 documents, source downloads and Constitution comparison read back. Independent offline regeneration reproduced exact product `9f7f2209f9bc03b0bf986f5129b3d4fbbaf2d1c261fed82e5c6fd2854274d602`. | None for v6 acceptance; do not rerun completed jobs. |
| 2. Source boundary | Accepted-source inventory covers 40,822 identities, including duplicate occurrences and 5,875 current/prior-current identities. Supplemental older-source bundle publicly retained and independently verified. | Qualify original baselines; acquire/segment remaining obtainable primary sources; link originals, amendments, commencement, corrections and repeal evidence to document intervals. Availability counts are not legal coverage. |
| 3. Structures | Published v10 product `e80c877f2bf3e35703ed702d6ba5ce9d5d5c810c1233f56e24e90670c5c31ce2` has 5,443 qualified bodies and 431 explicit rejections. Independent offline regeneration reproduced its exact identity. Earlier qualified HTML/CSS payloads were preserved across the grouped changes. | Public reader v10 deployment acceptance; 431 remaining v10 structural rejections including images, formulas, tables and other source forms. Implementable structures remain defects/work, not completed limitations. |
| 4. Ordered operations | Merged interface `ordered-operations` retains complete raw trees, exact source paths, all parsed operations, unmatched blocks and zero-operation acts. | Resolve replacement/insertion/repeal/renumber/move scope, prove coverage against raw acts, and qualify complete replacement structures. Adjacency is only candidate evidence. |
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
- Reader publication [36233063699](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36233063699) succeeded, including acknowledgement. Independent readback matched public receipt and acknowledgement at `10780c51747514e4e981b6e793569d250f7c67f9`, eight history products, ten sample bodies/source pointers and unchanged Constitution comparison. Browser citation copy was read from the actual clipboard. See `docs/evidence/observed-reader-v7-public.json`.
- Independent v7 regeneration [36234686740](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36234686740) succeeded: exact published product reproduced with the pinned generator/runtime and networking denied during regeneration. See `docs/evidence/body-reproduction-public-v7.json`; do not rerun it.
- Earlier publication attempts stopped safely when their branch moved. Hold further merges until the active writer finishes; do not rerun failed stale checkouts blindly.
- A literal fork cannot be established under the same authenticated owner: GitHub returned the original repository with `fork:false`, and no eligible organization is available. A different eligible account or explicitly approved organization is a concrete prerequisite. Fresh clone/install is verified separately.
- The optional GCS current-object mirror was previously checked against 11,510 objects. Read-only audit 36236278859 verified 11,510 live generations, no noncurrent generations and 368,697 soft-deleted generations. Bucket configuration and IAM reads returned HTTP 403, so retention/lifecycle/access settings remain unverified; the workflow needs bucket-metadata and IAM read permission. No settings were changed. See `docs/evidence/gcs-configuration-audit-20260926.json`. Inherited project IAM and effective object access are outside that evidence.
- The producer's daily source poll is scheduled for 02:00 UTC. Same-day manual or push-triggered runs do not prove a genuine subsequent scheduled cycle.

All 943 distinct image URLs referenced by the retained current-body inventory have now been acquired as complete files (1,141 source uses, 99,978,844 bytes) and published through the existing producer evidence path. Independent public download verified the manifest and all members; see `docs/evidence/image-acquisition-public.json`. Reader integration and structural qualification remain separate work. Image retrieval clocks are later than the XML observation and must not be backdated. Formulas remain exact TeX evidence; a local pinned offline MathML adapter renders 350 of 355 retained formulas, with five explicit parser gaps. It is not yet integrated into body qualification.

## Issues and next actions

Reader issues #3–#7 and history #4, #5, #6 and #8 remain open. Reader #8–#10 and history #1, #3 and #7 were closed with earlier delivery evidence. Do not close semantic history requirements because a structural product or workflow passes.

The primary-source, ordered-evidence, watcher and v8/v9/v10 changes are merged (reader PR #26; history PR #25). History run 36236255332 published v10 product `e80c877f2bf3e35703ed702d6ba5ce9d5d5c810c1233f56e24e90670c5c31ce2` with 5,443 qualified bodies and 431 rejections. Independent reproduction 36237465923 succeeded with exact identity and offline regeneration; see `docs/evidence/body-reproduction-public-v10.json`. Reader publication 36236279051 remains in progress at wind-down; no rerun was started. Further implementation is stopped. Unmerged runtime changes were verified into the history unfinished-work archive and removed from active code. Outstanding requirements are recorded in WIND-DOWN.md; no completion claims or semantic issue closures were made for them.
