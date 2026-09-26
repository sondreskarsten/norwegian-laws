# Norwegian laws: delivery backlog

Updated **2026-09-26** from source, workflow, live-source and browser audits.
The active [full product completion plan](docs/superpowers/plans/2026-09-25-norwegian-laws-product-completion.md)
maps 20 user stories to ten delivery packages, including historical-date reconstruction.
**Work is resumed under the [approved delivery plan](docs/superpowers/plans/2026-09-26-fastest-delivery.md). Cloud setup and handoff are out of scope.**
Use this backlog for delivery evidence and the plan for execution order; a bounded
observation pilot does not complete the whole historical product.

## Current delivery position

**Work resumed on 26 September 2026.** Read
[Delivery status and remaining work](docs/DELIVERY-STATUS.md) first. It supersedes
older status/counts in this backlog and names the running publications, delivered
features, exact remaining coverage and restart checks. The complete scope and
acceptance remain in the product plan; historical-date reconstruction is unfinished.

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
