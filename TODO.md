# Norwegian laws: delivery backlog

Updated **2026-09-25** from source, workflow, live-source and browser audits.
The active [full product completion plan](docs/superpowers/plans/2026-09-25-norwegian-laws-product-completion.md)
maps 20 user stories to ten delivery packages, including historical-date reconstruction.
**All work continues in the existing task; cloud setup and handoff are removed from scope.**
Use this backlog for delivery evidence and the plan for execution order; a bounded
observation pilot does not complete the whole historical product.

## Current delivery position

The verified public reader through [PR #17](https://github.com/sondreskarsten/norwegian-laws/pull/17)
uses source `8ccd1da470df26f8d7532583241cbf80a894c3ea`. Its archive exposes all 105
known prior copies with pinned provenance and download links. Representative
downloads match their recorded bytes; archive, recovery, paragraph history,
timeline and activity pages fit 390px. Publication dates are separate from raw
commencement clauses, and parsed coverage gaps remain explicit. The public
receipt and acknowledgement agree; see [PR17 evidence](docs/evidence/reader-pr17-public.json).
[PR16 evidence](docs/evidence/reader-pr16-public.json) retains the earlier recovery readback.
PR #15's subscription availability, compact lookup, exported counts and crosslinks
were independently read back at its earlier source `9285be5`.
All five PR #14 container-order repairs were compared with their source; the
patent appendix also passed visual readback. The older run receipts below remain
historical evidence, not the current source identity.

History now retains **three real observations** and five immutable qualified-body
products. [History PR #11](https://github.com/sondreskarsten/norwegian-laws-history/pull/11)
published the first two products and all **105 prior reader copies**;
[PR #12](https://github.com/sondreskarsten/norwegian-laws-history/pull/12) published
the mobile heading repair while preserving previous products. All 69 new product
artifacts were read back. History #7 is closed. Two published sample products were
independently regenerated offline on pinned Python 3.12.14, with all 23 files per
product identical and five previous receipts unchanged. Literal clean-fork
acceptance remains in #8. Qualified bodies still cover
only three simple documents; full structure and legal-date reconstruction remain open.

The next source-body delivery has passed a complete local v5 rehearsal and
independent consumer validation: all 5,874 selected bodies match retained XML,
while all 39,208 amendment models and existing conventional reader models match
the previous publication. A strict UTF-8 repair prevents an observed decoder
misclassification from corrupting Norwegian characters. History PR #14 is merged
and accepts the new contract. Producer activation and richer body publication
still require public readback. Full-text result links now target the matched
passage in supporting browsers; the actual late Regnskapsloven passage was
verified locally at phone width. See the local reports in `docs/evidence/`.

PR #17 deployed future-exit capture after controlled Git publication, replay and
re-entry checks. This production run contained zero new exits, so it does not
establish a naturally occurring exit readback. Chrome locally blocked one raw
regulation download; independent HTTP retrieval returned its exact recorded bytes.
Topic, ministry and activity membership/count audits passed against the public
catalog and export. The next scheduled daily cycle and external notification
delivery have not been established.

**Current publishing repair is live and read back.**
[Delivery run 36159622728](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36159622728)
published source commit `8020b8f610171108d7f82c2f3811688a4605b918` on September 25.
The public catalog matches all 756 law and 5,118 regulation identities in the
fresh source and production snapshot. The missing regulation serves its source
text; the obsolete current entry returns 404. The public receipt matches the
committed acknowledgement. Daily operation still needs a subsequent observation.

[PR #12](https://github.com/sondreskarsten/norwegian-laws/pull/12) is live through
[run 36162836802](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36162836802),
source `27df76fb664c71a2e1dd5e2764305185c4683dfe`. Its public receipt and committed
acknowledgement agree. Ordered Regnskapsloven paragraphs, regulation amendment
exports, feeds, 404 recovery and mobile comparison were read from the deployed
site. PR #13 subsequently delivered source evidence, optional full-text search
and per-law legacy-version headers through
[run 36167592215](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36167592215),
source `2d90a466a8ca3954494f82041409b39242c5c1f5`. Public site/release receipts,
catalog membership, live browser search and exact XML retrieval agree.

Keep the existing personal repositories:
[norwegian-laws](https://github.com/sondreskarsten/norwegian-laws) for current
publication and [norwegian-laws-history](https://github.com/sondreskarsten/norwegian-laws-history)
for the new history product. Preserve the generated `gh-pages`, `law-history`
branches and existing tags. Automatic legacy-history regeneration is gated by
`ENABLE_LEGACY_HISTORY == 'true'`; leave it disabled during migration. The manual
legacy workflow is retired to an explanation-only run with read permission;
it no longer rebuilds or pushes historical branches or tags.

## 1. Finish current-data delivery

Delivered: live-manifest archive selection, source identity and SHA256 cache
checks, atomic downloads, a processed source receipt, snapshot validation,
and publication acknowledgement after public-site readback.

- [x] Run the complete fresh-source pipeline and reconcile **document identities**
  through source, snapshot, generated corpus and the public catalog. The audit found
  `forskrift/2026-09-18-1871` missing and `forskrift/2019-11-22-1547` retained even
  though both regulation sets counted 5,118. Handle the duplicate Constitution
  source explicitly; the snapshot records one last-occurrence-wins duplicate.
- [x] Publish the exact processed source receipt and pinned source commit;
  advance published state only after the public site serves that identity.
  Polling now compares against published acknowledgement, preserving retries
  when publication fails with unchanged upstream input.
- [x] Read the new regulation and receipt from the live site and confirm that
  the removed current entry is absent. Snapshot counts and hashes were also
  checked from the actual downloaded production artifact.
- [x] Publish durable snapshot membership/integrity metadata and retained raw
  evidence for independent consumers. The first
  [observation release](https://github.com/sondreskarsten/norwegian-laws/releases/tag/observation-ccdbf3e45098076118bf9362b60d31b7a80dc1aab1dcc2e226a4aee58c92b596)
  binds source `2d90a466a8ca3954494f82041409b39242c5c1f5` to a 191,396,694-byte
  bundle, publicly read back by SHA-256. The history workflow independently
  accepted all 45,114 source members. GitHub administrators can still delete
  assets; this is content-addressed publication, not physical WORM storage.
- [x] Read the global and per-law feeds and both compressed display exports from
  the live site against the production snapshot: 100 global feed entries, 50
  Regnskapsloven entries, 39,208 act rows and 99,102 eligible amendment rows,
  including 72,538 regulation targets. Display filtering/truncation is preserved.
- [ ] Verify the next daily update before describing ongoing delivery as complete.
- [x] Keep cloud mirroring optional and publish clean output. Run
  [36167592293](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36167592293)
  verified exactly 11,510 current objects and independently read the receipt,
  catalog, one law and one regulation with matching hashes/lengths. No current
  runtime credential artifacts remain; earlier cleanup was confirmed in logs.
- [ ] Audit retained GCS object versions and IAM separately if the optional mirror
  remains in use. Current-object readback does not establish those properties.

## 2. Complete the shared data interface

- [x] Preserve mixed text/list order within legal paragraphs and resolve structured
  regulation amendment targets. The live Regnskapsloven §6-2 now follows source
  order; regulation targets appear in the public export.
- [x] Publish the container-order repair and read the five confirmed examples
  from the live reader. PR #14 run 36171176807 published source
  `7971606f7683612779e17cea1ef53d8531ba0fa3`; public source/model/HTML order and
  receipt/acknowledgement agree. See [live evidence](docs/evidence/live-container-order-readback.json).
  Whole-document structural fidelity still needs its separate gate. The readback
  exposed a separate heading cross-link defect; its local repair and browser
  evidence are in [the reader follow-up](docs/evidence/crosslink-heading-local.json).
- [ ] Finish a versioned producer/consumer contract: ordered content, source and
  output identities, parser/formatter versions, exact membership and explicit
  unresolved content. Verify deterministic replay through independently installed
  packages. The publisher already declares its loader dependency; fresh isolated
  local installation/replay passed, while the latest public contract still needs
  its final independent readback.
- [ ] Preserve the existing JSONL display API with documented limits, and provide
  a versioned lossless amendment interface for history. Current export drops
  unknown targets and truncates instructions/replacement text; it is not a
  canonical reconstruction input.

## 3. Deliver evidence-backed history

The history repository now contains an independent observation consumer and
default-token catch-up workflow in [history PR #2](https://github.com/sondreskarsten/norwegian-laws-history/pull/2),
merged as `810d60b4174fe3feda7bea37ad4310b237cd404e`. The reuse audit is complete.
[First real intake](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36169832648)
accepted public evidence and committed the ledger as
`611153d93419437ba74a07ab07ce5067afabbbef`. Fresh independent exact-XML retrieval
and idempotent production replay passed; history #3 is closed. Three real
observations and immutable bounded products are now published; portability
acceptance and full corpus support remain separate delivery gates. The
legacy builder's synthetic baseline and guessed legal dates are not imported.

| Open issue | Remaining deliverable and acceptance evidence |
|---|---|
| [history #8: observed pilot](https://github.com/sondreskarsten/norwegian-laws-history/issues/8) | Real observations and bounded derived products are published using the ordinary repository token. Two published sample products reproduce exactly offline on the pinned runtime. Complete literal clean-fork acceptance and the next scheduled cycle. |
| [history #4: structural gate](https://github.com/sondreskarsten/norwegian-laws-history/issues/4), [#5: canonical format](https://github.com/sondreskarsten/norwegian-laws-history/issues/5), [#6: temporal claims](https://github.com/sondreskarsten/norwegian-laws-history/issues/6) | Expand the narrow structural grammar using the complete 5,874-document form inventory; publish operation evidence and scoped temporal claims. Materialization/publication mechanics are delivered in closed #7, with unsupported documents rejected explicitly. |
| [#3: orphan v2000](https://github.com/sondreskarsten/norwegian-laws/issues/3) | Replace the hardcoded version range with an explicit supported-version catalog. Stop presenting the disconnected v2000 graph as a verified version; retain existing refs until an explicit migration decision. |
| [#4: future-year ordering](https://github.com/sondreskarsten/norwegian-laws/issues/4) | Prevent future or unsupported years from appearing as completed historical snapshots. Verify the order and provenance of selectable checkpoints; the audit confirmed v2028 was behind v2026. |
| [#5: inaccurate point-in-time claims](https://github.com/sondreskarsten/norwegian-laws/issues/5) | Correct version-page, diff and Git examples to describe the actual evidence and limitations. Display source basis, knowledge cutoff, legal-date certainty and reconstruction status for each supported result. |
| [#6: missing repealed documents](https://github.com/sondreskarsten/norwegian-laws/issues/6) | Retain terminal texts and source evidence for documents leaving the current corpus. Record observed exit separately from proven legal repeal; preserve unknown legal dates. Verify retrieval of a repealed example and provide recovery links for unavailable periods. |
| [#7: unstable history publication](https://github.com/sondreskarsten/norwegian-laws/issues/7) | Publish stable, citable identities with idempotent updates, explicit correction/version policy and checked remote/LFS readback. Preserve legacy references during consumer migration. Force rebuilding is confirmed; the claim that every SHA changes every day was not supported by the September 25 run. |

## 4. Finish the reader experience

- [x] [#8: search payload](https://github.com/sondreskarsten/norwegian-laws/issues/8)
  — the live default index is 1,735,672 decoded bytes / 292,915 gzip response
  bytes; the dedicated metadata catalog is 1,378,178 / 273,059 bytes. Title
  search loads no Pagefind assets. Explicit full-text search finds the late
  Regnskapsloven passage and opens its law; the page stays within 390px width.
  Browser and independent HTTP readback passed. No throttled-network timing
  claim is made.
- [x] [#9: missing/repealed-page recovery](https://github.com/sondreskarsten/norwegian-laws/issues/9)
  — deploy a project 404 page with search, history and source links. Verify both
  an unknown URL and `lover/lov-1981-05-29-38.html` recover usefully.
- [x] [#10: mobile comparison](https://github.com/sondreskarsten/norwegian-laws/issues/10)
  — wrap controls and contain diff scrolling. Verify the page at 390px width,
  and clear the previous result when equal or otherwise invalid versions are
  selected. Retest search, reading, crosslinks and paragraph deep links after
  deployment.

Close each item with its source/build identity, deployed receipt and relevant
consumer readback. Keep local implementation, publication and verified daily
operation as separate states.
