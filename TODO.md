# Norwegian laws: delivery backlog

Updated **2026-09-25** from source, workflow, live-source and browser audits.
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
site. Per-law legacy-version headers need the next release's final cleanup.

Keep the existing personal repositories:
[norwegian-laws](https://github.com/sondreskarsten/norwegian-laws) for current
publication and [norwegian-laws-history](https://github.com/sondreskarsten/norwegian-laws-history)
for the new history product. Preserve the generated `gh-pages`, `law-history`
branches and existing tags. Automatic legacy-history regeneration is gated by
`ENABLE_LEGACY_HISTORY == 'true'`; leave it disabled during migration. Manual
legacy dispatch remains available.

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
- [ ] Publish durable snapshot membership/integrity metadata and immutable raw
  evidence for independent consumers; the current workflow artifact lasts seven days.
- [x] Read the global and per-law feeds and both compressed display exports from
  the live site against the production snapshot: 100 global feed entries, 50
  Regnskapsloven entries, 39,208 act rows and 99,102 eligible amendment rows,
  including 72,538 regulation targets. Display filtering/truncation is preserved.
- [ ] Verify the next daily update before describing ongoing delivery as complete.
- [ ] Keep cloud mirroring optional. Publish only clean output; investigate and
  remove previously replicated `gha-creds-*.json` artifacts as authorized, then
  verify destination contents and access independently of upload logs.

## 2. Complete the shared data interface

- [x] Preserve mixed text/list order within legal paragraphs and resolve structured
  regulation amendment targets. The live Regnskapsloven §6-2 now follows source
  order; regulation targets appear in the public export.
- [ ] Preserve whole-document structural order. A separate mixed section/subsection
  counterexample still reorders content despite 100% token coverage. Do not claim
  the paragraph repair certifies an entire canonical document.
- [ ] Finish a versioned producer/consumer contract: ordered content, source and
  output identities, parser/formatter versions, exact membership and explicit
  unresolved content. Verify deterministic replay through independently installed
  packages; declare the publisher's loader dependency or remove that coupling.
- [ ] Preserve the existing JSONL display API with documented limits, and provide
  a versioned lossless amendment interface for history. Current export drops
  unknown targets and truncates instructions/replacement text; it is not a
  canonical reconstruction input.

## 3. Deliver evidence-backed history

The new history repository was a README-only placeholder at audit time. The
legacy builder uses current text as a 2001 baseline and substitutes publication
dates for unknown commencement; its tags are not verified historical snapshots.

| Open issue | Remaining deliverable and acceptance evidence |
|---|---|
| [history #1: reusable pipeline and history implementation](https://github.com/sondreskarsten/norwegian-laws-history/issues/1) | Implement a small law-and-regulation pilot using the repaired interface, immutable source provenance and independently known historical checkpoints. Separate source publication, observation/knowledge time and legal valid time; retain unknown or partial commencement and unsupported intervals explicitly. Do not import the legacy graph, tags or generated text as authoritative evidence. |
| [#3: orphan v2000](https://github.com/sondreskarsten/norwegian-laws/issues/3) | Replace the hardcoded version range with an explicit supported-version catalog. Stop presenting the disconnected v2000 graph as a verified version; retain existing refs until an explicit migration decision. |
| [#4: future-year ordering](https://github.com/sondreskarsten/norwegian-laws/issues/4) | Prevent future or unsupported years from appearing as completed historical snapshots. Verify the order and provenance of selectable checkpoints; the audit confirmed v2028 was behind v2026. |
| [#5: inaccurate point-in-time claims](https://github.com/sondreskarsten/norwegian-laws/issues/5) | Correct version-page, diff and Git examples to describe the actual evidence and limitations. Display source basis, knowledge cutoff, legal-date certainty and reconstruction status for each supported result. |
| [#6: missing repealed documents](https://github.com/sondreskarsten/norwegian-laws/issues/6) | Retain terminal texts and source evidence for documents leaving the current corpus. Record observed exit separately from proven legal repeal; preserve unknown legal dates. Verify retrieval of a repealed example and provide recovery links for unavailable periods. |
| [#7: unstable history publication](https://github.com/sondreskarsten/norwegian-laws/issues/7) | Publish stable, citable identities with idempotent updates, explicit correction/version policy and checked remote/LFS readback. Preserve legacy references during consumer migration. Force rebuilding is confirmed; the claim that every SHA changes every day was not supported by the September 25 run. |

## 4. Finish the reader experience

- [ ] [#8: search payload](https://github.com/sondreskarsten/norwegian-laws/issues/8)
  — reduce or explicitly separate the full-text download from lightweight search.
  The audit measured 29,717,270 decoded bytes for `search.json`; verify actual
  transferred bytes and usable results on a constrained mobile connection.
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
